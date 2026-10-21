# Finding your Verdi IDs

The integration needs a few IDs (GUIDs) that identify your station, team group, vehicle trains,
crew functions, availabilities and function calendar. They are visible in the requests the Verdi
web interface makes while you use its dashboard.

> **Warning.** The browser's network tab also shows your **bearer token** (in the `Authorization`
> header, and in the address after login). Anyone with that token can act as you until it expires.
> **Never share HAR files, network-tab screenshots or copied request headers**, not in issues,
> chats or forums. Copy only the ID values you need.

1. Sign in to your Verdi address in a desktop browser and open the dashboard.
2. Press F12, open the **Network** tab and filter on `commands`.
3. Reload the page. Click a request and open **Payload** (or *Request*):

| Integration field | Request (path ends with) | Field in the payload |
|-------------------|--------------------------|----------------------|
| Station ID | `configuration/readinesses/commands` | `stationIds` |
| Vehicle train IDs | `configuration/readinesses/commands` | `vehicleTrainIds` |
| Availability IDs | `configuration/persons/commands` | `availabilityFilter` |
| Team group ID | `configuration/team/groups/commands` | `teamGroupFilter` |
| Crew function IDs | `planning/functioncalendars/commands` | `functionCalendarCrewFunctionIds` |
| Function calendar ID | `planning/functioncalendar/events/commands` (open the roster) | `functionCalendarId` |

Lists go into the integration comma-separated.

## Tenant name (for the Token Grabber)

Sign out, keep the network tab open with **Preserve log** on, and filter on `authorize`. Start the
login and click the **first** request to `/auth/connect/authorize`. Its `acr_values` parameter
reads `tenant:<name>`; the part after `tenant:` is your tenant name.

Do not copy the later `/callback` address: it contains your tokens.

## Your person GUID (for "My availability")

The integration suggests it in its options when it can confirm it. Otherwise, find your own
entry in the `configuration/persons/commands` response (`guid` of your person record).
