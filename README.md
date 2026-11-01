# Verdi HA (unofficial)

> **Unofficial, not affiliated with Cevi or Verdi, not for operational use, uses your own Verdi account and its permissions, use at your own risk.**
> See [DISCLAIMER.md](DISCLAIMER.md) and [ADDITIONAL_TERMS.md](ADDITIONAL_TERMS.md).

A Home Assistant integration that shows information from Verdi with your own account, read-only unless you switch on changing your own status,
plus a Home Assistant app (formerly called add-on) that keeps the login token fresh.

## What you get

| Entity | Shows |
|--------|-------|
| `binary_sensor.<name>_readiness_<train>` | Whether a vehicle train is complete, with positions as attributes |
| `sensor.<vehicle>` | Vehicle availability |
| `binary_sensor.<vehicle>_on_intervention` | Whether the vehicle is on an intervention |
| `sensor.<name>_personnel` | Head count of the configured availabilities (the statuses Verdi sets when someone is called always count too), with counts per availability as attributes |
| `sensor.<name>_team_on_duty_<group>` | Current team, next team and rotation time |
| `sensor.<name>_on_duty_<function>` | Whether a crew function is filled now (or who, see privacy) |
| `sensor.<name>_my_availability` | Your own availability, its end time, per station and planning group (with its switch under "Your own data from the Verdi app" on) |
| `binary_sensor.<name>_pre_alert` | Whether you have a pre-alert (off by default; switch on in the options) |
| `binary_sensor.<name>_garrison` | Whether you're on garrison (off by default; switch on in the options) |
| `binary_sensor.<name>_paged` | Whether you're paged right now, with the page's station, crew function, vehicle, alarm time, incident and your confirmation as attributes |
| `sensor.<name>_availability_this_year_<station>` | Your availability % this year at a station; earlier years as attributes |
| `sensor.<name>_times_called_<station>_<service>` | How often you were called for a service, with the last call |
| `calendar.<name>_my_shifts` | Your own shifts, about a month ahead |
| `calendar.<name>_my_availability` | Availability you set, and exceptions, about a month ahead |
| `calendar.<name>_roster` | Shifts of the function calendar |
| with "Change my status" on | Actions, two selects and two buttons to change your own status (see [Changing your status](#changing-your-status-optional)) |
| `sensor.<name>_token_expires` | When the current token expires |
| `sensor.<name>_pace` | Polling pace: normal, intervention or backoff (diagnostic, disabled by default) |

The integration only reads, unless you switch on "Change my status": then it can also set and end your own status and add or remove your own planned statuses (four calls, listed in [docs/endpoints.md](docs/endpoints.md)). Its reads are listed there too,
with the same requests the Verdi web interface makes for the station data, and the read commands of
Verdi's app route for your own data. Each lookup is fetched only when it's due: personnel and
vehicles every tick (60 seconds by default, 30 seconds during an intervention), the rest when the
station data shows a change, at a time Verdi announced (a team rotation, a shift change, the end of
your availability), or after a safety interval. While you can be paged, your current page is checked
on a separate fast tick (15 seconds by default); when your availability says you can't be paged,
that check pauses. While Verdi has trouble, polling slows down; it never makes more than 30 calls a
minute.

## Optional: Remote Calendar subscription

Besides the integration's own two calendars, you can subscribe to your Verdi calendar feed with
Home Assistant's built-in **Remote Calendar** integration. It is an optional, lightweight alternative:

- it gives you **one combined, read-only calendar**;
- it refreshes **about once a day** by default; for another schedule, turn off "Enable polling for
  changes" on that calendar and add an automation that calls the **Update** entity action for it;
- it runs entirely in Home Assistant's Remote Calendar integration, so it does **not** use the Verdi
  integration's token or its call budget.

To set it up, add the Remote Calendar integration and enter your **Verdi calendar feed URL**, the
personal calendar link you find in the Verdi web app.

**Caveat.** The feed URL works without a login: anyone who has the link can read your planning.
Remote Calendar stores the URL in Home Assistant's configuration, so it also ends up in your backups.
Treat it like a password, keep your backups encrypted, and don't share the link. The integration's
two typed calendars remain the default and are not affected by this option.

## Changing your status (optional)

Off by default. With **Change my status** on (options, "Your own data"):

- actions `verdi.add_exception` (your status now, for a duration or unlimited), `verdi.return_to_planning`,
  `verdi.add_event` (a status for a time slot, returns the new event's ID) and `verdi.delete_event`;
- a **Status to set** and a **Duration** select, and **Set status** and **Back to planning** buttons.

Only Home Assistant administrators can use them; automations and scripts can too, so an automation you write can
be started by anyone who can trigger it. Your Verdi account needs the rights to change your own status and
calendar; without them the buttons stay unavailable. Pressing **Set status** without choosing a status gives an
"unknown status" error that lists the choices.

A status you set while a fixed planning applies can be overruled by that planning: Verdi accepts it, but the
planning keeps winning. The response of `verdi.add_exception` (`active`) says whether the status is active (true),
overruled by a fixed planning (false), or empty when that couldn't be checked; your availability sensor shows what
really applies.

On the days the clocks change, a planned status's duration is the real elapsed time.

**Add and remove from the availability calendar** is a second switch. Home Assistant's calendar view doesn't tell
the integration who is using it, so with this on **anyone who can open the calendar** can add or remove your planned
statuses and end a running one. The event's title must be a status name. An all-day planned status for today can't
be added from the calendar (its start, midnight, is already past); use a time slot.

When a change fails, Home Assistant itself may write Verdi's refusal message to its own log: for automations, for
failed actions and button presses started from the UI, and for every refused calendar removal. The integration
never logs it itself.

## Privacy

What the integration pulls from Verdi and stores in Home Assistant, including the recorder history:

- vehicle names and statuses, readiness, team names and rotation times;
- head counts per availability;
- roster shift times per crew function;
- with the matching switch under "Your own data from the Verdi app" on: your availability (overall,
  per station and per planning group) with its end time; pre-alert details (description, station,
  function, start and, when Verdi sends one, end) and your garrison station and city, both off by
  default; your shifts and availability events about a month ahead; and your availability % per year
  and times called with the last call. The calendar feed link Verdi returns is never stored;
- while you're paged: the page's station, crew function, vehicle, alarm time, incident and your
  confirmation (as the Paged sensor's attributes, so also in the history);
- with **Change my status** on, the integration sends Verdi your person ID, the chosen status, duration or
  time slot and your station or calendar, and nothing else; Verdi's answers to these changes are shown to
  whoever made the change and not stored or logged by the integration;
- the times of your last ten pages and of the station's last ten interventions, without IDs or page
  contents, kept in Home Assistant's storage and removed with the integration.

**Colleagues' names.** With the option "Show colleagues' names" **off** (the default for new setups),
names are dropped as soon as a response is read: on-duty sensors show *filled* or *open*, and
calendar events show only the function. With the option **on**, colleagues' names and their shift
times are shown and **stored in Home Assistant's history**. Make sure you are allowed to do that.

The token and the app's login state are credentials for your account:

- the token lives only in Home Assistant's memory, never in its configuration or logs;
- the app keeps its login state (`verdi_state.json`) in its own data folder, which is part of
  Home Assistant backups. **Keep your backups encrypted** and store the encryption key safely.

Diagnostics downloads contain counts, settings, lookup times, and the times of your last ten pages and of the
station's last ten interventions; every identifier is removed.

## Requirements

- Home Assistant 2026.4 or later.
- For automatic token refresh: Home Assistant OS or Supervised (the app), or any machine that can
  run a long-lived container or service ([standalone relay](docs/standalone-relay.md)).
- A PC with a screen for the one-time login (Windows, macOS or Linux, with Python 3.11+).

## Installation

### 1. Integration (Marketplace or HACS)

[![Open your Home Assistant instance and open this repository.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jertech&repository=verdi-ha&category=integration)

The button opens this repository in your Home Assistant. Or add it by hand:

- **Home Assistant 2026.11 or later:** **Settings > Marketplace**, open the menu, choose
  **Custom repositories**, add `https://github.com/jertech/verdi-ha` with type **Integration**.
  The Marketplace needs a GitHub connection for custom repositories.
- **Older versions, with HACS:** in HACS, open the menu, choose **Custom repositories**, add
  `https://github.com/jertech/verdi-ha` with type **Integration**.

Then install **Verdi (unofficial)**, and restart Home Assistant when it asks you to.

### 2. Token Relay app (Home Assistant OS)

1. Go to **Settings > Apps > App store** (called *Add-on store* in older versions), open the menu,
   choose **Repositories** and add `https://github.com/jertech/verdi-ha`.
2. Install **Verdi Token Relay**. Don't start it yet.

### 3. One-time login on a PC

The login includes your organisation's MFA, so it has to happen once in a real browser window:

```sh
python3 -m venv ~/.venvs/verdi && . ~/.venvs/verdi/bin/activate   # Windows: py -m venv %USERPROFILE%\.venvs\verdi && %USERPROFILE%\.venvs\verdi\Scripts\activate
pip install playwright==1.64.1
playwright install chromium
export VERDI_URL=https://yourzone.verdi.cloud VERDI_TENANT=YourTenant VERDI_STATE=~/verdi_state.json   # Windows: set ...
python3 verdi_token_relay/verdi_token_relay.py login
```

Keep the virtual environment and `verdi_state.json` outside the repository folder, as above.

The script is [verdi_token_relay/verdi_token_relay.py](verdi_token_relay/verdi_token_relay.py).
Your tenant name is the value after `tenant:` in the web login (see [docs/finding-your-ids.md](docs/finding-your-ids.md)).
Sign in in the window that opens. The script saves `verdi_state.json`: **treat it like a password.**

### 4. Give the login to the app

1. Copy `verdi_state.json` into the app's configuration folder (for example through the Samba app,
   into the Verdi Token Relay's folder in the `apps_configs` share).
2. In the app's **Configuration** tab, set your Verdi address and tenant, then start the app.
   It moves the file into its private data folder and deletes the copy you dropped in.

### 5. Add the integration

[![Open your Home Assistant instance and start setting up the Verdi integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=verdi)

**Settings > Devices & services > Add integration > Verdi (unofficial)**. Accept the notice, enter your
Verdi address and the IDs ([how to find them](docs/finding-your-ids.md)). The app delivers a token
within about 90 seconds; until then the integration shows as "retrying setup".

Options (**Configure** on the integration):
- "Show colleagues' names";
- **Station:** the tick (default 60 seconds, at least 30), the tick during an intervention
  (default 30, at least 15), the fast tick (default 15, at least 10), the vehicles that count for
  interventions (none picked: all), the availabilities that can't be paged (none picked: guessed
  from the name) and the availabilities that count in the personnel sensor, by name (the statuses
  Verdi sets when someone is called always count too);
- **Fast lane:** which lookups run on the fast tick: your current page always, vehicles and
  personnel if you add them (the options refuse a combination above 24 calls a minute);
- **Your own data from the Verdi app:** one switch each for your availability, pre-alert,
  garrison, your calendars and your statistics (pre-alert and garrison off by default);
- **Safety intervals:** the longest time between two fetches of readiness, roster, team on duty,
  your availability, pre-alert and garrison, your calendars and your statistics.

## How the token gets to Home Assistant

The app (or standalone relay) keeps the current token in memory and posts it to
`POST /api/verdi/token` on Home Assistant every 90 seconds, and right away when Home Assistant
comes back after a restart. Shortly before a token expires, it runs the normal web login in a
headless browser, which completes without interaction thanks to the saved login state. After a
restart, the integration waits up to 10 minutes for a token before it asks you to re-authenticate.

The endpoint requires a Home Assistant **administrator** and only accepts a token; it never returns
one. The app uses Home Assistant's API access for this (`homeassistant_api`), which technically
allows the app more than this one call; the app's code only calls this endpoint.

If the login ever needs interaction again (for example after a password change), Home Assistant
asks you to re-authenticate: redo step 3, copy the new `verdi_state.json` as in step 4, and restart
the app.

## Not using Home Assistant OS?

See [docs/standalone-relay.md](docs/standalone-relay.md) for running the relay as a service.

## Security

Please report vulnerabilities privately; see [SECURITY.md](SECURITY.md). Never post tokens,
`verdi_state.json`, HAR files, screenshots of the browser's network tab, IDs or names in issues.

## License

Copyright (C) 2026 jertech and contributors.

This program is free software: you can redistribute it and/or modify it under the terms of the
GNU General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version, with the additional terms in
[ADDITIONAL_TERMS.md](ADDITIONAL_TERMS.md). See [LICENSE](LICENSE) and [NOTICE](NOTICE).
