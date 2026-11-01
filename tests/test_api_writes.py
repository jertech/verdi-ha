# SPDX-License-Identifier: GPL-3.0-or-later
"""The write calls: exact bodies and headers, accepted statuses, refusals with feedback."""

import pytest

from custom_components.verdi.api import (
    ALLOWED_ENDPOINTS,
    EVENT_TEMPLATE,
    VerdiApi,
    VerdiError,
    VerdiRefused,
    VerdiUnavailable,
    endpoint_key,
)
from tests.responses import guid

BASE = "https://zone.verdi.example/verdi-core/api/v1"
WEB = {"Accept": "application/json, text/plain, */*", "include-all": "false", "language": "nl"}


class Response:
    def __init__(self, status=200, body=None, headers=None, raw=None):
        self.status, self.body, self.headers, self.raw = status, body, headers or {}, raw
        self.read = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def json(self, content_type=None):
        self.read = True
        if self.raw is not None:
            raise ValueError("not JSON")
        return self.body


class Session:
    def __init__(self, response):
        self.response, self.sent = response, []

    def request(self, method, url, **kwargs):
        self.sent.append((method, url, kwargs.get("json"), kwargs.get("headers")))
        return self.response


def api_with(response):
    session = Session(response)
    return VerdiApi(session, BASE, "token"), session  # type: ignore[arg-type]


OK = {"result": "Success", "warningFeedback": [], "errorFeedback": []}


def test_delete_template_only_for_guids():
    g = guid(7)
    assert endpoint_key("DELETE", f"planning/personcalendar/events/{g}", None) == (
        "DELETE",
        EVENT_TEMPLATE,
        None,
    )
    assert (
        endpoint_key("DELETE", "planning/personcalendar/events/x", None)[1]
        == "planning/personcalendar/events/x"
    )
    assert ("DELETE", EVENT_TEMPLATE, None) in ALLOWED_ENDPOINTS


async def test_add_exception_body_and_headers():
    api, session = api_with(Response(200, OK))
    await api.add_exception("me-1", "av-2", "00:05:00", "station-1", "nl")
    method, url, body, headers = session.sent[0]
    assert (method, url) == ("POST", f"{BASE}/planning/personcalendar/events/commands")
    assert body == {
        "command": "PersonAvailabilityEventAddExceptionCommand",
        "personId": "me-1",
        "availabilityId": "av-2",
        "duration": "00:05:00",
        "stationIds": ["station-1"],
    }
    assert headers == {"Authorization": "Bearer token", **WEB}


async def test_unlimited_sends_null_duration():
    api, session = api_with(Response(200, OK))
    await api.add_exception("me-1", "av-2", None, "station-1", "fr")
    assert session.sent[0][2]["duration"] is None
    assert session.sent[0][3]["language"] == "fr"


async def test_return_to_planning_body():
    api, session = api_with(Response(200, OK))
    await api.return_to_planning("me-1", "st-1", None, "nl")
    method, url, body, _ = session.sent[0]
    assert (method, url) == ("POST", f"{BASE}/configuration/persons/commands")
    assert set(body) == {"command", "personId", "stationId", "planningGroupId", "timeStamp"}
    assert body["command"] == "PersonReturnToPlanningCommand"
    assert (body["stationId"], body["planningGroupId"]) == ("st-1", None)
    assert body["timeStamp"].endswith("Z") and "." in body["timeStamp"]


async def test_reads_never_ask_for_person():
    api, session = api_with(Response(200, {"data": []}))
    await api.event_priorities("nl")
    await api.person_calendars("me-1", "nl")
    (m1, u1, b1, h1), (m2, u2, b2, h2) = session.sent
    assert (m1, u1, b1) == ("POST", f"{BASE}/domaindata/predefined/eventpriorities/search", {})
    assert (m2, u2) == ("POST", f"{BASE}/planning/personcalendars/search")
    assert b2 == {"filter": [{"field": "person", "value": "me-1", "operator": "Eq"}]}
    assert h2["include-personcalendar"] == "recurrenceGroups,crewFunction,station"
    for headers in (h1, h2):
        assert not any("person" in v.split(",") for k, v in headers.items() if k.startswith("include-"))


async def test_add_event_accepts_201():
    api, session = api_with(Response(201, {"guid": guid(9), "editable": True}))
    answer = await api.add_event({"start": "x"}, "nl")
    assert answer["guid"] == guid(9)
    assert session.sent[0][:2] == ("POST", f"{BASE}/planning/personcalendar/events")


async def test_delete_event_accepts_204_without_reading():
    response = Response(204)
    api, session = api_with(response)
    assert await api.delete_event(guid(9), "nl") == {}
    assert session.sent[0][:3] == ("DELETE", f"{BASE}/planning/personcalendar/events/{guid(9)}", None)
    assert response.read is False


async def test_delete_event_refuses_a_non_guid():
    api, session = api_with(Response(204))
    with pytest.raises(VerdiError):
        await api.delete_event("../configuration", "nl")
    assert session.sent == []


async def test_refusal_feedback_is_not_in_the_message():
    body = {
        "result": "Failed",
        "errorFeedback": [{"message": "Alex Example is not plannable"}],
        "warningFeedback": [],
    }
    api, _ = api_with(Response(200, body))
    with pytest.raises(VerdiRefused) as err:
        await api.add_exception("me-1", "av-2", "00:05:00", "station-1", "nl")
    assert err.value.feedback == "Alex Example is not plannable"
    assert str(err.value) == "planning/personcalendar/events/commands: refused"
    assert "Alex" not in repr(err.value.args)


async def test_feedback_as_strings_and_problem_details():
    api, _ = api_with(Response(400, {"errorFeedback": ["Start in the past", "Start in the past"]}))
    with pytest.raises(VerdiRefused) as err:
        await api.add_event({}, "nl")
    assert err.value.feedback == "Start in the past"
    api, _ = api_with(Response(422, {"title": "Invalid duration"}))
    with pytest.raises(VerdiRefused) as err:
        await api.add_event({}, "nl")
    assert err.value.feedback == "Invalid duration"
    api, _ = api_with(Response(400, raw="<html>"))
    with pytest.raises(VerdiRefused) as err:
        await api.add_event({}, "nl")
    assert err.value.feedback == ""


async def test_feedback_is_capped():
    api, _ = api_with(Response(200, {"result": "Failed", "errorFeedback": ["x" * 500]}))
    with pytest.raises(VerdiRefused) as err:
        await api.add_exception("me-1", "av-2", None, "station-1", "nl")
    assert len(err.value.feedback) == 300


async def test_reads_keep_the_plain_error():
    api, _ = api_with(Response(200, {"result": "Failed", "errorFeedback": ["secret"]}))
    with pytest.raises(VerdiError) as err:
        await api.my_availability()
    assert not isinstance(err.value, VerdiRefused)


@pytest.mark.parametrize("status", [429, 503])
async def test_unavailable_keeps_its_status(status):
    api, _ = api_with(Response(status, headers={"Retry-After": "30"}))
    with pytest.raises(VerdiUnavailable) as err:
        await api.return_to_planning("me-1", "st-1", None, "nl")
    assert err.value.status == status and err.value.retry_after == 30
