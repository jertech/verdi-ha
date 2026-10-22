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


_OK = {"result": "Success", "warningFeedback": [], "errorFeedback": []}
_NOW_UNTIL = "2026-06-15T23:59:10.5982431+02:00"

CAROUSEL = {
    "globalAvailability": {
        "availabilityName": "Available 5 min",
        "availabilityColor": "#00ff00",
        "canReturnToPlanning": True,
        "end": _NOW_UNTIL,
        "isGarrisonCrew": False,
    },
    "stationAvailabilities": [
        {
            "stationId": "st-1",
            "stationName": "Station North",
            "availabilityName": "Available 5 min",
            "availabilityColor": "#00ff00",
            "canReturnToPlanning": True,
            "end": _NOW_UNTIL,
            "isGarrisonCrew": False,
        }
    ],
    "stationPlanningGroupAvailabilities": [
        {
            "stationId": "st-1",
            "stationName": "Station North",
            "planningGroupId": "pg-1",
            "planningGroupName": "All functions",
            "availabilityName": "Available 5 min",
            "availabilityColor": "#00ff00",
            "canReturnToPlanning": True,
            "end": _NOW_UNTIL,
            "isGarrisonCrew": False,
        }
    ],
    "planningGroupAvailabilities": [
        {
            "planningGroupId": "pg-1",
            "planningGroupName": "All functions",
            "availabilityName": "Available 5 min",
            "availabilityColor": "#00ff00",
            "canReturnToPlanning": True,
            "end": _NOW_UNTIL,
            "isGarrisonCrew": False,
        }
    ],
    **_OK,
}

# Pre-alert and garrison were only seen empty. The filled shapes below are assumptions, so the
# parser accepts a station or function as text or as an object.
PRE_ALERTS_NONE = {"preAlarms": [], **_OK}
PRE_ALERTS = {
    "preAlarms": [
        {
            "guid": "pa-1",
            "description": "Storm watch",
            "station": {"guid": "st-1", "name": "Station North"},
            "start": "2026-06-15T18:00:00+02:00",
            "current": True,
            "function": {"guid": "f-1", "functionName": "Driver"},
        }
    ],
    **_OK,
}
GARRISON_NONE = dict(_OK)
GARRISON = {
    "currentGarrison": {
        "guid": "ga-1",
        "station": "Station North",
        "address": "1 Main Street",
        "city": "Northville",
        "latitude": 51.0,
        "longitude": 3.5,
        "callConfirmation": None,
    },
    **_OK,
}

STATISTICS = {
    "interventionCounters": [
        {
            "station": "Station North",
            "values": [
                {"name": "2° Ambulance: laatst opgeroepen", "value": 16, "timestamp": "ma. 15 jun, 17:00"},
                {"name": "Fire: laatst opgeroepen", "value": 17, "timestamp": "ma. 15 jun, 12:00"},
            ],
        }
    ],
    "availabilityCounters": [
        {
            "name": "Beschikbaarheid (jaar) - Station North",
            "intervals": [
                {"name": "2026", "period": "", "percentage": 34.7312},
                {"name": "2025", "period": "", "percentage": 44.0567},
            ],
        },
        {"name": "Beschikbaarheid (jaar) - Station South", "intervals": []},
    ],
    **_OK,
}


def _event(guid, kind, title, start, end, name, position):
    return {
        "guid": guid,
        "type": kind,
        "color": "#ff0000",
        "icon": None,
        "title": title,
        "startDate": start,
        "start": "Einde:",
        "endDate": end,
        "end": "ma. 15 jun, 23:59",
        "name": name,
        "position": position,
    }


_OVERNIGHT = _event(
    "ev-4",
    "Shift",
    "🚑 Ambulance 1 ",
    "2026-06-22T23:00:00+02:00",
    "2026-06-23T03:00:00+02:00",
    "Crew",
    "Driver",
)
UPCOMING = {
    "calendarURI": "https:/zone.verdi.example/verdi-core/api/v1/calendar/secret-feed-id/events.ics",
    "groups": [
        {
            "title": "Vandaag",
            "items": [
                _event(
                    "ev-1",
                    "Single",
                    "Not available",
                    "2025-12-02T08:00:00+01:00",
                    "2027-06-30T10:00:00+02:00",
                    "All stations",
                    "All functions",
                ),
                _event(
                    "ev-2",
                    "Exception",
                    "All 5 min",
                    "2026-06-15T17:59:00+02:00",
                    "2026-06-15T23:59:00+02:00",
                    "Station North",
                    "All functions",
                ),
                _event(
                    "ev-3",
                    "Single",
                    "Urgent ",
                    "2026-06-15T18:08:00+02:00",
                    "2026-06-16T06:00:00+02:00",
                    "All stations",
                    "All functions",
                ),
            ],
        },
        {
            "title": "ma. 22 juni",
            "items": [
                _OVERNIGHT,
                _event(
                    "ev-5",
                    "Shift",
                    "🚑 Ambulance 1 ",
                    "2026-06-22T19:00:00+02:00",
                    "2026-06-22T23:00:00+02:00",
                    "Crew",
                    "Escort",
                ),
            ],
        },
        {
            "title": "di. 23 juni",
            "items": [
                _OVERNIGHT,
                _event(
                    "ev-6",
                    "Other",
                    "Something new",
                    "2026-06-23T08:00:00+02:00",
                    "2026-06-23T09:00:00+02:00",
                    "",
                    "",
                ),
                {**_event("ev-7", "Shift", "No dates", "", "", "Crew", "Driver"), "startDate": None},
            ],
        },
    ],
    **_OK,
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
