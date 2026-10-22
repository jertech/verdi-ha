# SPDX-License-Identifier: GPL-3.0-or-later
"""LookupCoordinator: only due lookups, failures, the guard, and when it wakes next."""

import logging
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.verdi.api import VerdiApi, VerdiAuthError, VerdiError, VerdiUnavailable
from custom_components.verdi.const import (
    CONF_EVENTS_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_STATISTICS_INTERVAL,
)
from custom_components.verdi.coordinator import Lookup, LookupCoordinator, interval
from custom_components.verdi.guard import Guard
from custom_components.verdi.schedule import LookupSchedule
from custom_components.verdi.token import get_store
from tests.conftest import BASE_URL, MidRandom, make_token

RETRY = timedelta(minutes=5)
FAILED = VerdiError("x/commands: HTTP 400")


def make(hass, entry, lookups, *, pace=(60.0, 30.0), keep=False) -> LookupCoordinator:
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
        retry=RETRY,
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


async def test_cap_stops_the_run(hass: HomeAssistant, config_entry):
    a, b = value(1), value(2)
    c = make(hass, config_entry, {"a": Lookup(a, parse), "b": Lookup(b, parse)})
    for _ in range(29):
        c.guard.record_call()
    await c.async_refresh()
    assert (a.call_count, b.call_count) == (1, 0)
    assert c.lookups["b"].schedule.reason(c.lookups["a"].schedule.last_fetch) is not None
    assert c.update_interval == timedelta(seconds=5)


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
    assert interval({}, CONF_SCAN_INTERVAL) == timedelta(seconds=120)
    assert interval({CONF_SCAN_INTERVAL: 5}, CONF_SCAN_INTERVAL) == timedelta(seconds=60)
    assert interval({}, CONF_EVENTS_INTERVAL) == timedelta(minutes=10)
    assert interval({}, CONF_STATISTICS_INTERVAL) == timedelta(hours=6)
    assert interval({CONF_STATISTICS_INTERVAL: 0}, CONF_STATISTICS_INTERVAL) == timedelta(hours=1)
