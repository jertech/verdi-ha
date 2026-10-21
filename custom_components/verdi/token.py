# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Token hand-off: the token grabber pushes tokens to POST /api/verdi/token.

Tokens live in memory only, never in the config entry, a file or a log. The view is
admin-only and write-only: it answers with a fixed result code and never echoes input.
This is deliberately not a service call, because service data ends up in the
call_service event and so in the recorder database.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any

from aiohttp import web
from homeassistant.components.http import KEY_HASS, KEY_HASS_USER, HomeAssistantView
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from yarl import URL

from .api import clean_token, jwt_claims, token_expiry
from .const import (
    CONF_ACCOUNT_SUB,
    CONF_BASE_URL,
    DOMAIN,
    TOKEN_GRACE_SECONDS,
    TOKEN_MIN_REMAINING,
    TOKEN_VIEW_MAX_BYTES,
    TOKEN_VIEW_URL,
)


@dataclass
class TokenStore:
    """Per config entry, the newest pushed token. In memory only."""

    started: float = field(default_factory=time.monotonic)
    tokens: dict[str, str] = field(default_factory=dict)
    # Tokens pasted in the config flow, keyed by unique_id until the entry exists.
    pending: dict[str, str] = field(default_factory=dict)

    def get(self, entry_id: str) -> str | None:
        token = self.tokens.get(entry_id)
        return token if token and is_usable(token) else None

    def in_grace(self) -> bool:
        return time.monotonic() - self.started < TOKEN_GRACE_SECONDS


def is_usable(token: str) -> bool:
    exp = token_expiry(token)
    return exp is not None and exp - datetime.now(UTC) >= timedelta(seconds=TOKEN_MIN_REMAINING)


def get_store(hass: HomeAssistant) -> TokenStore:
    return hass.data.setdefault(DOMAIN, TokenStore())


def origin(url: str | None) -> str | None:
    if not url:
        return None
    try:
        u = URL(url)
    except (ValueError, TypeError):
        return None
    if not u.is_absolute() or not u.host:
        return None
    return str(u.origin()).lower()


def _error(code: str, status: HTTPStatus) -> web.Response:
    return web.json_response({"result": code}, status=status)


def match_entry(
    entries: list[ConfigEntry], claims: dict[str, Any], entry_id: str | None
) -> tuple[ConfigEntry | None, bool]:
    """Find the entry a token belongs to. Returns (entry, record_sub)."""
    iss_origin = origin(claims.get("iss"))
    sub = claims.get("sub")
    same_site = [e for e in entries if iss_origin and origin(e.data.get(CONF_BASE_URL)) == iss_origin]
    if entry_id is not None:
        entry = next((e for e in same_site if e.entry_id == entry_id), None)
        if entry is None:
            return None, False
        stored = entry.data.get(CONF_ACCOUNT_SUB)
        if stored and stored != sub:
            return None, False
        return entry, bool(sub) and not stored
    if sub:
        entry = next((e for e in same_site if e.data.get(CONF_ACCOUNT_SUB) == sub), None)
        if entry is not None:
            return entry, False
    # A single entry that has not seen a token yet (new or migrated) takes the first one.
    if len(entries) == 1 and len(same_site) == 1 and not same_site[0].data.get(CONF_ACCOUNT_SUB):
        return same_site[0], bool(sub)
    return None, False


class VerdiTokenView(HomeAssistantView):
    url = TOKEN_VIEW_URL
    name = "api:verdi:token"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        user = request[KEY_HASS_USER]
        if not user.is_admin:
            return _error("forbidden", HTTPStatus.FORBIDDEN)
        if request.content_length is not None and request.content_length > TOKEN_VIEW_MAX_BYTES:
            return _error("invalid_request", HTTPStatus.BAD_REQUEST)
        raw = await request.content.read(TOKEN_VIEW_MAX_BYTES + 1)
        if len(raw) > TOKEN_VIEW_MAX_BYTES:
            return _error("invalid_request", HTTPStatus.BAD_REQUEST)
        try:
            body = json.loads(raw)
        except ValueError:
            return _error("invalid_request", HTTPStatus.BAD_REQUEST)
        if not isinstance(body, dict) or not isinstance(body.get("token"), str):
            return _error("invalid_request", HTTPStatus.BAD_REQUEST)
        entry_id = body.get("entry_id")
        if entry_id is not None and not isinstance(entry_id, str):
            return _error("invalid_request", HTTPStatus.BAD_REQUEST)

        token = clean_token(body["token"])
        claims = jwt_claims(token)
        if claims is None or token_expiry(token) is None:
            return _error("invalid_request", HTTPStatus.BAD_REQUEST)
        if not is_usable(token):
            return _error("expired", HTTPStatus.BAD_REQUEST)

        hass: HomeAssistant = request.app[KEY_HASS]
        entries = hass.config_entries.async_entries(DOMAIN, include_ignore=False, include_disabled=False)
        entry, record_sub = match_entry(entries, claims, entry_id)
        if entry is None:
            return _error("no_matching_entry", HTTPStatus.CONFLICT)

        accept_token(hass, entry, token, claims.get("sub") if record_sub else None)
        return web.json_response({"result": "ok"})


@callback
def accept_token(hass: HomeAssistant, entry: ConfigEntry, token: str, new_sub: str | None) -> None:
    get_store(hass).tokens[entry.entry_id] = token
    if new_sub:
        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_ACCOUNT_SUB: new_sub})

    reauth_flows = list(entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
    for flow in reauth_flows:
        hass.config_entries.flow.async_abort(flow["flow_id"])
    if entry.state in (ConfigEntryState.SETUP_RETRY, ConfigEntryState.SETUP_ERROR) or reauth_flows:
        hass.config_entries.async_schedule_reload(entry.entry_id)
    elif entry.state is ConfigEntryState.LOADED:
        entry.runtime_data.api.set_token(token)
