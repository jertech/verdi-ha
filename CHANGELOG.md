# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows
[Semantic Versioning](https://semver.org/). The integration and the app share version
numbers; each entry says which component changed.

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
