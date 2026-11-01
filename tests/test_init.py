# SPDX-License-Identifier: GPL-3.0-or-later
"""Setup, token grace period, reauth, repairs and migration."""

import time
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.verdi.api import VerdiAuthError
from custom_components.verdi.const import CONF_STATION_ID, DOMAIN, TOKEN_GRACE_SECONDS
from custom_components.verdi.guard import get_guard
from custom_components.verdi.token import get_store
from tests import responses as r
from tests.conftest import DATA, MidRandom, fake_command, make_token, setup_with_token


async def test_setup_creates_entities(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("binary_sensor.verdi_readiness_pump_1").state == "on"
    assert hass.states.get("sensor.verdi_p100").state == "Available"
    assert hass.states.get("sensor.verdi_personnel").state == "2"
    assert hass.states.get("sensor.verdi_team_on_duty_north").state == "Team A"
    assert hass.states.get("binary_sensor.verdi_p100_on_intervention").state == "off"
    assert hass.states.get("sensor.verdi_on_duty_officer").state == "filled"
    assert hass.states.get("sensor.verdi_on_duty_driver").state == "open"
    assert hass.states.get("sensor.verdi_token_expires").state != "unknown"
    assert hass.states.get("calendar.verdi_roster") is not None


async def test_waits_for_token_during_grace(hass: HomeAssistant, config_entry, mock_api):
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not list(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_reauth_after_grace(hass: HomeAssistant, config_entry, mock_api):
    config_entry.add_to_hass(hass)
    get_store(hass).started = time.monotonic() - 3600
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert list(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_reauth_when_grace_ends(hass: HomeAssistant, config_entry, mock_api):
    # HA's own retry of a waiting entry can be up to 10 minutes away; keep it from running.
    with patch("homeassistant.config_entries.async_call_later"):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.SETUP_RETRY
        get_store(hass).started = time.monotonic() - TOKEN_GRACE_SECONDS - 1
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=TOKEN_GRACE_SECONDS + 5))
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert list(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_rejected_token_at_setup_retries_first(hass: HomeAssistant, config_entry):
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(VerdiAuthError("401"))),
        patch("custom_components.verdi.api.VerdiApi.current_user", side_effect=VerdiAuthError("401")),
    ):
        config_entry.add_to_hass(hass)
        get_store(hass).tokens[config_entry.entry_id] = make_token()
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not list(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


@pytest.mark.parametrize("block", ["retry_after", "cap"])
async def test_setup_waiting_for_the_guard_retries(hass: HomeAssistant, config_entry, block):
    """The guard outlives reloads: a setup inside its wait must not end up without entities."""
    calls: list = []
    config_entry.add_to_hass(hass)
    guard = get_guard(hass, config_entry.entry_id, MidRandom())
    if block == "retry_after":
        guard.wait(600)
    else:
        for _ in range(30):
            guard.record_call()
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(r.all_ok(), calls)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER) as user,
    ):
        get_store(hass).tokens[config_entry.entry_id] = make_token()
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert calls == []
    assert user.call_count == 0


async def test_expired_token_is_not_used(hass: HomeAssistant, config_entry, mock_api):
    config_entry.add_to_hass(hass)
    get_store(hass).tokens[config_entry.entry_id] = make_token(lifetime=30)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_missing_config_raises_repair(hass: HomeAssistant, mock_api):
    data = {k: v for k, v in DATA.items() if k != CONF_STATION_ID}
    entry = MockConfigEntry(domain=DOMAIN, version=2, data=data, unique_id="x")
    entry.add_to_hass(hass)
    get_store(hass).tokens[entry.entry_id] = make_token()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"missing_config_{entry.entry_id}")


async def test_migration_v1_drops_tokens_and_keeps_names(hass: HomeAssistant, mock_api):
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        title="Verdi",
        unique_id="station-1",
        data={**DATA, "token": make_token(), "token_file": "/share/verdi_token.txt"},
        options={"scan_interval": 15, "person_id": "me-1"},
    )
    entry.add_to_hass(hass)
    get_store(hass).tokens[entry.entry_id] = make_token()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.version == 4
    assert entry.data == DATA
    assert entry.options == {"scan_interval": 60, "show_names": True, **SWITCHES_ON}
    assert hass.states.get("sensor.verdi_on_duty_officer").state == "Sam Sample"


SWITCHES_ON = {
    "my_availability": True,
    "paged": True,
    "pre_alert": False,
    "garrison": False,
    "my_events": True,
    "statistics": True,
    "status_changes": False,
    "calendar_edit": False,
}


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            {"scan_interval": 120, "show_names": False, "personal_data": True, "personal_interval": 30,
             "events_interval": 10, "statistics_interval": 6},
            {"scan_interval": 60, "show_names": False, "events_interval": 60, "statistics_interval": 24,
             **SWITCHES_ON},
        ),
        (
            {"scan_interval": 45, "personal_data": False, "events_interval": 5, "statistics_interval": 12},
            {"scan_interval": 45, "events_interval": 10, "statistics_interval": 12,
             **dict.fromkeys(SWITCHES_ON, False)},
        ),
        ({}, SWITCHES_ON),
    ],
)  # fmt: skip
async def test_migrate_v3_to_v4(hass: HomeAssistant, mock_api, old, new):
    entry = MockConfigEntry(
        domain=DOMAIN, version=3, title="Verdi", unique_id="station-1", data=dict(DATA), options=old
    )
    entry.add_to_hass(hass)
    get_store(hass).tokens[entry.entry_id] = make_token()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.version == 4
    assert entry.options == new


async def test_unload(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_rejected_token_retries_then_reauths(hass: HomeAssistant, config_entry, freezer):
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(VerdiAuthError("401"))),
        patch("custom_components.verdi.api.VerdiApi.current_user", side_effect=VerdiAuthError("401")),
    ):
        config_entry.add_to_hass(hass)
        get_store(hass).tokens[config_entry.entry_id] = make_token(lifetime=7200)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.SETUP_RETRY
        freezer.tick(timedelta(seconds=121))
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert list(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
