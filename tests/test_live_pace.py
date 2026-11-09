# SPDX-License-Identifier: GPL-3.0-or-later
"""While live updates are connected the coordinators tick slower; when they drop, as before."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.verdi.api import VerdiUnavailable
from custom_components.verdi.schedule import MANUAL
from tests.conftest import setup_with_token


async def _tick(coordinator) -> timedelta:
    coordinator._tick_at = None  # the next run is a tick
    await coordinator.async_refresh()
    return coordinator._tick_at - dt_util.now()


async def test_station_ticks_every_fifteen_minutes_while_live(
    hass: HomeAssistant, config_entry, mock_api, freezer
):
    await setup_with_token(hass, config_entry)
    c = config_entry.runtime_data
    c.on_run = None  # signals.py would set the flag from the fixture's running intervention
    c.intervention = False
    assert await _tick(c) == timedelta(seconds=60)
    c.live_connected = True
    assert await _tick(c) == timedelta(seconds=900)
    c.intervention = True
    assert await _tick(c) == timedelta(seconds=900)
    assert c.tick_seconds() == 900


async def test_a_slower_option_is_kept_while_live(hass: HomeAssistant, config_entry, mock_api, freezer):
    await setup_with_token(hass, config_entry, options={"scan_interval": 1200})
    c = config_entry.runtime_data
    c.on_run = None  # signals.py would set the flag from the fixture's running intervention
    c.intervention = False
    c.live_connected = True
    assert await _tick(c) == timedelta(seconds=1200)


async def test_fast_lane_ticks_every_minute_and_bursts(hass: HomeAssistant, config_entry, mock_api, freezer):
    await setup_with_token(hass, config_entry)
    fast = config_entry.runtime_data.fast
    fast.paused = False  # paging on, so the fast lane has a tick
    assert await _tick(fast) == timedelta(seconds=15)
    fast.live_connected = True
    assert await _tick(fast) == timedelta(seconds=60)
    fast.burst_until = dt_util.now() + timedelta(seconds=90)
    assert await _tick(fast) == timedelta(seconds=10)
    fast.burst_until = dt_util.now() - timedelta(seconds=1)
    assert await _tick(fast) == timedelta(seconds=60)


async def test_dropped_live_pulls_the_tick_in(hass: HomeAssistant, config_entry, mock_api, freezer):
    await setup_with_token(hass, config_entry)
    c = config_entry.runtime_data
    c.on_run = None  # signals.py would set the flag from the fixture's running intervention
    c.intervention = False
    c._tick_at = dt_util.now() + timedelta(seconds=280)
    c.live_dropped()
    assert c._tick_at == dt_util.now() + timedelta(seconds=60)
    c._tick_at = dt_util.now() + timedelta(seconds=20)
    c.live_dropped()
    assert c._tick_at == dt_util.now() + timedelta(seconds=20)  # never later
    c._tick_at = None
    c.pull_tick(10)
    assert c._tick_at is None  # no planned tick: the next run is one anyway


async def test_backoff_uses_the_normal_pace_while_live(hass: HomeAssistant, config_entry, mock_api, freezer):
    await setup_with_token(hass, config_entry)
    c = config_entry.runtime_data
    c.on_run = None  # signals.py would set the flag from the fixture's running intervention
    c.intervention = False
    c.live_connected = True
    c._tick_at = None
    with (
        patch.object(c.guard, "unavailable", wraps=c.guard.unavailable) as unavailable,
        patch(
            "custom_components.verdi.api.VerdiApi.command",
            side_effect=VerdiUnavailable("HTTP 503", status=503),
        ),
    ):
        await c.async_refresh()
    assert unavailable.call_args.args[1] == 60


async def test_pace_name_live(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    c = config_entry.runtime_data
    c.live_connected = True
    assert c.pace_name == "live"
    c.guard.level = 1
    assert c.pace_name == "backoff"
    c.guard.level = 0
    er.async_get(hass).async_update_entity("sensor.verdi_pace", disabled_by=None)
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    c = config_entry.runtime_data
    c.live_connected = True
    c.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.verdi_pace").state == "live"


async def test_safety_is_longer_while_live_and_back_on_a_drop(
    hass: HomeAssistant, config_entry, mock_api, freezer
):
    await setup_with_token(hass, config_entry, options={"readiness_safety": 10, "roster_safety": 30})
    c = config_entry.runtime_data
    c.on_run = None
    c.live_connected = True
    for key in ("readiness", "roster", "roster_calendar"):
        c.mark_due(key, MANUAL)
    await c.async_refresh()
    now = dt_util.now()
    assert c.lookups["readiness"].schedule._safety_at == now + timedelta(minutes=60)
    assert c.lookups["roster"].schedule._safety_at == now + timedelta(minutes=120)
    assert c.lookups["roster_calendar"].schedule._safety_at == now + timedelta(minutes=120)
    assert c.lookups["teams"].schedule.live_safety is None
    c.live_connected = False
    c.live_dropped()
    assert c.lookups["readiness"].schedule._safety_at == now + timedelta(minutes=10)
    assert c.lookups["roster"].schedule._safety_at == now + timedelta(minutes=30)
    assert c.lookups["roster_calendar"].schedule._safety_at == now + timedelta(minutes=30)
