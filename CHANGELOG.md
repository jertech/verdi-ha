# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows
[Semantic Versioning](https://semver.org/). The integration and the app share version
numbers; each entry says which component changed.

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
- Tokens are delivered by the Token Grabber through `POST /api/verdi/token` (administrators only)
  and kept in memory only. The token file and the stored token are removed.
- New option "Show colleagues' names", off by default for new setups. Existing setups keep names.
- Your person GUID is entered as text; the integration suggests it when it can confirm it.
- Minimum poll interval 60 seconds, default 120 seconds.
- Reconfigure flow, repair issue for missing settings, diagnostics without identifiers.
- Translations: English, Dutch, French.
- Removed: the "My intervention" sensor.
- Config entry version 2: existing entries migrate automatically.

### App (Verdi Token Grabber)
- Pushes the token to Home Assistant instead of writing a token file; no `/share` access.
- Takes the one-time login state from its own configuration folder and deletes the dropped-in copy.
- Prebuilt images for amd64 and aarch64.
