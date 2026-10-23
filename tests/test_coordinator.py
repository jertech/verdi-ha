# SPDX-License-Identifier: GPL-3.0-or-later
"""LookupCoordinator: only due lookups, failures, the guard, and when it wakes next."""

import asyncio
import logging
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from custom_components.verdi.api import VerdiApi, VerdiAuthError, VerdiError, VerdiUnavailable
from custom_components.verdi.const import (
    CONF_EVENTS_INTERVAL,
    CONF_INTERVENTION_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_STATISTICS_INTERVAL,
)
from custom_components.verdi.coordinator import Lookup, LookupCoordinator, PersonId, interval
from custom_components.verdi.guard import Guard
from custom_components.verdi.schedule import LookupSchedule
from custom_components.verdi.token import get_store
from tests.conftest import BASE_URL, MidRandom, make_token

RETRY = timedelta(minutes=5)
FAILED = VerdiError("x/commands: HTTP 400")
UNAVAILABLE = VerdiUnavailable("x/commands: HTTP 503")


def make(hass, entry, lookups, *, pace=(60.0, 30.0), keep=False, retry=RETRY) -> LookupCoordinator:
    entry.add_to_hass(hass)
    get_store(hass).tokens[entry.entry_id] = make_token(lifetime=86400)
    api = VerdiApi(async_get_clientsession(hass), BASE_URL, None)
    return LookupCoordinator(
        hass,
        entry,
        api,
        "test",
        lookups,
        pace=lambda: pace,
        retry=retry,
        keep_on_failure=keep,
        guard=Guard(MidRandom()),
        rng=MidRandom(),
    )


def value(v):
    return AsyncMock(return_value={"v": v})


def parse(data):
    return data["v"]


async def test_only_due_lookups_are_called(hass: HomeAssistant, config_entry, freezer):
    tick, slow = value(1), value(2)
    c = make(
        hass,
        config_entry,
        {
            "tick": Lookup(tick, parse, LookupSchedule(always=True)),
            "slow": Lookup(slow, parse, LookupSchedule(safety=timedelta(minutes=15))),
        },
    )
    await c.async_refresh()
    assert c.data == {"tick": 1, "slow": 2}
    assert c.update_interval == timedelta(seconds=60)
    freezer.tick(timedelta(seconds=60))
    await c.async_refresh()
    assert (tick.call_count, slow.call_count) == (2, 1)
    assert c.data == {"tick": 1, "slow": 2}
    freezer.tick(timedelta(minutes=15))
    await c.async_refresh()
    assert slow.call_count == 2


async def test_failed_lookup_keeps_value_and_retries(hass: HomeAssistant, config_entry, freezer):
    fetch = AsyncMock(side_effect=[{"v": 1}, FAILED, {"v": 2}])
    c = make(
        hass,
        config_entry,
        {"stats": Lookup(fetch, parse, LookupSchedule(safety=timedelta(hours=6)))},
        pace=None,
        keep=True,
    )
    await c.async_refresh()
    assert c.update_interval == timedelta(hours=6)
    freezer.tick(timedelta(hours=6))
    await c.async_refresh()
    assert c.last_update_success
    assert c.data == {"stats": 1}
    assert c.update_interval == RETRY
    freezer.tick(RETRY)
    await c.async_refresh()
    assert c.data == {"stats": 2}


async def test_nothing_to_keep_is_a_failure(hass: HomeAssistant, config_entry):
    c = make(hass, config_entry, {"x": Lookup(AsyncMock(side_effect=FAILED), parse)}, keep=True)
    await c.async_refresh()
    assert not c.last_update_success


async def test_without_keep_every_lookup_failing_is_a_failure(hass: HomeAssistant, config_entry, freezer):
    c = make(hass, config_entry, {"x": Lookup(AsyncMock(side_effect=[{"v": 1}, FAILED]), parse)})
    await c.async_refresh()
    freezer.tick(timedelta(seconds=60))
    await c.async_refresh()
    assert not c.last_update_success


async def test_failing_off_tick_lookup_keeps_the_station_available(
    hass: HomeAssistant, config_entry, freezer
):
    safety = AsyncMock(side_effect=[{"v": 2}, FAILED])
    c = make(
        hass,
        config_entry,
        {
            "tick": Lookup(value(1), parse, LookupSchedule(always=True)),
            "safe": Lookup(safety, parse, LookupSchedule(safety=timedelta(minutes=15))),
        },
    )
    await c.async_refresh()
    freezer.tick(timedelta(minutes=16))
    c._tick_at = dt_util.now() + timedelta(hours=1)  # not a tick: only the safety lookup is due
    await c.async_refresh()
    assert safety.call_count == 2
    assert c.last_update_success
    assert c.data == {"tick": 1, "safe": 2}


async def test_failing_single_lookup_refresh_keeps_the_station_available(
    hass: HomeAssistant, config_entry, freezer
):
    x = AsyncMock(side_effect=[{"v": 1}, FAILED])
    c = make(hass, config_entry, {"x": Lookup(x, parse, LookupSchedule(safety=timedelta(hours=1)))})
    await c.async_refresh()
    await c.async_refresh_lookup("x")
    assert x.call_count == 2
    assert c.last_update_success
    assert c.data == {"x": 1}


async def test_short_401_glitch_is_tolerated(hass: HomeAssistant, config_entry, freezer, caplog):
    first, second = AsyncMock(side_effect=[{"v": 1}, VerdiAuthError("a: HTTP 401"), {"v": 3}]), value(2)
    c = make(
        hass,
        config_entry,
        {"a": Lookup(first, parse), "b": Lookup(second, parse)},
    )
    await c.async_refresh()
    freezer.tick(timedelta(seconds=60))
    await c.async_refresh()
    assert c.last_update_success
    assert c.data == {"a": 1, "b": 2}
    assert second.call_count == 1  # the run stopped at the 401
    assert caplog.text.count("Verdi rejected the token") == 1
    freezer.tick(timedelta(seconds=60))
    await c.async_refresh()
    assert c.data == {"a": 3, "b": 2}


async def test_401s_for_two_minutes_ask_for_reauth(hass: HomeAssistant, config_entry, freezer):
    c = make(hass, config_entry, {"a": Lookup(AsyncMock(return_value={"v": 1}), parse)})
    await c.async_refresh()
    c.lookups["a"].fetch = AsyncMock(side_effect=VerdiAuthError("a: HTTP 401"))
    freezer.tick(timedelta(seconds=60))
    await c._async_update_data()
    freezer.tick(timedelta(seconds=60))
    await c._async_update_data()
    freezer.tick(timedelta(seconds=60))
    with pytest.raises(ConfigEntryAuthFailed):
        await c._async_update_data()


async def test_first_run_with_nothing_fetched_fails(hass: HomeAssistant, config_entry):
    c = make(hass, config_entry, {"a": Lookup(AsyncMock(side_effect=VerdiAuthError("a: HTTP 401")), parse)})
    with pytest.raises(UpdateFailed):
        await c._async_update_data()


async def test_server_errors_back_off_and_recover(hass: HomeAssistant, config_entry, freezer):
    fetch = AsyncMock(return_value={"v": 1})
    c = make(hass, config_entry, {"a": Lookup(fetch, parse)}, keep=True)
    await c.async_refresh()
    fetch.side_effect = VerdiUnavailable("a: HTTP 503")
    waits = []
    for _ in range(4):
        freezer.tick(c.update_interval)
        await c.async_refresh()
        waits.append(c.update_interval.total_seconds())
        assert c.data == {"a": 1}
    assert waits == [90, 150, 180, 180]  # middle of [60, 120], [60, 240], [60, 300], [60, 300]
    fetch.side_effect = None
    freezer.tick(c.update_interval)
    await c.async_refresh()
    assert c.update_interval == timedelta(seconds=60)


async def test_cap_stops_the_run_and_keeps_the_rest_due(hass: HomeAssistant, config_entry, freezer):
    a, b = value(1), value(2)
    c = make(hass, config_entry, {"a": Lookup(a, parse), "b": Lookup(b, parse)})
    await c.async_refresh()
    freezer.tick(timedelta(seconds=60))
    for _ in range(29):
        c.guard.record_call()
    await c.async_refresh()
    assert (a.call_count, b.call_count) == (2, 1)
    assert c.update_interval == timedelta(seconds=5)
    freezer.tick(timedelta(seconds=5))
    await c.async_refresh()
    assert (a.call_count, b.call_count) == (2, 1)  # the cap still holds
    freezer.tick(timedelta(seconds=60))
    await c.async_refresh()
    assert (a.call_count, b.call_count) == (3, 2)


async def test_a_failing_lookup_without_a_tick_does_not_back_off(hass: HomeAssistant, config_entry):
    c = make(
        hass,
        config_entry,
        {"x": Lookup(AsyncMock(side_effect=UNAVAILABLE), parse, LookupSchedule(safety=timedelta(hours=6)))},
        pace=None,
        keep=True,
    )
    await c.async_refresh()
    assert c.update_interval == RETRY
    assert c.guard.level == 0
    assert c.guard.can_call()


async def test_manual_refresh_during_a_tick_run(hass: HomeAssistant, config_entry):
    gate = asyncio.Event()

    async def slow_a():
        await gate.wait()
        return {"v": 1}

    b, d = value(2), value(3)
    c = make(hass, config_entry, {"a": Lookup(slow_a, parse), "b": Lookup(b, parse), "d": Lookup(d, parse)})
    tick_run = asyncio.create_task(c.async_refresh())
    await asyncio.sleep(0)
    manual = asyncio.create_task(c.async_refresh_lookup("d"))
    await asyncio.sleep(0)
    gate.set()
    await asyncio.gather(tick_run, manual)
    assert c.last_update_success
    assert c.data == {"a": 1, "b": 2, "d": 3}
    assert b.call_count == 1


async def test_refresh_one_lookup(hass: HomeAssistant, config_entry):
    a, b = value(1), value(2)
    c = make(hass, config_entry, {"a": Lookup(a, parse), "b": Lookup(b, parse)})
    await c.async_refresh()
    await c.async_refresh_lookup("b")
    assert (a.call_count, b.call_count) == (1, 2)
    assert c.lookups["b"].schedule.last_reason == "manual"


async def test_hooks_see_old_and_new_values(hass: HomeAssistant, config_entry, freezer):
    fetch = AsyncMock(side_effect=[{"v": 1}, {"v": 2}])
    c = make(hass, config_entry, {"a": Lookup(fetch, parse)})
    seen, runs = [], []
    c.on_fetched = lambda key, new, old: seen.append((key, new, old))
    c.on_run = lambda data, previous: runs.append((dict(data), dict(previous)))
    await c.async_refresh()
    freezer.tick(timedelta(seconds=60))
    await c.async_refresh()
    assert seen == [("a", 1, None), ("a", 2, 1)]
    assert runs[-1] == ({"a": 2}, {"a": 1})


async def test_idle_when_nothing_is_ever_due(hass: HomeAssistant, config_entry):
    c = make(hass, config_entry, {"a": Lookup(value(1), parse, LookupSchedule())}, pace=None)
    await c.async_refresh()
    assert c.update_interval == timedelta(hours=1)


async def test_recovery_and_failure_are_logged_once(hass: HomeAssistant, config_entry, freezer, caplog):
    caplog.set_level(logging.INFO)
    fetch = AsyncMock(side_effect=[{"v": 1}, FAILED, {"v": 2}, {"v": 3}])
    c = make(hass, config_entry, {"vehicles": Lookup(fetch, parse)}, keep=True)
    for _ in range(4):
        await c.async_refresh()
        freezer.tick(timedelta(seconds=60))
    assert caplog.text.count("Verdi lookup vehicles failed") == 1
    assert caplog.text.count("Verdi lookup vehicles works again") == 1


def test_interval_options():
    assert interval({}, CONF_SCAN_INTERVAL) == timedelta(seconds=60)
    assert interval({CONF_SCAN_INTERVAL: 5}, CONF_SCAN_INTERVAL) == timedelta(seconds=30)
    assert interval({}, CONF_INTERVENTION_INTERVAL) == timedelta(seconds=30)
    assert interval({}, CONF_EVENTS_INTERVAL) == timedelta(minutes=60)
    assert interval({}, CONF_STATISTICS_INTERVAL) == timedelta(hours=24)
    assert interval({CONF_STATISTICS_INTERVAL: 0}, CONF_STATISTICS_INTERVAL) == timedelta(hours=1)


async def test_first_run_blocked_by_the_guard_fails(hass: HomeAssistant, config_entry):
    a = value(1)
    c = make(hass, config_entry, {"a": Lookup(a, parse)})
    c.guard.wait(600)
    with pytest.raises(UpdateFailed):
        await c._async_update_data()
    assert a.call_count == 0


async def test_first_run_capped_part_way_fails(hass: HomeAssistant, config_entry):
    a, b = value(1), value(2)
    c = make(hass, config_entry, {"a": Lookup(a, parse), "b": Lookup(b, parse)})
    for _ in range(29):
        c.guard.record_call()
    with pytest.raises(UpdateFailed):
        await c._async_update_data()
    assert (a.call_count, b.call_count) == (1, 0)


async def test_server_error_stops_the_run_and_blocks_every_call(hass: HomeAssistant, config_entry, freezer):
    a, b = value(1), value(2)
    c = make(hass, config_entry, {"a": Lookup(a, parse), "b": Lookup(b, parse)}, keep=True)
    await c.async_refresh()
    a.side_effect = UNAVAILABLE
    freezer.tick(timedelta(seconds=60))
    await c.async_refresh()
    assert (a.call_count, b.call_count) == (2, 1)  # b not called after a's 503
    assert c.guard.level == 1
    assert c.update_interval == timedelta(seconds=90)  # middle of [60, 120]
    freezer.tick(timedelta(seconds=60))
    await c.async_refresh()  # a tick, but still inside the backoff
    await c.async_refresh_lookup("b")
    assert (a.call_count, b.call_count) == (2, 1)
    assert c.guard.level == 1
    a.side_effect = None
    freezer.tick(timedelta(seconds=30))
    await c.async_refresh()
    assert (a.call_count, b.call_count) == (3, 2)  # b's manual mark and the tick
    assert c.guard.level == 0
    assert c.lookups["b"].schedule.last_reason == "manual"


async def test_retry_after_longer_than_the_backoff_wins(hass: HomeAssistant, config_entry, freezer):
    fetch = value(1)
    c = make(hass, config_entry, {"a": Lookup(fetch, parse)}, keep=True)
    await c.async_refresh()
    fetch.side_effect = VerdiUnavailable("a: HTTP 429", retry_after=600)
    freezer.tick(timedelta(seconds=60))
    await c.async_refresh()
    assert c.update_interval == timedelta(seconds=600)
    freezer.tick(timedelta(seconds=599))
    assert not c.guard.can_call()


async def test_one_failing_lookup_keeps_the_normal_tick(hass: HomeAssistant, config_entry, freezer):
    a, b = value(1), value(2)
    readiness = AsyncMock(side_effect=UNAVAILABLE)
    c = make(
        hass,
        config_entry,
        {
            "a": Lookup(a, parse),
            "b": Lookup(b, parse),
            "readiness": Lookup(readiness, parse, LookupSchedule(safety=timedelta(minutes=15))),
        },
        retry=timedelta(seconds=60),
    )
    for _ in range(4):
        await c.async_refresh()
        assert c.update_interval == timedelta(seconds=60)
        assert c.guard.level == 0
        assert c.guard.can_call()
        freezer.tick(timedelta(seconds=60))
    assert (a.call_count, b.call_count, readiness.call_count) == (4, 4, 4)


async def test_a_retry_before_the_tick_does_not_back_off(hass: HomeAssistant, config_entry, freezer):
    """The jittered tick (54-66 s) often comes after a failed lookup's retry (60 s): that run
    calls only the failing lookup, fetches nothing, and must not back off the whole entry."""
    a, b = value(1), value(2)
    readiness = AsyncMock(side_effect=UNAVAILABLE)
    c = make(
        hass,
        config_entry,
        {
            "a": Lookup(a, parse),
            "b": Lookup(b, parse),
            "readiness": Lookup(readiness, parse, LookupSchedule(safety=timedelta(minutes=15))),
        },
        pace=(66.0, 30.0),
        retry=timedelta(seconds=60),
    )
    await c.async_refresh()  # a and b fine, readiness fails: retry at 60 s, tick at 66 s
    assert c.update_interval == timedelta(seconds=60)
    freezer.tick(timedelta(seconds=60))
    await c.async_refresh()  # readiness alone, fails again
    assert (a.call_count, b.call_count, readiness.call_count) == (1, 1, 2)
    assert c.guard.level == 0
    assert c.guard.can_call()
    assert c.update_interval == timedelta(seconds=6)  # the tick stays at 66 s
    freezer.tick(timedelta(seconds=6))
    await c.async_refresh()
    assert (a.call_count, b.call_count) == (2, 2)


async def test_a_tick_where_only_vehicles_fail_does_not_back_off(hass: HomeAssistant, config_entry, freezer):
    personnel = value({"total": 2})  # lookup_counts reads the total
    vehicles = AsyncMock(side_effect=UNAVAILABLE)
    c = make(
        hass,
        config_entry,
        {"personnel": Lookup(personnel, parse), "vehicles": Lookup(vehicles, parse)},
        retry=timedelta(seconds=60),
    )
    for _ in range(4):
        await c.async_refresh()
        assert c.guard.level == 0
        assert c.guard.can_call()
        assert c.update_interval == timedelta(seconds=60)
        freezer.tick(timedelta(seconds=60))
    assert (personnel.call_count, vehicles.call_count) == (4, 4)
    assert c.data == {"personnel": {"total": 2}, "vehicles": None}


async def test_a_mark_during_the_fetch_fetches_again(hass: HomeAssistant, config_entry, freezer):
    calls = []

    async def fetch():
        calls.append(1)
        if len(calls) == 1:
            c.mark_due("x", "trigger:test")  # e.g. a signal from the other coordinator
        return {"v": len(calls)}

    c = make(hass, config_entry, {"x": Lookup(fetch, parse, LookupSchedule(safety=timedelta(hours=1)))})
    await c.async_refresh()
    assert c.update_interval == timedelta(seconds=5)
    freezer.tick(timedelta(seconds=5))
    await c.async_refresh()
    assert len(calls) == 2
    assert c.lookups["x"].schedule.last_reason == "trigger:test"


async def test_a_failed_tick_lookup_waits_for_the_next_tick(hass: HomeAssistant, config_entry, freezer):
    fetch = value(1)
    # The tick (66 s) comes later than the retry (60 s), as it does about half the time.
    c = make(
        hass,
        config_entry,
        {"a": Lookup(fetch, parse)},
        pace=(66.0, 30.0),
        keep=True,
        retry=timedelta(seconds=60),
    )
    await c.async_refresh()
    fetch.side_effect = FAILED
    freezer.tick(timedelta(seconds=66))
    await c.async_refresh()
    assert c.update_interval == timedelta(seconds=66)  # no wake for a retry 6 s before the tick
    fetch.side_effect = None
    freezer.tick(timedelta(seconds=66))
    await c.async_refresh()
    assert fetch.call_count == 3
    assert c.lookups["a"].schedule.last_reason == "tick"


async def test_person_id_goes_through_the_guard(hass: HomeAssistant):
    api = VerdiApi(async_get_clientsession(hass), BASE_URL, "token")
    guard = Guard(MidRandom())
    person = PersonId(api, guard)
    api.current_user = AsyncMock(return_value={"personGuid": "me-1"})
    guard.wait(600)
    with pytest.raises(VerdiError):
        await person.get()
    assert api.current_user.call_count == 0
    guard = Guard(MidRandom())
    person = PersonId(api, guard)
    assert await person.get() == "me-1"
    assert await person.get() == "me-1"  # kept in memory
    assert api.current_user.call_count == 1
    assert guard.calls_last_minute() == 1


async def test_person_id_reports_trouble_to_the_guard(hass: HomeAssistant):
    api = VerdiApi(async_get_clientsession(hass), BASE_URL, "token")
    guard = Guard(MidRandom())
    person = PersonId(api, guard)
    api.current_user = AsyncMock(side_effect=VerdiUnavailable("security/users/authorize: timeout"))
    with pytest.raises(VerdiUnavailable):
        await person.get()
    assert guard.level == 0  # only a failed station tick backs off
    assert guard.can_call()
    api.current_user.side_effect = VerdiUnavailable("security/users/authorize: HTTP 429", retry_after=600)
    with pytest.raises(VerdiUnavailable):
        await person.get(report=False)  # inside a run: the run reports
    assert guard.can_call()
    with pytest.raises(VerdiUnavailable):
        await person.get()
    assert guard.level == 0
    assert not guard.can_call()
