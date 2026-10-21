# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Roster calendar, fed by FunctionCalendarEventGetForCalendarCommand."""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import VerdiConfigEntry, parse
from .api import VerdiError
from .const import CONF_FUNCTION_CALENDAR_ID
from .coordinator import VerdiCoordinator
from .entity import device_info

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: VerdiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    if entry.data.get(CONF_FUNCTION_CALENDAR_ID):
        async_add_entities([VerdiRosterCalendar(entry.runtime_data)])


def _to_event(item: dict[str, Any]) -> CalendarEvent | None:
    start = dt_util.parse_datetime(item["start"] or "")
    end = dt_util.parse_datetime(item["end"] or "")
    if not start or not end:
        return None
    return CalendarEvent(start=start, end=end, summary=item["summary"], uid=item["id"])


class VerdiRosterCalendar(CoordinatorEntity[VerdiCoordinator], CalendarEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "roster"

    def __init__(self, coordinator: VerdiCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._calendar_id = entry.data[CONF_FUNCTION_CALENDAR_ID]
        self._attr_unique_id = f"{entry.entry_id}_roster_calendar"
        self._attr_device_info = device_info(entry)
        self._upcoming: list[CalendarEvent] = []

    def _function_names(self) -> dict[str, str]:
        roster = (self.coordinator.data or {}).get("roster") or []
        return {r["id"]: r["function"] for r in roster if r.get("id")}

    async def _fetch(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        data = await self.coordinator.api.calendar_events(self._calendar_id, start, end)
        items = parse.calendar_events(data, self._function_names(), names=self.coordinator.show_names)
        events = [_to_event(e) for e in items]
        return sorted((e for e in events if e), key=lambda e: e.start)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        try:
            return await self._fetch(start_date, end_date)
        except VerdiError:
            return []

    async def async_update(self) -> None:
        await super().async_update()
        now = dt_util.utcnow()
        with suppress(VerdiError):
            self._upcoming = await self._fetch(now - timedelta(hours=24), now + timedelta(days=7))

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self.async_update()

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.utcnow()
        return next((e for e in self._upcoming if e.end > now), None)
