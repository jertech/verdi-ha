# SPDX-License-Identifier: GPL-3.0-or-later
"""StatusWriter: every write passes the same checks, in order, and never retries."""

import asyncio
import logging
import random
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from custom_components.verdi import parse_personal
from custom_components.verdi.api import VerdiAuthError, VerdiRefused, VerdiUnavailable
from custom_components.verdi.guard import Guard
from custom_components.verdi.write import StatusWriter
from tests import responses as r
from tests.responses import guid

STATION = "station-1"


class Person:
    def __init__(self, rights=None, value="me-1"):
        self.value, self.rights = value, rights or {"status": True, "calendar": True}

    async def get(self, *, report=True):
        return self.value


def make(hass, *, options=None, rights=None, events=None, availability=None, personal=True):
    api = MagicMock()
    for name in ("add_exception", "return_to_planning", "delete_event"):
        setattr(api, name, AsyncMock(return_value=dict(r.WRITE_OK)))
    api.add_event = AsyncMock(return_value={"guid": guid(9)})
    api.event_priorities = AsyncMock(return_value=r.EVENT_PRIORITIES)
    api.person_calendars = AsyncMock(return_value=r.PERSON_CALENDARS)
    api.my_availability = AsyncMock(return_value=r.CAROUSEL)
    guard = Guard(random.Random(1))
    for name in ("succeeded", "unavailable", "rejected"):
        setattr(guard, name, MagicMock(side_effect=AssertionError(f"writer called guard.{name}")))
    data = {
        "availability": availability
        if availability is not None
        else parse_personal.my_availability(r.CAROUSEL),
        "events": events if events is not None else parse_personal.upcoming_events(r.UPCOMING),
    }
    p = None
    if personal:
        p = SimpleNamespace(lookups={"availability": 1, "events": 1}, data=data,
                            async_refresh_lookup=AsyncMock())  # fmt: skip
    station = SimpleNamespace(
        api=api,
        guard=guard,
        person=Person(rights),
        availabilities=SimpleNamespace(listed={"av-1": "Available", "av-2": "Urgent"}),
        personal=p,
    )
    entry = SimpleNamespace(
        entry_id="e1",
        data={"station_id": STATION},
        options={"status_changes": True, "calendar_edit": True, **(options or {})},
    )
    return StatusWriter(hass, entry, station), station


async def test_option_off_refuses_without_calls(hass):
    writer, station = make(hass, options={"status_changes": False})
    with pytest.raises(ServiceValidationError) as err:
        await writer.add_exception("Urgent", "5m")
    assert err.value.translation_key == "status_changes_off"
    station.api.add_exception.assert_not_called()


async def test_calendar_path_needs_its_switch(hass):
    writer, _ = make(hass, options={"calendar_edit": False})
    with pytest.raises(ServiceValidationError) as err:
        await writer.calendar_delete("ev-1")
    assert err.value.translation_key == "calendar_edit_off"


async def test_missing_right_refuses(hass):
    writer, station = make(hass, rights={"status": False, "calendar": True})
    with pytest.raises(HomeAssistantError) as err:
        await writer.add_exception("Urgent", "5m")
    assert err.value.translation_key == "no_right"
    station.api.add_exception.assert_not_called()


async def test_add_exception_sends_and_refreshes(hass):
    availability = parse_personal.my_availability(r.CAROUSEL)
    availability["blocks"][0].update({"station_id": STATION, "availability": "Urgent"})
    writer, station = make(hass, availability=availability)
    assert await writer.add_exception("urgent", "unlimited") == {"active": True}
    station.api.add_exception.assert_awaited_once_with("me-1", "av-2", None, STATION, "en")
    refreshed = [c.args[0] for c in station.personal.async_refresh_lookup.await_args_list]
    assert refreshed == ["availability", "events"]
    assert station.guard.calls_last_minute() == 1
    assert writer.diagnostics()["writes"]["add_exception"]["outcome"] == "ok"


async def test_add_exception_overruled_is_not_an_error(hass):
    writer, _ = make(hass)  # the carousel still shows "Available 5 min"
    assert await writer.add_exception("Urgent", "5m") == {"active": False}


async def test_add_exception_without_my_availability_reads_once(hass):
    writer, station = make(hass, personal=False)
    assert await writer.add_exception("Urgent", "5m") == {"active": False}
    station.api.my_availability.assert_awaited_once()


async def test_unknown_status_lists_the_names(hass):
    writer, _ = make(hass)
    with pytest.raises(ServiceValidationError) as err:
        await writer.add_exception("Sleeping", "5m")
    assert err.value.translation_key == "unknown_status"
    assert err.value.translation_placeholders["choices"] == "Available, Urgent"


async def test_lists_not_loaded(hass):
    writer, station = make(hass)
    station.availabilities.listed = None
    with pytest.raises(ServiceValidationError) as err:
        await writer.add_exception("Urgent", "5m")
    assert err.value.translation_key == "lists_not_loaded"


async def test_busy_is_refused_not_queued(hass):
    writer, station = make(hass)
    other, _ = make(hass)  # another entry, same person
    gate = asyncio.Event()

    async def slow(*args):
        await gate.wait()
        return dict(r.WRITE_OK)

    station.api.add_exception.side_effect = slow
    first = hass.async_create_task(writer.add_exception("Urgent", "5m"))
    await asyncio.sleep(0)
    with pytest.raises(HomeAssistantError) as err:
        await other.add_exception("Urgent", "5m")
    assert err.value.translation_key == "busy"
    gate.set()
    await first


async def test_guard_full_sends_nothing(hass):
    writer, station = make(hass)
    station.guard.wait(60)
    with pytest.raises(HomeAssistantError) as err:
        await writer.add_exception("Urgent", "5m")
    assert err.value.translation_key == "verdi_busy"
    station.api.add_exception.assert_not_called()


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (VerdiUnavailable("x", 30, status=429), "verdi_busy"),
        (VerdiUnavailable("x", None, status=503), "outcome_unknown"),
        (VerdiUnavailable("x: timeout"), "outcome_unknown"),
        (VerdiAuthError("x"), "token_refused"),
    ],
)
async def test_errors_map_and_never_retry(hass, error, key):
    writer, station = make(hass)
    station.api.add_exception.side_effect = error
    with pytest.raises(HomeAssistantError) as err:
        await writer.add_exception("Urgent", "5m")
    assert err.value.translation_key == key
    assert station.api.add_exception.await_count == 1
    if key == "verdi_busy":
        assert not station.guard.can_call()
    assert writer.diagnostics()["writes"]["add_exception"]["outcome"] == key


async def test_feedback_never_logged(hass, caplog):
    caplog.set_level(logging.DEBUG)
    writer, station = make(hass)
    station.api.add_exception.side_effect = VerdiRefused("p: refused", "Alex Example is busy")
    with pytest.raises(HomeAssistantError) as err:
        await writer.add_exception("Urgent", "5m")
    assert err.value.translation_key == "verdi_refused"
    assert err.value.translation_placeholders == {"feedback": "Alex Example is busy"}
    assert "Alex" not in caplog.text
    assert "Alex" not in repr(writer.diagnostics())


async def test_return_to_planning_one_command_per_target(hass):
    writer, station = make(hass)
    await writer.return_to_planning()
    sent = [c.args[1:3] for c in station.api.return_to_planning.await_args_list]
    assert sent == [("st-1", None), (None, "pg-1")]  # the station-group block under st-1 is skipped


async def test_return_to_planning_nothing_flagged(hass):
    availability = parse_personal.my_availability(r.CAROUSEL)
    for block in availability["blocks"]:
        block["can_return"] = False
    writer, station = make(hass, availability=availability)
    with pytest.raises(HomeAssistantError) as err:
        await writer.return_to_planning()
    assert err.value.translation_key == "nothing_to_end"
    station.api.return_to_planning.assert_not_called()


async def test_return_to_planning_partly_ended(hass):
    writer, station = make(hass)
    station.api.return_to_planning.side_effect = [dict(r.WRITE_OK), VerdiRefused("p: refused", "no")]
    with pytest.raises(HomeAssistantError) as err:
        await writer.return_to_planning()
    assert err.value.translation_key == "partly_ended"


async def test_add_event_loads_once_and_returns_the_id(hass):
    writer, station = make(hass)
    start = dt_util.utcnow() + timedelta(hours=1)
    assert await writer.add_event("Urgent", start, start + timedelta(minutes=10)) == {"event_id": guid(9)}
    assert await writer.add_event("Urgent", start, start + timedelta(minutes=20), "Station North")
    station.api.event_priorities.assert_awaited_once()
    station.api.person_calendars.assert_awaited_once()
    first, second = (c.args[0] for c in station.api.add_event.await_args_list)
    assert first["personCalendar"] == {"guid": "cal-gen"} and "station" not in first
    assert second["personCalendar"] == {"guid": "cal-st"} and second["station"] == {"guid": "st-1"}
    assert first["eventPriority"] == r.SINGLE_KIND and first["personAvailability"] == {"guid": "av-2"}


@pytest.mark.parametrize(
    ("offset", "length", "key"),
    [
        (-timedelta(hours=1), timedelta(minutes=10), "event_in_past"),
        (timedelta(hours=1), timedelta(0), "end_before_start"),
    ],
)
async def test_add_event_checks_times(hass, offset, length, key):
    writer, station = make(hass)
    start = dt_util.utcnow() + offset
    with pytest.raises(ServiceValidationError) as err:
        await writer.add_event("Urgent", start, start + length)
    assert err.value.translation_key == key
    station.api.add_event.assert_not_called()


async def test_add_event_unknown_calendar(hass):
    writer, _ = make(hass)
    start = dt_util.utcnow() + timedelta(hours=1)
    with pytest.raises(ServiceValidationError) as err:
        await writer.add_event("Urgent", start, start + timedelta(hours=1), "Elsewhere")
    assert err.value.translation_key == "unknown_calendar"
    assert err.value.translation_placeholders["choices"] == "Station North, general"


def _events_with(item_id, kind):
    events = parse_personal.upcoming_events(r.UPCOMING)
    events["availability"][0].update({"id": item_id, "kind": kind})
    return events


async def test_delete_event_own_single(hass):
    writer, station = make(hass, events=_events_with(guid(5), "single"))
    await writer.delete_event(guid(5))
    station.api.delete_event.assert_awaited_once_with(guid(5), "en")


async def test_delete_event_refuses_a_shift_and_unknown_ids(hass):
    events = parse_personal.upcoming_events(r.UPCOMING)
    events["shifts"][0]["id"] = guid(6)
    writer, station = make(hass, events=events)
    for event_id in (guid(6), guid(7), "not-a-guid"):
        with pytest.raises(ServiceValidationError) as err:
            await writer.delete_event(event_id)
        assert err.value.translation_key == "not_own_event"
    station.api.delete_event.assert_not_called()
    refreshed = [c.args[0] for c in station.personal.async_refresh_lookup.await_args_list]
    assert refreshed.count("events") == 2  # one refresh per unknown GUID, none for the non-GUID


async def test_delete_event_needs_events(hass):
    writer, _ = make(hass, personal=False)
    with pytest.raises(ServiceValidationError) as err:
        await writer.delete_event(guid(5))
    assert err.value.translation_key == "needs_events"


async def test_calendar_create_refuses_repeats_and_maps_all_day(hass):
    writer, station = make(hass)
    with pytest.raises(ServiceValidationError) as err:
        await writer.calendar_create(dtstart=dt_util.utcnow(), dtend=dt_util.utcnow(), summary="Urgent",
                                     rrule="FREQ=DAILY")  # fmt: skip
    assert err.value.translation_key == "repeat_not_supported"
    day = (dt_util.now() + timedelta(days=2)).date()
    await writer.calendar_create(dtstart=day, dtend=day + timedelta(days=1), summary="urgent")
    body = station.api.add_event.await_args.args[0]
    assert body["startTime"] == "00:00:00" and body["duration"] == "1.00:00:00"


async def test_calendar_delete_exception_running_over_and_single(hass):
    now = dt_util.utcnow()
    events = parse_personal.upcoming_events(r.UPCOMING)
    running, single = events["availability"][1], events["availability"][0]
    running.update(
        {
            "id": guid(1),
            "kind": "exception",
            "start": now - timedelta(minutes=1),
            "end": now + timedelta(hours=1),
        }
    )
    single.update({"id": guid(2), "kind": "single"})
    events["availability"].append(
        {**running, "id": guid(3), "start": now - timedelta(hours=2), "end": now - timedelta(hours=1)}
    )
    writer, station = make(hass, events=events)
    await writer.calendar_delete(guid(1))
    assert station.api.return_to_planning.await_count == 2
    await writer.calendar_delete(guid(2))
    station.api.delete_event.assert_awaited_once()
    with pytest.raises(ServiceValidationError) as err:
        await writer.calendar_delete(guid(3))
    assert err.value.translation_key == "exception_over"
    with pytest.raises(ServiceValidationError) as err:
        await writer.calendar_delete(guid(4))
    assert err.value.translation_key == "unknown_event"


async def test_require_admin(hass, hass_admin_user, hass_read_only_user):
    from homeassistant.core import Context

    from custom_components.verdi.write import require_admin

    await require_admin(hass, None)
    await require_admin(hass, Context())
    await require_admin(hass, Context(user_id=hass_admin_user.id))
    with pytest.raises(HomeAssistantError) as err:
        await require_admin(hass, Context(user_id=hass_read_only_user.id))
    assert err.value.translation_key == "not_admin"


async def test_setup_creates_the_writer_only_when_on(hass, config_entry, mock_api):
    from tests.conftest import setup_with_token

    await setup_with_token(hass, config_entry, options={"status_changes": True})
    coordinator = config_entry.runtime_data
    assert isinstance(coordinator.writer, StatusWriter)
    assert coordinator.person.rights is not None  # read at setup, though no own lookup is on
    await hass.config_entries.async_unload(config_entry.entry_id)
    hass.config_entries.async_update_entry(
        config_entry, options={**config_entry.options, "status_changes": False}
    )
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.runtime_data.writer is None
