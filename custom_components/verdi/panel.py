# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""The status page: a sidebar panel, and the websocket command that tells it which entities to show."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_RESTORED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration

from .const import DOMAIN

PANEL_PATH = "verdi"
STATIC_URL = "/verdi_static"
# hass.data key. A panel can't be registered twice, and HA 2026.4.0 has no async_panel_exists.
PANEL_SHOWN = f"{DOMAIN}_panel_shown"


def status_page(hass: HomeAssistant) -> list[dict[str, Any]]:
    """The sensors of each entry, by translation key: the availability calendar shares one of the keys."""
    registry = er.async_get(hass)
    sections = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        found: dict[str, list[str]] = {"my_availability": [], "vehicles": [], "personnel": []}
        loaded = entry.state is ConfigEntryState.LOADED
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
            if entity.domain == "sensor" and entity.translation_key in found and not entity.disabled:
                # My availability switched off by the options stays restored. Vehicle and personnel sensors
                # exist only if their lookup answered once, so a failed lookup looks restored: keep them.
                state = hass.states.get(entity.entity_id)
                if (
                    loaded
                    and entity.translation_key == "my_availability"
                    and state is not None
                    and state.attributes.get(ATTR_RESTORED)
                ):
                    continue
                found[entity.translation_key].append(entity.entity_id)
        if any(found.values()):
            sections.append(
                {
                    "title": entry.title,
                    "my_availability": next(iter(found["my_availability"]), None),
                    "vehicles": sorted(found["vehicles"]),
                    "personnel": next(iter(found["personnel"]), None),
                }
            )
    return sections


@websocket_api.websocket_command({vol.Required("type"): "verdi/status_page"})
@callback
def ws_status_page(hass: HomeAssistant, connection: Any, msg: dict[str, Any]) -> None:
    connection.send_result(msg["id"], {"sections": status_page(hass)})


async def async_setup_panel(hass: HomeAssistant) -> None:
    """Once per start: the page file and the command."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "frontend"), True)]
    )
    websocket_api.async_register_command(hass, ws_status_page)


async def async_show_panel(hass: HomeAssistant) -> None:
    if hass.data.get(PANEL_SHOWN):
        return
    hass.data[PANEL_SHOWN] = True  # before the await: two entries can set up at once
    integration = await async_get_integration(hass, DOMAIN)
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_PATH,
        webcomponent_name="verdi-panel",
        sidebar_title="Verdi (unofficial)",
        sidebar_icon="mdi:fire-truck",
        module_url=f"{STATIC_URL}/verdi-panel.js?v={integration.version}",
        require_admin=False,
    )


@callback
def async_hide_panel(hass: HomeAssistant) -> None:
    if hass.data.pop(PANEL_SHOWN, False):
        frontend.async_remove_panel(hass, PANEL_PATH)
