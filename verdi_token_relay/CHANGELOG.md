# Changelog

## 0.9.2

- Playwright 1.64.1.

## 0.9.1

- No changes; the version follows the integration.

## 0.9.0

- No changes; the version follows the integration.

## 0.8.2

- No changes; the version follows the integration.

## 0.8.1

- No changes; the version follows the integration.

## 0.8.0

- No changes; the version follows the integration.

## 0.7.0

- No changes; the version follows the integration.

## 0.6.0

- Renamed from "Verdi Token Grabber" to "Verdi Token Relay"; the slug changed from
  `verdi_token_grabber` to `verdi_token_relay`. Home Assistant treats the renamed app as new:
  uninstall the old one (this removes its `/data`, including the login state), install this one,
  and seed `verdi_state.json` again.

## 0.5.6

- Dutch and French option texts reviewed.

## 0.5.5

- The French option texts load again (`translations/fr.yaml` could not be read).
- Stops cleanly when stopped or updated, instead of being killed after 10 seconds.

## 0.5.4

- While Home Assistant restarts, retries every 10 seconds instead of logging "refused the token".
- Logs its version at start, each delivery once, how long a login took, the age of the login state,
  and when a failed login is retried.

## 0.5.3

- The setup docs name the Samba share correctly (`apps_configs`).

## 0.5.2

- The setup docs name the configuration folder correctly (`app_config`).

## 0.5.1

- Uses the full Chromium build for the headless login instead of the headless shell.
- When a headless login does not finish, the log says on which page it stopped.

## 0.5.0

- First public release. Pushes the token to Home Assistant instead of writing a file, takes the
  login state from the app configuration folder, and no longer maps `/share`.
