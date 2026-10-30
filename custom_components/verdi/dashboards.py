# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Availability IDs that the station's dashboards show, as suggestions for the options.

Read only while the options form is built: the dashboard list, then each dashboard, every call
through the entry's guard. Only the availability IDs of personnel widgets for the configured
station are kept; dashboard names, owners and roles are never read into anything.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any

from .api import VerdiApi, VerdiError, VerdiUnavailable, is_guid
from .guard import Guard

_LOGGER = logging.getLogger(__name__)

PERSONNEL_WIDGET = "PersonnelGroupedWidget"


class _Stop(Exception):
    """Verdi is busy or the guard says wait: no more calls."""


def availability_ids(grid: Any, station_id: str) -> list[str]:
    """The availability IDs of a dashboard's personnel widgets for station_id, in order, once each."""
    found: list[str] = []
    if not isinstance(grid, dict):
        return found
    station = station_id.lower()
    for item in grid.get("widgetGridItems") or []:
        if not isinstance(item, dict) or item.get("widgetType") != PERSONNEL_WIDGET:
            continue
        config = item.get("configuration")
        if not isinstance(config, dict):
            continue
        stations = config.get("stationIds")
        if not isinstance(stations, list) or station not in {str(s).lower() for s in stations}:
            continue
        availabilities = config.get("availabilityIds")
        for value in availabilities if isinstance(availabilities, list) else []:
            if is_guid(value) and value.lower() not in found:
                found.append(value.lower())
    return found


async def discover(api: VerdiApi, guard: Guard, station_id: str) -> list[str]:
    """IDs from every dashboard's personnel widgets for station_id. Fails soft: [] when the list
    can't be read or the guard says wait; a dashboard that fails is skipped; Verdi busy stops it."""
    found: list[str] = []
    try:
        listing = await _call(guard, api.widget_grids, "widgetgrid/commands")
        if listing is None:
            return found
        items = listing.get("items")
        for item in items if isinstance(items, list) else []:
            grid_id = item.get("guid") if isinstance(item, dict) else None
            if not is_guid(grid_id):
                continue
            grid = await _call(guard, partial(api.widget_grid, grid_id), "widgetgrid/{id}")
            found += [i for i in availability_ids(grid, station_id) if i not in found]
    except _Stop:
        pass
    return found


async def _call(
    guard: Guard, fetch: Callable[[], Awaitable[dict[str, Any]]], path: str
) -> dict[str, Any] | None:
    """One guarded call. None when it failed; _Stop when no more calls should follow."""
    if not guard.can_call():
        raise _Stop
    guard.record_call()
    try:
        data = await fetch()
    except VerdiUnavailable as err:
        guard.wait(err.retry_after)
        raise _Stop from err
    except VerdiError as err:
        _LOGGER.debug("Dashboard suggestions: %s failed (%s)", path, type(err).__name__)
        return None
    guard.succeeded()
    return data
