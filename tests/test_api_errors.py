# SPDX-License-Identifier: GPL-3.0-or-later
"""Which errors mean "Verdi is unavailable" (back off) and what Retry-After says."""

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import aiohttp
import pytest

from custom_components.verdi.api import VerdiApi, VerdiAuthError, VerdiError, VerdiUnavailable, retry_after

PATH = "configuration/vehicles/commands"


class FakeResponse:
    def __init__(self, status: int, headers: dict | None = None) -> None:
        self.status, self.headers = status, headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def json(self, content_type=None):
        return {"result": "Success"}


class FakeSession:
    def __init__(self, result) -> None:
        self.result = result

    def request(self, method, url, **kwargs):
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


async def call(result):
    api = VerdiApi(FakeSession(result), "https://zone.verdi.example/verdi-core/api/v1", "token")  # type: ignore[arg-type]
    return await api.vehicles("station-1")


async def test_503_with_retry_after_seconds():
    with pytest.raises(VerdiUnavailable) as err:
        await call(FakeResponse(503, {"Retry-After": "120"}))
    assert err.value.retry_after == 120
    assert str(err.value) == f"{PATH}: HTTP 503"


async def test_429_with_retry_after_date():
    when = datetime.now(UTC) + timedelta(seconds=90)
    with pytest.raises(VerdiUnavailable) as err:
        await call(FakeResponse(429, {"Retry-After": format_datetime(when, usegmt=True)}))
    assert 80 <= err.value.retry_after <= 91


def test_retry_after_parsing():
    assert retry_after(None) is None
    assert retry_after("soon") is None
    assert retry_after("nan") is None
    assert retry_after("99999") == 3600
    assert retry_after("-5") == 0


@pytest.mark.parametrize(
    ("error", "text"),
    [(TimeoutError(), "timeout"), (aiohttp.ClientConnectionError(), "ClientConnectionError")],
)
async def test_timeouts_and_connection_errors(error, text):
    with pytest.raises(VerdiUnavailable) as err:
        await call(error)
    assert str(err.value) == f"{PATH}: {text}"
    assert err.value.retry_after is None


async def test_auth_and_other_errors_stay_what_they_were():
    with pytest.raises(VerdiAuthError):
        await call(FakeResponse(401))
    with pytest.raises(VerdiAuthError):
        await call(FakeResponse(403))
    with pytest.raises(VerdiError) as err:
        await call(FakeResponse(404))
    assert not isinstance(err.value, VerdiUnavailable)
