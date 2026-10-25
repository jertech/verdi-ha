# SPDX-License-Identifier: GPL-3.0-or-later
"""update_entity on a Verdi entity fetches only that entity's lookup."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.verdi.api import VerdiApi
from custom_components.verdi.coordinator import Lookup, LookupCoordinator
from custom_components.verdi.guard import Guard
from custom_components.verdi.schedule import LookupSchedule
from custom_components.verdi.token import get_store
from tests import responses as r
from tests.conftest import BASE_URL, MidRandom, fake_command, make_token, setup_with_token


def _make(hass, entry, lookups) -> LookupCoordinator:
    entry.add_to_hass(hass)
    get_store(hass).tokens[entry.entry_id] = make_token(lifetime=86400)
    api = VerdiApi(async_get_clientsession(hass), BASE_URL, None)
    return LookupCoordinator(
        hass,
        entry,
        api,
        "test",
        lookups,
        pace=lambda: (60.0, 30.0),
        retry=timedelta(minutes=5),
        keep_on_failure=False,
        guard=Guard(MidRandom()),
        rng=MidRandom(),
    )


@pytest.mark.parametrize(
    ("entity_id", "expected"),
    [
        ("sensor.verdi_team_on_duty_north", ["TeamOnDutyWidgetCommand"]),
        ("sensor.verdi_token_expires", []),
        ("sensor.verdi_my_availability", ["GetPersonCurrentAvailabilityCarouselInformationCommand"]),
    ],
)
async def test_update_entity_fetches_one_lookup(hass: HomeAssistant, config_entry, entity_id, expected):
    calls: list = []
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(r.all_ok(), calls)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        await setup_with_token(hass, config_entry)
        assert await async_setup_component(hass, "homeassistant", {})
        calls.clear()
        await hass.services.async_call(
            "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
        )
    assert [c[1] for c in calls] == expected


async def test_every_entity_lookup_is_in_its_coordinator(hass: HomeAssistant, config_entry, freezer):
    """A lookup key the coordinator doesn't have would make update_entity a silent no-op."""
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(r.all_ok())),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        await setup_with_token(hass, config_entry, options={"pre_alert": True, "garrison": True})
        freezer.tick(timedelta(seconds=330))  # events and statistics are first fetched 60-600 s later
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    entities = [
        entity for platform in async_get_platforms(hass, "verdi") for entity in platform.entities.values()
    ]
    assert {e.lookup for e in entities if e.lookup} >= {
        "availability",
        "pre_alerts",
        "garrison",
        "events",
        "statistics",
    }
    for entity in entities:
        assert entity.lookup is None or entity.lookup in entity.coordinator.lookups, entity.entity_id


def _value(v):
    return AsyncMock(return_value={"v": v})


def _parse(data):
    return data["v"]


async def test_single_lookup_refresh_fetches_only_its_key(hass: HomeAssistant, config_entry):
    """async_refresh_lookup(key) narrows that one run to the requested lookup."""
    a, b = _value(1), _value(2)
    c = _make(
        hass,
        config_entry,
        {
            "availability": Lookup(a, _parse, LookupSchedule()),
            "roster": Lookup(b, _parse, LookupSchedule()),
        },
    )
    await c.async_refresh_lookup("availability")
    assert (a.call_count, b.call_count) == (1, 0)


async def test_overlapping_full_refresh_still_fetches_every_due_lookup(hass: HomeAssistant, config_entry):
    """A full refresh overlapping an in-flight single-lookup refresh must not be narrowed to that key.

    Driven with asyncio tasks and an event gate (no threads) so the overlap is deterministic: the
    single-lookup run holds the run lock while its fetch is paused, and a scheduled/tick refresh
    (_async_refresh, the path a tick takes — it does not take the debounce lock async_refresh does,
    so it really can overlap) is started during that window. The queue is consumed under the lock,
    so the overlapping refresh finds nothing queued and runs a FULL run, fetching the other due lookup.
    """
    gate = asyncio.Event()
    started = asyncio.Event()

    async def blocked_fetch():
        started.set()
        await gate.wait()
        return {"v": 1}

    b = _value(2)
    c = _make(
        hass,
        config_entry,
        {
            "availability": Lookup(blocked_fetch, _parse, LookupSchedule()),
            "roster": Lookup(b, _parse, LookupSchedule()),
        },
    )

    single = asyncio.create_task(c.async_refresh_lookup("availability"))
    await started.wait()  # the single-lookup run now holds the lock, paused inside availability's fetch

    full = asyncio.create_task(c._async_refresh())  # the path a tick takes
    for _ in range(10):  # let the full refresh reach the run lock and block there
        await asyncio.sleep(0)

    gate.set()
    await asyncio.gather(single, full)

    assert b.call_count == 1  # the overlapping full refresh fetched the other due lookup


async def test_coalesced_single_lookups_run_full_and_leave_no_stale_key(
    hass: HomeAssistant, config_entry
):
    """Two single-lookup requests coalesced by the debouncer into one run must not narrow it, and
    must leave nothing queued to narrow a later refresh."""
    a, b, extra = _value(1), _value(2), _value(3)
    c = _make(
        hass,
        config_entry,
        {
            "availability": Lookup(a, _parse, LookupSchedule()),
            "roster": Lookup(b, _parse, LookupSchedule()),
            "extra": Lookup(extra, _parse, LookupSchedule()),
        },
    )
    # Two async_refresh_lookup calls the debouncer coalesced into a single _async_update_data run.
    c._only_keys = ["availability", "roster"]
    await c._async_update_data()
    assert c._only_keys == []  # the queue was drained, no stale key left behind
    assert (a.call_count, b.call_count, extra.call_count) == (1, 1, 1)  # a full run, not narrowed
