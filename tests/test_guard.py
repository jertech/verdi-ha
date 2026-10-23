# SPDX-License-Identifier: GPL-3.0-or-later
"""Guard: call cap, backoff, Retry-After and the window for a rejected token."""

import random

from homeassistant.core import HomeAssistant

from custom_components.verdi.const import BACKOFF_MAX
from custom_components.verdi.guard import Guard, drop_guard, get_guard


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make(seed: int = 1) -> tuple[Guard, Clock]:
    clock = Clock()
    return Guard(random.Random(seed), clock), clock


def test_cap_per_minute():
    guard, clock = make()
    for _ in range(30):
        assert guard.can_call()
        guard.record_call()
    assert not guard.can_call()
    clock.now += 60
    assert guard.can_call()
    assert guard.calls_last_minute() == 0


def blocked_for(guard: Guard, clock: Clock) -> float:
    """Seconds until calls are allowed again, to the second."""
    waited = 0
    while not guard.can_call():
        clock.now += 1
        waited += 1
    clock.now -= waited
    return waited


def test_backoff_blocks_calls_doubling_up_to_the_cap_and_resets():
    guard, clock = make()
    assert guard.delay(60) == 60
    for errors, cap in ((1, 120), (2, 240), (3, BACKOFF_MAX), (6, BACKOFF_MAX)):
        samples = []
        for _ in range(50):
            guard.level = errors - 1
            guard.unavailable(pace=60)
            samples.append(blocked_for(guard, clock))
            clock.now += samples[-1]
        assert min(samples) >= 60 and max(samples) <= cap
        assert guard.level == errors
        assert guard.backing_off
    guard.succeeded()
    assert guard.level == 0
    assert not guard.backing_off
    assert guard.delay(60) == 60


def test_backoff_without_a_pace_starts_at_a_minute():
    guard, clock = make()
    guard.unavailable()
    assert 60 <= blocked_for(guard, clock) <= 120


def test_retry_after_blocks_calls():
    guard, clock = make()
    guard.unavailable(retry_after=600)
    assert blocked_for(guard, clock) == 600
    assert guard.delay(30) == 600
    clock.now += 600
    assert guard.can_call()
    guard.wait(90)
    assert blocked_for(guard, clock) == 90


def test_rejected_window():
    guard, clock = make()
    assert guard.rejected() is False
    clock.now += 119
    assert guard.rejected() is False
    clock.now += 1
    assert guard.rejected() is True
    guard.succeeded()
    assert guard.rejected() is False
    assert guard.diagnostics() == {
        "backoff_level": 0,
        "calls_last_minute": 0,
        "cap_per_minute": 30,
        "rejected_for_seconds": 0,
    }


async def test_one_guard_per_entry(hass: HomeAssistant):
    first = get_guard(hass, "entry-1", random.Random())
    assert get_guard(hass, "entry-1", random.Random()) is first
    assert get_guard(hass, "entry-2", random.Random()) is not first
    drop_guard(hass, "entry-1")
    assert get_guard(hass, "entry-1", random.Random()) is not first


def test_backoff_never_polls_faster_than_the_normal_pace():
    guard, clock = make()
    for pace in (600, 3600):
        guard.unavailable(pace=pace)
        assert blocked_for(guard, clock) == pace  # above the cap: exactly the pace
        clock.now += pace
