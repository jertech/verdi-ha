# Verdi endpoints used

The integration only calls the endpoints below. All are reads, except the four rows marked **Write**, which are only sent when "Change my status" is on in the options. The station lookups use the request
bodies the official Verdi web interface sends; your own data uses the read commands of Verdi's mobile
app route, which accept the same token. The API client refuses anything else, and a test keeps this
table and the client's allowlist identical.

Paths are relative to `<your Verdi address>/verdi-core/api/v1/`.

| Method | Path | Command | Used for |
|--------|------|---------|----------|
| POST | `configuration/readinesses/commands` | `ReadinessGetWidgetsCommand` | Readiness per vehicle train |
| POST | `configuration/persons/commands` | `PersonGetGroupedWidgetsCommand` | Personnel counts, and your own line (pageability, changes to your own data) |
| POST | `domaindata/person/availabilities/displayitems` | - | The station's availabilities, plannable and the ones Verdi sets when someone is called: who is listed in personnel, and their names in the options |
| POST | `configuration/vehicles/commands` | `VehicleWidgetsSummaryCommand` | Vehicle status |
| POST | `configuration/team/groups/commands` | `TeamOnDutyWidgetCommand` | Team on duty |
| POST | `planning/functioncalendars/commands` | `FunctionCalendarPlanningWidgetCommand` | On-duty sensors |
| POST | `planning/functioncalendar/events/commands` | `FunctionCalendarEventGetForCalendarCommand` | Roster calendar |
| GET | `security/users/authorize` | - | Your person GUID and, with status changes on, whether your account may change your status and calendar |
| POST | `mobile/app/commands` | `GetPersonCurrentAvailabilityCarouselInformationCommand` | My availability |
| POST | `mobile/app/commands` | `GetPersonCurrentPreAlertInformationCommand` | Pre-alert |
| POST | `mobile/app/commands` | `GetPersonCurrentGarrisonInformationCommand` | Garrison |
| POST | `mobile/app/commands` | `AppGetPersonStatisticsCommand` | Availability this year, times called |
| POST | `mobile/app/commands` | `AppGetUpcomingEventsCommand` | My shifts and My availability calendars |
| POST | `mobile/app/commands` | `GetPersonCurrentInterventionInformationCommand` | Current page |
| POST | `domaindata/predefined/eventpriorities/search` | - | Verdi's event kinds, for a new event (only with status changes on) |
| POST | `planning/personcalendars/search` | - | Your availability calendars, for a new event (only with status changes on) |
| POST | `planning/personcalendar/events/commands` | `PersonAvailabilityEventAddExceptionCommand` | **Write:** add an exception (your status from now on, for a duration or unlimited) |
| POST | `configuration/persons/commands` | `PersonReturnToPlanningCommand` | **Write:** return to planning |
| POST | `planning/personcalendar/events` | - | **Write:** new event (a status for a time slot) |
| DELETE | `planning/personcalendar/events/{guid}` | - | **Write:** remove one of your own events |

The writes and the two reads before them are sent on the web interface's route with its
headers. None of them asks Verdi to include your person record.

The `mobile/app/commands` rows are only called for the kinds of "Your own data from the Verdi app"
that are switched on in the options (your availability, calendars and statistics by default), and the current
page while Paged is in the Fast lane (the default).

The token relay additionally opens the web login (`<your Verdi address>/auth/connect/authorize`)
with the same parameters the web app uses, and reads the token from the redirect.
