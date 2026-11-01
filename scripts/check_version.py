#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Version checks. The integration's version must equal the release tag and have a CHANGELOG.md entry. The app
has its own version (from 1.0.0): its config.yaml and its script must agree, and its CHANGELOG.md must have an
entry for it. `--app` prints the app's version (used by the app image workflow)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "verdi_token_relay"


def app_version() -> str | None:
    match = re.search(r'^version:\s*"([^"]+)"', (APP / "config.yaml").read_text(), re.M)
    return match.group(1) if match else None


def main() -> int:
    manifest = json.loads((ROOT / "custom_components/verdi/manifest.json").read_text())["version"]
    errors = []
    if len(sys.argv) > 1:
        tag = sys.argv[1].removeprefix("refs/tags/").removeprefix("v")
        if tag != manifest:
            errors.append(f"tag {sys.argv[1]} != integration version {manifest}")
    if f"## [{manifest}]" not in (ROOT / "CHANGELOG.md").read_text():
        errors.append(f"CHANGELOG.md has no entry for {manifest}")
    app = app_version()
    match = re.search(r'^VERSION = "([^"]+)"', (APP / "verdi_token_relay.py").read_text(), re.M)
    if app is None or (match.group(1) if match else None) != app:
        errors.append(f"VERSION in verdi_token_relay.py != app version {app}")
    if app is None or not re.search(rf"^## {re.escape(app)}(\s|$)", (APP / "CHANGELOG.md").read_text(), re.M):
        errors.append(f"verdi_token_relay/CHANGELOG.md has no entry for app version {app}")
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--app"]:
        print(app_version() or "")
        sys.exit(0)
    sys.exit(main())
