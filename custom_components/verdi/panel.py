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
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_RESTORED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .token import get_store

PANEL_PATH = "verdi"
STATIC_URL = "/verdi_static"
# hass.data key. A panel can't be registered twice, and HA 2026.4.0 has no async_panel_exists.
PANEL_SHOWN = f"{DOMAIN}_panel_shown"
# What the page's dialog needs, by entity domain and translation key.
CONTROLS = {
    ("select", "status_to_set"): "status",
    ("select", "duration"): "duration",
    ("button", "back_to_planning"): "back_to_planning",
}


# What the page shows, by entity domain and translation key: sensors can share a key with a calendar.
SHOWN = {
    ("sensor", "my_availability"): "my_availability",
    ("binary_sensor", "pre_alert"): "pre_alert",
    ("binary_sensor", "garrison"): "garrison",
    ("binary_sensor", "readiness"): "readiness",
    ("sensor", "vehicles"): "vehicles",
    ("sensor", "personnel"): "personnel",
    ("sensor", "availability_year"): "statistics",
    ("sensor", "times_called"): "statistics",
}
# Your own data: a lookup switched off by the options leaves these restored.
PERSONAL = ("my_availability", "pre_alert", "garrison", "statistics")


def _verdi_order(entry: ConfigEntry) -> dict[str, int]:
    """Unique ID -> place in the latest answers. Verdi's order is the web app's, so the page keeps it."""
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        return {}
    prefix = entry.entry_id
    vehicles = (coordinator.lane("vehicles").data or {}).get("vehicles") or []
    ids = [f"{prefix}_vehicles_{v['id']}" for v in vehicles]
    ids += [f"{prefix}_readiness_{t['id']}_bin" for t in (coordinator.data or {}).get("readiness") or []]
    personal = coordinator.personal
    statistics = ((personal.data if personal else None) or {}).get("statistics") or {}
    for kind in ("availability_year", "times_called"):
        ids += [f"{prefix}_{kind}_{item['id']}" for item in statistics.get(kind) or []]
    return {unique_id: place for place, unique_id in enumerate(ids)}


def _sorted(entities: list[er.RegistryEntry], order: dict[str, int]) -> list[str]:
    """In Verdi's order; anything outside the answers last. Availability before counters until known."""
    known = sorted((e for e in entities if e.unique_id in order), key=lambda e: order[e.unique_id])
    rest = sorted(
        (e for e in entities if e.unique_id not in order), key=lambda e: (e.translation_key, e.entity_id)
    )
    return [e.entity_id for e in known + rest]


def _problem(hass: HomeAssistant, entry: ConfigEntry) -> str | None:
    """Why data may be missing, as a fixed word. No token counts only after the start-up grace."""
    store = get_store(hass)
    if any(entry.async_get_active_flows(hass, {SOURCE_REAUTH})):
        return "token"
    if store.get(entry.entry_id) is None:
        return None if store.in_grace() else "token"
    if entry.state is not ConfigEntryState.LOADED:
        return (
            "verdi" if entry.state in (ConfigEntryState.SETUP_RETRY, ConfigEntryState.SETUP_ERROR) else None
        )
    coordinator = entry.runtime_data
    # A run the guard blocks counts as a success, so backing off comes first.
    if coordinator.guard.backing_off:
        return "paused" if coordinator.guard.asked_to_wait else "verdi"
    return None if coordinator.last_update_success else "verdi"


def status_page(hass: HomeAssistant, admin: bool = False) -> list[dict[str, Any]]:
    """The entities of each entry, by translation key. An admin also gets what changing the status needs; the
    actions refuse anyone else."""
    registry = er.async_get(hass)
    sections = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        found: dict[str, list[er.RegistryEntry]] = {key: [] for key in set(SHOWN.values())}
        controls: dict[str, str] = {}
        loaded = entry.state is ConfigEntryState.LOADED
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
            control = CONTROLS.get((entity.domain, entity.translation_key))
            if control and not entity.disabled:
                controls[control] = entity.entity_id  # hidden is fine: hiding is about dashboards
            key = SHOWN.get((entity.domain, entity.translation_key))
            if key and not entity.disabled and not entity.hidden:
                # Personal data switched off by the options stays restored. Vehicle and personnel sensors
                # exist only if their lookup answered once, so a failed lookup looks restored: keep them.
                state = hass.states.get(entity.entity_id)
                if loaded and key in PERSONAL and state is not None and state.attributes.get(ATTR_RESTORED):
                    continue
                found[key].append(entity)
        if any(found[key] for key in ("my_availability", "vehicles", "personnel")):
            order = _verdi_order(entry)
            first = {key: next((e.entity_id for e in found[key]), None) for key in found}
            sections.append(
                {
                    "title": entry.title,
                    "my_availability": first["my_availability"],
                    "pre_alert": first["pre_alert"],
                    "garrison": first["garrison"],
                    "readiness": _sorted(found["readiness"], order),
                    "vehicles": _sorted(found["vehicles"], order),
                    "personnel": first["personnel"],
                    "statistics": _sorted(found["statistics"], order),
                    "controls": _controls(entry.entry_id, controls) if admin else None,
                    "problem": _problem(hass, entry),
                }
            )
    return sections


def _controls(entry_id: str, found: dict[str, str]) -> dict[str, str | None] | None:
    if "status" not in found or "duration" not in found:
        return None
    return {
        "entry_id": entry_id,
        "status": found["status"],
        "duration": found["duration"],
        "back_to_planning": found.get("back_to_planning"),
    }


@websocket_api.websocket_command({vol.Required("type"): "verdi/status_page"})
@callback
def ws_status_page(hass: HomeAssistant, connection: Any, msg: dict[str, Any]) -> None:
    connection.send_result(msg["id"], {"sections": status_page(hass, connection.user.is_admin)})


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
