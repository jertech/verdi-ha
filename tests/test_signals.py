# SPDX-License-Identifier: GPL-3.0-or-later
"""Signals: your own line, watched vehicles and roster shifts mark your own lookups due."""

import copy
import zlib
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.verdi.api import APP_ROUTE, VerdiError
from custom_components.verdi.const import CONF_FAST_LANE, DAILY_JITTER, DAILY_OFFSET_MAX
from custom_components.verdi.schedule import AHEAD
from custom_components.verdi.token import get_store
from tests import responses as r
from tests.conftest import ALL_OFF, MidRandom, fake_command, make_token, setup_with_token
from tests.ha import async_fire_time_changed

INTERVENTION = "GetPersonCurrentInterventionInformationCommand"
AVAILABILITY = "GetPersonCurrentAvailabilityCarouselInformationCommand"
PRE, STATS, EVENTS = (
    "GetPersonCurrentPreAlertInformationCommand",
    "AppGetPersonStatisticsCommand",
    "AppGetUpcomingEventsCommand",
)
PERSONNEL, VEHICLES, ROSTER = (
    "configuration/persons/commands",
    "configuration/vehicles/commands",
    "planning/functioncalendars/commands",
)


def quiet() -> dict:
    responses = r.all_ok()
    responses[PERSONNEL] = copy.deepcopy(r.PERSONNEL)
    responses[PERSONNEL]["personGroups"][0]["persons"][1]["isOnIntervention"] = False
    responses[VEHICLES] = copy.deepcopy(r.VEHICLES)
    responses[ROSTER] = copy.deepcopy(r.ROSTER)
    return responses


@pytest.fixture
def api():
    calls: list = []
    responses = quiet()
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(responses, calls)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER) as user,
    ):
        yield responses, calls, user


def me(responses: dict) -> dict:
    return responses[PERSONNEL]["personGroups"][0]["persons"][0]


def count(calls: list, command: str) -> int:
    return sum(1 for c in calls if c[0] == APP_ROUTE and c[1] == command)


async def tick(hass: HomeAssistant, freezer, seconds: float) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def start(hass, entry, freezer, options=None) -> None:
    freezer.move_to("2026-06-15T12:00:00+00:00")
    await setup_with_token(hass, entry, options=options)
    get_store(hass).tokens[entry.entry_id] = make_token(lifetime=86400)


async def test_own_availability_change(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    await start(hass, config_entry, freezer)
    await tick(hass, freezer, 330)  # first events and statistics
    calls.clear()
    me(responses)["currentAvailability"]["description"] = {"default": "Not available"}
    responses[APP_ROUTE][AVAILABILITY] = {
        **r.CAROUSEL,
        "globalAvailability": {**r.CAROUSEL["globalAvailability"], "availabilityName": "Not available"},
    }
    await tick(hass, freezer, 60)
    assert count(calls, AVAILABILITY) == 1
    assert count(calls, EVENTS) == 0
    await tick(hass, freezer, 31)  # the changed availability makes events due 30 s later
    assert count(calls, EVENTS) == 1
    assert hass.states.get("sensor.verdi_my_availability").state == "Not available"


async def test_own_pre_alert(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    await start(hass, config_entry, freezer, options={"pre_alert": True})
    calls.clear()
    me(responses)["isOnPreAlert"] = True
    await tick(hass, freezer, 30)  # a person on pre-alert switches the station to the 30 s tick
    await tick(hass, freezer, 30)
    assert count(calls, PRE) >= 1
    before = count(calls, PRE)
    await tick(hass, freezer, 30)
    assert count(calls, PRE) == before + 1


async def test_missing_own_line_falls_back_to_every_tick(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    responses[PERSONNEL]["personGroups"][0]["persons"].pop(0)
    # Paged off: its fast-lane polls would share the per-minute call budget this test measures.
    await start(hass, config_entry, freezer, options={"paged": False})
    calls.clear()
    for _ in range(3):
        await tick(hass, freezer, 60)
    assert count(calls, AVAILABILITY) == 3


async def test_unknown_person_falls_back_and_retries(hass: HomeAssistant, config_entry, api, freezer):
    _, calls, user = api
    user.side_effect = [VerdiError("security/users/authorize: HTTP 500")] * 2 + [r.CURRENT_USER] * 5
    # Paged off: it also asks for the person GUID, which would race this test's own-line retry.
    await start(
        hass, config_entry, freezer, options={"my_events": False, "statistics": False, "paged": False}
    )
    calls.clear()
    for _ in range(3):
        await tick(hass, freezer, 60)
    assert count(calls, AVAILABILITY) == 3
    asked = user.call_count
    for _ in range(5):
        await tick(hass, freezer, 60)
    assert user.call_count == asked + 1  # once more within the five minutes
    calls.clear()
    await tick(hass, freezer, 60)
    assert count(calls, AVAILABILITY) == 0  # your line is found now


async def test_statistics_coalesce(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    await start(hass, config_entry, freezer)
    await tick(hass, freezer, 330)
    base = count(calls, STATS)
    station = config_entry.runtime_data
    responses[VEHICLES]["data"][0]["isOnIntervention"] = True
    await station.async_refresh_lookup("vehicles")
    await tick(hass, freezer, 100)
    responses[VEHICLES]["data"][0]["isOnIntervention"] = False
    await station.async_refresh_lookup("vehicles")
    await tick(hass, freezer, 149)  # 249 s after the first flip
    assert count(calls, STATS) == base
    await tick(hass, freezer, 2)
    assert count(calls, STATS) == base + 1


async def test_statistics_at_most_ten_minutes_after_the_first_trigger(
    hass: HomeAssistant, config_entry, api, freezer
):
    responses, calls, _ = api
    await start(hass, config_entry, freezer)
    await tick(hass, freezer, 330)
    base = count(calls, STATS)
    for i in range(6):
        responses[VEHICLES]["data"][0]["isOnIntervention"] = i % 2 == 0
        await config_entry.runtime_data.async_refresh_lookup("vehicles")
        await tick(hass, freezer, 100)
    await tick(hass, freezer, 1)
    assert count(calls, STATS) == base + 1


async def test_unwatched_vehicle_triggers_nothing(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    responses[VEHICLES]["data"].append({**r.VEHICLES["data"][0], "guid": "v2", "name": "P200"})
    await start(hass, config_entry, freezer, options={"watched_vehicles": ["v2"]})
    await tick(hass, freezer, 330)
    base = count(calls, STATS)
    responses[VEHICLES]["data"][0]["isOnIntervention"] = True
    await tick(hass, freezer, 60)
    assert config_entry.runtime_data.update_interval == timedelta(seconds=60)
    await tick(hass, freezer, 200)
    assert count(calls, STATS) == base


async def test_vanished_watched_vehicles_count_as_all(hass: HomeAssistant, config_entry, api, freezer):
    responses, _, _ = api
    await start(hass, config_entry, freezer, options={"watched_vehicles": ["gone"]})
    responses[VEHICLES]["data"][0]["isOnIntervention"] = True
    await tick(hass, freezer, 60)
    assert config_entry.runtime_data.update_interval == timedelta(seconds=30)


async def test_intervention_tick(hass: HomeAssistant, config_entry, api, freezer):
    responses, _, _ = api
    await start(hass, config_entry, freezer)
    assert config_entry.runtime_data.update_interval == timedelta(seconds=60)
    responses[PERSONNEL]["personGroups"][0]["persons"][1]["isOnIntervention"] = True
    await tick(hass, freezer, 60)
    assert config_entry.runtime_data.update_interval == timedelta(seconds=30)


async def test_daily_statistics(hass: HomeAssistant, config_entry, api, freezer):
    _, calls, _ = api
    await hass.config.async_set_time_zone("Europe/Brussels")
    freezer.move_to("2026-06-15T23:00:00+02:00")
    await setup_with_token(hass, config_entry)
    get_store(hass).tokens[config_entry.entry_id] = make_token(lifetime=86400)
    await tick(hass, freezer, 330)
    base = count(calls, STATS)
    offset = zlib.crc32(config_entry.entry_id.encode()) % DAILY_OFFSET_MAX + 450
    freezer.move_to("2026-06-16T00:05:00+02:00")
    await tick(hass, freezer, offset - 1)
    assert count(calls, STATS) == base
    await tick(hass, freezer, 2)
    assert count(calls, STATS) == base + 1


async def test_your_roster_shift_fetches_events(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    await start(hass, config_entry, freezer)
    await tick(hass, freezer, 330)
    base = count(calls, EVENTS)
    responses[ROSTER]["items"][0]["next"]["personId"] = "me-1"
    config_entry.runtime_data.mark_due("roster", "manual")
    await tick(hass, freezer, 60)
    await tick(hass, freezer, 31)
    assert count(calls, EVENTS) == base + 1


async def test_one_daily_refresh_per_night(hass: HomeAssistant, config_entry, api, freezer, monkeypatch):
    """A later jitter draw at rescheduling must not give a second refresh the same night."""
    _, calls, _ = api
    draws = iter([10.0, 800.0, 10.0, 800.0])

    class Jitter(MidRandom):
        def uniform(self, a, b):
            return next(draws) if (a, b) == (0, DAILY_JITTER) else super().uniform(a, b)

    monkeypatch.setattr("custom_components.verdi.schedule.make_rng", Jitter)
    await hass.config.async_set_time_zone("Europe/Brussels")
    freezer.move_to("2026-06-15T23:00:00+02:00")
    await setup_with_token(hass, config_entry)
    get_store(hass).tokens[config_entry.entry_id] = make_token(lifetime=86400 * 3)
    await tick(hass, freezer, 330)
    base = count(calls, STATS)
    offset = zlib.crc32(config_entry.entry_id.encode()) % DAILY_OFFSET_MAX
    freezer.move_to("2026-06-16T00:05:00+02:00")
    await tick(hass, freezer, offset + 11)
    assert count(calls, STATS) == base + 1
    await tick(hass, freezer, 1000)  # past the second draw of the same night
    assert count(calls, STATS) == base + 1
    freezer.move_to("2026-06-17T00:05:00+02:00")
    await tick(hass, freezer, offset + 11)
    assert count(calls, STATS) == base + 2


async def test_failed_statistics_do_not_skip_the_delay(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    await start(hass, config_entry, freezer)
    await tick(hass, freezer, 330)
    base = count(calls, STATS)
    responses[APP_ROUTE][STATS] = VerdiError("down")
    responses[VEHICLES]["data"][0]["isOnIntervention"] = True
    await config_entry.runtime_data.async_refresh_lookup("vehicles")
    await tick(hass, freezer, 151)  # the failed fetch
    assert count(calls, STATS) == base + 1
    await tick(hass, freezer, 700)  # still failing, retried every 300 s; past 600 s after the first flip
    responses[APP_ROUTE][STATS] = r.all_ok()[APP_ROUTE][STATS]
    before = count(calls, STATS)
    responses[VEHICLES]["data"][0]["isOnIntervention"] = False
    await config_entry.runtime_data.async_refresh_lookup("vehicles")
    await tick(hass, freezer, 140)
    assert count(calls, STATS) == before
    await tick(hass, freezer, 11)
    assert count(calls, STATS) == before + 1


NAMES = {item["guid"]: item["text"] for item in r.AVAILABILITIES["data"]}
LIST = "domaindata/person/availabilities/displayitems"


@pytest.fixture
def filtered():
    """Personnel lists only persons whose availability was requested, as Verdi does. You are on
    a listed availability that isn't configured."""
    calls: list = []
    responses = quiet()
    me(responses)["currentAvailability"]["description"] = {"default": "Not available"}
    inner = fake_command(responses, calls)

    async def command(self, path, body):
        value = await inner(self, path, body)
        if path == PERSONNEL:
            wanted = {NAMES.get(i) for i in body["availabilityFilter"]}
            value = copy.deepcopy(value)
            for group in value["personGroups"]:
                group["persons"] = [
                    p
                    for p in group["persons"]
                    if p["currentAvailability"]["description"]["default"] in wanted
                ]
        return value

    with (
        patch("custom_components.verdi.api.VerdiApi.command", command),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        yield responses, calls


async def test_own_line_on_an_unconfigured_availability(hass: HomeAssistant, config_entry, filtered, freezer):
    _, calls = filtered
    await start(hass, config_entry, freezer)
    calls.clear()
    for _ in range(3):
        await tick(hass, freezer, 60)
    assert count(calls, AVAILABILITY) == 0  # no fallback: your line is listed
    assert sum(1 for c in calls if c[0] == PERSONNEL) == 3


async def test_list_failure_falls_back_and_retries(hass: HomeAssistant, config_entry, filtered, freezer):
    responses, calls = filtered
    responses[LIST] = VerdiError(f"{LIST}: HTTP 500")
    # Paged off: its fast-lane polls would share the per-minute call budget this test measures.
    await start(
        hass, config_entry, freezer, options={"my_events": False, "statistics": False, "paged": False}
    )
    calls.clear()
    for _ in range(3):
        await tick(hass, freezer, 60)
    assert count(calls, AVAILABILITY) == 3  # as in 0.8.1: your line is filtered out
    assert sum(1 for c in calls if c[0] == LIST) == 0  # asked again only after five minutes
    responses[LIST] = r.AVAILABILITIES
    for _ in range(3):
        await tick(hass, freezer, 60)
    assert sum(1 for c in calls if c[0] == LIST) == 2  # the plannable and the full list
    calls.clear()
    await tick(hass, freezer, 60)
    assert count(calls, AVAILABILITY) == 0  # your line is found now


async def test_list_failure_retried_without_personal_data(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, user = api
    responses[LIST] = VerdiError(f"{LIST}: HTTP 500")
    await start(hass, config_entry, freezer, options=ALL_OFF)
    station = config_entry.runtime_data
    assert station.availabilities.listed is None
    asked = user.call_count
    calls.clear()
    for _ in range(3):
        await tick(hass, freezer, 60)
    assert sum(1 for c in calls if c[0] == LIST) == 0  # asked again only after five minutes
    responses[LIST] = r.AVAILABILITIES
    for _ in range(3):
        await tick(hass, freezer, 60)
    assert sum(1 for c in calls if c[0] == LIST) == 2  # the plannable and the full list
    assert station.availabilities.listed is not None
    assert user.call_count == asked  # no personal data: the retry never asks for your person GUID


async def test_list_failure_retried_with_your_line_present(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, user = api
    responses[LIST] = VerdiError(f"{LIST}: HTTP 500")
    # Paged off: its fast-lane polls would share the per-minute call budget this test measures.
    await start(
        hass, config_entry, freezer, options={"my_events": False, "statistics": False, "paged": False}
    )
    station = config_entry.runtime_data
    assert station.availabilities.listed is None
    assert station.person.value is not None
    asked = user.call_count
    calls.clear()
    for _ in range(3):
        await tick(hass, freezer, 60)
    assert count(calls, AVAILABILITY) == 0  # your line is listed: no fallback
    assert sum(1 for c in calls if c[0] == LIST) == 0  # asked again only after five minutes
    responses[LIST] = r.AVAILABILITIES
    for _ in range(3):
        await tick(hass, freezer, 60)
    assert sum(1 for c in calls if c[0] == LIST) == 2  # the plannable and the full list
    assert station.availabilities.listed is not None
    assert user.call_count == asked  # the person GUID is known: not asked again


async def test_vehicle_on_fast_lane_still_switches_the_pace(hass: HomeAssistant, config_entry, api, freezer):
    responses, _, _ = api
    await start(hass, config_entry, freezer, options={CONF_FAST_LANE: ["vehicles"]})
    station = config_entry.runtime_data
    fast = station.fast
    assert fast is not None and "vehicles" in fast.lookups and "vehicles" not in station.lookups
    assert station.update_interval == timedelta(seconds=60)
    responses[VEHICLES]["data"][0]["isOnIntervention"] = True
    await fast.async_refresh_lookup("vehicles")
    await hass.async_block_till_done()
    # The watched vehicle's change on the fast lane still paces the station as an intervention:
    # the fast-lane run set the flag, and the station adopts the quicker tick on its next run.
    assert station.intervention is True
    await tick(hass, freezer, 60)
    assert station.update_interval == timedelta(seconds=30)


async def test_vehicle_on_fast_lane_still_fires_statistics(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    await start(hass, config_entry, freezer, options={CONF_FAST_LANE: ["vehicles"]})
    await tick(hass, freezer, 330)  # first events and statistics
    fast = config_entry.runtime_data.fast
    base = count(calls, STATS)
    responses[VEHICLES]["data"][0]["isOnIntervention"] = True
    await fast.async_refresh_lookup("vehicles")
    await tick(hass, freezer, 151)  # the moved lookup still triggers the statistics refresh
    assert count(calls, STATS) == base + 1


async def test_late_person_id_fixes_roster_mine_without_events(
    hass: HomeAssistant, config_entry, api, freezer
):
    responses, calls, user = api
    responses[ROSTER]["items"][0]["next"]["personId"] = "me-1"
    user.side_effect = VerdiError("down")
    await start(hass, config_entry, freezer)
    coordinator = config_entry.runtime_data
    assert coordinator.person.value is None
    await tick(hass, freezer, 330)
    assert coordinator.data["roster"]
    assert not any((i["next"] or {}).get("mine") for i in coordinator.data["roster"])
    calls.clear()
    user.side_effect = None
    user.return_value = r.CURRENT_USER
    await coordinator.person.get()
    assert coordinator.data["roster"][0]["next"]["mine"] is True
    assert coordinator.lookups["roster"].schedule.last_reason is not None
    await tick(hass, freezer, 60)
    await tick(hass, freezer, 31)
    assert count(calls, EVENTS) == 0


async def test_paged_on_refreshes_your_own_data(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    await start(hass, config_entry, freezer, options={"pre_alert": True})
    await tick(hass, freezer, 330)  # first events and statistics
    fast = config_entry.runtime_data.fast
    calls.clear()
    responses[APP_ROUTE][INTERVENTION] = r.CURRENT_INTERVENTION
    await fast.async_refresh_lookup("paged")
    await hass.async_block_till_done()
    assert count(calls, AVAILABILITY) == 1
    assert count(calls, PRE) == 1
    assert count(calls, STATS) == 0
    await tick(hass, freezer, 151)  # 120 s after the page, plus the trigger delay
    assert count(calls, STATS) == 1


SENSOR = "sensor.verdi_my_availability"


def ends(responses: dict, at: str | None, name: str = "Available 5 min") -> None:
    """Your current status: its name and its end."""
    responses[APP_ROUTE][AVAILABILITY] = {
        **r.CAROUSEL,
        "globalAvailability": {**r.CAROUSEL["globalAvailability"], "availabilityName": name, "end": at},
    }


def events_schedule(entry):
    return entry.runtime_data.personal.lookups["events"].schedule


async def minutes(hass: HomeAssistant, freezer, n: int) -> None:
    for _ in range(n):
        await tick(hass, freezer, 60)


def with_alert_at_three(responses: dict) -> None:
    """You add a status for 15:00-17:00 local (13:00-15:00 UTC) in the Verdi app."""
    upcoming = copy.deepcopy(r.UPCOMING)
    base = upcoming["groups"][0]["items"][0]  # the long "Not available" single
    upcoming["groups"][0]["items"].append(
        {
            **base,
            "guid": "ev-new",
            "title": "Alert 5 min",
            "startDate": "2026-06-15T15:00:00+02:00",
            "endDate": "2026-06-15T17:00:00+02:00",
        }
    )
    responses[APP_ROUTE][EVENTS] = upcoming


async def test_events_fetched_again_before_your_status_ends(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    ends(responses, "2026-06-15T13:00:00Z")  # start() puts the clock at 12:00 UTC
    await start(hass, config_entry, freezer)
    await tick(hass, freezer, 330)  # 12:05:30: the events' startup fetch
    assert count(calls, EVENTS) == 1
    assert hass.states.get(SENSOR).attributes["next_status"] == "Not available"
    with_alert_at_three(responses)  # nothing announces it
    await minutes(hass, freezer, 41)  # 12:46:30
    assert count(calls, EVENTS) == 1
    assert hass.states.get(SENSOR).attributes["next_status"] == "Not available"
    await tick(hass, freezer, 61)  # 12:47:31; due 12:47:30 = 13:00 - 750 s
    assert count(calls, EVENTS) == 2
    assert events_schedule(config_entry).last_reason == AHEAD
    assert hass.states.get(SENSOR).attributes["next_status"] == "Alert 5 min"


async def test_the_fetch_before_the_end_moves_with_the_end(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    ends(responses, "2026-06-15T13:00:00Z")
    await start(hass, config_entry, freezer)
    await tick(hass, freezer, 330)  # 12:05:30
    assert events_schedule(config_entry).ahead_at == datetime(2026, 6, 15, 12, 47, 30, tzinfo=UTC)
    ends(responses, "2026-06-15T14:00:00Z", name="Not available")  # a new status, ending later
    await minutes(hass, freezer, 45)  # 12:50:30; the availability safety (12:30) saw it
    assert count(calls, EVENTS) == 2  # startup + the change trigger (12:30:30); nothing at 12:47:30
    assert events_schedule(config_entry).last_reason == "trigger:availability"
    assert events_schedule(config_entry).ahead_at == datetime(2026, 6, 15, 13, 47, 30, tzinfo=UTC)
    await minutes(hass, freezer, 57)  # 13:47:30
    await tick(hass, freezer, 1)  # 13:47:31
    assert count(calls, EVENTS) == 4  # + the hourly safety (13:30:30) + ahead (13:47:30)
    assert events_schedule(config_entry).last_reason == AHEAD


async def test_a_status_that_just_changed_and_ends_soon_is_fetched_once(
    hass: HomeAssistant, config_entry, api, freezer
):
    responses, calls, _ = api
    await start(hass, config_entry, freezer)  # the fixture's status ends 21:59 UTC
    await tick(hass, freezer, 330)  # 12:05:30
    ends(responses, "2026-06-15T12:40:00Z", name="Not available")
    await minutes(hass, freezer, 36)  # 12:41:30; availability safety 12:30 saw the change
    assert count(calls, EVENTS) == 2  # startup + the change trigger (12:30:30) only
    assert events_schedule(config_entry).ahead_at is None


async def test_a_restart_inside_the_window_adds_no_fetch(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    ends(responses, "2026-06-15T12:15:00Z")
    await start(hass, config_entry, freezer)
    assert events_schedule(config_entry).ahead_at is None  # the startup fetch (12:05:30) is inside the window
    await minutes(hass, freezer, 16)  # 12:16
    assert count(calls, EVENTS) == 1


async def test_a_restart_just_before_the_end_fetches_soon(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    ends(responses, "2026-06-15T12:03:00Z")  # before the startup fetch (12:05:30)
    await start(hass, config_entry, freezer)
    assert events_schedule(config_entry).ahead_at == datetime(2026, 6, 15, 12, 0, 30, tzinfo=UTC)
    await tick(hass, freezer, 31)  # 12:00:31
    assert count(calls, EVENTS) == 1
    assert events_schedule(config_entry).last_reason == AHEAD


async def test_an_events_fetch_inside_the_window_clears_the_slot(
    hass: HomeAssistant, config_entry, api, freezer
):
    responses, calls, _ = api
    ends(responses, "2026-06-15T13:00:00Z")
    await start(hass, config_entry, freezer)
    await tick(hass, freezer, 330)  # 12:05:30
    await minutes(hass, freezer, 40)  # 12:45:30: inside the window (from 12:45)
    await config_entry.runtime_data.personal.async_refresh_lookup("events")
    await hass.async_block_till_done()
    assert events_schedule(config_entry).ahead_at is None
    calls.clear()
    await minutes(hass, freezer, 14)  # 12:59:30
    assert count(calls, EVENTS) == 0


async def test_no_end_no_slot(hass: HomeAssistant, config_entry, api, freezer):
    responses, _, _ = api
    ends(responses, None)
    await start(hass, config_entry, freezer)
    assert events_schedule(config_entry).ahead_at is None
    responses[APP_ROUTE][AVAILABILITY] = {k: v for k, v in r.CAROUSEL.items() if k != "globalAvailability"}
    await minutes(hass, freezer, 31)  # the availability safety (12:30) gets the empty answer
    assert events_schedule(config_entry).ahead_at is None


async def test_events_off_no_slot_no_error(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    ends(responses, "2026-06-15T12:20:00Z")
    await start(hass, config_entry, freezer, options={"my_events": False})
    await minutes(hass, freezer, 21)
    assert count(calls, EVENTS) == 0
    assert hass.states.get(SENSOR).state == "Available 5 min"


async def test_a_far_end_leaves_the_hourly_fetch_alone(hass: HomeAssistant, config_entry, api, freezer):
    responses, _, _ = api
    ends(responses, "2027-06-30T08:00:00Z")
    await start(hass, config_entry, freezer)
    await tick(hass, freezer, 330)  # 12:05:30
    schedule = events_schedule(config_entry)
    assert schedule.ahead_at == datetime(2027, 6, 30, 7, 47, 30, tzinfo=UTC)
    assert schedule.next_due(datetime(2026, 6, 15, 12, 5, 30, tzinfo=UTC)) == datetime(
        2026, 6, 15, 13, 5, 30, tzinfo=UTC
    )
