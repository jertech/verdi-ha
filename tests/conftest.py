# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared fixtures for the Verdi tests."""

from __future__ import annotations

import base64
import json
import random
import time
from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.verdi.api import APP_ROUTE
from custom_components.verdi.const import (
    CONF_AVAILABILITY_IDS,
    CONF_BASE_URL,
    CONF_CREW_FUNCTION_IDS,
    CONF_FUNCTION_CALENDAR_ID,
    CONF_STATION_ID,
    CONF_TEAM_GROUP_ID,
    CONF_VEHICLE_TRAIN_IDS,
    DOMAIN,
)
from custom_components.verdi.token import get_store
from tests import responses as r

VERDI = "https://zone.verdi.example"


class MidRandom(random.Random):
    """Always the middle of the range, so jitter and delays are predictable in tests."""

    def uniform(self, a: float, b: float) -> float:
        return (a + b) / 2


BASE_URL = f"{VERDI}/verdi-core/api/v1"
SUB = "11111111-2222-4333-8444-555555555555"

DATA = {
    CONF_BASE_URL: BASE_URL,
    CONF_STATION_ID: "station-1",
    CONF_TEAM_GROUP_ID: "team-1",
    CONF_FUNCTION_CALENDAR_ID: "cal-1",
    CONF_VEHICLE_TRAIN_IDS: ["train-1"],
    CONF_CREW_FUNCTION_IDS: ["cf-1"],
    CONF_AVAILABILITY_IDS: ["av-1"],
}


def _b64(obj: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")


def make_token(*, sub: str | None = SUB, iss: str = f"{VERDI}/auth", lifetime: int = 3600) -> str:
    claims = {"iss": iss, "exp": int(time.time()) + lifetime, "client_id": "verdi-web"}
    if sub:
        claims["sub"] = sub
    return f"{_b64({'alg': 'RS256', 'typ': 'at+jwt'})}.{_b64(claims)}.c2lnbmF0dXJl"


def fake_command(responses, calls: list | None = None):
    """Answer from responses[path]; the app route answers per command. An Exception value is raised."""

    async def _command(self, path, body):
        if isinstance(responses, Exception):
            raise responses
        if calls is not None:
            calls.append((path, body.get("command"), body.get("language")))
        value = responses[path]
        if path == APP_ROUTE:
            value = value[body["command"]]
        if isinstance(value, Exception):
            raise value
        return value

    return _command


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id="station-1",
        title="Verdi",
        data=dict(DATA),
        source=SOURCE_USER,
    )


@pytest.fixture
def mock_api():
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(r.all_ok())),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        yield


async def setup_with_token(
    hass: HomeAssistant, entry: MockConfigEntry, names: bool = False, options: dict | None = None
) -> None:
    """Add the entry with a pushed token already in memory, and set it up."""
    entry.add_to_hass(hass)
    if names or options:
        new = {**entry.options, **(options or {})}
        if names:
            new["show_names"] = True
        hass.config_entries.async_update_entry(entry, options=new)
    get_store(hass).tokens[entry.entry_id] = make_token()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
