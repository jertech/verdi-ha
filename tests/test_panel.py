# SPDX-License-Identifier: GPL-3.0-or-later
"""The status page: sidebar panel and websocket command."""

import copy
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.verdi.api import VerdiError, VerdiUnavailable
from custom_components.verdi.const import DOMAIN
from custom_components.verdi.panel import _problem, status_page
from custom_components.verdi.token import get_store
from tests import responses as r
from tests.conftest import ALL_OFF, DATA, fake_command, make_token, setup_with_token

ON = {"status_changes": True}
CONTROLS = {
    "status": "select.verdi_status",
    "duration": "select.verdi_duration",
    "back_to_planning": "button.verdi_return_to_planning",
}


def second_entry() -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, version=4, unique_id="station-2", title="Verdi 2", data=dict(DATA))


def panel(hass: HomeAssistant):
    return hass.data.get("frontend_panels", {}).get("verdi")


async def test_panel_settings(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    shown = panel(hass)
    assert shown.sidebar_title == "Verdi (unofficial)"
    assert shown.sidebar_icon == "mdi:fire-truck"
    assert shown.require_admin is False
    assert shown.config["_panel_custom"]["name"] == "verdi-panel"
    assert shown.config["_panel_custom"]["module_url"].startswith("/verdi_static/verdi-panel.js?v=")


async def test_panel_once_with_two_entries(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    await setup_with_token(hass, second_entry())
    assert panel(hass) is not None


async def test_panel_stays_through_a_reload(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    shown = panel(hass)
    assert shown is not None
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert panel(hass) is shown


async def test_panel_goes_with_the_last_entry(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    other = second_entry()
    await setup_with_token(hass, other)
    await hass.config_entries.async_remove(other.entry_id)
    assert panel(hass) is not None
    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert panel(hass) is None


async def test_panel_comes_back_with_a_new_entry(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    await setup_with_token(hass, second_entry())
    assert panel(hass) is not None


async def test_page_file_needs_no_login(hass: HomeAssistant, config_entry, mock_api, hass_client_no_auth):
    await setup_with_token(hass, config_entry)
    client = await hass_client_no_auth()
    resp = await client.get("/verdi_static/verdi-panel.js")
    assert resp.status == 200


async def _sections(hass, client) -> list:
    await client.send_json_auto_id({"type": "verdi/status_page"})
    msg = await client.receive_json()
    assert msg["success"]
    return msg["result"]["sections"]


async def test_command_lists_the_entities(hass: HomeAssistant, config_entry, mock_api, hass_ws_client):
    await setup_with_token(hass, config_entry, options={"pre_alert": True, "garrison": True})
    assert await _sections(hass, await hass_ws_client(hass)) == [
        {
            "title": "Verdi",
            "my_availability": "sensor.verdi_my_availability",
            "pre_alert": "binary_sensor.verdi_pre_alert",
            "garrison": "binary_sensor.verdi_garrison",
            "readiness": ["binary_sensor.verdi_readiness_pump_1"],
            "vehicles": ["sensor.verdi_p100"],
            "personnel": "sensor.verdi_personnel",
            "statistics": [],
            "controls": None,
            "problem": None,
        }
    ]


async def test_command_for_a_non_admin(
    hass: HomeAssistant, config_entry, mock_api, hass_ws_client, hass_read_only_access_token
):
    await setup_with_token(hass, config_entry)
    client = await hass_ws_client(hass, hass_read_only_access_token)
    assert len(await _sections(hass, client)) == 1


async def test_command_gives_a_section_per_entry(hass: HomeAssistant, config_entry, mock_api, hass_ws_client):
    await setup_with_token(hass, config_entry)
    await setup_with_token(hass, second_entry())
    sections = await _sections(hass, await hass_ws_client(hass))
    assert [s["title"] for s in sections] == ["Verdi", "Verdi 2"]


async def test_command_never_picks_the_calendar(hass: HomeAssistant, config_entry, mock_api, hass_ws_client):
    await setup_with_token(hass, config_entry)
    assert hass.states.get("calendar.verdi_my_availability") is not None
    sections = await _sections(hass, await hass_ws_client(hass))
    assert sections[0]["my_availability"].startswith("sensor.")


async def test_command_leaves_out_disabled_entities(
    hass: HomeAssistant, config_entry, mock_api, hass_ws_client
):
    await setup_with_token(hass, config_entry)
    er.async_get(hass).async_update_entity("sensor.verdi_p100", disabled_by=er.RegistryEntryDisabler.USER)
    sections = await _sections(hass, await hass_ws_client(hass))
    assert sections[0]["vehicles"] == []


async def test_command_without_personal_data(hass: HomeAssistant, config_entry, mock_api, hass_ws_client):
    await setup_with_token(hass, config_entry, options=ALL_OFF)
    sections = await _sections(hass, await hass_ws_client(hass))
    assert sections[0]["my_availability"] is None


async def test_command_leaves_out_an_empty_entry(hass: HomeAssistant, config_entry, mock_api, hass_ws_client):
    await setup_with_token(hass, config_entry)
    registry = er.async_get(hass)
    for entity_id in ("sensor.verdi_p100", "sensor.verdi_my_availability", "sensor.verdi_personnel"):
        registry.async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    assert await _sections(hass, await hass_ws_client(hass)) == []


async def test_command_forgets_a_sensor_switched_off_by_the_options(
    hass: HomeAssistant, config_entry, mock_api, hass_ws_client
):
    await setup_with_token(hass, config_entry)
    assert (await _sections(hass, await hass_ws_client(hass)))[0]["my_availability"] is not None
    hass.config_entries.async_update_entry(config_entry, options={**config_entry.options, **ALL_OFF})
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert (await _sections(hass, await hass_ws_client(hass)))[0]["my_availability"] is None


async def test_panel_exists_while_an_entry_waits_for_a_token(hass: HomeAssistant, config_entry, mock_api):
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert panel(hass) is not None


@pytest.mark.parametrize(
    ("path", "key"),
    [
        ("configuration/vehicles/commands", "vehicles"),
        ("configuration/persons/commands", "personnel"),
    ],
)
async def test_rows_stay_when_a_lookup_failed_on_reload(hass: HomeAssistant, config_entry, path, key):
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(r.all_ok())),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        await setup_with_token(hass, config_entry)
        before = status_page(hass)
    assert before[0][key]
    with (
        patch(
            "custom_components.verdi.api.VerdiApi.command",
            fake_command({**r.all_ok(), path: VerdiError("down")}),
        ),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        assert await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()
    assert [{**section, "problem": None} for section in status_page(hass)] == before


async def test_a_waiting_entry_keeps_its_rows(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    before = status_page(hass)
    get_store(hass).tokens.pop(config_entry.entry_id)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert [{**section, "problem": None} for section in status_page(hass)] == before


async def test_controls_for_an_admin(hass: HomeAssistant, config_entry, mock_api, hass_ws_client):
    await setup_with_token(hass, config_entry, options=ON)
    sections = await _sections(hass, await hass_ws_client(hass))
    assert sections[0]["controls"] == {"entry_id": config_entry.entry_id, **CONTROLS}


async def test_no_controls_for_a_non_admin(
    hass: HomeAssistant, config_entry, mock_api, hass_ws_client, hass_read_only_access_token
):
    await setup_with_token(hass, config_entry, options=ON)
    client = await hass_ws_client(hass, hass_read_only_access_token)
    section = (await _sections(hass, client))[0]
    assert section["controls"] is None
    assert section["my_availability"] == "sensor.verdi_my_availability"


async def test_no_controls_with_status_changes_off(
    hass: HomeAssistant, config_entry, mock_api, hass_ws_client
):
    await setup_with_token(hass, config_entry)
    assert (await _sections(hass, await hass_ws_client(hass)))[0]["controls"] is None


@pytest.mark.parametrize("entity_id", ["select.verdi_status", "select.verdi_duration"])
async def test_no_controls_with_a_select_disabled(
    hass: HomeAssistant, config_entry, mock_api, hass_ws_client, entity_id
):
    await setup_with_token(hass, config_entry, options=ON)
    er.async_get(hass).async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    assert (await _sections(hass, await hass_ws_client(hass)))[0]["controls"] is None


async def test_a_hidden_select_still_counts(hass: HomeAssistant, config_entry, mock_api, hass_ws_client):
    await setup_with_token(hass, config_entry, options=ON)
    er.async_get(hass).async_update_entity("select.verdi_status", hidden_by=er.RegistryEntryHider.USER)
    assert (await _sections(hass, await hass_ws_client(hass)))[0]["controls"] is not None


async def test_a_renamed_select_is_still_found(hass: HomeAssistant, config_entry, mock_api, hass_ws_client):
    await setup_with_token(hass, config_entry, options=ON)
    er.async_get(hass).async_update_entity("select.verdi_status", new_entity_id="select.my_choice")
    assert (await _sections(hass, await hass_ws_client(hass)))[0]["controls"]["status"] == "select.my_choice"


async def test_controls_without_the_return_button(
    hass: HomeAssistant, config_entry, mock_api, hass_ws_client
):
    await setup_with_token(hass, config_entry, options=ON)
    er.async_get(hass).async_update_entity(
        "button.verdi_return_to_planning", disabled_by=er.RegistryEntryDisabler.USER
    )
    controls = (await _sections(hass, await hass_ws_client(hass)))[0]["controls"]
    assert controls["back_to_planning"] is None
    assert controls["status"] == "select.verdi_status"


async def test_two_entries_keep_their_own_controls(
    hass: HomeAssistant, config_entry, mock_api, hass_ws_client
):
    await setup_with_token(hass, config_entry, options=ON)
    other = second_entry()
    await setup_with_token(hass, other, options=ON)
    sections = await _sections(hass, await hass_ws_client(hass))
    assert {s["controls"]["entry_id"] for s in sections} == {config_entry.entry_id, other.entry_id}
    assert len({s["controls"]["status"] for s in sections}) == 2


async def test_controls_alone_make_no_section(hass: HomeAssistant, config_entry, mock_api, hass_ws_client):
    await setup_with_token(hass, config_entry, options=ON)
    registry = er.async_get(hass)
    for entity_id in ("sensor.verdi_p100", "sensor.verdi_my_availability", "sensor.verdi_personnel"):
        registry.async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    assert await _sections(hass, await hass_ws_client(hass)) == []


def two_of_each() -> dict:
    """Verdi's order: Z9 before P100, Pump 1 before Aerial. Sorting by name or by entity ID reverses both."""
    answers = copy.deepcopy(r.all_ok())
    vehicles = answers["configuration/vehicles/commands"]["data"]
    vehicles.insert(0, {**vehicles[0], "guid": "v0", "name": "Z9"})
    trains = answers["configuration/readinesses/commands"]["groups"][0]["items"]
    trains.append({**trains[0], "guid": "t2", "title": {"default": "Aerial"}, "trainOrder": 2})
    return answers


async def test_vehicles_and_trains_come_in_verdis_order(hass: HomeAssistant, config_entry, hass_ws_client):
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(two_of_each())),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        await setup_with_token(hass, config_entry)
        section = (await _sections(hass, await hass_ws_client(hass)))[0]
    assert section["vehicles"] == ["sensor.verdi_z9", "sensor.verdi_p100"]
    assert section["readiness"] == [
        "binary_sensor.verdi_readiness_pump_1",
        "binary_sensor.verdi_readiness_aerial",
    ]


async def test_entities_outside_the_answer_go_last(hass: HomeAssistant, config_entry):
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(two_of_each())),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        await setup_with_token(hass, config_entry)
    # P100 alone in the next answer: Z9 keeps its entity, and goes last.
    config_entry.runtime_data.lane("vehicles").data["vehicles"].pop(0)
    assert status_page(hass)[0]["vehicles"] == ["sensor.verdi_p100", "sensor.verdi_z9"]


async def test_statistics_come_with_availability_first(
    hass: HomeAssistant, config_entry, mock_api, hass_ws_client, freezer
):
    await setup_with_token(hass, config_entry)
    freezer.tick(timedelta(seconds=330))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    section = (await _sections(hass, await hass_ws_client(hass)))[0]
    assert section["statistics"] == [
        "sensor.verdi_availability_this_year_station_north",
        "sensor.verdi_times_called_station_north_2deg_ambulance",
        "sensor.verdi_times_called_station_north_fire",
    ]


async def test_hidden_trains_stay_out(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    er.async_get(hass).async_update_entity(
        "binary_sensor.verdi_readiness_pump_1", hidden_by=er.RegistryEntryHider.USER
    )
    assert status_page(hass)[0]["readiness"] == []


async def test_no_tag_entities_by_default(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    section = status_page(hass)[0]
    assert (section["pre_alert"], section["garrison"]) == (None, None)


async def test_positions_keep_verdis_order_through_the_websocket(
    hass: HomeAssistant, config_entry, mock_api, hass_ws_client
):
    await setup_with_token(hass, config_entry)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "get_states"})
    states = (await client.receive_json())["result"]
    train = next(s for s in states if s["entity_id"] == "binary_sensor.verdi_readiness_pump_1")
    assert list(train["attributes"]["positions"]) == ["Driver", "Crew"]


async def test_no_problem_while_all_is_well(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    assert status_page(hass)[0]["problem"] is None


async def test_problem_token_without_a_usable_token(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    get_store(hass).tokens.pop(config_entry.entry_id)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert status_page(hass)[0]["problem"] == "token"


async def test_problem_token_during_reauth(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    assert any(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
    assert status_page(hass)[0]["problem"] == "token"


async def test_problem_verdi_when_setup_failed_despite_a_token(hass: HomeAssistant, config_entry):
    # Not setup_with_token: that helper asserts the entry loaded.
    config_entry.add_to_hass(hass)
    get_store(hass).tokens[config_entry.entry_id] = make_token()
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(VerdiError("down"))),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert _problem(hass, config_entry) == "verdi"


async def test_problem_verdi_when_updates_fail(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    config_entry.runtime_data.last_update_success = False
    assert status_page(hass)[0]["problem"] == "verdi"


@pytest.mark.parametrize(
    ("trouble", "expected"),
    [
        (VerdiUnavailable("down", status=503), "verdi"),
        (VerdiUnavailable("down"), "verdi"),
        (VerdiUnavailable("busy", status=429), "paused"),
        (VerdiUnavailable("busy", retry_after=120, status=503), "paused"),
    ],
)
async def test_problem_after_a_failed_tick(hass: HomeAssistant, config_entry, freezer, trouble, expected):
    failing = {
        **r.all_ok(),
        "configuration/persons/commands": trouble,
        "configuration/vehicles/commands": trouble,
    }
    with patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER):
        with patch("custom_components.verdi.api.VerdiApi.command", fake_command(r.all_ok())):
            await setup_with_token(hass, config_entry)
        with patch("custom_components.verdi.api.VerdiApi.command", fake_command(failing)):
            freezer.tick(timedelta(seconds=120))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
    assert config_entry.runtime_data.guard.backing_off
    assert _problem(hass, config_entry) == expected


async def test_problem_clears_after_a_success(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    guard = config_entry.runtime_data.guard
    guard.level, guard.asked_to_wait = 1, True
    guard.succeeded()
    assert guard.asked_to_wait is False
    assert _problem(hass, config_entry) is None
