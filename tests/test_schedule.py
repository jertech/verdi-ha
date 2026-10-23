# SPDX-License-Identifier: GPL-3.0-or-later
"""LookupSchedule: when a lookup is due, and the randomness that spreads the load."""

import random
from datetime import UTC, datetime, timedelta

from custom_components.verdi.schedule import (
    RETRY,
    SAFETY,
    STARTUP,
    TICK,
    TIME,
    LookupSchedule,
    earliest_after,
    jittered,
)
from tests.conftest import MidRandom

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
RNG = MidRandom()


def fetched(s: LookupSchedule, now: datetime, value, reason: str, rng: random.Random = RNG) -> None:
    s.start(now)
    s.fetched(now, value, reason, rng)


def test_new_schedule_is_due_at_startup():
    s = LookupSchedule(safety=timedelta(minutes=15))
    assert s.reason(NOW) == STARTUP
    assert s.next_due(NOW) == NOW


def test_safety_interval_after_a_fetch():
    s = LookupSchedule(safety=timedelta(minutes=15))
    fetched(s, NOW, {"x": 1}, STARTUP)
    assert s.reason(NOW + timedelta(minutes=14)) is None
    assert s.next_due(NOW) == NOW + timedelta(minutes=15)
    assert s.reason(NOW + timedelta(minutes=15)) == SAFETY


def test_always_is_due_on_ticks_only():
    s = LookupSchedule(always=True)
    fetched(s, NOW, [], STARTUP)
    assert s.reason(NOW + timedelta(hours=5)) is None
    assert s.reason(NOW, tick=True) == TICK
    assert s.next_due(NOW) is None


def test_known_change_time():
    s = LookupSchedule(next_change=lambda value, now: earliest_after([value["next"]], now))
    fetched(s, NOW, {"next": "2026-06-15T13:00:00+00:00"}, STARTUP)
    at = NOW + timedelta(hours=1, seconds=75)  # middle of 30-120 s
    assert s.next_due(NOW) == at
    assert s.reason(at - timedelta(seconds=1)) is None
    assert s.reason(at) == TIME


def test_known_change_in_the_past_is_ignored():
    s = LookupSchedule(next_change=lambda value, now: earliest_after([value], now))
    fetched(s, NOW, "2026-06-15T11:00:00+00:00", STARTUP)
    assert s.next_due(NOW) is None


def test_earliest_after_ignores_past_naive_and_garbage():
    values = [
        "2026-06-15T11:00:00+00:00",
        "2026-06-15T14:00:00",
        "nonsense",
        None,
        datetime(2026, 6, 15, 16, 0, tzinfo=UTC),
        "2026-06-15T13:00:00+02:00",
    ]
    assert earliest_after(values, NOW) == datetime(2026, 6, 15, 16, 0, tzinfo=UTC)
    assert earliest_after([], NOW) is None


def test_marks_earlier_wins_unless_replaced():
    s = LookupSchedule()
    fetched(s, NOW, 1, STARTUP)
    s.mark_due("trigger:a", NOW + timedelta(minutes=5))
    s.mark_due("trigger:b", NOW + timedelta(minutes=9))
    assert s.next_due(NOW) == NOW + timedelta(minutes=5)
    s.mark_due("trigger:c", NOW + timedelta(minutes=9), replace=True)
    assert s.next_due(NOW) == NOW + timedelta(minutes=9)
    assert s.reason(NOW + timedelta(minutes=9)) == "trigger:c"
    s.mark_due("trigger:now")
    assert s.reason(NOW) == "trigger:now"


def test_failed_is_due_again_after_retry():
    s = LookupSchedule(safety=timedelta(hours=6))
    s.start(NOW)
    s.failed(NOW, STARTUP, timedelta(minutes=5))
    assert s.reason(NOW) is None
    assert s.reason(NOW + timedelta(minutes=5)) == RETRY
    assert s.calls_today == 1


def test_start_at_delays_the_first_fetch():
    s = LookupSchedule()
    s.start_at(NOW + timedelta(minutes=5))
    assert s.reason(NOW) is None
    assert s.reason(NOW + timedelta(minutes=5)) == STARTUP


def test_calls_today_restart_on_a_new_day_and_diagnostics():
    s = LookupSchedule(safety=timedelta(minutes=15))
    fetched(s, NOW, 1, STARTUP)
    fetched(s, NOW + timedelta(minutes=15), 1, SAFETY)
    assert s.calls_today == 2
    tomorrow = NOW + timedelta(days=1)
    assert s.diagnostics(tomorrow)["calls_today"] == 0
    fetched(s, tomorrow, 1, SAFETY)
    assert s.diagnostics(tomorrow) == {
        "calls_today": 1,
        "last_fetch": tomorrow.isoformat(),
        "last_reason": SAFETY,
        "next_due": (tomorrow + timedelta(minutes=15)).isoformat(),
    }


def test_jitter_bounds_and_minimum():
    rng = random.Random(1)
    samples = [jittered(60, rng) for _ in range(1000)]
    assert min(samples) >= 54 and max(samples) <= 66
    assert min(jittered(10, rng, 10) for _ in range(1000)) >= 10


def test_safety_jitter_never_below_its_minimum():
    s = LookupSchedule(safety=timedelta(minutes=5), safety_minimum=300)
    rng = random.Random(2)
    for _ in range(200):
        fetched(s, NOW, 1, SAFETY, rng)
        assert s.next_due(NOW) >= NOW + timedelta(minutes=5)


def test_a_mark_during_the_fetch_stays():
    s = LookupSchedule(safety=timedelta(hours=1))
    s.start(NOW)
    s.mark_due("trigger:own_availability")
    s.fetched(NOW, 1, STARTUP, RNG)
    assert s.reason(NOW) == "trigger:own_availability"
    s.start(NOW)
    s.mark_due("trigger:own_availability")
    s.failed(NOW, "trigger:own_availability", timedelta(minutes=5))
    assert s.reason(NOW) == "trigger:own_availability"


def test_a_failed_tick_lookup_waits_for_the_next_tick():
    s = LookupSchedule(always=True)
    s.start(NOW)
    s.failed(NOW, STARTUP, timedelta(minutes=1))
    assert s.next_due(NOW) is None
    assert s.reason(NOW + timedelta(minutes=1)) is None
    assert s.reason(NOW + timedelta(minutes=1), tick=True) == TICK
