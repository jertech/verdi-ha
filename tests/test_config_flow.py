# SPDX-License-Identifier: GPL-3.0-or-later
"""Config, reconfigure, reauth and options flows."""

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, section
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.verdi.api import VerdiAuthError, VerdiError, VerdiUnavailable
from custom_components.verdi.const import CONF_ACCOUNT_SUB, DOMAIN
from custom_components.verdi.token import get_store
from tests import responses as r
from tests.conftest import BASE_URL, DATA, SUB, make_token, setup_with_token


def gid(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012x}"


STATION, OTHER_STATION = gid(1), gid(99)
USER_INPUT = {
    "accept_disclaimer": True,
    "verdi_url": "https://zone.verdi.example/home",
    "station_id": STATION,
    "team_group_id": gid(2),
    "function_calendar_id": gid(3),
    "vehicle_train_ids": f"{gid(4)}, {gid(5)}",
    "crew_function_ids": gid(6),
    "availability_ids": gid(7),
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
    assert result["data"]["vehicle_train_ids"] == [gid(4), gid(5)]
    assert "token" not in result["data"] and "accept_disclaimer" not in result["data"]
    assert result["result"].unique_id == STATION


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


async def test_reconfigure(hass: HomeAssistant, mock_api):
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=4,
        unique_id=STATION,
        title="Verdi",
        data={**DATA, "station_id": STATION},
        source=SOURCE_USER,
    )
    await setup_with_token(hass, entry)
    new = {k: v for k, v in USER_INPUT.items() if k != "accept_disclaimer"}
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**new, "availability_ids": f"{gid(7)},{gid(8)}{gid(9)}"}
    )
    assert result["errors"] == {"availability_ids": "invalid_id"}
    assert entry.data["availability_ids"] == DATA["availability_ids"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**new, "team_group_id": gid(12)}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["team_group_id"] == gid(12)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**new, "station_id": OTHER_STATION}
    )
    assert result["reason"] == "wrong_station"


async def test_setup_refuses_values_that_are_not_ids(hass: HomeAssistant):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **USER_INPUT,
            "station_id": "station-1",
            "availability_ids": f"{gid(7)}, {gid(8)}{gid(9)}",
            "function_calendar_id": "",
            "crew_function_ids": " ",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        "station_id": "invalid_id",
        "availability_ids": "invalid_id",
        "crew_function_ids": "required",
    }
    upper = gid(7).upper()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, "availability_ids": upper}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["availability_ids"] == [upper.lower()]
    # Only the availabilities are lowered; the station ID is the entry's unique ID.
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**USER_INPUT, "station_id": gid(0xA1).upper(), "team_group_id": gid(0xB2).upper()},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["station_id"] == gid(0xA1).upper()
    assert result["data"]["team_group_id"] == gid(0xB2).upper()


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
        "station": {
            "scan_interval": 60,
            "intervention_interval": 30,
            "fast_interval": 15,
            "watched_vehicles": [],
            "availability_ids": ["av-1", "av-2"],
            "non_pageable": [],
        },
        "fast_lane": {"fast_lane": ["paged"]},
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
            "fast_lane": {"fast_lane": ["paged", "vehicles"]},
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
        "fast_interval": 15,
        "fast_lane": ["paged", "vehicles"],
        "watched_vehicles": ["v1"],
        "non_pageable": [],
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


def _station_field(result, key: str):
    station = next(v for k, v in result["data_schema"].schema.items() if str(k) == "station").schema.schema
    return next(v for k, v in station.items() if str(k) == key)


def _submit(station: dict) -> dict:
    return {
        "show_names": False,
        "station": {"scan_interval": 60, "intervention_interval": 30, "watched_vehicles": [], **station},
        "fast_lane": {},
        "own_data": {},
        "safety": {},
    }


GRID = "custom_components.verdi.api.VerdiApi.widget_grid"
STAR = "00000000… ★"


async def test_options_pick_availabilities_by_name(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.config_entries.options.async_configure(result["flow_id"], _submit({}))  # stores defaults
    await hass.async_block_till_done()
    data = {**config_entry.data, "availability_ids": ["av-1", "av-radio"]}
    hass.config_entries.async_update_entry(config_entry, data=data)
    before = dict(config_entry.options)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    options = [(o["value"], o["label"]) for o in _station_field(result, "availability_ids").config["options"]]
    # The list's names; a configured ID the list doesn't have stays pickable.
    assert options == [
        ("av-1", "Available"),
        ("av-2", "Urgent"),
        ("av-3", "Not available"),
        ("av-4", "Sick"),
        ("av-radio", "av-radio"),
        (r.AV_CALLED, STAR),
        (r.AV_RADIO, STAR),
    ]
    with patch("custom_components.verdi.async_setup_entry", return_value=True) as setup:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], _submit({"availability_ids": ["av-1", "av-3", "av-radio"]})
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.data["availability_ids"] == ["av-1", "av-3", "av-radio"]
    assert config_entry.options == before
    assert setup.call_count == 1  # reloaded once, though no option changed


async def test_options_need_an_availability(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _submit({"availability_ids": []})
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_availability"}
    assert config_entry.data["availability_ids"] == ["av-1", "av-2"]


async def test_options_and_availabilities_change_together(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    with patch("custom_components.verdi.async_setup_entry", return_value=True) as setup:
        await hass.config_entries.options.async_configure(
            result["flow_id"], _submit({"scan_interval": 45, "availability_ids": ["av-2"]})
        )
        await hass.async_block_till_done()
    assert config_entry.data["availability_ids"] == ["av-2"]
    assert config_entry.options["scan_interval"] == 45
    assert setup.call_count == 1  # one reload, not two


ITEMS = "custom_components.verdi.api.VerdiApi.availability_display_items"


async def test_options_offer_real_availability_names(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry, options={"non_pageable": ["Custom"]})
    items = [{"id": "g1", "text": "Standby"}, {"id": "g2", "text": "Absent"}]
    with patch(ITEMS, return_value=items) as fetch:
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
    fetch.assert_awaited_once_with(config_entry.data["station_id"])
    field = _station_field(result, "non_pageable")
    assert field.config["multiple"] is True
    assert field.config["custom_value"] is True
    assert [o["value"] for o in field.config["options"]] == ["Standby", "Absent", "Custom"]


async def test_options_survive_a_failing_name_fetch(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry, options={"non_pageable": ["Custom"]})
    with patch(ITEMS, side_effect=VerdiError("boom")):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == "form"
    field = _station_field(result, "non_pageable")
    assert [o["value"] for o in field.config["options"]] == ["Custom"]
    assert _defaults(result["data_schema"])["station"]["non_pageable"] == ["Custom"]


async def test_options_over_24_calls_are_refused(hass: HomeAssistant, config_entry, mock_api):
    # The estimate tops out near 23 with these options, so lower the limit to exercise the refusal.
    await setup_with_token(hass, config_entry)
    before = dict(config_entry.options)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    submit = _submit({"intervention_interval": 15, "fast_interval": 10})
    submit["fast_lane"] = {"fast_lane": ["paged", "vehicles", "personnel"]}
    with patch("custom_components.verdi.config_flow.CALL_LIMIT", 20):
        result = await hass.config_entries.options.async_configure(result["flow_id"], submit)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "too_many_calls"}
    assert float(result["description_placeholders"]["rate"]) > 20
    assert config_entry.options == before


async def test_options_at_or_under_24_calls_save(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    submit = _submit({"fast_interval": 12})
    submit["fast_lane"] = {"fast_lane": ["paged", "vehicles"]}
    result = await hass.config_entries.options.async_configure(result["flow_id"], submit)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options["fast_lane"] == ["paged", "vehicles"]
    assert config_entry.options["fast_interval"] == 12


async def test_options_mark_dashboard_availabilities(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    options = [(o["value"], o["label"]) for o in _station_field(result, "availability_ids").config["options"]]
    assert options == [
        ("av-1", "Available"),
        ("av-2", "Urgent"),
        ("av-3", "Not available"),
        ("av-4", "Sick"),
        (r.AV_CALLED, STAR),
        (r.AV_RADIO, STAR),
    ]
    field = _station_field(result, "availability_ids")
    assert field.config["custom_value"] is True
    assert result["description_placeholders"]["unselected"] == "2"


async def test_options_count_only_unselected_dashboard_availabilities(
    hass: HomeAssistant, config_entry, mock_api
):
    await setup_with_token(hass, config_entry)
    data = {**config_entry.data, "availability_ids": ["av-1", r.AV_CALLED, r.AV_RADIO]}
    hass.config_entries.async_update_entry(config_entry, data=data)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["description_placeholders"]["unselected"] == "0"
    options = [(o["value"], o["label"]) for o in _station_field(result, "availability_ids").config["options"]]
    assert (r.AV_CALLED, STAR) in options
    assert (r.AV_RADIO, STAR) in options


async def test_options_open_when_the_dashboard_lookup_blows_up(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    with patch("custom_components.verdi.config_flow.discover", side_effect=RuntimeError("x")):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"]["unselected"] == "\u2013"


async def test_pasted_ids_are_trimmed(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    with patch("custom_components.verdi.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], _submit({"availability_ids": ["av-1", f" {r.guid(0xB2)}\n"]})
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.data["availability_ids"] == ["av-1", r.guid(0xB2)]


async def test_options_read_the_dashboards_once_per_form(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    with patch(GRID, side_effect=lambda grid_id: r.WIDGET_GRID[grid_id]) as grid:
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        submit = _submit({"intervention_interval": 15, "fast_interval": 10})
        submit["fast_lane"] = {"fast_lane": ["paged", "vehicles", "personnel"]}
        with patch("custom_components.verdi.config_flow.CALL_LIMIT", 20):
            result = await hass.config_entries.options.async_configure(result["flow_id"], submit)
    assert result["errors"] == {"base": "too_many_calls"}
    assert result["description_placeholders"]["unselected"] == "2"
    assert grid.await_count == 3


async def test_options_read_the_names_once_per_form(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    items = [{"id": "g1", "text": "Standby"}]
    with patch(ITEMS, return_value=items) as names:
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        submit = _submit({"intervention_interval": 15, "fast_interval": 10})
        submit["fast_lane"] = {"fast_lane": ["paged", "vehicles", "personnel"]}
        with patch("custom_components.verdi.config_flow.CALL_LIMIT", 20):
            result = await hass.config_entries.options.async_configure(result["flow_id"], submit)
    assert result["errors"] == {"base": "too_many_calls"}
    assert [o["value"] for o in _station_field(result, "non_pageable").config["options"]] == ["Standby"]
    assert names.await_count == 1


async def test_the_name_lookup_reports_to_the_guard(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    guard = config_entry.runtime_data.guard
    with patch("custom_components.verdi.config_flow.discover", return_value=[]):
        guard.level = 2
        await hass.config_entries.options.async_init(config_entry.entry_id)
        assert guard.level == 0  # a successful lookup counts as a success
        with patch(ITEMS, side_effect=VerdiUnavailable("429", retry_after=30)):
            await hass.config_entries.options.async_init(config_entry.entry_id)
    assert not guard.can_call()  # Verdi asked to wait: the guard waits


async def test_pasted_ids_are_checked_and_lowered(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    new = r.guid(0xB1)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _submit({"availability_ids": ["av-1", "not-an-id"]})
    )
    assert result["errors"] == {"base": "invalid_availability_id"}
    assert config_entry.data["availability_ids"] == ["av-1", "av-2"]
    with patch("custom_components.verdi.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            _submit({"availability_ids": ["av-1", r.AV_CALLED.upper(), r.AV_CALLED, new.upper()]}),
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.data["availability_ids"] == ["av-1", r.AV_CALLED, new]


async def test_options_without_discovery_look_as_before(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    config_entry.runtime_data.guard.wait(60)
    with patch(GRID) as grid, patch(ITEMS) as names:
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    grid.assert_not_awaited()
    names.assert_not_awaited()
    assert result["description_placeholders"]["unselected"] == "\u2013"
    labels = [o["label"] for o in _station_field(result, "availability_ids").config["options"]]
    assert "★" not in "".join(labels)


async def test_options_on_an_unloaded_entry(hass: HomeAssistant, config_entry, mock_api):
    config_entry.add_to_hass(hass)  # not set up: no runtime_data, no token
    with patch(GRID) as grid:
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    grid.assert_not_awaited()
    assert result["description_placeholders"]["unselected"] == "\u2013"
    options = [(o["value"], o["label"]) for o in _station_field(result, "availability_ids").config["options"]]
    assert options == [("av-1", "av-1"), ("av-2", "av-2")]


async def test_options_survive_failing_dashboards(hass: HomeAssistant, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    with patch(GRID, side_effect=VerdiError("result=Failed")):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"]["unselected"] == "\u2013"
