# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure helpers for changing your own status."""

from datetime import UTC, datetime, timedelta

import pytest
from homeassistant.util import dt as dt_util

from custom_components.verdi import write_data as w
from tests import responses as r


def test_rights_only_person_entries_scoped_to_you():
    assert w.rights(r.RIGHTS_USER, "me-1") == {"status": True, "calendar": True}
    assert w.rights(r.RIGHTS_USER, "someone-else") == {"status": False, "calendar": False}
    vehicles_only = {**r.RIGHTS_USER, "allowedRights": r.RIGHTS_USER["allowedRights"][2:]}
    assert w.rights(vehicles_only, "veh-1") == {"status": False, "calendar": False}
    by_right_guid = {**r.CURRENT_USER, "allowedRights": [{**r.RIGHTS_USER["allowedRights"][0],
                     "rightPerTypeGuid": "x", "right": {"guid": w.RIGHT_STATUS}}]}  # fmt: skip
    assert w.rights(by_right_guid, "me-1")["status"] is False
    assert w.rights(r.CURRENT_USER, "me-1") == {"status": False, "calendar": False}
    assert w.rights({"allowedRights": "odd"}, "me-1") == {"status": False, "calendar": False}


def test_single_kind():
    assert w.single_kind(r.EVENT_PRIORITIES) == r.SINGLE_KIND
    assert w.single_kind({"data": []}) is None
    assert w.single_kind(None) is None


def test_calendars_default_and_find():
    cals = w.calendars(r.PERSON_CALENDARS)
    assert [c["id"] for c in cals] == ["cal-st", "cal-gen"]
    assert w.default_calendar(cals)["id"] == "cal-gen"
    assert w.find_calendar(cals, "station north")["id"] == "cal-st"
    assert w.find_calendar(cals, "General")["id"] == "cal-gen"
    assert w.find_calendar(cals, "General planning")["id"] == "cal-gen"
    assert w.find_calendar(cals, "Algemene planning")["id"] == "cal-gen"
    assert w.find_calendar(cals, "elsewhere") is None
    assert w.default_calendar([cals[0]])["id"] == "cal-st"
    assert w.default_calendar([]) is None
    assert [w.calendar_label(c) for c in cals] == ["Station North", "general"]


@pytest.mark.parametrize(
    ("delta", "text"),
    [
        (timedelta(minutes=10), "00:10:00"),
        (timedelta(hours=13), "13:00:00"),
        (timedelta(days=1), "1.00:00:00"),
        (timedelta(days=1, hours=1), "1.01:00:00"),
        (timedelta(days=2, minutes=5, seconds=7), "2.00:05:07"),
    ],
)
def test_timespan(delta, text):
    assert w.timespan(delta) == text


def test_durations_table():
    assert w.DURATIONS["5m"] == "00:05:00"
    assert w.DURATIONS["1d1h"] == "1.01:00:00"
    assert w.DURATIONS["unlimited"] is None
    assert next(iter(w.DURATIONS)) == w.DEFAULT_DURATION == "5m"
    assert len(w.DURATIONS) == 19


def test_event_body_web_shape_summer_and_winter():
    cals = w.calendars(r.PERSON_CALENDARS)
    summer = datetime(2026, 7, 1, 21, 40, tzinfo=UTC)
    body = w.event_body(person="me-1", availability="av-2", kind=r.SINGLE_KIND, calendar=cals[1],
                        start=summer, end=summer + timedelta(minutes=10))  # fmt: skip
    assert body == {
        "isoTime": {},
        "start": "2026-07-01T21:40:00.000Z",
        "end": "2026-07-01T21:50:00.000Z",
        "editable": True,
        "duration": "00:10:00",
        "startTime": "23:40:00",
        "person": {"guid": "me-1"},
        "personAvailability": {"guid": "av-2"},
        "eventPriority": r.SINGLE_KIND,
        "personCalendar": {"guid": "cal-gen"},
    }
    winter = datetime(2026, 12, 1, 21, 40, tzinfo=UTC)
    body = w.event_body(person="me-1", availability="av-2", kind=r.SINGLE_KIND, calendar=cals[0],
                        start=winter, end=winter + timedelta(days=1, hours=1))  # fmt: skip
    assert body["startTime"] == "22:40:00"
    assert body["duration"] == "1.01:00:00"
    assert body["station"] == {"guid": "st-1"}
    assert "crewFunction" not in body


@pytest.mark.parametrize(
    ("day", "duration", "start", "end"),
    [
        ((2027, 3, 28), "23:00:00", "2027-03-27T23:00:00.000Z", "2027-03-28T22:00:00.000Z"),
        ((2027, 10, 31), "1.01:00:00", "2027-10-30T22:00:00.000Z", "2027-10-31T23:00:00.000Z"),
    ],
)
def test_event_body_duration_is_elapsed_across_dst(day, duration, start, end):
    brussels = dt_util.get_time_zone(w.BRUSSELS)
    first = datetime(*day, tzinfo=brussels)
    body = w.event_body(person="me-1", availability="av-2", kind=r.SINGLE_KIND,
                        calendar=w.calendars(r.PERSON_CALENDARS)[1], start=first,
                        end=datetime.combine(first.date() + timedelta(days=1), first.time(), brussels))  # fmt: skip
    assert (body["duration"], body["start"], body["end"]) == (duration, start, end)
    assert body["startTime"] == "00:00:00"


def _block(scope, station=None, group=None, flagged=True, name="Urgent"):
    return {"scope": scope, "station_id": station, "planning_group_id": group, "availability": name,
            "can_return": flagged, "end": None}  # fmt: skip


def test_return_targets_skip_groups_under_a_sent_station():
    blocks = [
        _block("station", "st-1"),
        _block("station_group", "st-1", "pg-1"),
        _block("station_group", "st-2", "pg-2"),
        _block("group", None, "pg-3"),
        _block("group", None, "pg-4", flagged=False),
        _block("station", "ST-1"),
    ]
    assert w.return_targets(blocks) == [("st-1", None), ("st-2", "pg-2"), (None, "pg-3")]
    assert w.return_targets([_block("station", "st-1", flagged=False)]) == []
    assert w.return_targets([]) == []


def test_is_active():
    mine = {"availability": "Available", "blocks": [_block("station", "STATION-1", name="Urgent")]}
    assert w.is_active(mine, "station-1", "urgent") is True
    assert w.is_active(mine, "station-1", "Available") is False
    other = {"availability": "Urgent", "blocks": [_block("station", "st-9", name="Available")]}
    assert w.is_active(other, "station-1", "Urgent") is True
    assert w.is_active(None, "station-1", "Urgent") is False


def test_find_status_by_name_or_id():
    listed = {"av-1": "Available", "av-2": "Urgent"}
    assert w.find_status(listed, " urgent ") == ("av-2", "Urgent")
    assert w.find_status(listed, "AV-1") == ("av-1", "Available")
    assert w.find_status(listed, "Sick") is None
    assert w.find_status(listed, None) is None
