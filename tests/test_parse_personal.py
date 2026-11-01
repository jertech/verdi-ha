# SPDX-License-Identifier: GPL-3.0-or-later
"""Parsing the app route's answers about yourself, against synthetic responses and scrubbed fixtures."""

import copy
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from custom_components.verdi import parse_personal as p
from tests import responses as r

FIX = Path(__file__).parent / "fixtures"
TZ = ZoneInfo("Europe/Brussels")
NOW = datetime(2026, 6, 15, 20, 0, tzinfo=TZ)


def load(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "text", ["wo. 21 okt, 17:31", "mer.. 21 oct., 17:31", "Wed. 21 Oct, 17:31", "21 okt., 17:31"]
)
def test_last_called_in_each_language(text):
    now = datetime(2026, 10, 22, 12, 0, tzinfo=TZ)
    assert p.last_called(text, now) == datetime(2026, 10, 21, 17, 31, tzinfo=TZ)


@pytest.mark.parametrize(
    ("word", "month"),
    [("mrt", 3), ("mars", 3), ("Mar", 3), ("mei", 5), ("mai", 5), ("May", 5), ("févr", 2), ("août", 8),
     ("juil", 7), ("déc", 12), ("Dec", 12), ("sept", 9)],
)  # fmt: skip
def test_last_called_months(word, month):
    now = datetime(2026, 12, 31, 23, 0, tzinfo=TZ)
    assert p.last_called(f"vr. 10 {word}, 10:00", now).month == month


def test_last_called_new_year_belongs_to_previous_year():
    now = datetime(2027, 1, 1, 8, 0, tzinfo=TZ)
    assert p.last_called("do. 31 dec, 23:00", now) == datetime(2026, 12, 31, 23, 0, tzinfo=TZ)


@pytest.mark.parametrize(
    "text", ["", None, 17, "gisteren", "15 xyz, 10:00", "32 jun, 10:00", "15 jun, 25:00"]
)
def test_last_called_unknown_text(text):
    assert p.last_called(text, NOW) is None


def test_my_availability():
    mine = p.my_availability(r.CAROUSEL)
    assert mine["availability"] == "Available 5 min"
    assert mine["end"] == datetime(2026, 6, 15, 23, 59, 10, 598243, tzinfo=TZ)
    assert mine["color"] == "#00ff00"
    assert mine["garrison_crew"] is False
    assert mine["stations"] == {"Station North": "Available 5 min"}
    assert mine["planning_groups"] == {"All functions": "Available 5 min"}
    assert p.my_availability({"result": "Success"}) is None


def test_pre_alerts_accept_objects_and_text():
    assert p.pre_alerts(r.PRE_ALERTS) == [
        {
            "description": "Storm watch",
            "station": "Station North",
            "function": "Driver",
            "start": datetime(2026, 6, 15, 18, 0, tzinfo=TZ),
            "end": None,
        }
    ]
    text = {"preAlarms": [{"description": "Storm watch", "station": "Station North", "function": "Driver"}]}
    assert p.pre_alerts(text)[0]["station"] == "Station North"
    assert p.pre_alerts(text)[0]["start"] is None
    assert p.pre_alerts(r.PRE_ALERTS_NONE) == []
    assert p.pre_alerts({}) == []


def test_garrison():
    assert p.garrison(r.GARRISON) == {"active": True, "station": "Station North", "city": "Northville"}
    assert p.garrison(r.GARRISON_NONE) == {"active": False, "station": None, "city": None}
    assert p.garrison({"currentGarrison": {"guid": None, "station": None}})["active"] is False
    as_object = {"currentGarrison": {"guid": "g", "station": {"guid": "s", "name": "Station North"}}}
    assert p.garrison(as_object)["station"] == "Station North"


def test_statistics():
    stats = p.statistics(r.STATISTICS, NOW)
    assert stats["availability_year"] == [
        {
            "id": "station_north",
            "station": "Station North",
            "percentage": 34.7,
            "years": {"2026": 34.7, "2025": 44.1},
        }
    ]
    assert stats["times_called"] == [
        {
            "id": "station_north_2_ambulance",
            "station": "Station North",
            "service": "2° Ambulance",
            "value": 16,
            "last_called": datetime(2026, 6, 15, 17, 0, tzinfo=TZ),
        },
        {
            "id": "station_north_fire",
            "station": "Station North",
            "service": "Fire",
            "value": 17,
            "last_called": datetime(2026, 6, 15, 12, 0, tzinfo=TZ),
        },
    ]


def test_statistics_keeps_count_without_readable_time():
    data = {
        "interventionCounters": [
            {"station": "Station North", "values": [{"name": "Fire", "value": 3, "timestamp": "?"}]}
        ]
    }
    assert p.statistics(data, NOW)["times_called"] == [
        {
            "id": "station_north_fire",
            "station": "Station North",
            "service": "Fire",
            "value": 3,
            "last_called": None,
        }
    ]


def test_upcoming_events_split_dedupe_sort():
    events = p.upcoming_events(r.UPCOMING)
    assert [e["summary"] for e in events["shifts"]] == ["🚑 Ambulance 1 · Escort", "🚑 Ambulance 1 · Driver"]
    assert events["shifts"][0]["description"] == "Crew"
    assert [e["summary"] for e in events["availability"]] == ["Not available", "All 5 min", "Urgent"]
    assert events["availability"][1]["description"] == "Station North · All functions"
    assert events["availability"][0]["end"] == datetime(2027, 6, 30, 10, 0, tzinfo=TZ)


def test_upcoming_events_never_carry_the_feed_link():
    text = json.dumps(p.upcoming_events(r.UPCOMING), default=str)
    assert "secret-feed-id" not in text
    assert "calendar/" not in text


def test_fixture_availability():
    mine = p.my_availability(load("app_availability"))
    assert mine["availability"]
    assert mine["end"].tzinfo is not None
    assert len(mine["stations"]) == 1
    assert len(mine["planning_groups"]) == 1


def test_fixture_statistics():
    stats = p.statistics(load("app_statistics"), NOW)
    assert len(stats["availability_year"]) == 1  # only one station has intervals
    assert list(stats["availability_year"][0]["years"]) == ["2026", "2025"]
    assert len(stats["times_called"]) == 2
    assert {c["last_called"] for c in stats["times_called"]} == {datetime(2026, 6, 15, 17, 0, tzinfo=TZ)}


def test_fixture_upcoming_events():
    events = p.upcoming_events(load("app_upcoming_events"))
    assert len(events["shifts"]) == 12
    assert len(events["availability"]) == 3


def test_last_called_just_under_a_year_ago_is_not_tomorrow():
    now = datetime(2026, 10, 22, 20, 0, tzinfo=TZ)
    assert p.last_called("vr. 23 okt, 17:31", now) == datetime(2025, 10, 23, 17, 31, tzinfo=TZ)


def test_statistics_this_year_is_the_largest_year_when_listed_oldest_first():
    data = {
        "availabilityCounters": [
            {
                "name": "Beschikbaarheid (jaar) - Station North",
                "intervals": [{"name": "2025", "percentage": 44.1}, {"name": "2026", "percentage": 34.7}],
            }
        ]
    }
    item = p.statistics(data, NOW)["availability_year"][0]
    assert item["percentage"] == 34.7
    assert list(item["years"]) == ["2025", "2026"]


def test_statistics_keeps_first_interval_when_names_are_not_years():
    data = {
        "availabilityCounters": [
            {
                "name": "Beschikbaarheid - Station North",
                "intervals": [
                    {"name": "Last 12 months", "percentage": 50},
                    {"name": "2025", "percentage": 60},
                ],
            }
        ]
    }
    assert p.statistics(data, NOW)["availability_year"][0]["percentage"] == 50.0


def test_upcoming_events_drop_items_ending_before_they_start():
    data = {
        "groups": [
            {
                "items": [
                    r._event(
                        "a",
                        "Single",
                        "Backwards",
                        "2026-06-16T08:00:00+02:00",
                        "2026-06-15T08:00:00+02:00",
                        "Station North",
                        "All",
                    ),
                    r._event(
                        "b",
                        "Single",
                        "Fine",
                        "2026-06-15T08:00:00+02:00",
                        "2026-06-16T08:00:00+02:00",
                        "Station North",
                        "All",
                    ),
                ]
            }
        ]
    }
    assert [e["summary"] for e in p.upcoming_events(data)["availability"]] == ["Fine"]


def test_my_availability_lists_every_end():
    data = copy.deepcopy(r.CAROUSEL)
    data["stationAvailabilities"][0]["end"] = "2026-06-15T20:00:00+02:00"
    data["planningGroupAvailabilities"][0]["end"] = None
    ends = p.my_availability(data)["ends"]
    assert [e.isoformat() for e in ends] == ["2026-06-15T20:00:00+02:00", "2026-06-15T23:59:10.598243+02:00"]


def test_pre_alert_end_from_current_or_top_level():
    data = copy.deepcopy(r.PRE_ALERTS)
    assert p.pre_alerts(data)[0]["end"] is None
    data["preAlarms"][0]["current"] = {"end": "2026-06-15T19:00:00+02:00"}
    assert p.pre_alerts(data)[0]["end"].hour == 19
    data["preAlarms"][0]["current"] = True
    data["preAlarms"][0]["end"] = "2026-06-15T21:00:00+02:00"
    assert p.pre_alerts(data)[0]["end"].hour == 21


def test_current_intervention_keeps_only_safe_fields():
    out = p.current_intervention(r.CURRENT_INTERVENTION)
    assert out == {
        "station": "Station 1", "crew_function": "Driver", "vehicle": "P100",
        "alarm_time": "2026-10-24T09:00:00+00:00", "incident": "Fire", "confirmation": "Confirmed",
    }  # fmt: skip
    for leaked in (
        "Main St 1", "Townsville", "51.1", "3.7", "A Caller", "+320000", "secret", "RG1",
        "iv-1", "st-1", "cf-9", "cc-1", "Declined",
    ):  # fmt: skip
        assert leaked not in repr(out)


def test_current_intervention_none_when_absent():
    assert p.current_intervention({"currentIntervention": None}) is None
    assert p.current_intervention({}) is None


def test_current_intervention_never_returns_objects():
    out = p.current_intervention(
        {
            "currentIntervention": {
                "station": "Plain station",
                "vehicle": {"guid": "x-1", "name": "P1"},
                "incident": {"guid": "y-1"},
                "alarmDate": {"guid": "z-1"},
                "crewFunction": ["not", "a", "label"],
            }
        }
    )
    assert out == {
        "station": "Plain station", "crew_function": None, "vehicle": "P1",
        "alarm_time": None, "incident": None, "confirmation": None,
    }  # fmt: skip
    assert all(v is None or isinstance(v, str) for v in out.values())


def test_page_keys_are_names_only():
    keys = p.page_keys(r.CURRENT_INTERVENTION)
    assert keys == sorted(keys)
    for name in ("alarmDate", "station", "station.name", "station.guid", "crewFunction.functionName",
                 "callConfirmation.description", "callerPhoneNumber", "vehicle"):  # fmt: skip
        assert name in keys
    for value in ("Station 1", "st-1", "Main St 1", "+320000", "Confirmed"):
        assert value not in repr(keys)


def test_page_keys_filter_and_cap():
    assert p.page_keys({}) == []
    assert p.page_keys({"currentIntervention": None}) == []
    odd = {"ok": 1, "bad key": 2, "x" * 41: 3, "ünïcode": 4, "station": {"name": 1, "no-dash": 2}}
    assert p.page_keys({"currentIntervention": odd}) == ["ok", "station", "station.name"]
    many = {chr(65 + i % 26) * (1 + i // 26): i for i in range(60)}
    assert len(p.page_keys({"currentIntervention": many})) == 40


def test_my_availability_keeps_blocks_for_writes():
    blocks = p.my_availability(r.CAROUSEL)["blocks"]
    assert [b["scope"] for b in blocks] == ["station", "station_group", "group"]
    assert blocks[0] == {
        "scope": "station",
        "station_id": "st-1",
        "planning_group_id": None,
        "availability": "Available 5 min",
        "can_return": True,
        "end": datetime(2026, 6, 15, 23, 59, 10, 598243, tzinfo=TZ),
    }
    assert blocks[1]["planning_group_id"] == "pg-1" and blocks[2]["station_id"] is None


def test_upcoming_events_keep_the_kind():
    events = p.upcoming_events(r.UPCOMING)
    assert [e["kind"] for e in events["availability"]] == ["single", "exception", "single"]
    assert {e["kind"] for e in events["shifts"]} == {"shift"}
