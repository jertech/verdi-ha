# Changelog

The app has its own version number from 1.0.0 on and gets a new one only when the app itself changes.
Before that it followed the integration's version.

## 1.0.4 - 2026-11-26

- When a login page doesn't load (no internet or DNS, or the site is down), the log now says
  `Could not reach <host> (net::ERR_...)`. Before, it said "The login needs interaction" and asked for a new
  one-time login that wasn't needed.

## 1.0.3 - 2026-11-21

- Playwright 1.65.2, with a newer Chromium (159).

## 1.0.2 - 2026-11-20

- Playwright 1.65.1: a security update of the Node.js it uses internally (same Chromium).

## 1.0.1 - 2026-11-20

- Playwright 1.65.0, with a newer Chromium.
- Python 3.15 base image.
- Adds the `libatomic1` library that Playwright 1.65 needs.
- Corrected the explanation of the "Home Assistant is not reachable" log line: it also appears while the
  Verdi integration isn't installed yet.

## 1.0.0 - 2026-11-01

- Own version number; the integration's releases no longer change the app's version. The same program as
  0.9.2.
- Until now the app followed the integration's version, so most of those versions had no app changes:
  0.7.0 to 0.9.1 and 0.9.3 to 0.10.0 had none; 0.9.5 was the first public release (images 0.9.5 to 0.10.1 on
  GHCR); 0.10.1 linked step 3 of the README, explained two more log lines, and corrected a French option text.

## 0.9.2 - not published

- Playwright 1.64.1.

## 0.6.0 - not published

- Renamed from "Verdi Token Grabber" to "Verdi Token Relay"; the slug changed from
  `verdi_token_grabber` to `verdi_token_relay`. Home Assistant treats the renamed app as new:
  uninstall the old one (this removes its `/data`, including the login state), install this one,
  and seed `verdi_state.json` again.

## 0.5.6 - not published

- Dutch and French option texts reviewed.

## 0.5.5 - not published

- The French option texts load again (`translations/fr.yaml` could not be read).
- Stops cleanly when stopped or updated, instead of being killed after 10 seconds.

## 0.5.4 - not published

- While Home Assistant restarts, retries every 10 seconds instead of logging "refused the token".
- Logs its version at start, each delivery once, how long a login took, the age of the login state,
  and when a failed login is retried.

## 0.5.3 - not published

- The setup docs name the Samba share correctly (`apps_configs`).

## 0.5.2 - not published

- The setup docs name the configuration folder correctly (`app_config`).

## 0.5.1 - not published

- Uses the full Chromium build for the headless login instead of the headless shell.
- When a headless login does not finish, the log says on which page it stopped.

## 0.5.0 - not published

- First release (not published). Pushes the token to Home Assistant instead of writing a file, takes the
  login state from the app configuration folder, and no longer maps `/share`.
