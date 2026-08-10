#!/usr/bin/env python3
"""Typeset dialog balloons onto wordless panels.

Reads balloons.json beside this script:
  [{"image": "panel-1.png", "out": "panel-1-lettered.png",
    "balloons": [{"cx": 512, "cy": 180, "text": "It's dying!",
                  "tail": [430, 420], "size": 44}]}]

cx,cy = balloon centre; tail = point the tail aims at (speaker's mouth);
size = font px. Balloon fits itself around the text.
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
INK = (52, 48, 46, 255)
PAPER = (253, 250, 244, 255)

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/ChalkboardSE.ttc",
    "/System/Library/Fonts/Supplemental/Chalkboard.ttc",
    "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
]


def font_at(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    sys.exit("no balloon font found")


def draw_balloon(img: Image.Image, spec: dict) -> None:
    draw = ImageDraw.Draw(img)
    font = font_at(spec.get("size", 44))
    lines = spec["text"].split("\n")
    line_sizes = [draw.textbbox((0, 0), l, font=font) for l in lines]
    text_w = max(b[2] - b[0] for b in line_sizes)
    line_h = max(b[3] - b[1] for b in line_sizes) + 8
    text_h = line_h * len(lines)
    # Ellipse big enough for the text block plus breathing room.
    rx = int(text_w * 0.72) + 28
    ry = int(text_h * 0.95) + 22
    cx, cy = spec["cx"], spec["cy"]
    if "tail" in spec:
        tx, ty = spec["tail"]
        import math

        # Cap the tail: aim at the target but extend at most ~150px past
        # the rim, so it gestures toward the speaker without crossing them.
        ang = math.atan2(ty - cy, tx - cx)
        rim_x = cx + rx * math.cos(ang)
        rim_y = cy + ry * math.sin(ang)
        dist = math.hypot(tx - rim_x, ty - rim_y)
        max_len = spec.get("tail_len", 150)
        if dist > max_len:
            tx = rim_x + (tx - rim_x) * max_len / dist
            ty = rim_y + (ty - rim_y) * max_len / dist
        spread = 0.22
        base = [
            (cx + rx * 0.92 * math.cos(ang - spread), cy + ry * 0.92 * math.sin(ang - spread)),
            (cx + rx * 0.92 * math.cos(ang + spread), cy + ry * 0.92 * math.sin(ang + spread)),
        ]
        draw.polygon([base[0], (tx, ty), base[1]], fill=PAPER, outline=INK, width=4)
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=PAPER, outline=INK, width=5)
    if "tail" in spec:
        # Re-fill the tail joint so the ellipse outline doesn't cut it off.
        draw.polygon([base[0], (tx, ty), base[1]], fill=PAPER)
        draw.line([base[0], (tx, ty)], fill=INK, width=4)
        draw.line([base[1], (tx, ty)], fill=INK, width=4)
    y = cy - text_h / 2 + 4
    for line, bbox in zip(lines, line_sizes):
        w = bbox[2] - bbox[0]
        draw.text((cx - w / 2 - bbox[0], y - bbox[1]), line, font=font, fill=INK)
        y += line_h


def main() -> None:
    specs = json.loads((HERE / "balloons.json").read_text())
    for panel in specs:
        img = Image.open(HERE / panel["image"]).convert("RGBA")
        for balloon in panel["balloons"]:
            draw_balloon(img, balloon)
        out = HERE / panel["out"]
        img.convert("RGB").save(out)
        print(f"lettered {out.name}")


if __name__ == "__main__":
    main()
