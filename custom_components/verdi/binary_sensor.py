# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Verdi binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VerdiConfigEntry
from .coordinator import LookupCoordinator, VerdiCoordinator
from .entity import device_info, find

PARALLEL_UPDATES = 0

READINESS_ATTRS = ("group", "fastest_response_time", "slowest_response_time", "positions")


async def async_setup_entry(
    hass: HomeAssistant, entry: VerdiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    c = entry.runtime_data
    data = c.data or {}
    entities: list[BinarySensorEntity] = []
    for t in data.get("readiness") or []:
        entities.append(
            VerdiListBinarySensor(
                c,
                "readiness",
                t["id"],
                lambda i: i["complete"],
                lambda i: {k: i[k] for k in READINESS_ATTRS},
                "readiness",
                {"train": t["title"] or "?"},
            )
        )
    for v in data.get("vehicles") or []:
        entities.append(
            VerdiListBinarySensor(
                c,
                "vehicles",
                v["id"],
                lambda i: i["on_intervention"],
                lambda i: {"availability": i["availability"]},
                "vehicle_on_intervention",
                {"vehicle": v["name"] or "?"},
            )
        )
    if c.personal is not None:
        entities += [
            PersonalBinarySensor(
                c.personal.fast, "pre_alert", "pre_alerts", bool, lambda v: v[0] if v else None
            ),
            PersonalBinarySensor(
                c.personal.fast,
                "garrison",
                "garrison",
                lambda v: v["active"],
                lambda v: {"station": v["station"], "city": v["city"]} if v["active"] else None,
            ),
        ]
    async_add_entities(entities)


class VerdiListBinarySensor(CoordinatorEntity[VerdiCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VerdiCoordinator,
        section: str,
        item_id: str,
        value: Callable[[dict[str, Any]], bool],
        attrs: Callable[[dict[str, Any]], dict[str, Any]],
        translation_key: str,
        placeholders: dict[str, str],
    ) -> None:
        super().__init__(coordinator)
        self._section, self._item_id, self._value, self._attrs = section, item_id, value, attrs
        self._attr_translation_key = translation_key
        self._attr_translation_placeholders = placeholders
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{section}_{item_id}_bin"
        self._attr_device_info = device_info(coordinator.config_entry)

    @property
    def _item(self) -> dict[str, Any] | None:
        return find((self.coordinator.data or {}).get(self._section), self._item_id)

    @property
    def available(self) -> bool:
        return super().available and self._item is not None

    @property
    def is_on(self) -> bool | None:
        return self._value(self._item) if self._item else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self._attrs(self._item) if self._item else None


class PersonalBinarySensor(CoordinatorEntity[LookupCoordinator], BinarySensorEntity):
    """On while you have a pre-alert, or while you're on garrison."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LookupCoordinator,
        translation_key: str,
        key: str,
        value: Callable[[Any], bool],
        attrs: Callable[[Any], dict[str, Any] | None],
    ) -> None:
        super().__init__(coordinator)
        self._key, self._value, self._attrs = key, value, attrs
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{translation_key}"
        self._attr_device_info = device_info(coordinator.config_entry)

    @property
    def _data(self) -> Any:
        return (self.coordinator.data or {}).get(self._key)

    @property
    def available(self) -> bool:
        return super().available and self._data is not None

    @property
    def is_on(self) -> bool | None:
        return self._value(self._data) if self._data is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self._attrs(self._data) if self._data is not None else None
