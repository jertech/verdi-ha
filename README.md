# Verdi HA (unofficial)

> **Unofficial, not affiliated with Cevi or Verdi, not for operational use, uses your own Verdi account and its permissions, use at your own risk.**
> See [DISCLAIMER.md](DISCLAIMER.md) and [ADDITIONAL_TERMS.md](ADDITIONAL_TERMS.md).

A Home Assistant integration that shows read-only information from Verdi with your own account,
plus a Home Assistant app (formerly called add-on) that keeps the login token fresh.

## What you get

| Entity | Shows |
|--------|-------|
| `binary_sensor.<name>_readiness_<train>` | Whether a vehicle train is complete, with positions as attributes |
| `sensor.<vehicle>` | Vehicle availability |
| `binary_sensor.<vehicle>_on_intervention` | Whether the vehicle is on an intervention |
| `sensor.<name>_personnel` | Head count, with counts per availability as attributes |
| `sensor.<name>_team_on_duty_<group>` | Current team, next team and rotation time |
| `sensor.<name>_on_duty_<function>` | Whether a crew function is filled now (or who, see privacy) |
| `sensor.<name>_my_availability` | Your own availability, its end time, per station and planning group (with "Your own data") |
| `binary_sensor.<name>_pre_alert` | Whether you have a pre-alert |
| `binary_sensor.<name>_garrison` | Whether you're on garrison |
| `sensor.<name>_availability_this_year_<station>` | Your availability % this year at a station; earlier years as attributes |
| `sensor.<name>_times_called_<station>_<service>` | How often you were called for a service, with the last call |
| `calendar.<name>_my_shifts` | Your own shifts, about a month ahead |
| `calendar.<name>_my_availability` | Availability you set, and exceptions, about a month ahead |
| `calendar.<name>_roster` | Shifts of the function calendar |
| `sensor.<name>_token_expires` | When the current token expires |

The integration only reads. It calls the endpoints listed in [docs/endpoints.md](docs/endpoints.md),
with the same requests the Verdi web interface makes for the station data, and the read commands of
Verdi's app route for your own data. The station data is polled every 120 seconds by default
(60 seconds at the fastest).

## Privacy

What the integration pulls from Verdi and stores in Home Assistant, including the recorder history:

- vehicle names and statuses, readiness, team names and rotation times;
- head counts per availability;
- roster shift times per crew function;
- with "Your own data" on: your availability (overall, per station and per planning group) with its
  end time, pre-alert details (description, station, function, start), your garrison station and
  city, your shifts and availability events about a month ahead, and your availability % per year
  and times called with the last call. The calendar feed link Verdi returns is never stored.

**Colleagues' names.** With the option "Show colleagues' names" **off** (the default for new setups),
names are dropped as soon as a response is read: on-duty sensors show *filled* or *open*, and
calendar events show only the function. With the option **on**, colleagues' names and their shift
times are shown and **stored in Home Assistant's history**. Make sure you are allowed to do that.

The token and the app's login state are credentials for your account:

- the token lives only in Home Assistant's memory, never in its configuration or logs;
- the app keeps its login state (`verdi_state.json`) in its own data folder, which is part of
  Home Assistant backups. **Keep your backups encrypted** and store the encryption key safely.

Diagnostics downloads contain only counts and settings with every identifier removed.

## Requirements

- Home Assistant 2026.4 or later.
- For automatic token refresh: Home Assistant OS or Supervised (the app), or any machine that can
  run a long-lived container or service ([standalone relay](docs/standalone-relay.md)).
- A PC with a screen for the one-time login (Windows, macOS or Linux, with Python 3.11+).

## Installation

### 1. Integration (HACS)

1. In HACS, open the menu, choose **Custom repositories**, add `https://github.com/jertech/verdi-ha`
   with type **Integration**.
2. Install **Verdi (unofficial)** and restart Home Assistant.

### 2. Token Relay app (Home Assistant OS)

1. Go to **Settings > Apps > App store** (called *Add-on store* in older versions), open the menu,
   choose **Repositories** and add `https://github.com/jertech/verdi-ha`.
2. Install **Verdi Token Relay**. Don't start it yet.

### 3. One-time login on a PC

The login includes your organisation's MFA, so it has to happen once in a real browser window:

```sh
python3 -m venv ~/.venvs/verdi && . ~/.venvs/verdi/bin/activate   # Windows: py -m venv %USERPROFILE%\.venvs\verdi && %USERPROFILE%\.venvs\verdi\Scripts\activate
pip install playwright==1.64.0
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

**Settings > Devices & services > Add integration > Verdi (unofficial)**. Accept the notice, enter your
Verdi address and the IDs ([how to find them](docs/finding-your-ids.md)). The app delivers a token
within about 90 seconds; until then the integration shows as "retrying setup".

Options (**Configure** on the integration): the station poll interval, "Show colleagues' names",
and "Your own data from the Verdi app" (on by default) with its poll intervals: your availability,
pre-alert and garrison every 60 seconds (at least 10), your calendars every 10 minutes, and your
statistics every 6 hours, plus just after midnight and two minutes after a vehicle of your station
starts or ends an intervention.

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
