#!/usr/bin/env python3
"""Create a numbered contact sheet from rendered PDF page PNGs."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pattern", help="Glob pattern for input PNG pages")
    parser.add_argument("output", type=Path)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--thumb-width", type=int, default=300)
    args = parser.parse_args()

    paths = sorted(Path.cwd().glob(args.pattern))
    if not paths:
        raise SystemExit(f"No pages matched {args.pattern!r}")
    thumbs: list[Image.Image] = []
    label_height = 28
    for path in paths:
        with Image.open(path) as source:
            image = source.convert("RGB")
            height = round(image.height * args.thumb_width / image.width)
            image.thumbnail((args.thumb_width, height), Image.Resampling.LANCZOS)
            thumbs.append(image.copy())
    cell_width = args.thumb_width + 24
    cell_height = max(image.height for image in thumbs) + label_height + 24
    rows = math.ceil(len(thumbs) / args.columns)
    sheet = Image.new("RGB", (cell_width * args.columns, cell_height * rows), "#d8d4ca")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (path, image) in enumerate(zip(paths, thumbs, strict=True)):
        column, row = index % args.columns, index // args.columns
        x = column * cell_width + (cell_width - image.width) // 2
        y = row * cell_height + label_height
        sheet.paste(image, (x, y))
        draw.text((column * cell_width + 12, 8), f"{index + 1:02d}  {path.name}", fill="#181818", font=font)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output, optimize=True)


if __name__ == "__main__":
    main()

