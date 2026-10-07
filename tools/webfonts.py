#!/usr/bin/env python3
"""webfonts.py: subset the site fonts to woff2, deterministically.

Usage: uv run --with fonttools --with brotli tools/webfonts.py

Writes mag/assets/fonts/web/*.woff2 from mag/assets/fonts/*/*.ttf. Same input,
same bytes. Also writes coverage.txt, one line per CSS font stack (serif,
display, sans, poster, mono): the code points that stack renders, Noto clipped
to its unicode-range. `mag site` refuses a page whose text a stack lacks.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent / "mag" / "assets" / "fonts"
OUT = ROOT / "web"

TEXT = [
    "geist/Geist-Variable.ttf",
    "geist/Geist-Italic-Variable.ttf",
    "geist-mono/GeistMono-Regular.ttf",
]
SYMBOLS = ["noto-sans-math/NotoSansMath-Regular.ttf"]
EMOJI = "noto-emoji/NotoEmoji-Variable.ttf"

LATIN = [(0x20, 0x7E), (0xA0, 0x17F), (0x2000, 0x206F), (0x20A0, 0x20CF), (0x2122, 0x2122)]
ARROWS_AND_SHAPES = [(0x2190, 0x21FF), (0x2200, 0x22FF), (0x25A0, 0x25FF)]
EMOJI_RANGES = [(0x2600, 0x27BF), (0xFE00, 0xFE0F), (0x1F300, 0x1FAFF)]
FEATURES = ["kern", "liga", "calt", "ccmp", "locl", "mark", "mkmk", "case", "lnum", "onum", "tnum"]


def codepoints(ranges):
    return [c for lo, hi in ranges for c in range(lo, hi + 1)]


def build(source: Path, ranges) -> Path:
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = FEATURES
    options.hinting = False
    options.notdef_outline = True
    options.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14]
    options.name_languages = [0x409]
    options.drop_tables += ["DSIG", "meta"]
    font = TTFont(source, recalcTimestamp=False)
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=codepoints(ranges))
    subsetter.subset(font)
    target = OUT / (source.stem + ".woff2")
    subset.save_font(font, str(target), options)
    return target


def runs_of(codepoints) -> str:
    runs = []
    for cp in sorted(codepoints):
        if runs and cp == runs[-1][1] + 1:
            runs[-1][1] = cp
        else:
            runs.append([cp, cp])
    return " ".join(f"{lo:04X}-{hi:04X}" for lo, hi in runs)


def coverage() -> str:
    def cmap(name, ranges=None):
        found = set(TTFont(OUT / (Path(name).stem + ".woff2")).getBestCmap())
        return found & set(codepoints(ranges)) if ranges else found

    sans = [cmap(n) for n in TEXT[:2]]
    stacks = {"serif": sans, "display": sans, "sans": sans, "poster": sans, "mono": [cmap(TEXT[2])]}
    math = cmap(SYMBOLS[0], ARROWS_AND_SHAPES)
    emoji = cmap(EMOJI, EMOJI_RANGES)
    return "".join(f"{k}: {runs_of(set().union(*v, math, emoji))}\n" for k, v in stacks.items())


def main() -> None:
    if len(sys.argv) > 1:
        raise SystemExit(__doc__)
    OUT.mkdir(exist_ok=True)
    targets = [build(ROOT / name, LATIN + ARROWS_AND_SHAPES) for name in TEXT]
    targets += [build(ROOT / name, ARROWS_AND_SHAPES) for name in SYMBOLS]
    targets.append(build(ROOT / EMOJI, EMOJI_RANGES))
    for target in targets:
        print(f"{target.name}: {target.stat().st_size}")
    (OUT / "coverage.txt").write_text(coverage())


if __name__ == "__main__":
    main()
