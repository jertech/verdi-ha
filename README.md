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
| `sensor.<name>_my_availability` | Your own availability (after you set your person GUID) |
| `calendar.<name>_roster` | Shifts of the function calendar |
| `sensor.<name>_token_expires` | When the current token expires |

The integration only reads. It calls the endpoints listed in [docs/endpoints.md](docs/endpoints.md),
with the same requests the Verdi web interface makes, and polls every 120 seconds by default
(60 seconds at the fastest).

## Privacy

What the integration pulls from Verdi and stores in Home Assistant, including the recorder history:

- vehicle names and statuses, readiness, team names and rotation times;
- head counts per availability, and your own availability;
- roster shift times per crew function.

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
  run a long-lived container or service ([standalone grabber](docs/standalone-grabber.md)).
- A PC with a screen for the one-time login (Windows, macOS or Linux, with Python 3.11+).

## Installation

### 1. Integration (HACS)

1. In HACS, open the menu, choose **Custom repositories**, add `https://github.com/jertech/verdi-ha`
   with type **Integration**.
2. Install **Verdi (unofficial)** and restart Home Assistant.

### 2. Token Grabber app (Home Assistant OS)

1. Go to **Settings > Apps > App store** (called *Add-on store* in older versions), open the menu,
   choose **Repositories** and add `https://github.com/jertech/verdi-ha`.
2. Install **Verdi Token Grabber**. Don't start it yet.

### 3. One-time login on a PC

The login includes your organisation's MFA, so it has to happen once in a real browser window:

```sh
python3 -m venv venv && . venv/bin/activate     # Windows: venv\Scripts\activate
pip install playwright==1.64.0
playwright install chromium
export VERDI_URL=https://yourzone.verdi.cloud VERDI_TENANT=YourTenant   # Windows: set ...
python3 verdi_token_grabber.py login
```

The script is [verdi_token_grabber/verdi_token_grabber.py](verdi_token_grabber/verdi_token_grabber.py).
Your tenant name is the value after `tenant:` in the web login (see [docs/finding-your-ids.md](docs/finding-your-ids.md)).
Sign in in the window that opens. The script saves `verdi_state.json`: **treat it like a password.**

### 4. Give the login to the app

1. Copy `verdi_state.json` into the app's configuration folder (for example through the Samba app,
   into the Verdi Token Grabber's folder under `app_config`).
2. In the app's **Configuration** tab, set your Verdi address and tenant, then start the app.
   It moves the file into its private data folder and deletes the copy you dropped in.

### 5. Add the integration

**Settings > Devices & services > Add integration > Verdi (unofficial)**. Accept the notice, enter your
Verdi address and the IDs ([how to find them](docs/finding-your-ids.md)). The app delivers a token
within about 90 seconds; until then the integration shows as "retrying setup".

Options (**Configure** on the integration): poll interval, "Show colleagues' names", and your person
GUID for the "My availability" sensor. When the integration can confirm your person GUID, it
suggests it.

## How the token gets to Home Assistant

The app (or standalone grabber) keeps the current token in memory and posts it to
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

See [docs/standalone-grabber.md](docs/standalone-grabber.md) for running the grabber as a service.

## Security

Please report vulnerabilities privately; see [SECURITY.md](SECURITY.md). Never post tokens,
`verdi_state.json`, HAR files, screenshots of the browser's network tab, IDs or names in issues.

## License

Copyright (C) 2026 jertech and contributors.

This program is free software: you can redistribute it and/or modify it under the terms of the
GNU General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version, with the additional terms in
[ADDITIONAL_TERMS.md](ADDITIONAL_TERMS.md). See [LICENSE](LICENSE) and [NOTICE](NOTICE).
