# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""The status and duration the "Set status" button uses. Choosing writes nothing to Verdi."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import VerdiConfigEntry
from .coordinator import VerdiCoordinator
from .entity import VerdiEntity, device_info
from .write import StatusWriter
from .write_data import DURATIONS

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: VerdiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    c = entry.runtime_data
    if c.writer is not None:
        async_add_entities([StatusSelect(c, c.writer), DurationSelect(c, c.writer)])


class _ChoiceSelect(VerdiEntity, SelectEntity, RestoreEntity):
    coordinator: VerdiCoordinator
    _key: str

    def __init__(self, coordinator: VerdiCoordinator, writer: StatusWriter) -> None:
        super().__init__(coordinator)
        self._writer = writer
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{self._attr_translation_key}"
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._restore(last.state)

    def _restore(self, value: str) -> None:
        self._writer.choice[self._key] = value

    @property
    def current_option(self) -> str | None:
        value = self._writer.choice[self._key]
        return value if value in self.options else None

    async def async_select_option(self, option: str) -> None:
        self._writer.choice[self._key] = option
        self.async_write_ha_state()


class StatusSelect(_ChoiceSelect):
    _attr_translation_key = "status_to_set"
    _key = "status"

    @property
    def options(self) -> list[str]:
        return self._writer.status_names() or []

    @property
    def available(self) -> bool:
        return (
            super().available
            and self._writer.status_names() is not None
            and not self._writer.rights_missing("status")
        )


class DurationSelect(_ChoiceSelect):
    _attr_translation_key = "duration"
    _attr_options = list(DURATIONS)
    _key = "duration"

    def _restore(self, value: str) -> None:
        if value in DURATIONS:
            self._writer.choice[self._key] = value
