# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Verdi sensors."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VerdiConfigEntry
from .api import token_expiry
from .coordinator import LookupCoordinator, VerdiCoordinator
from .entity import device_info, find

PARALLEL_UPDATES = 0

FILLED, OPEN = "filled", "open"
AVAILABILITY_YEAR, TIMES_CALLED = "availability_year", "times_called"
MY_AVAILABILITY_ATTRS = ("end", "color", "garrison_crew", "stations", "planning_groups")

VEHICLE_ATTRS = ("station", "availability_since", "color", "on_intervention", "at_outpost")


def _roster_value(names: bool) -> Callable[[dict[str, Any]], Any]:
    def value(item: dict[str, Any]) -> Any:
        current = item["current"]
        if names:
            return (current or {}).get("name")
        return FILLED if current else OPEN

    return value


def _roster_attrs(names: bool) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def attrs(item: dict[str, Any]) -> dict[str, Any]:
        current, nxt = item["current"] or {}, item["next"] or {}
        result = {
            "description": item["description"],
            "start": current.get("start"),
            "end": current.get("end"),
            "next_start": nxt.get("start"),
            "next_end": nxt.get("end"),
        }
        if names:
            result["next"] = nxt.get("name")
        return result

    return attrs


async def async_setup_entry(
    hass: HomeAssistant, entry: VerdiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    c = entry.runtime_data
    data = c.data or {}
    entities: list[SensorEntity] = [TokenExpirySensor(c)]
    if data.get("personnel") is not None:
        entities.append(PersonnelSensor(c))
    for v in data.get("vehicles") or []:
        entities.append(
            VerdiListSensor(
                c,
                "vehicles",
                v["id"],
                lambda i: i["availability"],
                lambda i: {k: i[k] for k in VEHICLE_ATTRS},
                name=v["name"],
            )
        )
    for t in data.get("teams") or []:
        entities.append(
            VerdiListSensor(
                c,
                "teams",
                t["id"],
                lambda i: i["current_team"],
                lambda i: {"next_team": i["next_team"], "next_rotation": i["next_rotation"]},
                translation_key="team_on_duty",
                placeholders={"group": t["group"] or "?"},
            )
        )
    for r in data.get("roster") or []:
        entities.append(
            VerdiListSensor(
                c,
                "roster",
                r["id"],
                _roster_value(c.show_names),
                _roster_attrs(c.show_names),
                translation_key="on_duty_name" if c.show_names else "on_duty",
                placeholders={"function": r["function"] or "?"},
                enum_options=None if c.show_names else [FILLED, OPEN],
            )
        )
    async_add_entities(entities)
    if c.personal is not None:
        async_add_entities([MyAvailabilitySensor(c.personal.fast)])
        _add_statistics_sensors(entry, c.personal.statistics, async_add_entities)


def _add_statistics_sensors(
    entry: VerdiConfigEntry,
    coordinator: LookupCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a sensor for each station and counter as soon as statistics list it."""
    added: set[tuple[str, str]] = set()

    @callback
    def add_new() -> None:
        stats = (coordinator.data or {}).get("statistics") or {}
        new = []
        for kind in (AVAILABILITY_YEAR, TIMES_CALLED):
            for item in stats.get(kind) or []:
                if (kind, item["id"]) not in added:
                    added.add((kind, item["id"]))
                    new.append(StatisticSensor(coordinator, kind, item))
        if new:
            async_add_entities(new)

    add_new()
    entry.async_on_unload(coordinator.async_add_listener(add_new))


class VerdiListSensor(CoordinatorEntity[VerdiCoordinator], SensorEntity):
    """One sensor per item of a list lookup (vehicle, team, crew function)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VerdiCoordinator,
        section: str,
        item_id: str,
        value: Callable[[dict[str, Any]], Any],
        attrs: Callable[[dict[str, Any]], dict[str, Any]],
        *,
        name: str | None = None,
        translation_key: str | None = None,
        placeholders: dict[str, str] | None = None,
        enum_options: list[str] | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._section, self._item_id, self._value, self._attrs = section, item_id, value, attrs
        if translation_key:
            self._attr_translation_key = translation_key
            self._attr_translation_placeholders = placeholders or {}
        else:
            self._attr_name = name
            self._attr_translation_key = section
        if enum_options:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = enum_options
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{section}_{item_id}"
        self._attr_device_info = device_info(coordinator.config_entry)

    @property
    def _item(self) -> dict[str, Any] | None:
        return find((self.coordinator.data or {}).get(self._section), self._item_id)

    @property
    def available(self) -> bool:
        return super().available and self._item is not None

    @property
    def native_value(self) -> Any:
        return self._value(self._item) if self._item else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self._attrs(self._item) if self._item else None


class PersonnelSensor(CoordinatorEntity[VerdiCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "personnel"
    _attr_native_unit_of_measurement = "persons"

    def __init__(self, coordinator: VerdiCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_personnel"
        self._attr_device_info = device_info(coordinator.config_entry)

    @property
    def _summary(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get("personnel")

    @property
    def native_value(self) -> int | None:
        return self._summary["total"] if self._summary else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        s = self._summary
        if not s:
            return None
        counts = {k: s[k] for k in ("on_intervention", "on_pre_alert", "present", "truncated")}
        return {**s["by_availability"], **counts}


class TokenExpirySensor(CoordinatorEntity[VerdiCoordinator], SensorEntity):
    """When the current token stops working. Shows the time only, never the token."""

    _attr_has_entity_name = True
    _attr_translation_key = "token_expiry"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: VerdiCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_token_expiry"
        self._attr_device_info = device_info(coordinator.config_entry)

    @property
    def native_value(self) -> datetime | None:
        return token_expiry(self.coordinator.api.token)


class MyAvailabilitySensor(CoordinatorEntity[LookupCoordinator], SensorEntity):
    """Your own availability now, from the Verdi app route."""

    _attr_has_entity_name = True
    _attr_translation_key = "my_availability"

    def __init__(self, coordinator: LookupCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_my_availability"
        self._attr_device_info = device_info(coordinator.config_entry)

    @property
    def _mine(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get("availability")

    @property
    def available(self) -> bool:
        return super().available and self._mine is not None

    @property
    def native_value(self) -> str | None:
        return self._mine["availability"] if self._mine else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return {k: self._mine[k] for k in MY_AVAILABILITY_ATTRS} if self._mine else None


class StatisticSensor(CoordinatorEntity[LookupCoordinator], SensorEntity):
    """Your availability this year at a station, or how often you were called for a service."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LookupCoordinator, kind: str, item: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self.kind, self.item_id = kind, item["id"]
        self._attr_translation_key = kind
        self._attr_translation_placeholders = {"station": item["station"]}
        if kind == AVAILABILITY_YEAR:
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        else:
            self._attr_translation_placeholders["service"] = item["service"]
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{kind}_{item['id']}"
        self._attr_device_info = device_info(coordinator.config_entry)

    @property
    def _item(self) -> dict[str, Any] | None:
        stats = (self.coordinator.data or {}).get("statistics") or {}
        return find(stats.get(self.kind), self.item_id)

    @property
    def available(self) -> bool:
        return super().available and self._item is not None

    @property
    def native_value(self) -> float | int | None:
        if not self._item:
            return None
        return self._item["percentage"] if self.kind == AVAILABILITY_YEAR else self._item["value"]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if not self._item:
            return None
        if self.kind == AVAILABILITY_YEAR:
            return {"years": self._item["years"]}
        return {"last_called": self._item["last_called"]}
