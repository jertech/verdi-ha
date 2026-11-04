# Changing your status

With this on, you can change your own status in Verdi from Home Assistant: from a button, from the
status page, or from an automation. It uses Verdi's own terms:

- **Add exception:** a status that starts now and lasts for a set time, or until you return to planning.
- **Return to planning:** ends your running exceptions, so your normal planning applies again.
- **New event:** a status for a time slot in your availability calendar.
- **Remove event:** removes one of your own events.

It only changes your own status and planning, never anyone else's.

## Turn it on

1. On the integration, press **Configure** and open **Your own data from the Verdi app**.
2. Turn on **Change my status from Home Assistant**.
3. For the **Return to planning** button, also turn on **My availability**. For removing events, turn on
   **My shifts and availability calendars**.

Your Verdi account needs the rights to change your own status and your own calendar. Without the status
right, the buttons and the Status select stay unavailable. An action without the right it needs is refused.

## Buttons and selects

| Entity | What it does |
|--------|--------------|
| **Status** (select) | The status for the exception. |
| **Duration** (select) | How long it lasts: 5 minutes to 1 day 1 hour, or unlimited. |
| **Add exception** (button) | Adds the exception with the chosen status and duration. |
| **Return to planning** (button) | Ends your running exceptions. Unavailable while there is none. |

Pick a status before you press **Add exception**. Without one, you get an "unknown status" error that
lists the choices.

## Actions

| Action | Fields | Returns |
|--------|--------|---------|
| `verdi.add_exception` | `status` (required): a status name, as in the Status select. `duration`: `5m` to `1d1h`, or `unlimited`; default `5m`. | `active`: `true` when the exception applies, `false` when a fixed planning overrules it, empty when that couldn't be checked. |
| `verdi.return_to_planning` | none | nothing |
| `verdi.add_event` | `status` (required). `start` and `end` (required): the time slot; the start can't be in the past. `calendar`: the station or crew function name; leave empty for the general planning. | `event_id`: the new event's ID. |
| `verdi.delete_event` | `event_id` (required): from `verdi.add_event` or the availability calendar. | nothing |

All actions also take `config_entry_id`. You only need it when you have more than one Verdi entry.

## Examples

Use the status names of your own zone; they're the choices in the Status select.

**Not available while you're away from home, back to planning when you're home.**

```yaml
automation:
  - alias: "Verdi: not available when I leave home"
    triggers:
      - trigger: zone
        entity_id: person.me
        zone: zone.home
        event: leave
    actions:
      - action: verdi.add_exception
        data:
          status: "Niet beschikbaar"
          duration: unlimited

  - alias: "Verdi: back to planning when I get home"
    triggers:
      - trigger: zone
        entity_id: person.me
        zone: zone.home
        event: enter
    actions:
      - action: verdi.return_to_planning
```

**Plan a time slot, and get a notification if a fixed planning overrules an exception.**

```yaml
script:
  verdi_available_tonight:
    alias: "Verdi: available tonight"
    sequence:
      # Run it before 18:00: an event can't start in the past.
      - action: verdi.add_event
        data:
          status: "Beschikbaar"
          start: "{{ today_at('18:00') }}"
          end: "{{ today_at('23:00') }}"

  verdi_unavailable_for_an_hour:
    alias: "Verdi: unavailable for an hour"
    sequence:
      - action: verdi.add_exception
        data:
          status: "Niet beschikbaar"
          duration: 1h
        response_variable: result
      - if: "{{ result.active == false }}"
        then:
          - action: notify.notify
            data:
              message: "Verdi accepted the exception, but your fixed planning overrules it."
```

## Verdi's rules

Verdi checks every change and refuses one that breaks its rules, with its own message:

- An exception starts the moment you add it. Unless it's unlimited, it must end at least 5 minutes from now.
- An event's end must be after its start.

**A fixed planning can win.** An exception you add while a fixed planning applies can be overruled by that
planning. Verdi accepts the exception, but the planning stays in force. `active` in the response of
`verdi.add_exception` tells you, and your availability sensor always shows what really applies.

On the days the clocks change, an event's duration is the real time that passes.

## Editing from the calendar

**Add and remove events in the availability calendar** is a second switch. It needs **Change my status**
and **My shifts and availability calendars** on. Then you can add and remove events in the
**My availability** calendar in Home Assistant's calendar view.

- The event's title must be a status name.
- An all-day event for today can't be added, because its start (midnight) is already past. Use a time
  slot instead.
- Removing a running exception from the calendar returns you to planning. That ends **every** running
  exception, not only that one.

> **Anyone who can open the calendar can change your status.** Home Assistant's calendar view doesn't tell
> the integration who is using it. With this switch on, any Home Assistant user who can open the calendar
> can add or remove your events and end a running exception.

## Who can use it

Only Home Assistant administrators can press the buttons, change the selects, use the actions and change
the status on the status page. Automations and scripts can too. So an automation you write can be started
by anyone who can trigger it.

Only one change is sent at a time. A second press or call while a change is still on its way is refused.

## When a change fails

Home Assistant may write Verdi's refusal message to its log: for automations, for failed actions and
button presses from the interface, for changes from the status page, and for every refused removal from
the calendar. The integration itself never logs it.
