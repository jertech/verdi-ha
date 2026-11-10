# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""When a lookup is due: a safety interval, the next change its data announces, and triggers.

No Home Assistant imports. Times are aware datetimes; all randomness comes from the
random.Random passed in, so tests can make it predictable.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from .const import BOUNDARY_DELAY, JITTER

# Why a lookup ran, as shown in diagnostics. Triggers use "trigger:<name>".
STARTUP, TICK, TIME, SAFETY, RETRY, MANUAL = "startup", "tick", "time", "safety", "retry", "manual"
AHEAD = "ahead"  # fetched shortly before a known moment, so the data is fresh then

type NextChange = Callable[[Any, datetime], datetime | None]


def make_rng() -> random.Random:
    """One random source per entry. Tests replace this to make timing predictable."""
    return random.Random()  # noqa: S311 - jitter spreads load, it is not a secret


def jittered(seconds: float, rng: random.Random, minimum: float = 0.0) -> float:
    """seconds, varied by ±10 %, never below minimum."""
    return max(seconds * rng.uniform(1 - JITTER, 1 + JITTER), minimum)


def parse_iso(value: Any) -> datetime | None:
    """An ISO date-time text as a datetime (offset or not); anything else is None."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def earliest_after(values: Iterable[Any], now: datetime) -> datetime | None:
    """The first moment after now among ISO texts or datetimes with an offset; others are ignored."""
    moments = []
    for value in values:
        moment = value
        if isinstance(moment, str):
            moment = parse_iso(moment)
        if isinstance(moment, datetime) and moment.tzinfo and moment > now:
            moments.append(moment)
    return min(moments, default=None)


@dataclass
class LookupSchedule:
    """When one lookup is due.

    always: fetched on every tick of its coordinator. safety: longest time between fetches,
    varied per run but never below safety_minimum seconds. next_change: reads from the lookup's
    value when it changes next; the lookup is due known_delay seconds (random) after that.
    ahead_at: one fetch planned before a known moment (see set_ahead).
    """

    always: bool = False
    safety: timedelta | None = None
    safety_minimum: float = 0.0
    live_safety: timedelta | None = None
    next_change: NextChange | None = None
    known_delay: tuple[float, float] = BOUNDARY_DELAY
    last_fetch: datetime | None = None
    last_reason: str | None = None
    calls_today: int = 0
    _now_reason: str | None = STARTUP
    _later: datetime | None = None
    _later_reason: str | None = None
    _held: datetime | None = None  # a later mark a retry moved aside, still due at its time
    _held_reason: str | None = None
    ahead_at: datetime | None = None  # see set_ahead
    _known_at: datetime | None = None
    _safety_at: datetime | None = None
    _day: date | None = field(default=None, repr=False)

    def start_at(self, at: datetime) -> None:
        """Fetch the first time at `at` instead of right away."""
        self._now_reason, self._later, self._later_reason = None, at, STARTUP

    def mark_due(self, reason: str, at: datetime | None = None, *, replace: bool = False) -> None:
        """Due now, or at `at`. An earlier mark wins unless replace is set."""
        if at is None:
            self._now_reason = reason
        elif replace or self._later is None or at < self._later:
            self._later, self._later_reason = at, reason

    def set_ahead(self, at: datetime | None) -> None:
        """Due at `at`, in a slot of its own: it replaces the previous one, and other marks and fetches
        before it leave it alone. None clears it."""
        self.ahead_at = at

    def reason(self, now: datetime, tick: bool = False) -> str | None:
        """Why the lookup is due now, or None."""
        if self._now_reason:
            return self._now_reason
        if self.always and tick:
            return TICK
        if self._later and self._later <= now:
            return self._later_reason
        if self._held and self._held <= now:
            return self._held_reason
        if self.ahead_at and self.ahead_at <= now:
            return AHEAD
        if self._known_at and self._known_at <= now:
            return TIME
        if self._safety_at and self._safety_at <= now:
            return SAFETY
        return None

    def next_due(self, now: datetime) -> datetime | None:
        """When the lookup is due next, apart from ticks; now if it already is."""
        if self._now_reason:
            return now
        return min(
            (t for t in (self._later, self._held, self.ahead_at, self._known_at, self._safety_at) if t),
            default=None,
        )

    def start(self, now: datetime) -> None:
        """A fetch starts. Times that have come are used up, so a failure doesn't leave the
        lookup due at once; a mark made while it is fetched still counts."""
        self._now_reason = None
        if self._later and self._later <= now:
            self._later = self._later_reason = None
        if self._held and self._held <= now:
            self._held = self._held_reason = None
        if self.ahead_at and self.ahead_at <= now:
            self.ahead_at = None
        if self._known_at and self._known_at <= now:
            self._known_at = None
        if self._safety_at and self._safety_at <= now:
            self._safety_at = None

    def _count(self, now: datetime, reason: str) -> None:
        if self._day != now.date():
            self._day, self.calls_today = now.date(), 0
        self.calls_today += 1
        self.last_fetch, self.last_reason = now, reason

    def fetched(self, now: datetime, value: Any, reason: str, rng: random.Random, live: bool = False) -> None:
        self._count(now, reason)
        if self._later_reason == RETRY:
            self._later = self._later_reason = None
        if self.safety:
            safety = max(self.safety, self.live_safety) if live and self.live_safety else self.safety
            seconds = jittered(safety.total_seconds(), rng, self.safety_minimum)
            self._safety_at = now + timedelta(seconds=seconds)
        change = self.next_change(value, now) if self.next_change and value is not None else None
        self._known_at = change + timedelta(seconds=rng.uniform(*self.known_delay)) if change else None

    def live_dropped(self, now: datetime, rng: random.Random) -> None:
        """Live updates dropped: a safety planned for the connection is at most one normal safety away.
        A lookup without a live safety was not planned for the connection and stays as it is."""
        if not self.safety or self._safety_at is None or self.live_safety is None:
            return
        at = now + timedelta(seconds=jittered(self.safety.total_seconds(), rng, self.safety_minimum))
        self._safety_at = min(self._safety_at, at)

    def failed(self, now: datetime, reason: str, retry: timedelta) -> None:
        self._count(now, reason)
        if not self.always:  # the next tick fetches it anyway
            at = now + retry
            later = self._later
            if (
                later
                and later > at
                and self._later_reason != RETRY
                and (self._held is None or later < self._held)
            ):
                self._held, self._held_reason = later, self._later_reason
            self.mark_due(RETRY, at, replace=True)

    def diagnostics(self, now: datetime) -> dict[str, Any]:
        """Times in now's zone: a moment Verdi sent in UTC reads like the rest."""
        due = self.next_due(now)

        def shown(moment: datetime | None) -> str | None:
            return moment.astimezone(now.tzinfo).isoformat() if moment else None

        return {
            "calls_today": self.calls_today if self._day == now.date() else 0,
            "last_fetch": shown(self.last_fetch),
            "last_reason": self.last_reason,
            "next_due": shown(due),
        }
