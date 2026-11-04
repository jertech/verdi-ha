# Remote Calendar

Instead of, or next to, the integration's **My shifts** and **My availability** calendars, you can
subscribe to your Verdi calendar feed with Home Assistant's built-in **Remote Calendar** integration.

How it differs from the integration's calendars:

- you get **one combined calendar**, and you can only read it;
- it refreshes **about once a day** by default;
- it runs only in Remote Calendar, so it doesn't use the Verdi integration's token or its calls to Verdi.

## Set it up

1. Find your **calendar feed link** in the Verdi web app: your personal calendar link.
2. In Home Assistant, add the **Remote Calendar** integration and paste the link.

To refresh on another schedule, turn off **Enable polling for changes** on that calendar and add an
automation that calls the **Update** entity action for it.

## Keep the link private

The feed link works without a login: **anyone who has it can read your planning.** Remote Calendar stores
the link in Home Assistant's configuration, so it also ends up in your backups.

- Treat the link like a password and don't share it.
- Keep your backups encrypted.

The integration's own calendars aren't affected by any of this.
