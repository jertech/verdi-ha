# SPDX-License-Identifier: GPL-3.0-or-later
"""Parsing, against synthetic responses and the anonymised fixtures."""

import copy
import json
from pathlib import Path

from custom_components.verdi import parse
from tests import responses as r

FIX = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def test_readiness_positions_sorted_and_stable_id():
    train = parse.readiness_trains(r.READINESS)[0]
    assert train["id"] == "station_north_pump_1"
    assert list(train["positions"]) == ["Driver", "Crew"]


def test_personnel_summary_never_has_names():
    s = parse.personnel_summary(r.PERSONNEL)
    assert s["total"] == 2
    assert s["by_availability"] == {"Available": 1, "Urgent": 1}  # trailing space cleaned
    assert all(
        set(p) == {"id", "availability", "on_intervention", "on_pre_alert", "present", "garrison_crew"}
        for p in s["persons"]
    )


def test_roster_without_names():
    rows = parse.roster(r.ROSTER)
    assert rows[0]["current"] == {
        "start": "2026-06-15T07:00:00Z",
        "end": "2026-06-15T19:00:00Z",
        "mine": False,
    }
    assert rows[1]["current"] is None
    assert "Sam" not in json.dumps(rows)


def test_roster_with_names():
    rows = parse.roster(r.ROSTER, names=True)
    assert rows[0]["current"]["name"] == "Sam Sample"
    assert rows[0]["next"]["name"] == "Robin Test"


def test_calendar_summary():
    names = {"cf-1": "Officer"}
    assert parse.calendar_events(r.CALENDAR, names)[0]["summary"] == "Officer"
    assert parse.calendar_events(r.CALENDAR, names, names=True)[0]["summary"] == "Officer: Sam Sample"
    assert parse.calendar_events(r.CALENDAR, {}, names=False)[0]["summary"] == "Shift"


# Anonymised fixtures: the response shapes Verdi returns, every identifying value replaced.


def test_fixture_readiness():
    trains = parse.readiness_trains(load("readiness"))
    assert len(trains) == 6
    assert trains[0]["id"] == "station_a_train_1"
    assert all(t["complete"] for t in trains)
    assert trains[0]["positions"]["Position 1"] is True


def test_fixture_vehicle_names_are_cleaned():
    vehicles = parse.vehicles(load("vehicles"))
    assert len(vehicles) == 14
    assert vehicles[0]["name"] == "Vehicle 01 (PLATE-01)"  # doubled space collapsed
    assert vehicles[4]["name"] == "Vehicle 05 (PLATE-05)"  # trailing space removed


def test_fixture_personnel_counts_and_cleaned_labels():
    s = parse.personnel_summary(load("personnel"))
    assert s["total"] == 41
    assert s["by_availability"]["Availability 4"] == 1  # was "Availability 4 "
    assert sum(s["by_availability"].values()) == 41


def test_fixture_team_dash_means_no_next_team():
    team = parse.teams_on_duty(load("team_on_duty"))[0]
    assert team["current_team"] == "Station A - Team 1"
    assert team["next_team"] is None


def test_fixture_roster_handles_unfilled_function():
    rows = parse.roster(load("roster_now"))
    assert rows[0]["function"] == "Function 1"
    assert rows[0]["current"]["start"] == "2026-06-15T19:00:00+02:00"
    assert rows[2]["current"] is None and rows[2]["next"] is None


def test_personnel_keeps_garrison_crew_flag():
    data = copy.deepcopy(r.PERSONNEL)
    data["personGroups"][0]["persons"][0]["isGarrisonCrew"] = True
    persons = parse.personnel_summary(data)["persons"]
    assert [p["garrison_crew"] for p in persons] == [True, False]


def test_roster_marks_your_own_shifts_only():
    items = parse.roster(r.ROSTER, me="q")
    assert items[0]["current"]["mine"] is False
    assert items[0]["next"]["mine"] is True
    assert "personId" not in str(items)
    assert all(not (i["current"] or {}).get("mine") for i in parse.roster(r.ROSTER))


def test_calendar_events_keep_person_only_with_names():
    names = {"cf-1": "Officer"}
    assert parse.calendar_events(r.CALENDAR, names)[0]["person"] is None
    with_names = parse.calendar_events(r.CALENDAR, names, names=True)[0]
    assert (with_names["person"], with_names["summary"]) == ("Sam Sample", "Officer: Sam Sample")
    assert parse.calendar_summary(None, None) == "Shift"
    assert parse.calendar_summary("Officer", None) == "Officer"
