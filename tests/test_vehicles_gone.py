"""A vehicle Verdi stopped listing: hidden at once, removed after a week, back in view when listed again."""

from __future__ import annotations

import copy
from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.verdi.api import VerdiError
from custom_components.verdi.const import CONF_FAST_LANE
from custom_components.verdi.panel import status_page
from custom_components.verdi.token import get_store

from . import responses as r
from .conftest import fake_command, make_token, setup_with_token

PATH = "configuration/vehicles/commands"
SENSOR, BINARY = "sensor.verdi_p100", "binary_sensor.verdi_p100_on_intervention"
OTHER = {**r.VEHICLES["data"][0], "guid": "v2", "name": "P200"}


def answers(*vehicles: dict) -> dict:
    data = copy.deepcopy(r.all_ok())
    data[PATH]["data"] = list(vehicles)
    return data


async def reload(hass: HomeAssistant, entry, data, freezer: FrozenDateTimeFactory, days: float = 1) -> None:
    freezer.tick(timedelta(days=days))
    get_store(hass).tokens[entry.entry_id] = make_token()  # the old one expired while the clock moved
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(data)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()


async def start(hass: HomeAssistant, entry, options: dict | None = None) -> er.EntityRegistry:
    with (
        patch(
            "custom_components.verdi.api.VerdiApi.command",
            fake_command(answers(r.VEHICLES["data"][0], OTHER)),
        ),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        await setup_with_token(hass, entry, options=options)
    registry = er.async_get(hass)
    assert registry.async_get(SENSOR).hidden_by is None
    return registry


async def test_gone_vehicle_is_hidden_and_stays_registered(hass, config_entry, freezer):
    registry = await start(hass, config_entry)
    await reload(hass, config_entry, answers(OTHER), freezer)
    for entity_id in (SENSOR, BINARY):
        assert registry.async_get(entity_id).hidden_by is er.RegistryEntryHider.INTEGRATION
    assert registry.async_get("sensor.verdi_p200").hidden_by is None


async def test_the_page_leaves_a_gone_vehicle_out(hass, config_entry, freezer):
    await start(hass, config_entry)
    await reload(hass, config_entry, answers(OTHER), freezer)
    assert status_page(hass)[0]["vehicles"] == ["sensor.verdi_p200"]


async def test_the_page_leaves_out_a_vehicle_you_hid(hass, config_entry, freezer):
    registry = await start(hass, config_entry)
    registry.async_update_entity(SENSOR, hidden_by=er.RegistryEntryHider.USER)
    assert status_page(hass)[0]["vehicles"] == ["sensor.verdi_p200"]


async def test_removed_a_week_after_it_was_first_missed(hass, config_entry, freezer):
    registry = await start(hass, config_entry)
    await reload(hass, config_entry, answers(OTHER), freezer)
    await reload(hass, config_entry, answers(OTHER), freezer, days=6.9)
    assert registry.async_get(SENSOR) is not None
    await reload(hass, config_entry, answers(OTHER), freezer, days=0.2)
    assert registry.async_get(SENSOR) is None
    assert registry.async_get(BINARY) is None
    assert hass.states.get(SENSOR) is None
    assert registry.async_get("sensor.verdi_p200") is not None


async def test_a_listed_vehicle_comes_back_with_a_new_week(hass, config_entry, freezer):
    registry = await start(hass, config_entry)
    both = answers(r.VEHICLES["data"][0], OTHER)
    await reload(hass, config_entry, answers(OTHER), freezer)
    await reload(hass, config_entry, both, freezer, days=6)
    assert registry.async_get(SENSOR).hidden_by is None
    assert hass.states.get(SENSOR).state != "unavailable"
    await reload(hass, config_entry, answers(OTHER), freezer, days=6)
    await reload(hass, config_entry, answers(OTHER), freezer, days=6)
    assert registry.async_get(SENSOR) is not None  # the clock restarted when it came back


async def test_a_vehicle_you_hid_stays_hidden_when_listed(hass, config_entry, freezer):
    registry = await start(hass, config_entry)
    registry.async_update_entity(SENSOR, hidden_by=er.RegistryEntryHider.USER)
    await reload(hass, config_entry, answers(OTHER), freezer)
    assert registry.async_get(SENSOR).hidden_by is er.RegistryEntryHider.USER
    await reload(hass, config_entry, answers(r.VEHICLES["data"][0], OTHER), freezer)
    assert registry.async_get(SENSOR).hidden_by is er.RegistryEntryHider.USER


async def test_a_failed_lookup_or_an_empty_list_changes_nothing(hass, config_entry, freezer):
    registry = await start(hass, config_entry)
    await reload(hass, config_entry, {**r.all_ok(), PATH: VerdiError("down")}, freezer, days=8)
    await reload(hass, config_entry, answers(), freezer, days=8)
    for entity_id in (SENSOR, "sensor.verdi_p200"):
        assert registry.async_get(entity_id).hidden_by is None


async def test_a_gone_vehicle_on_the_fast_lane_is_hidden_too(hass, config_entry, freezer):
    registry = await start(hass, config_entry, {CONF_FAST_LANE: ["vehicles"]})
    await reload(hass, config_entry, answers(OTHER), freezer)
    assert registry.async_get(SENSOR).hidden_by is er.RegistryEntryHider.INTEGRATION
    assert registry.async_get("sensor.verdi_p200").hidden_by is None
