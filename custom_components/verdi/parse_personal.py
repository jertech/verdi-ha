# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Turn the app route's answers about yourself into plain dicts. No Home Assistant imports.

AppGetUpcomingEventsCommand also returns calendarURI, a link that opens your planning without
any token. It is never read here, so it never leaves the response.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from .parse import clean, slug
from .schedule import parse_iso

SHIFT, SINGLE, EXCEPTION = "Shift", "Single", "Exception"

# Month abbreviations in the "last called" text, which Verdi writes in the request language.
MONTHS = {
    "jan": 1, "janv": 1, "feb": 2, "févr": 2, "mrt": 3, "mar": 3, "mars": 3, "apr": 4, "avr": 4,
    "mei": 5, "may": 5, "mai": 5, "jun": 6, "juin": 6, "jul": 7, "juil": 7, "aug": 8, "août": 8,
    "sep": 9, "sept": 9, "okt": 10, "oct": 10, "nov": 11, "dec": 12, "déc": 12,
}  # fmt: skip
# "<weekday> <day> <month>, HH:MM": "wo. 21 okt, 17:31", "mer.. 21 oct., 17:31", "Wed. 21 Oct, 17:31".
TIME_TEXT = re.compile(r"(\d{1,2})\s+([^\W\d_]+)\.?,?\s+(\d{1,2}):(\d{2})")


def _moment(value: Any) -> datetime | None:
    """An ISO date-time with a UTC offset; anything else is None."""
    moment = parse_iso(value)
    return moment if moment and moment.tzinfo else None


def _label(value: Any) -> str | None:
    """A name sent as text or as an object (pre-alert and garrison were only seen empty)."""
    if isinstance(value, dict):
        value = value.get("name") or value.get("functionName") or value.get("description")
    return clean(value) if isinstance(value, str) else None


def _by_name(items: list[dict[str, Any]] | None, name_key: str) -> dict[str, str | None]:
    return {
        name: clean(item.get("availabilityName"))
        for item in items or []
        if (name := clean(item.get(name_key)))
    }


def last_called(text: Any, now: datetime) -> datetime | None:
    """Read Verdi's "last called" text, which has no year, in now's time zone.

    The year is the latest one that doesn't put the moment more than two hours after now (clock skew).
    """
    if not isinstance(text, str) or not (m := TIME_TEXT.search(text)):
        return None
    day, word, hour, minute = m.groups()
    if (month := MONTHS.get(word.casefold())) is None:
        return None
    for year in (now.year, now.year - 1):
        try:
            moment = now.replace(
                year=year,
                month=month,
                day=int(day),
                hour=int(hour),
                minute=int(minute),
                second=0,
                microsecond=0,
            )
        except ValueError:
            continue
        if moment <= now + timedelta(hours=2):
            return moment
    return None


BLOCKS = (
    ("stationAvailabilities", "station"),
    ("stationPlanningGroupAvailabilities", "station_group"),
    ("planningGroupAvailabilities", "group"),
)


def _text_id(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _blocks(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Per station / planning group: the IDs and flags back to planning needs. Kept in memory only; the
    sensor's attributes don't show them."""
    found: list[dict[str, Any]] = []
    for key, scope in BLOCKS:
        for block in data.get(key) or []:
            if not isinstance(block, dict):
                continue
            found.append(
                {
                    "scope": scope,
                    "station_id": _text_id(block.get("stationId")),
                    "planning_group_id": _text_id(block.get("planningGroupId")),
                    "availability": clean(block.get("availabilityName")),
                    "can_return": block.get("canReturnToPlanning") is True,
                    "end": _moment(block.get("end")),
                }
            )
    return found


def my_availability(data: dict[str, Any]) -> dict[str, Any] | None:
    """Your availability now: overall, per station and per planning group."""
    overall = data.get("globalAvailability")
    if not isinstance(overall, dict):
        return None
    blocks = [overall]
    for key in ("stationAvailabilities", "stationPlanningGroupAvailabilities", "planningGroupAvailabilities"):
        blocks += [b for b in data.get(key) or [] if isinstance(b, dict)]
    ends = sorted({end for b in blocks if (end := _moment(b.get("end")))})
    return {
        "availability": clean(overall.get("availabilityName")),
        "end": _moment(overall.get("end")),
        "color": overall.get("availabilityColor"),
        "garrison_crew": bool(overall.get("isGarrisonCrew")),
        "stations": _by_name(data.get("stationAvailabilities"), "stationName"),
        "planning_groups": _by_name(data.get("planningGroupAvailabilities"), "planningGroupName"),
        "ends": ends,
        "blocks": _blocks(data),
    }


def pre_alerts(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "description": clean(alert.get("description")),
            "station": _label(alert.get("station")),
            "function": _label(alert.get("function")),
            "start": _moment(alert.get("start")),
            "end": _moment(
                (alert.get("current") or {}).get("end")
                if isinstance(alert.get("current"), dict)
                else alert.get("end")
            ),
        }
        for alert in data.get("preAlarms") or []
        if isinstance(alert, dict)
    ]


def garrison(data: dict[str, Any]) -> dict[str, Any]:
    current = data.get("currentGarrison")
    if not isinstance(current, dict) or not (current.get("guid") or current.get("station")):
        return {"active": False, "station": None, "city": None}
    return {"active": True, "station": _label(current.get("station")), "city": clean(current.get("city"))}


def current_intervention(data: dict[str, Any]) -> dict[str, Any] | None:
    """Your current page, non-sensitive fields only, each text or None. None when you're not paged.

    Everything locating the incident or a third party (address, city, coordinates, caller,
    free-text info, radio group) is dropped here and never stored. Objects are reduced to their
    label, so no identifier reaches the sensor's attributes.
    """
    page = data.get("currentIntervention")
    if not isinstance(page, dict) or not page:
        return None
    alarm = page.get("alarmDate")
    return {
        "station": _label(page.get("station")),
        "crew_function": _label(page.get("crewFunction")),
        "vehicle": _label(page.get("vehicle")),
        "alarm_time": alarm if isinstance(alarm, str) else None,
        "incident": _label(page.get("incident")),
        "confirmation": _label(page.get("callConfirmation")),
    }


PAGE_KEY = re.compile(r"[A-Za-z]{1,40}")
PAGE_NESTED = ("station", "crewFunction", "callConfirmation")
PAGE_LISTS = ("callConfirmations",)
PAGE_KEYS_MAX = 60  # as timing.KEYS_MAX: a fetch never keeps fewer names than the page record


def page_keys(data: dict[str, Any]) -> list[str]:
    """The key names of your current page, one level deep under its station, crew function,
    confirmation, and the items of the confirmation choices. Names only, never values:
    diagnostics show the shape of a real page."""
    page = data.get("currentIntervention")
    if not isinstance(page, dict):
        return []
    names: list[str] = []
    for key, value in page.items():
        if not (isinstance(key, str) and PAGE_KEY.fullmatch(key)):
            continue
        names.append(key)
        if key in PAGE_NESTED and isinstance(value, dict):
            names += [f"{key}.{sub}" for sub in value if isinstance(sub, str) and PAGE_KEY.fullmatch(sub)]
        if key in PAGE_LISTS and isinstance(value, list):
            subs = {sub for item in value if isinstance(item, dict) for sub in item}
            names += [
                f"{key}[].{sub}" for sub in sorted(subs) if isinstance(sub, str) and PAGE_KEY.fullmatch(sub)
            ]
    return sorted(names)[:PAGE_KEYS_MAX]


def statistics(data: dict[str, Any], now: datetime) -> dict[str, list[dict[str, Any]]]:
    """Availability % per station and year (this year is the largest year, else the first listed),
    and how often you were called per station and service."""
    availability_year = []
    for counter in data.get("availabilityCounters") or []:
        head, sep, tail = (clean(counter.get("name")) or "").rpartition(" - ")
        station = clean(tail if sep else head)
        years = {
            name: round(float(interval["percentage"]), 1)
            for interval in counter.get("intervals") or []
            if (name := clean(interval.get("name"))) and isinstance(interval.get("percentage"), int | float)
        }
        if station and years:
            this_year = max(years, key=int) if all(y.isdecimal() and len(y) == 4 for y in years) else None
            availability_year.append(
                {
                    "id": slug(station),
                    "station": station,
                    "percentage": years[this_year] if this_year else next(iter(years.values())),
                    "years": years,
                }
            )
    times_called = []
    for group in data.get("interventionCounters") or []:
        station = clean(group.get("station"))
        for value in group.get("values") or []:
            name = clean(value.get("name")) or ""
            head, sep, _ = name.rpartition(":")
            service, count = clean(head if sep else name), value.get("value")
            if not station or not service or not isinstance(count, int):
                continue
            times_called.append(
                {
                    "id": slug(station, service),
                    "station": station,
                    "service": service,
                    "value": count,
                    "last_called": last_called(value.get("timestamp"), now),
                }
            )
    return {"availability_year": availability_year, "times_called": times_called}


def upcoming_events(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Your shifts, and the availability you set (Single) with its exceptions, sorted by start.

    An item can be listed under more than one day heading; it is kept once.
    """
    shifts: dict[Any, dict[str, Any]] = {}
    availability: dict[Any, dict[str, Any]] = {}
    for group in data.get("groups") or []:
        for item in group.get("items") or []:
            start, end = _moment(item.get("startDate")), _moment(item.get("endDate"))
            title = clean(item.get("title"))
            if not start or not end or end < start or not title:
                continue
            scope, position = clean(item.get("name")), clean(item.get("position"))
            if item.get("type") == SHIFT:
                found, summary, description = shifts, " · ".join(p for p in (title, position) if p), scope
            elif item.get("type") in (SINGLE, EXCEPTION):
                found, summary = availability, title
                description = " · ".join(p for p in (scope, position) if p) or None
            else:
                continue
            key = item.get("guid") or (start, end, summary)
            found.setdefault(
                key,
                {
                    "id": item.get("guid"),
                    "kind": str(item.get("type")).lower(),
                    "start": start,
                    "end": end,
                    "summary": summary,
                    "description": description,
                },
            )
    return {
        "shifts": sorted(shifts.values(), key=lambda e: e["start"]),
        "availability": sorted(availability.values(), key=lambda e: e["start"]),
    }
