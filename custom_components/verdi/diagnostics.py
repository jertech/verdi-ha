# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Diagnostics: settings with every identifier redacted, and counts instead of data."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import VerdiConfigEntry
from .api import token_expiry
from .const import (
    CONF_ACCOUNT_SUB,
    CONF_AVAILABILITY_IDS,
    CONF_BASE_URL,
    CONF_CREW_FUNCTION_IDS,
    CONF_FUNCTION_CALENDAR_ID,
    CONF_STATION_ID,
    CONF_TEAM_GROUP_ID,
    CONF_VEHICLE_TRAIN_IDS,
    CONF_WATCHED_VEHICLES,
    LEGACY_PERSON_ID,
)
from .coordinator import lookup_counts
from .estimate import steady_per_min
from .personal import personal_counts
from .token import get_store

TO_REDACT = {
    CONF_ACCOUNT_SUB,
    CONF_AVAILABILITY_IDS,
    CONF_BASE_URL,
    CONF_CREW_FUNCTION_IDS,
    CONF_FUNCTION_CALENDAR_ID,
    LEGACY_PERSON_ID,
    CONF_STATION_ID,
    CONF_TEAM_GROUP_ID,
    CONF_VEHICLE_TRAIN_IDS,
    CONF_WATCHED_VEHICLES,
    "token",
    "token_file",
}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: VerdiConfigEntry) -> dict[str, Any]:
    coordinator = getattr(entry, "runtime_data", None)
    data = (coordinator.data or {}) if coordinator else {}
    now = dt_util.now()
    token = get_store(hass).tokens.get(entry.entry_id)
    return {
        "entry": {
            "version": entry.version,
            "state": entry.state.value,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "token": {
            "present": token is not None,
            "expires": (exp.isoformat() if (exp := token_expiry(token)) else None),
        },
        "counts": lookup_counts(data),
        "availabilities": coordinator.availabilities.diagnostics() if coordinator else None,
        "personal": personal_counts(coordinator.personal) if coordinator else None,
        "schedules": {
            "station": coordinator.schedule_diagnostics(now) if coordinator else None,
            "personal": (
                coordinator.personal.schedule_diagnostics(now)
                if coordinator and coordinator.personal
                else None
            ),
            "fast": coordinator.fast.schedule_diagnostics(now) if coordinator and coordinator.fast else None,
        },
        "pace": coordinator.pace_name if coordinator else None,
        "steady_per_min": steady_per_min(dict(entry.options)),
        "fast_lane": {
            "active": sorted(coordinator.fast.lookups) if coordinator and coordinator.fast else [],
            "paging_paused": bool(coordinator.fast.paused) if coordinator and coordinator.fast else False,
        },
        "guard": coordinator.guard.diagnostics() if coordinator else None,
        "timing": coordinator.timing.diagnostics() if coordinator and coordinator.timing else None,
        "writes": (
            coordinator.writer.diagnostics()
            if coordinator and getattr(coordinator, "writer", None) is not None
            else None
        ),
        "last_update_success": coordinator.last_update_success if coordinator else None,
    }
