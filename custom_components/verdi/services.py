# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Actions to change your own status. Admin services: a user who isn't an admin is refused by Home Assistant;
automations and scripts started by Home Assistant (no user) may call them."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN
from .write import StatusWriter, invalid
from .write_data import DEFAULT_DURATION, DURATIONS

ENTRY = {vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string}
ADD_EXCEPTION = vol.Schema(
    {
        **ENTRY,
        vol.Required("status"): cv.string,
        vol.Optional("duration", default=DEFAULT_DURATION): vol.In(list(DURATIONS)),
    }
)
RETURN = vol.Schema(ENTRY)
ADD_EVENT = vol.Schema(
    {
        **ENTRY,
        vol.Required("status"): cv.string,
        vol.Required("start"): cv.datetime,
        vol.Required("end"): cv.datetime,
        vol.Optional("calendar"): cv.string,
    }
)
DELETE_EVENT = vol.Schema({**ENTRY, vol.Required("event_id"): cv.string})


def _writer(hass: HomeAssistant, call: ServiceCall) -> StatusWriter:
    wanted = call.data.get(ATTR_CONFIG_ENTRY_ID)
    entries = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.state is ConfigEntryState.LOADED and (wanted is None or e.entry_id == wanted)
    ]
    if len(entries) != 1:
        raise invalid("entry_not_found")
    writer = getattr(entries[0].runtime_data, "writer", None)
    if writer is None:
        raise invalid("status_changes_off")
    return writer


def async_setup_services(hass: HomeAssistant) -> None:
    async def add_exception(call: ServiceCall) -> dict[str, Any]:
        return await _writer(hass, call).add_exception(call.data["status"], call.data["duration"])

    async def return_to_planning(call: ServiceCall) -> None:
        await _writer(hass, call).return_to_planning()

    async def add_event(call: ServiceCall) -> dict[str, Any]:
        d = call.data
        return await _writer(hass, call).add_event(d["status"], d["start"], d["end"], d.get("calendar"))

    async def delete_event(call: ServiceCall) -> None:
        await _writer(hass, call).delete_event(call.data["event_id"])

    async_register_admin_service(
        hass, DOMAIN, "add_exception", add_exception, ADD_EXCEPTION, SupportsResponse.OPTIONAL
    )
    async_register_admin_service(hass, DOMAIN, "return_to_planning", return_to_planning, RETURN)
    async_register_admin_service(hass, DOMAIN, "add_event", add_event, ADD_EVENT, SupportsResponse.OPTIONAL)
    async_register_admin_service(hass, DOMAIN, "delete_event", delete_event, DELETE_EVENT)
