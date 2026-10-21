# Verdi Token Grabber

> **Unofficial, not affiliated with Cevi or Verdi, not for operational use, uses your own Verdi account and its permissions, use at your own risk.**

This app keeps a Verdi token available to the Verdi (unofficial) integration. It never stores
your password: it reuses the login state of a one-time browser login that you do on a PC.

## Setup

1. Do the one-time login on a PC (see the project README, step 3). This creates `verdi_state.json`.
2. Copy `verdi_state.json` into this app's configuration folder (for example through the Samba
   app's `app_configs` share).
3. Set **Verdi address** and **Tenant** below and start the app.

On start, the app moves the file into its private data folder and deletes the copy you dropped in.

## What it does

- Keeps the current token in memory and posts it to Home Assistant every 90 seconds, and right
  away when Home Assistant comes back after a restart.
- Runs a headless browser login only shortly before the token expires.
- Never writes the token to disk and never prints it.

## Security notes

- `verdi_state.json` is effectively a long-lived login for your account. It is stored in the
  app's data folder, which is included in Home Assistant backups: keep backups encrypted.
- The app uses Home Assistant API access (`homeassistant_api`) for the single call that delivers
  the token. That access technically allows more; the app's code makes only this call.
- No ports, no ingress, no host network, no extra privileges.

## When the log says "The login needs interaction"

Your saved login expired (for example after a password change or a long time unused). Redo the
one-time login on a PC, copy the new `verdi_state.json` into the configuration folder again and
restart the app.

## Options

| Option | Meaning |
|--------|---------|
| Verdi address | `https://yourzone.verdi.cloud` |
| Tenant | Your tenant name (after `tenant:` in the web login) |
| Login language | Language of the login page (`nl`, `fr` or `en`) |
| Config entry ID | Only needed with more than one Verdi entry in Home Assistant |
