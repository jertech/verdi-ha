# Changelog

The app has its own version number from 1.0.0 on and gets a new one only when the app itself changes.
Before that it followed the integration's version.

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
