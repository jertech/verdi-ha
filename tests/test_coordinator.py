# SPDX-License-Identifier: GPL-3.0-or-later
"""LookupCoordinator: failing lookups, keeping earlier values, retrying sooner; interval options."""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.verdi.api import VerdiApi, VerdiAuthError, VerdiError
from custom_components.verdi.const import (
    CONF_EVENTS_INTERVAL,
    CONF_PERSONAL_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_STATISTICS_INTERVAL,
)
from custom_components.verdi.coordinator import LookupCoordinator, interval
from custom_components.verdi.token import get_store
from tests.conftest import BASE_URL, make_token

SIX_HOURS, RETRY = timedelta(hours=6), timedelta(minutes=5)
FAILED = VerdiError("mobile/app/commands: HTTP 500")


def coordinator(hass: HomeAssistant, entry, fetch, **kwargs) -> LookupCoordinator:
    entry.add_to_hass(hass)
    get_store(hass).tokens[entry.entry_id] = make_token()
    api = VerdiApi(async_get_clientsession(hass), BASE_URL, None)
    lookups = {"stats": (fetch, lambda data: data["v"])}
    return LookupCoordinator(hass, entry, api, "test", SIX_HOURS, lookups, **kwargs)


async def test_keeps_previous_value_and_retries_sooner(hass: HomeAssistant, config_entry):
    fetch = AsyncMock(side_effect=[{"v": 1}, FAILED, {"v": 2}])
    c = coordinator(hass, config_entry, fetch, keep_on_failure=True, retry=RETRY)
    await c.async_refresh()
    assert c.data == {"stats": 1}
    assert c.update_interval == SIX_HOURS
    await c.async_refresh()
    assert c.last_update_success
    assert c.data == {"stats": 1}
    assert c.update_interval == RETRY
    await c.async_refresh()
    assert c.data == {"stats": 2}
    assert c.update_interval == SIX_HOURS


async def test_nothing_to_keep_is_a_failure(hass: HomeAssistant, config_entry):
    c = coordinator(hass, config_entry, AsyncMock(side_effect=FAILED), keep_on_failure=True, retry=RETRY)
    await c.async_refresh()
    assert not c.last_update_success
    assert c.update_interval == RETRY


async def test_without_keep_every_lookup_failing_is_a_failure(hass: HomeAssistant, config_entry):
    c = coordinator(hass, config_entry, AsyncMock(side_effect=[{"v": 1}, FAILED]))
    await c.async_refresh()
    await c.async_refresh()
    assert not c.last_update_success
    assert c.update_interval == SIX_HOURS


async def test_rejected_token_asks_for_reauth(hass: HomeAssistant, config_entry):
    c = coordinator(hass, config_entry, AsyncMock(side_effect=VerdiAuthError("x: HTTP 401")))
    with pytest.raises(ConfigEntryAuthFailed):
        await c._async_update_data()


def test_interval_options():
    assert interval({}, CONF_SCAN_INTERVAL) == timedelta(seconds=120)
    assert interval({CONF_SCAN_INTERVAL: 5}, CONF_SCAN_INTERVAL) == timedelta(seconds=60)
    assert interval({}, CONF_PERSONAL_INTERVAL) == timedelta(seconds=60)
    assert interval({CONF_PERSONAL_INTERVAL: 1}, CONF_PERSONAL_INTERVAL) == timedelta(seconds=10)
    assert interval({}, CONF_EVENTS_INTERVAL) == timedelta(minutes=10)
    assert interval({}, CONF_STATISTICS_INTERVAL) == timedelta(hours=6)
    assert interval({CONF_STATISTICS_INTERVAL: 0}, CONF_STATISTICS_INTERVAL) == timedelta(hours=1)
