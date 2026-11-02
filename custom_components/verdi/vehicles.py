# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Vehicles Verdi stopped listing: hidden at once, removed after a week, in view again when listed."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN

GONE_AFTER = timedelta(weeks=1)
MISSING_SINCE = "missing_since"


@callback
def async_tidy_vehicles(
    hass: HomeAssistant, entry: ConfigEntry, vehicles: list[dict[str, Any]] | None
) -> None:
    """Run at every setup, before the platforms. No list or an empty one says nothing about a vehicle."""
    if not vehicles:
        return
    registry = er.async_get(hass)
    listed = {v["id"] for v in vehicles}
    prefix = f"{entry.entry_id}_vehicles_"
    now = dt_util.utcnow()
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if not entity.unique_id.startswith(prefix):
            continue
        since = entity.options.get(DOMAIN, {}).get(MISSING_SINCE)
        if entity.unique_id.removeprefix(prefix).removesuffix("_bin") in listed:
            if since:
                registry.async_update_entity_options(entity.entity_id, DOMAIN, {})
            if entity.hidden_by is er.RegistryEntryHider.INTEGRATION:
                registry.async_update_entity(entity.entity_id, hidden_by=None)
        elif not since:
            registry.async_update_entity_options(entity.entity_id, DOMAIN, {MISSING_SINCE: now.isoformat()})
            if entity.hidden_by is None:
                registry.async_update_entity(entity.entity_id, hidden_by=er.RegistryEntryHider.INTEGRATION)
        elif now - dt_util.parse_datetime(since, raise_on_error=True) >= GONE_AFTER:
            registry.async_remove(entity.entity_id)
