"""Write the Berreta Futura brand marks from Inter Display Black outlines.

    uv run --with fonttools --with uharfbuzz tools/logo.py

Writes mag/assets/brand/wordmark.svg, mark.svg, and mark-square.svg. The
construction is specified in mag/assets/brand/README.md; the same font file
always yields the same bytes.
"""

import math
import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "mag/assets/fonts/inter/InterDisplay-Black.ttf"
OUT = ROOT / "mag/assets/brand"
INK, PAPER, RED = "var(--ink, #0a0b0d)", "var(--paper, #ffffff)", "var(--red, #f05738)"
BOX, TILE = "var(--box, #0a0b0d)", "var(--tile, #f05738)"
SLANT = math.tan(math.radians(10))
SIZE, TRACKING, PAD, GAP, STAGGER = 100, -0.02, (0.14, 0.13, 0.14, 0.13), 0.10, 0.7
RED_OFFSET = (-0.12, 0.08)
TT = TTFont(FONT)
GLYPHS = TT.getGlyphSet()
UPEM = TT["head"].unitsPerEm
CAP = TT["OS/2"].sCapHeight
HB = hb.Font(hb.Face(hb.Blob.from_file_path(str(FONT))))


def fmt(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


class Run:
    def __init__(self, text, x, base):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(HB, buf, {"kern": True})
        self.glyphs, pen_x = [], 0.0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            self.glyphs.append((TT.getGlyphName(info.codepoint), pen_x))
            pen_x += pos.x_advance + TRACKING * UPEM
        self.x, self.base, self.s = x, base, SIZE / UPEM
        self.xmin, _, self.xmax, _ = self.bounds()
        self.top = base - CAP * self.s

    def draw(self, pen, g):
        for name, gx in self.glyphs:
            t = g.translate(self.x + gx * self.s, self.base).scale(self.s, -self.s)
            GLYPHS[name].draw(TransformPen(pen, t))

    def d(self, g=Transform()):
        pen = SVGPathPen(GLYPHS, ntos=fmt)
        self.draw(pen, g)
        return pen.getCommands()

    def bounds(self, g=Transform()):
        pen = BoundsPen(GLYPHS)
        self.draw(pen, g)
        return pen.bounds


def wordmark():
    paths, boxes = [], []
    head = Run("BERRETA", 0, 0)
    paths.append((INK, head.d()))
    boxes.append(head.bounds())
    probe = Run("FUTURA", 0, 0)
    box_w = probe.xmax - probe.xmin + (PAD[0] + PAD[2]) * SIZE
    x = head.xmax - box_w * STAGGER + PAD[0] * SIZE - probe.xmin
    tail = Run("FUTURA", x, GAP * SIZE + (CAP / UPEM + PAD[1]) * SIZE)
    left, top = tail.xmin - PAD[0] * SIZE, tail.top - PAD[1] * SIZE
    right, bottom = tail.xmax + PAD[2] * SIZE, tail.base + PAD[3] * SIZE
    mid = (top + bottom) / 2
    skew = Transform(1, 0, -SLANT, 1, SLANT * mid, 0)
    corners = [
        skew.transformPoint(p) for p in ((left, top), (right, top), (right, bottom), (left, bottom))
    ]
    paths.append((BOX, "M" + "L".join(f"{px:.2f} {py:.2f}" for px, py in corners) + "Z"))
    boxes.append((min(c[0] for c in corners), top, max(c[0] for c in corners), bottom))
    cap = CAP * tail.s
    red = Transform().translate(RED_OFFSET[0] * cap, RED_OFFSET[1] * cap).transform(skew)
    for fill, g in ((RED, red), (PAPER, skew)):
        paths.append((fill, tail.d(g)))
        boxes.append(tail.bounds(g))
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    view = f"{x0:.2f} {y0:.2f} {x1 - x0:.2f} {y1 - y0:.2f}"
    body = "".join(f'<path fill="{fill}" d="{d}"/>' for fill, d in paths)
    return svg(view, body)


def outline(ch):
    name = TT.getBestCmap()[ord(ch)]
    pen, bounds = SVGPathPen(GLYPHS), BoundsPen(GLYPHS)
    GLYPHS[name].draw(pen)
    GLYPHS[name].draw(bounds)
    return pen.getCommands(), bounds.bounds


def mark(radius, pad=0.16, overlap=0.15, share=0.80):
    bpath, (bx0, _, bx1, _) = outline("B")
    fpath, (fx0, _, fx1, _) = outline("F")
    box_h, box_w = CAP * (1 + 2 * pad), fx1 - fx0 + 2 * pad * CAP
    box_x = bx1 - bx0 - overlap * CAP
    total_w = box_x + box_w + box_h * SLANT
    s = 512 * share / max(total_w, box_h)
    ox, oy = (512 - total_w * s) / 2, (512 + box_h * s) / 2

    def at(x, y):
        return f"translate({ox + x * s:.2f} {oy + y * s:.2f}) scale({s:.5f} {-s:.5f})"

    skew = f"{at(box_x, 0)} matrix(1 0 {SLANT:.6f} 1 0 0)"
    body = (
        f'<rect width="512" height="512" rx="{512 * radius:.0f}" fill="{TILE}"/>'
        f'<path fill="{BOX}" transform="{skew}" d="M0 0H{box_w:.1f}V{box_h:.1f}H0Z"/>'
        f'<path fill="{PAPER}" transform="{skew} translate({pad * CAP - fx0:.1f} {pad * CAP:.1f})"'
        f' d="{fpath}"/>'
        f'<path fill="{PAPER}" transform="{at(-bx0, -(box_h - CAP) / 2)}" d="{bpath}"/>'
    )
    return svg("0 0 512 512", body)


def svg(view, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" role="img"'
        f' aria-label="Berreta Futura"><title>Berreta Futura</title>{body}</svg>\n'
    )


def main():
    if sys.argv[1:]:
        raise SystemExit(__doc__)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "wordmark.svg").write_text(wordmark())
    (OUT / "mark.svg").write_text(mark(0.2))
    (OUT / "mark-square.svg").write_text(mark(0.0))


if __name__ == "__main__":
    main()
