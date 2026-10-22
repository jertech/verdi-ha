# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Polls Verdi lookups, each only when it is due (schedule.py). The station's are here, your own
in personal.py."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import parse, schedule
from .api import VerdiApi, VerdiAuthError, VerdiError, VerdiUnavailable
from .const import (
    CALL_GAP,
    CONF_AVAILABILITY_IDS,
    CONF_BASE_URL,
    CONF_CREW_FUNCTION_IDS,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_NAMES,
    CONF_STATION_ID,
    CONF_TEAM_GROUP_ID,
    CONF_VEHICLE_TRAIN_IDS,
    DOMAIN,
    FEATURES,
    IDLE_WAKE,
    INTERVALS,
    MIN_WAKE,
    REJECTED_WINDOW,
)
from .guard import Guard, get_guard
from .schedule import MANUAL, TICK, LookupSchedule, jittered
from .token import get_store

if TYPE_CHECKING:
    from .personal import Personal

_LOGGER = logging.getLogger(__name__)

type Fetch = Callable[[], Awaitable[dict[str, Any]]]
type Parser = Callable[[dict[str, Any]], Any]
type Pace = Callable[[], tuple[float, float] | None]
type FetchHook = Callable[[str, Any, Any], None]
type RunHook = Callable[[dict[str, Any], dict[str, Any]], None]


def interval(options: Mapping[str, Any], key: str) -> timedelta:
    """An interval option as a timedelta, never below its minimum."""
    default, minimum, _maximum, unit = INTERVALS[key]
    return timedelta(seconds=max(int(options.get(key, default)), minimum) * unit)


def minimum(key: str) -> float:
    """An interval option's minimum, in seconds."""
    _default, low, _maximum, unit = INTERVALS[key]
    return float(low * unit)


def pace(options: Mapping[str, Any], key: str) -> tuple[float, float]:
    """A tick interval option: (seconds, minimum seconds)."""
    return interval(options, key).total_seconds(), minimum(key)


def enabled(options: Mapping[str, Any], key: str) -> bool:
    """Whether a kind of your own data is switched on."""
    return bool(options.get(key, FEATURES[key]))


def lookup_counts(data: dict[str, Any]) -> dict[str, int | None]:
    """How many items each lookup returned; numbers only, never content."""
    personnel = data.get("personnel") or {}
    return {
        key: (len(value) if isinstance(value, list) else None)
        for key, value in data.items()
        if key != "personnel"
    } | {"personnel": personnel.get("total")}


@dataclass
class Lookup:
    fetch: Fetch
    parse: Parser
    schedule: LookupSchedule = field(default_factory=lambda: LookupSchedule(always=True))


class LookupCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Runs the due lookups of a group. A failing lookup keeps its previous value.

    pace: the tick as (seconds, minimum), or None to wake only when a lookup is due. retry: a
    failed lookup is due again this soon. keep_on_failure: when nothing could be fetched, keep
    earlier values instead of marking the entities unavailable. on_fetched and on_run let
    signals.py mark other lookups due.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: VerdiApi,
        name: str,
        lookups: dict[str, Lookup],
        *,
        pace: Pace,
        retry: timedelta,
        guard: Guard,
        rng: random.Random,
        keep_on_failure: bool = False,
    ) -> None:
        # The first run sets the real interval; pace() may need config_entry, which isn't set yet.
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=name,
            update_interval=retry,
            always_update=False,
        )
        self.api, self.lookups, self.guard, self.rng = api, lookups, guard, rng
        self._pace, self._retry, self._keep_on_failure = pace, retry, keep_on_failure
        self._failing: set[str] = set()
        self._tick_at: datetime | None = None
        self._only: str | None = None
        self._run_lock = asyncio.Lock()
        self._rejected_logged = False
        self.on_fetched: FetchHook | None = None
        self.on_run: RunHook | None = None

    def mark_due(self, key: str, reason: str, at: datetime | None = None, *, replace: bool = False) -> bool:
        """Mark a lookup due now or at `at`. False if this coordinator doesn't have it."""
        if (lookup := self.lookups.get(key)) is None:
            return False
        lookup.schedule.mark_due(reason, at, replace=replace)
        return True

    async def async_refresh_lookup(self, key: str) -> None:
        """Fetch one lookup now, for update_entity."""
        if key not in self.lookups:
            return
        self.lookups[key].schedule.mark_due(MANUAL)
        self._only = key
        try:
            await self.async_refresh()
        finally:
            self._only = None

    def schedule_diagnostics(self, now: datetime) -> dict[str, Any]:
        return {key: lookup.schedule.diagnostics(now) for key, lookup in self.lookups.items()}

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

    async def _gap(self) -> None:
        low, high = CALL_GAP
        if high > 0:
            await asyncio.sleep(self.rng.uniform(low, high))

    def _fetched(self, key: str, new: Any, old: Any) -> None:
        if self.on_fetched:
            self.on_fetched(key, new, old)

    async def _async_update_data(self) -> dict[str, Any]:
        # Home Assistant doesn't serialise refreshes; a run reads self.data, so runs go one by one.
        only = self._only
        async with self._run_lock:
            return await self._run(only)

    async def _run(self, only: str | None) -> dict[str, Any]:
        self._refresh_token()
        started, now = time.monotonic(), dt_util.now()
        previous = self.data or {}
        data = {key: previous.get(key) for key in self.lookups}
        tick = only is None and (self._tick_at is None or now >= self._tick_at - timedelta(seconds=1))
        fetched: list[str] = []
        failed: list[str] = []
        rejected = False
        for index, (key, lookup) in enumerate(self.lookups.items()):
            if only not in (None, key):
                continue
            reason = lookup.schedule.reason(now, tick)
            if reason is None:
                continue
            if not self.guard.can_call():
                if tick:  # the rest of this tick's lookups stay due for the next wake
                    for rest in list(self.lookups.values())[index:]:
                        if rest.schedule.always:
                            rest.schedule.mark_due(TICK)
                break
            if fetched or failed:
                await self._gap()
            self.guard.record_call()
            try:
                value = lookup.parse(await lookup.fetch())
            except VerdiAuthError as err:
                lookup.schedule.failed(now, reason, self._retry)
                if self.guard.rejected():
                    raise ConfigEntryAuthFailed(
                        translation_domain=DOMAIN, translation_key="token_rejected"
                    ) from err
                if not self._rejected_logged:
                    _LOGGER.warning(
                        "Verdi rejected the token; trying again for up to %d minutes before "
                        "asking to sign in",
                        REJECTED_WINDOW // 60,
                    )
                    self._rejected_logged = True
                failed.append(key)
                rejected = True
                break  # the token applies to every lookup
            except (VerdiError, KeyError, TypeError, AttributeError) as err:
                if isinstance(err, VerdiUnavailable):
                    self.guard.unavailable(err.retry_after)
                # One failing lookup should not take the other sensors down. The message
                # holds only the path and status or error type, never response content.
                if key not in self._failing:
                    _LOGGER.warning(
                        "Verdi lookup %s failed: %s",
                        key,
                        err if isinstance(err, VerdiError) else type(err).__name__,
                    )
                lookup.schedule.failed(now, reason, self._retry)
                failed.append(key)
            else:
                self.guard.succeeded()
                self._rejected_logged = False
                lookup.schedule.fetched(now, value, reason, self.rng)
                if key in self._failing:
                    _LOGGER.info("Verdi lookup %s works again", key)
                old, data[key] = data[key], value
                fetched.append(key)
                self._fetched(key, value, old)
        self._failing = (self._failing - set(fetched)) | set(failed)
        if self.on_run:
            self.on_run(data, previous)
        if tick and (current := self._pace()):
            self._tick_at = now + timedelta(seconds=jittered(current[0], self.rng, current[1]))
        self.update_interval = self._next_interval(now)
        if failed and not fetched:
            nothing_to_show = not (self._keep_on_failure and any(v is not None for v in data.values()))
            if not previous or (nothing_to_show and not rejected):
                raise UpdateFailed(f"Verdi lookups failed: {', '.join(failed)}")
        _LOGGER.debug(
            "Verdi poll took %.1f s: %s",
            time.monotonic() - started,
            lookup_counts({key: data[key] for key in fetched}),
        )
        return data

    def _next_interval(self, now: datetime) -> timedelta:
        moments = [m for lookup in self.lookups.values() if (m := lookup.schedule.next_due(now))]
        if self._tick_at:
            moments.append(self._tick_at)
        wait = max((min(moments) - now).total_seconds(), MIN_WAKE) if moments else float(IDLE_WAKE)
        if self.guard.backing_off:
            current = self._pace()
            wait = max(wait, self.guard.delay(min(wait, current[0]) if current else wait) or 0.0)
        return timedelta(seconds=wait)


class VerdiCoordinator(LookupCoordinator):
    """The station's lookups. Your own lookups, when enabled, are in .personal."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, token: str) -> None:
        d = entry.data
        names = bool(entry.options.get(CONF_SHOW_NAMES, False))
        rng = schedule.make_rng()
        api = VerdiApi(async_get_clientsession(hass), d[CONF_BASE_URL], token)
        lookups = {
            "readiness": Lookup(
                lambda: api.readiness(d[CONF_STATION_ID], d[CONF_VEHICLE_TRAIN_IDS]), parse.readiness_trains
            ),
            "personnel": Lookup(
                lambda: api.personnel(d[CONF_STATION_ID], d[CONF_AVAILABILITY_IDS]), parse.personnel_summary
            ),
            "vehicles": Lookup(lambda: api.vehicles(d[CONF_STATION_ID]), parse.vehicles),
            "teams": Lookup(lambda: api.team_on_duty(d[CONF_TEAM_GROUP_ID]), parse.teams_on_duty),
            "roster": Lookup(
                lambda: api.roster(d[CONF_CREW_FUNCTION_IDS]), lambda data: parse.roster(data, names=names)
            ),
        }
        super().__init__(
            hass,
            entry,
            api,
            DOMAIN,
            lookups,
            pace=lambda: pace(entry.options, CONF_SCAN_INTERVAL),
            retry=interval(entry.options, CONF_SCAN_INTERVAL),
            guard=get_guard(hass, entry.entry_id, rng),
            rng=rng,
        )
        self.show_names: bool = names
        self.personal: Personal | None = None
