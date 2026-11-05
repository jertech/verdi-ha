# SPDX-License-Identifier: GPL-3.0-or-later
"""Live updates: the option, the entity, a token push and diagnostics."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.verdi.diagnostics import async_get_config_entry_diagnostics
from custom_components.verdi.token import accept_token
from tests.conftest import make_token, setup_with_token
from tests.test_config_flow import _submit

ENTITY = "binary_sensor.verdi_live_updates"


async def test_entity_follows_the_connection(hass: HomeAssistant, config_entry, mock_api, real_live):
    await setup_with_token(hass, config_entry)
    entry = er.async_get(hass).async_get(ENTITY)
    assert entry is not None
    assert entry.entity_category is EntityCategory.DIAGNOSTIC
    assert entry.disabled_by is None
    state = hass.states.get(ENTITY)
    assert state.state == "off"
    assert state.attributes["device_class"] == BinarySensorDeviceClass.CONNECTIVITY
    assert set(state.attributes) >= {"since", "reconnects_today", "last_event", "unannounced_changes"}
    config_entry.runtime_data.live_updates.state(True)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == "on"


async def test_switching_it_off(hass: HomeAssistant, config_entry, mock_api, real_live):
    await setup_with_token(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    submit = _submit({})
    submit["safety"] = {"live_updates": False}
    await hass.config_entries.options.async_configure(result["flow_id"], submit)
    await hass.async_block_till_done()
    assert config_entry.options["live_updates"] is False
    assert config_entry.runtime_data.live_updates is None
    assert hass.states.get(ENTITY) is None or hass.states.get(ENTITY).state == "unavailable"


async def test_a_token_push_wakes_the_client(hass: HomeAssistant, config_entry, mock_api, real_live):
    await setup_with_token(hass, config_entry)
    live = config_entry.runtime_data.live_updates
    live.client = MagicMock()
    accept_token(hass, config_entry, make_token(), None)
    live.client.token_pushed.assert_called_once()


async def test_diagnostics_hold_no_ids(hass: HomeAssistant, config_entry, mock_api, real_live):
    await setup_with_token(hass, config_entry)
    live = config_entry.runtime_data.live_updates
    live.handle("ReceiveChanged", ["2026-01-01T00:00:00Z", "Vehicle", "v1", []])
    data = await async_get_config_entry_diagnostics(hass, config_entry)
    block = data["live"]
    assert block["events_today"] == {"receivechanged": 1}
    assert block["ticks"]["station"] == config_entry.runtime_data.tick_seconds()
    text = json.dumps(block)
    for secret in ("station-1", "me-1", "v1", make_token()[:20]):
        assert secret not in text
