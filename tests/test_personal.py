# SPDX-License-Identifier: GPL-3.0-or-later
"""Your own data: which calls go out, in which language, and when statistics refresh."""

import copy
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.verdi.api import APP_COMMANDS, APP_ROUTE, VerdiError
from custom_components.verdi.personal import request_language
from custom_components.verdi.token import get_store
from tests import responses as r
from tests.conftest import ALL_OFF, fake_command, make_token, setup_with_token

STATS, EVENTS = "AppGetPersonStatisticsCommand", "AppGetUpcomingEventsCommand"
VEHICLES = "configuration/vehicles/commands"


@pytest.fixture
def api():
    calls: list = []
    responses = r.all_ok()
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(responses, calls)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER) as user,
    ):
        yield responses, calls, user


def app_calls(calls: list, command: str | None = None) -> list:
    return [c for c in calls if c[0] == APP_ROUTE and command in (None, c[1])]


async def tick(hass: HomeAssistant, freezer, seconds: float) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("language", "expected"), [("nl", "nl"), ("nl-BE", "nl"), ("fr", "fr"), ("de", "en"), ("en-GB", "en")]
)
async def test_request_language(hass: HomeAssistant, language, expected):
    hass.config.language = language
    assert request_language(hass) == expected


async def test_setup_calls_each_personal_lookup_once(hass: HomeAssistant, config_entry, api):
    _, calls, user = api
    hass.config.language = "fr"
    await setup_with_token(hass, config_entry)
    assert sorted(c[1] for c in app_calls(calls)) == sorted(APP_COMMANDS)
    assert {c[2] for c in app_calls(calls) if c[1] in (STATS, EVENTS)} == {"fr"}
    assert user.call_count == 1
    personal = config_entry.runtime_data.personal
    assert personal.fast.update_interval == timedelta(seconds=60)
    assert personal.events.update_interval == timedelta(minutes=60)
    assert personal.statistics.update_interval == timedelta(hours=24)


async def test_personal_data_off_makes_no_app_calls(hass: HomeAssistant, config_entry, api):
    _, calls, user = api
    await setup_with_token(hass, config_entry, options=ALL_OFF)
    assert app_calls(calls) == []
    assert user.call_count == 0
    assert config_entry.runtime_data.personal is None


async def test_statistics_refresh_after_intervention_changes(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    await setup_with_token(hass, config_entry)
    station = config_entry.runtime_data
    on_intervention = copy.deepcopy(r.VEHICLES)
    on_intervention["data"][0]["isOnIntervention"] = True
    responses[VEHICLES] = on_intervention
    await station.async_refresh_lookup("vehicles")
    await tick(hass, freezer, 60)
    responses[VEHICLES] = r.VEHICLES
    await station.async_refresh_lookup("vehicles")  # a second change restarts the wait
    await tick(hass, freezer, 61)
    assert len(app_calls(calls, STATS)) == 1  # only setup's
    await tick(hass, freezer, 60)
    assert len(app_calls(calls, STATS)) == 2


async def test_statistics_refresh_after_midnight(hass: HomeAssistant, config_entry, api, freezer):
    _, calls, _ = api
    await hass.config.async_set_time_zone("Europe/Brussels")
    freezer.move_to("2026-06-15T23:00:00+02:00")
    await setup_with_token(hass, config_entry)
    get_store(hass).tokens[config_entry.entry_id] = make_token(lifetime=7200)  # outlives the jump
    freezer.move_to("2026-06-16T00:05:00+02:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(app_calls(calls, STATS)) == 2


async def test_failed_person_lookup_is_retried(hass: HomeAssistant, config_entry, api, freezer):
    _, _, user = api
    user.side_effect = [
        VerdiError("security/users/authorize: HTTP 500"),
        VerdiError("security/users/authorize: HTTP 500"),
        r.CURRENT_USER,
    ]
    await setup_with_token(hass, config_entry)
    personal = config_entry.runtime_data.personal
    assert not personal.events.last_update_success  # first to ask, got the 500
    assert personal.statistics.last_update_success
    personal.events.async_add_listener(lambda: None)  # entities subscribe like this
    await tick(hass, freezer, 5 * 60 + 1)
    assert personal.events.last_update_success
    assert user.call_count == 3
