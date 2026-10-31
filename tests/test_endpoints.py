# SPDX-License-Identifier: GPL-3.0-or-later
"""The API client only calls the endpoints documented in docs/endpoints.md."""

import re
from pathlib import Path

import pytest
from aiohttp import ClientSession

from custom_components.verdi.api import ALLOWED_ENDPOINTS, VerdiApi, VerdiError, is_guid

GRID = "00000000-0000-4000-8000-000000000001"

DOC = Path(__file__).resolve().parent.parent / "docs" / "endpoints.md"


def documented() -> set[tuple[str, str, str | None]]:
    rows = set()
    for line in DOC.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*(GET|POST)\s*\|\s*`([^`]+)`\s*\|\s*(?:`([^`]+)`|-)\s*\|", line)
        if m:
            rows.add((m.group(1), m.group(2), m.group(3)))
    return rows


def test_allowlist_matches_docs():
    assert documented() == set(ALLOWED_ENDPOINTS)


async def test_other_endpoints_are_refused():
    async with ClientSession() as session:
        api = VerdiApi(session, "https://zone.verdi.example/verdi-core/api/v1", "x")
        with pytest.raises(VerdiError, match="not allowed"):
            await api.command("mobile/app/commands", {"command": "AnythingCommand"})
        with pytest.raises(VerdiError, match="not allowed"):
            await api.command("configuration/vehicles/commands", {"command": "VehicleDeleteCommand"})


async def test_every_lookup_is_allowed():
    """Each client method sends an allowed (method, path, command)."""
    calls = []

    class Recorder(VerdiApi):
        async def _request(self, method, path, body):
            calls.append((method, path, (body or {}).get("command")))
            return {}

    from datetime import UTC, datetime

    api = Recorder(None, "https://x.example", "t")  # type: ignore[arg-type]
    now = datetime.now(UTC)
    await api.readiness("s", ["t"])
    await api.personnel("s", ["a"])
    await api.availabilities("s", 0, 50)
    await api.availabilities("s", 0, 50, plannable=False)
    await api.vehicles("s")
    await api.team_on_duty("g")
    await api.roster(["c"])
    await api.calendar_events("c", now, now)
    await api.current_user()
    await api.my_availability()
    await api.pre_alerts()
    await api.garrison()
    await api.statistics("p", "nl")
    await api.upcoming_events("p", "nl")
    await api.current_intervention("p", "nl")
    assert set(calls) == set(ALLOWED_ENDPOINTS)


async def test_app_route_bodies():
    bodies = []

    class Recorder(VerdiApi):
        async def _request(self, method, path, body):
            bodies.append((path, body))
            return {}

    api = Recorder(None, "https://x.example", "t")  # type: ignore[arg-type]
    await api.my_availability()
    await api.statistics("person-1", "fr")
    await api.upcoming_events("person-1", "en")
    assert bodies == [
        ("mobile/app/commands", {"command": "GetPersonCurrentAvailabilityCarouselInformationCommand"}),
        (
            "mobile/app/commands",
            {"command": "AppGetPersonStatisticsCommand", "personId": "person-1", "language": "fr"},
        ),
        (
            "mobile/app/commands",
            {"command": "AppGetUpcomingEventsCommand", "personId": "person-1", "language": "en"},
        ),
    ]


def test_is_guid():
    assert is_guid(GRID)
    assert is_guid(GRID.upper())
    for value in ("av-1", "", None, 5, f"{GRID} ", f"{GRID}{GRID}", GRID[:-1]):
        assert not is_guid(value)


async def test_availability_list_bodies():
    bodies = []

    class Recorder(VerdiApi):
        async def _request(self, method, path, body):
            bodies.append(body)
            return {}

    api = Recorder(None, "https://x.example", "t")  # type: ignore[arg-type]
    await api.availabilities("s", 0, 50)
    await api.availabilities("s", 50, 50, plannable=False)
    station = {"field": "station", "value": "s", "operator": "Contains"}
    assert bodies == [
        {
            "filter": [{"field": "allowPlanning", "value": "true", "operator": "Eq"}, station],
            "skip": 0,
            "take": 50,
        },
        {"filter": [station], "skip": 50, "take": 50},
    ]
