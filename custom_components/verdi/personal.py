# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Your own data, from the read commands of Verdi's mobile app route.

One coordinator without a tick: each switched-on lookup runs after its safety interval, at a
time its data announced, or when signals.py marks it due. Your events and statistics are first
fetched a few minutes after setup.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import parse_personal
from .const import (
    CONF_ALERTS_SAFETY,
    CONF_AVAILABILITY_SAFETY,
    CONF_EVENTS_INTERVAL,
    CONF_GARRISON,
    CONF_MY_AVAILABILITY,
    CONF_MY_EVENTS,
    CONF_PRE_ALERT,
    CONF_STATISTICS,
    CONF_STATISTICS_INTERVAL,
    DOMAIN,
    END_DELAY,
    PERSONAL_RETRY_SECONDS,
    STARTUP_DELAY,
)
from .coordinator import (
    Lookup,
    LookupCoordinator,
    VerdiCoordinator,
    enabled,
    request_language,
    safety_schedule,
)
from .schedule import earliest_after

__all__ = ["create_personal", "personal_counts", "request_language"]


def statistics_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    """Where the statistics counters are remembered between restarts: names only, no values."""
    return Store(hass, 1, f"{DOMAIN}.statistics.{entry_id}")


def _ends(items: Any, now: datetime) -> datetime | None:
    if isinstance(items, dict):
        return earliest_after(items.get("ends") or [], now)
    return earliest_after((i.get("end") for i in items or []), now)


def create_personal(
    hass: HomeAssistant, entry: ConfigEntry, station: VerdiCoordinator
) -> LookupCoordinator | None:
    """The coordinator for your own data, or None when every kind is switched off."""
    o, api = entry.options, station.api
    person, language = station.person, request_language(hass)

    async def events() -> dict[str, Any]:
        return await api.upcoming_events(await person.get(report=False), language)

    async def statistics() -> dict[str, Any]:
        return await api.statistics(await person.get(report=False), language)

    def later() -> datetime:
        return dt_util.now() + timedelta(seconds=station.rng.uniform(*STARTUP_DELAY))

    lookups: dict[str, Lookup] = {}
    if enabled(o, CONF_MY_AVAILABILITY):
        lookups["availability"] = Lookup(
            api.my_availability,
            parse_personal.my_availability,
            safety_schedule(o, CONF_AVAILABILITY_SAFETY, next_change=_ends, known_delay=END_DELAY),
        )
    if enabled(o, CONF_PRE_ALERT):
        lookups["pre_alerts"] = Lookup(
            api.pre_alerts,
            parse_personal.pre_alerts,
            safety_schedule(o, CONF_ALERTS_SAFETY, next_change=_ends, known_delay=END_DELAY),
        )
    if enabled(o, CONF_GARRISON):
        lookups["garrison"] = Lookup(
            api.garrison, parse_personal.garrison, safety_schedule(o, CONF_ALERTS_SAFETY)
        )
    if enabled(o, CONF_MY_EVENTS):
        lookups["events"] = Lookup(
            events, parse_personal.upcoming_events, safety_schedule(o, CONF_EVENTS_INTERVAL)
        )
        lookups["events"].schedule.start_at(later())
    if enabled(o, CONF_STATISTICS):
        lookups["statistics"] = Lookup(
            statistics,
            lambda data: parse_personal.statistics(data, dt_util.now()),
            safety_schedule(o, CONF_STATISTICS_INTERVAL),
        )
        lookups["statistics"].schedule.start_at(later())
    if not lookups:
        return None
    return LookupCoordinator(
        hass,
        entry,
        api,
        f"{DOMAIN} personal",
        lookups,
        pace=lambda: None,
        retry=timedelta(seconds=PERSONAL_RETRY_SECONDS),
        keep_on_failure=True,
        guard=station.guard,
        rng=station.rng,
    )


def personal_counts(personal: LookupCoordinator | None) -> dict[str, Any] | None:
    """How much of your own data each switched-on lookup returned; numbers and flags only."""
    if personal is None:
        return None
    data, on = personal.data or {}, personal.lookups
    counts: dict[str, Any] = {}
    if "availability" in on:
        counts["availability"] = data.get("availability") is not None
    if "pre_alerts" in on:
        counts["pre_alerts"] = len(data.get("pre_alerts") or [])
    if "garrison" in on:
        counts["garrison"] = bool((data.get("garrison") or {}).get("active"))
    if "events" in on:
        planned = data.get("events") or {}
        counts["shifts"] = len(planned.get("shifts") or [])
        counts["availability_events"] = len(planned.get("availability") or [])
    if "statistics" in on:
        numbers = data.get("statistics") or {}
        counts["availability_year"] = len(numbers.get("availability_year") or [])
        counts["times_called"] = len(numbers.get("times_called") or [])
    counts["last_update_success"] = personal.last_update_success
    return counts
