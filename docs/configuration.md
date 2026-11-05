# Configuration

## Setup

When you add the integration, you enter:

| Field | |
|-------|---|
| Verdi address | The address you open in the browser, for example `https://yourzone.verdi.cloud`. |
| Station ID | Your station. |
| Team group ID | For the team on duty. |
| Vehicle train IDs | The trains to show readiness for, comma-separated. |
| Crew function IDs | The functions for the on-duty sensors, comma-separated. |
| Availability IDs | The availabilities that count in the Personnel sensor, comma-separated. |
| Function calendar ID | Optional, for the roster calendar. |

[Finding your IDs](finding-your-ids.md) explains where to find each one. To change them later, choose
**Reconfigure** on the integration. The station ID must stay the same.

## Options

Press **Configure** on the integration.

**Show colleagues' names.** Off by default. Off: on-duty sensors show *filled* or *open*, and calendar
events show only the function. On: colleagues' names and shift times are shown, and stored in Home
Assistant's history. See [privacy](privacy.md).

### Station

| Option | Default | |
|--------|---------|---|
| Tick | 60 s (at least 30) | How often personnel and vehicles are checked. |
| Tick during an intervention | 30 s (at least 15) | The same, while the station has an intervention or a pre-alert. |
| Fast tick | 15 s (at least 10) | For the lookups in the Fast lane. |
| Vehicles that count for interventions | all | When one of these is on an intervention, the intervention tick applies and statistics are refreshed afterwards. |
| Availabilities that cannot be paged | guessed from the name | While you have one of these, your page isn't checked. |
| Availabilities counted in Personnel | from setup | Statuses Verdi sets when someone is called always count too. |

### Fast lane

Which lookups run on the fast tick instead of the normal tick:

- **Paged** (on by default): checks whether you're paged. Untick it and the Paged sensor and the banner on
  the status page are gone.
- **Vehicles** and **Personnel** (off by default).

### Your own data from the Verdi app

One switch for each: **My availability**, **Pre-alert**, **Garrison**, **My shifts and availability
calendars** and **Statistics**. Pre-alert and garrison are off by default, the others on. A switch that's
off means nothing is fetched and the entities aren't created.

The last two switches change your own status: **Change my status from Home Assistant** and **Add and
remove events in the availability calendar**. Both are off by default. See
[changing your status](changing-status.md).

### Safety intervals

Most lookups only run when something signals a change (see below). The safety interval is the longest
time between two lookups when nothing does.

| Lookup | Default | Minimum |
|--------|---------|---------|
| Readiness | 15 min | 5 min |
| Roster and roster calendar | 30 min | 10 min |
| Team on duty | 6 h | 1 h |
| My availability | 30 min | 5 min |
| Pre-alert and garrison | 60 min | 10 min |
| My calendars | 60 min | 10 min |
| Statistics | 24 h | 1 h |

Statistics are also fetched once a day after midnight and after an intervention.

**Live updates from Verdi** (on by default) keeps one connection open to Verdi's live updates, the same the web
interface uses. Verdi then says when something changes at your station, for you or for your station's vehicles, and the
integration fetches that right away, so changes show within seconds. While the connection is up it polls far less: the
station every 5 minutes instead of every minute (also during an intervention), and your current page every minute
instead of every 15 seconds (every 10 seconds for a minute and a half after a new intervention in your zone). A slower
interval you set yourself is kept. When the connection drops, polling goes back to the normal pace at once. Switch it
off to poll only, as before.

## Language

The integration speaks Dutch, French and English. Any other language gets English.

| What | Language |
|------|----------|
| The status page's own labels (My status, Vehicles, Until …) | Your own Home Assistant language, from your user profile |
| Entity names, options and error messages | Home Assistant's system language (**Settings > System > General**) |
| Verdi's own texts, such as why it refused a status change | Home Assistant's system language: the integration asks Verdi for that language |
| Names of statuses, vehicles, trains and stations | As your zone has them in Verdi, whatever language you use |
| The Verdi login page in the Token Relay app | The app's **Login language** option (`nl`, `fr` or `en`) |

## How often the integration calls Verdi

- **Every tick:** personnel and vehicles. 60 seconds by default, 30 seconds during an intervention.
- **Every fast tick:** your page, while you can be paged. When your availability says you can't be paged,
  this check pauses.
- **Everything else** is fetched when the station data shows a change, at a time Verdi announced (a team
  rotation, a shift change, the end of your availability), or after its safety interval.

When Verdi has trouble or asks to slow down, the integration slows down by itself. It never makes more
than 30 calls a minute per Verdi entry. The options refuse settings that would go above 24 calls a minute
during an intervention.

With live updates connected, a day at the defaults takes roughly a third of the calls: the station's tick and the
current page are polled less, and a change is fetched when Verdi announces it. When the connection is down, the
numbers above apply.

The `sensor.<name>_pace` diagnostic sensor shows the current pace (normal, intervention, live or backoff). It's
disabled by default.

The requests it makes are listed in [endpoints.md](endpoints.md).
