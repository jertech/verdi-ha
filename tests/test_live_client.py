# SPDX-License-Identifier: GPL-3.0-or-later
"""The live client: the web interface's way to connect, subscribe, keep alive and come back."""

from __future__ import annotations

import asyncio
import logging
import re
from contextlib import suppress
from pathlib import Path

import aiohttp
import pytest

from custom_components.verdi import live
from custom_components.verdi.const import LIVE_CHANNELS, LIVE_ROUTE
from custom_components.verdi.guard import Guard
from custom_components.verdi.live import LiveClient
from tests.conftest import MidRandom
from tests.live_hub import Hub

TOKEN = "header.secret-token-value.sig"
pytestmark = pytest.mark.usefixtures("socket_enabled")  # the fake hub listens on 127.0.0.1

EVENT = {"type": 1, "target": "ReceiveChanged", "arguments": ["2026-01-01T00:00:00Z", "Person", "p1", []]}


class Sleeps:
    """Records each sleep and returns at once; after `limit` sleeps it parks until the test cancels."""

    def __init__(self, limit: int = 3) -> None:
        self.seen: list[float] = []
        self.limit = limit
        self.done = asyncio.Event()

    async def __call__(self, seconds: float) -> None:
        self.seen.append(seconds)
        if len(self.seen) > self.limit:
            self.done.set()
            await asyncio.Event().wait()
        await asyncio.sleep(0)


async def until(check, timeout: float = 5.0) -> None:
    async with asyncio.timeout(timeout):
        while not check():
            await asyncio.sleep(0.01)


@pytest.fixture
async def hub():
    h = Hub(channels=len(LIVE_CHANNELS))
    await h.start()
    yield h
    await h.close()


@pytest.fixture
async def session():
    async with aiohttp.ClientSession() as s:
        yield s


def make(session, hub, sleeps, *, token=lambda: TOKEN, guard=None, events=None, states=None, clock=None):
    events = [] if events is None else events
    states = [] if states is None else states
    kwargs = {"clock": clock} if clock else {}
    return LiveClient(
        session,
        hub.url(),
        token,
        guard or Guard(MidRandom()),
        lambda target, args: events.append((target, args)),
        states.append,
        MidRandom(),
        sleep=sleeps,
        **kwargs,
    )


async def drive(client: LiveClient, sleeps: Sleeps) -> None:
    task = asyncio.ensure_future(client.run())
    try:
        await asyncio.wait_for(sleeps.done.wait(), 10)
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def test_connects_like_the_web_interface(hub, session):
    hub.script = [[("acks",), ("send", EVENT), ("close",)]]
    events, states, sleeps = [], [], Sleeps(limit=1)
    client = make(session, hub, sleeps, events=events, states=states)
    await drive(client, sleeps)
    assert hub.negotiations == [f"Bearer {TOKEN}"]
    assert hub.tokens == [TOKEN]
    assert hub.sent[0] == {"protocol": "json", "version": 1}
    assert hub.invoked() == [("SubscribeAll", [c]) for c in LIVE_CHANNELS]
    assert events == [("ReceiveChanged", EVENT["arguments"])]
    assert states == [True, False]
    assert client.last_close == "closed"
    assert sleeps.seen[0] == 15  # the start delay: the middle of 0-30 s


async def test_backoff_steps(hub, session):
    hub.negotiate_status = 503
    sleeps = Sleeps(limit=8)
    await drive(make(session, hub, sleeps), sleeps)
    assert sleeps.seen[1:8] == [4, 15, 30, 60, 120, 300, 300]


async def test_retry_after_is_honoured(hub, session):
    hub.negotiate_status, hub.retry_after = 429, "120"
    guard, sleeps = Guard(MidRandom()), Sleeps(limit=1)
    await drive(make(session, hub, sleeps, guard=guard), sleeps)
    assert sleeps.seen[1] >= 119


async def test_each_negotiate_counts_and_no_attempt_while_backing_off(hub, session):
    guard, sleeps = Guard(MidRandom()), Sleeps(limit=1)
    guard.unavailable(None, 60)
    await drive(make(session, hub, sleeps, guard=guard), sleeps)
    assert hub.negotiations == []
    assert sleeps.seen[1] >= 59
    guard2, sleeps2 = Guard(MidRandom()), Sleeps(limit=1)
    hub.negotiate_status = 503
    await drive(make(session, hub, sleeps2, guard=guard2), sleeps2)
    assert guard2.calls_last_minute() == 1


async def test_rejected_token_waits_for_a_push(hub, session):
    hub.negotiate_status = 401
    sleeps = Sleeps(limit=5)
    client = make(session, hub, sleeps)
    task = asyncio.ensure_future(client.run())
    try:
        await until(lambda: len(hub.negotiations) == 1)
        await asyncio.sleep(0.1)
        assert len(hub.negotiations) == 1  # waiting, not retrying
        client.token_pushed()
        await until(lambda: len(hub.negotiations) == 2)
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def test_no_token_waits_for_a_push(hub, session):
    tokens: list[str | None] = [None]
    sleeps = Sleeps(limit=5)
    client = make(session, hub, sleeps, token=lambda: tokens[0])
    task = asyncio.ensure_future(client.run())
    try:
        await asyncio.sleep(0.1)
        assert hub.negotiations == []
        tokens[0] = TOKEN
        client.token_pushed()
        await until(lambda: len(hub.negotiations) == 1)
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def test_not_found_retries_slowly_and_warns_once(hub, session, caplog):
    hub.negotiate_status = 404
    sleeps = Sleeps(limit=2)
    await drive(make(session, hub, sleeps), sleeps)
    assert sleeps.seen[1:3] == [1800, 1800]
    assert sum(1 for r in caplog.records if r.levelno == logging.WARNING) == 1


async def test_no_websockets_stops(hub, session, caplog):
    hub.negotiate_body = {"connectionToken": "ct", "availableTransports": [{"transport": "LongPolling"}]}
    client = make(session, hub, Sleeps(limit=5))
    await asyncio.wait_for(client.run(), 10)
    assert hub.tokens == []
    assert sum(1 for r in caplog.records if r.levelno == logging.WARNING) == 1


async def test_subscription_error_never_connects(hub, session):
    hub.ack_error = "nope"
    states, sleeps = [], Sleeps(limit=1)
    client = make(session, hub, sleeps, states=states)
    await drive(client, sleeps)
    assert states == []
    assert client.ends["subscribe"] == 1


async def test_silence_ends_the_connection_and_pings_go_out(hub, session, monkeypatch):
    monkeypatch.setattr(live, "LIVE_KEEPALIVE", 0.1)
    monkeypatch.setattr(live, "LIVE_SERVER_TIMEOUT", 0.35)
    hub.script = [[("acks",)]]  # then silent
    sleeps = Sleeps(limit=1)
    client = make(session, hub, sleeps)
    await drive(client, sleeps)
    assert client.ends["silent"] == 1
    assert any(f == {"type": 6} for f in hub.sent)


async def test_server_close_frame_ends_the_connection(hub, session):
    hub.script = [[("acks",), ("send", {"type": 7, "error": "bye", "allowReconnect": True})]]
    sleeps = Sleeps(limit=1)
    client = make(session, hub, sleeps)
    await drive(client, sleeps)
    assert client.last_close == "server_close"


async def test_newest_token_on_each_connection(hub, session):
    hub.script = [[("acks",), ("close",)], [("acks",), ("close",)]]
    tokens = iter(["t1", "t2", "t3"])
    current: list[str] = [next(tokens)]

    def token() -> str:
        value = current[0]
        current[0] = next(tokens)
        return value

    sleeps = Sleeps(limit=2)
    await drive(make(session, hub, sleeps, token=token), sleeps)
    assert hub.tokens[:2] == ["t1", "t2"]


async def test_reconnect_request_and_reset(hub, session, monkeypatch):
    monkeypatch.setattr(live, "LIVE_KEEPALIVE", 0.05)
    hub.negotiate_status = 200
    hub.script = [[("acks",)]]
    states, sleeps = [], Sleeps(limit=1)
    client = make(session, hub, sleeps, states=states)
    task = asyncio.ensure_future(client.run())
    try:
        await until(lambda: states == [True])
        client.reconnect()
        await until(lambda: states == [True, False])
        assert client.last_close == "reconnect"
        await until(lambda: len(sleeps.seen) >= 2)
        assert sleeps.seen[1] == 4
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def test_reconnect_request_does_not_outlive_its_connection(hub, session):
    hub.script = [[("acks",), ("sleep", 0.3), ("close",)], [("acks",)]]
    states, sleeps = [], Sleeps(limit=3)
    client = make(session, hub, sleeps, states=states)
    task = asyncio.ensure_future(client.run())
    try:
        await until(lambda: states == [True])
        client.reconnect()  # the hub closes before the client's next loop check
        await until(lambda: states == [True, False, True])
        await asyncio.sleep(0.3)
        assert states == [True, False, True]  # the second connection stays up
        assert "reconnect" not in client.ends
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def test_down_for_15_minutes_warns_once(hub, session, caplog):
    hub.negotiate_status = 503
    now = [0.0]
    sleeps = Sleeps(limit=10)  # attempts at 15, 19, 34, 64, 124, 244, 544, 844, 1144 and 1444 s

    async def sleep(seconds: float) -> None:
        now[0] += seconds
        await sleeps(seconds)

    client = make(session, hub, sleep, clock=lambda: now[0])
    task = asyncio.ensure_future(client.run())
    try:
        await asyncio.wait_for(sleeps.done.wait(), 10)
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "15 minutes" in warnings[0].getMessage()


async def _reconnect_after(hub, session, caplog, down_for: float):
    """Connect, lose the connection, and come back `down_for` seconds later on a fake clock."""
    caplog.set_level(logging.DEBUG)
    hub.script = [[("acks",), ("close",)], [("acks",)]]
    now = [0.0]
    calls = [0]

    async def sleep(seconds: float) -> None:
        calls[0] += 1
        now[0] += down_for if calls[0] == 2 else seconds  # the first is the start delay
        if calls[0] > 2:
            await asyncio.Event().wait()
        await asyncio.sleep(0)

    client = make(session, hub, sleep, clock=lambda: now[0])
    task = asyncio.ensure_future(client.run())
    try:
        await until(lambda: client.connects == 2)
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    return [r for r in caplog.records if r.name.startswith("custom_components.verdi")]


async def test_connected_again_is_quiet_within_a_normal_backoff(hub, session, caplog):
    ours = await _reconnect_after(hub, session, caplog, 330)
    again = [r for r in ours if "connected again" in r.getMessage()]
    assert again
    assert all(r.levelno == logging.DEBUG for r in again)


async def test_connected_again_is_info_after_a_long_outage(hub, session, caplog):
    ours = await _reconnect_after(hub, session, caplog, 400)
    again = [r for r in ours if "connected again" in r.getMessage()]
    assert [r.levelno for r in again] == [logging.INFO]


async def _run_past_15_minutes(hub, session, caplog):
    now = [0.0]
    sleeps = Sleeps(limit=6)

    async def sleep(seconds: float) -> None:
        now[0] += seconds  # 404: every 1800 s, well past 900 s
        await sleeps(seconds)

    client = make(session, hub, sleep, clock=lambda: now[0])
    task = asyncio.ensure_future(client.run())
    try:
        await asyncio.wait_for(sleeps.done.wait(), 10)
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    return [
        r for r in caplog.records if r.levelno == logging.WARNING and r.name.startswith("custom_components")
    ]


async def test_a_404_run_warns_once_not_twice(hub, session, caplog):
    hub.negotiate_status = 404
    warnings = await _run_past_15_minutes(hub, session, caplog)
    assert len(warnings) == 1
    assert "HTTP 404" in warnings[0].getMessage()


async def test_a_401_run_never_warns_it_is_down(hub, session, caplog):
    hub.negotiate_status = 401
    now = [0.0]
    sleeps = Sleeps(limit=1)

    async def sleep(seconds: float) -> None:
        now[0] += seconds
        await sleeps(seconds)

    client = make(session, hub, sleep, clock=lambda: now[0])
    task = asyncio.ensure_future(client.run())
    try:
        await until(lambda: client.ends["auth"] == 1)
        now[0] += 1000
        client.token_pushed()
        await until(lambda: client.ends["auth"] == 2)
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    assert not [r for r in caplog.records if r.levelno == logging.WARNING]


async def test_a_raising_on_state_does_not_stop_run(hub, session, caplog):
    hub.script = [[("acks",), ("close",)], [("acks",)]]
    calls = []

    def boom(connected: bool) -> None:
        calls.append(connected)
        raise RuntimeError("boom-message")

    client = LiveClient(
        session, hub.url(), lambda: TOKEN, Guard(MidRandom()), lambda t, a: None, boom, MidRandom(),
        sleep=Sleeps(limit=5),
    )  # fmt: skip
    task = asyncio.ensure_future(client.run())
    try:
        await until(lambda: client.connects == 2)  # it reconnected after the failing callbacks
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1  # once per kind
    assert "RuntimeError" in warnings[0].getMessage()
    assert "boom-message" not in caplog.text
    assert len(calls) >= 3


async def test_a_raising_on_event_does_not_drop_the_connection(hub, session, caplog):
    hub.script = [[("acks",), ("send", EVENT), ("send", EVENT), ("sleep", 0.2)]]
    seen = []

    def boom(target, args) -> None:
        seen.append(target)
        raise ValueError("boom-message")

    client = LiveClient(
        session, hub.url(), lambda: TOKEN, Guard(MidRandom()), boom, lambda c: None, MidRandom(),
        sleep=Sleeps(limit=5),
    )  # fmt: skip
    task = asyncio.ensure_future(client.run())
    try:
        await until(lambda: len(seen) == 2)
        assert client.connected
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    assert client.ends["error"] == 0
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and "ValueError" in warnings[0].getMessage()
    assert "boom-message" not in caplog.text


async def test_logs_never_hold_the_url_or_token(hub, session, caplog):
    caplog.set_level(logging.DEBUG)
    hub.negotiate_body = {**hub.negotiate_body, "connectionToken": "wrong"}  # the socket answers 404
    sleeps = Sleeps(limit=3)
    await drive(make(session, hub, sleeps), sleeps)
    hub.negotiate_status = 401
    client = make(session, hub, Sleeps(limit=5))
    task = asyncio.ensure_future(client.run())
    try:
        await until(lambda: client.ends["auth"] == 1)
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    # Only our own records: the fake hub's access log does show the URL, as any server's would.
    ours = [r for r in caplog.records if r.name.startswith("custom_components.verdi")]
    assert ours  # the ends were logged at debug
    text = "\n".join(r.getMessage() for r in ours)
    for secret in (TOKEN, "secret-token-value", "access_token", "liveupdates"):
        assert secret not in text
    assert not any(r.exc_info for r in ours)


async def test_only_subscribe_all_is_sent():
    with pytest.raises(ValueError):
        await LiveClient._send(None, None, "Invoke", "x")  # type: ignore[arg-type]


def test_hub_is_documented():
    doc = (Path(__file__).resolve().parent.parent / "docs" / "endpoints.md").read_text(encoding="utf-8")
    rows = set(re.findall(r"^\|\s*(?:Negotiate|WebSocket)\s*\|\s*`([^`]+)`", doc, flags=re.MULTILINE))
    assert rows == {f"{LIVE_ROUTE}/negotiate", LIVE_ROUTE}
    channels = re.search(r"^Channels: (.+)$", doc, flags=re.MULTILINE)
    assert channels is not None
    assert re.findall(r"`([^`]+)`", channels.group(1)) == list(LIVE_CHANNELS)


async def test_backoff_starts_over_only_after_a_stable_connection(hub, session):
    hub.script = [[("acks",), ("close",)] for _ in range(3)]
    now, lasted = [0.0], iter([0, 299, 300])  # how long each connection stays up on the fake clock
    states, sleeps = [], Sleeps(limit=3)

    def on_state(up: bool) -> None:
        states.append(up)
        if up:
            now[0] += next(lasted)

    client = make(session, hub, sleeps, states=states, clock=lambda: now[0])
    client._on_state = on_state
    await drive(client, sleeps)
    assert states == [True, False] * 3
    assert sleeps.seen[1:4] == [4, 15, 4]  # short, 299 s: the next step; 300 s: from the start


async def test_reconnect_request_starts_the_backoff_over(hub, session, monkeypatch):
    monkeypatch.setattr(live, "LIVE_KEEPALIVE", 0.05)
    hub.script = [[("acks",), ("close",)], [("acks",)]]
    states, sleeps = [], Sleeps(limit=2)
    client = make(session, hub, sleeps, states=states)
    task = asyncio.ensure_future(client.run())
    try:
        await until(lambda: states == [True, False, True])
        client.reconnect()
        await until(lambda: len(sleeps.seen) >= 3)
        assert client.last_close == "reconnect"
        assert sleeps.seen[1:3] == [4, 4]  # without the reset the second would be 15
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
