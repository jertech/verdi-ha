# SPDX-License-Identifier: GPL-3.0-or-later
"""The status page's settings: stored per user, station and width."""

from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.helpers.storage import Store, get_internal_store_manager
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.verdi.const import DOMAIN
from custom_components.verdi.page_settings import DATA, STORE_KEY, PageSettings
from tests.conftest import setup_with_token

BORD = {"preset": "bord", "changes": {}}
LIST_VIEW = {"preset": "overzicht", "changes": {"blocks": {"vehicles": {"view": "list"}}}}


async def ask(client, **message) -> dict:
    await client.send_json_auto_id(message)
    return await client.receive_json()


async def save(client, entry_id: str, **sets) -> dict:
    return await ask(client, type="verdi/save_page_settings", entry_id=entry_id, **sets)


async def section(client) -> dict:
    return (await ask(client, type="verdi/status_page"))["result"]["sections"][0]


def stored(data) -> dict:
    return {"version": 1, "key": STORE_KEY, "data": data}


async def test_a_new_user_has_no_settings(hass, config_entry, mock_api, hass_ws_client):
    await setup_with_token(hass, config_entry)
    found = await section(await hass_ws_client(hass))
    assert found["entry_id"] == config_entry.entry_id
    assert found["settings"] == {}


async def test_saved_settings_come_back(hass, config_entry, mock_api, hass_ws_client):
    await setup_with_token(hass, config_entry)
    client = await hass_ws_client(hass)
    assert (await save(client, config_entry.entry_id, wide=BORD))["success"]
    assert (await section(client))["settings"] == {"wide": BORD}


async def test_saving_one_set_keeps_the_other(hass, config_entry, mock_api, hass_ws_client):
    await setup_with_token(hass, config_entry)
    client = await hass_ws_client(hass)
    await save(client, config_entry.entry_id, wide=BORD)
    await save(client, config_entry.entry_id, phone=LIST_VIEW)
    assert (await section(client))["settings"] == {"wide": BORD, "phone": LIST_VIEW}


async def test_a_non_admin_saves_and_sees_only_their_own(
    hass, config_entry, mock_api, hass_ws_client, hass_read_only_access_token
):
    await setup_with_token(hass, config_entry)
    await save(await hass_ws_client(hass), config_entry.entry_id, wide=BORD)
    reader = await hass_ws_client(hass, hass_read_only_access_token)
    assert (await section(reader))["settings"] == {}
    assert (await save(reader, config_entry.entry_id, wide=LIST_VIEW))["success"]
    assert (await section(reader))["settings"] == {"wide": LIST_VIEW}
    assert (await section(await hass_ws_client(hass)))["settings"] == {"wide": BORD}


BANNER_OFF = {"preset": "overzicht", "changes": {"banner": False}}


async def test_the_banner_switch_is_stored(hass, config_entry, mock_api, hass_ws_client):
    await setup_with_token(hass, config_entry)
    client = await hass_ws_client(hass)
    assert (await save(client, config_entry.entry_id, phone=BANNER_OFF))["success"]
    assert (await section(client))["settings"] == {"phone": BANNER_OFF}


@pytest.mark.parametrize(
    "bad",
    [
        {"preset": "aangepast", "changes": {}},
        {"preset": "bord"},
        {"preset": "overzicht", "changes": {"banner": "no"}},
        {"preset": "bord", "changes": {"blocks": {"map": {"shown": False}}}},
        {"preset": "bord", "changes": {"blocks": {"vehicles": {"place": "middle"}}}},
        {"preset": "bord", "changes": {"blocks": {"vehicles": {"view": "chips"}}}},
        {"preset": "bord", "changes": {"blocks": {"myStatus": {"view": "tiles"}}}},
        {"preset": "bord", "changes": {"order": ["vehicles"]}},
        {
            "preset": "bord",
            "changes": {"order": ["vehicles", "vehicles", "readiness", "personnel", "statistics"]},
        },
    ],
)
async def test_bad_settings_are_refused(hass, config_entry, mock_api, hass_ws_client, bad):
    await setup_with_token(hass, config_entry)
    client = await hass_ws_client(hass)
    answer = await save(client, config_entry.entry_id, wide=bad)
    assert answer["error"]["code"] == "invalid_format"
    assert (await section(client))["settings"] == {}


async def test_an_unknown_station_is_refused(hass, config_entry, mock_api, hass_ws_client):
    await setup_with_token(hass, config_entry)
    answer = await save(await hass_ws_client(hass), "gone", wide=BORD)
    assert answer["error"]["code"] == "not_found"


async def test_a_store_that_cant_load_gives_a_working_page(
    hass, config_entry, mock_api, hass_storage, hass_ws_client
):
    hass_storage[STORE_KEY] = {"version": 99, "key": STORE_KEY, "data": {}}
    await setup_with_token(hass, config_entry)
    assert (await section(await hass_ws_client(hass)))["settings"] == {}


@pytest.mark.parametrize(
    "file",
    [
        stored(["x"]),
        stored("x"),
        stored({"users": "x"}),
        stored({"users": ["x"]}),
        {"version": 1, "key": STORE_KEY},
        {"key": STORE_KEY, "data": {}},
        ["x"],
        {"version": 0, "key": STORE_KEY, "data": {}},
        {"version": "1", "key": STORE_KEY, "data": {}},
    ],
)
async def test_a_file_of_the_wrong_shape_gives_a_working_page(
    hass, config_entry, mock_api, hass_storage, hass_ws_client, file, caplog
):
    hass_storage[STORE_KEY] = file
    await setup_with_token(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert "page settings" in caplog.text
    client = await hass_ws_client(hass)
    assert (await section(client))["settings"] == {}
    assert (await save(client, config_entry.entry_id, wide=BORD))["success"]
    assert (await section(client))["settings"] == {"wide": BORD}


@pytest.mark.parametrize(
    "content",
    [
        '["x"]',
        "7",
        "null",
        '{"version": 1, "key": "verdi.page_settings"}',
        '{"key": "verdi.page_settings", "data": {}}',
        '{"version": "1", "key": "verdi.page_settings", "data": {}}',
        '{"version": 0, "key": "verdi.page_settings", "data": {}}',
    ],
)
async def test_a_real_file_of_the_wrong_shape_loads_as_empty(hass, tmp_path, content, caplog):
    """hass_storage checks a file's keys itself, so this one goes through Store's own reading."""
    hass.config.config_dir = str(tmp_path)
    (tmp_path / ".storage").mkdir()
    (tmp_path / ".storage" / STORE_KEY).write_text(content)
    get_internal_store_manager(hass).async_invalidate(STORE_KEY)
    settings = PageSettings(hass)
    with patch.object(Store, "_async_load", Store._async_load_data):
        await settings.async_load()
    assert settings.users == {}
    assert "page settings" in caplog.text


@pytest.mark.parametrize(
    ("damage", "kept"),
    [
        ("user", {"wide": BORD}),
        ("own user", {}),
        ("station", {"wide": BORD}),
        ("own station", {}),
        ("set", {"phone": LIST_VIEW}),
    ],
)
async def test_only_the_part_of_the_wrong_shape_is_dropped(
    hass, config_entry, mock_api, hass_storage, hass_ws_client, hass_admin_user, damage, kept
):
    me, entry = hass_admin_user.id, config_entry.entry_id
    users = {
        "user": {"someone": "x", me: {entry: {"wide": BORD}}},
        "own user": {me: "x"},
        "station": {me: {"another": "x", entry: {"wide": BORD}}},
        "own station": {me: {entry: "x"}},
        "set": {me: {entry: {"wide": "x", "phone": LIST_VIEW}}},
    }
    hass_storage[STORE_KEY] = stored({"users": users[damage]})
    await setup_with_token(hass, config_entry)
    client = await hass_ws_client(hass)
    assert (await section(client))["settings"] == kept
    assert (await save(client, entry, wide=LIST_VIEW))["success"]
    assert (await section(client))["settings"] == {**kept, "wide": LIST_VIEW}
    assert await hass.config_entries.async_remove(entry)
    await hass.async_block_till_done()
    assert hass.data[DATA].users == {}


async def test_reading_drops_the_wrong_shape_too(hass):
    settings = PageSettings(hass)
    settings.users = {"a": "x", "b": {"e": "x"}, "c": {"e": {"wide": "x", "phone": BORD}}}
    assert settings.read("a", "e") == {}
    assert settings.read("b", "e") == {}
    assert settings.read("c", "e") == {"phone": BORD}
    assert settings.read(None, "e") == {}


async def test_stored_settings_survive_a_restart(hass, config_entry, mock_api, hass_storage, hass_ws_client):
    await setup_with_token(hass, config_entry)
    await save(await hass_ws_client(hass), config_entry.entry_id, wide=BORD)
    await hass.async_block_till_done()
    assert hass_storage[STORE_KEY]["version"] == 1
    restarted = PageSettings(hass)
    await restarted.async_load()
    assert restarted.users == hass.data[DATA].users != {}


async def test_removing_a_station_removes_its_settings(
    hass, config_entry, mock_api, hass_ws_client, hass_storage
):
    await setup_with_token(hass, config_entry)
    await save(await hass_ws_client(hass), config_entry.entry_id, wide=BORD)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[DATA].users == {}
    assert STORE_KEY not in hass_storage


def disabled_station(hass, unique_id: str) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, version=4, unique_id=unique_id, disabled_by=ConfigEntryDisabler.USER
    )
    entry.add_to_hass(hass)
    return entry


async def test_removing_a_disabled_station_cleans_the_file(hass, hass_storage, caplog):
    """With only disabled entries HA never sets the domain up, so there are no settings in memory."""
    gone, stays = disabled_station(hass, "station-1"), disabled_station(hass, "station-2")
    hass_storage[STORE_KEY] = stored(
        {"users": {"u": {gone.entry_id: {"wide": BORD}, stays.entry_id: {"phone": BORD}}}}
    )
    assert DATA not in hass.data
    assert await hass.config_entries.async_remove(gone.entry_id)
    await hass.async_block_till_done()
    assert "Error calling entry remove callback" not in caplog.text
    assert hass_storage[STORE_KEY]["data"] == {"users": {"u": {stays.entry_id: {"phone": BORD}}}}


async def test_removing_the_last_station_while_disabled_deletes_the_file(hass, hass_storage, caplog):
    entry = disabled_station(hass, "station-1")
    hass_storage[STORE_KEY] = stored({"users": {"u": {entry.entry_id: {"wide": BORD}}}})
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert "Error calling entry remove callback" not in caplog.text
    assert STORE_KEY not in hass_storage
