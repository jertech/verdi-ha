# SPDX-License-Identifier: GPL-3.0-or-later
"""update_entity on a Verdi entity fetches only that entity's lookup."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_fire_time_changed

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


async def test_every_entity_lookup_is_in_its_coordinator(hass: HomeAssistant, config_entry, freezer):
    """A lookup key the coordinator doesn't have would make update_entity a silent no-op."""
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(r.all_ok())),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        await setup_with_token(hass, config_entry, options={"pre_alert": True, "garrison": True})
        freezer.tick(timedelta(seconds=330))  # events and statistics are first fetched 60-600 s later
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    entities = [
        entity for platform in async_get_platforms(hass, "verdi") for entity in platform.entities.values()
    ]
    assert {e.lookup for e in entities if e.lookup} >= {
        "availability",
        "pre_alerts",
        "garrison",
        "events",
        "statistics",
    }
    for entity in entities:
        assert entity.lookup is None or entity.lookup in entity.coordinator.lookups, entity.entity_id
