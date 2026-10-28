# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""When pages and station interventions happened: the last few of each, for diagnostics.

Pure: no Home Assistant imports, no calls, no timers. signals.py feeds it every paged,
personnel and vehicles fetch with the time of that fetch's run. It keeps its own last-seen
state per input and never relies on the coordinator's previous value. Records hold times,
flags, counts and key names only, never IDs or page contents.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Any

KEEP = 10  # closed records kept per kind
JOIN = timedelta(minutes=10)  # rejoin after a close; how far back an earlier rise counts
PAGE_TIMEOUT = timedelta(hours=6)
STATION_TIMEOUT = timedelta(hours=3)
PAGE_FIELDS = ("station", "crew_function", "vehicle", "alarm_time", "incident", "confirmation")

Record = dict[str, Any]


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def _at(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    return moment if moment.tzinfo else None


def _seconds(record: Record, start: str, end: str) -> float | None:
    first, last = _at(record.get(start)), _at(record.get(end))
    return round((last - first).total_seconds(), 1) if first and last else None


def _active(record: Record | None, on: str, off: str) -> bool:
    return record is not None and record.get(on) is not None and record.get(off) is None


def _other_page(record: Record, alarm: Any) -> bool:
    """A different page: both alarm times known and not equal."""
    return bool(alarm and record.get("alarm_time") and alarm != record["alarm_time"])


def _records(value: Any) -> list[Record]:
    return [r for r in value if isinstance(r, dict)][:KEEP] if isinstance(value, list) else []


class TimingLog:
    """The last KEEP pages and station interventions, plus at most one open record of each."""

    def __init__(self) -> None:
        self.pages: list[Record] = []  # closed, newest first
        self.page: Record | None = None
        self.interventions: list[Record] = []
        self.intervention: Record | None = None
        self.on_change: Callable[[], None] | None = None
        # Memory only: (value, time) of the last fetch per input; None until seen after load.
        self._paged: tuple[bool, datetime, Any] | None = None  # (on, time, alarm_time)
        self._paged_loaded = True  # the next paged fetch is the first since load
        self._own: tuple[bool, datetime] | None = None
        self._own_known: bool | None = None  # False while your line is missing
        # Memory only: the last own-flag off-blip rejoin, so a page split in the same run can undo it.
        self._rejoin: tuple[Record, Any, Any, datetime, str | None, bool] | None = None
        # Memory only: the open records as loaded, to tell late changes from live ones.
        self._saved_page: Record | None = None
        self._saved_intervention: Record | None = None
        self._vehicles: tuple[bool, datetime] | None = None
        self._counts: list[tuple[datetime, int, bool]] = []  # (time, count, list changed)

    # Saved state and diagnostics.

    def dump(self) -> dict[str, Any]:
        return {
            "pages": self.pages,
            "page": self.page,
            "interventions": self.interventions,
            "intervention": self.intervention,
        }

    def load(self, data: Any) -> None:
        """Restore saved records; anything of an unknown shape is dropped."""
        if not isinstance(data, dict):
            return
        self.pages = _records(data.get("pages"))
        self.interventions = _records(data.get("interventions"))
        page, intervention = data.get("page"), data.get("intervention")
        self.page = page if isinstance(page, dict) else None
        self.intervention = intervention if isinstance(intervention, dict) else None
        self._saved_page, self._saved_intervention = self.page, self.intervention

    def diagnostics(self) -> dict[str, Any]:
        pages = ([self.page] if self.page else []) + self.pages
        stations = ([self.intervention] if self.intervention else []) + self.interventions
        return {
            "pages": [
                {
                    **p,
                    "own_after_paged_s": _seconds(p, "paged_on", "own_on"),
                    "paged_duration_s": _seconds(p, "paged_on", "paged_off"),
                }
                for p in pages
            ],
            "station_interventions": [
                {**s, "persons_after_vehicle_s": _seconds(s, "vehicle_on", "persons_rise")} for s in stations
            ],
        }

    # Inputs.

    def paging(self, paused: bool) -> None:
        """A resume makes the next paged fetch a fresh baseline, so paged_on_after never points
        to a fetch from before the pause."""
        if not paused:
            self._paged = None

    def paged(self, now: datetime, page: dict[str, Any] | None, keys: list[str]) -> None:
        self._expire(now)
        alarm = page.get("alarm_time") if page else None
        prev, self._paged = self._paged, (page is not None, now, alarm)
        loaded, self._paged_loaded = self._paged_loaded, False
        rec = self.page
        if page is None:
            if _active(rec, "paged_on", "paged_off"):
                self._end(rec, "paged_off", now, late=prev is None)
                self._try_close_page(now)
            return
        moved = None
        if self._rejoin is not None and self._rejoin[0] is rec and not _other_page(rec, alarm):
            self._rejoin = None  # the same page: the own flag's rejoin is confirmed
        if _active(rec, "paged_on", "paged_off"):
            if not _other_page(rec, alarm):
                return  # the same page, still on
            self._end(rec, "paged_off", now, late=prev is None)  # back-to-back: no off fetch between
            moved = self._split(rec, now)
            rec = None
        elif prev is not None and prev[0] and not (alarm and prev[2] and alarm != prev[2]):
            return  # still on after its record timed out
        if rec is None and (recent := self._recent(now)) is not None and not _other_page(recent, alarm):
            rec = self._reopen()
        if rec is not None and rec.get("paged_on") is not None:
            if not _other_page(rec, alarm):
                self._set(rec, "paged_off", None)  # a short off-blip of the same page
                return
            moved = self._split(rec, now)  # an earlier page whose record your own flag kept open
            rec = None
        if rec is None:
            rec = self._open_page(now)
        rec.update(
            {
                "alarm_time": alarm,
                "paged_on": _iso(now),
                "paged_on_after": _iso(prev[1]) if prev else None,
                "fields": {name: page.get(name) is not None for name in PAGE_FIELDS},
                "keys": list(keys),
            }
        )
        if moved:
            rec.update({"own_on": _iso(moved[3]), "own_on_after": moved[4], "paged_paused": moved[5]})
        if prev is None and loaded:
            self._late_or_startup(rec, self._saved_page)
        self._changed()

    def own(self, now: datetime, on: bool | None, paused: bool) -> None:
        """Your own line's on-intervention flag; None while your line is missing (unknown)."""
        self._expire(now)
        self._own_known = on is not None
        if on is None:
            return  # unknown opens or closes nothing
        prev, self._own = self._own, (on, now)
        rec = self.page
        if not on:
            self._rejoin = None  # the blip is confirmed
            if _active(rec, "own_on", "own_off"):
                self._end(rec, "own_off", now, late=prev is None)
                self._try_close_page(now)
            return
        if _active(rec, "own_on", "own_off") or (prev is not None and prev[0]):
            return  # already on
        closed = None
        if rec is None and self._recent(now) is not None:
            closed = self.pages[0].get("closed")
            rec = self._reopen()
        if rec is not None and rec.get("own_on") is not None:
            after = _iso(prev[1]) if prev else None
            self._rejoin = (rec, rec.get("own_off"), closed, now, after, paused)
            self._set(rec, "own_off", None)  # a short off-blip
            return
        if rec is None:
            rec = self._open_page(now)
        rec.update(
            {
                "own_on": _iso(now),
                "own_on_after": _iso(prev[1]) if prev else None,
                "paged_paused": paused,
            }
        )
        if prev is None:
            self._late_or_startup(rec, self._saved_page)
        self._changed()

    def vehicles(self, now: datetime, any_on: bool) -> None:
        """Whether any watched vehicle is on intervention."""
        self._expire(now)
        prev, self._vehicles = self._vehicles, (any_on, now)
        rec = self.intervention
        if not any_on:
            if rec is not None and rec.get("vehicle_off") is None:
                self._end(rec, "vehicle_off", now, late=prev is None)
                self._try_close_intervention(now)
            return
        if prev is None or prev[0]:
            return  # a baseline after load, or still on
        if rec is not None:
            rec["concurrent"] = self._still_up(rec)  # a new intervention while people were still out
            self._close_intervention(now)
        before, rise, rise_after = self._rise_before(now)
        self.intervention = {
            "opened": _iso(now),
            "vehicle_on": _iso(now),
            "vehicle_on_after": _iso(prev[1]),
            "vehicle_off": None,
            "persons_before": before,
            "persons_rise": rise,
            "persons_rise_after": rise_after,
            "persons_back": None,
            "truncated": False,
            "concurrent": False,
            "interrupted": False,
        }
        self._changed()

    def persons(self, now: datetime, count: int, truncated: bool, list_changed: bool) -> None:
        """How many listed people are on intervention; list_changed when the requested
        availabilities changed since the last fetch (the jump is the list, not people)."""
        self._expire(now)
        last = self._counts[-1] if self._counts else None
        self._counts.append((now, count, list_changed))
        while len(self._counts) > 2 and now - self._counts[1][0] > JOIN:
            self._counts.pop(0)
        rec = self.intervention
        if rec is None:
            return
        if truncated and not rec.get("truncated"):
            self._set(rec, "truncated", True)
        if list_changed or rec.get("persons_before") is None:
            if rec.get("persons_rise") is None:
                self._set(rec, "persons_before", count)  # a new baseline
            return
        if rec.get("persons_rise") is None:
            if count > rec["persons_before"]:
                self._late(rec, last is None)
                rec.update({"persons_rise": _iso(now), "persons_rise_after": _iso(last[0]) if last else None})
                self._changed()
        elif rec.get("persons_back") is None and count <= rec["persons_before"]:
            self._late(rec, last is None)
            self._set(rec, "persons_back", _iso(now))
            self._try_close_intervention(now)

    # Helpers.

    def _changed(self) -> None:
        if self.on_change is not None:
            self.on_change()

    def _set(self, rec: Record, field: str, value: Any) -> None:
        rec[field] = value
        self._changed()

    def _late(self, rec: Record, first: bool) -> None:
        """A change to a record as loaded, first seen after downtime: its times are late."""
        if first and rec is self._saved_intervention:
            rec["interrupted"] = True

    def _late_or_startup(self, rec: Record, saved: Record | None) -> None:
        if rec is saved:
            rec["interrupted"] = True  # joined a saved record after downtime
        else:
            rec["startup"] = True

    def _split(
        self, rec: Record, now: datetime
    ) -> tuple[Record, Any, Any, datetime, str | None, bool] | None:
        """Close a page record for a new page; an own-flag rejoin from this run belongs to the new page."""
        moved, self._rejoin = self._rejoin, None
        if moved is not None and moved[0] is not rec:
            moved = None
        if moved is not None:
            rec["own_off"] = moved[1]
        self._close_page(now)
        if moved is not None and moved[2]:
            rec["closed"] = moved[2]
        return moved

    def _end(self, rec: Record, field: str, now: datetime, *, late: bool) -> None:
        rec[field] = _iso(now)
        if late:
            rec["interrupted"] = True  # seen only after downtime: the time is late
        self._changed()

    def _expire(self, now: datetime) -> None:
        if self.page and (opened := _at(self.page.get("opened"))) and now - opened >= PAGE_TIMEOUT:
            self._close_page(now)
        rec = self.intervention
        if rec and (opened := _at(rec.get("opened"))) and now - opened >= STATION_TIMEOUT:
            rec["concurrent"] = self._still_up(rec)
            self._close_intervention(now)

    def _open_page(self, now: datetime) -> Record:
        self.page = {
            "opened": _iso(now),
            "alarm_time": None,
            "paged_on": None,
            "paged_on_after": None,
            "paged_off": None,
            "own_on": None,
            "own_on_after": None,
            "own_off": None,
            "fields": {},
            "keys": [],
            "startup": False,
            "interrupted": False,
            "paged_paused": False,
        }
        return self.page

    def _recent(self, now: datetime) -> Record | None:
        """The last closed page when it closed less than JOIN ago."""
        if self.pages and (closed := _at(self.pages[0].get("closed"))) and now - closed < JOIN:
            return self.pages[0]
        return None

    def _reopen(self) -> Record:
        rec = self.pages.pop(0)
        rec.pop("closed", None)
        self.page = rec
        self._changed()
        return rec

    def _try_close_page(self, now: datetime) -> None:
        rec = self.page
        if rec is None or _active(rec, "paged_on", "paged_off"):
            return
        if _active(rec, "own_on", "own_off") and self._own_known is not False:
            return
        self._close_page(now)

    def _close_page(self, now: datetime) -> None:
        rec, self.page = self.page, None
        if rec is None:
            return
        rec["closed"] = _iso(now)
        self.pages = [rec, *self.pages][:KEEP]
        self._changed()

    def _still_up(self, rec: Record) -> bool:
        before = rec.get("persons_before")
        count = self._counts[-1][1] if self._counts else None
        return before is not None and count is not None and count > before

    def _rise_before(self, now: datetime) -> tuple[int | None, str | None, str | None]:
        """(count before, rise, fetch before the rise) for the earliest rise at most JOIN ago;
        without one, the latest count and no rise."""
        for (before_at, before, _), (rose_at, count, changed) in pairwise(self._counts):
            if now - rose_at <= JOIN and not changed and count > before:
                return before, _iso(rose_at), _iso(before_at)
        return (self._counts[-1][1] if self._counts else None), None, None

    def _try_close_intervention(self, now: datetime) -> None:
        rec = self.intervention
        if rec is None or rec.get("vehicle_off") is None:
            return
        if rec.get("persons_rise") is not None and rec.get("persons_back") is None:
            return
        self._close_intervention(now)

    def _close_intervention(self, now: datetime) -> None:
        rec, self.intervention = self.intervention, None
        if rec is None:
            return
        rec["closed"] = _iso(now)
        self.interventions = [rec, *self.interventions][:KEEP]
        self._changed()
