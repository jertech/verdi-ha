#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Draw the integration and app icons: a white shield with a check mark on a teal rounded square.

Standard library only. The PNGs carry IHDR, IDAT and IEND and nothing else, so they pass
scripts/check_image_metadata.py. Run from the repository root to rewrite the committed icons.
"""

from __future__ import annotations

import math
import struct
import sys
import zlib
from pathlib import Path

TEAL = (15, 118, 110)
WHITE = (255, 255, 255)
SUBROWS = 16  # vertical samples per pixel row; horizontal coverage is exact

# Geometry on a 512 x 512 canvas.
CORNER_RADIUS = 102.4
SHIELD_HALF_WIDTH = 143.22
SHIELD_TOP = 92.5
SHIELD_SHOULDER = 132.5
SHIELD_WAIST = 244.0
SHIELD_BOTTOM = 429.8
SHIELD_CURVE = ((121.97, 251.71), (187.0, 429.8))  # cubic control points, left side
CHECK_POINTS = ((184.5, 254.0), (244.95, 314.7), (336.0, 193.5))
CHECK_WIDTH = 35.75

OUTPUTS = {
    "custom_components/verdi/brand/icon.png": 256,
    "custom_components/verdi/brand/icon@2x.png": 512,
    "verdi_token_grabber/icon.png": 128,
}

Point = tuple[float, float]


def arc(cx: float, cy: float, r: float, start: float, end: float, steps: int = 48) -> list[Point]:
    angles = (start + (end - start) * i / steps for i in range(steps + 1))
    return [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in angles]


def cubic(p0: Point, p1: Point, p2: Point, p3: Point, steps: int = 64) -> list[Point]:
    out = []
    for i in range(steps + 1):
        t = i / steps
        m = 1 - t
        out.append(
            (
                m**3 * p0[0] + 3 * m * m * t * p1[0] + 3 * m * t * t * p2[0] + t**3 * p3[0],
                m**3 * p0[1] + 3 * m * m * t * p1[1] + 3 * m * t * t * p2[1] + t**3 * p3[1],
            )
        )
    return out


def rounded_square() -> list[Point]:
    r, far = CORNER_RADIUS, 512 - CORNER_RADIUS
    return (
        arc(r, r, r, math.pi, 1.5 * math.pi)
        + arc(far, r, r, 1.5 * math.pi, 2 * math.pi)
        + arc(far, far, r, 0, 0.5 * math.pi)
        + arc(r, far, r, 0.5 * math.pi, math.pi)
    )


def shield() -> list[Point]:
    left, (c1, c2) = 256 - SHIELD_HALF_WIDTH, SHIELD_CURVE
    left_side = cubic((left, SHIELD_WAIST), c1, c2, (256, SHIELD_BOTTOM))
    right_side = [(512 - x, y) for x, y in left_side]
    return [
        (256, SHIELD_TOP),
        (512 - left, SHIELD_SHOULDER),
        *right_side[:-1],
        *reversed(left_side),
        (left, SHIELD_SHOULDER),
    ]


def check() -> list[Point]:
    """Outline of the check stroke: butt ends, round outer join, mitred inner corner."""
    (ax, ay), (jx, jy), (bx, by) = CHECK_POINTS
    half = CHECK_WIDTH / 2

    def normal(x0: float, y0: float, x1: float, y1: float) -> Point:
        length = math.hypot(x1 - x0, y1 - y0)
        return (y1 - y0) / length * half, -(x1 - x0) / length * half

    n1, n2 = normal(ax, ay, jx, jy), normal(jx, jy, bx, by)
    # The inner corner is where the two upper edges meet.
    p, d = (ax + n1[0], ay + n1[1]), (jx - ax, jy - ay)
    q, e = (jx + n2[0], jy + n2[1]), (bx - jx, by - jy)
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / (d[0] * e[1] - d[1] * e[0])
    inner = (p[0] + t * d[0], p[1] + t * d[1])
    start, end = math.atan2(-n2[1], -n2[0]), math.atan2(-n1[1], -n1[0])
    if end < start:
        end += 2 * math.pi
    return [
        (ax + n1[0], ay + n1[1]),
        inner,
        (bx + n2[0], by + n2[1]),
        (bx - n2[0], by - n2[1]),
        *arc(jx, jy, half, start, end),
        (ax - n1[0], ay - n1[1]),
    ]


def coverage(polygon: list[Point], size: int) -> list[list[float]]:
    """Fraction of each pixel inside the polygon (even-odd), on a size x size grid."""
    scale = size / 512
    pts = [(x * scale, y * scale) for x, y in polygon]
    edges = [(a, b) for a, b in zip(pts, pts[1:] + pts[:1], strict=True) if a[1] != b[1]]
    grid = [[0.0] * size for _ in range(size)]
    for py in range(size):
        row = grid[py]
        for sub in range(SUBROWS):
            y = py + (sub + 0.5) / SUBROWS
            xs = sorted(
                x0 + (y - y0) / (y1 - y0) * (x1 - x0)
                for (x0, y0), (x1, y1) in edges
                if min(y0, y1) <= y < max(y0, y1)
            )
            for x0, x1 in zip(xs[::2], xs[1::2], strict=True):
                left, right = max(x0, 0.0), min(x1, float(size))
                first, last = int(left), min(int(right), size - 1)
                if first == last:
                    row[first] += (right - left) / SUBROWS
                    continue
                row[first] += (first + 1 - left) / SUBROWS
                for x in range(first + 1, last):
                    row[x] += 1 / SUBROWS
                row[last] += (right - last) / SUBROWS
    return grid


def render(size: int) -> bytes:
    background, white, mark = (coverage(shape(), size) for shape in (rounded_square, shield, check))
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            a, s, c = (min(g[y][x], 1.0) for g in (background, white, mark))
            s *= 1 - c
            alpha = round(a * 255)
            rgb = (round(TEAL[i] + (WHITE[i] - TEAL[i]) * s) if alpha else 0 for i in range(3))
            raw.extend((*rgb, alpha))
    return png(size, bytes(raw))


def png(size: int, raw: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> int:
    for name, size in OUTPUTS.items():
        Path(name).write_bytes(render(size))
        print(f"{name}: {size}x{size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
