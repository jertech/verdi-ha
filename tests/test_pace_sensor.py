# SPDX-License-Identifier: GPL-3.0-or-later
"""The Pace diagnostic sensor: disabled by default, reports the coordinator's pace."""

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.conftest import setup_with_token


async def _enable(hass, config_entry):
    await setup_with_token(hass, config_entry)
    er.async_get(hass).async_update_entity("sensor.verdi_pace", disabled_by=None)
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_pace_sensor_disabled_by_default(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    reg = er.async_get(hass)
    entry = reg.async_get("sensor.verdi_pace")
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_pace_sensor_state_and_attributes(hass: HomeAssistant, config_entry, mock_api):
    await _enable(hass, config_entry)
    coordinator = config_entry.runtime_data
    coordinator.intervention = False
    coordinator.async_update_listeners()
    state = hass.states.get("sensor.verdi_pace")
    assert state.state == "normal"
    assert "fast_lane" in state.attributes
    assert state.attributes["paging_paused"] is False

    coordinator.intervention = True
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.verdi_pace").state == "intervention"
