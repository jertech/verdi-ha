# Token relay

Verdi's login goes through your zone's sign-in with MFA, which Home Assistant can't do by itself. The
**Verdi Token Relay** app does it instead and hands the integration a fresh token.

## How it works

1. You log in once on a PC ([installation, step 3](../README.md#3-one-time-login-on-a-pc)). That saves your
   login in `verdi_state.json`.
2. The app keeps the current token in memory and sends it to Home Assistant every 90 seconds, and right
   away when Home Assistant comes back after a restart.
3. Shortly before a token expires, the app runs the normal web login in a browser without a window. Thanks
   to the saved login, that needs nothing from you.

After a restart, the integration waits up to 10 minutes for a token before it asks you to re-authenticate.

## What the app can do in Home Assistant

The app sends the token to `POST /api/verdi/token` on Home Assistant. That endpoint needs a Home Assistant
**administrator** and only accepts a token; it never gives one back.

The app uses Home Assistant's API access for this (`homeassistant_api`). That technically allows the app
more than this one call, but its code only calls this endpoint.

## When you need to log in again

If the login ever needs you again, for example after a password change, Home Assistant asks you to
re-authenticate:

1. Do the one-time login on a PC again ([step 3](../README.md#3-one-time-login-on-a-pc)).
2. Copy the new `verdi_state.json` into the app's folder ([step 4](../README.md#4-give-the-login-to-the-app)).
3. Restart the app.

The prompt closes by itself when the next token arrives.

## Without Home Assistant OS

Apps need Home Assistant OS. On other installs, run the relay as a container or service:
see [standalone relay](standalone-relay.md).
