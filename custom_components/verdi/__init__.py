# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Verdi: unofficial, read-only lookups against the Verdi API with your own account."""

from __future__ import annotations

import logging
from contextlib import suppress
from datetime import datetime

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HassJob, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType

from .api import VerdiError
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SHOW_NAMES,
    DOMAIN,
    FEATURES,
    INTERVALS,
    ISSUE_MISSING_CONFIG,
    LEGACY_MIN_SCAN_INTERVAL,
    LEGACY_PERSON_ID,
    LEGACY_PERSONAL_DATA,
    LEGACY_PERSONAL_INTERVAL,
    LEGACY_TOKEN_KEYS,
    OLD_DEFAULTS,
    REQUIRED_DATA,
    TOKEN_GRACE_SECONDS,
)
from .coordinator import VerdiCoordinator, create_fast
from .guard import drop_guard
from .personal import create_personal, statistics_store
from .signals import Signals, load_timing, timing_store
from .token import VerdiTokenView, get_store

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type VerdiConfigEntry = ConfigEntry[VerdiCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    store = get_store(hass)  # starts the grace period for the first token push
    hass.http.register_view(VerdiTokenView())
    _LOGGER.debug("Waiting up to %d s for the first token push", TOKEN_GRACE_SECONDS)

    @callback
    def grace_over(_now: datetime) -> None:
        # HA's own retry of a waiting entry can be up to 10 minutes away. Re-check now, so an
        # entry that still has no token asks for reauthentication when the grace period ends.
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is ConfigEntryState.SETUP_RETRY and store.get(entry.entry_id) is None:
                _LOGGER.debug("Token grace period over; re-checking %s, which has no token yet", entry.title)
                hass.config_entries.async_schedule_reload(entry.entry_id)

    async_call_later(hass, max(store.grace_left(), 0) + 1, HassJob(grace_over, cancel_on_shutdown=True))
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
        expired = entry.entry_id in store.tokens
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="token_expired" if expired else "no_token_after_wait"
        )

    coordinator = VerdiCoordinator(hass, entry, token)
    personal = create_personal(hass, entry, coordinator)
    # Moves the chosen lookups off the station, so it must run before the station's first refresh.
    fast = create_fast(hass, entry, coordinator)
    # The first refresh already feeds the timing log, so it's loaded before Signals exists.
    timing = await load_timing(hass, entry)
    signals = Signals(hass, entry, coordinator, personal, fast, timing)
    # Without the list, personnel only lists the configured availabilities; a failure is retried later.
    with suppress(VerdiError):
        await coordinator.availabilities.load()
    if personal is not None:
        # Your own line in personnel and your roster shifts need it; a failure is retried later.
        with suppress(VerdiError):
            await coordinator.person.get()
    await coordinator.async_config_entry_first_refresh()
    if fast is not None:
        await fast.async_refresh()
    if personal is not None:
        await personal.async_refresh()
    coordinator.personal = personal
    coordinator.fast = fast
    coordinator.timing = timing
    signals.start()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VerdiConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: VerdiConfigEntry) -> None:
    drop_guard(hass, entry.entry_id)
    get_store(hass).tokens.pop(entry.entry_id, None)
    await statistics_store(hass, entry.entry_id).async_remove()
    await timing_store(hass, entry.entry_id).async_remove()
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_MISSING_CONFIG}_{entry.entry_id}")


async def async_migrate_entry(hass: HomeAssistant, entry: VerdiConfigEntry) -> bool:
    if entry.version > 4:
        return False
    if entry.version == 1:
        # Version 2 keeps tokens in memory only, and adds the names toggle. Existing
        # entries keep showing names, as version 1 did.
        data = {k: v for k, v in entry.data.items() if k not in LEGACY_TOKEN_KEYS}
        options = dict(entry.options)
        options[CONF_SCAN_INTERVAL] = max(
            int(options.get(CONF_SCAN_INTERVAL, OLD_DEFAULTS[CONF_SCAN_INTERVAL])), LEGACY_MIN_SCAN_INTERVAL
        )
        options.setdefault(CONF_SHOW_NAMES, True)
        hass.config_entries.async_update_entry(entry, data=data, options=options, version=2)
        _LOGGER.debug("Migrated Verdi entry to version 2")
    if entry.version == 2:
        options = {k: v for k, v in entry.options.items() if k != LEGACY_PERSON_ID}
        hass.config_entries.async_update_entry(entry, options=options, version=3)
        _LOGGER.debug("Migrated Verdi entry to version 3")
    if entry.version == 3:
        # One switch per kind of your own data; intervals still on an old default move to the new one.
        personal = bool(entry.options.get(LEGACY_PERSONAL_DATA, True))
        drop = (LEGACY_PERSONAL_DATA, LEGACY_PERSONAL_INTERVAL)
        options = {k: v for k, v in entry.options.items() if k not in drop}
        options.update({key: default and personal for key, default in FEATURES.items()})
        for key, old in OLD_DEFAULTS.items():
            if key in options:
                value = int(options[key])
                options[key] = INTERVALS[key][0] if value == old else max(value, INTERVALS[key][1])
        hass.config_entries.async_update_entry(entry, options=options, version=4)
        _LOGGER.debug("Migrated Verdi entry to version 4")
    return True
