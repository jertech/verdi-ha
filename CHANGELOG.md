# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows
[Semantic Versioning](https://semver.org/). The integration and the app share version
numbers; each entry says which component changed.

## [0.10.1] - unreleased

### Integration
- The status-change entities, actions and options use Verdi's own terms: **Add exception** (was "Set status"),
  **Return to planning** (was "Back to planning"), **New event** (was "Plan a status"), **Remove event** (was
  "Remove a planned status"); the status select is now **Status**. Dutch and French follow Verdi's labels too
  (Uitzondering toevoegen / Ajouter exception, Terug naar planning / Retour au planning, Nieuwe gebeurtenis /
  Nouvel événement, Gebeurtenis verwijderen / Supprimer événement). Existing entities keep their IDs; only new
  setups get IDs from the new names (such as `button.verdi_add_exception`). Action names (`verdi.add_exception`
  and the others) don't change.
- The options' call estimate counts the page only while Paged is ticked in the Fast lane, as the polling does.
- Clearer texts: the Fast lane says what unticking Paged does, "Your own data" mentions the two status switches,
  the calendar field of `verdi.add_event` takes a station or crew function name, a status can also be given by
  ID, and a refused token says nothing was sent and where to look. The calendar field also accepts "General
  planning" in English. French: "Cycle rapide", "Alarmé",
  "Personnes".
- Documentation: requirements, the one-time login steps, what is stored and what diagnostics contain, the
  prerequisites and Verdi's own rules for changing your status, and the standalone relay's settings.

### App
- No changes; the version follows the integration.

## [0.10.0] - 2026-11-01

### Integration
- **Change your own status from Home Assistant** (option "Change my status", off by default): actions to set your
  status now for a duration or unlimited, go back to planning, plan a status for a time slot and remove a planned
  one; a status and a duration select with "Set status" and "Back to planning" buttons. Only Home Assistant
  administrators (and automations) can use them. Your Verdi account needs the rights to change your own status
  and calendar.
- A second option lets the availability calendar add and remove planned statuses and end a running one. Home
  Assistant's calendar view can't tell who uses it, so with this on anyone who can open the calendar can add or
  remove planned statuses and end a running one. Removing a running status from the calendar ends every running
  status, not only that one. An all-day planned status for today can't be added from the calendar; use a time
  slot.
- A status set while a fixed planning applies can be overruled by it; the response of `verdi.add_exception`
  says whether it is active (true), overruled (false) or empty when that couldn't be checked.
- On the days the clocks change, a planned status's duration is the real elapsed time.
- Pressing "Set status" without choosing a status gives an "unknown status" error listing the choices.
- When a change fails, Home Assistant itself may write Verdi's refusal message to its own log (for automations,
  failed actions and button presses started from the UI, and every refused calendar removal); the integration
  never logs it.
- The calendar option needs "Change my status" and "My shifts and availability calendars" on; removing a planned
  status with `verdi.delete_event` needs the calendars switch. A second press or call while a change is still being
  sent is refused.
- Diagnostics show the two options, the two rights and per change how often and how it went (no texts or IDs).
- The page timing record collects the page's field names over the whole page and notes when your confirmation
  first appears.

### App
- No changes; the version follows the integration.

## [0.9.7] - 2026-10-31

### Integration
- The options refuse to remove an availability while Verdi's availability list hasn't loaded yet
  (Verdi unreachable, or no token yet): until then the form can't tell which configured ones are
  the statuses Verdi sets when someone is called. Adding one still works; try again in a few minutes
  to remove one.
- Saving the options keeps the configured availabilities in their order; new ones are added at the
  end. A save that changes nothing no longer reloads the integration.
- A test covers a failing later page of the full availability list.

### App
- No changes; the version follows the integration.

## [0.9.6] - 2026-10-31

### Integration
- Ready for the Home Assistant Marketplace (2026.11) and HACS: the README explains installing through
  **Settings > Marketplace** or HACS, with a button that opens the repository in your Home Assistant
  and one that starts the setup.
- `strings.json` is no longer shipped: custom integrations use the files in `translations/`.
- `hacs.json` drops the `render_readme` key, which the Marketplace no longer uses.
- The HACS and hassfest checks also run every night.

### App
- No changes; the version follows the integration.

## [0.9.5] - 2026-10-31

First public release.

### Integration
- The statuses Verdi sets when someone is called are found automatically (from the station's full
  availability list, read on start, retried on failure) and are always requested and counted in
  Personnel, whether or not they are selected.
- The options list only the availabilities people choose themselves, by name. Call statuses already
  in your settings are kept when you save.
- The station-dashboard suggestions from 0.9.3 are removed: the names now come from Verdi directly.

### App
- No changes; the version follows the integration.

## [0.9.4] - not published

### Integration
- The options read the station's availability names once per form, also when the form is shown again
  after an error.
- Clearer wording in the options for availabilities that aren't in the plannable list (en, nl, fr).

### App
- No changes; the version follows the integration.

## [0.9.3] - not published

### Integration
- The options name every availability they can. The others show a short ID, marked ★ when a station
  dashboard shows them, and you can paste an availability ID. The options say how many availabilities
  a station dashboard shows that aren't selected: these usually include the statuses people get when
  they're called, and without them called people drop out of Personnel. Reading the dashboards happens
  only while the options are open.
- Setup and Reconfigure refuse values that aren't Verdi IDs.
- The timing log saves only when a failing update actually cleared a record, and drops saved records
  without an opening time.

### App
- No changes; the version follows the integration.

## [0.9.2] - not published

### Integration
- The Paged sensor reads the page's station, crew function, vehicle, incident and your confirmation
  under the names Verdi uses; four of them used to stay empty. Every attribute is plain text, so no
  identifier can reach the sensor's attributes.
- Paged no longer stays on when your availability turns non-pageable during a page: the page is
  polled until it ends, then paging pauses.
- When you are paged, your own availability and pre-alert are refreshed at once and your statistics
  about two minutes later.
- Diagnostics show the times of your last ten pages and of the station's last ten interventions
  (when the watched vehicles and the people on intervention changed). They are kept between restarts
  in Home Assistant's storage and removed with the entry.

### App
- Playwright 1.64.1.

## [0.9.1] - not published

### Integration
- Diagnostics now redact the watched-vehicles option. The vehicle IDs chosen under "watched vehicles"
  were printed in clear in a downloaded diagnostics report; they are now redacted like every other
  identifier.
- Diagnostics list the fast lane's schedule (calls today, last fetch, next due) next to the station's
  and your own, so lookups moved to the fast lane stay visible.

### App
- No changes; the version follows the integration.

## [0.9.0] - not published

### Integration
- New **Paged** binary sensor and a **fast lane**: while you are pageable, your current page is
  polled on a short interval instead of the normal one.
- New options `fast_interval` and `fast_lane`: the page is always on the fast lane, and you can
  optionally add vehicles and personnel. Watched vehicles on the fast lane refresh quickly.
- Pageability is decided from your availability. The `non_pageable` option now offers the real
  per-station availability names to pick from.
- New diagnostic **Pace** sensor (normal / intervention / backoff), disabled by default.
- The options screen estimates the steady request rate and refuses a combination that would
  exceed 24 requests per minute. The available ranges already stay within that limit, so this is
  a guard rail.
- After a restart, your statistics sensors keep their last value and the personal calendars stay
  available during the first-fetch delay, instead of briefly reading "no longer provided" or
  unavailable.
- Fixed: `update_entity` on one entity no longer narrows a concurrent full refresh.
- Fixed: your roster "mine" flags now fill in correctly when your person id resolves late.
- Documentation: an optional native Remote Calendar subscription.
- Internal cleanup.

### App
- No changes; the version follows the integration.

## [0.8.2] - not published

### Integration
- Your own availability, pre-alert, garrison and intervention are now seen in the personnel list
  whatever your availability. Personnel is requested with all of the station's availabilities, so
  your line is there even when your availability isn't one of the configured ones (such as "not
  available"); before, your availability was then fetched separately on every tick. The personnel
  sensor still counts only the configured availabilities.
- The availabilities are listed by name in the options (Station), so you no longer need their IDs;
  configured IDs the list doesn't have stay selectable.
- New read: the station's availability list (`domaindata/person/availabilities/displayitems`), once
  per load of the integration.

### App
- No changes; the version follows the integration.

## [0.8.1] - not published

### Integration
- While Verdi has trouble (busy, errors, timeouts), every call waits: a run stops at the first
  such error, and the backoff (and any Retry-After) now also holds calendar views, "Update entity",
  your own data and the person lookup. A setup during an outage no longer waits for each call's
  timeout. One lookup that keeps failing no longer slows the whole station down; it has its own retry.
- A setup while Verdi asked to wait, or at the 30 calls a minute, is tried again later instead of
  loading without the station's entities.
- A change signal that arrives while the same lookup is being fetched is no longer lost.
- Personnel and vehicles are no longer fetched twice in a row after a failure.

### App
- No changes; the version follows the integration.

## [0.8.0] - not published

### Integration
- Each lookup is fetched only when it's due, which cuts the load on Verdi by more than half:
  - personnel and vehicles every tick (default 60 s, at least 30 s; was 120 s), and every 30 s
    (at least 15 s) while a vehicle or a person of your station is on an intervention or a pre-alert;
  - readiness when personnel or vehicles changed, team on duty at its rotation time, roster and
    roster calendar at their next shift change;
  - your availability when your own line in the personnel list changes or your availability ends,
    pre-alert and garrison when your flags there change, your calendars when your availability or
    your roster shifts change, statistics after an intervention and once a day between 00:05 and 01:05;
  - every lookup also after a safety interval (options).
- New options, in sections: the tick during an intervention, the vehicles that count for
  interventions, one switch per kind of your own data, and the safety intervals.
- Pre-alert and garrison are now **off by default**, also for existing installs; switch them on
  in the options if your zone uses them. Existing entries are migrated (config entry version 4);
  intervals still on an old default move to the new one.
- A short glitch where Verdi rejects the token no longer asks you to sign in again: that only
  happens when it lasts two minutes. While Verdi has trouble (busy, errors, timeouts), polling
  slows down to at most every 5 minutes and honours Retry-After; at most 30 calls a minute.
- The roster calendar's current shift no longer freezes after startup; calendar views are kept
  in memory for 5 minutes.
- "Update entity" on a Verdi entity fetches only that entity's data.
- Diagnostics show per lookup how often and why it ran.

### App
- No changes; the version follows the integration.

## [0.7.0] - not published

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

## [0.6.0] - not published

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

## [0.5.6] - not published

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

## [0.5.5] - not published

### App
- The French option texts load again: the Supervisor could not read `translations/fr.yaml`
  (an unquoted `: ` in the Tenant description). A test now parses every app YAML file.
- Stops cleanly when the Supervisor stops or updates it, instead of being killed after 10 seconds
  (exit code 137).

## [0.5.4] - not published

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

## [0.5.3] - not published

### App
- The setup docs name the Samba share correctly: `apps_configs` (0.5.2 said `app_config`).

### Repository
- Test: no person is suggested when Verdi returns an empty or missing `personGuid`.

## [0.5.2] - not published

### App
- The setup docs name the app's configuration folder correctly (`app_config`).

### Repository
- `scripts/draw_icon.py` draws the integration and app icons; the committed icons are its output
  (no visible change).

## [0.5.1] - not published

### App
- Uses the full Chromium build for the headless login instead of the headless shell.
- When a headless login does not finish, the log says on which page (host and path only) it
  stopped.

## [0.5.0] - not published

First release (not published).

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

[0.10.1]: https://github.com/jertech/verdi-ha/compare/v0.10.0...HEAD
[0.10.0]: https://github.com/jertech/verdi-ha/releases/tag/v0.10.0
[0.9.7]: https://github.com/jertech/verdi-ha/releases/tag/v0.9.7
[0.9.6]: https://github.com/jertech/verdi-ha/releases/tag/v0.9.6
[0.9.5]: https://github.com/jertech/verdi-ha/releases/tag/v0.9.5
