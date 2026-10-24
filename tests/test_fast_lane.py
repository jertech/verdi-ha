# SPDX-License-Identifier: GPL-3.0-or-later
"""Fast lane: chosen lookups move off the station, and readiness follows them."""

import copy
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.verdi.const import CONF_FAST_LANE, CONF_PAGED
from tests import responses as r
from tests.conftest import fake_command, setup_with_token

PERSONNEL = "configuration/persons/commands"
VEHICLES = "configuration/vehicles/commands"
READINESS = "configuration/readinesses/commands"
NOW = "2026-06-15T12:00:00+00:00"


@pytest.fixture
def api():
    calls: list = []
    responses = r.all_ok()
    responses[PERSONNEL] = copy.deepcopy(r.PERSONNEL)
    responses[PERSONNEL]["personGroups"][0]["persons"][1]["isOnIntervention"] = False  # quiet station
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(responses, calls)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        yield responses, calls


def paths(calls: list) -> list[str]:
    return [c[0] for c in calls if c[0] != "mobile/app/commands"]


async def test_vehicle_change_on_fast_lane_marks_station_readiness(
    hass: HomeAssistant, config_entry, api, freezer
):
    responses, calls = api
    freezer.move_to(NOW)
    await setup_with_token(
        hass, config_entry, options={CONF_FAST_LANE: ["vehicles"], CONF_PAGED: True}
    )
    station = config_entry.runtime_data
    fast = station.fast
    assert fast is not None
    # The chosen lookup moved off the station onto the fast lane.
    assert "vehicles" not in station.lookups
    assert "vehicles" in fast.lookups
    # Readiness was fetched at startup, so it is not due now.
    assert station.lookups["readiness"].schedule.reason(dt_util.now()) is None

    # A vehicle starts an intervention; the fast lane picks it up at fast_interval.
    responses[VEHICLES] = copy.deepcopy(r.VEHICLES)
    responses[VEHICLES]["data"][0]["isOnIntervention"] = True
    freezer.tick(timedelta(seconds=15))
    await fast.async_refresh()
    assert VEHICLES in paths(calls)

    # The change on the fast lane marked the station's readiness lookup due.
    assert station.lookups["readiness"].schedule.reason(dt_util.now()) == "trigger:vehicles"


async def test_fast_lane_empty_by_default(hass: HomeAssistant, config_entry, api):
    await setup_with_token(hass, config_entry)
    station = config_entry.runtime_data
    # Default fast lane holds only "paged" (a no-op until Task 4), so nothing moves.
    assert station.fast is None
    assert "vehicles" in station.lookups
    assert "personnel" in station.lookups


async def test_fast_lane_runs_vehicles_at_fast_interval(
    hass: HomeAssistant, config_entry, api, freezer
):
    _, calls = api
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry, options={CONF_FAST_LANE: ["vehicles"]})
    fast = config_entry.runtime_data.fast
    # Active because vehicles are on it: scheduled at the fast interval (15 s default).
    assert fast.update_interval == timedelta(seconds=15)
    calls.clear()
    freezer.tick(timedelta(seconds=15))
    await fast.async_refresh()
    assert paths(calls) == [VEHICLES]


async def test_pausing_keeps_vehicles_on_the_fast_lane(
    hass: HomeAssistant, config_entry, api, freezer
):
    _, calls = api
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry, options={CONF_FAST_LANE: ["vehicles"]})
    fast = config_entry.runtime_data.fast
    # Pausing suppresses only the (future) paged lookup; the coordinator keeps polling vehicles.
    fast.paused = True
    calls.clear()
    freezer.tick(timedelta(seconds=15))
    await fast.async_refresh()
    assert paths(calls) == [VEHICLES]
    assert fast.update_interval == timedelta(seconds=15)
