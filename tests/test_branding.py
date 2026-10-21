# SPDX-License-Identifier: GPL-3.0-or-later
"""Brand images exist, are PNGs, and carry no metadata."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "custom_components" / "verdi" / "brand"


def test_brand_icon_present():
    for name in ("icon.png", "icon@2x.png"):
        assert (BRAND / name).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", name


def test_manifest_and_addon_versions_match():
    manifest = json.loads((ROOT / "custom_components" / "verdi" / "manifest.json").read_text())
    addon = (ROOT / "verdi_token_grabber" / "config.yaml").read_text()
    assert f'version: "{manifest["version"]}"' in addon
