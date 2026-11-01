# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Changing your own status: one path for every write (actions, buttons, the availability calendar).

Each write: option on → your rights → one write at a time per person → the guard → send, never retried →
refresh your own lookups. Verdi's refusal texts go to the caller only (the raised error), never to a log
written here, diagnostics or storage: they may name you.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from . import parse_personal, write_data
from .api import VerdiAuthError, VerdiError, VerdiRefused, VerdiUnavailable, is_guid
from .const import CONF_CALENDAR_EDIT, CONF_STATION_ID, CONF_STATUS_CHANGES, DOMAIN, WRITE_LOCKS
from .coordinator import enabled, request_language

PAST_SLACK = timedelta(minutes=1)
_REFRESH = object()  # _availability: refresh now, rather than check a refresh that already ran


def fail(key: str, **placeholders: str) -> HomeAssistantError:
    """Verdi's side or a check of ours that isn't the user's input."""
    return HomeAssistantError(
        translation_domain=DOMAIN, translation_key=key, translation_placeholders=placeholders or None
    )


def invalid(key: str, **placeholders: str) -> ServiceValidationError:
    """Something the caller can fix."""
    return ServiceValidationError(
        translation_domain=DOMAIN, translation_key=key, translation_placeholders=placeholders or None
    )


async def require_admin(hass: HomeAssistant, context: Context | None) -> None:
    """A user who isn't an admin may not change the status; calls without a user (automations) may."""
    user_id = context.user_id if context else None
    if user_id is None:
        return
    user = await hass.auth.async_get_user(user_id)
    if user is None or not user.is_admin:
        raise fail("not_admin")


class StatusWriter:
    """Your own status and planning, for one entry. station is the entry's VerdiCoordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, station: Any) -> None:
        self._hass, self._station = hass, station
        self._api = station.api
        self._station_id: str = entry.data[CONF_STATION_ID]
        self._language = request_language(hass)
        self.status_changes = enabled(entry.options, CONF_STATUS_CHANGES)
        self.calendar_edit = enabled(entry.options, CONF_CALENDAR_EDIT)
        # The selects' current choice, read by the "Set status" button.
        self.choice: dict[str, str | None] = {"status": None, "duration": write_data.DEFAULT_DURATION}
        self._kind: dict[str, Any] | None = None
        self._calendars: list[dict[str, Any]] | None = None
        self._stats: dict[str, dict[str, Any]] = {}

    # What the entities show.

    def status_names(self) -> list[str] | None:
        listed = self._station.availabilities.listed
        return list(dict.fromkeys(listed.values())) if listed is not None else None

    def rights_missing(self, right: str) -> bool:
        """True only when the rights are known and this one is missing; unknown rights are checked on use."""
        rights = self._station.person.rights
        return rights is not None and not rights.get(right)

    # The four writes.

    async def add_exception(self, status: str | None, duration: str | None) -> dict[str, bool | None]:
        """Your status now, for a duration (a key of write_data.DURATIONS) or unlimited. active: whether
        your availability shows it now; None when that couldn't be read (the change itself went through)."""
        self._check_on(False)
        availability_id, name = self._status(status)
        key = duration or write_data.DEFAULT_DURATION
        if key not in write_data.DURATIONS:
            raise invalid("unknown_duration")

        held: list[Any] = []

        async def send(person: str) -> None:
            await self._call(
                lambda: self._api.add_exception(
                    person, availability_id, write_data.DURATIONS[key], self._station_id, self._language
                )
            )
            held.append(self._held())

        await self._write("add_exception", "status", False, send)
        # _write just refreshed your availability: read what that refresh got, without a second call.
        try:
            mine = await self._availability(refreshed_from=held[0])
        except HomeAssistantError:
            mine = None
        if mine is None:
            return {"active": None}
        return {"active": write_data.is_active(mine, self._station_id, name)}

    async def return_to_planning(self, *, from_calendar: bool = False) -> None:
        """Back to planning for every block Verdi flags; a group block under a sent station is skipped."""
        self._check_on(from_calendar)

        async def send(person: str) -> None:
            # An availability that couldn't be read now, or one held from before, raises: it isn't "nothing
            # to end", and its targets may already have ended.
            mine = await self._availability()
            if mine is None:
                raise fail("outcome_unknown")
            targets = write_data.return_targets(mine.get("blocks") or [])
            if not targets:
                raise fail("nothing_to_end")
            # done: how many commands Verdi already took before this one.
            for done, (station_id, group_id) in enumerate(targets):
                try:
                    await self._call(
                        lambda s=station_id, g=group_id: self._api.return_to_planning(
                            person, s, g, self._language
                        )
                    )
                except HomeAssistantError as err:
                    if done:
                        feedback = (err.translation_placeholders or {}).get("feedback", "-")
                        raise fail("partly_ended", feedback=feedback) from None
                    raise

        await self._write("return_to_planning", "status", from_calendar, send)

    async def add_event(
        self,
        status: str | None,
        start: datetime,
        end: datetime,
        calendar: str | None = None,
        *,
        from_calendar: bool = False,
    ) -> dict[str, str | None]:
        """A planned status for a time slot, in the given calendar or the general one."""
        self._check_on(from_calendar)
        availability_id, _name = self._status(status)
        start, end = _aware(start), _aware(end)
        if end <= start:
            raise invalid("end_before_start")
        if start < dt_util.utcnow() - PAST_SLACK:
            raise invalid("event_in_past")

        async def send(person: str) -> dict[str, str | None]:
            kind = await self._single_kind()
            cals = await self._person_calendars(person)
            chosen = (
                write_data.find_calendar(cals, calendar) if calendar else write_data.default_calendar(cals)
            )
            if chosen is None:
                raise invalid(
                    "unknown_calendar",
                    calendar=calendar or "-",
                    choices=", ".join(write_data.calendar_label(c) for c in cals) or "-",
                )
            body = write_data.event_body(
                person=person, availability=availability_id, kind=kind, calendar=chosen, start=start, end=end
            )
            answer = await self._call(lambda: self._api.add_event(body, self._language))
            event_id = answer.get("guid")
            return {"event_id": event_id if isinstance(event_id, str) else None}

        return await self._write("add_event", "calendar", from_calendar, send)

    async def delete_event(self, event_id: str, *, from_calendar: bool = False) -> None:
        """Remove one of your own planned statuses; any other ID is refused before calling Verdi."""
        self._check_on(from_calendar)
        personal = self._station.personal
        if personal is None or "events" not in personal.lookups:
            raise invalid("needs_events")
        if not is_guid(event_id):
            raise invalid("not_own_event")
        item = self._availability_item(event_id)
        if item is None:
            await personal.async_refresh_lookup("events")
            item = self._availability_item(event_id)
        if item is None or item.get("kind") != "single":
            raise invalid("not_own_event")

        async def send(person: str) -> None:
            await self._call(lambda: self._api.delete_event(event_id, self._language))

        await self._write("delete_event", "calendar", from_calendar, send)

    # From the availability calendar.

    async def calendar_create(self, **kwargs: Any) -> None:
        self._check_on(True)
        if kwargs.get("rrule"):
            raise invalid("repeat_not_supported")
        start, end = _from_calendar(kwargs["dtstart"]), _from_calendar(kwargs["dtend"])
        await self.add_event(kwargs.get("summary"), start, end, from_calendar=True)

    async def calendar_delete(self, uid: str) -> None:
        self._check_on(True)
        item = self._availability_item(uid)
        if item is None:
            raise invalid("unknown_event")
        if item.get("kind") == "single":
            await self.delete_event(uid, from_calendar=True)
            return
        now = dt_util.utcnow()
        if item.get("kind") == "exception" and item["start"] <= now < item["end"]:
            await self.return_to_planning(from_calendar=True)
            return
        if item.get("kind") == "exception" and item["end"] <= now:
            raise invalid("exception_over")
        raise invalid("unknown_event")

    # Diagnostics: switches, rights, what is loaded, and per write kind how it went. No bodies, texts or IDs.

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status_changes": self.status_changes,
            "calendar_edit": self.calendar_edit,
            "rights": dict(self._station.person.rights) if self._station.person.rights is not None else None,
            "event_kind_loaded": self._kind is not None,
            "calendars": len(self._calendars) if self._calendars is not None else None,
            "writes": {k: _shown(s) for k, s in self._stats.items()},
        }

    # The shared path.

    def _check_on(self, from_calendar: bool) -> None:
        if not self.status_changes:
            raise invalid("status_changes_off")
        if from_calendar and not self.calendar_edit:
            raise invalid("calendar_edit_off")

    def _status(self, status: str | None) -> tuple[str, str]:
        listed = self._station.availabilities.listed
        if listed is None:
            raise invalid("lists_not_loaded")
        found = write_data.find_status(listed, status)
        if found is None:
            raise invalid(
                "unknown_status", status=str(status or ""), choices=", ".join(self.status_names() or [])
            )
        return found

    async def _write(
        self, kind: str, right: str, from_calendar: bool, send: Callable[[str], Awaitable[Any]]
    ) -> Any:
        self._check_on(from_calendar)
        try:
            person = await self._person()
            if not (self._station.person.rights or {}).get(right):
                raise fail("no_right")
            lock = self._lock(person)
            if lock.locked():
                raise fail("busy")
            async with lock:
                result = await send(person)
        except HomeAssistantError as err:
            self._record(kind, err.translation_key or "error")
            raise
        self._record(kind, "ok")
        await self._refresh()
        return result

    async def _person(self) -> str:
        try:
            return await self._station.person.get()
        except VerdiAuthError:
            raise fail("token_refused") from None
        except VerdiError:
            raise fail("not_ready") from None

    def _lock(self, person: str) -> asyncio.Lock:
        locks: dict[str, asyncio.Lock] = self._hass.data.setdefault(WRITE_LOCKS, {})
        return locks.setdefault(person.lower(), asyncio.Lock())

    async def _call(self, call: Callable[[], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
        """One Verdi call through the guard. Never retried; the station's backoff and 401 window stay as
        they are."""
        guard = self._station.guard
        if not guard.can_call():
            raise fail("verdi_busy")
        guard.record_call()
        try:
            return await call()
        except VerdiRefused as err:
            raise fail("verdi_refused", feedback=err.feedback or "-") from None
        except VerdiUnavailable as err:
            if err.status == 429:
                guard.wait(err.retry_after)
                raise fail("verdi_busy") from None
            raise fail("outcome_unknown") from None
        except VerdiAuthError:
            raise fail("token_refused") from None
        except VerdiError:
            raise fail("outcome_unknown") from None

    async def _single_kind(self) -> dict[str, Any]:
        if self._kind is None:
            self._kind = write_data.single_kind(
                await self._call(lambda: self._api.event_priorities(self._language))
            )
            if self._kind is None:
                raise fail("outcome_unknown")
        return self._kind

    async def _person_calendars(self, person: str) -> list[dict[str, Any]]:
        if self._calendars is None:
            data = await self._call(lambda: self._api.person_calendars(person, self._language))
            self._calendars = write_data.calendars(data)
        return self._calendars

    async def _availability(self, *, refreshed_from: Any = _REFRESH) -> dict[str, Any] | None:
        """Your availability now, a failure raising the mapped error. Through the personal coordinator:
        refreshed here, or refreshed_from is what it held before a refresh that already ran. Without it,
        read once. None: Verdi's answer had none."""
        personal = self._station.personal
        if personal is None or "availability" not in personal.lookups:
            return parse_personal.my_availability(await self._call(self._api.my_availability))
        before = refreshed_from
        if before is _REFRESH:
            before = self._held()
            await personal.async_refresh_lookup("availability")
        mine = self._held()
        # The refresh never raises. A fetch stores a newly parsed object; the same one means the run
        # failed or the guard held it back, and what is held predates this write.
        if mine is before:
            raise fail("outcome_unknown" if self._station.guard.can_call() else "verdi_busy")
        return mine

    def _held(self) -> Any:
        """The availability the personal coordinator holds right now (the object itself), if any."""
        personal = self._station.personal
        return ((personal.data or {}) if personal is not None else {}).get("availability")

    def _availability_item(self, item_id: str) -> dict[str, Any] | None:
        personal = self._station.personal
        events = ((personal.data or {}).get("events") or {}) if personal is not None else {}
        want = item_id.lower()
        return next(
            (i for i in events.get("availability") or [] if (i.get("id") or "").lower() == want), None
        )

    async def _refresh(self) -> None:
        personal = self._station.personal
        if personal is None:
            return
        for key in ("availability", "events"):
            if key in personal.lookups:
                await personal.async_refresh_lookup(key)

    def _record(self, kind: str, outcome: str) -> None:
        today = dt_util.now().date().isoformat()
        stats = self._stats.get(kind)
        if stats is None or stats["day"] != today:
            stats = self._stats[kind] = {"day": today, "today": 0}
        stats["today"] += 1
        stats["last"] = dt_util.now().isoformat(timespec="seconds")
        stats["outcome"] = outcome


def _shown(stats: dict[str, Any]) -> dict[str, Any]:
    """One write kind's counters for diagnostics; a count from an earlier day is today's zero."""
    shown = {n: v for n, v in stats.items() if n != "day"}
    if stats["day"] != dt_util.now().date().isoformat():
        shown["today"] = 0
    return shown


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=dt_util.get_default_time_zone())


def _from_calendar(value: date | datetime) -> datetime:
    """A calendar view's start or end; an all-day date is Belgian midnight."""
    if isinstance(value, datetime):
        return _aware(value)
    return datetime.combine(value, time(0), tzinfo=dt_util.get_time_zone(write_data.BRUSSELS))
