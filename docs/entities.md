# Entities

In the entity IDs, `<name>` is the name of your Verdi entry. `<train>`, `<vehicle>` and the other parts are
the names Verdi uses. You can turn most entities on or off in the integration's options
([configuration](configuration.md)).

## Your station

| Entity | What it shows |
|--------|---------------|
| `binary_sensor.<name>_readiness_<train>` | On when the vehicle train is complete. The positions are attributes. |
| `sensor.<name>_<vehicle>` | The vehicle's status. |
| `binary_sensor.<name>_<vehicle>_on_intervention` | On while the vehicle is on an intervention. |
| `sensor.<name>_personnel` | How many people have one of the availabilities you picked in the options. Statuses Verdi sets when someone is called always count. The count per availability and their colours (`availability_colors`) are attributes. |
| `sensor.<name>_team_on_duty_<group>` | The current team. The next team and the rotation time are attributes. |
| `sensor.<name>_on_duty_<function>` | Whether the crew function is filled now: *filled* or *open*. With "Show colleagues' names" on, who fills it. |
| `calendar.<name>_roster` | The shifts of the function calendar. Only with a Function calendar ID. |

**Vehicles Verdi no longer lists.** When Verdi stops listing a vehicle for your station, its entities
are hidden at once and removed a week later. Until then you may still see them in the integration's
entity list.

## You

These come from Verdi's app. Each has its own switch under "Your own data from the Verdi app", except
Paged, which is in the Fast lane.

| Entity | What it shows |
|--------|---------------|
| `sensor.<name>_my_availability` | Your current availability. Its end time, your availability per station and per planning group, and the colours of the availabilities (`availability_colors`) are attributes. |
| `binary_sensor.<name>_paged` | On while you're paged. The station, crew function, vehicle, alarm time, incident, city and your confirmation are attributes. On by default; it disappears when you untick Paged in the Fast lane. |
| `binary_sensor.<name>_pre_alert` | On when you have a pre-alert. Off by default. |
| `binary_sensor.<name>_garrison` | On when you're on garrison. Off by default. |
| `sensor.<name>_availability_this_year_<station>` | Your availability this year at that station, in %. Earlier years are attributes. |
| `sensor.<name>_times_called_<station>_<service>` | How often you were called for that service, with the last call. |
| `calendar.<name>_my_shifts` | Your shifts, about a month ahead. |
| `calendar.<name>_my_availability` | The availability you set and your exceptions, about a month ahead. |

## Changing your status

Only with **Change my status** on. See [changing your status](changing-status.md).

| Entity | What it does |
|--------|--------------|
| `select.<name>_status` | The status for **Add exception**. |
| `select.<name>_duration` | How long the exception lasts. |
| `button.<name>_add_exception` | Adds the exception with the chosen status and duration. |
| `button.<name>_return_to_planning` | Ends your running exceptions. Needs "My availability" on. |

## Diagnostic

| Entity | What it shows |
|--------|---------------|
| `sensor.<name>_token_expires` | When the current token expires. |
| `sensor.<name>_pace` | How fast the integration polls: normal, intervention, live (live updates connected) or backoff. Disabled by default. |
| `binary_sensor.<name>_live_updates` | On while the live updates connection to Verdi is up. Attributes: since when, reconnects today, the last notice, and changes polling found that Verdi hadn't announced. Only with "Live updates from Verdi" on. |
