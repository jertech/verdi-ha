# SPDX-License-Identifier: GPL-3.0-or-later
"""The real live client inside Home Assistant, against the fake hub: setup connects it, a notice
fetches, a dropped connection comes back, and unloading the entry ends it."""

from __future__ import annotations

import asyncio

import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.verdi import live
from custom_components.verdi.const import CONF_BASE_URL, DOMAIN, LIVE_CHANNELS
from custom_components.verdi.token import get_store
from tests import responses as r
from tests.conftest import DATA, fake_command, setup_with_token
from tests.ha import MockConfigEntry
from tests.live_hub import Hub

pytestmark = pytest.mark.usefixtures("socket_enabled")  # the fake hub listens on 127.0.0.1

ENTITY = "binary_sensor.verdi_live_updates"
PERSONNEL = "PersonGetGroupedWidgetsCommand"
OWN_STATION = {
    "type": 1,
    "target": "ReceivePersonAvailabilityChange",
    "arguments": [{"stationId": "station-1"}],
}


@pytest.fixture
async def live_hub(monkeypatch):
    monkeypatch.setattr(live, "LIVE_START_DELAY", (0, 0))
    monkeypatch.setattr(live, "LIVE_BACKOFF", (0.05,))
    hub = Hub(channels=len(LIVE_CHANNELS))
    await hub.start()
    yield hub
    await hub.close()


@pytest.fixture
def entry(live_hub) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        version=4,
        unique_id="station-1",
        title="Verdi",
        data={**DATA, CONF_BASE_URL: live_hub.url()},
        source=SOURCE_USER,
    )


async def until(check, timeout: float = 5.0) -> None:
    async with asyncio.timeout(timeout):
        while not check():
            await asyncio.sleep(0.01)


def _state(hass: HomeAssistant) -> str | None:
    state = hass.states.get(ENTITY)
    return state.state if state else None


async def test_the_real_client_runs_inside_home_assistant(hass: HomeAssistant, entry, live_hub):
    live_hub.script = [
        [("acks",), ("sleep", 0.2), ("send", OWN_STATION), ("sleep", 0.3), ("close",)],
        [("acks",)],
    ]
    calls: list = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("custom_components.verdi.api.VerdiApi.command", fake_command(r.all_ok(), calls))
        mp.setattr("custom_components.verdi.api.VerdiApi.current_user", lambda self: _user())
        await setup_with_token(hass, entry)
        signals = entry.runtime_data.live_updates
        assert signals is not None and signals.client is not None
        await until(lambda: _state(hass) == "on")
        assert live_hub.negotiations == [f"Bearer {get_store(hass).get(entry.entry_id)}"]
        assert entry.runtime_data.pace_name == "live"
        calls.clear()
        await until(lambda: signals.marks["personnel"] == 1)
        await until(lambda: PERSONNEL in [c[1] for c in calls])
        assert (
            entry.runtime_data.lookups["personnel"].schedule.last_reason
            == "live:receivepersonavailabilitychange"
        )
        await until(lambda: signals.client.connects == 2)  # dropped, then back after the backoff
        assert signals.client.ends["closed"] == 1
        assert _state(hass) == "on"
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    running = [t for t in asyncio.all_tasks() if t.get_name() == "verdi live updates" and not t.done()]
    assert running == []  # unloading cancelled the client


async def _user():
    return r.CURRENT_USER
