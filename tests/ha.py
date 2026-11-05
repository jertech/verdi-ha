# SPDX-License-Identifier: GPL-3.0-or-later
"""Home Assistant's test helpers, from whichever package is installed: `pytest-homeassistant` (Home
Assistant's own, from 2026.11) or `pytest-homeassistant-custom-component` (before 2026.11; the minimum
version's run)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

from homeassistant.helpers import storage

try:
    from pytest_homeassistant.common import (
        MockConfigEntry,
        MockUser,
        async_fire_time_changed,
        mock_restore_cache,
        mock_restore_cache_with_extra_data,
    )
    from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
except ModuleNotFoundError:
    from pytest_homeassistant_custom_component.common import (
        MockConfigEntry,
        MockUser,
        async_fire_time_changed,
        mock_restore_cache,
        mock_restore_cache_with_extra_data,
    )
    from pytest_homeassistant_custom_component.components.diagnostics import (
        get_diagnostics_for_config_entry,
    )

__all__ = [
    "MockConfigEntry",
    "MockUser",
    "async_fire_time_changed",
    "get_diagnostics_for_config_entry",
    "mock_restore_cache",
    "mock_restore_cache_with_extra_data",
    "real_store_files",
]


@contextmanager
def real_store_files() -> Iterator[None]:
    """Stores made and loaded inside read the real file on disk, past the test storage mock. The new
    package replaces the file layer with a subclass of it; the old one replaces Store._async_load."""
    io = getattr(storage, "_FileStoreIO", None)
    if io is not None and io.__name__ != "_FileStoreIO":
        with patch.object(storage, "_FileStoreIO", io.__mro__[1]):
            yield
    else:
        with patch.object(storage.Store, "_async_load", storage.Store._async_load_data):
            yield
