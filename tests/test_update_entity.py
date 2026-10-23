# SPDX-License-Identifier: GPL-3.0-or-later
"""update_entity on a Verdi entity fetches only that entity's lookup."""

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests import responses as r
from tests.conftest import fake_command, setup_with_token


@pytest.mark.parametrize(
    ("entity_id", "expected"),
    [
        ("sensor.verdi_team_on_duty_north", ["TeamOnDutyWidgetCommand"]),
        ("sensor.verdi_token_expires", []),
        ("sensor.verdi_my_availability", ["GetPersonCurrentAvailabilityCarouselInformationCommand"]),
    ],
)
async def test_update_entity_fetches_one_lookup(hass: HomeAssistant, config_entry, entity_id, expected):
    calls: list = []
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(r.all_ok(), calls)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        await setup_with_token(hass, config_entry)
        assert await async_setup_component(hass, "homeassistant", {})
        calls.clear()
        await hass.services.async_call(
            "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
        )
    assert [c[1] for c in calls] == expected
