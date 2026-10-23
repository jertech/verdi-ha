# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Per entry: a cap on calls per minute, longer waits while Verdi has trouble, and patience
with a rejected token. Shared by the entry's coordinators and kept across reloads."""

from __future__ import annotations

import random
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant

from .const import BACKOFF_MAX, CALL_CAP, DOMAIN, REJECTED_WINDOW

GUARDS = f"{DOMAIN}_guards"


def _monotonic() -> float:
    return time.monotonic()  # looked up on each call, so a frozen test clock applies


class Guard:
    def __init__(self, rng: random.Random, clock: Callable[[], float] = _monotonic) -> None:
        self._rng, self._clock = rng, clock
        self._calls: deque[float] = deque()
        self.level = 0
        self._wait_until = 0.0
        self._rejected_since: float | None = None

    def calls_last_minute(self) -> int:
        now = self._clock()
        while self._calls and now - self._calls[0] >= 60:
            self._calls.popleft()
        return len(self._calls)

    def can_call(self) -> bool:
        return self.calls_last_minute() < CALL_CAP and self._clock() >= self._wait_until

    def record_call(self) -> None:
        self._calls.append(self._clock())

    def succeeded(self) -> None:
        self.level, self._rejected_since = 0, None

    def unavailable(self, retry_after: float | None = None) -> None:
        """Verdi answered 429/5xx or could not be reached."""
        self.level = min(self.level + 1, 10)
        if retry_after:
            self._wait_until = max(self._wait_until, self._clock() + retry_after)

    def rejected(self) -> bool:
        """A 401/403. True once they have lasted REJECTED_WINDOW seconds without a success."""
        now = self._clock()
        if self._rejected_since is None:
            self._rejected_since = now
        return now - self._rejected_since >= REJECTED_WINDOW

    @property
    def backing_off(self) -> bool:
        return self.level > 0 or self._clock() < self._wait_until

    def delay(self, base: float | None) -> float | None:
        """Seconds until the next run: base, stretched while backing off or asked to wait."""
        wait = base
        if self.level:
            start = base or 60.0
            cap = max(start, min(start * 2**self.level, BACKOFF_MAX))
            wait = self._rng.uniform(start, cap)
        if (left := self._wait_until - self._clock()) > 0:
            wait = max(wait or 0.0, left)
        return wait

    def diagnostics(self) -> dict[str, Any]:
        since = self._rejected_since
        return {
            "backoff_level": self.level,
            "calls_last_minute": self.calls_last_minute(),
            "cap_per_minute": CALL_CAP,
            "rejected_for_seconds": round(self._clock() - since) if since is not None else None,
        }


def get_guard(hass: HomeAssistant, entry_id: str, rng: random.Random) -> Guard:
    """The entry's guard. It outlives reloads, so a rejected token's time keeps counting."""
    guards: dict[str, Guard] = hass.data.setdefault(GUARDS, {})
    if entry_id not in guards:
        guards[entry_id] = Guard(rng)
    return guards[entry_id]


def drop_guard(hass: HomeAssistant, entry_id: str) -> None:
    hass.data.get(GUARDS, {}).pop(entry_id, None)
