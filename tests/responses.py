# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic Verdi responses with the captured shapes. All names are made up."""

PERSON_NAMES = ("Alex Example", "Sam Sample", "Robin Test")

READINESS = {
    "groups": [
        {
            "guid": "g1",
            "title": {"default": "Station North"},
            "items": [
                {
                    "guid": "changes-every-request",
                    "title": {"default": "Pump 1"},
                    "isComplete": True,
                    "slowestResponseTime": "00:08:00",
                    "fastestResponseTime": "00:04:00",
                    "trainOrder": 1,
                    "items": [
                        {
                            "guid": "p2",
                            "trainItemOrder": 2,
                            "trainItemName": {"default": "Crew"},
                            "isComplete": False,
                        },
                        {
                            "guid": "p1",
                            "trainItemOrder": 1,
                            "trainItemName": {"default": "Driver"},
                            "isComplete": True,
                        },
                    ],
                }
            ],
        }
    ],
    "result": "Success",
    "warningFeedback": [],
    "errorFeedback": [],
}

PERSONNEL = {
    "personGroups": [
        {
            "groupId": "g",
            "title": {"default": "Officer"},
            "persons": [
                {
                    "guid": "me-1",
                    "firstName": "Alex",
                    "name": "Example",
                    "isOnIntervention": False,
                    "isOnPreAlert": False,
                    "isPresent": True,
                    "currentAvailability": {
                        "guid": "a",
                        "backgroundColor": "#fff",
                        "description": {"default": "Available"},
                    },
                },
                {
                    "guid": "colleague-1",
                    "firstName": "Sam",
                    "name": "Sample",
                    "isOnIntervention": True,
                    "isOnPreAlert": False,
                    "isPresent": False,
                    "currentAvailability": {
                        "guid": "b",
                        "backgroundColor": "#f00",
                        "description": {"default": "Urgent "},
                    },
                },
            ],
        }
    ],
    "isTruncated": False,
    "result": "Success",
    "warningFeedback": [],
    "errorFeedback": [],
}

VEHICLES = {
    "data": [
        {
            "guid": "v1",
            "name": "P100",
            "stationName": "Station North",
            "isOnIntervention": False,
            "isAtOutpost": False,
            "currentAvailability": {
                "guid": "a1",
                "backgroundColor": "#0f0",
                "description": {"default": "Available"},
                "start": "2026-06-15T17:00:00Z",
            },
            "tagNames": [],
        }
    ],
    "total": 1,
    "result": "Success",
    "warningFeedback": [],
    "errorFeedback": [],
}

TEAMS = {
    "teamsOnDuty": [
        {
            "groupId": "team-1",
            "groupName": "North",
            "currentTeamName": "Team A",
            "nextTeamName": "Team B",
            "nextRotation": "2026-06-16T06:00:00Z",
        }
    ],
    "result": "Success",
    "warningFeedback": [],
    "errorFeedback": [],
}

ROSTER = {
    "items": [
        {
            "functionCalendarCrewFunctionId": "cf-1",
            "crewFunctionName": "Officer",
            "functionCalendarCrewFunctionDescription": "Watch",
            "current": {
                "personId": "p",
                "firstName": "Sam",
                "name": "Sample",
                "start": "2026-06-15T07:00:00Z",
                "end": "2026-06-15T19:00:00Z",
            },
            "next": {
                "personId": "q",
                "firstName": "Robin",
                "name": "Test",
                "start": "2026-06-15T19:00:00Z",
                "end": "2026-06-16T07:00:00Z",
            },
        },
        {
            "functionCalendarCrewFunctionId": "cf-2",
            "crewFunctionName": "Driver",
            "functionCalendarCrewFunctionDescription": "Watch",
            "current": None,
            "next": None,
        },
    ],
    "result": "Success",
    "warningFeedback": [],
    "errorFeedback": [],
}

CALENDAR = {
    "events": [
        {
            "guid": "e1",
            "start": "2099-06-15T07:00:00Z",
            "end": "2099-06-15T19:00:00Z",
            "person": {"firstName": "Sam", "name": "Sample"},
            "functionCalendarCrewFunction": {"guid": "cf-1"},
        }
    ],
    "isShiftPlanningCalendar": True,
    "result": "Success",
    "warningFeedback": [],
    "errorFeedback": [],
}

CURRENT_USER = {
    "isApplication": False,
    "userGuid": "u-1",
    "userName": "alex@example.org",
    "isSuperAdmin": False,
    "personGuid": "me-1",
    "name": "Alex Example",
    "allowedRights": [],
}


def all_ok() -> dict:
    return {
        "configuration/readinesses/commands": READINESS,
        "configuration/persons/commands": PERSONNEL,
        "configuration/vehicles/commands": VEHICLES,
        "configuration/team/groups/commands": TEAMS,
        "planning/functioncalendars/commands": ROSTER,
        "planning/functioncalendar/events/commands": CALENDAR,
    }
