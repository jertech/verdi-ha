# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Vehicles Verdi stopped listing: hidden at once, removed after a week, in view again when listed."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import LookupCoordinator

GONE_AFTER = timedelta(weeks=1)
CHECK_EVERY = timedelta(hours=1)
MISSING_SINCE = "missing_since"


@callback
def _tidy(hass: HomeAssistant, entry: ConfigEntry, vehicles: list[dict[str, Any]] | None) -> set[str]:
    """Return the vehicles listed again. No list or an empty one says nothing about a vehicle."""
    if not vehicles:
        return set()
    registry = er.async_get(hass)
    listed = {v["id"] for v in vehicles}
    prefix = f"{entry.entry_id}_vehicles_"
    now = dt_util.utcnow()
    back: set[str] = set()
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if not entity.unique_id.startswith(prefix):
            continue
        vehicle_id = entity.unique_id.removeprefix(prefix).removesuffix("_bin")
        since = entity.options.get(DOMAIN, {}).get(MISSING_SINCE)
        if vehicle_id in listed:
            if since:
                back.add(vehicle_id)
                registry.async_update_entity_options(entity.entity_id, DOMAIN, {})
            if entity.hidden_by is er.RegistryEntryHider.INTEGRATION:
                registry.async_update_entity(entity.entity_id, hidden_by=None)
            continue
        if since and now - dt_util.parse_datetime(since, raise_on_error=True) >= GONE_AFTER:
            registry.async_remove(entity.entity_id)
            continue
        if not since:
            registry.async_update_entity_options(entity.entity_id, DOMAIN, {MISSING_SINCE: now.isoformat()})
        if entity.hidden_by is None:  # also one made visible while it was gone
            registry.async_update_entity(entity.entity_id, hidden_by=er.RegistryEntryHider.INTEGRATION)
    return back


@callback
def async_track_vehicles(hass: HomeAssistant, entry: ConfigEntry, lane: LookupCoordinator) -> None:
    """Tidy now, before the platforms, then whenever the lookup's answer changes. Hourly too, because an
    unchanged answer wakes no listener: a vehicle made visible or a week that passed changes nothing in it."""

    def vehicles() -> list[dict[str, Any]] | None:
        return (lane.data or {}).get("vehicles")

    _tidy(hass, entry, vehicles())
    loaded = {v["id"] for v in vehicles() or []}

    @callback
    def tidy(_now: datetime | None = None) -> None:
        if "vehicles" in lane.failing:
            return
        if _tidy(hass, entry, vehicles()) - loaded:  # missing at setup, so it has no sensors yet
            # After the listeners: a reload now would let the ones still waiting write to removed entities.
            hass.loop.call_soon(hass.config_entries.async_schedule_reload, entry.entry_id)

    entry.async_on_unload(lane.async_add_listener(tidy))
    entry.async_on_unload(async_track_time_interval(hass, tidy, CHECK_EVERY, cancel_on_shutdown=True))
