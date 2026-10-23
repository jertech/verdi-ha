# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Turn Verdi responses into plain dicts. No Home Assistant imports, so it is easy to test.

Personal names are dropped here, at parse time, unless the user enabled
"Show colleagues' names": nothing downstream ever sees them.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

# Verdi uses "-" for "no value" in some fields (e.g. nextTeamName).
EMPTY_MARKERS = {"", "-"}


def clean(value: Any) -> Any:
    """Collapse stray and doubled spaces in labels; map "" and "-" to None."""
    if isinstance(value, str):
        value = re.sub(r"\s+", " ", value).strip()
        return None if value in EMPTY_MARKERS else value
    return value


def localized(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("default") or next((v for v in value.values() if isinstance(v, str)), None)
    return clean(value)


def slug(*parts: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", " ".join(str(p) for p in parts if p).lower()).strip("_")


def full_name(person: dict[str, Any] | None) -> str | None:
    if not person:
        return None
    return clean(" ".join(p for p in (person.get("firstName"), person.get("name")) if p))


def readiness_trains(data: dict[str, Any]) -> list[dict[str, Any]]:
    trains = []
    for group in data.get("groups") or []:
        for train in group.get("items") or []:
            title, group_title = localized(train.get("title")), localized(group.get("title"))
            positions = sorted(train.get("items") or [], key=lambda p: p.get("trainItemOrder") or 0)
            trains.append(
                {
                    # The train GUIDs in this response change on every request, so the
                    # stable key is built from the station and train titles.
                    "id": slug(group_title, title),
                    "title": title,
                    "group": group_title,
                    "complete": bool(train.get("isComplete")),
                    "fastest_response_time": train.get("fastestResponseTime"),
                    "slowest_response_time": train.get("slowestResponseTime"),
                    "positions": {
                        localized(pos.get("trainItemName")): bool(pos.get("isComplete")) for pos in positions
                    },
                }
            )
    return trains


def vehicles(data: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for v in data.get("data") or []:
        availability = v.get("currentAvailability") or {}
        result.append(
            {
                "id": v.get("guid"),
                "name": clean(v.get("name")),
                "station": clean(v.get("stationName")),
                "availability": localized(availability.get("description")),
                "availability_since": availability.get("start"),
                "color": availability.get("backgroundColor"),
                "on_intervention": bool(v.get("isOnIntervention")),
                "at_outpost": bool(v.get("isAtOutpost")),
            }
        )
    return result


def personnel_summary(data: dict[str, Any]) -> dict[str, Any]:
    """Counts per availability, plus id and status per person. Never names."""
    persons = [p for g in data.get("personGroups") or [] for p in g.get("persons") or []]

    def availability(p: dict[str, Any]) -> str | None:
        return localized((p.get("currentAvailability") or {}).get("description"))

    return {
        "persons": [
            {
                "id": p.get("guid"),
                "availability": availability(p),
                "on_intervention": bool(p.get("isOnIntervention")),
                "on_pre_alert": bool(p.get("isOnPreAlert")),
                "present": bool(p.get("isPresent")),
                "garrison_crew": bool(p.get("isGarrisonCrew")),
            }
            for p in persons
        ],
        "total": len(persons),
        "by_availability": dict(Counter(availability(p) or "unknown" for p in persons)),
        "on_intervention": sum(bool(p.get("isOnIntervention")) for p in persons),
        "on_pre_alert": sum(bool(p.get("isOnPreAlert")) for p in persons),
        "present": sum(bool(p.get("isPresent")) for p in persons),
        "truncated": bool(data.get("isTruncated")),
    }


def teams_on_duty(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": t.get("groupId"),
            "group": clean(t.get("groupName")),
            "current_team": clean(t.get("currentTeamName")),
            "next_team": clean(t.get("nextTeamName")),
            "next_rotation": t.get("nextRotation"),
        }
        for t in data.get("teamsOnDuty") or []
    ]


def _shift(slot: dict[str, Any] | None, names: bool, me: str | None) -> dict[str, Any] | None:
    if not slot:
        return None
    # Only whether the shift is yours is kept, never another person's ID.
    shift = {
        "start": slot.get("start"),
        "end": slot.get("end"),
        "mine": bool(me) and slot.get("personId") == me,
    }
    if names:
        shift["name"] = full_name(slot)
    return shift


def roster(data: dict[str, Any], names: bool = False, me: str | None = None) -> list[dict[str, Any]]:
    return [
        {
            "id": item.get("functionCalendarCrewFunctionId"),
            "function": clean(item.get("crewFunctionName")),
            "description": clean(item.get("functionCalendarCrewFunctionDescription")),
            "current": _shift(item.get("current"), names, me),
            "next": _shift(item.get("next"), names, me),
        }
        for item in data.get("items") or []
    ]


def calendar_summary(function: str | None, person: str | None) -> str:
    return f"{function}: {person}" if person and function else person or function or "Shift"


def calendar_events(
    data: dict[str, Any], function_names: dict[str, str] | None = None, names: bool = False
) -> list[dict[str, Any]]:
    """Shifts from FunctionCalendarEventGetForCalendarCommand.

    An event only carries the crew-function GUID; its name comes from the roster lookup.
    """
    function_names = function_names or {}
    events = []
    for e in data.get("events") or []:
        function_id = (e.get("functionCalendarCrewFunction") or {}).get("guid")
        function = function_names.get(function_id)
        person = (full_name(e.get("person")) or "?") if names else None
        events.append(
            {
                "id": e.get("guid"),
                "start": e.get("start"),
                "end": e.get("end"),
                "summary": calendar_summary(function, person),
                "function_id": function_id,
                "person": person,
            }
        )
    return events
