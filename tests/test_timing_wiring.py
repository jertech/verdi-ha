# SPDX-License-Identifier: GPL-3.0-or-later
"""The timing log is fed from the fetches, saved, kept across a reload and removed with the entry."""

import copy
import logging
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.verdi.api import APP_ROUTE
from custom_components.verdi.timing import PAGE_FIELDS, TimingLog
from tests import responses as r
from tests.conftest import fake_command, setup_with_token

PERSONNEL, VEHICLES = "configuration/persons/commands", "configuration/vehicles/commands"
INTERVENTION = "GetPersonCurrentInterventionInformationCommand"
NOW = "2026-06-15T12:00:00+00:00"


@pytest.fixture
def api():
    calls: list = []
    responses = r.all_ok()
    responses[PERSONNEL] = copy.deepcopy(r.PERSONNEL)
    responses[PERSONNEL]["personGroups"][0]["persons"][1]["isOnIntervention"] = False
    responses[VEHICLES] = copy.deepcopy(r.VEHICLES)
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(responses, calls)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        yield responses


async def wait(hass: HomeAssistant, freezer, seconds: float) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def key(entry) -> str:
    return f"verdi.timing.{entry.entry_id}"


async def test_page_record_from_setup(hass: HomeAssistant, config_entry, api, freezer):
    api[APP_ROUTE][INTERVENTION] = r.CURRENT_INTERVENTION
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    page = config_entry.runtime_data.timing.page
    assert page["paged_on"] is not None and page["startup"] is True
    assert page["fields"] == dict.fromkeys(PAGE_FIELDS, True)
    assert "station.name" in page["keys"]


async def test_own_flag_feeds_the_page(hass: HomeAssistant, config_entry, api, freezer):
    api[PERSONNEL]["personGroups"][0]["persons"][0]["isOnIntervention"] = True
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    assert config_entry.runtime_data.timing.page["own_on"] is not None


async def test_station_intervention_in_one_tick(hass: HomeAssistant, config_entry, api, freezer):
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    api[VEHICLES]["data"][0]["isOnIntervention"] = True
    api[PERSONNEL]["personGroups"][0]["persons"][1]["isOnIntervention"] = True
    await wait(hass, freezer, 60)
    shown = config_entry.runtime_data.timing.diagnostics()["station_interventions"][0]
    assert shown["persons_before"] == 0 and shown["persons_after_vehicle_s"] == 0.0


async def test_page_record_survives_a_reload(hass: HomeAssistant, config_entry, api, freezer, hass_storage):
    api[APP_ROUTE][INTERVENTION] = r.CURRENT_INTERVENTION
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    first = config_entry.runtime_data.timing.page["paged_on"]
    await wait(hass, freezer, 6)
    assert hass_storage[key(config_entry)]["data"]["page"]["paged_on"] == first
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    timing = config_entry.runtime_data.timing
    assert timing.page["paged_on"] == first and timing.pages == []


async def test_store_removed_with_the_entry(hass: HomeAssistant, config_entry, api, freezer, hass_storage):
    api[APP_ROUTE][INTERVENTION] = r.CURRENT_INTERVENTION
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    await wait(hass, freezer, 6)
    assert key(config_entry) in hass_storage
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert key(config_entry) not in hass_storage


async def test_reload_right_after_a_change_keeps_the_record(hass: HomeAssistant, config_entry, api, freezer):
    api[APP_ROUTE][INTERVENTION] = r.CURRENT_INTERVENTION
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    first = config_entry.runtime_data.timing.page["paged_on"]
    await wait(hass, freezer, 1)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    timing = config_entry.runtime_data.timing
    assert timing.page["paged_on"] == first and timing.pages == []


async def test_remove_right_after_a_change_leaves_no_store(
    hass: HomeAssistant, config_entry, api, freezer, hass_storage
):
    api[APP_ROUTE][INTERVENTION] = r.CURRENT_INTERVENTION
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    await wait(hass, freezer, 1)
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    await wait(hass, freezer, 10)
    assert key(config_entry) not in hass_storage


def _warnings(caplog) -> list[str]:
    return [
        m.getMessage()
        for m in caplog.records
        if m.levelno == logging.WARNING and m.name == "custom_components.verdi.signals"
    ]


async def test_a_bad_saved_record_cannot_break_setup(
    hass: HomeAssistant, config_entry, api, freezer, hass_storage, caplog
):
    hass_storage[key(config_entry)] = {
        "version": 1,
        "minor_version": 1,
        "key": key(config_entry),
        "data": {
            "pages": [],
            "page": None,
            "interventions": [],
            "intervention": {"opened": "not a time", "persons_before": "3", "vehicle_on": NOW},
        },
    }
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    assert config_entry.state.value == "loaded"
    assert config_entry.runtime_data.timing.intervention is None
    assert _warnings(caplog) == []


async def test_a_failing_feed_is_contained_and_logged_once(
    hass: HomeAssistant, config_entry, api, freezer, caplog
):
    def boom(*args, **kwargs):
        raise RuntimeError("secret value 123")

    with patch.object(TimingLog, "persons", boom):
        freezer.move_to(NOW)
        await setup_with_token(hass, config_entry)
        assert config_entry.state.value == "loaded"
        coordinator = config_entry.runtime_data
        before = coordinator.data["vehicles"]
        api[VEHICLES]["data"][0]["isOnIntervention"] = True
        await wait(hass, freezer, 60)
        await wait(hass, freezer, 60)
    assert coordinator.last_update_success
    assert coordinator.data["vehicles"] != before  # the run's data still arrived
    warnings = _warnings(caplog)
    assert len(warnings) == 1
    assert "RuntimeError" in warnings[0]
    assert "secret" not in caplog.text and "123" not in warnings[0]


async def test_unload_detaches_the_save_callback(hass: HomeAssistant, config_entry, api, freezer):
    api[APP_ROUTE][INTERVENTION] = r.CURRENT_INTERVENTION
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    timing = config_entry.runtime_data.timing
    assert timing.on_change is not None
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert timing.on_change is None


async def test_a_failing_feed_saves_only_when_it_clears_a_record(
    hass: HomeAssistant, config_entry, api, freezer
):
    def boom(*args, **kwargs):
        raise RuntimeError("feed")

    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    timing = config_entry.runtime_data.timing
    saves: list[int] = []
    timing.on_change = lambda: saves.append(1)
    timing.intervention = {"opened": NOW}
    with patch.object(TimingLog, "persons", boom):
        await wait(hass, freezer, 60)
        await wait(hass, freezer, 60)
    assert timing.intervention is None
    assert saves == [1]
