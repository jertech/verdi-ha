# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Verdi's live updates: one connection to the hub the web interface also uses (SignalR, JSON protocol).

Verdi only says that something changed, never what: this module keeps the connection and hands each
notice on; live_signals.py decides what to fetch. Only SubscribeAll is ever sent. The WebSocket URL
carries the token, so nothing here logs a URL or an exception's text.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import date, datetime
from typing import Any

import aiohttp
from homeassistant.util import dt as dt_util
from yarl import URL

from .api import retry_after
from .const import (
    LIVE_BACK_INFO,
    LIVE_BACKOFF,
    LIVE_BACKOFF_JITTER,
    LIVE_CHANNELS,
    LIVE_DOWN_WARN,
    LIVE_KEEPALIVE,
    LIVE_NOT_FOUND_RETRY,
    LIVE_ROUTE,
    LIVE_SERVER_TIMEOUT,
    LIVE_STABLE,
    LIVE_START_DELAY,
)
from .guard import Guard

_LOGGER = logging.getLogger(__name__)

RS = "\x1e"
HANDSHAKE = json.dumps({"protocol": "json", "version": 1}) + RS
PING = json.dumps({"type": 6}) + RS
SEND_ALLOWED = frozenset({"SubscribeAll"})

# How an attempt or a connection ended (diagnostics and the next step).
NO_TOKEN = "no_token"  # noqa: S105 - an end kind, not a password
GUARD = "guard"
AUTH = "auth"
NOT_FOUND = "not_found"
NO_WEBSOCKETS = "no_websockets"
UNAVAILABLE = "unavailable"
HANDSHAKE_FAILED = "handshake"
SUBSCRIBE_FAILED = "subscribe"
CLOSED = "closed"
SERVER_CLOSE = "server_close"
SILENT = "silent"
RECONNECT = "reconnect"
ERROR = "error"
DOWN = "down"

type EventHook = Callable[[str, list[Any]], None]
type StateHook = Callable[[bool], None]
type Sleep = Callable[[float], Awaitable[None]]


class LiveEnded(Exception):
    """An attempt or a connection ended. kind: one of the names above; status: the HTTP status, if any;
    retry: seconds Verdi asked to wait (Retry-After). Never carries a URL or a message."""

    def __init__(self, kind: str, status: int | None = None, retry: float | None = None) -> None:
        super().__init__(kind)
        self.kind, self.status, self.retry = kind, status, retry


class LiveClient:
    """One connection per config entry. on_event gets (target, arguments) for every notice; on_state
    True once every subscription is acknowledged, False when that connection ends."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        token: Callable[[], str | None],
        guard: Guard,
        on_event: EventHook,
        on_state: StateHook,
        rng: random.Random,
        *,
        sleep: Sleep = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._session = session
        self._hub = f"{base_url.rstrip('/')}/{LIVE_ROUTE}"
        hub = URL(self._hub)
        self._ws_url = hub.with_scheme("wss" if hub.scheme == "https" else "ws")
        self._token, self._guard = token, guard
        self._on_event, self._on_state = on_event, on_state
        self._rng, self._sleep, self._clock = rng, sleep, clock
        self._token_pushed = asyncio.Event()
        self._drop = False
        self._step = 0
        self._acks = 0
        self._connected_at: float | None = None
        self._down_since = clock()
        self._ever = False
        self._warned: set[str] = set()
        self._reconnects = 0
        self._reconnects_day: date | None = None
        self.connected = False
        self.since: datetime | None = None
        self.last_event: datetime | None = None
        self.last_close: str | None = None
        self.connects = 0
        self.ends: Counter[str] = Counter()

    # Called from outside.

    def token_pushed(self) -> None:
        """A new token arrived: a wait for one ends."""
        self._token_pushed.set()

    def reconnect(self) -> None:
        """Drop the connection at the next frame or ping (at most a keepalive away) and connect again."""
        if self.connected:
            self._drop = True

    @property
    def reconnects_today(self) -> int:
        return self._reconnects if self._reconnects_day == dt_util.now().date() else 0

    def diagnostics(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "since": self.since.isoformat() if self.since else None,
            "connects": self.connects,
            "reconnects_today": self.reconnects_today,
            "ends": dict(self.ends),
            "last_close": self.last_close,
            "last_event": self.last_event.isoformat() if self.last_event else None,
        }

    # The loop.

    async def run(self) -> None:
        """Connect, listen and come back, until cancelled (unload, shutdown) or Verdi offers no WebSockets."""
        await self._sleep(self._rng.uniform(*LIVE_START_DELAY))
        while True:
            try:
                await self._attempt()
                end = LiveEnded(CLOSED)
            except LiveEnded as err:
                end = err
            except Exception as err:  # a message may hold the URL: never let it reach a log
                _LOGGER.debug("Verdi live updates: unexpected %s", type(err).__name__)
                end = LiveEnded(ERROR)
            self._down(end)
            if not await self._pause(end):
                return

    async def _attempt(self) -> None:
        self._token_pushed.clear()  # a push from now on ends a wait for a token
        token = self._token()
        if not token:
            raise LiveEnded(NO_TOKEN)
        if self._guard.backing_off or not self._guard.can_call():
            raise LiveEnded(GUARD)
        self._guard.record_call()
        connection = await self._negotiate(token)
        url = self._ws_url.with_query({"id": connection, "access_token": token})
        try:
            async with self._session.ws_connect(url, autoping=True) as ws:
                await self._listen(ws)
        except aiohttp.WSServerHandshakeError as err:
            raise LiveEnded(AUTH if err.status in (401, 403) else UNAVAILABLE, err.status) from None
        except (aiohttp.ClientError, TimeoutError):
            raise LiveEnded(UNAVAILABLE) from None

    async def _negotiate(self, token: str) -> str:
        try:
            async with self._session.post(
                f"{self._hub}/negotiate",
                params={"negotiateVersion": "1"},
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status in (401, 403):
                    raise LiveEnded(AUTH, resp.status)
                if resp.status == 429 or resp.status >= 500:
                    raise LiveEnded(UNAVAILABLE, resp.status, retry_after(resp.headers.get("Retry-After")))
                if resp.status != 200:
                    raise LiveEnded(NOT_FOUND, resp.status)
                data = await resp.json(content_type=None)
        except LiveEnded:
            raise
        except (aiohttp.ClientError, TimeoutError, ValueError):
            raise LiveEnded(UNAVAILABLE) from None
        if not isinstance(data, dict):
            raise LiveEnded(NO_WEBSOCKETS)
        offered = [t.get("transport") for t in data.get("availableTransports") or [] if isinstance(t, dict)]
        connection = data.get("connectionToken") or data.get("connectionId")
        if (
            data.get("url")
            or "WebSockets" not in offered
            or not connection
            or not isinstance(connection, str)
        ):
            raise LiveEnded(NO_WEBSOCKETS)  # a redirect counts as no WebSockets too
        return connection

    async def _listen(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        self._drop = False  # a reconnect request only applies to the connection it was made on
        await ws.send_str(HANDSHAKE)
        try:
            first = await ws.receive(timeout=LIVE_SERVER_TIMEOUT)
        except TimeoutError:
            raise LiveEnded(HANDSHAKE_FAILED) from None
        if first.type is not aiohttp.WSMsgType.TEXT:
            raise LiveEnded(HANDSHAKE_FAILED)
        answer, _, rest = first.data.partition(RS)
        if answer != "{}":
            raise LiveEnded(HANDSHAKE_FAILED)
        self._acks = 0
        for channel in LIVE_CHANNELS:
            await self._send(ws, "SubscribeAll", channel)
        self._frames(rest)
        heard = pinged = self._clock()
        while True:
            if self._drop:
                self._drop = False
                raise LiveEnded(RECONNECT)
            now = self._clock()
            if now - pinged >= LIVE_KEEPALIVE:
                await ws.send_str(PING)
                pinged = now
            wait = min(pinged + LIVE_KEEPALIVE, heard + LIVE_SERVER_TIMEOUT) - now
            try:
                msg = await ws.receive(timeout=max(wait, 0.05))
            except TimeoutError:
                if self._clock() - heard >= LIVE_SERVER_TIMEOUT:
                    raise LiveEnded(SILENT) from None
                continue
            if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
                raise LiveEnded(CLOSED)
            if msg.type is aiohttp.WSMsgType.ERROR:
                raise LiveEnded(UNAVAILABLE)
            if msg.type is aiohttp.WSMsgType.TEXT:
                heard = self._clock()
                self._frames(msg.data)

    async def _send(self, ws: aiohttp.ClientWebSocketResponse, target: str, *arguments: Any) -> None:
        if target not in SEND_ALLOWED:
            raise ValueError(f"{target} is not sent on the live connection")
        frame = {"arguments": list(arguments), "invocationId": "0", "target": target, "type": 1}
        await ws.send_str(json.dumps(frame) + RS)

    def _frames(self, text: str) -> None:
        for frame in filter(None, text.split(RS)):
            try:
                data = json.loads(frame)
            except ValueError:
                continue
            if not isinstance(data, dict):
                continue
            kind = data.get("type")
            if kind == 3:
                if data.get("error"):
                    raise LiveEnded(SUBSCRIBE_FAILED)
                self._acks += 1
                if self._acks == len(LIVE_CHANNELS):
                    self._up()
            elif kind == 1 and isinstance(data.get("target"), str):
                arguments = data.get("arguments")
                self.last_event = dt_util.now()
                self._call(
                    "event", self._on_event, data["target"], arguments if isinstance(arguments, list) else []
                )
            elif kind == 7:
                raise LiveEnded(SERVER_CLOSE)

    # Up, down and waiting.

    def _up(self) -> None:
        now = self._clock()
        down_for = now - self._down_since
        if not self._ever:
            _LOGGER.info("Verdi live updates connected")
        else:
            today = dt_util.now().date()
            if self._reconnects_day != today:
                self._reconnects_day, self._reconnects = today, 0
            self._reconnects += 1
            # A flapping connection waits up to the longest backoff each time: that is not news.
            level = (
                logging.INFO
                if DOWN in self._warned or down_for > LIVE_BACK_INFO * (1 + LIVE_BACKOFF_JITTER)
                else logging.DEBUG
            )
            _LOGGER.log(level, "Verdi live updates connected again after %d minutes", int(down_for // 60))
        self._ever = True
        self._warned.discard(DOWN)
        self.connected, self.since, self._connected_at = True, dt_util.now(), now
        self.connects += 1
        self._call("state", self._on_state, True)

    def _down(self, end: LiveEnded) -> None:
        self.ends[end.kind] += 1
        _LOGGER.debug("Verdi live updates: %s%s", end.kind, f" (HTTP {end.status})" if end.status else "")
        now = self._clock()
        if self.connected:
            lasted = now - self._connected_at if self._connected_at is not None else 0.0
            if lasted >= LIVE_STABLE or end.kind == RECONNECT:
                self._step = 0
            self.connected, self.since, self.last_close = False, dt_util.now(), end.kind
            self._down_since = now
            self._call("state", self._on_state, False)
        elif (
            now - self._down_since >= LIVE_DOWN_WARN
            and DOWN not in self._warned
            and NOT_FOUND not in self._warned  # that warning said it already
            and end.kind not in (AUTH, NO_TOKEN)  # these wait for a token push; the REST polls report it
        ):
            self._warned.add(DOWN)
            _LOGGER.warning(
                "Verdi live updates have been down for %d minutes; polling at the normal pace until back",
                LIVE_DOWN_WARN // 60,
            )

    def _call(self, kind: str, callback: Callable[..., None], *args: Any) -> None:
        """Run a callback; its failure must not end the connection, and never logs its message."""
        try:
            callback(*args)
        except Exception as err:
            self._warn_once(
                f"callback-{kind}",
                "Verdi live updates: the %s callback failed (%s)",
                kind,
                type(err).__name__,
            )

    def _warn_once(self, kind: str, message: str, *args: Any) -> None:
        if kind not in self._warned:
            self._warned.add(kind)
            _LOGGER.warning(message, *args)

    async def _pause(self, end: LiveEnded) -> bool:
        """Wait before the next attempt. False: stop for good."""
        if end.kind == NO_WEBSOCKETS:
            self._warn_once(
                NO_WEBSOCKETS, "Verdi offers no live updates connection; polling at the normal pace"
            )
            return False
        if end.kind in (NO_TOKEN, AUTH):
            await self._token_pushed.wait()
            return True
        if end.kind == NOT_FOUND:
            self._warn_once(
                NOT_FOUND, "Verdi's live updates answered HTTP %s; trying again every 30 minutes", end.status
            )
            await self._sleep(LIVE_NOT_FOUND_RETRY)
            return True
        if end.retry:
            self._guard.wait(end.retry)
        seconds = self._backoff()
        if end.kind == GUARD or self._guard.backing_off:
            seconds = self._guard.delay(seconds)
        await self._sleep(seconds)
        return True

    def _backoff(self) -> float:
        base = LIVE_BACKOFF[min(self._step, len(LIVE_BACKOFF) - 1)]
        self._step += 1
        return base * self._rng.uniform(1 - LIVE_BACKOFF_JITTER, 1 + LIVE_BACKOFF_JITTER)
