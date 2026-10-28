# SPDX-License-Identifier: GPL-3.0-or-later
"""The Paged lookup on the fast lane and the Paged binary sensor."""

import copy
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.verdi.api import APP_ROUTE, VerdiError
from tests import responses as r
from tests.conftest import fake_command, setup_with_token

PERSONNEL = "configuration/persons/commands"
VEHICLES = "configuration/vehicles/commands"
INTERVENTION = "GetPersonCurrentInterventionInformationCommand"
NOW = "2026-06-15T12:00:00+00:00"


def me(responses: dict) -> dict:
    return responses[PERSONNEL]["personGroups"][0]["persons"][0]


def interventions(calls: list) -> int:
    return sum(1 for c in calls if c[0] == APP_ROUTE and c[1] == INTERVENTION)


@pytest.fixture
def api():
    calls: list = []
    responses = r.all_ok()
    responses[PERSONNEL] = copy.deepcopy(r.PERSONNEL)
    responses[PERSONNEL]["personGroups"][0]["persons"][1]["isOnIntervention"] = False
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(responses, calls)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        yield responses, calls


async def test_paged_on_with_safe_attributes(hass: HomeAssistant, config_entry, api, freezer):
    responses, _ = api
    responses[APP_ROUTE][INTERVENTION] = r.CURRENT_INTERVENTION
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    state = hass.states.get("binary_sensor.verdi_paged")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["station"] == "Station 1"
    assert state.attributes["vehicle"] == "P100"
    assert state.attributes["incident"] == "Fire"
    assert state.attributes["crew_function"] == "Driver"
    assert state.attributes["confirmation"] == "Confirmed"
    # The sensitive fields the parser drops never reach the attributes.
    for hidden in ("address", "city", "latitude", "longitude", "callerName", "info", "radioGroup"):
        assert hidden not in state.attributes
    shown = repr(dict(state.attributes))
    for identifier in ("iv-1", "st-1", "cf-9", "cc-1"):
        assert identifier not in shown


async def test_paged_off_but_available_when_not_paged(hass: HomeAssistant, config_entry, api, freezer):
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)  # all_ok returns an empty current intervention
    state = hass.states.get("binary_sensor.verdi_paged")
    assert state is not None
    assert state.state == "off"  # not "unavailable": no page means not paged, not missing data


async def test_paged_absent_when_switch_off(hass: HomeAssistant, config_entry, api, freezer):
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry, options={"paged": False})
    assert hass.states.get("binary_sensor.verdi_paged") is None
    assert config_entry.runtime_data.fast is None


async def test_paged_not_due_while_non_pageable(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls = api
    me(responses)["currentAvailability"]["description"] = {"default": "Niet beschikbaar"}
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    fast = config_entry.runtime_data.fast
    assert fast is not None
    # The non-pageable own line paused the paged lookup at the first personnel fetch.
    assert fast.paused is True
    assert fast.lookups["paged"].schedule.reason(dt_util.now(), tick=True) is None
    # A fast-lane poll does not fetch the paged lookup while paused.
    calls.clear()
    freezer.tick(timedelta(seconds=15))
    await fast.async_refresh()
    assert interventions(calls) == 0


async def test_becoming_pageable_fetches_paged(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls = api
    me(responses)["currentAvailability"]["description"] = {"default": "Niet beschikbaar"}
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    fast = config_entry.runtime_data.fast
    assert fast.paused is True
    # Become pageable again; the personnel fetch resumes paging and marks paged due at once.
    me(responses)["currentAvailability"]["description"] = {"default": "Available"}
    calls.clear()
    await config_entry.runtime_data.async_refresh_lookup("personnel")
    await hass.async_block_till_done()
    assert fast.paused is False
    assert interventions(calls) >= 1  # marked due and polled


async def test_pause_suppresses_only_paged(hass: HomeAssistant, config_entry, api, freezer):
    _, calls = api
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry, options={"fast_lane": ["vehicles", "paged"]})
    fast = config_entry.runtime_data.fast
    assert fast is not None and "vehicles" in fast.lookups and "paged" in fast.lookups
    fast.paused = True
    calls.clear()
    freezer.tick(timedelta(seconds=15))
    await fast.async_refresh()
    # Vehicles keep polling on the shared lane; only the paged lookup is suppressed.
    assert any(c[0] == VEHICLES for c in calls)
    assert interventions(calls) == 0


async def test_pause_waits_until_the_page_ends(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls = api
    responses[APP_ROUTE][INTERVENTION] = r.CURRENT_INTERVENTION
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    station = config_entry.runtime_data
    fast = station.fast
    me(responses)["currentAvailability"]["description"] = {"default": "Niet beschikbaar"}
    await station.async_refresh_lookup("personnel")
    await hass.async_block_till_done()
    assert fast.paused is False  # still paged: keep polling until the page ends
    calls.clear()
    freezer.tick(timedelta(seconds=15))
    await fast.async_refresh()
    assert interventions(calls) == 1
    assert hass.states.get("binary_sensor.verdi_paged").state == "on"
    responses[APP_ROUTE][INTERVENTION] = r.CURRENT_INTERVENTION_NONE
    freezer.tick(timedelta(seconds=15))
    await fast.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.verdi_paged").state == "off"
    assert fast.paused is True


async def test_pageable_again_cancels_a_pending_pause(hass: HomeAssistant, config_entry, api, freezer):
    responses, _ = api
    responses[APP_ROUTE][INTERVENTION] = r.CURRENT_INTERVENTION
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    station = config_entry.runtime_data
    fast = station.fast
    me(responses)["currentAvailability"]["description"] = {"default": "Niet beschikbaar"}
    await station.async_refresh_lookup("personnel")
    me(responses)["currentAvailability"]["description"] = {"default": "Available"}
    await station.async_refresh_lookup("personnel")
    await hass.async_block_till_done()
    responses[APP_ROUTE][INTERVENTION] = r.CURRENT_INTERVENTION_NONE
    freezer.tick(timedelta(seconds=15))
    await fast.async_refresh()
    await hass.async_block_till_done()
    assert fast.paused is False


async def test_failing_paged_fetch_does_not_pause(hass: HomeAssistant, config_entry, api, freezer):
    responses, _ = api
    responses[APP_ROUTE][INTERVENTION] = r.CURRENT_INTERVENTION
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    station = config_entry.runtime_data
    fast = station.fast
    me(responses)["currentAvailability"]["description"] = {"default": "Niet beschikbaar"}
    await station.async_refresh_lookup("personnel")
    responses[APP_ROUTE][INTERVENTION] = VerdiError("mobile/app/commands: HTTP 500")
    freezer.tick(timedelta(seconds=15))
    await fast.async_refresh()
    await hass.async_block_till_done()
    assert fast.paused is False  # no answer is not "no page": keep polling


async def test_cancelled_pause_keeps_the_timing_baseline(hass: HomeAssistant, config_entry, api, freezer):
    responses, _ = api
    responses[APP_ROUTE][INTERVENTION] = r.CURRENT_INTERVENTION
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    station = config_entry.runtime_data
    fast = station.fast
    me(responses)["currentAvailability"]["description"] = {"default": "Niet beschikbaar"}
    await station.async_refresh_lookup("personnel")
    responses[APP_ROUTE][INTERVENTION] = r.CURRENT_INTERVENTION_NONE
    me(responses)["currentAvailability"]["description"] = {"default": "Available"}
    await station.async_refresh_lookup("personnel")
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=15))
    await fast.async_refresh()
    await hass.async_block_till_done()
    timing = station.timing
    record = timing.page or timing.pages[0]
    assert record["paged_off"] is not None
    assert record["interrupted"] is False  # the lookup never stopped, so the end is not late


async def test_a_page_arriving_while_paused_keeps_polling_until_it_ends(
    hass: HomeAssistant, config_entry, api, freezer
):
    responses, _ = api
    me(responses)["currentAvailability"]["description"] = {"default": "Niet beschikbaar"}
    freezer.move_to(NOW)
    await setup_with_token(hass, config_entry)
    fast = config_entry.runtime_data.fast
    signals = fast.on_fetched.__self__
    assert fast.paused is True and signals._pageable is False
    # A paged fetch that began before the pause decision returns a page.
    signals._paged_fetched({"alarm_time": None}, None)
    assert fast.paused is False and signals._pause_pending is True
    signals._paged_fetched(None, {"alarm_time": None})
    assert fast.paused is True and signals._pause_pending is False
