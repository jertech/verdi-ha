# SPDX-License-Identifier: GPL-3.0-or-later
"""Adding and removing planned statuses from the availability calendar (behind its own switch)."""

import copy
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.calendar import CalendarEntityFeature
from homeassistant.util import dt as dt_util

from custom_components.verdi.api import VerdiApi
from tests import responses as r
from tests.conftest import fake_command, setup_with_token

ON = {"status_changes": True, "calendar_edit": True}


@pytest.fixture
def writes():
    upcoming = copy.deepcopy(r.UPCOMING)
    upcoming["groups"][0]["items"][0]["guid"] = r.guid(5)  # a Single
    responses = r.all_ok()
    responses["mobile/app/commands"]["AppGetUpcomingEventsCommand"] = upcoming
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(responses)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.RIGHTS_USER),
        patch.object(VerdiApi, "event_priorities", AsyncMock(return_value=r.EVENT_PRIORITIES)),
        patch.object(VerdiApi, "person_calendars", AsyncMock(return_value=r.PERSON_CALENDARS)),
        patch.object(VerdiApi, "add_event", AsyncMock(return_value={"guid": r.guid(9)})) as add,
        patch.object(VerdiApi, "delete_event", AsyncMock(return_value={})) as delete,
    ):
        yield add, delete


async def _features(hass, entity_id):
    return hass.states.get(entity_id).attributes.get("supported_features", 0)


async def test_switch_off_keeps_calendars_read_only(hass, config_entry, writes):
    await setup_with_token(hass, config_entry, options={"status_changes": True})
    assert await _features(hass, "calendar.verdi_my_availability") == 0


async def test_switch_on_availability_only(hass, config_entry, writes):
    await setup_with_token(hass, config_entry, options=ON)
    wanted = CalendarEntityFeature.CREATE_EVENT | CalendarEntityFeature.DELETE_EVENT
    assert await _features(hass, "calendar.verdi_my_availability") == wanted
    assert await _features(hass, "calendar.verdi_my_shifts") == 0


async def test_create_and_delete_from_the_view(hass, config_entry, writes, hass_ws_client):
    add, delete = writes
    await setup_with_token(hass, config_entry, options=ON)
    personal = config_entry.runtime_data.personal
    await personal.async_refresh_lookup("events")  # events load after a startup delay; fetch them now
    client = await hass_ws_client(hass)
    start = dt_util.now() + timedelta(hours=3)
    await client.send_json_auto_id({
        "type": "calendar/event/create",
        "entity_id": "calendar.verdi_my_availability",
        "event": {"summary": "urgent", "dtstart": start.isoformat(), "dtend": (start + timedelta(hours=1)).isoformat()},
    })  # fmt: skip
    assert (await client.receive_json())["success"]
    assert add.await_args.args[0]["personAvailability"] == {"guid": "av-2"}
    await client.send_json_auto_id({
        "type": "calendar/event/create",
        "entity_id": "calendar.verdi_my_availability",
        "event": {"summary": "Nope", "dtstart": start.isoformat(), "dtend": (start + timedelta(hours=1)).isoformat()},
    })  # fmt: skip
    assert not (await client.receive_json())["success"]
    assert add.await_count == 1
    await client.send_json_auto_id(
        {"type": "calendar/event/delete", "entity_id": "calendar.verdi_my_availability", "uid": r.guid(5)}
    )
    assert (await client.receive_json())["success"]
    delete.assert_awaited_once()
