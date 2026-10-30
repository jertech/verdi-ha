# Verdi endpoints used

The integration only calls the endpoints below. All are reads. The station lookups use the request
bodies the official Verdi web interface sends; your own data uses the read commands of Verdi's mobile
app route, which accept the same token. The API client refuses anything else, and a test keeps this
table and the client's allowlist identical.

Paths are relative to `<your Verdi address>/verdi-core/api/v1/`.

| Method | Path | Command | Used for |
|--------|------|---------|----------|
| POST | `configuration/readinesses/commands` | `ReadinessGetWidgetsCommand` | Readiness per vehicle train |
| POST | `configuration/persons/commands` | `PersonGetGroupedWidgetsCommand` | Personnel counts |
| POST | `domaindata/person/availabilities/displayitems` | - | The station's availabilities, plannable and the ones Verdi sets when someone is called: who is listed in personnel, and their names in the options |
| POST | `configuration/vehicles/commands` | `VehicleWidgetsSummaryCommand` | Vehicle status |
| POST | `configuration/team/groups/commands` | `TeamOnDutyWidgetCommand` | Team on duty |
| POST | `planning/functioncalendars/commands` | `FunctionCalendarPlanningWidgetCommand` | On-duty sensors |
| POST | `planning/functioncalendar/events/commands` | `FunctionCalendarEventGetForCalendarCommand` | Roster calendar |
| GET | `security/users/authorize` | - | Your person GUID, for your own data |
| POST | `mobile/app/commands` | `GetPersonCurrentAvailabilityCarouselInformationCommand` | My availability |
| POST | `mobile/app/commands` | `GetPersonCurrentPreAlertInformationCommand` | Pre-alert |
| POST | `mobile/app/commands` | `GetPersonCurrentGarrisonInformationCommand` | Garrison |
| POST | `mobile/app/commands` | `AppGetPersonStatisticsCommand` | Availability this year, times called |
| POST | `mobile/app/commands` | `AppGetUpcomingEventsCommand` | My shifts and My availability calendars |
| POST | `mobile/app/commands` | `GetPersonCurrentInterventionInformationCommand` | Current page (provisional shape) |

The `mobile/app/commands` rows are only called for the kinds of "Your own data from the Verdi app"
that are switched on in the options (your availability, calendars and statistics by default).

The token relay additionally opens the web login (`<your Verdi address>/auth/connect/authorize`)
with the same parameters the web app uses, and reads the token from the redirect.
