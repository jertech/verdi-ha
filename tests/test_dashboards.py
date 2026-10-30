# SPDX-License-Identifier: GPL-3.0-or-later
"""Availability IDs a station dashboard shows, read only for the options."""

import random

from custom_components.verdi.api import VerdiAuthError, VerdiError, VerdiUnavailable
from custom_components.verdi.dashboards import availability_ids, discover
from custom_components.verdi.guard import Guard
from tests import responses as r


class FakeApi:
    def __init__(self, grids=None, listing=None):
        self.grids = r.WIDGET_GRID if grids is None else grids
        self.listing = r.WIDGET_GRIDS if listing is None else listing
        self.calls: list[str] = []

    async def widget_grids(self):
        self.calls.append("list")
        if isinstance(self.listing, Exception):
            raise self.listing
        return self.listing

    async def widget_grid(self, grid_id):
        self.calls.append(grid_id)
        value = self.grids[grid_id]
        if isinstance(value, Exception):
            raise value
        return value


def guard() -> Guard:
    return Guard(random.Random(0), clock=lambda: 1000.0)


def test_availability_ids_only_for_the_station():
    assert availability_ids(r.WIDGET_GRID[r.DASH_1], "station-1") == [r.AV_CALLED, r.AV_RADIO]
    assert availability_ids(r.WIDGET_GRID[r.DASH_2], "station-1") == []
    assert availability_ids(r.WIDGET_GRID[r.DASH_3], "station-1") == [r.AV_RADIO]  # case-insensitive
    for stations in (None, []):
        grid = r.widget_grid(r.DASH_1, [r.personnel_widget(stations, [r.AV_CALLED])])
        assert availability_ids(grid, "station-1") == []
    assert availability_ids(None, "station-1") == []
    assert (
        availability_ids(
            r.widget_grid(r.DASH_1, ["junk", {"widgetType": "PersonnelGroupedWidget"}]), "station-1"
        )
        == []
    )


async def test_discover_unions_the_dashboards_in_order():
    api, g = FakeApi(), guard()
    assert await discover(api, g, "station-1") == [r.AV_CALLED, r.AV_RADIO]
    assert api.calls == ["list", r.DASH_1, r.DASH_2, r.DASH_3]
    assert g.calls_last_minute() == 4


async def test_a_failing_dashboard_is_skipped():
    grids = {**r.WIDGET_GRID, r.DASH_1: VerdiAuthError("403")}
    assert await discover(FakeApi(grids), guard(), "station-1") == [r.AV_RADIO]


async def test_a_failing_list_gives_nothing():
    assert await discover(FakeApi(listing=VerdiError("result=Failed")), guard(), "station-1") == []


async def test_discover_stops_when_verdi_is_busy():
    grids = {**r.WIDGET_GRID, r.DASH_2: VerdiUnavailable("429", retry_after=30)}
    api, g = FakeApi(grids), guard()
    assert await discover(api, g, "station-1") == [r.AV_CALLED, r.AV_RADIO]
    assert api.calls == ["list", r.DASH_1, r.DASH_2]
    assert not g.can_call()


async def test_nothing_is_called_while_the_guard_says_wait():
    api, g = FakeApi(), guard()
    g.wait(60)
    assert await discover(api, g, "station-1") == []
    assert api.calls == []


async def test_items_without_an_id_are_not_fetched():
    listing = {**r.WIDGET_GRIDS, "items": [{"guid": "x"}, "junk", {"guid": r.DASH_1}]}
    api = FakeApi(listing=listing)
    assert await discover(api, guard(), "station-1") == [r.AV_CALLED, r.AV_RADIO]
    assert api.calls == ["list", r.DASH_1]
