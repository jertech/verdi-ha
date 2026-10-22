# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows
[Semantic Versioning](https://semver.org/). The integration and the app share version
numbers; each entry says which component changed.

## [0.7.0] - unreleased

### Integration
- Your own data, read with the same token through the read commands of Verdi's mobile app route
  (option "Your own data from the Verdi app", on by default):
  - "My availability" now shows your overall availability with its end time, per station and per
    planning group. It no longer needs your person GUID; the entity and its history stay. Its
    attributes `on_intervention`, `on_pre_alert` and `present` are gone, so update automations
    that use them.
  - Binary sensors "Pre-alert" and "Garrison".
  - "Availability this year" per station (earlier years as attributes) and "Times called" per
    station and service (with the last call).
  - Calendars "My shifts" and "My availability" (availability you set, and exceptions), about a
    month ahead.
- New options: poll intervals for your availability, pre-alert and garrison (default 60 s, at
  least 10 s), your calendars (default 10 min, at least 1 min) and your statistics (default 6 h; statistics also
  refresh just after midnight and two minutes after a vehicle of your station starts or ends an
  intervention).
- The "My person GUID" option is gone; existing entries are migrated (config entry version 3).
- Diagnostics show counts for your own data, never its content.

### App
- No changes; the version follows the integration.

## [0.6.0] - unreleased

### App
- Renamed the app from "Verdi Token Grabber" to "Verdi Token Relay". The name describes it better:
  it signs in with your own account and relays your token to Home Assistant. The add-on slug changed
  from `verdi_token_grabber` to `verdi_token_relay`, and the image from `verdi-ha-token-grabber` to
  `verdi-ha-token-relay`. Because the slug changed, Home Assistant treats this as a new add-on:
  uninstall the old one (this removes its `/data`, including the login state), install the renamed
  one, and seed `verdi_state.json` again.

### Integration
- Wording that referred to the "Token Grabber" now says "Token Relay". Entity IDs and behaviour do
  not change.

## [0.5.6] - unreleased

### Integration
- Dutch and French texts reviewed: clearer wording in setup, reauth, options and error messages.
  In French, on-duty sensors now show "Pourvu" / "Vacant" instead of "Occupé" / "Libre".
- Dutch and French names now match the Verdi web app: Middelentrein / Train des moyens,
  Functie / Fonction, Status / Statut for the availability IDs, Disponibilité de départs,
  Sur intervention, and Personen / Personnes for the personnel sensor. Entity IDs do not change.

### App
- Dutch and French option texts reviewed.

### Docs
- French disclaimer: the liability sentence could be read as "not liable for all damage";
  it now says the authors are liable for no damage, loss or claim, as in the English version.

## [0.5.5] - unreleased

### App
- The French option texts load again: the Supervisor could not read `translations/fr.yaml`
  (an unquoted `: ` in the Tenant description). A test now parses every app YAML file.
- Stops cleanly when the Supervisor stops or updates it, instead of being killed after 10 seconds
  (exit code 137).

## [0.5.4] - unreleased

### Integration
- When the 10-minute wait for the first token ends, an entry that still has none asks for
  reauthentication right away, instead of at Home Assistant's next retry (up to 10 minutes later).
- Clearer reasons when a token is missing: no token within 10 minutes, or the token expired.
- Logs when a failed lookup works again, and when the token view refuses a push (with the reason).
- Debug log (Enable debug logging): token received with its expiry, each poll's duration and item
  counts, and the end of the token wait. Never tokens, names or response content.

### App
- While Home Assistant restarts behind the Supervisor proxy (HTTP 502, 503 or 504), the app retries
  every 10 seconds and logs "not reachable" instead of "refused the token".
- Logs its version at start, "Token delivered to Home Assistant" once per token, how long each login
  took and how many days ago the login state was made, and when a failed login is retried.

## [0.5.3] - unreleased

### App
- The setup docs name the Samba share correctly: `apps_configs` (0.5.2 said `app_config`).

### Repository
- Test: no person is suggested when Verdi returns an empty or missing `personGuid`.

## [0.5.2] - unreleased

### App
- The setup docs name the app's configuration folder correctly (`app_config`).

### Repository
- `scripts/draw_icon.py` draws the integration and app icons; the committed icons are its output
  (no visible change).

## [0.5.1] - unreleased

### App
- Uses the full Chromium build for the headless login instead of the headless shell.
- When a headless login does not finish, the log says on which page (host and path only) it
  stopped.

## [0.5.0] - unreleased

First public release.

### Integration
- Configurable for any Verdi zone; no zone-specific defaults.
- Tokens are delivered by the Token Relay through `POST /api/verdi/token` (administrators only)
  and kept in memory only. The token file and the stored token are removed.
- New option "Show colleagues' names", off by default for new setups. Existing setups keep names.
- Your person GUID is entered as text; the integration suggests it when it can confirm it.
- Minimum poll interval 60 seconds, default 120 seconds.
- Reconfigure flow, repair issue for missing settings, diagnostics without identifiers.
- Translations: English, Dutch, French.
- Removed: the "My intervention" sensor.
- Config entry version 2: existing entries migrate automatically.

### App (Verdi Token Relay)
- Pushes the token to Home Assistant instead of writing a token file; no `/share` access.
- Takes the one-time login state from its own configuration folder and deletes the dropped-in copy.
- Prebuilt images for amd64 and aarch64.
