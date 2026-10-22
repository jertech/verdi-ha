# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Polls Verdi lookups on schedules: the station's here, your own in personal.py."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import parse
from .api import VerdiApi, VerdiAuthError, VerdiError
from .const import (
    CONF_AVAILABILITY_IDS,
    CONF_BASE_URL,
    CONF_CREW_FUNCTION_IDS,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_NAMES,
    CONF_STATION_ID,
    CONF_TEAM_GROUP_ID,
    CONF_VEHICLE_TRAIN_IDS,
    DOMAIN,
    INTERVALS,
)
from .token import get_store

if TYPE_CHECKING:
    from .personal import Personal

_LOGGER = logging.getLogger(__name__)

type Fetch = Callable[[], Awaitable[dict[str, Any]]]
type Parser = Callable[[dict[str, Any]], Any]


def interval(options: Mapping[str, Any], key: str) -> timedelta:
    """An interval option as a timedelta, never below its minimum."""
    default, minimum, _maximum, unit = INTERVALS[key]
    return timedelta(seconds=max(int(options.get(key, default)), minimum) * unit)


def lookup_counts(data: dict[str, Any]) -> dict[str, int | None]:
    """How many items each lookup returned; numbers only, never content."""
    personnel = data.get("personnel") or {}
    return {
        key: (len(value) if isinstance(value, list) else None)
        for key, value in data.items()
        if key != "personnel"
    } | {"personnel": personnel.get("total")}


class LookupCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Runs a few lookups on one schedule. A failing lookup keeps its previous value.

    keep_on_failure: when every lookup fails, keep showing earlier values instead of marking the
    entities unavailable. retry: after a failed lookup, poll again this soon.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: VerdiApi,
        name: str,
        update_interval: timedelta,
        lookups: dict[str, tuple[Fetch, Parser]],
        *,
        keep_on_failure: bool = False,
        retry: timedelta | None = None,
    ) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=name, update_interval=update_interval)
        self.api = api
        self._lookups = lookups
        self._interval = update_interval
        self._keep_on_failure = keep_on_failure
        self._retry = retry
        self._failing: set[str] = set()

    def _refresh_token(self) -> None:
        """Pick up the newest pushed token before each poll."""
        store = get_store(self.hass)
        token = store.get(self.config_entry.entry_id)
        if token is None:
            expired = self.config_entry.entry_id in store.tokens
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="token_expired" if expired else "no_token"
            )
        self.api.set_token(token)

    async def _async_update_data(self) -> dict[str, Any]:
        self._refresh_token()
        started = time.monotonic()
        previous = self.data or {}
        data: dict[str, Any] = {}
        errors = []
        for key, (fetch, parser) in self._lookups.items():
            try:
                data[key] = parser(await fetch())
            except VerdiAuthError as err:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN, translation_key="token_rejected"
                ) from err
            except (VerdiError, KeyError, TypeError, AttributeError) as err:
                # One failing lookup should not take the other sensors down. The message
                # holds only the path and status or error type, never response content.
                _LOGGER.warning(
                    "Verdi lookup %s failed: %s",
                    key,
                    err if isinstance(err, VerdiError) else type(err).__name__,
                )
                errors.append(key)
                data[key] = previous.get(key)
            else:
                if key in self._failing:
                    _LOGGER.info("Verdi lookup %s works again", key)
        self._failing = set(errors)
        if self._retry is not None:
            self.update_interval = min(self._interval, self._retry) if errors else self._interval
        nothing_to_show = not (self._keep_on_failure and any(v is not None for v in data.values()))
        if len(errors) == len(self._lookups) and nothing_to_show:
            raise UpdateFailed(f"All Verdi lookups failed: {', '.join(errors)}")
        _LOGGER.debug("Verdi poll took %.1f s: %s", time.monotonic() - started, lookup_counts(data))
        return data


class VerdiCoordinator(LookupCoordinator):
    """The station's lookups. Your own lookups, when enabled, are in .personal."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, token: str) -> None:
        d = entry.data
        names = bool(entry.options.get(CONF_SHOW_NAMES, False))
        api = VerdiApi(async_get_clientsession(hass), d[CONF_BASE_URL], token)
        lookups: dict[str, tuple[Fetch, Parser]] = {
            "readiness": (
                lambda: api.readiness(d[CONF_STATION_ID], d[CONF_VEHICLE_TRAIN_IDS]),
                parse.readiness_trains,
            ),
            "personnel": (
                lambda: api.personnel(d[CONF_STATION_ID], d[CONF_AVAILABILITY_IDS]),
                parse.personnel_summary,
            ),
            "vehicles": (lambda: api.vehicles(d[CONF_STATION_ID]), parse.vehicles),
            "teams": (lambda: api.team_on_duty(d[CONF_TEAM_GROUP_ID]), parse.teams_on_duty),
            "roster": (
                lambda: api.roster(d[CONF_CREW_FUNCTION_IDS]),
                lambda data: parse.roster(data, names=names),
            ),
        }
        super().__init__(hass, entry, api, DOMAIN, interval(entry.options, CONF_SCAN_INTERVAL), lookups)
        self.show_names: bool = names
        self.personal: Personal | None = None
