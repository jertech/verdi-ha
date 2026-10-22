# SPDX-License-Identifier: GPL-3.0-or-later
"""With "Show colleagues' names" off, no name reaches states, calendar, diagnostics or logs."""

import json
import logging

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from tests import responses as r
from tests.conftest import BASE_URL, DATA, VERDI, setup_with_token

NAME_PARTS = ("Alex", "Example", "Sam", "Sample", "Robin", "Test")


def _all_state_text(hass: HomeAssistant) -> str:
    return json.dumps(
        [(s.entity_id, s.state, dict(s.attributes)) for s in hass.states.async_all()], default=str
    )


async def _calendar_text(hass, hass_client) -> str:
    client = await hass_client()
    resp = await client.get(
        "/api/calendars/calendar.verdi_roster?start=2099-06-14T00:00:00Z&end=2099-06-17T00:00:00Z"
    )
    assert resp.status == 200
    return await resp.text()


async def test_no_names_anywhere(hass: HomeAssistant, config_entry, mock_api, hass_client, caplog):
    caplog.set_level(logging.DEBUG)
    assert await async_setup_component(hass, "diagnostics", {})
    await setup_with_token(hass, config_entry)
    texts = [_all_state_text(hass), await _calendar_text(hass, hass_client), caplog.text]
    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    texts.append(json.dumps(diag))
    for text in texts:
        for part in NAME_PARTS:
            assert part not in text, part
    assert '"summary":"Officer"' in texts[1]


async def test_names_when_enabled(hass: HomeAssistant, config_entry, mock_api, hass_client):
    await setup_with_token(hass, config_entry, names=True)
    state = hass.states.get("sensor.verdi_on_duty_officer")
    assert state.state == "Sam Sample"
    assert state.attributes["next"] == "Robin Test"
    assert "Officer: Sam Sample" in await _calendar_text(hass, hass_client)
    # Personnel never carries names, even with the toggle on.
    assert "Alex" not in _all_state_text(hass)


async def test_diagnostics_redacts_identifiers(hass: HomeAssistant, config_entry, mock_api, hass_client):
    assert await async_setup_component(hass, "diagnostics", {})
    await setup_with_token(hass, config_entry, names=True)
    diag = json.dumps(await get_diagnostics_for_config_entry(hass, hass_client, config_entry))
    for value in (
        BASE_URL,
        VERDI,
        *[v for v in DATA.values() if isinstance(v, str)],
        "train-1",
        "cf-1",
        "av-1",
    ):
        assert value not in diag, value
    assert "eyJ" not in diag  # no JWT
    for part in (*NAME_PARTS, r.CURRENT_USER["userName"]):
        assert part not in diag


async def test_calendar_feed_link_never_leaves_the_response(
    hass: HomeAssistant, config_entry, mock_api, hass_client, caplog
):
    caplog.set_level(logging.DEBUG)
    assert await async_setup_component(hass, "diagnostics", {})
    await setup_with_token(hass, config_entry)
    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    client = await hass_client()
    resp = await client.get(
        "/api/calendars/calendar.verdi_my_availability?start=2020-01-01T00:00:00Z&end=2030-01-01T00:00:00Z"
    )
    events_data = json.dumps(config_entry.runtime_data.personal.events.data, default=str)
    for text in (_all_state_text(hass), await resp.text(), json.dumps(diag), events_data, caplog.text):
        assert "secret-feed-id" not in text
        assert "calendarURI" not in text
    assert diag["personal"] == {
        "availability": True,
        "pre_alerts": 0,
        "garrison": False,
        "shifts": 2,
        "availability_events": 3,
        "availability_year": 1,
        "times_called": 2,
        "last_update_success": {"fast": True, "events": True, "statistics": True},
    }


async def test_diagnostics_without_personal_data(hass: HomeAssistant, config_entry, mock_api, hass_client):
    assert await async_setup_component(hass, "diagnostics", {})
    await setup_with_token(hass, config_entry, options={"personal_data": False})
    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag["personal"] is None
