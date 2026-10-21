# Changelog

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
