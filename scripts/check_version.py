#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The integration and the app share one version, which must equal the release tag."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    manifest = json.loads((ROOT / "custom_components/verdi/manifest.json").read_text())["version"]
    match = re.search(r'^version:\s*"([^"]+)"', (ROOT / "verdi_token_grabber/config.yaml").read_text(), re.M)
    addon = match.group(1) if match else None
    errors = []
    if addon != manifest:
        errors.append(f"app version {addon} != integration version {manifest}")
    if len(sys.argv) > 1:
        tag = sys.argv[1].removeprefix("refs/tags/").removeprefix("v")
        if tag != manifest:
            errors.append(f"tag {sys.argv[1]} != version {manifest}")
    if f"## [{manifest}]" not in (ROOT / "CHANGELOG.md").read_text():
        errors.append(f"CHANGELOG.md has no entry for {manifest}")
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
