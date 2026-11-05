# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Live notices to marks: which lookup a change notice from Verdi makes due.

Verdi's notices hold IDs only and come for the whole zone. Only those about the entry's station, your
own person and the station's vehicles count; the value is always fetched over REST, through the guard.
While the connection is up the coordinators tick slower (coordinator.py); when it drops, as before.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .const import (
    BOUNDARY_DELAY,
    CONF_BASE_URL,
    CONF_LIVE_UPDATES,
    CONF_STATION_ID,
    LIVE_BURST_SECONDS,
    LIVE_BURST_TICK,
    LIVE_PAGED_CATCH_UP_AGE,
    LIVE_UNANNOUNCED_LIMIT,
)
from .coordinator import FastCoordinator, LookupCoordinator, VerdiCoordinator, readiness_inputs, roster_change
from .live import LiveClient
from .schedule import TICK
from .token import get_store

PERSONAL = ("availability", "pre_alerts", "garrison")
CATCH_UP = ("personnel", "vehicles", "readiness", "paged")
CHECKED = ("personnel", "vehicles")
CHANGES = ("receivechanged", "receivecreated")


def _same(a: Any, b: Any) -> bool:
    return isinstance(a, str) and isinstance(b, str) and a.lower() == b.lower()


def _first(arguments: list[Any]) -> dict[str, Any]:
    return arguments[0] if arguments and isinstance(arguments[0], dict) else {}


class LiveSignals:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, station: VerdiCoordinator) -> None:
        self._hass, self._entry, self._station = hass, entry, station
        self._station_id: str = entry.data[CONF_STATION_ID]
        self.client: LiveClient | None = None
        self.connected = False
        self.unannounced = 0
        self._announced: set[str] = set()
        self._streak: Counter[str] = Counter()
        self._timers: dict[tuple[int, datetime], Callable[[], None]] = {}
        self._day: date | None = None
        self.events: Counter[str] = Counter()
        self.marks: Counter[str] = Counter()
        self.dropped = 0
        self.bursts = 0

    # Notices.

    @callback
    def handle(self, target: str, arguments: list[Any]) -> None:
        self._today()
        name = target.lower()
        self.events[name] += 1
        if not self._dispatch(name, arguments):
            self.dropped += 1

    def _dispatch(self, name: str, arguments: list[Any]) -> bool:
        """Mark what the notice is about. False when it isn't about this station, you or its vehicles."""
        reason = f"live:{name}"
        me = self._station.person.value
        if name == "receivepersonavailabilitychange":
            if _same(_first(arguments).get("stationId"), self._station_id):
                return self._mark(reason, "personnel")
        elif name == "receivestationreadinesschanged":
            if arguments and _same(arguments[0], self._station_id):
                return self._mark(reason, "readiness")
        elif name in CHANGES and len(arguments) >= 3:
            model = arguments[1].lower() if isinstance(arguments[1], str) else None
            guid = arguments[2]
            changed = arguments[3] if len(arguments) > 3 and isinstance(arguments[3], list) else []
            if model == "person":
                if _same(guid, me):
                    return self._mark(reason, "availability", "personnel")
                if isinstance(guid, str) and guid.lower() in self._persons():
                    return self._mark(reason, "personnel")
            elif model == "vehicle":
                if isinstance(guid, str) and guid.lower() in self._vehicles():
                    return self._mark(reason, "vehicles")
            elif model == "intervention":
                if name == "receivecreated":
                    return self._burst(reason)
                if any(_same(prop, "DateStarted") for prop in changed):
                    return self._mark(reason, "paged")
        elif name == "receiveinterventionattendanceconfirmation":
            if _same(_first(arguments).get("personId"), me):
                return self._mark(reason, "paged")
        elif name in ("receiveprealertdispatched", "receiveprealertended"):
            return self._mark(reason, "pre_alerts", "personnel")
        elif name == "receivegarrisoncrewattendanceconfirmation":
            return self._mark(reason, "garrison")
        return False

    def _burst(self, reason: str) -> bool:
        """A new intervention somewhere in the zone: look for your page now and every 10 s for 90 s."""
        fast = self._station.fast
        if not isinstance(fast, FastCoordinator) or "paged" not in fast.lookups or fast.paused:
            return False
        now = dt_util.now()
        if self._station.timing is not None:
            self._station.timing.live_intervention(now)
        fast.burst_until = now + timedelta(seconds=LIVE_BURST_SECONDS)
        fast.pull_tick(LIVE_BURST_TICK)
        self.bursts += 1
        return self._mark(reason, "paged")

    def _coordinator(self, key: str) -> LookupCoordinator | None:
        return self._station.personal if key in PERSONAL else self._station.lane(key)

    def _mark(self, reason: str, *keys: str, at: datetime | None = None) -> bool:
        woken: list[LookupCoordinator] = []
        for key in keys:
            coordinator = self._coordinator(key)
            if coordinator is None or not coordinator.mark_due(key, reason, at):
                continue
            if at is None:
                self._announced.add(key)
                self.marks[key] += 1
            if coordinator not in woken:
                woken.append(coordinator)
        for coordinator in woken:
            if at is None:
                self._wake(coordinator)
            else:
                self._wake_at(coordinator, at)
        return bool(woken)

    def _wake(self, coordinator: LookupCoordinator) -> None:
        self._entry.async_create_background_task(
            self._hass, coordinator.async_request_refresh(), "verdi live refresh"
        )

    def _wake_at(self, coordinator: LookupCoordinator, at: datetime) -> None:
        """Wake at the mark's time, not now: a run now fetches nothing and its refresh cooldown would hold
        the next notice's fetch (a page) for up to 10 s."""
        key = (id(coordinator), at)
        if key in self._timers:
            return

        @callback
        def fire(_now: datetime) -> None:
            self._timers.pop(key, None)
            self._wake(coordinator)

        self._timers[key] = async_track_point_in_utc_time(self._hass, fire, at)

    @callback
    def shutdown(self) -> None:
        for cancel in self._timers.values():
            cancel()
        self._timers.clear()

    def _persons(self) -> set[str]:
        personnel = (self._station.lane("personnel").data or {}).get("personnel") or {}
        return {str(p["id"]).lower() for p in personnel.get("persons") or [] if p.get("id")}

    def _vehicles(self) -> set[str]:
        vehicles = (self._station.lane("vehicles").data or {}).get("vehicles") or []
        return {str(v["id"]).lower() for v in vehicles if v.get("id")}

    # Connection state.

    @callback
    def state(self, connected: bool) -> None:
        self.connected = connected
        coordinators = [c for c in (self._station, self._station.fast) if c is not None]
        for coordinator in coordinators:
            coordinator.live_connected = connected
        if not connected:
            for coordinator in coordinators:
                coordinator.live_dropped()
                self._wake(coordinator)
        if connected:
            self._streak.clear()
            self._announced.clear()
            self._catch_up()
            self._roster_marks((self._station.data or {}).get("roster"))
        self._station.async_update_listeners()

    def _catch_up(self) -> None:
        """Fetch what Verdi may have changed before the connection was up: a change in that moment has
        no notice, and while connected the station's next tick is minutes away. So the station's lookups
        always; the page only when older than LIVE_PAGED_CATCH_UP_AGE, since its tick is a minute and a
        run on its lane holds the next notice's fetch for HA's 10 s refresh cooldown."""
        now = dt_util.now()
        keys = []
        for key in CATCH_UP:
            lookup = self._station.lane(key).lookups.get(key)
            if lookup is None:
                continue
            last = lookup.schedule.last_fetch
            if key != "paged" or last is None or now - last >= timedelta(seconds=LIVE_PAGED_CATCH_UP_AGE):
                keys.append(key)
        if keys:
            self._mark("live:connected", *keys)

    def _roster_marks(self, roster: Any) -> None:
        """Verdi may not announce a scheduled change at your station: fetch at the roster's next boundary."""
        if not isinstance(roster, list):
            return
        at = roster_change(roster, dt_util.now())
        if at is None:
            return
        at += timedelta(seconds=self._station.rng.uniform(*BOUNDARY_DELAY))
        self._mark("live:roster", "personnel", "readiness", at=at)

    # Fetches (from signals.py, for the station and the fast lane).

    @callback
    def fetched(self, key: str, new: Any, old: Any) -> None:
        if key == "roster":
            if self.connected:
                self._roster_marks(new)
            return
        if key not in CHECKED:
            return
        announced = key in self._announced
        self._announced.discard(key)
        if not self.connected or old is None:
            return
        lookup = self._station.lane(key).lookups.get(key)
        if lookup is None or lookup.schedule.last_reason != TICK:
            return
        if not announced and readiness_inputs(key, new) != readiness_inputs(key, old):
            self.unannounced += 1
            self._streak[key] += 1
            if self._streak[key] >= LIVE_UNANNOUNCED_LIMIT and self.client is not None:
                self._streak[key] = 0
                self.client.reconnect()
        else:
            self._streak[key] = 0

    # Visibility.

    def _today(self) -> None:
        today = dt_util.now().date()
        if self._day != today:
            self._day = today
            self.events.clear()
            self.marks.clear()
            self.dropped = self.bursts = 0

    def attributes(self) -> dict[str, Any]:
        client = self.client
        return {
            "since": client.since.isoformat() if client is not None and client.since else None,
            "reconnects_today": client.reconnects_today if client is not None else 0,
            "last_event": client.last_event.isoformat() if client is not None and client.last_event else None,
            "unannounced_changes": self.unannounced,
        }

    def diagnostics(self) -> dict[str, Any]:
        self._today()
        fast = self._station.fast
        return {
            **(self.client.diagnostics() if self.client is not None else {}),
            "events_today": dict(self.events),
            "dropped_today": self.dropped,
            "marks_today": dict(self.marks),
            "bursts_today": self.bursts,
            "unannounced_changes": self.unannounced,
            "ticks": {
                "station": self._station.tick_seconds(),
                "fast": fast.tick_seconds() if fast is not None else None,
            },
        }


@callback
def async_setup_live(
    hass: HomeAssistant, entry: ConfigEntry, station: VerdiCoordinator, signals: Any
) -> LiveSignals | None:
    """Start live updates when the option is on (the default); None when it's off."""
    if not entry.options.get(CONF_LIVE_UPDATES, True):
        return None
    live = LiveSignals(hass, entry, station)
    store = get_store(hass)
    live.client = LiveClient(
        async_get_clientsession(hass),
        entry.data[CONF_BASE_URL],
        lambda: store.get(entry.entry_id),
        station.guard,
        live.handle,
        live.state,
        station.rng,
    )
    signals.live = live
    entry.async_on_unload(live.shutdown)
    entry.async_create_background_task(hass, live.client.run(), "verdi live updates")
    return live
