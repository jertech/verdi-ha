# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Minimal read-only client for the Verdi API.

Every lookup is a POST of {"command": "<Name>Command", ...} to <area>/commands: the web interface's
bodies for the station lookups, and the read commands of Verdi's mobile app route for your own
data. Only the endpoints in ALLOWED_ENDPOINTS can be called (see docs/endpoints.md).
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import aiohttp

APP_ROUTE = "mobile/app/commands"
# Read commands of Verdi's mobile app route, for your own data.
APP_COMMANDS = (
    "GetPersonCurrentAvailabilityCarouselInformationCommand",
    "GetPersonCurrentPreAlertInformationCommand",
    "GetPersonCurrentGarrisonInformationCommand",
    "AppGetPersonStatisticsCommand",
    "AppGetUpcomingEventsCommand",
)

# (method, path, command). Keep in sync with docs/endpoints.md; a test enforces it.
ALLOWED_ENDPOINTS: frozenset[tuple[str, str, str | None]] = frozenset(
    {
        ("POST", "configuration/readinesses/commands", "ReadinessGetWidgetsCommand"),
        ("POST", "configuration/persons/commands", "PersonGetGroupedWidgetsCommand"),
        ("POST", "configuration/vehicles/commands", "VehicleWidgetsSummaryCommand"),
        ("POST", "configuration/team/groups/commands", "TeamOnDutyWidgetCommand"),
        ("POST", "planning/functioncalendars/commands", "FunctionCalendarPlanningWidgetCommand"),
        (
            "POST",
            "planning/functioncalendar/events/commands",
            "FunctionCalendarEventGetForCalendarCommand",
        ),
        ("GET", "security/users/authorize", None),
    }
    | {("POST", APP_ROUTE, command) for command in APP_COMMANDS}
)


class VerdiError(Exception):
    """Verdi returned an error or an unexpected response."""


class VerdiAuthError(VerdiError):
    """The token is missing, expired or rejected."""


class VerdiUnavailable(VerdiError):
    """Verdi is busy or unreachable: 429, 5xx, a timeout or a connection error.

    retry_after: seconds Verdi asked to wait, if it said so.
    """

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def retry_after(value: str | None) -> float | None:
    """Seconds from a Retry-After header (seconds or an HTTP date), between 0 and an hour."""
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        seconds = (when - datetime.now(UTC)).total_seconds()
    return min(max(seconds, 0.0), 3600.0)


def clean_token(token: str) -> str:
    return token.strip().removeprefix("Bearer ").strip()


def jwt_claims(token: str) -> dict[str, Any] | None:
    """Decode a JWT payload WITHOUT verifying it. For routing and display only.

    Returns None unless the token has three base64url segments whose header and
    payload decode to JSON objects.
    """
    parts = token.split(".")
    if len(parts) != 3 or not all(parts[:2]):
        return None
    decoded = []
    for segment in parts[:2]:
        try:
            raw = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
            value = json.loads(raw)
        except (ValueError, TypeError):
            return None
        if not isinstance(value, dict):
            return None
        decoded.append(value)
    return decoded[1]


def token_expiry(token: str | None) -> datetime | None:
    claims = jwt_claims(token) if token else None
    try:
        return datetime.fromtimestamp(int(claims["exp"]), UTC) if claims else None
    except (KeyError, ValueError, TypeError, OverflowError):
        return None


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class VerdiApi:
    def __init__(self, session: aiohttp.ClientSession, base_url: str, token: str | None) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self.token = clean_token(token or "")

    def set_token(self, token: str) -> None:
        self.token = clean_token(token)

    async def _request(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        command = body.get("command") if body else None
        if (method, path, command) not in ALLOWED_ENDPOINTS:
            raise VerdiError(f"{path}: endpoint not allowed")
        if not self.token:
            raise VerdiAuthError(f"{path}: no token")
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        try:
            async with self._session.request(
                method,
                f"{self._base_url}/{path}",
                json=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status in (401, 403):
                    raise VerdiAuthError(f"{path}: HTTP {resp.status}")
                if resp.status == 429 or resp.status >= 500:
                    raise VerdiUnavailable(
                        f"{path}: HTTP {resp.status}", retry_after(resp.headers.get("Retry-After"))
                    )
                if resp.status != 200:
                    raise VerdiError(f"{path}: HTTP {resp.status}")
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise VerdiUnavailable(f"{path}: {type(err).__name__}") from err
        except TimeoutError as err:
            raise VerdiUnavailable(f"{path}: timeout") from err
        except ValueError as err:
            raise VerdiError(f"{path}: invalid JSON") from err
        if not isinstance(data, dict):
            raise VerdiError(f"{path}: unexpected response type")
        if data.get("result") not in (None, "Success"):
            # errorFeedback can contain personal data; never put it in the message.
            raise VerdiError(f"{path}: result={data.get('result')}")
        return data

    async def command(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", path, body)

    # Lookups, with bodies matching what the web interface sends.

    async def current_user(self) -> dict[str, Any]:
        return await self._request("GET", "security/users/authorize", None)

    async def readiness(self, station_id: str, train_ids: list[str]) -> dict[str, Any]:
        return await self.command(
            "configuration/readinesses/commands",
            {
                "command": "ReadinessGetWidgetsCommand",
                "stationIds": [station_id],
                "vehicleTrainIds": train_ids,
            },
        )

    async def personnel(self, station_id: str, availability_ids: list[str]) -> dict[str, Any]:
        return await self.command(
            "configuration/persons/commands",
            {
                "command": "PersonGetGroupedWidgetsCommand",
                "groupBy": "grade",
                "sortDefinition": {
                    "isDefault": False,
                    "field": "name",
                    "group": "person",
                    "defaultDirection": "Asc",
                },
                "stationFilter": [station_id],
                "includeInactiveStations": False,
                "gradeFilter": None,
                "availabilityFilter": availability_ids,
                "crewFunctionFilter": None,
                "teamFilter": None,
                "functionCalendarFilter": None,
                "vehicleCalendarFilter": None,
            },
        )

    async def vehicles(self, station_id: str) -> dict[str, Any]:
        return await self.command(
            "configuration/vehicles/commands",
            {
                "command": "VehicleWidgetsSummaryCommand",
                "searchParameters": {
                    "filter": [{"field": "station", "value": station_id, "operator": "Contains"}],
                    "search": "",
                    "skip": 0,
                    "take": 50,
                    "sort": [{"field": "name", "direction": "Asc"}],
                },
            },
        )

    async def team_on_duty(self, team_group_id: str) -> dict[str, Any]:
        return await self.command(
            "configuration/team/groups/commands",
            {
                "command": "TeamOnDutyWidgetCommand",
                "teamGroupFilter": [team_group_id],
                "showNextChange": False,
                "ShowPersons": False,
                "forContext": "fordashboardpage",
            },
        )

    async def roster(self, crew_function_ids: list[str]) -> dict[str, Any]:
        return await self.command(
            "planning/functioncalendars/commands",
            {
                "command": "FunctionCalendarPlanningWidgetCommand",
                "functionCalendarCrewFunctionIds": crew_function_ids,
                "targetDate": utc_now_iso(),
                "hideContactInformation": True,
            },
        )

    async def calendar_events(self, calendar_id: str, start: datetime, end: datetime) -> dict[str, Any]:
        return await self.command(
            "planning/functioncalendar/events/commands",
            {
                "command": "FunctionCalendarEventGetForCalendarCommand",
                "functionCalendarId": calendar_id,
                "from": _iso(start),
                "to": _iso(end),
                "includeHistoric": False,
            },
        )

    # Your own data, from the read commands of Verdi's mobile app route.

    async def my_availability(self) -> dict[str, Any]:
        return await self.command(APP_ROUTE, {"command": APP_COMMANDS[0]})

    async def pre_alerts(self) -> dict[str, Any]:
        return await self.command(APP_ROUTE, {"command": APP_COMMANDS[1]})

    async def garrison(self) -> dict[str, Any]:
        return await self.command(APP_ROUTE, {"command": APP_COMMANDS[2]})

    async def statistics(self, person_id: str, language: str) -> dict[str, Any]:
        return await self.command(
            APP_ROUTE, {"command": APP_COMMANDS[3], "personId": person_id, "language": language}
        )

    async def upcoming_events(self, person_id: str, language: str) -> dict[str, Any]:
        return await self.command(
            APP_ROUTE, {"command": APP_COMMANDS[4], "personId": person_id, "language": language}
        )
