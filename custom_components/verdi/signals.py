# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Change signals in the station data that make your own lookups due.

Your own line in the personnel list (availability, pre-alert, garrison, intervention), the
watched vehicles' interventions and your shifts in the roster. Also sets the station's tick
during an intervention, and refreshes statistics once a day between 00:05 and 01:05.
"""

from __future__ import annotations

import zlib
from contextlib import suppress
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .api import VerdiError
from .const import (
    CONF_WATCHED_VEHICLES,
    DAILY_JITTER,
    DAILY_OFFSET_MAX,
    PERSONAL_RETRY_SECONDS,
    STATISTICS_AFTER_INTERVENTION,
    STATISTICS_DAILY_AT,
    STATISTICS_MAX_DELAY,
    TRIGGER_DELAY,
)
from .coordinator import LookupCoordinator, VerdiCoordinator

OWN = ("availability", "pre_alerts", "garrison")


def _person(personnel: dict[str, Any] | None, me: str | None) -> dict[str, Any] | None:
    if not me:
        return None
    return next((p for p in (personnel or {}).get("persons") or [] if p.get("id") == me), None)


def _mine(roster: list[dict[str, Any]] | None) -> list[bool]:
    return [bool((i[slot] or {}).get("mine")) for i in roster or [] for slot in ("current", "next")]


class Signals:
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        station: VerdiCoordinator,
        personal: LookupCoordinator | None,
    ) -> None:
        self._hass, self._entry, self._station, self._personal = hass, entry, station, personal
        self._picked = set(entry.options.get(CONF_WATCHED_VEHICLES) or [])
        self._ready = self._marked = False
        self._stats_first: datetime | None = None
        self._retry_at: datetime | None = None
        self._unsub_daily: CALLBACK_TYPE | None = None
        self._stopped = False
        station.on_fetched, station.on_run = self._station_fetched, self._station_run
        if personal is not None:
            personal.on_fetched = self._personal_fetched
        entry.async_on_unload(self._stop)

    @callback
    def start(self) -> None:
        """Setup is done: from now on, marks also wake the personal coordinator."""
        self._ready = True
        if self._personal is not None and "statistics" in self._personal.lookups:
            self._schedule_daily()

    def _later(self, base: float = 0.0) -> datetime:
        return dt_util.now() + timedelta(seconds=base + self._station.rng.uniform(*TRIGGER_DELAY))

    def _mark(self, key: str, reason: str, at: datetime | None = None, *, replace: bool = False) -> None:
        if self._personal is not None and self._personal.mark_due(key, reason, at, replace=replace):
            self._marked = True

    def _watched(self, vehicles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """The picked vehicles; all of them when none is picked or none of the picked still exists."""
        picked = [v for v in vehicles if v.get("id") in self._picked]
        return picked or vehicles

    @callback
    def _station_fetched(self, key: str, new: Any, old: Any) -> None:
        if self._personal is None:
            return
        if key == "personnel":
            self._own_line(new, old)
        elif key == "vehicles" and old is not None:
            before = {v["id"]: v["on_intervention"] for v in self._watched(old)}
            if any(
                before.get(v["id"], v["on_intervention"]) != v["on_intervention"] for v in self._watched(new)
            ):
                self._statistics_soon("trigger:vehicle")
                self._mark("garrison", "trigger:vehicle")
        elif key == "roster" and old is not None and _mine(new) != _mine(old):
            self._mark("events", "trigger:roster", self._later())

    def _own_line(self, new: dict[str, Any], old: dict[str, Any] | None) -> None:
        me = self._station.person.value
        mine = _person(new, me)
        if mine is None:
            for key in OWN:
                self._mark(key, "trigger:no_own_line")
            if me is None or self._station.availabilities.listed is None:
                self._retry_missing()
            return
        was = _person(old, me)
        if old is None:
            return  # the first poll; startup covers it
        if was is None or mine["availability"] != was["availability"]:
            self._mark("availability", "trigger:own_availability")
        was = was or {}
        if mine["on_pre_alert"] != bool(was.get("on_pre_alert")):
            self._mark("pre_alerts", "trigger:own_pre_alert")
        elif mine["on_pre_alert"]:
            self._mark("pre_alerts", "active")
        if mine["garrison_crew"] != bool(was.get("garrison_crew")):
            self._mark("garrison", "trigger:own_garrison")
        elif mine["garrison_crew"]:
            self._mark("garrison", "active")
        if mine["on_intervention"] != bool(was.get("on_intervention")):
            self._statistics_soon("trigger:own_intervention")

    def _retry_missing(self) -> None:
        """Ask again for your person GUID or the availability list, whichever is missing."""
        now = dt_util.now()
        if self._retry_at and now < self._retry_at:
            return
        self._retry_at = now + timedelta(seconds=PERSONAL_RETRY_SECONDS)

        async def ask() -> None:
            with suppress(VerdiError):
                await self._station.person.get()
            if self._station.availabilities.listed is None:
                with suppress(VerdiError):
                    await self._station.availabilities.load()

        self._entry.async_create_background_task(self._hass, ask(), "verdi own line retry")

    def _statistics_soon(self, reason: str) -> None:
        """Statistics a while after a trigger; later triggers push it back, within a limit."""
        if self._personal is None or "statistics" not in self._personal.lookups:
            return
        now = dt_util.now()
        if self._stats_first is None or now - self._stats_first >= timedelta(seconds=STATISTICS_MAX_DELAY):
            self._stats_first = now  # a burst starts; also after a failed fetch left the last one behind
        at = min(
            self._later(STATISTICS_AFTER_INTERVENTION),
            self._stats_first + timedelta(seconds=STATISTICS_MAX_DELAY),
        )
        self._mark("statistics", reason, at, replace=True)

    @callback
    def _station_run(self, data: dict[str, Any], previous: dict[str, Any]) -> None:
        personnel = data.get("personnel") or {}
        self._station.intervention = (
            any(v["on_intervention"] for v in self._watched(data.get("vehicles") or []))
            or bool(personnel.get("on_intervention"))
            or bool(personnel.get("on_pre_alert"))
        )
        if self._marked and self._ready and self._personal is not None:
            self._marked = False
            self._entry.async_create_background_task(
                self._hass, self._personal.async_request_refresh(), "verdi personal refresh"
            )

    @callback
    def _personal_fetched(self, key: str, new: Any, old: Any) -> None:
        if key == "statistics":
            self._stats_first = None
        elif key == "availability" and old is not None and new != old:
            self._mark("events", "trigger:availability", self._later())

    def _schedule_daily(self, first_day: date | None = None) -> None:
        hour, minute = STATISTICS_DAILY_AT
        offset = zlib.crc32(self._entry.entry_id.encode()) % DAILY_OFFSET_MAX
        offset += self._station.rng.uniform(0, DAILY_JITTER)
        now = dt_util.now()
        day = first_day or now.date()
        while True:
            when = dt_util.start_of_local_day(day) + timedelta(hours=hour, minutes=minute, seconds=offset)
            if when > now:
                break
            day += timedelta(days=1)
        self._unsub_daily = async_track_point_in_time(self._hass, self._daily, when)

    async def _daily(self, _now: datetime) -> None:
        self._unsub_daily = None
        try:
            if self._personal is not None:
                self._personal.mark_due("statistics", "daily")
                await self._personal.async_request_refresh()
        finally:
            if not self._stopped:
                self._schedule_daily(dt_util.now().date() + timedelta(days=1))

    @callback
    def _stop(self) -> None:
        self._stopped = True
        if self._unsub_daily:
            self._unsub_daily()
            self._unsub_daily = None
