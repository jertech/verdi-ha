# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Verdi: unofficial, read-only lookups against the Verdi API with your own account."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SHOW_NAMES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ISSUE_MISSING_CONFIG,
    LEGACY_TOKEN_KEYS,
    MIN_SCAN_INTERVAL,
    REQUIRED_DATA,
)
from .coordinator import VerdiCoordinator
from .token import VerdiTokenView, get_store

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type VerdiConfigEntry = ConfigEntry[VerdiCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    get_store(hass)  # starts the grace period for the first token push
    hass.http.register_view(VerdiTokenView())
    return True


async def async_setup_entry(hass: HomeAssistant, entry: VerdiConfigEntry) -> bool:
    missing = [key for key in REQUIRED_DATA if not entry.data.get(key)]
    issue_id = f"{ISSUE_MISSING_CONFIG}_{entry.entry_id}"
    if missing:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_MISSING_CONFIG,
            translation_placeholders={"title": entry.title},
        )
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="missing_config",
        )
    ir.async_delete_issue(hass, DOMAIN, issue_id)

    store = get_store(hass)
    if entry.unique_id and (pasted := store.pending.pop(entry.unique_id, None)):
        store.tokens[entry.entry_id] = pasted
    token = store.get(entry.entry_id)
    if token is None:
        if store.in_grace():
            raise ConfigEntryNotReady(translation_domain=DOMAIN, translation_key="waiting_for_token")
        raise ConfigEntryAuthFailed(translation_domain=DOMAIN, translation_key="no_token")

    coordinator = VerdiCoordinator(hass, entry, token)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VerdiConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: VerdiConfigEntry) -> None:
    get_store(hass).tokens.pop(entry.entry_id, None)
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_MISSING_CONFIG}_{entry.entry_id}")


async def async_migrate_entry(hass: HomeAssistant, entry: VerdiConfigEntry) -> bool:
    if entry.version > 2:
        return False
    if entry.version == 1:
        # Version 2 keeps tokens in memory only, and adds the names toggle. Existing
        # entries keep showing names, as version 1 did.
        data = {k: v for k, v in entry.data.items() if k not in LEGACY_TOKEN_KEYS}
        options = dict(entry.options)
        options[CONF_SCAN_INTERVAL] = max(
            int(options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)), MIN_SCAN_INTERVAL
        )
        options.setdefault(CONF_SHOW_NAMES, True)
        hass.config_entries.async_update_entry(entry, data=data, options=options, version=2)
        _LOGGER.debug("Migrated Verdi entry to version 2")
    return True
