# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
from custom_components.verdi import pageable


def test_word_list_fallback_marks_unavailable_names():
    assert pageable.is_pageable("Niet beschikbaar", None, None) is False
    assert pageable.is_pageable("Alles 5min", None, None) is True


def test_saved_list_overrides_word_list():
    # "Dringend" is pageable by the word list, but the user put it in non_pageable:
    assert pageable.is_pageable("Dringend", None, ["Dringend"]) is False
    # and a word-list hit NOT in the saved list is pageable once a list is saved:
    assert pageable.is_pageable("Niet beschikbaar", None, ["Dringend"]) is True


def test_falls_back_to_my_availability_when_own_line_missing():
    assert pageable.is_pageable(None, "Niet beschikbaar", None) is False


def test_pageable_when_nothing_known():
    assert pageable.is_pageable(None, None, None) is True
