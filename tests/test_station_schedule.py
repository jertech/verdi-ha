# SPDX-License-Identifier: GPL-3.0-or-later
"""Station lookups: every tick, on changes, at announced times and after safety intervals."""

import copy
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from tests import responses as r
from tests.conftest import fake_command, setup_with_token

READINESS, PERSONNEL = "configuration/readinesses/commands", "configuration/persons/commands"
VEHICLES, TEAMS, ROSTER = (
    "configuration/vehicles/commands",
    "configuration/team/groups/commands",
    "planning/functioncalendars/commands",
)
NOW = "2026-06-15T12:00:00+00:00"


@pytest.fixture
def api():
    calls: list = []
    responses = r.all_ok()
    responses[PERSONNEL] = copy.deepcopy(r.PERSONNEL)
    responses[PERSONNEL]["personGroups"][0]["persons"][1]["isOnIntervention"] = False  # quiet station
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(responses, calls)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER) as user,
    ):
        yield responses, calls, user


def paths(calls: list) -> list[str]:
    return [c[0] for c in calls if c[0] != "mobile/app/commands"]


async def run(hass: HomeAssistant, freezer, seconds: float) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_quiet_tick_calls_personnel_and_vehicles(hass: HomeAssistant, config_entry, api, freezer):
    _, calls, user = api
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    assert user.call_count == 1
    calls.clear()
    await run(hass, freezer, 60)
    assert paths(calls) == [PERSONNEL, VEHICLES]
    assert config_entry.runtime_data.update_interval == timedelta(seconds=60)


async def test_changes_fetch_readiness_in_the_same_run(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    calls.clear()
    responses[PERSONNEL]["personGroups"][0]["persons"][0]["currentAvailability"]["description"] = {
        "default": "Not available"
    }
    await run(hass, freezer, 60)
    assert paths(calls) == [PERSONNEL, VEHICLES, READINESS]
    calls.clear()
    responses[VEHICLES] = copy.deepcopy(r.VEHICLES)
    responses[VEHICLES]["data"][0]["currentAvailability"]["description"] = {"default": "Workshop"}
    await run(hass, freezer, 60)
    assert paths(calls) == [PERSONNEL, VEHICLES, READINESS]


async def test_readiness_safety_interval(hass: HomeAssistant, config_entry, api, freezer):
    _, calls, _ = api
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    calls.clear()
    for _ in range(15):
        await run(hass, freezer, 60)
    assert paths(calls).count(READINESS) == 1


async def test_teams_at_rotation_and_roster_at_boundary(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    responses[TEAMS] = copy.deepcopy(r.TEAMS)
    responses[TEAMS]["teamsOnDuty"][0]["nextRotation"] = "2026-06-15T12:10:00+00:00"
    responses[ROSTER] = copy.deepcopy(r.ROSTER)
    responses[ROSTER]["items"][0]["current"]["end"] = "2026-06-15T12:20:00+00:00"
    responses[ROSTER]["items"][0]["next"]["start"] = "2026-06-15T12:20:00+00:00"
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    calls.clear()
    for _ in range(10):
        await run(hass, freezer, 60)
    assert TEAMS not in paths(calls)
    await run(hass, freezer, 75)
    assert TEAMS in paths(calls)
    calls.clear()
    for _ in range(10):
        await run(hass, freezer, 60)
    assert paths(calls).count(ROSTER) == 1


async def test_intervention_tick(hass: HomeAssistant, config_entry, api, freezer):
    responses, _, _ = api
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    responses[VEHICLES] = copy.deepcopy(r.VEHICLES)
    responses[VEHICLES]["data"][0]["isOnIntervention"] = True
    await run(hass, freezer, 60)
    assert config_entry.runtime_data.update_interval == timedelta(seconds=30)


async def test_your_roster_shift_is_marked(hass: HomeAssistant, config_entry, api):
    responses, _, _ = api
    responses[ROSTER] = copy.deepcopy(r.ROSTER)
    responses[ROSTER]["items"][0]["next"]["personId"] = "me-1"
    await setup_with_token(hass, config_entry)
    roster = config_entry.runtime_data.data["roster"]
    assert roster[0]["next"]["mine"] is True
    assert roster[0]["current"]["mine"] is False
