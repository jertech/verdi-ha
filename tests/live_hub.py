# SPDX-License-Identifier: GPL-3.0-or-later
"""A fake live-updates hub on aiohttp's test server: negotiate, handshake, acknowledgements, scripted frames."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestServer

RS = "\x1e"
BASE = "/verdi-core/api/v1"
OK_NEGOTIATE = {
    "negotiateVersion": 1,
    "connectionId": "c",
    "connectionToken": "ct",
    "availableTransports": [{"transport": "WebSockets", "transferFormats": ["Text", "Binary"]}],
}


@dataclass
class Hub:
    """script: one list of steps per WebSocket connection, run after the handshake. Steps:
    ("acks",) waits until every SubscribeAll is acknowledged; ("send", frame) sends a frame;
    ("sleep", seconds); ("close",) closes the socket. After the steps the hub keeps the socket open
    (and silent) until the client closes it. Connections beyond the script get no steps."""

    negotiate_status: int = 200
    negotiate_body: dict[str, Any] = field(default_factory=lambda: dict(OK_NEGOTIATE))
    retry_after: str | None = None
    handshake: str = "{}" + RS
    ack_error: str | None = None
    channels: int = 8
    script: list[list[tuple]] = field(default_factory=list)
    negotiations: list[str] = field(default_factory=list)  # Authorization header per negotiate
    tokens: list[str] = field(default_factory=list)  # access_token per WebSocket
    sent: list[dict[str, Any]] = field(default_factory=list)  # every frame the client sent
    server: TestServer | None = None

    def url(self) -> str:
        assert self.server is not None
        return str(self.server.make_url(BASE))

    async def start(self) -> None:
        app = web.Application()
        app.router.add_post(f"{BASE}/platform/liveupdates/negotiate", self._negotiate)
        app.router.add_get(f"{BASE}/platform/liveupdates", self._socket)
        self.server = TestServer(app)
        await self.server.start_server()

    async def close(self) -> None:
        assert self.server is not None
        await self.server.close()

    def invoked(self) -> list[tuple[str, list[Any]]]:
        return [(f["target"], f["arguments"]) for f in self.sent if f.get("type") == 1]

    async def _negotiate(self, request: web.Request) -> web.StreamResponse:
        self.negotiations.append(request.headers.get("Authorization", ""))
        assert request.query.get("negotiateVersion") == "1"
        if self.negotiate_status != 200:
            headers = {"Retry-After": self.retry_after} if self.retry_after else None
            return web.Response(status=self.negotiate_status, headers=headers)
        return web.json_response(self.negotiate_body)

    async def _socket(self, request: web.Request) -> web.StreamResponse:
        if request.query.get("id") != "ct":
            return web.Response(status=404)
        self.tokens.append(request.query.get("access_token", ""))
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        steps = self.script.pop(0) if self.script else []
        first = await ws.receive()
        self.sent.append(json.loads(first.data.rstrip(RS)))
        await ws.send_str(self.handshake)
        acked = asyncio.Event()
        reader = asyncio.ensure_future(self._read(ws, acked))
        try:
            for step in steps:
                if step[0] == "acks":
                    await asyncio.wait_for(acked.wait(), 5)
                elif step[0] == "send":
                    await ws.send_str(json.dumps(step[1]) + RS)
                elif step[0] == "sleep":
                    await asyncio.sleep(step[1])
                elif step[0] == "close":
                    await ws.close()
                    return ws
            await reader
        finally:
            reader.cancel()
        return ws

    async def _read(self, ws: web.WebSocketResponse, acked: asyncio.Event) -> None:
        count = 0
        async for msg in ws:
            if msg.type is not WSMsgType.TEXT:
                continue
            for frame in filter(None, msg.data.split(RS)):
                data = json.loads(frame)
                self.sent.append(data)
                if data.get("type") != 1:
                    continue
                answer: dict[str, Any] = {"type": 3, "invocationId": data.get("invocationId")}
                if self.ack_error:
                    answer["error"] = self.ack_error
                else:
                    answer["result"] = None
                await ws.send_str(json.dumps(answer) + RS)
                count += 1
                if count >= self.channels:
                    acked.set()
