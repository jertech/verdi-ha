# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic Verdi responses in the shapes Verdi returns. All names are made up."""

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

# The station's plannable availabilities. The fixture configures av-1 and av-2; av-3 and av-4 are
# only listed, and "Radio" (configured in some tests) isn't plannable, so the list leaves it out.
AVAILABILITIES = {
    "data": [
        {"guid": "av-1", "text": "Available"},
        {"guid": "av-2", "text": "Urgent "},
        {"guid": "av-3", "text": "Not available"},
        {"guid": "av-4", "text": "Sick"},
    ],
    "itemsCount": 4,
    "startIndex": 0,
    "total": 4,
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


_RIGHT_STATUS = "3d7e487d-2454-5452-946c-8ff5c1b3be9f"
_RIGHT_CALENDAR = "93c495ad-6409-5c55-b07a-3c7ccea36c5a"


def _right(per_type: str, model: str, scope: list[str]) -> dict:
    return {
        "roleGuid": "role-1",
        "right": {"guid": "r-x", "name": {"default": "Right"}, "type": "SomeRight"},
        "rightPerTypeGuid": per_type,
        "rightType": {"guid": "allow", "name": {"default": "Allow"}},
        "serviceModelType": model,
        "applicabilities": [{"applicabilityGuid": "ap-1", "entityTypeGuid": "et-1"}],
        "applicableEntityGuids": scope,
    }


# Rights as Verdi lists them: per right type, per model, scoped to entities. Yours are the Person ones
# that list your person GUID; the same right on vehicles doesn't count.
RIGHTS_USER = {
    **CURRENT_USER,
    "allowedRights": [
        _right(_RIGHT_STATUS, "Person", ["ME-1"]),
        _right(_RIGHT_CALENDAR, "Person", ["me-1"]),
        _right(_RIGHT_STATUS, "Vehicle", ["veh-1", "veh-2"]),
    ],
}

SINGLE_KIND = {
    "name": {"default": "Event", "nl": "Gebeurtenis", "fr": "Événement", "en": "Event"},
    "priority": 6,
    "permissions": {"canEdit": True},
    "guid": "7e390610-06d7-557e-b8aa-59d801261b29",
    "isObsolete": False,
}
EVENT_PRIORITIES = {
    "data": [
        {"name": {"default": "Shift"}, "priority": 4, "guid": "9e9045a2-4612-468f-a7a3-6d5060f9e18d"},
        {"name": {"default": "Exception"}, "priority": 5, "guid": "25cf071d-81e3-5ba3-91de-2388548afeb2"},
        SINGLE_KIND,
    ],
    "total": 3,
}
PERSON_CALENDARS = {
    "data": [
        {
            "guid": "cal-st",
            "person": {"guid": "me-1"},
            "station": {"guid": "st-1", "name": "Station North"},
            "recurrenceGroups": [],
            "permissions": {},
            "isObsolete": False,
        },
        {
            "guid": "cal-gen",
            "person": {"guid": "me-1"},
            "recurrenceGroups": [],
            "permissions": {},
            "isObsolete": False,
        },
        {"guid": "cal-old", "person": {"guid": "me-1"}, "isObsolete": True},
    ],
    "total": 3,
}
WRITE_OK = {"result": "Success", "warningFeedback": [], "errorFeedback": []}


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

# The shape of a real page (confirmed, including the confirmation after you confirm). Made-up values. The
# sensitive fields are present on purpose, to prove the parser drops them; the nested objects carry ids that must never leak.
CURRENT_INTERVENTION = {
    "currentIntervention": {
        "guid": "iv-1",
        "description": "secret description",
        "station": {"guid": "st-1", "name": "Station 1"},
        "crewFunction": {"guid": "cf-9", "functionName": "Driver"},
        "interventionDate": "2026-10-24T08:59:00+00:00",
        "alarmDate": "2026-10-24T09:00:00+00:00",
        "incident": "Fire",
        "address": "Main St 1",
        "city": "Townsville",
        "latitude": 51.1,
        "longitude": 3.7,
        "info": "secret",
        "callerName": "A Caller",
        "callerPhoneNumber": "+320000",
        "radioGroup": "RG1",
        "extraInfo": "secret2",
        "vehicle": "P100",
        "callConfirmation": {
            "guid": "cc-1",
            "description": "Confirmed",
            "backgroundColor": "#0f0",
            "extraConfirmation": False,
        },
        "callConfirmations": [
            {
                "guid": "cc-1",
                "description": "Confirmed",
                "backgroundColor": "#0f0",
                "extraConfirmation": False,
            },
            {
                "guid": "cc-2",
                "description": "Declined",
                "backgroundColor": "#f00",
                "extraConfirmation": False,
            },
        ],
    },
    **_OK,
}
CURRENT_INTERVENTION_NONE = dict(_OK)

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
        "domaindata/person/availabilities/displayitems": AVAILABILITIES,
        "configuration/vehicles/commands": VEHICLES,
        "configuration/team/groups/commands": TEAMS,
        "planning/functioncalendars/commands": ROSTER,
        "planning/functioncalendar/events/commands": CALENDAR,
        "mobile/app/commands": {
            "GetPersonCurrentAvailabilityCarouselInformationCommand": CAROUSEL,
            "GetPersonCurrentPreAlertInformationCommand": PRE_ALERTS_NONE,
            "GetPersonCurrentGarrisonInformationCommand": GARRISON_NONE,
            "AppGetPersonStatisticsCommand": STATISTICS,
            "AppGetUpcomingEventsCommand": UPCOMING,
            "GetPersonCurrentInterventionInformationCommand": CURRENT_INTERVENTION_NONE,
        },
    }


# Synthetic GUIDs for tests.
def guid(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012x}"
