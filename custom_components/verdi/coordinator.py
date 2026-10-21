# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Polls all Verdi lookups on one schedule."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

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
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from .token import get_store

_LOGGER = logging.getLogger(__name__)


def lookup_counts(data: dict[str, Any]) -> dict[str, int | None]:
    """How many items each lookup returned; numbers only, never content."""
    personnel = data.get("personnel") or {}
    return {
        key: (len(value) if isinstance(value, list) else None)
        for key, value in data.items()
        if key != "personnel"
    } | {"personnel": personnel.get("total")}


class VerdiCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, token: str) -> None:
        interval = max(int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)), MIN_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        d = entry.data
        self.show_names: bool = bool(entry.options.get(CONF_SHOW_NAMES, False))
        self.api = VerdiApi(async_get_clientsession(hass), d[CONF_BASE_URL], token)
        names = self.show_names
        self._failing: set[str] = set()
        self._lookups = {
            "readiness": (
                lambda: self.api.readiness(d[CONF_STATION_ID], d[CONF_VEHICLE_TRAIN_IDS]),
                parse.readiness_trains,
            ),
            "personnel": (
                lambda: self.api.personnel(d[CONF_STATION_ID], d[CONF_AVAILABILITY_IDS]),
                parse.personnel_summary,
            ),
            "vehicles": (lambda: self.api.vehicles(d[CONF_STATION_ID]), parse.vehicles),
            "teams": (lambda: self.api.team_on_duty(d[CONF_TEAM_GROUP_ID]), parse.teams_on_duty),
            "roster": (
                lambda: self.api.roster(d[CONF_CREW_FUNCTION_IDS]),
                lambda data: parse.roster(data, names=names),
            ),
        }

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
        if len(errors) == len(self._lookups):
            raise UpdateFailed(f"All Verdi lookups failed: {', '.join(errors)}")
        _LOGGER.debug("Verdi poll took %.1f s: %s", time.monotonic() - started, lookup_counts(data))
        return data
