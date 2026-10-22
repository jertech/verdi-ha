# SPDX-License-Identifier: GPL-3.0-or-later
"""Config, reconfigure, reauth and options flows."""

from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.verdi.api import VerdiAuthError
from custom_components.verdi.const import CONF_ACCOUNT_SUB, DOMAIN
from custom_components.verdi.token import get_store
from tests.conftest import BASE_URL, SUB, make_token, setup_with_token

USER_INPUT = {
    "accept_disclaimer": True,
    "verdi_url": "https://zone.verdi.example/home",
    "station_id": "station-1",
    "team_group_id": "team-1",
    "function_calendar_id": "cal-1",
    "vehicle_train_ids": "train-1, train-2",
    "crew_function_ids": "cf-1",
    "availability_ids": "av-1",
}
VEHICLES = "custom_components.verdi.config_flow.VerdiApi.vehicles"


async def _start(hass):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})


async def test_disclaimer_is_required(hass: HomeAssistant):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, "accept_disclaimer": False}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"accept_disclaimer": "must_accept"}


async def test_user_flow_without_token(hass: HomeAssistant):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["base_url"] == BASE_URL
    assert result["data"]["vehicle_train_ids"] == ["train-1", "train-2"]
    assert "token" not in result["data"] and "accept_disclaimer" not in result["data"]
    assert result["result"].unique_id == "station-1"


async def test_user_flow_with_test_token(hass: HomeAssistant, mock_api):
    token = make_token()
    with patch(VEHICLES, return_value={"result": "Success", "data": []}):
        result = await _start(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**USER_INPUT, "token": f"Bearer {token}"}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ACCOUNT_SUB] == SUB
    assert token not in str(result["data"])
    assert get_store(hass).tokens[result["result"].entry_id] == token


async def test_user_flow_errors(hass: HomeAssistant):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, "verdi_url": "http://plain.example", "station_id": " "}
    )
    assert result["errors"] == {"verdi_url": "invalid_url", "station_id": "required"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, "token": make_token(iss="https://other.example/auth")}
    )
    assert result["errors"] == {"base": "token_wrong_site"}

    with patch(VEHICLES, side_effect=VerdiAuthError("401")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**USER_INPUT, "token": make_token()}
        )
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reconfigure(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    result = await config_entry.start_reconfigure_flow(hass)
    new = {k: v for k, v in USER_INPUT.items() if k != "accept_disclaimer"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**new, "team_group_id": "team-2"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data["team_group_id"] == "team-2"

    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**new, "station_id": "another"}
    )
    assert result["reason"] == "wrong_station"


async def test_reauth_with_pasted_token(hass: HomeAssistant, config_entry, mock_api):
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "no_token"}
    token = make_token()
    with patch(VEHICLES, return_value={"result": "Success", "data": []}):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"token": token})
        await hass.async_block_till_done()
    assert result["reason"] == "reauth_successful"
    assert "token" not in config_entry.data
    assert config_entry.data[CONF_ACCOUNT_SUB] == SUB


async def test_options_suggest_detected_person(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    schema = {str(k): k for k in result["data_schema"].schema}
    assert schema["person_id"].description == {"suggested_value": "me-1"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 60, "show_names": False, "person_id": "me-1"}
    )
    await hass.async_block_till_done()
    assert config_entry.options["scan_interval"] == 60
    assert isinstance(config_entry.options["scan_interval"], int)
    assert hass.states.get("sensor.verdi_my_availability").state == "Available 5 min"


async def test_options_no_suggestion_when_guid_unknown(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    with patch(
        "custom_components.verdi.api.VerdiApi.current_user", return_value={"personGuid": "not-listed"}
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
    schema = {str(k): k for k in result["data_schema"].schema}
    assert schema["person_id"].description == {}


@pytest.mark.parametrize("user", [{"personGuid": ""}, {}])
async def test_options_no_suggestion_without_guid(hass: HomeAssistant, config_entry, mock_api, user):
    await setup_with_token(hass, config_entry)
    with patch("custom_components.verdi.api.VerdiApi.current_user", return_value=user):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
    schema = {str(k): k for k in result["data_schema"].schema}
    assert schema["person_id"].description == {}
