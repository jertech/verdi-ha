# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Pure helpers for changing your own status: rights, event kinds, calendars, request bodies, durations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

# Verdi's fixed GUIDs (the same in every Verdi zone).
SINGLE_EVENT = "7e390610-06d7-557e-b8aa-59d801261b29"
RIGHT_STATUS = "3d7e487d-2454-5452-946c-8ff5c1b3be9f"
RIGHT_CALENDAR = "93c495ad-6409-5c55-b07a-3c7ccea36c5a"
RIGHTS = {"status": RIGHT_STATUS, "calendar": RIGHT_CALENDAR}

BRUSSELS = "Europe/Brussels"
GENERAL = "general"
GENERAL_NAMES = frozenset({"general", "algemene planning", "planning général", "planning générale"})

# The durations Verdi offers for an exception, as (option key → Verdi value); None is unlimited.
DURATIONS: dict[str, str | None] = {
    "5m": "00:05:00",
    "10m": "00:10:00",
    "15m": "00:15:00",
    "20m": "00:20:00",
    "30m": "00:30:00",
    "45m": "00:45:00",
    "1h": "01:00:00",
    "2h": "02:00:00",
    "4h": "04:00:00",
    "6h": "06:00:00",
    "8h": "08:00:00",
    "9h": "09:00:00",
    "10h": "10:00:00",
    "11h": "11:00:00",
    "12h": "12:00:00",
    "13h": "13:00:00",
    "1d": "1.00:00:00",
    "1d1h": "1.01:00:00",
    "unlimited": None,
}
DEFAULT_DURATION = "5m"


def _lower(value: Any) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def rights(user: Any, person_id: str) -> dict[str, bool]:
    """Which of the two rights your account has for yourself: Person entries whose rightPerTypeGuid is the
    right and whose scope lists your person GUID. The same right on vehicles doesn't count."""
    me = _lower(person_id)
    found = dict.fromkeys(RIGHTS, False)
    entries = user.get("allowedRights") if isinstance(user, dict) else None
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict) or entry.get("serviceModelType") != "Person":
            continue
        scope = entry.get("applicableEntityGuids")
        if not isinstance(scope, list) or me not in {_lower(g) for g in scope}:
            continue
        right = _lower(entry.get("rightPerTypeGuid"))
        for name, guid in RIGHTS.items():
            if right == guid:
                found[name] = True
    return found


def single_kind(data: Any) -> dict[str, Any] | None:
    """The single-event kind as Verdi returns it; it goes back unchanged in a new event's body."""
    items = data.get("data") if isinstance(data, dict) else None
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and _lower(item.get("guid")) == SINGLE_EVENT:
            return item
    return None


def _ref(value: Any, name_key: str) -> tuple[str | None, str | None]:
    if isinstance(value, dict) and isinstance(value.get("guid"), str):
        name = value.get(name_key)
        return value["guid"], name.strip() if isinstance(name, str) and name.strip() else None
    return None, None


def calendars(data: Any) -> list[dict[str, Any]]:
    """Your calendars that aren't obsolete: id, station and crew function (id and name)."""
    found: list[dict[str, Any]] = []
    items = data.get("data") if isinstance(data, dict) else None
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or item.get("isObsolete") or not isinstance(item.get("guid"), str):
            continue
        station_id, station = _ref(item.get("station"), "name")
        crew_id, crew = _ref(item.get("crewFunction"), "functionName")
        found.append(
            {
                "id": item["guid"],
                "station_id": station_id,
                "station": station,
                "crew_function_id": crew_id,
                "crew_function": crew,
            }
        )
    return found


def default_calendar(cals: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The calendar without station and crew function (the general planning), else the first."""
    return next(
        (c for c in cals if not c["station_id"] and not c["crew_function_id"]), cals[0] if cals else None
    )


def calendar_label(cal: dict[str, Any]) -> str:
    return cal["station"] or cal["crew_function"] or GENERAL


def find_calendar(cals: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    want = _lower(name)
    if want in GENERAL_NAMES:
        return next((c for c in cals if not c["station_id"] and not c["crew_function_id"]), None)
    return next((c for c in cals if _lower(calendar_label(c)) == want), None)


def timespan(delta: timedelta) -> str:
    """A .NET TimeSpan as Verdi writes it: hh:mm:ss, with d. in front from a day on."""
    seconds = max(int(delta.total_seconds()), 0)
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    clock = f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{days}.{clock}" if days else clock


def utc_ms(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def event_body(
    *,
    person: str,
    availability: str,
    kind: dict[str, Any],
    calendar: dict[str, Any],
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    """A new single event in the web interface's shape; startTime is Belgian local time."""
    local = start.astimezone(dt_util.get_time_zone(BRUSSELS))
    body: dict[str, Any] = {
        "isoTime": {},
        "start": utc_ms(start),
        "end": utc_ms(end),
        "editable": True,
        # Elapsed time, as start and end in UTC: across a DST change a wall-clock difference would disagree.
        "duration": timespan(end.astimezone(UTC) - start.astimezone(UTC)),
        "startTime": local.strftime("%H:%M:%S"),
        "person": {"guid": person},
        "personAvailability": {"guid": availability},
        "eventPriority": kind,
        "personCalendar": {"guid": calendar["id"]},
    }
    if calendar["station_id"]:
        body["station"] = {"guid": calendar["station_id"]}
    if calendar["crew_function_id"]:
        body["crewFunction"] = {"guid": calendar["crew_function_id"]}
    return body


def find_status(listed: dict[str, str], status: Any) -> tuple[str, str] | None:
    """(id, name) of a plannable status given by name or ID, case-insensitive."""
    want = _lower(status)
    if not want:
        return None
    for availability_id, name in listed.items():
        if _lower(availability_id) == want or _lower(name) == want:
            return availability_id, name
    return None


def return_targets(blocks: list[dict[str, Any]]) -> list[tuple[str | None, str | None]]:
    """(stationId, planningGroupId) per command for back to planning: each flagged station once; a flagged
    station-planning-group block under a sent station is skipped; other group blocks as they are."""
    targets: list[tuple[str | None, str | None]] = []
    sent: set[str] = set()
    for block in blocks:
        station = block.get("station_id")
        if (
            block.get("scope") == "station"
            and block.get("can_return")
            and station
            and _lower(station) not in sent
        ):
            sent.add(_lower(station))
            targets.append((station, None))
    for block in blocks:
        if not block.get("can_return"):
            continue
        station, group = block.get("station_id"), block.get("planning_group_id")
        if block.get("scope") == "station_group" and station and group and _lower(station) not in sent:
            targets.append((station, group))
        elif block.get("scope") == "group" and group:
            targets.append((None, group))
    return list(dict.fromkeys(targets))


def is_active(mine: Any, station_id: str, status: str) -> bool:
    """Whether your availability shows the status: the configured station's block, else the overall one."""
    if not isinstance(mine, dict):
        return False
    want = _lower(status)
    for block in mine.get("blocks") or []:
        if block.get("scope") == "station" and _lower(block.get("station_id")) == _lower(station_id):
            return _lower(block.get("availability")) == want
    return _lower(mine.get("availability")) == want
