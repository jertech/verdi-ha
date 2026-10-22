# SPDX-License-Identifier: GPL-3.0-or-later
"""Entities for your own data."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.verdi.api import APP_ROUTE, VerdiError
from tests import responses as r
from tests.conftest import fake_command, setup_with_token

STATS = "AppGetPersonStatisticsCommand"


async def test_my_availability_from_the_app_route(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    state = hass.states.get("sensor.verdi_my_availability")
    assert state.state == "Available 5 min"
    assert state.attributes["stations"] == {"Station North": "Available 5 min"}
    assert state.attributes["planning_groups"] == {"All functions": "Available 5 min"}
    assert state.attributes["garrison_crew"] is False
    assert state.attributes["color"] == "#00ff00"
    assert state.attributes["end"].isoformat().startswith("2026-06-15T23:59:10")
    entity = er.async_get(hass).async_get("sensor.verdi_my_availability")
    assert entity.unique_id == f"{config_entry.entry_id}_my_availability"


async def test_no_personal_sensors_when_off(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry, options={"personal_data": False})
    assert hass.states.get("sensor.verdi_my_availability") is None
    assert hass.states.get("sensor.verdi_times_called_station_north_fire") is None


async def test_statistics_sensors(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    year = hass.states.get("sensor.verdi_availability_this_year_station_north")
    assert year.state == "34.7"
    assert year.attributes["unit_of_measurement"] == "%"
    assert year.attributes["state_class"] == "measurement"
    assert year.attributes["years"] == {"2026": 34.7, "2025": 44.1}
    assert hass.states.get("sensor.verdi_availability_this_year_station_south") is None
    fire = hass.states.get("sensor.verdi_times_called_station_north_fire")
    assert fire.state == "17"
    assert fire.attributes["state_class"] == "total_increasing"
    called = fire.attributes["last_called"]
    assert (called.month, called.day, called.hour) == (6, 15, 12)
    entity_id = "sensor.verdi_times_called_station_north_2deg_ambulance"
    assert hass.states.get(entity_id).state == "16"
    entity = er.async_get(hass).async_get(entity_id)
    assert entity.unique_id == f"{config_entry.entry_id}_times_called_station_north_2_ambulance"


async def test_statistics_sensors_appear_after_a_failed_start(hass: HomeAssistant, config_entry, freezer):
    responses = r.all_ok()
    responses[APP_ROUTE][STATS] = VerdiError("mobile/app/commands: HTTP 500")
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(responses)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        await setup_with_token(hass, config_entry)
        assert hass.states.get("sensor.verdi_times_called_station_north_fire") is None
        responses[APP_ROUTE][STATS] = r.STATISTICS
        freezer.tick(timedelta(minutes=5, seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.verdi_times_called_station_north_fire").state == "17"


PRE, GARRISON = "GetPersonCurrentPreAlertInformationCommand", "GetPersonCurrentGarrisonInformationCommand"


async def test_pre_alert_and_garrison_off(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    assert hass.states.get("binary_sensor.verdi_pre_alert").state == "off"
    assert hass.states.get("binary_sensor.verdi_garrison").state == "off"


async def test_pre_alert_and_garrison_on(hass: HomeAssistant, config_entry):
    responses = r.all_ok()
    responses[APP_ROUTE].update({PRE: r.PRE_ALERTS, GARRISON: r.GARRISON})
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(responses)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        await setup_with_token(hass, config_entry)
    pre = hass.states.get("binary_sensor.verdi_pre_alert")
    assert pre.state == "on"
    assert (pre.attributes["description"], pre.attributes["station"], pre.attributes["function"]) == (
        "Storm watch",
        "Station North",
        "Driver",
    )
    garrison = hass.states.get("binary_sensor.verdi_garrison")
    assert garrison.state == "on"
    assert (garrison.attributes["station"], garrison.attributes["city"]) == ("Station North", "Northville")


async def test_personal_calendars(hass: HomeAssistant, config_entry, hass_client, freezer):
    calls: list = []
    await hass.config.async_set_time_zone("Europe/Brussels")
    real_now = datetime.now(UTC)
    freezer.move_to("2026-06-15T18:00:00+02:00")
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(r.all_ok(), calls)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        await setup_with_token(hass, config_entry)
        assert hass.states.get("calendar.verdi_my_shifts").state == "off"
        assert hass.states.get("calendar.verdi_my_availability").state == "on"
        before = len(calls)
        freezer.move_to(real_now)  # the test client's access token is only valid around now
        client = await hass_client()
        resp = await client.get(
            "/api/calendars/calendar.verdi_my_shifts?start=2026-06-22T00:00:00Z&end=2026-06-24T00:00:00Z"
        )
        shifts = await resp.json()
        resp = await client.get(
            "/api/calendars/calendar.verdi_my_availability?start=2026-06-15T00:00:00Z&end=2026-06-16T00:00:00Z"
        )
        availability = await resp.json()
        assert len(calls) == before  # served from the last poll
    assert [e["summary"] for e in shifts] == ["🚑 Ambulance 1 · Escort", "🚑 Ambulance 1 · Driver"]
    assert shifts[0]["description"] == "Crew"
    assert [e["summary"] for e in availability] == ["Not available", "All 5 min", "Urgent"]
