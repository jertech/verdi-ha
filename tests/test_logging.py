# SPDX-License-Identifier: GPL-3.0-or-later
"""What the integration logs: state changes once, details at debug, never tokens or names.

Home Assistant itself logs an authentication failure once, with our exception message as the
reason, so these tests check that the reason is specific rather than adding log lines.
"""

import logging
import time
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.verdi.api import VerdiAuthError, VerdiError
from custom_components.verdi.token import get_store
from tests import responses as r
from tests.conftest import make_token, setup_with_token


def warnings_with(caplog, text: str) -> int:
    """Records at WARNING or above that mention text (HA adds a DEBUG traceback of its own)."""
    return sum(1 for rec in caplog.records if rec.levelno >= logging.WARNING and text in rec.getMessage())


async def test_no_token_after_grace_warns(hass: HomeAssistant, config_entry, mock_api, caplog):
    config_entry.add_to_hass(hass)
    get_store(hass).started = time.monotonic() - 3600
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert warnings_with(caplog, "No token arrived from the Verdi Token Grabber within 10 minutes") == 1


async def test_expired_token_warns_once(hass: HomeAssistant, config_entry, mock_api, caplog):
    await setup_with_token(hass, config_entry)
    expired = make_token(lifetime=30)
    get_store(hass).tokens[config_entry.entry_id] = expired
    coordinator = config_entry.runtime_data
    await coordinator.async_refresh()
    await coordinator.async_refresh()
    assert warnings_with(caplog, "The Verdi token expired and no new one arrived") == 1
    assert expired not in caplog.text


async def test_rejected_token_warns(hass: HomeAssistant, config_entry, mock_api, caplog):
    await setup_with_token(hass, config_entry)
    with patch("custom_components.verdi.api.VerdiApi.vehicles", side_effect=VerdiAuthError("HTTP 401")):
        await config_entry.runtime_data.async_refresh()
    assert warnings_with(caplog, "Verdi rejected the token") == 1


async def test_lookup_recovery_is_logged(hass: HomeAssistant, config_entry, mock_api, caplog):
    caplog.set_level(logging.INFO)
    await setup_with_token(hass, config_entry)
    coordinator = config_entry.runtime_data
    with patch("custom_components.verdi.api.VerdiApi.vehicles", side_effect=VerdiError("HTTP 500")):
        await coordinator.async_refresh()
    assert "Verdi lookup vehicles failed" in caplog.text
    await coordinator.async_refresh()
    assert caplog.text.count("Verdi lookup vehicles works again") == 1
    await coordinator.async_refresh()
    assert caplog.text.count("Verdi lookup vehicles works again") == 1


async def test_poll_details_at_debug_without_names(hass: HomeAssistant, config_entry, mock_api, caplog):
    caplog.set_level(logging.DEBUG, logger="custom_components.verdi")
    await setup_with_token(hass, config_entry, names=True)
    await config_entry.runtime_data.async_refresh()
    assert "Verdi poll took" in caplog.text
    assert "'vehicles': " in caplog.text
    for name in r.PERSON_NAMES:
        for part in name.split():
            assert part not in caplog.text
