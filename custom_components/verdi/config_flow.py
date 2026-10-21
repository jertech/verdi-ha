# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Config, reconfigure, reauth and options flows for Verdi.

Tokens normally arrive from the Verdi Token Grabber through POST /api/verdi/token.
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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import VerdiApi, VerdiAuthError, VerdiError, clean_token, jwt_claims
from .const import (
    API_PATH,
    CONF_ACCEPT,
    CONF_ACCOUNT_SUB,
    CONF_AVAILABILITY_IDS,
    CONF_BASE_URL,
    CONF_CREW_FUNCTION_IDS,
    CONF_FUNCTION_CALENDAR_ID,
    CONF_PERSON_ID,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_NAMES,
    CONF_STATION_ID,
    CONF_TEAM_GROUP_ID,
    CONF_TOKEN,
    CONF_VEHICLE_TRAIN_IDS,
    CONF_VERDI_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
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
    VERSION = 2

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
        """Normally resolved by the grabber's next push, which aborts this flow.

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
        if user_input is not None:
            options = dict(user_input)
            options[CONF_PERSON_ID] = (options.get(CONF_PERSON_ID) or "").strip()
            if not options[CONF_PERSON_ID]:
                options.pop(CONF_PERSON_ID)
            options[CONF_SCAN_INTERVAL] = max(int(options[CONF_SCAN_INTERVAL]), MIN_SCAN_INTERVAL)
            return self.async_create_entry(data=options)

        options = self.config_entry.options
        person = options.get(CONF_PERSON_ID) or await self._detect_person()
        fields: dict[Any, Any] = {
            vol.Required(
                CONF_SCAN_INTERVAL, default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ): NumberSelector(
                NumberSelectorConfig(min=MIN_SCAN_INTERVAL, max=3600, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_SHOW_NAMES, default=options.get(CONF_SHOW_NAMES, False)): BooleanSelector(),
            vol.Optional(CONF_PERSON_ID, description={"suggested_value": person} if person else {}): TEXT,
        }
        return self.async_show_form(step_id="init", data_schema=vol.Schema(fields))

    async def _detect_person(self) -> str | None:
        """Suggest your own person GUID, only if it is in the personnel list.

        security/users/authorize returns the signed-in user's personGuid. It is only
        suggested when the same GUID appears in the personnel lookup, so a mismatch
        leaves the field empty instead of pointing at the wrong person.
        """
        coordinator = getattr(self.config_entry, "runtime_data", None)
        if coordinator is None:
            return None
        persons = ((coordinator.data or {}).get("personnel") or {}).get("persons") or []
        try:
            me = (await coordinator.api.current_user()).get("personGuid")
        except VerdiError:
            return None
        if isinstance(me, str) and any(p.get("id") == me for p in persons):
            return me
        return None
