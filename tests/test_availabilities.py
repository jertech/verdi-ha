# SPDX-License-Identifier: GPL-3.0-or-later
"""The station's availability list: personnel lists everyone, only the configured availabilities count."""

import copy
import random
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.verdi import parse
from custom_components.verdi.api import VerdiError, VerdiUnavailable
from custom_components.verdi.const import DOMAIN
from custom_components.verdi.coordinator import Availabilities
from custom_components.verdi.guard import Guard
from tests import responses as r
from tests.conftest import DATA, fake_command, setup_with_token
from tests.test_guard import Clock

LIST = "domaindata/person/availabilities/displayitems"
PERSONNEL = "configuration/persons/commands"


def person(guid: str, availability: str, **flags: bool) -> dict:
    return {
        "guid": guid,
        "firstName": "Alex",
        "name": "Example",
        "isOnIntervention": flags.get("intervention", False),
        "isOnPreAlert": False,
        "isPresent": flags.get("present", False),
        "currentAvailability": {
            "guid": "a",
            "description": {"default": availability},
        },
    }


def personnel(*persons: dict) -> dict:
    return {**r.PERSONNEL, "personGroups": [{"groupId": "g", "persons": list(persons)}]}


COUNTED = [
    person("p1", "Available", present=True),
    person("p2", "Urgent ", intervention=True),
    person("p3", "Radio"),
]
EXTRA = [person("p4", "Not available", intervention=True), person("p5", "Sick", present=True)]


class FakeApi:
    """Pages of the availability list; an Exception in pages is raised."""

    def __init__(self, pages: list) -> None:
        self.pages, self.calls = pages, []

    async def availabilities(self, station_id: str, skip: int, take: int) -> dict:
        self.calls.append((station_id, skip, take))
        page = self.pages[len(self.calls) - 1]
        if isinstance(page, Exception):
            raise page
        return page


def make(pages: list, configured: list[str] | None = None) -> tuple[Availabilities, FakeApi, Guard, Clock]:
    api, clock = FakeApi(pages), Clock()
    guard = Guard(random.Random(1), clock)
    listed = Availabilities(api, guard, "station-1", configured or ["av-1", "av-2"])  # type: ignore[arg-type]
    return listed, api, guard, clock


def test_availability_list_cleans_names():
    data = {"data": [{"guid": "a", "text": "Urgent "}, {"guid": "b", "text": " "}, {"text": "No ID"}]}
    assert parse.availability_list(data) == {"a": "Urgent"}


def test_counts_skip_listed_unconfigured_availabilities():
    """Same counts as when Verdi lists only the configured availabilities, as before."""
    before = parse.personnel_summary(personnel(*COUNTED))
    after = parse.personnel_summary(personnel(*COUNTED, *EXTRA), exclude=frozenset({"Not available", "Sick"}))
    assert {k: v for k, v in after.items() if k != "persons"} == {
        k: v for k, v in before.items() if k != "persons"
    }
    assert after["total"] == 3
    assert after["by_availability"] == {"Available": 1, "Urgent": 1, "Radio": 1}
    # Everyone stays listed, for your own line and the readiness check.
    assert [p["id"] for p in after["persons"]] == ["p1", "p2", "p3", "p4", "p5"]


async def test_requested_and_excluded():
    listed, api, _, _ = make([r.AVAILABILITIES], configured=["av-radio", "av-1"])
    assert listed.requested() == ["av-radio", "av-1"]  # not loaded: as before
    assert listed.excluded() == frozenset()
    await listed.load()
    assert api.calls == [("station-1", 0, 50)]
    assert listed.requested() == ["av-radio", "av-1", "av-2", "av-3", "av-4"]
    assert listed.excluded() == frozenset({"Urgent", "Not available", "Sick"})
    assert listed.diagnostics() == {"loaded": True, "listed": 4, "configured": 2, "requested": 5}


async def test_a_name_that_is_also_configured_is_counted():
    page = {"data": [{"guid": "av-1", "text": "Same"}, {"guid": "av-9", "text": "Same"}], "total": 2}
    listed, _, _, _ = make([page], configured=["av-1"])
    await listed.load()
    assert listed.excluded() == frozenset()


async def test_pages_until_total():
    first = {"data": [{"guid": f"a{i}", "text": f"A{i}"} for i in range(50)], "total": 60}
    second = {"data": [{"guid": f"b{i}", "text": f"B{i}"} for i in range(10)], "total": 60}
    listed, api, guard, _ = make([first, second])
    await listed.load()
    assert [c[1] for c in api.calls] == [0, 50]
    assert len(listed.listed or {}) == 60
    assert guard.calls_last_minute() == 2


async def test_guard_blocks_the_list():
    listed, api, guard, _ = make([r.AVAILABILITIES])
    guard.wait(600)
    with pytest.raises(VerdiError):
        await listed.load()
    assert api.calls == []
    assert listed.listed is None


async def test_trouble_is_reported_and_keeps_the_old_behaviour():
    listed, _, guard, clock = make([VerdiUnavailable("HTTP 503", retry_after=120)])
    with pytest.raises(VerdiUnavailable):
        await listed.load()
    assert listed.listed is None
    assert listed.requested() == ["av-1", "av-2"]
    assert not guard.can_call()
    clock.now += 120
    assert guard.can_call()


async def test_a_failing_second_page_loads_nothing():
    first = {"data": [{"guid": f"a{i}", "text": f"A{i}"} for i in range(50)], "total": 60}
    listed, _, _, _ = make([first, VerdiError("HTTP 400")])
    with pytest.raises(VerdiError):
        await listed.load()
    assert listed.listed is None


def recording(responses: dict, bodies: list):
    inner = fake_command(responses)

    async def _command(self, path, body):
        bodies.append((path, body))
        return await inner(self, path, body)

    return _command


async def test_personnel_requested_with_every_availability(hass: HomeAssistant):
    bodies: list = []
    responses = r.all_ok()
    responses[PERSONNEL] = personnel(*COUNTED, *EXTRA)
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=4,
        unique_id="station-1",
        title="Verdi",
        data={**DATA, "availability_ids": ["av-radio", "av-1", "av-2"]},
    )
    with (
        patch("custom_components.verdi.api.VerdiApi.command", recording(responses, bodies)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        await setup_with_token(hass, config_entry)
    asked = [b["availabilityFilter"] for path, b in bodies if path == PERSONNEL]
    assert asked == [["av-radio", "av-1", "av-2", "av-3", "av-4"]]
    state = hass.states.get("sensor.verdi_personnel")
    assert state.state == "3"
    assert {
        k: state.attributes.get(k) for k in ("Available", "Urgent", "Radio", "Not available", "Sick")
    } == {
        "Available": 1,
        "Urgent": 1,
        "Radio": 1,
        "Not available": None,
        "Sick": None,
    }
    assert (state.attributes["on_intervention"], state.attributes["present"]) == (1, 1)


async def test_without_the_list_only_the_configured_ones(hass: HomeAssistant, config_entry):
    bodies: list = []
    responses = r.all_ok()
    responses[LIST] = VerdiError(f"{LIST}: HTTP 404")
    with (
        patch("custom_components.verdi.api.VerdiApi.command", recording(responses, bodies)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        await setup_with_token(hass, config_entry)
    assert [b["availabilityFilter"] for path, b in bodies if path == PERSONNEL] == [["av-1", "av-2"]]
    assert hass.states.get("sensor.verdi_personnel").state == "2"
    assert config_entry.runtime_data.availabilities.diagnostics()["loaded"] is False


@pytest.fixture
def unconfigured_me():
    """You are on a listed availability that isn't configured: only the full list has your line."""
    responses = copy.deepcopy(r.all_ok())
    responses[PERSONNEL] = copy.deepcopy(r.PERSONNEL)
    responses[PERSONNEL]["personGroups"][0]["persons"][0]["currentAvailability"]["description"] = {
        "default": "Not available"
    }
    return responses


async def test_your_line_while_on_an_unconfigured_availability(
    hass: HomeAssistant, config_entry, unconfigured_me
):
    with (
        patch("custom_components.verdi.api.VerdiApi.command", fake_command(unconfigured_me)),
        patch("custom_components.verdi.api.VerdiApi.current_user", return_value=r.CURRENT_USER),
    ):
        await setup_with_token(hass, config_entry)
    coordinator = config_entry.runtime_data
    assert any(p["id"] == "me-1" for p in coordinator.data["personnel"]["persons"])
    assert coordinator.data["personnel"]["total"] == 1  # you aren't counted
    assert hass.states.get("sensor.verdi_personnel").state == "1"
