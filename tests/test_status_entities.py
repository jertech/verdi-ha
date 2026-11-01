# SPDX-License-Identifier: GPL-3.0-or-later
"""Status select, duration select and the two buttons."""

import asyncio
import copy
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Context, State
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from pytest_homeassistant_custom_component.common import MockUser, mock_restore_cache

from custom_components.verdi.api import VerdiApi
from tests import responses as r
from tests.conftest import fake_command, setup_with_token

ON = {"status_changes": True}


@pytest.fixture
def writes():
    with (
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.RIGHTS_USER),
        patch.object(VerdiApi, "add_exception", AsyncMock(return_value=dict(r.WRITE_OK))) as add,
        patch.object(VerdiApi, "return_to_planning", AsyncMock(return_value=dict(r.WRITE_OK))) as back,
    ):
        yield add, back


async def test_no_entities_when_off(hass, config_entry, mock_api):
    await setup_with_token(hass, config_entry)
    assert hass.states.get("select.verdi_status_to_set") is None
    assert hass.states.get("button.verdi_set_status") is None


async def test_selects_and_set_status(hass, config_entry, mock_api, writes, hass_admin_user):
    add, _ = writes
    await setup_with_token(hass, config_entry, options=ON)
    status = hass.states.get("select.verdi_status_to_set")
    assert status.attributes["options"] == ["Available", "Urgent", "Not available", "Sick"]
    assert hass.states.get("select.verdi_duration").state == "5m"
    await hass.services.async_call("select", "select_option",
                                   {"entity_id": "select.verdi_status_to_set", "option": "Urgent"}, blocking=True)  # fmt: skip
    await hass.services.async_call("select", "select_option",
                                   {"entity_id": "select.verdi_duration", "option": "unlimited"}, blocking=True)  # fmt: skip
    add.assert_not_called()  # choosing writes nothing
    await hass.services.async_call("button", "press", {"entity_id": "button.verdi_set_status"}, blocking=True,
                                   context=Context(user_id=hass_admin_user.id))  # fmt: skip
    assert add.await_args.args[1:3] == ("av-2", None)


async def test_non_admin_button_press_is_refused(hass, config_entry, mock_api, writes, local_auth):
    add, _ = writes
    await setup_with_token(hass, config_entry, options=ON)
    user = MockUser(groups=[await hass.auth.async_get_group(GROUP_ID_USER)]).add_to_hass(hass)
    assert user.is_admin is False
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call("button", "press", {"entity_id": "button.verdi_set_status"}, blocking=True,
                                       context=Context(user_id=user.id))  # fmt: skip
    assert err.value.translation_key == "not_admin"
    add.assert_not_called()


async def test_read_only_user_is_stopped_by_home_assistant(
    hass, config_entry, mock_api, writes, hass_read_only_user
):
    add, _ = writes
    await setup_with_token(hass, config_entry, options=ON)
    with pytest.raises(Unauthorized):
        await hass.services.async_call("button", "press", {"entity_id": "button.verdi_set_status"}, blocking=True,
                                       context=Context(user_id=hass_read_only_user.id))  # fmt: skip
    add.assert_not_called()


async def test_choices_restored(hass, config_entry, mock_api, writes):
    mock_restore_cache(
        hass, [State("select.verdi_status_to_set", "Sick"), State("select.verdi_duration", "2h")]
    )
    await setup_with_token(hass, config_entry, options=ON)
    assert hass.states.get("select.verdi_status_to_set").state == "Sick"
    assert hass.states.get("select.verdi_duration").state == "2h"


async def test_back_to_planning_available_only_when_flagged(hass, config_entry, writes):
    _, back = writes
    quiet = copy.deepcopy(r.CAROUSEL)
    for key in ("stationAvailabilities", "stationPlanningGroupAvailabilities", "planningGroupAvailabilities"):
        for block in quiet[key]:
            block["canReturnToPlanning"] = False
    responses = r.all_ok()
    responses["mobile/app/commands"]["GetPersonCurrentAvailabilityCarouselInformationCommand"] = quiet
    with patch("custom_components.verdi.api.VerdiApi.command", fake_command(responses)):
        await setup_with_token(hass, config_entry, options=ON)
        assert hass.states.get("button.verdi_back_to_planning").state == STATE_UNAVAILABLE
    with patch("custom_components.verdi.api.VerdiApi.command", fake_command(r.all_ok())):
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("button.verdi_back_to_planning").state != STATE_UNAVAILABLE
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.verdi_back_to_planning"}, blocking=True
        )
    assert back.await_count == 2  # st-1, then the planning group pg-1


async def test_no_back_button_without_my_availability(hass, config_entry, mock_api, writes):
    await setup_with_token(hass, config_entry, options={**ON, "my_availability": False})
    assert hass.states.get("button.verdi_back_to_planning") is None
    assert hass.states.get("button.verdi_set_status") is not None


async def test_second_press_while_busy_is_refused_not_queued(
    hass, config_entry, mock_api, writes, hass_admin_user
):
    add, _ = writes
    release = asyncio.Event()
    entered = asyncio.Event()

    async def held(*args, **kwargs):
        entered.set()
        await release.wait()
        return dict(r.WRITE_OK)

    add.side_effect = held
    await setup_with_token(hass, config_entry, options=ON)
    await hass.services.async_call("select", "select_option",
                                   {"entity_id": "select.verdi_status_to_set", "option": "Urgent"}, blocking=True)  # fmt: skip
    admin = Context(user_id=hass_admin_user.id)
    first = hass.async_create_task(
        hass.services.async_call(
            "button", "press", {"entity_id": "button.verdi_set_status"}, blocking=True, context=admin
        )
    )
    await entered.wait()
    second = hass.async_create_task(
        hass.services.async_call(
            "button", "press", {"entity_id": "button.verdi_set_status"}, blocking=True, context=admin
        )
    )
    # Refused at once; a queued press would still be waiting here, and would write once the first ends.
    await asyncio.wait({second}, timeout=1)
    release.set()
    await first
    with pytest.raises(HomeAssistantError) as err:
        await second
    assert err.value.translation_key == "busy"
    assert add.await_count == 1
