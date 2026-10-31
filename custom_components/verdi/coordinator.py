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
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import parse, parse_personal, schedule
from .api import VerdiApi, VerdiAuthError, VerdiError, VerdiUnavailable
from .const import (
    BACKOFF_START,
    CALL_GAP,
    CONF_AVAILABILITY_IDS,
    CONF_BASE_URL,
    CONF_CREW_FUNCTION_IDS,
    CONF_FAST_INTERVAL,
    CONF_FAST_LANE,
    CONF_FUNCTION_CALENDAR_ID,
    CONF_INTERVENTION_INTERVAL,
    CONF_PAGED,
    CONF_READINESS_SAFETY,
    CONF_ROSTER_SAFETY,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_NAMES,
    CONF_STATION_ID,
    CONF_TEAM_GROUP_ID,
    CONF_TEAMS_SAFETY,
    CONF_VEHICLE_TRAIN_IDS,
    DOMAIN,
    FAST_LANE_DEFAULT,
    FEATURES,
    IDLE_WAKE,
    INTERVALS,
    MIN_WAKE,
    REJECTED_WINDOW,
)
from .guard import Guard, get_guard
from .schedule import MANUAL, TICK, LookupSchedule, earliest_after, jittered
from .timing import TimingLog
from .token import get_store

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


def request_language(hass: HomeAssistant) -> str:
    """Verdi answers in nl, fr or en; any other Home Assistant language gets en."""
    language = (hass.config.language or "").lower()
    return next((code for code in ("nl", "fr") if language.startswith(code)), "en")


def safety_schedule(options: Mapping[str, Any], key: str, **kwargs: Any) -> LookupSchedule:
    """A schedule with a safety interval option."""
    return LookupSchedule(safety=interval(options, key), safety_minimum=minimum(key), **kwargs)


def readiness_inputs(key: str, value: Any) -> list[tuple[str, ...]] | None:
    """The fields of personnel and vehicles that readiness depends on."""
    if key == "personnel":
        persons = (value or {}).get("persons") or []
        return sorted(
            (str(p["id"]), str(p["availability"]), str(p["present"]), str(p["on_intervention"]))
            for p in persons
        )
    if key == "vehicles":
        return sorted((str(v["id"]), str(v["availability"]), str(v["on_intervention"])) for v in value or [])
    return None


def teams_change(teams: list[dict[str, Any]], now: datetime) -> datetime | None:
    return earliest_after((t.get("next_rotation") for t in teams), now)


def roster_change(roster: list[dict[str, Any]], now: datetime) -> datetime | None:
    return earliest_after(
        (
            moment
            for item in roster
            for moment in ((item["current"] or {}).get("end"), (item["next"] or {}).get("start"))
        ),
        now,
    )


def calendar_change(events: list[dict[str, Any]], now: datetime) -> datetime | None:
    return earliest_after((moment for e in events for moment in (e.get("start"), e.get("end"))), now)


class PersonId:
    """Your person GUID from security/users/authorize, asked once and kept in memory.

    The call goes through the guard. report: tell the guard how it went (a success, or a
    Retry-After to honour); off inside a coordinator run, which reports for the whole lookup.
    """

    def __init__(self, api: VerdiApi, guard: Guard) -> None:
        self._api, self._guard = api, guard
        self.value: str | None = None
        self.on_resolved: Callable[[], None] | None = None

    async def get(self, *, report: bool = True) -> str:
        if self.value is None:
            if not self._guard.can_call():
                raise VerdiError("security/users/authorize: waiting before calling Verdi again")
            self._guard.record_call()
            try:
                user = await self._api.current_user()
            except VerdiUnavailable as err:
                if report:
                    self._guard.wait(err.retry_after)
                raise
            if report:
                self._guard.succeeded()
            guid = user.get("personGuid")
            if not isinstance(guid, str) or not guid:
                raise VerdiError("security/users/authorize: no personGuid")
            self.value = guid
            if self.on_resolved:
                self.on_resolved()
        return self.value


class Availabilities:
    """The station's availabilities, asked on entry load and kept in memory: the plannable list
    behind the web app's availability filter, and the full list, whose extra entries are the
    statuses Verdi sets when someone is called (automatic).

    Personnel is requested with all of them, so your own line and called people are there whatever
    their availability. Configured and automatic ones count; the other plannable ones are listed but
    not counted. Configured ones Verdi doesn't list are still requested and counted. Until both lists
    are loaded, only the configured ones are requested. The calls go through the guard, as PersonId's.
    """

    PAGE = 50
    MAX_PAGES = 10

    def __init__(self, api: VerdiApi, guard: Guard, station_id: str, configured: list[str]) -> None:
        self._api, self._guard, self._station_id = api, guard, station_id
        self.configured = list(configured)
        self.listed: dict[str, str] | None = None
        self.automatic: dict[str, str] | None = None

    async def load(self) -> None:
        listed = await self._read(plannable=True)
        everything = await self._read(plannable=False)
        self.listed = listed
        self.automatic = {i: name for i, name in everything.items() if i not in listed}

    async def _read(self, *, plannable: bool) -> dict[str, str]:
        found: dict[str, str] = {}
        skip = 0
        for _ in range(self.MAX_PAGES):
            if not self._guard.can_call():
                raise VerdiError("availabilities: waiting before calling Verdi again")
            self._guard.record_call()
            try:
                data = await self._api.availabilities(self._station_id, skip, self.PAGE, plannable=plannable)
            except VerdiUnavailable as err:
                self._guard.wait(err.retry_after)
                raise
            self._guard.succeeded()
            found |= parse.availability_list(data)
            items = len(data.get("data") or [])
            skip += items
            total = data.get("total")
            if not items or not isinstance(total, int) or skip >= total:
                break
        return found

    def requested(self) -> list[str]:
        """The IDs to request personnel with: the configured ones, then the rest of the plannable list,
        then the automatic ones."""
        return list(dict.fromkeys([*self.configured, *(self.listed or {}), *(self.automatic or {})]))

    def excluded(self) -> frozenset[str]:
        """Names of plannable availabilities that aren't configured: listed in personnel, not counted.
        Automatic ones always count."""
        listed = self.listed or {}
        counted = {name for i, name in listed.items() if i in self.configured}
        counted |= set((self.automatic or {}).values())
        return frozenset(name for i, name in listed.items() if i not in self.configured) - counted

    def diagnostics(self) -> dict[str, Any]:
        return {
            "loaded": self.listed is not None,
            "listed": len(self.listed) if self.listed is not None else None,
            "automatic": len(self.automatic) if self.automatic is not None else None,
            "configured": len(self.configured),
            "requested": len(self.requested()),
        }


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


@dataclass
class PagedSchedule(LookupSchedule):
    """The paged lookup's schedule: never due while paging is paused (per-lookup pause), whatever
    the tick. `paused` is set once the fast coordinator exists."""

    paused: Callable[[], bool] | None = None

    def reason(self, now: datetime, tick: bool = False) -> str | None:
        if self.paused is not None and self.paused():
            return None
        return super().reason(now, tick)

    def next_due(self, now: datetime) -> datetime | None:
        if self.paused is not None and self.paused():
            return None
        return super().next_due(now)


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
        self._only_keys: list[str] = []
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
        self._only_keys.append(key)
        await self.async_refresh()

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
        # Drain the whole single-lookup queue under the lock so no key can linger into a later run:
        # exactly one queued key narrows this run to it; nothing queued, or two-or-more coalesced
        # into one run, is a FULL run (each queued key was already marked due, so a full run fetches
        # them along with everything else).
        async with self._run_lock:
            keys = self._only_keys
            self._only_keys = []
            only = keys[0] if len(keys) == 1 else None
            return await self._run(only)

    async def _run(self, only: str | None) -> dict[str, Any]:
        self._refresh_token()
        started, now = time.monotonic(), dt_util.now()
        previous = self.data or {}
        data = {key: previous.get(key) for key in self.lookups}
        tick = only is None and (self._tick_at is None or now >= self._tick_at - timedelta(seconds=1))
        fetched: list[str] = []
        failed: list[str] = []
        rejected = blocked = back_off = False
        trouble: VerdiUnavailable | None = None
        for index, (key, lookup) in enumerate(self.lookups.items()):
            if only not in (None, key):
                continue
            reason = lookup.schedule.reason(now, tick)
            if reason is None:
                continue
            if not self.guard.can_call():
                blocked = True
                if tick:
                    self._keep_tick_due(index)
                break
            if fetched or failed:
                await self._gap()
            lookup.schedule.start(now)
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
                if isinstance(err, VerdiUnavailable):
                    trouble, back_off = err, tick and lookup.schedule.always and not fetched
                    if tick:
                        self._keep_tick_due(index + 1)
                    break  # Verdi has trouble: no more calls in this run
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
        if back_off and trouble is not None:
            # A tick that got nothing back: the whole entry waits. Any other failing lookup
            # has its own retry and must not slow the station down.
            current = self._pace()
            self.guard.unavailable(trouble.retry_after, current[0] if current else BACKOFF_START)
        elif trouble is not None:
            self.guard.wait(trouble.retry_after)
        if self.on_run:
            self.on_run(data, previous)
        if tick and (current := self._pace()):
            self._tick_at = now + timedelta(seconds=jittered(current[0], self.rng, current[1]))
        self.update_interval = self._next_interval(now)
        if blocked and not previous:
            # Entities are made from the first data; setup is tried again later.
            raise UpdateFailed("Waiting before calling Verdi again")
        if failed and not fetched:
            # Off-tick and single-lookup runs never take earlier values away; a tick only
            # fails when nothing could be fetched and the coordinator doesn't keep values.
            nothing_to_show = not (
                (self._keep_on_failure or not tick) and any(v is not None for v in data.values())
            )
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
        return timedelta(seconds=self.guard.delay(wait))

    def _keep_tick_due(self, start: int) -> None:
        """The tick's lookups from index start on weren't fetched: they stay due for the next wake."""
        for rest in list(self.lookups.values())[start:]:
            if rest.schedule.always:
                rest.schedule.mark_due(TICK)


class VerdiCoordinator(LookupCoordinator):
    """The station's lookups. Personnel and vehicles every tick; readiness when they change;
    teams and roster at the times Verdi announced; each also after its safety interval.
    Your own lookups, when enabled, are in .personal."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, token: str) -> None:
        d, o = entry.data, entry.options
        names = bool(o.get(CONF_SHOW_NAMES, False))
        rng = schedule.make_rng()
        api = VerdiApi(async_get_clientsession(hass), d[CONF_BASE_URL], token)
        guard = get_guard(hass, entry.entry_id, rng)
        self.person = PersonId(api, guard)
        self.person.on_resolved = self._remark_roster
        self._roster_raw: Any = None
        self.availabilities = Availabilities(api, guard, d[CONF_STATION_ID], d[CONF_AVAILABILITY_IDS])
        self.intervention = False
        lookups = {
            "personnel": Lookup(
                lambda: api.personnel(d[CONF_STATION_ID], self.availabilities.requested()),
                lambda data: parse.personnel_summary(data, exclude=self.availabilities.excluded()),
            ),
            "vehicles": Lookup(lambda: api.vehicles(d[CONF_STATION_ID]), parse.vehicles),
            "readiness": Lookup(
                lambda: api.readiness(d[CONF_STATION_ID], d[CONF_VEHICLE_TRAIN_IDS]),
                parse.readiness_trains,
                safety_schedule(o, CONF_READINESS_SAFETY),
            ),
            "teams": Lookup(
                lambda: api.team_on_duty(d[CONF_TEAM_GROUP_ID]),
                parse.teams_on_duty,
                safety_schedule(o, CONF_TEAMS_SAFETY, next_change=teams_change),
            ),
            "roster": Lookup(
                lambda: api.roster(d[CONF_CREW_FUNCTION_IDS]),
                self._parse_roster,
                safety_schedule(o, CONF_ROSTER_SAFETY, next_change=roster_change),
            ),
        }
        if calendar_id := d.get(CONF_FUNCTION_CALENDAR_ID):

            async def roster_calendar() -> dict[str, Any]:
                now = dt_util.utcnow()
                return await api.calendar_events(
                    calendar_id, now - timedelta(hours=24), now + timedelta(days=7)
                )

            lookups["roster_calendar"] = Lookup(
                roster_calendar,
                lambda data: parse.calendar_events(data, names=names),
                safety_schedule(o, CONF_ROSTER_SAFETY, next_change=calendar_change),
            )
        super().__init__(
            hass,
            entry,
            api,
            DOMAIN,
            lookups,
            pace=self._tick,
            retry=interval(o, CONF_SCAN_INTERVAL),
            guard=guard,
            rng=rng,
        )
        self.show_names: bool = names
        self.personal: LookupCoordinator | None = None
        self.fast: LookupCoordinator | None = None
        self.timing: TimingLog | None = None
        self.timing_store: Store[dict[str, Any]] | None = None

    def _parse_roster(self, data: Any) -> list[dict[str, Any]]:
        self._roster_raw = data
        return parse.roster(data, names=self.show_names, me=self.person.value)

    @callback
    def _remark_roster(self) -> None:
        """The person ID arrived after the roster was parsed: redo the `mine` flags from the cached
        response. Data only: no _fetched, so it doesn't mark events due."""
        if self._roster_raw is None or not (self.data or {}).get("roster"):
            return
        roster = parse.roster(self._roster_raw, names=self.show_names, me=self.person.value)
        if roster != self.data["roster"]:
            self.async_set_updated_data({**self.data, "roster": roster})

    def _tick(self) -> tuple[float, float]:
        key = CONF_INTERVENTION_INTERVAL if self.intervention else CONF_SCAN_INTERVAL
        return pace(self.config_entry.options, key)

    @property
    def pace_name(self) -> str:
        if self.guard.backing_off:
            return "backoff"
        return "intervention" if self.intervention else "normal"

    def _fetched(self, key: str, new: Any, old: Any) -> None:
        if old is not None and readiness_inputs(key, new) != readiness_inputs(key, old):
            self.mark_due("readiness", f"trigger:{key}")
        super()._fetched(key, new, old)


# Station lookups that may poll on the fast lane instead. "paged" is the paging lookup, added by
# create_fast rather than moved off the station (it has no station equivalent).
FAST_MOVABLE = ("vehicles", "personnel")


class FastCoordinator(LookupCoordinator):
    """The fast lane: the paged lookup and any of vehicles/personnel moved here by the fast_lane
    option, polled at fast_interval. It shares the station's api, guard and rng.

    A personnel/vehicle change here marks the station's readiness lookup due, exactly as it would
    on the station coordinator, so readiness keeps following those lookups wherever they live.

    paused suppresses only the paged lookup. The coordinator still ticks while vehicles or personnel
    are on it; it goes idle (pace None) only when paging is off or paused and neither is on it.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        station: VerdiCoordinator,
        lookups: dict[str, Lookup],
    ) -> None:
        self.station = station
        self.paused = False
        self.page_keys: list[str] = []
        super().__init__(
            hass,
            entry,
            station.api,
            f"{DOMAIN} fast",
            lookups,
            pace=self._fast_tick,
            retry=interval(entry.options, CONF_FAST_INTERVAL),
            guard=station.guard,
            rng=station.rng,
        )

    def _active(self) -> bool:
        """The fast lane ticks while paging is on and not paused, or vehicles/personnel are on it."""
        paging = "paged" in self.lookups and not self.paused
        has_units = any(key in self.lookups for key in FAST_MOVABLE)
        return paging or has_units

    def _fast_tick(self) -> tuple[float, float] | None:
        if not self._active():
            return None
        return pace(self.config_entry.options, CONF_FAST_INTERVAL)

    def _fetched(self, key: str, new: Any, old: Any) -> None:
        if old is not None and readiness_inputs(key, new) != readiness_inputs(key, old):
            self.station.mark_due("readiness", f"trigger:{key}")
        super()._fetched(key, new, old)


def create_fast(hass: HomeAssistant, entry: ConfigEntry, station: VerdiCoordinator) -> FastCoordinator | None:
    """Move the chosen station lookups onto a fast-lane coordinator, or None when it holds nothing.

    The keys named in CONF_FAST_LANE that exist as station lookups today (vehicles/personnel) are
    removed from the station and placed on the fast lane. "paged" adds the paging lookup when the
    paged switch is on; it polls your current intervention while pageable (signals.py pauses it).
    """
    o = entry.options
    chosen = o.get(CONF_FAST_LANE, FAST_LANE_DEFAULT)
    lookups: dict[str, Lookup] = {}
    for key in FAST_MOVABLE:
        if key in chosen and key in station.lookups:
            lookups[key] = station.lookups.pop(key)
    paged_schedule: PagedSchedule | None = None
    if "paged" in chosen and enabled(o, CONF_PAGED):
        language = request_language(hass)

        async def paged() -> dict[str, Any]:
            return await station.api.current_intervention(await station.person.get(report=False), language)

        paged_schedule = PagedSchedule(always=True)

        def parse_paged(data: dict[str, Any]) -> dict[str, Any] | None:
            fast.page_keys = parse_personal.page_keys(data)  # names only, for the timing log
            return parse_personal.current_intervention(data)

        lookups["paged"] = Lookup(paged, parse_paged, paged_schedule)
    if not lookups:
        return None
    fast = FastCoordinator(hass, entry, station, lookups)
    if paged_schedule is not None:
        paged_schedule.paused = lambda: fast.paused
    return fast
