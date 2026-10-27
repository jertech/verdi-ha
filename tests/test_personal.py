# SPDX-License-Identifier: GPL-3.0-or-later
"""Your own data: which calls go out, in which language, and when."""

import copy
import zlib
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.verdi.api import APP_ROUTE, VerdiError
from custom_components.verdi.const import DAILY_OFFSET_MAX
from custom_components.verdi.personal import request_language
from custom_components.verdi.token import get_store
from tests import responses as r
from tests.conftest import ALL_OFF, fake_command, make_token, setup_with_token

AVAILABILITY = "GetPersonCurrentAvailabilityCarouselInformationCommand"
PRE, GARRISON = "GetPersonCurrentPreAlertInformationCommand", "GetPersonCurrentGarrisonInformationCommand"
STATS, EVENTS = "AppGetPersonStatisticsCommand", "AppGetUpcomingEventsCommand"
VEHICLES = "configuration/vehicles/commands"


@pytest.fixture
def api():
    calls: list = []
    responses = r.all_ok()
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(responses, calls)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER) as user,
    ):
        yield responses, calls, user


def app_calls(calls: list, command: str | None = None) -> list:
    return [c for c in calls if c[0] == APP_ROUTE and command in (None, c[1])]


async def tick(hass: HomeAssistant, freezer, seconds: float) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("language", "expected"), [("nl", "nl"), ("nl-BE", "nl"), ("fr", "fr"), ("de", "en"), ("en-GB", "en")]
)
async def test_request_language(hass: HomeAssistant, language, expected):
    hass.config.language = language
    assert request_language(hass) == expected


async def test_setup_burst_is_small(hass: HomeAssistant, config_entry, api, freezer):
    _, calls, user = api
    hass.config.language = "fr"
    # Paged off: it polls the app route on the fast lane, which is not the personal burst here.
    await setup_with_token(hass, config_entry, options={"paged": False})
    assert [c[1] for c in app_calls(calls)] == [AVAILABILITY]
    assert len([c for c in calls if c[0] != APP_ROUTE]) == 7  # the availability list and 6 lookups
    assert user.call_count == 1
    await tick(hass, freezer, 330)
    assert sorted(c[1] for c in app_calls(calls)) == sorted([AVAILABILITY, EVENTS, STATS])
    assert {c[2] for c in app_calls(calls) if c[1] in (STATS, EVENTS)} == {"fr"}


async def test_pre_alert_and_garrison_only_when_switched_on(hass: HomeAssistant, config_entry, api):
    _, calls, _ = api
    await setup_with_token(hass, config_entry, options={"pre_alert": True, "garrison": True, "paged": False})
    assert {c[1] for c in app_calls(calls)} == {AVAILABILITY, PRE, GARRISON}
    assert hass.states.get("binary_sensor.verdi_pre_alert").state == "off"
    assert hass.states.get("binary_sensor.verdi_garrison").state == "off"


async def test_defaults_have_no_pre_alert_or_garrison(hass: HomeAssistant, config_entry, api):
    await setup_with_token(hass, config_entry)
    assert hass.states.get("binary_sensor.verdi_pre_alert") is None
    assert hass.states.get("binary_sensor.verdi_garrison") is None


async def test_all_switches_off_make_no_app_calls(hass: HomeAssistant, config_entry, api):
    _, calls, user = api
    await setup_with_token(hass, config_entry, options=ALL_OFF)
    assert app_calls(calls) == []
    assert user.call_count == 0
    assert config_entry.runtime_data.personal is None


async def test_availability_safety_and_end(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    freezer.move_to("2026-06-15T12:00:00+00:00")
    carousel = copy.deepcopy(r.CAROUSEL)
    carousel["globalAvailability"]["end"] = "2026-06-15T12:10:00+00:00"
    responses[APP_ROUTE][AVAILABILITY] = carousel
    await setup_with_token(hass, config_entry, options={"my_events": False, "statistics": False})
    calls.clear()
    await tick(hass, freezer, 10 * 60 + 18)  # end + middle of 5-30 s (17.5 s)
    assert len(app_calls(calls, AVAILABILITY)) == 1
    calls.clear()
    await tick(hass, freezer, 30 * 60)
    assert len(app_calls(calls, AVAILABILITY)) == 1


async def test_failed_lookup_is_retried(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    responses[APP_ROUTE][AVAILABILITY] = VerdiError("mobile/app/commands: HTTP 500")
    await setup_with_token(hass, config_entry, options={"my_events": False, "statistics": False})
    responses[APP_ROUTE][AVAILABILITY] = r.CAROUSEL
    await tick(hass, freezer, 5 * 60)
    assert len(app_calls(calls, AVAILABILITY)) == 2
    assert hass.states.get("sensor.verdi_my_availability").state == "Available 5 min"


async def test_statistics_after_intervention_and_midnight(hass: HomeAssistant, config_entry, api, freezer):
    responses, calls, _ = api
    await hass.config.async_set_time_zone("Europe/Brussels")
    freezer.move_to("2026-06-15T23:00:00+02:00")
    await setup_with_token(hass, config_entry)
    get_store(hass).tokens[config_entry.entry_id] = make_token(lifetime=7200)
    await tick(hass, freezer, 330)
    assert len(app_calls(calls, STATS)) == 1
    on_intervention = copy.deepcopy(r.VEHICLES)
    on_intervention["data"][0]["isOnIntervention"] = True
    responses[VEHICLES] = on_intervention
    await config_entry.runtime_data.async_refresh_lookup("vehicles")
    await tick(hass, freezer, 151)
    assert len(app_calls(calls, STATS)) == 2
    offset = zlib.crc32(config_entry.entry_id.encode()) % DAILY_OFFSET_MAX + 450
    freezer.move_to("2026-06-16T00:05:00+02:00")
    await tick(hass, freezer, offset + 1)
    assert len(app_calls(calls, STATS)) == 3


async def test_no_personal_calls_during_a_backoff(hass: HomeAssistant, config_entry, api, freezer):
    _, calls, _ = api
    await setup_with_token(hass, config_entry, options={"my_events": False, "statistics": False})
    personal = config_entry.runtime_data.personal
    personal.guard.unavailable()  # the station's run met a 503: 60-120 s without calls
    calls.clear()
    personal.mark_due("availability", "trigger:own_availability")
    await personal.async_refresh()
    assert calls == []
    assert personal.last_update_success
    await tick(hass, freezer, 90)  # the backoff is over; the mark is still there
    assert len(app_calls(calls, AVAILABILITY)) == 1
