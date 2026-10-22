# SPDX-License-Identifier: GPL-3.0-or-later
"""Guard: call cap, backoff, Retry-After and the window for a rejected token."""

import random

from homeassistant.core import HomeAssistant

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


def test_backoff_doubles_up_to_the_cap_and_resets():
    guard, _ = make()
    assert guard.delay(60) == 60
    for errors, cap in ((1, 120), (2, 240), (3, 300), (6, 300)):
        while guard.level < errors:
            guard.unavailable()
        samples = [guard.delay(60) for _ in range(200)]
        assert min(samples) >= 60 and max(samples) <= cap
        assert guard.backing_off
    guard.succeeded()
    assert guard.delay(60) == 60
    assert not guard.backing_off


def test_backoff_without_a_pace_starts_at_a_minute():
    guard, _ = make()
    assert guard.delay(None) is None
    guard.unavailable()
    assert 60 <= guard.delay(None) <= 120


def test_retry_after_blocks_calls():
    guard, clock = make()
    guard.unavailable(retry_after=90)
    assert not guard.can_call()
    assert guard.delay(30) >= 90
    clock.now += 90
    assert guard.can_call()


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
