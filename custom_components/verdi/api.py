# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Minimal client for the Verdi API.

Lookups are a POST of {"command": "<Name>Command", ...} to <area>/commands: the web interface's bodies for
the station lookups, and the read commands of Verdi's mobile app route for your own data. With "Change my
status" on, four writes of your own status and planning go out on the web route, as the web interface sends
them. Only the endpoints in ALLOWED_ENDPOINTS can be called (see docs/endpoints.md).
"""

from __future__ import annotations

import base64
import json
import math
import re
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
    "GetPersonCurrentInterventionInformationCommand",
)
GUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def is_guid(value: Any) -> bool:
    return isinstance(value, str) and GUID.fullmatch(value) is not None


WEB_ACCEPT = "application/json, text/plain, */*"
EVENTS = "planning/personcalendar/events"
EVENT_TEMPLATE = f"{EVENTS}/{{guid}}"
CALENDAR_INCLUDE = "recurrenceGroups,crewFunction,station"
REFUSED_STATUSES = (400, 404, 409, 422)
FEEDBACK_MAX = 300

# The writes of your own status and planning; only the write calls below (refusals=True) may send them.
WRITE_ENDPOINTS: frozenset[tuple[str, str, str | None]] = frozenset(
    {
        ("POST", "planning/personcalendar/events/commands", "PersonAvailabilityEventAddExceptionCommand"),
        ("POST", "configuration/persons/commands", "PersonReturnToPlanningCommand"),
        ("POST", EVENTS, None),
        ("DELETE", EVENT_TEMPLATE, None),
    }
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
        ("POST", "domaindata/person/availabilities/displayitems", None),
        ("GET", "security/users/authorize", None),
        ("POST", "domaindata/predefined/eventpriorities/search", None),
        ("POST", "planning/personcalendars/search", None),
    }
    | {("POST", APP_ROUTE, command) for command in APP_COMMANDS}
    | WRITE_ENDPOINTS
)


def endpoint_key(method: str, path: str, command: str | None) -> tuple[str, str, str | None]:
    """The allowlist entry a request falls under: an event DELETE with a GUID as last segment maps to the
    template; everything else must match exactly."""
    prefix = f"{EVENTS}/"
    if method == "DELETE" and path.startswith(prefix) and is_guid(path[len(prefix) :]):
        return (method, EVENT_TEMPLATE, command)
    return (method, path, command)


def feedback(data: Any) -> str:
    """Verdi's refusal texts, joined once each and capped. For the caller only: may name you, so never log or
    store it."""
    texts: list[str] = []
    if isinstance(data, dict):
        for key in ("errorFeedback", "warningFeedback"):
            items = data.get(key)
            for item in items if isinstance(items, list) else []:
                text = item
                if isinstance(item, dict):
                    text = next(
                        (item[k] for k in ("message", "description", "text") if isinstance(item.get(k), str)),
                        None,
                    )
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
        if not texts:
            for key in ("message", "title", "detail"):
                if isinstance(data.get(key), str) and data[key].strip():
                    texts.append(data[key].strip())
                    break
    return "; ".join(dict.fromkeys(texts))[:FEEDBACK_MAX]


class VerdiError(Exception):
    """Verdi returned an error or an unexpected response."""


class VerdiAuthError(VerdiError):
    """The token is missing, expired or rejected."""


class VerdiUnavailable(VerdiError):
    """Verdi is busy or unreachable: 429, 5xx, a timeout or a connection error.

    retry_after: seconds Verdi asked to wait, if it said so. status: the HTTP status, None without one.
    """

    def __init__(self, message: str, retry_after: float | None = None, status: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.status = status


class VerdiRefused(VerdiError):
    """Verdi refused a write. feedback holds Verdi's own texts for the caller; it may name you, so it is
    never part of the message and never logged or stored."""

    def __init__(self, message: str, feedback: str = "") -> None:
        super().__init__(message)
        self.feedback = feedback


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
    if math.isnan(seconds):
        return None
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

    async def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None,
        *,
        headers: dict[str, str] | None = None,
        ok: tuple[int, ...] = (200,),
        refusals: bool = False,
    ) -> dict[str, Any]:
        """refusals: a write; a refusal raises VerdiRefused with Verdi's feedback (outside the message)."""
        command = body.get("command") if body else None
        key = endpoint_key(method, path, command)
        if key not in ALLOWED_ENDPOINTS:
            raise VerdiError(f"{path}: endpoint not allowed")
        if key in WRITE_ENDPOINTS and not refusals:
            raise VerdiError(f"{path}: write not allowed here")
        if not self.token:
            raise VerdiAuthError(f"{path}: no token")
        sent = {"Authorization": f"Bearer {self.token}", "Accept": "application/json", **(headers or {})}
        try:
            async with self._session.request(
                method,
                f"{self._base_url}/{path}",
                json=body,
                headers=sent,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status in (401, 403):
                    raise VerdiAuthError(f"{path}: HTTP {resp.status}")
                if resp.status == 429 or resp.status >= 500:
                    raise VerdiUnavailable(
                        f"{path}: HTTP {resp.status}",
                        retry_after(resp.headers.get("Retry-After")),
                        status=resp.status,
                    )
                if resp.status not in ok:
                    if refusals and resp.status in REFUSED_STATUSES:
                        try:
                            answer = await resp.json(content_type=None)
                        except ValueError:
                            answer = None
                        raise VerdiRefused(f"{path}: refused", feedback(answer))
                    raise VerdiError(f"{path}: HTTP {resp.status}")
                if resp.status == 204:
                    return {}
                data = await resp.json(content_type=None)
                if data is None and refusals:
                    data = {}  # a write answered 200 without a body went through
        except aiohttp.ClientError as err:
            raise VerdiUnavailable(f"{path}: {type(err).__name__}") from err
        except TimeoutError as err:
            raise VerdiUnavailable(f"{path}: timeout") from err
        except ValueError as err:
            raise VerdiError(f"{path}: invalid JSON") from err
        if not isinstance(data, dict):
            raise VerdiError(f"{path}: unexpected response type")
        if data.get("result") not in (None, "Success"):
            if refusals:
                raise VerdiRefused(f"{path}: refused", feedback(data))
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

    async def availabilities(
        self, station_id: str, skip: int, take: int, *, plannable: bool = True
    ) -> dict[str, Any]:
        """The station's availabilities: the plannable ones, as the web app's availability filter lists
        them, or (plannable=False) all of them, also the ones Verdi sets when someone is called."""
        station = {"field": "station", "value": station_id, "operator": "Contains"}
        planning = {"field": "allowPlanning", "value": "true", "operator": "Eq"}
        return await self.command(
            "domaindata/person/availabilities/displayitems",
            {"filter": [planning, station] if plannable else [station], "skip": skip, "take": take},
        )

    async def availability_display_items(self, station_id: str) -> list[dict[str, Any]]:
        """The station's plannable availabilities as id and name, for the options."""
        data = await self.availabilities(station_id, 0, 50)
        return [{"id": i["guid"], "text": i["text"]} for i in data.get("data") or []]

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

    async def current_intervention(self, person_id: str, language: str) -> dict[str, Any]:
        return await self.command(
            APP_ROUTE,
            {"command": APP_COMMANDS[5], "personId": person_id, "language": language},
        )

    # Changing your own status and planning (only with "Change my status" on). The web route, as the
    # web interface sends them. Never an include header with "person": the national number rides along.

    @staticmethod
    def _web(language: str, **extra: str) -> dict[str, str]:
        return {"Accept": WEB_ACCEPT, "include-all": "false", "language": language, **extra}

    async def event_priorities(self, language: str) -> dict[str, Any]:
        return await self._request(
            "POST", "domaindata/predefined/eventpriorities/search", {}, headers=self._web(language)
        )

    async def person_calendars(self, person_id: str, language: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "planning/personcalendars/search",
            {"filter": [{"field": "person", "value": person_id, "operator": "Eq"}]},
            headers=self._web(language, **{"include-personcalendar": CALENDAR_INCLUDE}),
        )

    async def add_exception(
        self, person_id: str, availability_id: str, duration: str | None, station_id: str, language: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "planning/personcalendar/events/commands",
            {
                "command": "PersonAvailabilityEventAddExceptionCommand",
                "personId": person_id,
                "availabilityId": availability_id,
                "duration": duration,
                "stationIds": [station_id],
            },
            headers=self._web(language),
            refusals=True,
        )

    async def return_to_planning(
        self, person_id: str, station_id: str | None, planning_group_id: str | None, language: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "configuration/persons/commands",
            {
                "command": "PersonReturnToPlanningCommand",
                "personId": person_id,
                "stationId": station_id,
                "planningGroupId": planning_group_id,
                "timeStamp": utc_now_iso(),
            },
            headers=self._web(language),
            refusals=True,
        )

    async def add_event(self, body: dict[str, Any], language: str) -> dict[str, Any]:
        return await self._request(
            "POST", EVENTS, body, headers=self._web(language), ok=(200, 201), refusals=True
        )

    async def delete_event(self, event_id: str, language: str) -> dict[str, Any]:
        if not is_guid(event_id):
            raise VerdiError("delete: not an event ID")
        return await self._request(
            "DELETE", f"{EVENTS}/{event_id}", None, headers=self._web(language), ok=(200, 204), refusals=True
        )
