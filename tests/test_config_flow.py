# SPDX-License-Identifier: GPL-3.0-or-later
"""Config, reconfigure, reauth and options flows."""

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, section

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


def _defaults(schema) -> dict:
    out = {}
    for marker, value in schema.schema.items():
        if isinstance(value, section):
            out[str(marker)] = _defaults(value.schema)
        else:
            out[str(marker)] = marker.default() if callable(marker.default) else None
    return out


async def test_options_form(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry, options={"paged": True})
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    schema = result["data_schema"]
    assert _defaults(schema) == {
        "show_names": False,
        "station": {"scan_interval": 60, "intervention_interval": 30, "watched_vehicles": []},
        "own_data": {
            "my_availability": True,
            "pre_alert": False,
            "garrison": False,
            "my_events": True,
            "statistics": True,
        },
        "safety": {
            "readiness_safety": 15,
            "roster_safety": 30,
            "teams_safety": 6,
            "availability_safety": 30,
            "alerts_safety": 60,
            "events_interval": 60,
            "statistics_interval": 24,
        },
    }
    safety = next(v for k, v in schema.schema.items() if str(k) == "safety")
    assert safety.options["collapsed"] is True
    vehicles = next(v for k, v in schema.schema.items() if str(k) == "station").schema.schema
    selector = next(v for k, v in vehicles.items() if str(k) == "watched_vehicles")
    assert [o["value"] for o in selector.config["options"]] == ["v1"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "show_names": True,
            "station": {"scan_interval": 45.0, "intervention_interval": 15.0, "watched_vehicles": ["v1"]},
            "own_data": {
                "my_availability": True,
                "pre_alert": True,
                "garrison": False,
                "my_events": False,
                "statistics": True,
            },
            "safety": {
                "readiness_safety": 5.0,
                "roster_safety": 10.0,
                "teams_safety": 1.0,
                "availability_safety": 5.0,
                "alerts_safety": 10.0,
                "events_interval": 10.0,
                "statistics_interval": 1.0,
            },
        },
    )
    await hass.async_block_till_done()
    assert config_entry.options == {
        "show_names": True,
        "paged": True,
        "scan_interval": 45,
        "intervention_interval": 15,
        "watched_vehicles": ["v1"],
        "my_availability": True,
        "pre_alert": True,
        "garrison": False,
        "my_events": False,
        "statistics": True,
        "readiness_safety": 5,
        "roster_safety": 10,
        "teams_safety": 1,
        "availability_safety": 5,
        "alerts_safety": 10,
        "events_interval": 10,
        "statistics_interval": 1,
    }
    assert all(
        isinstance(v, int) for k, v in config_entry.options.items() if k.endswith(("interval", "safety"))
    )
