# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""The status page's settings: each user's preset and changes, per station, for phone and wide."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA = f"{DOMAIN}_page_settings"
STORE_KEY = f"{DOMAIN}.page_settings"
PRESETS = ("overzicht", "bord", "lijst")
BLOCKS = ("myStatus", "readiness", "vehicles", "personnel", "statistics")
PLACES = ("left", "right", "full")
VIEWS = {
    "vehicles": ("tiles", "border", "list"),
    "readiness": ("lines", "chips"),
    "personnel": ("bar", "pills"),
    "statistics": ("numbers", "rows"),
}


def _each_block_once(order: list[str]) -> list[str]:
    if sorted(order) != sorted(BLOCKS):
        raise vol.Invalid("order must hold each block once")
    return order


def _block(name: str) -> vol.Schema:
    fields: dict[Any, Any] = {vol.Optional("shown"): bool, vol.Optional("place"): vol.In(PLACES)}
    if name in VIEWS:
        fields[vol.Optional("view")] = vol.In(VIEWS[name])
    return vol.Schema(fields)


SET_SCHEMA = vol.Schema(
    {
        vol.Required("preset"): vol.In(PRESETS),
        vol.Required("changes"): {
            vol.Optional("order"): vol.All([str], _each_block_once),
            vol.Optional("blocks"): {vol.Optional(name): _block(name) for name in BLOCKS},
        },
    }
)


class PageSettings:
    """Kept in memory, as `verdi/status_page` is a callback and can't wait for a file."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, 1, STORE_KEY)
        self.users: dict[str, dict[str, dict[str, Any]]] = {}

    async def async_load(self) -> None:
        try:
            stored = await self._store.async_load()
        except HomeAssistantError as err:
            _LOGGER.warning("Can't read the page settings, using the default page: %s", err)
            return
        users = (stored or {}).get("users")
        self.users = users if isinstance(users, dict) else {}

    def read(self, user_id: str | None, entry_id: str) -> dict[str, Any]:
        return (self.users.get(user_id or "") or {}).get(entry_id) or {}

    async def async_save(self, user_id: str, entry_id: str, sets: dict[str, Any]) -> None:
        stations = self.users.get(user_id) or {}
        station = {**(stations.get(entry_id) or {}), **sets}
        self.users = {**self.users, user_id: {**stations, entry_id: station}}
        await self._store.async_save({"users": self.users})

    async def async_remove_station(self, entry_id: str, *, last: bool) -> None:
        if last:
            self.users = {}
            await self._store.async_remove()
            return
        self.users = {
            user_id: {key: value for key, value in stations.items() if key != entry_id}
            for user_id, stations in self.users.items()
        }
        await self._store.async_save({"users": self.users})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "verdi/save_page_settings",
        vol.Required("entry_id"): str,
        vol.Optional("wide"): SET_SCHEMA,
        vol.Optional("phone"): SET_SCHEMA,
    }
)
@websocket_api.async_response
async def ws_save_page_settings(hass: HomeAssistant, connection: Any, msg: dict[str, Any]) -> None:
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "No such station")
        return
    sets = {key: msg[key] for key in ("wide", "phone") if key in msg}
    await hass.data[DATA].async_save(connection.user.id, msg["entry_id"], sets)
    connection.send_result(msg["id"])


async def async_setup_page_settings(hass: HomeAssistant) -> None:
    hass.data[DATA] = settings = PageSettings(hass)
    await settings.async_load()
    websocket_api.async_register_command(hass, ws_save_page_settings)
