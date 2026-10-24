# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Config, reconfigure, reauth and options flows for Verdi.

Tokens normally arrive from the Verdi Token Relay through POST /api/verdi/token.
A pasted token is accepted for testing only: it expires in about an hour.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import VerdiApi, VerdiAuthError, VerdiError, clean_token, jwt_claims
from .const import (
    API_PATH,
    CONF_ACCEPT,
    CONF_ACCOUNT_SUB,
    CONF_ALERTS_SAFETY,
    CONF_AVAILABILITY_IDS,
    CONF_AVAILABILITY_SAFETY,
    CONF_BASE_URL,
    CONF_CREW_FUNCTION_IDS,
    CONF_EVENTS_INTERVAL,
    CONF_FUNCTION_CALENDAR_ID,
    CONF_GARRISON,
    CONF_INTERVENTION_INTERVAL,
    CONF_MY_AVAILABILITY,
    CONF_MY_EVENTS,
    CONF_NON_PAGEABLE,
    CONF_PRE_ALERT,
    CONF_READINESS_SAFETY,
    CONF_ROSTER_SAFETY,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_NAMES,
    CONF_STATION_ID,
    CONF_STATISTICS,
    CONF_STATISTICS_INTERVAL,
    CONF_TEAM_GROUP_ID,
    CONF_TEAMS_SAFETY,
    CONF_TOKEN,
    CONF_VEHICLE_TRAIN_IDS,
    CONF_VERDI_URL,
    CONF_WATCHED_VEHICLES,
    DOMAIN,
    INTERVALS,
)
from .coordinator import enabled
from .token import get_store, is_usable, origin

_LOGGER = logging.getLogger(__name__)

ID_FIELDS = (
    CONF_STATION_ID,
    CONF_TEAM_GROUP_ID,
    CONF_FUNCTION_CALENDAR_ID,
    CONF_VEHICLE_TRAIN_IDS,
    CONF_CREW_FUNCTION_IDS,
    CONF_AVAILABILITY_IDS,
)
LIST_FIELDS = (CONF_VEHICLE_TRAIN_IDS, CONF_CREW_FUNCTION_IDS, CONF_AVAILABILITY_IDS)
OPTIONAL_FIELDS = (CONF_FUNCTION_CALENDAR_ID,)
PLACEHOLDERS = {"example_url": "https://<zone>.verdi.cloud"}
TEXT = TextSelector()
SECRET = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
STATION, OWN_DATA, SAFETY = "station", "own_data", "safety"
STATION_INTERVALS = (CONF_SCAN_INTERVAL, CONF_INTERVENTION_INTERVAL)
OWN_SWITCHES = (CONF_MY_AVAILABILITY, CONF_PRE_ALERT, CONF_GARRISON, CONF_MY_EVENTS, CONF_STATISTICS)
SAFETY_INTERVALS = (
    CONF_READINESS_SAFETY,
    CONF_ROSTER_SAFETY,
    CONF_TEAMS_SAFETY,
    CONF_AVAILABILITY_SAFETY,
    CONF_ALERTS_SAFETY,
    CONF_EVENTS_INTERVAL,
    CONF_STATISTICS_INTERVAL,
)


def _csv(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value or "").split(",") if v.strip()]


def _verdi_url(base_url: str | None) -> str:
    return origin(base_url) or ""


def _settings(user_input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate the form fields into entry.data. Returns (data, errors)."""
    errors: dict[str, str] = {}
    url = origin((user_input.get(CONF_VERDI_URL) or "").strip())
    if not url or not url.startswith("https://"):
        errors[CONF_VERDI_URL] = "invalid_url"
    data: dict[str, Any] = {CONF_BASE_URL: f"{url}{API_PATH}" if url else ""}
    for key in ID_FIELDS:
        if key in LIST_FIELDS:
            data[key] = _csv(user_input.get(key))
        else:
            data[key] = (user_input.get(key) or "").strip()
        if not data[key] and key not in OPTIONAL_FIELDS:
            errors[key] = "required"
    return data, errors


def _schema(defaults: Mapping[str, Any], *, disclaimer: bool) -> vol.Schema:
    def suggested(key: str) -> dict[str, Any]:
        value = defaults.get(key)
        if isinstance(value, list):
            value = ", ".join(value)
        return {"suggested_value": value} if value else {}

    fields: dict[Any, Any] = {}
    if disclaimer:
        fields[vol.Required(CONF_ACCEPT, default=False)] = BooleanSelector()
    fields[vol.Required(CONF_VERDI_URL, description=suggested(CONF_VERDI_URL))] = TEXT
    for key in ID_FIELDS:
        marker = vol.Optional if key in OPTIONAL_FIELDS else vol.Required
        fields[marker(key, description=suggested(key))] = TEXT
    if disclaimer:
        fields[vol.Optional(CONF_TOKEN)] = SECRET
    return vol.Schema(fields)


async def _validate_token(hass: HomeAssistant, data: dict[str, Any], token: str) -> str | None:
    """Check a pasted token with one cheap read. Returns an error key or None."""
    claims = jwt_claims(token)
    if claims is None:
        return "invalid_token"
    if not is_usable(token):
        return "token_expired"
    if origin(claims.get("iss")) != _verdi_url(data[CONF_BASE_URL]):
        return "token_wrong_site"
    api = VerdiApi(async_get_clientsession(hass), data[CONF_BASE_URL], token)
    try:
        await api.vehicles(data[CONF_STATION_ID])
    except VerdiAuthError:
        return "invalid_auth"
    except VerdiError:
        return "cannot_connect"
    return None


class VerdiConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 4

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _settings(user_input)
            if not user_input.get(CONF_ACCEPT):
                errors[CONF_ACCEPT] = "must_accept"
            token = clean_token(user_input.get(CONF_TOKEN) or "")
            if not errors and token:
                if error := await _validate_token(self.hass, data, token):
                    errors["base"] = error
                elif sub := (jwt_claims(token) or {}).get("sub"):
                    data[CONF_ACCOUNT_SUB] = sub
            if not errors:
                await self.async_set_unique_id(data[CONF_STATION_ID])
                self._abort_if_unique_id_configured()
                if token:
                    get_store(self.hass).pending[data[CONF_STATION_ID]] = token
                return self.async_create_entry(title="Verdi", data=data)
        defaults = dict(user_input or {})
        defaults.pop(CONF_TOKEN, None)
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(defaults, disclaimer=True),
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _settings(user_input)
            if not errors:
                await self.async_set_unique_id(data[CONF_STATION_ID])
                self._abort_if_unique_id_mismatch(reason="wrong_station")
                keep = (
                    {CONF_ACCOUNT_SUB: entry.data[CONF_ACCOUNT_SUB]}
                    if entry.data.get(CONF_ACCOUNT_SUB)
                    else {}
                )
                return self.async_update_reload_and_abort(entry, data={**data, **keep})
        defaults = {**entry.data, CONF_VERDI_URL: _verdi_url(entry.data.get(CONF_BASE_URL))}
        if user_input:
            defaults.update(user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(defaults, disclaimer=False),
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Normally resolved by the relay's next push, which aborts this flow.

        Pasting a token here is for testing only.
        """
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            token = clean_token(user_input.get(CONF_TOKEN) or "")
            if not token:
                errors["base"] = "no_token"
            elif error := await _validate_token(self.hass, dict(entry.data), token):
                errors["base"] = error
            else:
                sub = (jwt_claims(token) or {}).get("sub")
                stored = entry.data.get(CONF_ACCOUNT_SUB)
                if stored and sub != stored:
                    errors["base"] = "wrong_account"
                else:
                    get_store(self.hass).tokens[entry.entry_id] = token
                    data = {**entry.data, CONF_ACCOUNT_SUB: sub} if sub and not stored else entry.data
                    return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_TOKEN): SECRET}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> VerdiOptionsFlow:
        return VerdiOptionsFlow()


class VerdiOptionsFlow(OptionsFlowWithReload):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            entry = self.config_entry
            # Keys the form doesn't show (such as paged) stay as they are.
            options = dict(entry.options)
            options[CONF_SHOW_NAMES] = bool(user_input[CONF_SHOW_NAMES])
            for name in (STATION, OWN_DATA, SAFETY):
                options.update(user_input.get(name) or {})
            # The availabilities are settings in entry.data, picked here by name.
            availability_ids = [str(v) for v in options.pop(CONF_AVAILABILITY_IDS, None) or []]
            for key in (*STATION_INTERVALS, *SAFETY_INTERVALS):
                options[key] = max(int(options[key]), INTERVALS[key][1])
            options[CONF_WATCHED_VEHICLES] = [str(v) for v in options.get(CONF_WATCHED_VEHICLES) or []]
            options[CONF_NON_PAGEABLE] = [str(v) for v in options.get(CONF_NON_PAGEABLE) or []]
            if not availability_ids:
                errors["base"] = "no_availability"
            else:
                if availability_ids != list(entry.data.get(CONF_AVAILABILITY_IDS) or []):
                    self.hass.config_entries.async_update_entry(
                        entry, data={**entry.data, CONF_AVAILABILITY_IDS: availability_ids}
                    )
                    if options == dict(entry.options):
                        # The flow only reloads the entry when the options change.
                        self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_create_entry(data=options)

        options = self.config_entry.options

        def number(key: str) -> tuple[vol.Required, NumberSelector]:
            default, minimum, maximum, _unit = INTERVALS[key]
            return vol.Required(key, default=options.get(key, default)), NumberSelector(
                NumberSelectorConfig(min=minimum, max=maximum, step=1, mode=NumberSelectorMode.BOX)
            )

        station = dict(number(key) for key in STATION_INTERVALS)
        station[
            vol.Optional(CONF_WATCHED_VEHICLES, default=list(options.get(CONF_WATCHED_VEHICLES) or []))
        ] = SelectSelector(
            SelectSelectorConfig(options=self._vehicles(), multiple=True, mode=SelectSelectorMode.DROPDOWN)
        )
        station[
            vol.Required(
                CONF_AVAILABILITY_IDS, default=list(self.config_entry.data.get(CONF_AVAILABILITY_IDS) or [])
            )
        ] = SelectSelector(
            SelectSelectorConfig(
                options=self._availabilities(), multiple=True, mode=SelectSelectorMode.DROPDOWN
            )
        )
        saved = [str(v) for v in options.get(CONF_NON_PAGEABLE) or []]
        station[vol.Optional(CONF_NON_PAGEABLE, default=saved)] = SelectSelector(
            SelectSelectorConfig(
                options=[SelectOptionDict(value=n, label=n) for n in await self._availability_names(saved)],
                multiple=True,
                custom_value=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
        own = {vol.Required(key, default=enabled(options, key)): BooleanSelector() for key in OWN_SWITCHES}
        fields: dict[Any, Any] = {
            vol.Required(CONF_SHOW_NAMES, default=options.get(CONF_SHOW_NAMES, False)): BooleanSelector(),
            vol.Required(STATION): section(vol.Schema(station), {"collapsed": False}),
            vol.Required(OWN_DATA): section(vol.Schema(own), {"collapsed": False}),
            vol.Required(SAFETY): section(
                vol.Schema(dict(number(key) for key in SAFETY_INTERVALS)), {"collapsed": True}
            ),
        }
        return self.async_show_form(step_id="init", data_schema=vol.Schema(fields), errors=errors)

    def _vehicles(self) -> list[SelectOptionDict]:
        """The station's vehicles from the last poll, plus watched ones no longer listed."""
        coordinator = getattr(self.config_entry, "runtime_data", None)
        vehicles = ((coordinator.data or {}).get("vehicles") or []) if coordinator else []
        seen = {v["id"]: v["name"] or v["id"] for v in vehicles if v.get("id")}
        for vehicle_id in self.config_entry.options.get(CONF_WATCHED_VEHICLES) or []:
            seen.setdefault(vehicle_id, vehicle_id)
        return [SelectOptionDict(value=k, label=v) for k, v in seen.items()]

    def _availabilities(self) -> list[SelectOptionDict]:
        """The station's availabilities by name, plus configured ones the list doesn't have."""
        coordinator = getattr(self.config_entry, "runtime_data", None)
        listed = (coordinator.availabilities.listed or {}) if coordinator else {}
        seen = dict(listed)
        for availability_id in self.config_entry.data.get(CONF_AVAILABILITY_IDS) or []:
            seen.setdefault(availability_id, availability_id)
        return [SelectOptionDict(value=k, label=v) for k, v in seen.items()]

    async def _availability_names(self, saved: list[str]) -> list[str]:
        """The station's availability names, plus saved ones the list doesn't have.

        A failed fetch (no token, expired, Verdi down) is not an error here: the form
        still opens with the saved names, and manual entry works.
        """
        entry = self.config_entry
        token = get_store(self.hass).get(entry.entry_id)
        names: list[str] = []
        try:
            if token is None:
                raise VerdiAuthError("no usable token")
            api = VerdiApi(async_get_clientsession(self.hass), entry.data[CONF_BASE_URL], token)
            items = await api.availability_display_items(entry.data[CONF_STATION_ID])
            names = [str(i["text"]) for i in items if i.get("text")]
        except (VerdiError, KeyError, TypeError) as err:
            _LOGGER.debug("Could not list availability names: %s", err)
        return list(dict.fromkeys([*names, *saved]))
