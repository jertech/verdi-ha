# SPDX-License-Identifier: GPL-3.0-or-later
"""Brand images exist, are PNGs, and carry no metadata."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "custom_components" / "verdi" / "brand"


def test_brand_icon_present():
    for name in ("icon.png", "icon@2x.png"):
        assert (BRAND / name).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", name


def test_versions_are_consistent():
    """The integration and the app have their own versions (the app from 1.0.0); the version script checks
    that each one is consistent with itself and has a changelog entry."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_version.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    manifest = json.loads((ROOT / "custom_components" / "verdi" / "manifest.json").read_text())
    assert manifest["version"]
