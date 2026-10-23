# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Calendars: the roster (FunctionCalendarEventGetForCalendarCommand) and your own shifts and availability."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import VerdiConfigEntry, parse
from .api import VerdiError
from .const import CALENDAR_CACHE, CONF_FUNCTION_CALENDAR_ID
from .coordinator import LookupCoordinator, VerdiCoordinator
from .entity import device_info

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: VerdiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    c = entry.runtime_data
    entities: list[CalendarEntity] = []
    if entry.data.get(CONF_FUNCTION_CALENDAR_ID):
        entities.append(VerdiRosterCalendar(c))
    if c.personal is not None:
        entities += [
            PersonalCalendar(c.personal.events, "my_shifts", "shifts"),
            PersonalCalendar(c.personal.events, "my_availability", "availability"),
        ]
    async_add_entities(entities)


def _to_event(item: dict[str, Any]) -> CalendarEvent | None:
    start = dt_util.parse_datetime(item["start"] or "")
    end = dt_util.parse_datetime(item["end"] or "")
    if not start or not end:
        return None
    return CalendarEvent(start=start, end=end, summary=item["summary"], uid=item["id"])


class VerdiRosterCalendar(CoordinatorEntity[VerdiCoordinator], CalendarEntity):
    """Shifts of the function calendar. Current and next come from the station's polls; a
    calendar view asks Verdi for its range, served from memory for a few minutes."""

    _attr_has_entity_name = True
    _attr_translation_key = "roster"

    def __init__(self, coordinator: VerdiCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._calendar_id = entry.data[CONF_FUNCTION_CALENDAR_ID]
        self._attr_unique_id = f"{entry.entry_id}_roster_calendar"
        self._attr_device_info = device_info(entry)
        self._cache: dict[tuple[datetime, datetime], tuple[float, list[CalendarEvent]]] = {}

    def _events(self, items: list[dict[str, Any]]) -> list[CalendarEvent]:
        roster = (self.coordinator.data or {}).get("roster") or []
        functions = {r["id"]: r["function"] for r in roster if r.get("id")}
        events = [
            _to_event({**i, "summary": parse.calendar_summary(functions.get(i["function_id"]), i["person"])})
            for i in items
        ]
        return sorted((e for e in events if e), key=lambda e: e.start)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        key = (start_date, end_date)
        cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < CALENDAR_CACHE:
            return cached[1]
        guard = self.coordinator.guard
        if not guard.can_call():
            return cached[1] if cached else []
        guard.record_call()
        try:
            data = await self.coordinator.api.calendar_events(self._calendar_id, start_date, end_date)
        except VerdiError:
            return cached[1] if cached else []
        events = self._events(parse.calendar_events(data, names=self.coordinator.show_names))
        if key not in self._cache and len(self._cache) >= 8:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = (time.monotonic(), events)
        return events

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.utcnow()
        upcoming = self._events((self.coordinator.data or {}).get("roster_calendar") or [])
        return next((e for e in upcoming if e.end > now), None)


class PersonalCalendar(CoordinatorEntity[LookupCoordinator], CalendarEntity):
    """Your own shifts, or your availability events, about a month ahead, from the last poll."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LookupCoordinator, translation_key: str, section: str) -> None:
        super().__init__(coordinator)
        self._section = section
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{translation_key}_calendar"
        self._attr_device_info = device_info(coordinator.config_entry)

    @property
    def _events(self) -> list[CalendarEvent]:
        items = ((self.coordinator.data or {}).get("events") or {}).get(self._section) or []
        return [
            CalendarEvent(
                start=i["start"],
                end=i["end"],
                summary=i["summary"],
                description=i["description"],
                uid=i["id"],
            )
            for i in items
        ]

    @property
    def available(self) -> bool:
        return super().available and (self.coordinator.data or {}).get("events") is not None

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.utcnow()
        return next((e for e in self._events if e.end > now), None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [e for e in self._events if e.end > start_date and e.start < end_date]
