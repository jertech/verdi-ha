# Privacy

The integration stores what it fetches from Verdi in Home Assistant, including the recorder history.
This page lists what that is, and what you should protect.

## What is stored

**From your station**

- vehicle names and statuses, readiness, team names and rotation times;
- head counts per availability;
- roster shift times per crew function.

**About you**, only with the matching switch under "Your own data from the Verdi app" on:

- your availability (overall, per station and per planning group) and its end time;
- pre-alert details (description, station, function, start and, when Verdi sends one, end), off by default;
- your garrison station and city, off by default;
- your shifts and availability events, about a month ahead;
- your availability % per year, how often you were called, and the last call.

The calendar feed link Verdi returns is never stored.

**While you're paged:** the station, crew function, vehicle, alarm time, incident, city (as Verdi sends it,
sometimes with the postal code) and whether you've confirmed. These are attributes of the Paged sensor, so
they end up in the history too. The street address, coordinates, caller and free text are never stored.

**For the integration itself**, in Home Assistant's storage and removed with the integration:

- the times of your last ten pages and of the station's last ten interventions, with the field names
  (never the values) of those pages;
- the station and service names of your statistics counters (no values), so their sensors exist right
  after a restart;
- the account ID from the token, in the entry's settings, so the relay's tokens reach the right entry;
- the status page's settings: layout choices per user and station.

## Colleagues' names

With **Show colleagues' names** off (the default), names are dropped as soon as Verdi's answer is read.
On-duty sensors show *filled* or *open*, and calendar events show only the function.

With it on, colleagues' names and their shift times are shown and **stored in Home Assistant's history**.
Make sure you're allowed to do that.

## When you change your status

With **Change my status** on, the integration sends Verdi your person ID, the status, the duration or time
slot, the time of the change, and Verdi's own IDs for your station, planning group, calendar, crew function
and event type. Nothing about other people.

Verdi's answer is shown to whoever made the change. The integration doesn't store or log it.

## The token and your login

The token and the app's login state give access to your Verdi account.

- The token lives only in Home Assistant's memory, never in its configuration or logs.
- The app keeps its login state (`verdi_state.json`) in its own data folder. That folder is part of Home
  Assistant backups. **Keep your backups encrypted** and store the encryption key safely.

## Live updates

With **Live updates from Verdi** on (the default), the integration keeps one connection open to Verdi's live updates,
as the Verdi web interface does, with your token. Verdi sends change notices for your whole zone. Each holds only IDs
and the kind of change ("a person changed", "a vehicle changed", "a new intervention"), never names or contents. The
integration uses the notices about your station, yourself and your station's vehicles to decide what to fetch, and drops
the rest. It stores none of them; diagnostics only count them by kind.

## Diagnostics

A diagnostics download contains counts, settings, lookup times, the token's expiry, and the times of your
last ten pages (with their field names, never values) and of the station's last ten interventions. With
**Change my status** on, it also shows whether your account has the two rights and, per kind of change,
today's count, the last time and its outcome. Every identifier is removed.
