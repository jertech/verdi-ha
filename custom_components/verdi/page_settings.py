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
            vol.Optional("banner"): bool,
        },
    }
)


def _dicts(value: Any) -> dict[str, Any]:
    """Only what's a dict: a damaged file loses the broken part, not the page."""
    if not isinstance(value, dict):
        return {}
    return {key: item for key, item in value.items() if isinstance(item, dict)}


def _users(value: Any) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        user_id: {entry_id: _dicts(sets) for entry_id, sets in _dicts(stations).items()}
        for user_id, stations in _dicts(value).items()
    }


class PageSettings:
    """Kept in memory, as `verdi/status_page` is a callback and can't wait for a file."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, 1, STORE_KEY)
        self.users: dict[str, dict[str, dict[str, Any]]] = {}

    async def async_load(self) -> None:
        try:
            stored = await self._store.async_load()
        except Exception as err:  # whatever the file holds, the integration starts
            _LOGGER.warning("Can't read the page settings, using the default page: %r", err)
            return
        users = stored.get("users") if isinstance(stored, dict) else None
        self.users = _users(users)
        if stored and self.users != users:
            _LOGGER.warning("Ignoring the part of the page settings that has the wrong shape")

    def read(self, user_id: str | None, entry_id: str) -> dict[str, Any]:
        return _dicts(_dicts(self.users.get(user_id or "")).get(entry_id))

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


async def async_remove_station(hass: HomeAssistant, entry_id: str, *, last: bool) -> None:
    """Also works if the domain never set up, which HA skips when every entry is disabled."""
    settings = hass.data.get(DATA)
    if settings is None:
        settings = PageSettings(hass)
        await settings.async_load()
    await settings.async_remove_station(entry_id, last=last)


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
