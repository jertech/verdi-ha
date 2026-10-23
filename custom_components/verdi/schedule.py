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

type NextChange = Callable[[Any, datetime], datetime | None]


def make_rng() -> random.Random:
    """One random source per entry. Tests replace this to make timing predictable."""
    return random.Random()  # noqa: S311 - jitter spreads load, it is not a secret


def jittered(seconds: float, rng: random.Random, minimum: float = 0.0) -> float:
    """seconds, varied by ±10 %, never below minimum."""
    return max(seconds * rng.uniform(1 - JITTER, 1 + JITTER), minimum)


def earliest_after(values: Iterable[Any], now: datetime) -> datetime | None:
    """The first moment after now among ISO texts or datetimes with an offset; others are ignored."""
    moments = []
    for value in values:
        moment = value
        if isinstance(moment, str):
            try:
                moment = datetime.fromisoformat(moment)
            except ValueError:
                continue
        if isinstance(moment, datetime) and moment.tzinfo and moment > now:
            moments.append(moment)
    return min(moments, default=None)


@dataclass
class LookupSchedule:
    """When one lookup is due.

    always: fetched on every tick of its coordinator. safety: longest time between fetches,
    varied per run but never below safety_minimum seconds. next_change: reads from the lookup's
    value when it changes next; the lookup is due known_delay seconds (random) after that.
    """

    always: bool = False
    safety: timedelta | None = None
    safety_minimum: float = 0.0
    next_change: NextChange | None = None
    known_delay: tuple[float, float] = BOUNDARY_DELAY
    last_fetch: datetime | None = None
    last_reason: str | None = None
    calls_today: int = 0
    _now_reason: str | None = STARTUP
    _later: datetime | None = None
    _later_reason: str | None = None
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

    def reason(self, now: datetime, tick: bool = False) -> str | None:
        """Why the lookup is due now, or None."""
        if self._now_reason:
            return self._now_reason
        if self.always and tick:
            return TICK
        if self._later and self._later <= now:
            return self._later_reason
        if self._known_at and self._known_at <= now:
            return TIME
        if self._safety_at and self._safety_at <= now:
            return SAFETY
        return None

    def next_due(self, now: datetime) -> datetime | None:
        """When the lookup is due next, apart from ticks; now if it already is."""
        if self._now_reason:
            return now
        return min((t for t in (self._later, self._known_at, self._safety_at) if t), default=None)

    def start(self, now: datetime) -> None:
        """A fetch starts. Times that have come are used up, so a failure doesn't leave the
        lookup due at once; a mark made while it is fetched still counts."""
        self._now_reason = None
        if self._later and self._later <= now:
            self._later = self._later_reason = None
        if self._known_at and self._known_at <= now:
            self._known_at = None
        if self._safety_at and self._safety_at <= now:
            self._safety_at = None

    def _count(self, now: datetime, reason: str) -> None:
        if self._day != now.date():
            self._day, self.calls_today = now.date(), 0
        self.calls_today += 1
        self.last_fetch, self.last_reason = now, reason

    def fetched(self, now: datetime, value: Any, reason: str, rng: random.Random) -> None:
        self._count(now, reason)
        if self._later_reason == RETRY:
            self._later = self._later_reason = None
        if self.safety:
            seconds = jittered(self.safety.total_seconds(), rng, self.safety_minimum)
            self._safety_at = now + timedelta(seconds=seconds)
        change = self.next_change(value, now) if self.next_change and value is not None else None
        self._known_at = change + timedelta(seconds=rng.uniform(*self.known_delay)) if change else None

    def failed(self, now: datetime, reason: str, retry: timedelta) -> None:
        self._count(now, reason)
        if not self.always:  # the next tick fetches it anyway
            self.mark_due(RETRY, now + retry, replace=True)

    def diagnostics(self, now: datetime) -> dict[str, Any]:
        due = self.next_due(now)
        return {
            "calls_today": self.calls_today if self._day == now.date() else 0,
            "last_fetch": self.last_fetch.isoformat() if self.last_fetch else None,
            "last_reason": self.last_reason,
            "next_due": due.isoformat() if due else None,
        }
