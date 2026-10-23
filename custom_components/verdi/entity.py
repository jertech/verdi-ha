# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Shared entity helpers."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LookupCoordinator


def device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        model="Verdi (unofficial integration)",
        entry_type=DeviceEntryType.SERVICE,
    )


def find(items: list[dict[str, Any]] | None, item_id: str) -> dict[str, Any] | None:
    return next((i for i in items or [] if i.get("id") == item_id), None)


class VerdiEntity(CoordinatorEntity[LookupCoordinator]):
    """A Verdi entity on the entry's device. update_entity fetches only its own lookup."""

    _attr_has_entity_name = True
    lookup: str | None = None

    async def async_update(self) -> None:
        if self.lookup is None:
            self.async_write_ha_state()
            return
        await self.coordinator.async_refresh_lookup(self.lookup)
