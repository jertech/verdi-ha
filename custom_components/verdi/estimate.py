# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Sustained calls per minute for an option set. Pure: no Home Assistant imports.

Sized to the intervention pace (the fastest sustained pace). The every-tick lookups run at
intervention_interval, fast-lane lookups at fast_interval, and every timer-bounded lookup at
its minimum safety floor, the worst case the options allow.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .const import (
    CONF_ALERTS_SAFETY,
    CONF_AVAILABILITY_SAFETY,
    CONF_EVENTS_INTERVAL,
    CONF_FAST_INTERVAL,
    CONF_FAST_LANE,
    CONF_GARRISON,
    CONF_INTERVENTION_INTERVAL,
    CONF_MY_AVAILABILITY,
    CONF_MY_EVENTS,
    CONF_PAGED,
    CONF_PRE_ALERT,
    CONF_ROSTER_SAFETY,
    CONF_STATISTICS,
    CONF_STATISTICS_INTERVAL,
    CONF_TEAMS_SAFETY,
    FAST_LANE_DEFAULT,
    FEATURES,
    INTERVALS,
)

CALL_LIMIT = 24  # calls per minute an option set may sustain

EVERY_TICK = ("personnel", "vehicles", "readiness")
MOVABLE = ("personnel", "vehicles")


def _seconds(options: Mapping[str, Any], key: str) -> float:
    default, minimum, _maximum, unit = INTERVALS[key]
    try:
        value = float(options.get(key, default))
    except (TypeError, ValueError):
        value = float(default)
    return max(value, minimum) * unit


def _on(options: Mapping[str, Any], key: str) -> bool:
    return bool(options.get(key, FEATURES[key]))


def steady_per_min(options: Mapping[str, Any], *, calendar: bool = True) -> float:
    """Calls per minute; calendar says whether a roster calendar is configured (entry.data)."""
    lane = options.get(CONF_FAST_LANE, FAST_LANE_DEFAULT) or []
    fast = [k for k in MOVABLE if k in lane]
    tick = [k for k in EVERY_TICK if k not in fast]
    total = len(tick) * 60 / _seconds(options, CONF_INTERVENTION_INTERVAL)
    fast_count = len(fast) + (1 if _on(options, CONF_PAGED) else 0)
    total += fast_count * 60 / _seconds(options, CONF_FAST_INTERVAL)

    # Timer-bounded lookups at their minimum safety floor.
    floors = [INTERVALS[CONF_TEAMS_SAFETY], INTERVALS[CONF_ROSTER_SAFETY]]
    if calendar:
        floors.append(INTERVALS[CONF_ROSTER_SAFETY])
    for switch, key in (
        (CONF_MY_AVAILABILITY, CONF_AVAILABILITY_SAFETY),
        (CONF_PRE_ALERT, CONF_ALERTS_SAFETY),
        (CONF_GARRISON, CONF_ALERTS_SAFETY),
        (CONF_MY_EVENTS, CONF_EVENTS_INTERVAL),
        (CONF_STATISTICS, CONF_STATISTICS_INTERVAL),
    ):
        if _on(options, switch):
            floors.append(INTERVALS[key])
    total += sum(60 / (minimum * unit) for _d, minimum, _m, unit in floors)
    return total
