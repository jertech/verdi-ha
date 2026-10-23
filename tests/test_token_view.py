# SPDX-License-Identifier: GPL-3.0-or-later
"""POST /api/verdi/token: admin-only, write-only, validated, never echoes or logs."""

import logging

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.verdi.const import CONF_ACCOUNT_SUB, DOMAIN
from custom_components.verdi.token import accept_token, get_store
from tests.conftest import DATA, SUB, make_token, setup_with_token

URL = "/api/verdi/token"


@pytest.fixture
async def client(hass: HomeAssistant, hass_client):
    # Components with HTTP views must exist before the test client freezes the router.
    for component in (DOMAIN, "calendar", "diagnostics"):
        assert await async_setup_component(hass, component, {})
    return await hass_client()


async def _post(client, body=None, **kwargs):
    resp = await client.post(URL, json=body, **kwargs)
    return resp.status, await resp.json()


async def test_requires_admin(hass, hass_client, hass_read_only_access_token, config_entry):
    assert await async_setup_component(hass, DOMAIN, {})
    config_entry.add_to_hass(hass)
    client = await hass_client(hass_read_only_access_token)
    status, body = await _post(client, {"token": make_token()})
    assert (status, body) == (403, {"result": "forbidden"})
    assert config_entry.entry_id not in get_store(hass).tokens


async def test_requires_auth(hass, hass_client_no_auth):
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_client_no_auth()
    resp = await client.post(URL, json={"token": make_token()})
    assert resp.status == 401


@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        {"token": 5},
        {"token": "not-a-jwt"},
        {"token": "a.b.c"},
        {"token": make_token(), "entry_id": 5},
    ],
)
async def test_invalid_request(client, config_entry, hass, body):
    config_entry.add_to_hass(hass)
    status, resp = await _post(client, body)
    assert (status, resp) == (400, {"result": "invalid_request"})


async def test_body_too_large(client, config_entry, hass):
    config_entry.add_to_hass(hass)
    status, resp = await _post(client, {"token": make_token(), "pad": "x" * 20000})
    assert (status, resp) == (400, {"result": "invalid_request"})


async def test_expired(client, config_entry, hass, caplog):
    config_entry.add_to_hass(hass)
    token = make_token(lifetime=30)
    status, resp = await _post(client, {"token": token})
    assert (status, resp) == (400, {"result": "expired"})
    assert "Refused a token push: expired" in caplog.text
    assert token not in caplog.text


async def test_wrong_site(client, config_entry, hass):
    config_entry.add_to_hass(hass)
    status, resp = await _post(client, {"token": make_token(iss="https://other.verdi.example/auth")})
    assert (status, resp) == (409, {"result": "no_matching_entry"})


async def test_first_token_records_sub_and_reloads(client, config_entry, hass, mock_api, caplog):
    caplog.set_level(logging.DEBUG)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    token = make_token()
    status, resp = await _post(client, {"token": token})
    await hass.async_block_till_done()
    assert (status, resp) == (200, {"result": "ok"})
    assert config_entry.data[CONF_ACCOUNT_SUB] == SUB
    assert config_entry.state is ConfigEntryState.LOADED
    assert "Token for Verdi received, valid until" in caplog.text
    assert token not in caplog.text
    assert token.split(".")[1] not in caplog.text


async def test_routes_by_sub_with_several_entries(client, hass, mock_api):
    other_sub = "99999999-2222-4333-8444-555555555555"
    a = MockConfigEntry(domain=DOMAIN, version=2, unique_id="a", data={**DATA, CONF_ACCOUNT_SUB: SUB})
    b = MockConfigEntry(domain=DOMAIN, version=2, unique_id="b", data={**DATA, CONF_ACCOUNT_SUB: other_sub})
    a.add_to_hass(hass)
    b.add_to_hass(hass)
    status, _ = await _post(client, {"token": make_token(sub=other_sub)})
    assert status == 200
    assert b.entry_id in get_store(hass).tokens and a.entry_id not in get_store(hass).tokens
    status, resp = await _post(client, {"token": make_token(sub="unknown")})
    assert (status, resp) == (409, {"result": "no_matching_entry"})


async def test_unbound_entries_need_entry_id_when_several(client, hass):
    a = MockConfigEntry(domain=DOMAIN, version=2, unique_id="a", data=dict(DATA))
    b = MockConfigEntry(domain=DOMAIN, version=2, unique_id="b", data=dict(DATA))
    a.add_to_hass(hass)
    b.add_to_hass(hass)
    status, _ = await _post(client, {"token": make_token()})
    assert status == 409
    status, _ = await _post(client, {"token": make_token(), "entry_id": b.entry_id})
    assert status == 200
    assert b.data[CONF_ACCOUNT_SUB] == SUB


async def test_entry_id_must_match_stored_sub(client, hass):
    a = MockConfigEntry(
        domain=DOMAIN, version=2, unique_id="a", data={**DATA, CONF_ACCOUNT_SUB: "someone-else"}
    )
    a.add_to_hass(hass)
    status, _ = await _post(client, {"token": make_token(), "entry_id": a.entry_id})
    assert status == 409


async def test_push_swaps_token_in_loaded_entry(client, hass, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    hass.config_entries.async_update_entry(config_entry, data={**config_entry.data, CONF_ACCOUNT_SUB: SUB})
    new = make_token(lifetime=7200)
    status, _ = await _post(client, {"token": new})
    assert status == 200
    assert config_entry.runtime_data.api.token == new


async def test_push_during_reauth_reloads(client, hass, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    assert list(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
    status, _ = await _post(client, {"token": make_token()})
    await hass.async_block_till_done()
    assert status == 200
    assert not list(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
    assert config_entry.state is ConfigEntryState.LOADED


async def test_push_updates_token_expiry_without_a_poll(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    before = hass.states.get("sensor.verdi_token_expires").state
    accept_token(hass, config_entry, make_token(lifetime=7200), None)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.verdi_token_expires").state != before
