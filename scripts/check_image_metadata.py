#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fail if any image in the repository carries metadata (text chunks, EXIF, XMP, C2PA...)."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

# PNG chunks that describe pixels only. Anything else (tEXt, zTXt, iTXt, eXIf, caBX, ...) fails.
PNG_ALLOWED = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"gAMA", b"cHRM", b"sRGB", b"sBIT"}
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".ruff_cache", ".pytest_cache"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tif", ".tiff", ".avif"}


def png_problems(data: bytes) -> list[str]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return ["not a PNG"]
    problems, pos = [], 8
    while pos + 8 <= len(data):
        length, kind = struct.unpack(">I4s", data[pos : pos + 8])
        if kind not in PNG_ALLOWED:
            problems.append(f"chunk {kind.decode('latin-1')}")
        pos += 12 + length
        if kind == b"IEND":
            break
    if pos < len(data):
        problems.append("data after IEND")
    return problems


def jpeg_problems(data: bytes) -> list[str]:
    problems, pos = [], 2
    while pos + 4 <= len(data) and data[pos] == 0xFF:
        marker = data[pos + 1]
        if marker == 0xDA:  # start of scan
            break
        length = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
        if 0xE1 <= marker <= 0xEF or marker == 0xFE:  # APP1..APP15 (EXIF, XMP, C2PA...) and comments
            problems.append(f"segment 0x{marker:02X}")
        pos += 2 + length
    return problems


def main() -> int:
    failed = False
    for path in sorted(Path().rglob("*")):
        if not path.is_file() or SKIP_DIRS.intersection(path.parts):
            continue
        name = str(path)
        suffix = path.suffix.lower()
        if suffix not in IMAGE_SUFFIXES:
            continue
        data = path.read_bytes()
        if suffix == ".png":
            problems = png_problems(data)
        elif suffix in (".jpg", ".jpeg"):
            problems = jpeg_problems(data)
        else:
            problems = [f"{suffix} files are not allowed; use PNG or JPEG"]
        for problem in problems:
            failed = True
            print(f"{name}: {problem}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
