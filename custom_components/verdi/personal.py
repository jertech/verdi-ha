# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Your own data, from the read commands of Verdi's mobile app route.

Three coordinators on their own schedules: your availability, pre-alert and garrison; your
shifts and availability events; your statistics, which also refresh just after midnight and
shortly after a vehicle of the station starts or ends an intervention.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_time_change
from homeassistant.util import dt as dt_util

from . import parse_personal
from .api import VerdiApi, VerdiError
from .const import (
    CONF_EVENTS_INTERVAL,
    CONF_STATISTICS_INTERVAL,
    DOMAIN,
    LEGACY_PERSONAL_INTERVAL,
    PERSONAL_RETRY_SECONDS,
    STATISTICS_AFTER_INTERVENTION,
    STATISTICS_DAILY_AT,
)
from .coordinator import Fetch, Lookup, LookupCoordinator, Parser, VerdiCoordinator, pace


def request_language(hass: HomeAssistant) -> str:
    """Verdi answers in nl, fr or en; any other Home Assistant language gets en."""
    language = (hass.config.language or "").lower()
    return next((code for code in ("nl", "fr") if language.startswith(code)), "en")


class PersonId:
    """Your person GUID from security/users/authorize, asked once and kept in memory."""

    def __init__(self, api: VerdiApi) -> None:
        self._api = api
        self._value: str | None = None

    async def get(self) -> str:
        if self._value is None:
            guid = (await self._api.current_user()).get("personGuid")
            if not isinstance(guid, str) or not guid:
                raise VerdiError("security/users/authorize: no personGuid")
            self._value = guid
        return self._value


@dataclass
class Personal:
    fast: LookupCoordinator
    events: LookupCoordinator
    statistics: LookupCoordinator

    @property
    def coordinators(self) -> tuple[LookupCoordinator, ...]:
        return (self.fast, self.events, self.statistics)


def create_personal(hass: HomeAssistant, entry: ConfigEntry, station: VerdiCoordinator) -> Personal:
    api = station.api
    person, language = PersonId(api), request_language(hass)

    async def events() -> dict[str, Any]:
        return await api.upcoming_events(await person.get(), language)

    async def statistics() -> dict[str, Any]:
        return await api.statistics(await person.get(), language)

    def coordinator(name: str, option: str, lookups: dict[str, tuple[Fetch, Parser]]) -> LookupCoordinator:
        return LookupCoordinator(
            hass,
            entry,
            api,
            f"{DOMAIN} {name}",
            {key: Lookup(fetch, parser) for key, (fetch, parser) in lookups.items()},
            pace=lambda: pace(entry.options, option),
            retry=timedelta(seconds=PERSONAL_RETRY_SECONDS),
            keep_on_failure=True,
            guard=station.guard,
            rng=station.rng,
        )

    return Personal(
        fast=coordinator(
            "personal",
            LEGACY_PERSONAL_INTERVAL,
            {
                "availability": (api.my_availability, parse_personal.my_availability),
                "pre_alerts": (api.pre_alerts, parse_personal.pre_alerts),
                "garrison": (api.garrison, parse_personal.garrison),
            },
        ),
        events=coordinator(
            "events", CONF_EVENTS_INTERVAL, {"events": (events, parse_personal.upcoming_events)}
        ),
        statistics=coordinator(
            "statistics",
            CONF_STATISTICS_INTERVAL,
            {"statistics": (statistics, lambda data: parse_personal.statistics(data, dt_util.now()))},
        ),
    )


def _on_intervention(data: dict[str, Any] | None) -> frozenset[str]:
    return frozenset(v["id"] for v in (data or {}).get("vehicles") or [] if v.get("on_intervention"))


class StatisticsTriggers:
    """Refresh statistics at 00:05 local time, and a while after a vehicle of the station starts or
    ends an intervention, when times called change. Changes close together cause one refresh."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        station: VerdiCoordinator,
        statistics: LookupCoordinator,
    ) -> None:
        self._hass, self._station, self._statistics = hass, station, statistics
        self._seen = _on_intervention(station.data)
        self._pending: CALLBACK_TYPE | None = None
        hour, minute = STATISTICS_DAILY_AT
        entry.async_on_unload(async_track_time_change(hass, self._daily, hour=hour, minute=minute, second=0))
        entry.async_on_unload(station.async_add_listener(self._station_updated))
        entry.async_on_unload(self._cancel)

    async def _daily(self, _now: datetime) -> None:
        await self._statistics.async_refresh_lookup("statistics")

    async def _after_intervention(self, _now: datetime) -> None:
        self._pending = None
        await self._statistics.async_refresh_lookup("statistics")

    @callback
    def _station_updated(self) -> None:
        seen = _on_intervention(self._station.data)
        if seen == self._seen:
            return
        self._seen = seen
        self._cancel()
        self._pending = async_call_later(
            self._hass,
            STATISTICS_AFTER_INTERVENTION,
            HassJob(self._after_intervention, cancel_on_shutdown=True),
        )

    @callback
    def _cancel(self) -> None:
        if self._pending:
            self._pending()
            self._pending = None


async def async_setup_personal(
    hass: HomeAssistant, entry: ConfigEntry, station: VerdiCoordinator
) -> Personal:
    personal = create_personal(hass, entry, station)
    for coordinator in personal.coordinators:
        await coordinator.async_refresh()
    StatisticsTriggers(hass, entry, station, personal.statistics)
    return personal


def personal_counts(personal: Personal | None) -> dict[str, Any] | None:
    """How much of your own data each lookup returned; numbers and flags only, never content."""
    if personal is None:
        return None
    fast, events, stats = (c.data or {} for c in personal.coordinators)
    planned, numbers = events.get("events") or {}, stats.get("statistics") or {}
    return {
        "availability": fast.get("availability") is not None,
        "pre_alerts": len(fast.get("pre_alerts") or []),
        "garrison": bool((fast.get("garrison") or {}).get("active")),
        "shifts": len(planned.get("shifts") or []),
        "availability_events": len(planned.get("availability") or []),
        "availability_year": len(numbers.get("availability_year") or []),
        "times_called": len(numbers.get("times_called") or []),
        "last_update_success": {
            "fast": personal.fast.last_update_success,
            "events": personal.events.last_update_success,
            "statistics": personal.statistics.last_update_success,
        },
    }
