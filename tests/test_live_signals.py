# SPDX-License-Identifier: GPL-3.0-or-later
"""Live notices to marks: only the station, you and the station's vehicles count."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.verdi.coordinator import readiness_inputs
from custom_components.verdi.schedule import TICK
from tests import responses as r
from tests.conftest import fake_command, setup_with_token

PERSONNEL = "PersonGetGroupedWidgetsCommand"


@pytest.fixture
def api():
    calls: list = []
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(r.all_ok(), calls)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        yield calls


async def _live(hass, entry, options=None):
    await setup_with_token(hass, entry, options=options)
    live = entry.runtime_data.live_updates
    assert live is not None
    live.client = MagicMock()
    if entry.runtime_data.fast is not None:
        entry.runtime_data.fast.paused = False
    return live


def _reason(coordinator, key):
    """Why the lookup is due; once the wake has fetched it (tasks start eagerly), why it was fetched."""
    schedule = coordinator.lookups[key].schedule
    return schedule.reason(dt_util.now()) or schedule.last_reason


async def test_option_off_means_no_live_updates(hass: HomeAssistant, config_entry, api, real_live):
    await setup_with_token(hass, config_entry, options={"live_updates": False})
    assert config_entry.runtime_data.live_updates is None


async def test_own_station_availability_fetches_personnel(hass: HomeAssistant, config_entry, api, real_live):
    live = await _live(hass, config_entry)
    station = config_entry.runtime_data
    api.clear()
    live.handle("ReceivePersonAvailabilityChange", [{"stationId": "STATION-1", "crewFunctionId": "x"}])
    assert _reason(station, "personnel") == "live:receivepersonavailabilitychange"
    await hass.async_block_till_done()
    assert PERSONNEL in [c[1] for c in api]


async def test_other_station_is_dropped(hass: HomeAssistant, config_entry, api, real_live):
    live = await _live(hass, config_entry)
    live.handle("receivePersonAvailabilityChange", [{"stationId": "station-2", "crewFunctionId": "x"}])
    live.handle("ReceiveStationReadinessChanged", ["station-2"])
    live.handle("ReceiveChanged", ["2026-01-01T00:00:00Z", "Person", "someone-else", []])
    live.handle("ReceiveChanged", ["2026-01-01T00:00:00Z", "Vehicle", "v9", []])
    live.handle("ReceiveInterventionAlarmChangedNotification", ["i1"])
    assert live.dropped == 5
    assert live.marks == {}


async def test_readiness_person_and_vehicle(hass: HomeAssistant, config_entry, api, real_live):
    live = await _live(hass, config_entry)
    station = config_entry.runtime_data
    live.handle("ReceiveStationReadinessChanged", ["station-1"])
    assert _reason(station, "readiness") == "live:receivestationreadinesschanged"
    live.handle("ReceiveChanged", ["2026-01-01T00:00:00Z", "Vehicle", "V1", ["IsOnIntervention"]])
    assert _reason(station, "vehicles") == "live:receivechanged"
    other = next(p["id"] for p in station.data["personnel"]["persons"] if p["id"] != "me-1")
    live.handle("ReceiveChanged", ["2026-01-01T00:00:00Z", "Person", other.upper(), []])
    assert _reason(station, "personnel") == "live:receivechanged"


async def test_own_person_marks_availability_and_personnel(hass: HomeAssistant, config_entry, api, real_live):
    live = await _live(hass, config_entry)
    station = config_entry.runtime_data
    live.handle("ReceiveChanged", ["2026-01-01T00:00:00Z", "Person", "ME-1", []])
    assert _reason(station.personal, "availability") == "live:receivechanged"
    assert _reason(station, "personnel") == "live:receivechanged"


async def test_new_intervention_starts_a_burst(hass: HomeAssistant, config_entry, api, real_live, freezer):
    live = await _live(hass, config_entry)
    station = config_entry.runtime_data
    fast = station.fast
    fast._tick_at = dt_util.now() + timedelta(seconds=60)
    live.handle("ReceiveCreated", ["2026-01-01T00:00:00Z", "Intervention", "i1"])
    assert _reason(fast, "paged") == "live:receivecreated"
    assert fast.burst_until == dt_util.now() + timedelta(seconds=90)
    assert fast._tick_at == dt_util.now() + timedelta(seconds=10)
    assert station.timing._live_intervention == dt_util.now()
    assert live.bursts == 1


async def test_paused_paging_ignores_interventions(hass: HomeAssistant, config_entry, api, real_live):
    live = await _live(hass, config_entry)
    fast = config_entry.runtime_data.fast
    fast.paused = True
    live.handle("ReceiveCreated", ["2026-01-01T00:00:00Z", "Intervention", "i1"])
    assert fast.burst_until is None
    assert live.dropped == 1


async def test_intervention_start_and_own_confirmation(hass: HomeAssistant, config_entry, api, real_live):
    live = await _live(hass, config_entry)
    fast = config_entry.runtime_data.fast
    live.handle("ReceiveChanged", ["2026-01-01T00:00:00Z", "Intervention", "i1", ["CalculationState"]])
    assert live.dropped == 1
    live.handle("ReceiveChanged", ["2026-01-01T00:00:00Z", "Intervention", "i1", ["DateStarted"]])
    assert _reason(fast, "paged") == "live:receivechanged"
    live.handle(
        "ReceiveInterventionAttendanceConfirmation", [{"personId": "someone", "callConfirmation": {}}]
    )
    assert live.dropped == 2
    live.handle("ReceiveInterventionAttendanceConfirmation", [{"personId": "me-1", "callConfirmation": {}}])
    assert live.marks["paged"] == 2


async def test_pre_alert_and_garrison(hass: HomeAssistant, config_entry, api, real_live):
    live = await _live(hass, config_entry, options={"pre_alert": True, "garrison": True})
    station = config_entry.runtime_data
    live.handle("receivePreAlertDispatched", [{}])
    assert _reason(station.personal, "pre_alerts") == "live:receiveprealertdispatched"
    assert _reason(station, "personnel") == "live:receiveprealertdispatched"
    live.handle("receiveGarrisonCrewAttendanceConfirmation", [{}])
    assert _reason(station.personal, "garrison") == "live:receivegarrisoncrewattendanceconfirmation"


async def test_marks_follow_a_lookup_to_the_fast_lane(hass: HomeAssistant, config_entry, api, real_live):
    live = await _live(hass, config_entry, options={"fast_lane": ["paged", "vehicles"]})
    fast = config_entry.runtime_data.fast
    live.handle("ReceiveChanged", ["2026-01-01T00:00:00Z", "Vehicle", "v1", []])
    assert _reason(fast, "vehicles") == "live:receivechanged"


async def test_connect_catches_up_what_is_old(hass: HomeAssistant, config_entry, api, real_live, freezer):
    live = await _live(hass, config_entry)
    station = config_entry.runtime_data
    live.state(True)
    assert station.live_connected and station.fast.live_connected
    assert live.marks == {}  # everything was fetched seconds ago
    live.state(False)
    freezer.tick(timedelta(seconds=61))
    live.state(True)
    assert _reason(station, "personnel") == "live:connected"
    assert _reason(station, "vehicles") == "live:connected"
    assert _reason(station, "readiness") == "live:connected"
    assert _reason(station.fast, "paged") == "live:connected"


async def test_disconnect_returns_to_normal_ticks(hass: HomeAssistant, config_entry, api, real_live, freezer):
    live = await _live(hass, config_entry)
    station = config_entry.runtime_data
    live.state(True)
    station._tick_at = dt_util.now() + timedelta(seconds=290)
    live.state(False)
    assert not station.live_connected
    normal = station._pace()[0]  # 60 s, or 30 s: the fixture data has an intervention running
    assert normal < 290
    assert station._tick_at == dt_util.now() + timedelta(seconds=normal)


async def test_disconnect_marks_every_lane_before_waking_any(
    hass: HomeAssistant, config_entry, api, real_live
):
    live = await _live(hass, config_entry)
    station = config_entry.runtime_data
    assert station.fast is not None
    live.state(True)
    flags = []
    with patch.object(
        live, "_wake", lambda c: flags.append((station.live_connected, station.fast.live_connected))
    ):
        live.state(False)
    assert flags
    assert all(f == (False, False) for f in flags)


async def test_roster_boundary_marks_personnel(hass: HomeAssistant, config_entry, api, real_live, freezer):
    live = await _live(hass, config_entry)
    station = config_entry.runtime_data
    boundary = dt_util.now() + timedelta(hours=1)
    roster = [{"current": {"end": boundary}, "next": None}]
    with patch.object(station, "data", {**station.data, "roster": roster}):
        live.state(True)
    at = boundary + timedelta(seconds=75)  # the middle of BOUNDARY_DELAY (30, 120)
    assert station.lookups["personnel"].schedule.next_due(dt_util.now()) == at
    assert station.lookups["readiness"].schedule.next_due(dt_util.now()) <= at


async def test_two_unannounced_changes_reconnect(hass: HomeAssistant, config_entry, api, real_live):
    live = await _live(hass, config_entry)
    station = config_entry.runtime_data
    live.state(True)
    old = station.data["personnel"]
    new = {**old, "persons": [{**p, "availability": "Changed"} for p in old["persons"]]}
    assert readiness_inputs("personnel", new) != readiness_inputs("personnel", old)
    schedule = station.lookups["personnel"].schedule
    schedule.last_reason = TICK
    live.fetched("personnel", new, old)
    assert live.unannounced == 1
    live.client.reconnect.assert_not_called()
    live.fetched("personnel", new, old)
    live.client.reconnect.assert_called_once()


async def test_announced_and_off_tick_changes_do_not_count(hass: HomeAssistant, config_entry, api, real_live):
    live = await _live(hass, config_entry)
    station = config_entry.runtime_data
    live.state(True)
    old = station.data["personnel"]
    new = {**old, "persons": [{**p, "availability": "Changed"} for p in old["persons"]]}
    schedule = station.lookups["personnel"].schedule
    schedule.last_reason = "live:receivepersonavailabilitychange"
    live.fetched("personnel", new, old)
    schedule.last_reason = TICK
    with patch.object(live, "_wake"):  # the wake waits (debouncer cooldown): the next fetch is the tick
        live.handle("ReceivePersonAvailabilityChange", [{"stationId": "station-1"}])
    live.fetched("personnel", new, old)  # announced by the notice before it
    assert live.unannounced == 0


async def test_model_names_and_properties_ignore_case(hass: HomeAssistant, config_entry, api, real_live):
    live = await _live(hass, config_entry)
    station = config_entry.runtime_data
    live.handle("ReceiveChanged", ["2026-01-01T00:00:00Z", "person", "me-1", []])
    assert _reason(station.personal, "availability") == "live:receivechanged"
    live.handle("ReceiveChanged", ["2026-01-01T00:00:00Z", "VEHICLE", "v1", []])
    assert _reason(station, "vehicles") == "live:receivechanged"
    live.handle("ReceiveChanged", ["2026-01-01T00:00:00Z", "intervention", "i1", ["dateStarted"]])
    assert _reason(station.fast, "paged") == "live:receivechanged"
    assert live.dropped == 0


async def test_pre_alert_end_marks_pre_alerts_and_personnel(
    hass: HomeAssistant, config_entry, api, real_live
):
    live = await _live(hass, config_entry, options={"pre_alert": True})
    station = config_entry.runtime_data
    live.handle("ReceivePreAlertEnded", [{}])
    assert _reason(station.personal, "pre_alerts") == "live:receiveprealertended"
    assert _reason(station, "personnel") == "live:receiveprealertended"
    assert live.marks == {"pre_alerts": 1, "personnel": 1}


async def test_each_roster_fetch_moves_the_boundary_mark(
    hass: HomeAssistant, config_entry, api, real_live, freezer
):
    live = await _live(hass, config_entry)
    station = config_entry.runtime_data
    schedule = station.lookups["personnel"].schedule
    with patch.object(station, "data", {**station.data, "roster": []}):
        live.state(True)
    boundary = dt_util.now() + timedelta(hours=1)
    live.fetched("roster", [{"current": {"end": boundary}, "next": None}], [])
    assert schedule.next_due(dt_util.now()) == boundary + timedelta(seconds=75)
    sooner = dt_util.now() + timedelta(minutes=20)
    live.fetched("roster", [{"current": None, "next": {"start": sooner}}], [])
    assert schedule.next_due(dt_util.now()) == sooner + timedelta(seconds=75)
    live.state(False)
    live.fetched("roster", [{"current": {"end": dt_util.now() + timedelta(minutes=5)}, "next": None}], [])
    assert schedule.next_due(dt_util.now()) == sooner + timedelta(seconds=75)  # not connected: no mark


async def test_an_unchanged_tick_or_a_new_connection_ends_the_streak(
    hass: HomeAssistant, config_entry, api, real_live
):
    live = await _live(hass, config_entry)
    station = config_entry.runtime_data
    live.state(True)
    old = station.data["personnel"]
    new = {**old, "persons": [{**p, "availability": "Changed"} for p in old["persons"]]}
    station.lookups["personnel"].schedule.last_reason = TICK
    live.fetched("personnel", new, old)
    live.fetched("personnel", new, new)  # a tick with nothing new
    live.fetched("personnel", new, old)
    live.state(False)
    station.lookups["personnel"].schedule.last_reason = TICK
    live.state(True)
    station.lookups["personnel"].schedule.last_reason = TICK
    live.fetched("personnel", new, old)
    assert live.unannounced == 3
    live.client.reconnect.assert_not_called()
