# SPDX-License-Identifier: GPL-3.0-or-later
"""The status page's settings: stored per user, station and width."""

import pytest

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


@pytest.mark.parametrize(
    "bad",
    [
        {"preset": "aangepast", "changes": {}},
        {"preset": "bord"},
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
