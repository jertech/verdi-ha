# SPDX-License-Identifier: GPL-3.0-or-later
"""The steady calls-per-minute estimate."""

from custom_components.verdi import estimate
from custom_components.verdi.const import (
    CONF_FAST_INTERVAL,
    CONF_FAST_LANE,
    CONF_INTERVENTION_INTERVAL,
    CONF_PAGED,
)


def test_defaults_are_well_under_the_cap():
    assert estimate.steady_per_min({}) < 24


def test_everything_on_the_fast_lane_at_minimum_is_the_ceiling():
    # The brief asked for > 24; the spec's model gives ~22.5 here (and ~23.4 with every switch on).
    opts = {
        CONF_FAST_LANE: ["paged", "vehicles", "personnel"],
        CONF_FAST_INTERVAL: 10,
        CONF_INTERVENTION_INTERVAL: 15,
    }
    assert 22 < estimate.steady_per_min(opts) < 24


def test_moving_a_lookup_to_the_fast_lane_changes_its_pace():
    base = {CONF_PAGED: False, CONF_FAST_LANE: [], CONF_INTERVENTION_INTERVAL: 30, CONF_FAST_INTERVAL: 15}
    moved = {**base, CONF_FAST_LANE: ["vehicles"]}
    # vehicles: 2/min at 30 s becomes 4/min at 15 s
    assert estimate.steady_per_min(moved) - estimate.steady_per_min(base) == 2.0


def test_timer_floors_count_only_active_lookups():
    off = {"my_availability": False, "my_events": False, "statistics": False, CONF_PAGED: False}
    assert estimate.steady_per_min(off, calendar=False) < estimate.steady_per_min(off)
    assert estimate.steady_per_min(off) < estimate.steady_per_min({})


def test_page_counts_only_while_paged_is_in_the_fast_lane():
    base = {CONF_INTERVENTION_INTERVAL: 30, CONF_FAST_INTERVAL: 15}
    unticked = {**base, CONF_FAST_LANE: []}
    # the page: 4/min at 15 s, only while Paged is in the fast lane and its switch is on
    assert estimate.steady_per_min(base) - estimate.steady_per_min(unticked) == 4.0
    assert estimate.steady_per_min({**base, CONF_PAGED: False}) == estimate.steady_per_min(unticked)
