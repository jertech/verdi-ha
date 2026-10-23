# SPDX-License-Identifier: GPL-3.0-or-later
"""Roster calendar: current and next from the station's polls, views cached per range."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from tests import responses as r
from tests.conftest import fake_command, setup_with_token

EVENTS = "planning/functioncalendar/events/commands"
URL = "/api/calendars/calendar.verdi_roster?start=2099-06-14T00:00:00Z&end=2099-06-17T00:00:00Z"


def event(guid: str, start: str, end: str) -> dict:
    return {**r.CALENDAR["events"][0], "guid": guid, "start": start, "end": end}


def patched(responses: dict, calls: list):
    return (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(responses, calls)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    )


async def test_current_event_follows_the_polls(hass: HomeAssistant, config_entry, freezer):
    responses, calls = r.all_ok(), []
    responses[EVENTS] = {
        **r.CALENDAR,
        "events": [event("e1", "2026-06-15T10:00:00Z", "2026-06-15T12:30:00Z")],
    }
    freezer.move_to("2026-06-15T12:00:00+00:00")
    command, user = patched(responses, calls)
    with command, user:
        # A long safety interval, so the refresh below comes from the shift boundary.
        await setup_with_token(hass, config_entry, options={"roster_safety": 120})
        assert hass.states.get("calendar.verdi_roster").state == "on"
        responses[EVENTS] = {
            **r.CALENDAR,
            "events": [event("e2", "2026-06-15T12:30:00Z", "2026-06-15T16:30:00Z")],
        }
        freezer.tick(timedelta(minutes=31, seconds=15))  # boundary 12:30 + 75 s
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    data = config_entry.runtime_data.data["roster_calendar"]
    assert [e["id"] for e in data] == ["e2"]
    assert hass.states.get("calendar.verdi_roster").state == "on"


async def test_views_are_cached_per_range(hass: HomeAssistant, config_entry, hass_client, freezer):
    calls: list = []
    command, user = patched(r.all_ok(), calls)
    with command, user:
        await setup_with_token(hass, config_entry)
        client = await hass_client()  # its access token is valid around the real now: don't move the clock

        def views() -> int:
            return sum(1 for c in calls if c[0] == EVENTS)

        base = views()
        first = await (await client.get(URL)).json()
        await client.get(URL)
        assert views() == base + 1
        await client.get(URL.replace("06-17", "06-18"))
        assert views() == base + 2
        freezer.tick(timedelta(minutes=5, seconds=1))
        await client.get(URL)
        assert views() == base + 3
        for _ in range(30):
            config_entry.runtime_data.guard.record_call()
        resp = await client.get(URL.replace("06-17", "06-19"))
        assert await resp.json() == []
        assert views() == base + 3
    assert [e["summary"] for e in first] == ["Officer"]
