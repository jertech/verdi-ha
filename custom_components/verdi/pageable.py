# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Decide whether you can be paged, from your availability name."""
from __future__ import annotations

from collections.abc import Sequence

from .const import NON_PAGEABLE_WORDS


def _non_pageable(name: str, saved: Sequence[str] | None) -> bool:
    if saved:
        return name in saved
    lowered = name.casefold()
    return any(word in lowered for word in NON_PAGEABLE_WORDS)


def is_pageable(
    own_name: str | None, my_availability_name: str | None, non_pageable: Sequence[str] | None
) -> bool:
    """True unless the known availability name is non-pageable. The own line wins; My
    availability is the fallback; with neither, pageable (never pause blindly)."""
    name = own_name if own_name is not None else my_availability_name
    if name is None:
        return True
    return not _non_pageable(name, non_pageable)
