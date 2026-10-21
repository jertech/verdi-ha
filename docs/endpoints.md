# Verdi endpoints used

The integration only calls the endpoints below, with the request bodies the official
Verdi web interface sends for the signed-in user. All are reads. The API client refuses
anything else, and a test keeps this table and the client's allowlist identical.

Paths are relative to `<your Verdi address>/verdi-core/api/v1/`.

| Method | Path | Command | Used for |
|--------|------|---------|----------|
| POST | `configuration/readinesses/commands` | `ReadinessGetWidgetsCommand` | Readiness per vehicle train |
| POST | `configuration/persons/commands` | `PersonGetGroupedWidgetsCommand` | Personnel counts, your own availability |
| POST | `configuration/vehicles/commands` | `VehicleWidgetsSummaryCommand` | Vehicle status |
| POST | `configuration/team/groups/commands` | `TeamOnDutyWidgetCommand` | Team on duty |
| POST | `planning/functioncalendars/commands` | `FunctionCalendarPlanningWidgetCommand` | On-duty sensors |
| POST | `planning/functioncalendar/events/commands` | `FunctionCalendarEventGetForCalendarCommand` | Roster calendar |
| GET | `security/users/authorize` | - | Suggesting your own person GUID in the options |

The token grabber additionally opens the web login (`<your Verdi address>/auth/connect/authorize`)
with the same parameters the web app uses, and reads the token from the redirect.
