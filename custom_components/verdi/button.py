# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Set your status now, or go back to planning. A user who isn't an admin is refused."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VerdiConfigEntry
from .coordinator import LookupCoordinator
from .entity import VerdiEntity, device_info
from .write import StatusWriter, require_admin

# 0: a press while a write runs must reach the writer and be refused busy, not wait its turn and write again.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: VerdiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    c = entry.runtime_data
    if c.writer is None:
        return
    entities: list[ButtonEntity] = [SetStatusButton(c, c.writer)]
    if (p := c.personal) is not None and "availability" in p.lookups:
        entities.append(ReturnToPlanningButton(p, c.writer))
    async_add_entities(entities)


class _StatusButton(VerdiEntity, ButtonEntity):
    def __init__(self, coordinator: LookupCoordinator, writer: StatusWriter) -> None:
        super().__init__(coordinator)
        self._writer = writer
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{self._attr_translation_key}"
        self._attr_device_info = device_info(entry)

    @property
    def available(self) -> bool:
        return super().available and not self._writer.rights_missing("status")


class SetStatusButton(_StatusButton):
    _attr_translation_key = "set_status"

    async def async_press(self) -> None:
        await require_admin(self.hass, self._context)
        await self._writer.add_exception(self._writer.choice["status"], self._writer.choice["duration"])


class ReturnToPlanningButton(_StatusButton):
    _attr_translation_key = "back_to_planning"

    @property
    def available(self) -> bool:
        mine = (self.coordinator.data or {}).get("availability") or {}
        return super().available and any(b.get("can_return") for b in mine.get("blocks") or [])

    async def async_press(self) -> None:
        await require_admin(self.hass, self._context)
        await self._writer.return_to_planning()
