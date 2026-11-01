# SPDX-License-Identifier: GPL-3.0-or-later
"""The status actions: admins only for users, automations allowed, one entry picked."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import Context
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.util import dt as dt_util

from custom_components.verdi.api import VerdiApi
from custom_components.verdi.const import DOMAIN
from tests import responses as r
from tests.conftest import setup_with_token

ON = {"status_changes": True}


@pytest.fixture
def writes():
    with (
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.RIGHTS_USER),
        patch.object(VerdiApi, "add_exception", AsyncMock(return_value=dict(r.WRITE_OK))) as add,
        patch.object(VerdiApi, "return_to_planning", AsyncMock(return_value=dict(r.WRITE_OK))),
        patch.object(VerdiApi, "event_priorities", AsyncMock(return_value=r.EVENT_PRIORITIES)),
        patch.object(VerdiApi, "person_calendars", AsyncMock(return_value=r.PERSON_CALENDARS)),
        patch.object(VerdiApi, "add_event", AsyncMock(return_value={"guid": r.guid(9)})),
        patch.object(VerdiApi, "delete_event", AsyncMock(return_value={})),
    ):
        yield add


async def test_services_exist_without_entries(hass):
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, DOMAIN, {})
    for name in ("add_exception", "return_to_planning", "add_event", "delete_event"):
        assert hass.services.has_service(DOMAIN, name)


async def test_admin_and_automation_may_call(hass, config_entry, mock_api, writes, hass_admin_user):
    await setup_with_token(hass, config_entry, options=ON)
    for context in (Context(user_id=hass_admin_user.id), Context()):
        result = await hass.services.async_call(
            DOMAIN, "add_exception", {"status": "Urgent", "duration": "10m"},
            blocking=True, return_response=True, context=context,
        )  # fmt: skip
        assert result == {"active": False}
    assert writes.await_args.args[2] == "00:10:00"


async def test_non_admin_action_is_refused(hass, config_entry, mock_api, writes, hass_read_only_user):
    await setup_with_token(hass, config_entry, options=ON)
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN, "add_exception", {"status": "Urgent"}, blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )  # fmt: skip
    writes.assert_not_called()


async def test_add_event_returns_the_id(hass, config_entry, mock_api, writes):
    await setup_with_token(hass, config_entry, options=ON)
    start = dt_util.now() + timedelta(hours=2)
    result = await hass.services.async_call(
        DOMAIN, "add_event",
        {"config_entry_id": config_entry.entry_id, "status": "Urgent", "start": start, "end": start + timedelta(hours=1)},
        blocking=True, return_response=True,
    )  # fmt: skip
    assert result == {"event_id": r.guid(9)}


async def test_entry_with_status_changes_off(hass, config_entry, mock_api, writes):
    await setup_with_token(hass, config_entry)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, "return_to_planning", {}, blocking=True)
    assert err.value.translation_key == "status_changes_off"


async def test_unknown_entry(hass, config_entry, mock_api, writes):
    await setup_with_token(hass, config_entry, options=ON)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, "return_to_planning", {"config_entry_id": "nope"}, blocking=True
        )
    assert err.value.translation_key == "entry_not_found"


async def test_duration_must_be_a_known_key(hass, config_entry, mock_api, writes):
    import voluptuous as vol

    await setup_with_token(hass, config_entry, options=ON)
    with pytest.raises((vol.Invalid, ServiceValidationError)):
        await hass.services.async_call(
            DOMAIN, "add_exception", {"status": "Urgent", "duration": "3m"}, blocking=True
        )
