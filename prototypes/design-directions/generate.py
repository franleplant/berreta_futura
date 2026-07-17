"""PROTOTYPE: regenerate the archived A5 design directions for comparison."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.pagesizes import A5
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PREVIEWS = HERE / "previews"
W, H = A5

INK = (0.055, 0.075, 0.085)
PAPER = (0.982, 0.965, 0.91)
WHITE = (1, 1, 1)
OXBLOOD = (0.48, 0.10, 0.095)
COBALT = (0.06, 0.20, 0.42)
ORANGE = (0.93, 0.31, 0.08)
LILAC = (0.59, 0.53, 0.76)
SAND = (0.83, 0.78, 0.67)
SLATE = (0.31, 0.35, 0.37)
FOREST = (0.07, 0.29, 0.21)
SKY = (0.52, 0.72, 0.82)
YELLOW = (0.96, 0.72, 0.08)
BLUSH = (0.88, 0.68, 0.64)
VIOLET = (0.25, 0.10, 0.43)
ACID = (0.68, 0.86, 0.08)
COOL_GRAY = (0.88, 0.89, 0.90)

SERIF = "SourceSerif4-SmText"
SERIF_ITALIC = "SourceSerif4-SmText-Italic"
SERIF_BOLD = "SourceSerif4-SmText-Bold"
DISPLAY = "SourceSerif4-Display-Semibold"
SANS = "Inter"
SANS_MEDIUM = "Inter-Medium"
SANS_SEMIBOLD = "Inter-Semibold"
SANS_BOLD = "Inter-Bold"


@dataclass(frozen=True)
class Direction:
    key: str
    slug: str
    name: str


DIRECTIONS = (
    Direction("A", "a-quiet-axis", "Quiet Axis"),
    Direction("B", "b-field-notes", "Field Notes"),
    Direction("C", "c-signal---noise", "Signal / Noise"),
    Direction("D", "d-swiss-ledger", "Swiss Ledger"),
    Direction("E", "e-object-study", "Object Study"),
    Direction("F", "f-newsprint-club", "Newsprint Club"),
    Direction("G", "g-gallery-white", "Gallery White"),
    Direction("H", "h-chromatic-fold", "Chromatic Fold"),
    Direction("I", "i-measured-wonder", "Measured Wonder"),
    Direction("J", "j-the-red-thread", "The Red Thread"),
    Direction("K", "k-cabinet-of-futures", "Cabinet of Futures"),
    Direction("L", "l-scale-shift", "Scale Shift"),
    Direction("M", "m-three-apertures", "Three Apertures"),
    Direction("N", "n-salon", "Salon"),
    Direction("O", "o-monument", "Monument"),
    Direction("P", "p-paired-rooms", "Paired Rooms"),
)


def register_fonts() -> None:
    root = ROOT / "src/magazine/assets/fonts"
    fonts = {
        SANS: root / "inter/Inter-Regular.ttf",
        SANS_MEDIUM: root / "inter/Inter-Medium.ttf",
        SANS_SEMIBOLD: root / "inter/Inter-SemiBold.ttf",
        SANS_BOLD: root / "inter/Inter-Bold.ttf",
        SERIF: root / "source-serif-4/SourceSerif4SmText-Regular.ttf",
        SERIF_ITALIC: root / "source-serif-4/SourceSerif4SmText-It.ttf",
        SERIF_BOLD: root / "source-serif-4/SourceSerif4SmText-Bold.ttf",
        DISPLAY: root / "source-serif-4/SourceSerif4Display-Semibold.ttf",
    }
    registered = set(pdfmetrics.getRegisteredFontNames())
    for name, path in fonts.items():
        if name not in registered:
            pdfmetrics.registerFont(TTFont(name, path))


def clean_markdown(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        text = text.split("\n---\n", 1)[1]
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,3} .+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_`]", "", text)
    return [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


EDITORIAL = clean_markdown(ROOT / "editions/001-the-work-left-to-us/manuscript/editorial.md")
ARTICLE = clean_markdown(ROOT / "editions/001-the-work-left-to-us/articles/narayanan-what-will-be-left.md")


def color(c: canvas.Canvas, rgb: tuple[float, float, float], *, stroke: bool = False) -> None:
    (c.setStrokeColorRGB if stroke else c.setFillColorRGB)(*rgb)


def wrap(text: str, font: str, size: float, width: float) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.replace("—", "--").replace("“", '"').replace("”", '"').split():
        proposed = f"{current} {word}".strip()
        if current and pdfmetrics.stringWidth(proposed, font, size) > width:
            lines.append(current)
            current = word
        else:
            current = proposed
    if current:
        lines.append(current)
    return lines


def text_lines(c: canvas.Canvas, text: str, x: float, y: float, width: float, font: str, size: float, leading: float, rgb=INK, max_lines: int | None = None) -> float:
    color(c, rgb)
    c.setFont(font, size)
    lines = wrap(text, font, size, width)
    if max_lines:
        lines = lines[:max_lines]
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def fitted_title(c: canvas.Canvas, text: str, x: float, top: float, width: float, height: float, *, font: str, maximum: float, minimum: float, rgb=INK, leading_ratio: float = 1.0) -> float:
    """Draw a title inside a fixed zone and return its next safe baseline."""
    size = maximum
    while size > minimum:
        lines = wrap(text, font, size, width)
        if len(lines) * size * leading_ratio <= height:
            break
        size -= .5
    leading = size * leading_ratio
    color(c, rgb); c.setFont(font, size)
    y = top - size
    for line in wrap(text, font, size, width):
        c.drawString(x, y, line); y -= leading
    return y


def rule(c: canvas.Canvas, x1: float, y: float, x2: float, rgb=SAND, width: float = .55) -> None:
    color(c, rgb, stroke=True); c.setLineWidth(width); c.line(x1, y, x2, y)


# Round three uses a real, mirrored page system rather than unrelated coordinates.
BASE = 3.15
BODY_SIZE = 9.55
BODY_LEADING = BASE * 4
CAPTION_SIZE = 7.0
CAPTION_LEADING = BASE * 3


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y + self.height

    def intersects(self, other: "Box", gap: float = 0) -> bool:
        return not (
            self.right + gap <= other.x
            or other.right + gap <= self.x
            or self.top + gap <= other.y
            or other.top + gap <= self.y
        )


class Round3Page:
    """Binding-aware six-column page with explicit collision reservations."""

    def __init__(self, c: canvas.Canvas, number: int, name: str, accent) -> None:
        self.c = c
        self.number = number
        self.name = name
        self.accent = accent
        self.inner = 44
        self.outer = 34
        self.left = self.inner if number % 2 else self.outer
        self.right = self.outer if number % 2 else self.inner
        self.live_width = W - self.left - self.right
        self.gutter = BASE * 3
        self.column_width = (self.live_width - self.gutter * 5) / 6
        self.reservations: list[tuple[str, Box]] = []

    def columns(self, start: int, span: int, y: float, height: float) -> Box:
        x = self.left + start * (self.column_width + self.gutter)
        width = span * self.column_width + (span - 1) * self.gutter
        return Box(x, y, width, height)

    def reserve(self, label: str, box: Box, *, gap: float = BASE) -> Box:
        if box.x < 0 or box.y < 0 or box.right > W or box.top > H:
            raise ValueError(f"{self.name} page {self.number}: {label} escapes the page: {box}")
        for other_label, other in self.reservations:
            if box.intersects(other, gap):
                raise ValueError(
                    f"{self.name} page {self.number}: {label} collides with {other_label}: "
                    f"{box} / {other}"
                )
        self.reservations.append((label, box))
        return box

    def folio(self) -> None:
        box = self.reserve("folio", Box(self.left, 17, self.live_width, 18), gap=0)
        color(self.c, self.accent); self.c.setLineWidth(.8)
        outer_x = self.left if self.number % 2 == 0 else W - self.right
        self.c.line(outer_x, box.top, outer_x + (16 if self.number % 2 == 0 else -16), box.top)
        color(self.c, INK); self.c.setFont(SANS_MEDIUM, CAPTION_SIZE)
        if self.number % 2 == 0:
            self.c.drawString(self.left, box.y, f"{self.number:02d}")
            self.c.drawRightString(W - self.right, box.y, f"BERRETA FUTURA / {self.name.upper()}")
        else:
            self.c.drawString(self.left, box.y, f"BERRETA FUTURA / {self.name.upper()}")
            self.c.drawRightString(W - self.right, box.y, f"{self.number:02d}")


def draw_manual_title(page: Round3Page, label: str, lines: list[str], box: Box, *, font: str, size: float, leading: float, rgb=INK, align: str = "left") -> None:
    page.reserve(label, box)
    if size + (len(lines) - 1) * leading > box.height:
        raise ValueError(f"{page.name} page {page.number}: {label} is taller than its box")
    for line in lines:
        if pdfmetrics.stringWidth(line, font, size) > box.width:
            raise ValueError(f"{page.name} page {page.number}: {label} line is wider than its box: {line}")
    color(page.c, rgb); page.c.setFont(font, size)
    baseline = box.top - size
    for line in lines:
        if align == "right":
            page.c.drawRightString(box.right, baseline, line)
        else:
            page.c.drawString(box.x, baseline, line)
        baseline -= leading


def draw_copy_box(page: Round3Page, label: str, values: list[str], box: Box, *, font=SERIF, size=BODY_SIZE, leading=BODY_LEADING, rgb=INK, paragraph_gap: float = BASE * 2) -> None:
    page.reserve(label, box)
    wrapped = [wrap(value, font, size, box.width) for value in values]
    required = sum(len(lines) * leading for lines in wrapped) + paragraph_gap * max(0, len(values) - 1)
    if required > box.height:
        raise ValueError(
            f"{page.name} page {page.number}: {label} needs {required:.1f} pt, has {box.height:.1f} pt"
        )
    color(page.c, rgb); page.c.setFont(font, size)
    baseline = box.top - size
    for paragraph_index, lines in enumerate(wrapped):
        for line in lines:
            page.c.drawString(box.x, baseline, line)
            baseline -= leading
        if paragraph_index < len(wrapped) - 1:
            baseline -= paragraph_gap


def draw_two_column_flow(page: Round3Page, label: str, values: list[str], box: Box, *, font=SERIF, size=BODY_SIZE, leading=BODY_LEADING, rgb=INK, gutter: float = BASE * 4) -> None:
    page.reserve(label, box)
    column_width = (box.width - gutter) / 2
    flow: list[str | None] = []
    for index, value in enumerate(values):
        flow.extend(wrap(value, font, size, column_width))
        if index < len(values) - 1:
            flow.append(None)
    capacity = int(box.height // leading)
    if len(flow) > capacity * 2:
        raise ValueError(
            f"{page.name} page {page.number}: {label} needs {len(flow)} lines, has {capacity * 2}"
        )
    split = (len(flow) + 1) // 2
    if split > capacity:
        raise ValueError(
            f"{page.name} page {page.number}: {label} needs {split} lines per balanced column, has {capacity}"
        )
    color(page.c, rgb); page.c.setFont(font, size)
    for index, line in enumerate(flow):
        column = 0 if index < split else 1
        row = index if column == 0 else index - split
        if line is None:
            continue
        x = box.x + column * (column_width + gutter)
        y = box.top - size - row * leading
        page.c.drawString(x, y, line)


def draw_label_box(page: Round3Page, label: str, text: str, box: Box, *, rgb=INK, font=SANS_MEDIUM, align: str = "left") -> None:
    page.reserve(label, box)
    lines = wrap(text.upper(), font, CAPTION_SIZE, box.width)
    if len(lines) * CAPTION_LEADING > box.height:
        raise ValueError(f"{page.name} page {page.number}: {label} overflows")
    color(page.c, rgb); page.c.setFont(font, CAPTION_SIZE)
    baseline = box.top - CAPTION_SIZE
    for line in lines:
        if align == "right":
            page.c.drawRightString(box.right, baseline, line)
        else:
            page.c.drawString(box.x, baseline, line)
        baseline -= CAPTION_LEADING


def draw_tracked_label(page: Round3Page, label: str, text: str, box: Box, *, rgb=INK, tracking: float = .45, align: str = "left") -> None:
    page.reserve(label, box)
    value = text.upper()
    widths = [pdfmetrics.stringWidth(character, SANS_MEDIUM, CAPTION_SIZE) for character in value]
    total = sum(widths) + tracking * max(0, len(value) - 1)
    if total > box.width:
        raise ValueError(f"{page.name} page {page.number}: {label} tracked text overflows")
    x = box.right - total if align == "right" else box.x
    color(page.c, rgb); page.c.setFont(SANS_MEDIUM, CAPTION_SIZE)
    baseline = box.top - CAPTION_SIZE
    for character, width in zip(value, widths, strict=True):
        page.c.drawString(x, baseline, character)
        x += width + tracking


def draw_rotated_label(page: Round3Page, label: str, text: str, box: Box, *, rgb=INK, tracking: float = .35) -> None:
    page.reserve(label, box)
    value = text.upper()
    widths = [pdfmetrics.stringWidth(character, SANS_MEDIUM, CAPTION_SIZE) for character in value]
    total = sum(widths) + tracking * max(0, len(value) - 1)
    if total > box.height:
        raise ValueError(f"{page.name} page {page.number}: {label} rotated text overflows")
    color(page.c, rgb); page.c.setFont(SANS_MEDIUM, CAPTION_SIZE)
    page.c.saveState(); page.c.translate(box.x + CAPTION_SIZE, box.y); page.c.rotate(90)
    x = 0
    for character, width in zip(value, widths, strict=True):
        page.c.drawString(x, 0, character)
        x += width + tracking
    page.c.restoreState()


def paragraphs(c: canvas.Canvas, values: list[str], x: float, y: float, width: float, *, font=SERIF, size=9.6, leading=13, rgb=INK, bottom=44, columns=1, gutter=18, column_top: float | None = None) -> None:
    column_width = (width - gutter * (columns - 1)) / columns
    column = 0
    reset_y = y if column_top is None else column_top
    for paragraph in values:
        lines = wrap(paragraph, font, size, column_width)
        needed = len(lines) * leading + 8
        if y - needed < bottom and column < columns - 1:
            column += 1
            y = reset_y
        if y - needed < bottom:
            break
        color(c, rgb); c.setFont(font, size)
        px = x + column * (column_width + gutter)
        for line in lines:
            c.drawString(px, y, line); y -= leading
        y -= 8


def folio(c: canvas.Canvas, number: int, name: str, accent=OXBLOOD) -> None:
    color(c, accent); c.rect(34, 25, 12, 3, fill=1, stroke=0)
    color(c, SLATE); c.setFont(SANS_MEDIUM, 6.2)
    c.drawString(51, 23, f"BERRETA FUTURA / {name.upper()}")
    c.drawRightString(W - 34, 23, f"{number:02d}")


def cover_art_a(c: canvas.Canvas) -> None:
    path = ROOT / "editions/001-the-work-left-to-us/art/cover-art.png"
    image = ImageReader(path); iw, ih = image.getSize()
    scale = max(W / iw, H / ih)
    c.drawImage(image, (W - iw * scale) / 2, (H - ih * scale) / 2, iw * scale, ih * scale, preserveAspectRatio=True, mask="auto")


def cover_art_b(c: canvas.Canvas) -> None:
    color(c, PAPER); c.rect(0, 0, W, H, fill=1, stroke=0)
    color(c, SAND, stroke=True); c.setLineWidth(.35)
    for x in range(-30, int(W) + 30, 27): c.line(x, 0, x, H)
    for y in range(-20, int(H) + 20, 27): c.line(0, y, W, y)
    color(c, COBALT); c.rect(W * .48, -10, W * .39, H * 1.08, fill=1, stroke=0)
    color(c, PAPER); c.circle(W * .675, H * .56, 66, fill=1, stroke=0)
    color(c, ORANGE); c.circle(W * .675, H * .56, 31, fill=1, stroke=0)
    color(c, INK, stroke=True); c.setLineWidth(1.1)
    c.line(22, H * .26, W - 18, H * .73); c.line(38, H * .83, W - 8, H * .42)
    for x, y in ((38, H*.83), (W*.675, H*.56), (W-34, H*.69), (82, H*.36)):
        color(c, WHITE); c.circle(x, y, 5, fill=1, stroke=0); color(c, INK, stroke=True); c.circle(x, y, 5, fill=0, stroke=1)


def cover_art_c(c: canvas.Canvas) -> None:
    color(c, PAPER); c.rect(0, 0, W, H, fill=1, stroke=0)
    color(c, ORANGE); c.circle(W * .72, H * .72, 142, fill=1, stroke=0)
    color(c, LILAC); c.rect(-34, H * .18, W * .67, H * .63, fill=1, stroke=0)
    c.saveState(); c.translate(W * .32, H * .17); c.rotate(12)
    color(c, INK); c.rect(0, 0, 63, H * .76, fill=1, stroke=0)
    c.restoreState()
    color(c, PAPER)
    for y in range(84, int(H * .78), 23): c.rect(W * .30, y, W * .42, 6, fill=1, stroke=0)


def cover(c: canvas.Canvas, direction: Direction) -> None:
    {"A": cover_art_a, "B": cover_art_b, "C": cover_art_c}[direction.key](c)
    if direction.key == "A":
        color(c, PAPER); c.setFillAlpha(.94); c.rect(0, H - 226, W, 226, fill=1, stroke=0); c.setFillAlpha(1)
        x, y, ink, accent, display = 34, H - 32, INK, OXBLOOD, DISPLAY
    elif direction.key == "B":
        color(c, PAPER); c.rect(22, 20, W * .42, H - 40, fill=1, stroke=0)
        x, y, ink, accent, display = 33, H - 34, INK, ORANGE, SANS_BOLD
    else:
        color(c, PAPER); c.rect(0, H - 198, W, 198, fill=1, stroke=0)
        x, y, ink, accent, display = 30, H - 29, INK, ORANGE, SANS_BOLD
    color(c, ink); c.setFont(SANS_BOLD, 9); c.drawString(x, y, "BERRETA FUTURA")
    color(c, accent); c.rect(W - 60, y - 3, 28, 5, fill=1, stroke=0)
    title_size = 25 if direction.key == "B" else (34 if direction.key == "C" else 30)
    title_width = W * .42 - x - 12 if direction.key == "B" else W - x - 42
    title_y = y - 45; color(c, ink); c.setFont(display, title_size)
    for line in wrap("The Work Left to Us", display, title_size, title_width):
        c.drawString(x, title_y, line); title_y -= title_size * .98
    title_y -= 8
    title_y = text_lines(c, "Work, agency, ownership, and governance in the age of capable machines", x, title_y, title_width, SANS, 8.2, 10.4, ink)
    color(c, ink); c.setFont(SANS_SEMIBOLD, 6.5); c.drawString(x, 26, "ISSUE 001  /  16 JULY 2026")


def contents(c: canvas.Canvas, direction: Direction) -> None:
    accent = {"A": OXBLOOD, "B": ORANGE, "C": LILAC}[direction.key]
    color(c, WHITE); c.rect(0, 0, W, H, fill=1, stroke=0)
    if direction.key == "A":
        color(c, INK); c.rect(0, H - 122, W, 122, fill=1, stroke=0); color(c, PAPER); c.setFont(DISPLAY, 29); c.drawString(38, H - 76, "Contents")
        x, y, width = 40, H - 157, W - 80
    elif direction.key == "B":
        color(c, COBALT); c.rect(0, 0, 78, H, fill=1, stroke=0); color(c, PAPER); c.setFont(SANS_BOLD, 7); c.saveState(); c.translate(34, 46); c.rotate(90); c.drawString(0, 0, "CONTENTS / FIELD NOTES / ISSUE 001"); c.restoreState()
        color(c, INK); c.setFont(SANS_BOLD, 31); c.drawString(106, H - 62, "INDEX")
        x, y, width = 106, H - 105, W - 142
    else:
        color(c, ORANGE); c.rect(0, H - 26, W, 26, fill=1, stroke=0); color(c, INK); c.setFont(SANS_BOLD, 45); c.drawString(28, H - 84, "IN/") ; c.drawString(28, H - 125, "DEX")
        x, y, width = 30, H - 167, W - 60
    entries = [
        ("02", "Editorial", "The Last Mile Is the Whole World", "The editors"),
        ("03", "Feature 01", "What will be left for us to work on?", "Arvind Narayanan"),
        ("06", "Feature 02", "DSLs Enable Reliable Use of LLMs", "Unmesh Joshi"),
        ("11", "Feature 03", "The Reverse Information Paradox", "Satya Nadella"),
        ("15", "Feature 04", "A Framework for Frontier AI", "Demis Hassabis"),
    ]
    for page, label, title, author in entries:
        color(c, accent); c.setFont(SANS_BOLD, 6.2); c.drawString(x, y, label.upper()); c.drawRightString(x + width, y, page)
        y -= 13; color(c, INK); c.setFont(DISPLAY if direction.key == "A" else SANS_SEMIBOLD, 10.5)
        for line in wrap(title, DISPLAY if direction.key == "A" else SANS_SEMIBOLD, 10.5, width - 24)[:2]: c.drawString(x, y, line); y -= 12
        color(c, SLATE); c.setFont(SANS, 6.2); c.drawString(x, y, author.upper()); y -= 25
    folio(c, 2, direction.name, accent)


def opener(c: canvas.Canvas, direction: Direction, *, editorial: bool) -> None:
    accent = {"A": OXBLOOD, "B": ORANGE, "C": LILAC}[direction.key]
    color(c, WHITE); c.rect(0, 0, W, H, fill=1, stroke=0)
    label = "ORIGINAL EDITORIAL" if editorial else "FEATURE 01 / FAITHFUL SYNTHESIS"
    title = "The Last Mile Is the Whole World" if editorial else "What will be left for us to work on?"
    author = "THE EDITORS" if editorial else "ARVIND NARAYANAN"
    copy = EDITORIAL if editorial else ARTICLE
    if direction.key == "A":
        x, width, y = 40, W - 78, H - 57; color(c, accent); c.rect(x, y + 7, 25, 3, fill=1, stroke=0); color(c, accent); c.setFont(SANS_BOLD, 6.5); c.drawString(x + 32, y + 4, label)
        y -= 38; y = text_lines(c, title, x, y, width, DISPLAY, 28, 28, INK); y -= 9
        color(c, INK); c.setFont(SANS_BOLD, 7); c.drawString(x, y, author); y -= 23
        color(c, SAND, stroke=True); c.line(x, y, x + width, y); y -= 22
        y = text_lines(c, copy[0], x, y, width, SERIF, 11.3, 15.2, INK, 8)
    elif direction.key == "B":
        color(c, COBALT); c.rect(0, 0, 76, H, fill=1, stroke=0); color(c, PAPER); c.setFont(SANS_BOLD, 6.5); c.saveState(); c.translate(34, 43); c.rotate(90); c.drawString(0, 0, label); c.restoreState()
        x, width, y = 104, W - 138, H - 56; color(c, accent); c.setFont(SANS_BOLD, 7); c.drawString(x, y, "01 / 04"); y -= 32
        y = text_lines(c, title, x, y, width, SANS_BOLD, 24, 24, INK); y -= 12
        color(c, INK); c.setFont(SANS_BOLD, 7); c.drawString(x, y, author); y -= 25
        y = text_lines(c, copy[0], x, y, width, SERIF, 10.2, 13.8, INK, 10)
    else:
        color(c, accent); c.rect(0, H - 53, W, 53, fill=1, stroke=0); color(c, INK); c.setFont(SANS_BOLD, 7); c.drawString(30, H - 31, label)
        x, width, y = 30, W - 60, H - 91; y = text_lines(c, title.upper(), x, y, width, SANS_BOLD, 27, 25, INK); y -= 14
        color(c, ORANGE); c.rect(x, y, width * .38, 7, fill=1, stroke=0); y -= 22
        color(c, INK); c.setFont(SANS_BOLD, 7); c.drawString(x, y, author); y -= 25
        y = text_lines(c, copy[0], x + 42, y, width - 42, SERIF, 11, 14.7, INK, 9)
        color(c, accent); c.setFont(SANS_BOLD, 45); c.drawString(x - 5, y + 17, "01")
    folio(c, 3 if editorial else 4, direction.name, accent)


def continuation(c: canvas.Canvas, direction: Direction) -> None:
    accent = {"A": OXBLOOD, "B": ORANGE, "C": LILAC}[direction.key]
    color(c, WHITE); c.rect(0, 0, W, H, fill=1, stroke=0)
    if direction.key == "A":
        color(c, accent); c.rect(40, H - 31, 5, 5, fill=1, stroke=0); color(c, SLATE); c.setFont(SANS_MEDIUM, 6.2); c.drawString(53, H - 29, "BERRETA FUTURA / ISSUE 001"); c.drawRightString(W - 38, H - 29, "AMPLIFICATION OR REPLACEMENT")
        color(c, SAND, stroke=True); c.line(40, H - 39, W - 38, H - 39)
        paragraphs(c, ARTICLE[1:6], 40, H - 63, W - 78, size=9.6, leading=12.9)
    elif direction.key == "B":
        color(c, COBALT); c.rect(0, H - 44, W, 44, fill=1, stroke=0); color(c, PAPER); c.setFont(SANS_BOLD, 7); c.drawString(30, H - 27, "01  /  CAPABILITY IS NOT DEPLOYMENT"); color(c, ORANGE); c.circle(W - 34, H - 24, 6, fill=1, stroke=0)
        paragraphs(c, ARTICLE[1:7], 30, H - 70, W - 60, size=8.9, leading=12, columns=2, gutter=17)
    else:
        color(c, INK); c.setFont(SANS_BOLD, 6.5); c.drawString(30, H - 29, "BERRETA FUTURA"); c.drawRightString(W - 30, H - 29, "THE WORK SHIFTS TOWARD EVALUATION")
        color(c, accent); c.rect(30, H - 42, W - 60, 4, fill=1, stroke=0)
        color(c, ORANGE); c.setFont(SANS_BOLD, 51); c.drawString(25, H - 101, "05")
        paragraphs(c, ARTICLE[1:6], 91, H - 67, W - 121, size=9.7, leading=13.15)
    folio(c, 5, direction.name, accent)


def back(c: canvas.Canvas, direction: Direction) -> None:
    accent = {"A": OXBLOOD, "B": ORANGE, "C": LILAC}[direction.key]
    color(c, PAPER); c.rect(0, 0, W, H, fill=1, stroke=0)
    if direction.key == "B":
        color(c, COBALT); c.rect(0, 0, 82, H, fill=1, stroke=0)
        color(c, PAPER); c.setFont(SANS_BOLD, 31); c.saveState(); c.translate(52, 44); c.rotate(90); c.drawString(0, 0, "KEEP / TEST / GOVERN"); c.restoreState(); x, width = 108, W - 145
    elif direction.key == "C":
        color(c, ORANGE); c.circle(W - 24, H - 30, 118, fill=1, stroke=0); color(c, LILAC); c.rect(0, 0, W, 83, fill=1, stroke=0); x, width = 38, W - 76
    else:
        color(c, accent); c.rect(0, H - 15, W, 15, fill=1, stroke=0); x, width = 45, W - 90
    y = H * .62
    y = text_lines(c, "Intelligence does not govern itself. The boundaries we build around it will decide who learns, who owns, and who answers.", x, y, width, DISPLAY if direction.key == "A" else SANS_BOLD, 17 if direction.key != "C" else 20, 21, INK)
    color(c, accent if direction.key != "C" else INK); c.rect(x, 57, width, 1, fill=1, stroke=0)
    color(c, INK); c.setFont(SANS_BOLD, 6.4); c.drawString(x, 39, "BERRETA FUTURA  /  ISSUE 001")
    c.setFont(SANS, 6.4); c.drawString(x, 25, "BERRETA FUTURA / ISSUE 001 / THE WORK LEFT TO US")


def framed_art(c: canvas.Canvas, x: float, y: float, width: float, height: float, *, crop_x: float = .5, crop_y: float = .5) -> None:
    """Place the existing art inside a hard frame, independent from cover type."""
    image = ImageReader(ROOT / "editions/001-the-work-left-to-us/art/cover-art.png")
    iw, ih = image.getSize()
    scale = max(width / iw, height / ih)
    draw_width, draw_height = iw * scale, ih * scale
    path = c.beginPath(); path.rect(x, y, width, height)
    c.saveState(); c.clipPath(path, stroke=0)
    c.drawImage(
        image,
        x - (draw_width - width) * crop_x,
        y - (draw_height - height) * crop_y,
        draw_width,
        draw_height,
        preserveAspectRatio=True,
        mask="auto",
    )
    c.restoreState()


def print_safe_art(page: Round3Page, label: str, box: Box, *, crop_x: float = .5, crop_y: float = .5, circle: bool = False) -> float:
    """Place art at 300+ effective ppi and register its collision box."""
    page.reserve(label, box)
    image = ImageReader(ROOT / "editions/001-the-work-left-to-us/art/cover-art.png")
    iw, ih = image.getSize()
    scale = max(box.width / iw, box.height / ih)
    effective_ppi = 72 / scale
    if effective_ppi < 300:
        raise ValueError(
            f"{page.name} page {page.number}: {label} is only {effective_ppi:.1f} effective ppi"
        )
    draw_width, draw_height = iw * scale, ih * scale
    path = page.c.beginPath()
    if circle:
        if abs(box.width - box.height) > .1:
            raise ValueError("Circular art boxes must be square")
        path.circle(box.x + box.width / 2, box.y + box.height / 2, box.width / 2)
    else:
        path.rect(box.x, box.y, box.width, box.height)
    page.c.saveState(); page.c.clipPath(path, stroke=0)
    page.c.drawImage(
        image,
        box.x - (draw_width - box.width) * crop_x,
        box.y - (draw_height - box.height) * crop_y,
        draw_width,
        draw_height,
        preserveAspectRatio=True,
        mask="auto",
    )
    page.c.restoreState()
    return effective_ppi


def cover_new(c: canvas.Canvas, direction: Direction) -> None:
    key = direction.key
    color(c, PAPER if key in {"D", "F", "H"} else WHITE); c.rect(0, 0, W, H, fill=1, stroke=0)
    if key == "D":
        color(c, SAND, stroke=True); c.setLineWidth(.35)
        for x in (30, 102, 174, 246, 318, 390): c.line(x, 0, x, H)
        for y in range(40, 401, 40): c.line(0, y, W, y)
        color(c, OXBLOOD); c.rect(0, 0, 174, 180, fill=1, stroke=0)
        color(c, INK); c.rect(246, 42, 72, 260, fill=1, stroke=0)
        color(c, WHITE); c.circle(282, 210, 22, fill=1, stroke=0)
        color(c, INK); c.setFont(SANS_BOLD, 9); c.drawString(30, H - 30, "BERRETA FUTURA")
        color(c, OXBLOOD); c.setFont(SANS_BOLD, 7); c.drawRightString(W - 30, H - 30, "ISSUE 001 / PRIVATE")
        fitted_title(c, "The Work Left to Us", 30, H - 68, W - 60, 150, font=SANS_BOLD, maximum=35, minimum=27)
    elif key == "E":
        framed_art(c, 106, 156, W - 140, 345, crop_x=.58, crop_y=.52)
        color(c, INK, stroke=True); c.setLineWidth(.7); c.rect(106, 156, W - 140, 345, fill=0, stroke=1)
        color(c, INK); c.setFont(SANS_BOLD, 8); c.saveState(); c.translate(35, 42); c.rotate(90); c.drawString(0, 0, "BERRETA FUTURA / ISSUE 001 / OBJECT STUDY"); c.restoreState()
        color(c, SLATE); c.setFont(SANS, 6.2); c.drawString(106, 143, "FIG. 01 — WORK, SYSTEMS, INSTITUTIONS")
        fitted_title(c, "The Work Left to Us", 106, 125, W - 140, 82, font=DISPLAY, maximum=25, minimum=20)
    elif key == "F":
        color(c, INK); c.rect(0, H - 55, W, 55, fill=1, stroke=0)
        color(c, PAPER); c.setFont(SANS_BOLD, 10); c.drawString(27, H - 34, "BERRETA FUTURA")
        color(c, FOREST); c.rect(0, 0, W, 205, fill=1, stroke=0)
        color(c, INK)
        for row in range(7):
            for col in range(14):
                radius = 2 + ((row + col) % 4)
                c.circle(18 + col * 31, 21 + row * 27, radius, fill=1, stroke=0)
        color(c, FOREST); c.setFont(SANS_BOLD, 7); c.drawRightString(W - 27, H - 32, "PAPER 001 / JULY 2026")
        fitted_title(c, "The Work Left to Us", 27, H - 88, W - 54, 150, font=DISPLAY, maximum=39, minimum=31)
    elif key == "G":
        fitted_title(c, "The Work Left to Us", 34, H - 26, W - 68, 94, font=DISPLAY, maximum=30, minimum=24)
        framed_art(c, 34, 95, W - 91, 365, crop_x=.22, crop_y=.36)
        color(c, INK, stroke=True); c.setLineWidth(.5); c.rect(34, 95, W - 91, 365, fill=0, stroke=1)
        color(c, INK); c.setFont(SANS_BOLD, 7); c.saveState(); c.translate(W - 25, 98); c.rotate(90); c.drawString(0, 0, "BERRETA FUTURA / ISSUE 001"); c.restoreState()
        color(c, SLATE); c.setFont(SANS, 6); c.drawString(34, 79, "A PRIVATE READER ON WORK, AGENCY, OWNERSHIP, AND GOVERNANCE")
    else:
        color(c, SKY); c.rect(W * .54, H * .43, W * .46, H * .57, fill=1, stroke=0)
        color(c, YELLOW); c.rect(0, 0, W * .72, H * .34, fill=1, stroke=0)
        color(c, BLUSH); c.saveState(); c.translate(80, 170); c.rotate(-13); c.rect(0, 0, 112, 310, fill=1, stroke=0); c.restoreState()
        color(c, PAPER); c.rect(26, H - 224, W - 52, 190, fill=1, stroke=0)
        color(c, INK); c.setFont(SANS_BOLD, 9); c.drawString(39, H - 60, "BERRETA FUTURA")
        color(c, COBALT); c.rect(W - 78, H - 64, 39, 5, fill=1, stroke=0)
        fitted_title(c, "The Work Left to Us", 39, H - 88, W - 78, 116, font=SANS_BOLD, maximum=32, minimum=27)
    color(c, INK); c.setFont(SANS_SEMIBOLD, 6.2); c.drawString(30 if key != "E" else 106, 25, "16 JULY 2026  /  ISSUE 001")


def contents_new(c: canvas.Canvas, direction: Direction) -> None:
    key = direction.key
    color(c, WHITE); c.rect(0, 0, W, H, fill=1, stroke=0)
    entries = [
        ("02", "Editorial", "The Last Mile Is the Whole World", "The editors"),
        ("03", "Feature 01", "What will be left for us to work on?", "Arvind Narayanan"),
        ("06", "Feature 02", "DSLs Enable Reliable Use of LLMs", "Unmesh Joshi"),
        ("11", "Feature 03", "The Reverse Information Paradox", "Satya Nadella"),
        ("15", "Feature 04", "A Framework for Frontier AI", "Demis Hassabis"),
    ]
    if key == "D":
        color(c, INK); c.setFont(SANS_BOLD, 32); c.drawString(30, H - 56, "CONTENTS")
        y = H - 102
        for index, (page, label, title, author) in enumerate(entries, 1):
            rule(c, 30, y + 13, W - 30, INK, .7)
            color(c, OXBLOOD); c.setFont(SANS_BOLD, 7); c.drawString(30, y, f"{index:02d}")
            color(c, INK); c.setFont(SANS_BOLD, 7); c.drawString(64, y, label.upper())
            c.setFont(SANS_SEMIBOLD, 10); c.drawString(137, y, title)
            c.setFont(SANS_BOLD, 9); c.drawRightString(W - 30, y, page)
            color(c, SLATE); c.setFont(SANS, 6.2); c.drawString(137, y - 13, author.upper()); y -= 70
    elif key == "E":
        framed_art(c, 30, H - 208, 118, 150, crop_x=.78, crop_y=.2)
        color(c, SLATE); c.setFont(SANS, 6); c.drawString(30, H - 220, "CONTENTS / OBJECT 001")
        color(c, INK); c.setFont(DISPLAY, 27); c.drawString(180, H - 68, "Contents")
        y = H - 116
        for page, label, title, author in entries:
            color(c, SLATE); c.setFont(SANS_BOLD, 6); c.drawString(180, y, label.upper())
            color(c, INK); c.setFont(DISPLAY, 10.5); y = text_lines(c, title, 180, y - 13, W - 215, DISPLAY, 10.5, 12.2, INK, 2)
            color(c, INK); c.setFont(SANS_BOLD, 8); c.drawRightString(W - 30, y + 12, page); y -= 23
    elif key == "F":
        color(c, INK); c.rect(0, H - 72, W, 72, fill=1, stroke=0); color(c, PAPER); c.setFont(DISPLAY, 28); c.drawString(27, H - 45, "Inside this paper")
        column_width = (W - 66) / 2; y_positions = [H - 109, H - 109]
        for index, (page, label, title, author) in enumerate(entries):
            column = index % 2; x = 27 + column * (column_width + 12); y = y_positions[column]
            color(c, FOREST); c.setFont(SANS_BOLD, 6.2); c.drawString(x, y, f"{label.upper()} / {page}")
            y = text_lines(c, title, x, y - 17, column_width, DISPLAY, 13, 14.5, INK, 3)
            color(c, SLATE); c.setFont(SANS, 6.2); c.drawString(x, y - 2, author.upper()); y_positions[column] = y - 50
    elif key == "G":
        color(c, INK); c.setFont(DISPLAY, 27); c.drawString(58, H - 60, "Contents")
        y = H - 118
        for page, label, title, author in entries:
            color(c, SAND); c.setFont(DISPLAY, 31); c.drawString(58, y, page)
            color(c, SLATE); c.setFont(SANS_BOLD, 6); c.drawString(113, y + 10, label.upper())
            color(c, INK); c.setFont(DISPLAY, 11); c.drawString(113, y - 7, title)
            color(c, SLATE); c.setFont(SANS, 6); c.drawString(113, y - 20, author.upper()); y -= 82
    else:
        color(c, SKY); c.rect(0, 0, 54, H, fill=1, stroke=0); color(c, INK); c.setFont(SANS_BOLD, 28); c.drawString(83, H - 58, "CONTENTS")
        y = H - 104; accents = (YELLOW, BLUSH, SKY, OXBLOOD, LILAC)
        for index, (page, label, title, author) in enumerate(entries):
            color(c, accents[index]); c.rect(83, y - 25, 18, 37, fill=1, stroke=0)
            color(c, INK); c.setFont(SANS_BOLD, 7); c.drawString(111, y + 3, f"{label.upper()} / {page}")
            c.setFont(SANS_SEMIBOLD, 10.3); c.drawString(111, y - 13, title)
            color(c, SLATE); c.setFont(SANS, 6); c.drawString(111, y - 25, author.upper()); y -= 78
    folio(c, 2, direction.name, OXBLOOD if key == "D" else (FOREST if key == "F" else COBALT))


def opener_new(c: canvas.Canvas, direction: Direction, *, editorial: bool) -> None:
    key = direction.key
    color(c, WHITE); c.rect(0, 0, W, H, fill=1, stroke=0)
    label = "ORIGINAL EDITORIAL" if editorial else "FEATURE 01 / FAITHFUL SYNTHESIS"
    title = "The Last Mile Is the Whole World" if editorial else "What will be left for us to work on?"
    author = "THE EDITORS" if editorial else "ARVIND NARAYANAN"
    copy = EDITORIAL if editorial else ARTICLE
    if key == "D":
        color(c, OXBLOOD); c.rect(30, H - 48, 58, 18, fill=1, stroke=0); color(c, WHITE); c.setFont(SANS_BOLD, 6); c.drawString(38, H - 41, "01 / 04")
        color(c, INK); c.setFont(SANS_BOLD, 6.5); c.drawString(108, H - 41, label)
        color(c, SAND); c.setFont(SANS_BOLD, 60); c.drawString(25, H - 126, "01")
        title_bottom = fitted_title(c, title, 109, H - 73, W - 139, 132, font=SANS_BOLD, maximum=27, minimum=22)
        rule(c, 109, title_bottom - 2, W - 30, INK, .8)
        color(c, INK); c.setFont(SANS_BOLD, 7); c.drawString(109, title_bottom - 20, author)
        text_lines(c, copy[0], 109, title_bottom - 52, W - 139, SERIF, 10.4, 14, INK, 10)
    elif key == "E":
        color(c, SLATE); c.setFont(SANS_BOLD, 6.2); c.drawString(38, H - 34, label)
        framed_art(c, W - 151, H - 177, 112, 137, crop_x=.72, crop_y=.32)
        title_bottom = fitted_title(c, title, 38, H - 84, W - 215, 146, font=DISPLAY, maximum=26, minimum=20)
        color(c, INK); c.setFont(SANS_BOLD, 6.7); c.drawString(38, title_bottom - 10, author)
        rule(c, 38, H - 205, W - 38, SAND, .6)
        text_lines(c, copy[0], 92, H - 236, W - 130, SERIF, 10.8, 14.5, INK, 12)
        color(c, SLATE); c.setFont(SANS, 6); c.saveState(); c.translate(37, 80); c.rotate(90); c.drawString(0, 0, "OBJECT STUDY / ENTRY 01"); c.restoreState()
    elif key == "F":
        color(c, FOREST); c.rect(0, H - 42, W, 42, fill=1, stroke=0); color(c, WHITE); c.setFont(SANS_BOLD, 7); c.drawString(27, H - 26, label)
        title_bottom = fitted_title(c, title, 27, H - 71, W - 54, 136, font=DISPLAY, maximum=32, minimum=25)
        color(c, INK); c.setFont(SANS_BOLD, 7); c.drawString(27, title_bottom - 8, author)
        rule(c, 27, title_bottom - 25, W - 27, INK, 1.2)
        paragraphs(c, [copy[0]], 27, title_bottom - 49, W - 54, size=10, leading=13.2, columns=2, gutter=22, bottom=50)
    elif key == "G":
        color(c, SLATE); c.setFont(SANS_BOLD, 6); c.saveState(); c.translate(25, 66); c.rotate(90); c.drawString(0, 0, label); c.restoreState()
        title_bottom = fitted_title(c, title, 78, H - 116, W - 134, 150, font=DISPLAY, maximum=29, minimum=22)
        color(c, INK); c.setFont(SANS_BOLD, 6.5); c.drawString(78, title_bottom - 14, author)
        rule(c, 78, title_bottom - 33, W - 56, SAND, .5)
        text_lines(c, copy[0], 112, title_bottom - 64, W - 168, SERIF, 10.5, 14.2, INK, 11)
    else:
        color(c, SKY); c.rect(0, 0, 34, H, fill=1, stroke=0); color(c, YELLOW); c.rect(W - 20, H - 172, 20, 172, fill=1, stroke=0)
        color(c, COBALT); c.setFont(SANS_BOLD, 56); c.drawString(57, H - 89, "01")
        color(c, INK); c.setFont(SANS_BOLD, 6.5); c.drawString(149, H - 48, label)
        title_bottom = fitted_title(c, title, 149, H - 70, W - 179, 129, font=SANS_BOLD, maximum=25, minimum=20)
        color(c, INK); c.setFont(SANS_BOLD, 7); c.drawString(149, title_bottom - 11, author)
        rule(c, 57, H - 222, W - 38, COBALT, 1)
        text_lines(c, copy[0], 88, H - 255, W - 126, SERIF, 10.4, 14.1, INK, 12)
    folio(c, 3 if editorial else 4, direction.name, OXBLOOD if key == "D" else (FOREST if key == "F" else COBALT))


def continuation_new(c: canvas.Canvas, direction: Direction) -> None:
    key = direction.key
    color(c, WHITE); c.rect(0, 0, W, H, fill=1, stroke=0)
    if key == "D":
        color(c, OXBLOOD); c.setFont(SANS_BOLD, 7); c.drawString(30, H - 31, "01")
        color(c, INK); c.setFont(SANS_BOLD, 6.2); c.drawString(62, H - 31, "CAPABILITY IS NOT DEPLOYMENT")
        rule(c, 30, H - 42, W - 30, INK, .8)
        color(c, SLATE); c.setFont(SANS, 6.2); c.drawString(30, H - 69, "ARGUMENT")
        text_lines(c, "Capability → product → adoption → institutional change", 30, H - 85, 68, SANS_SEMIBOLD, 7.2, 9.5, OXBLOOD, 6)
        paragraphs(c, ARTICLE[1:7], 118, H - 68, W - 148, size=9.5, leading=12.9)
    elif key == "E":
        framed_art(c, 34, H - 210, 128, 156, crop_x=.35, crop_y=.76)
        color(c, SLATE); c.setFont(SANS, 6); c.drawString(34, H - 221, "FIG. 02 — CAPABILITY IS NOT DEPLOYMENT")
        color(c, INK); c.setFont(DISPLAY, 15); c.drawString(195, H - 68, "The gap is the subject.")
        text_lines(c, ARTICLE[1], 195, H - 100, W - 229, SERIF_ITALIC, 10.2, 14, INK, 9)
        rule(c, 34, H - 252, W - 34, SAND, .6)
        paragraphs(c, ARTICLE[2:7], 76, H - 282, W - 110, size=9.7, leading=13.1)
    elif key == "F":
        color(c, INK); c.rect(0, H - 38, W, 38, fill=1, stroke=0); color(c, WHITE); c.setFont(SANS_BOLD, 7); c.drawString(27, H - 24, "BERRETA FUTURA / WORK / EVIDENCE / GOVERNANCE")
        color(c, FOREST); c.setFont(DISPLAY, 18); c.drawString(27, H - 72, "Capability is not deployment")
        rule(c, 27, H - 87, W - 27, FOREST, 2)
        paragraphs(c, ARTICLE[1:7], 27, H - 113, W - 54, size=9.1, leading=12.2, columns=2, gutter=22, column_top=H - 113)
    elif key == "G":
        color(c, SLATE); c.setFont(SANS_BOLD, 6); c.drawString(54, H - 32, "ARVIND NARAYANAN / CONTINUED")
        color(c, SAND); c.setFont(DISPLAY, 47); c.drawString(54, H - 97, "05")
        paragraphs(c, ARTICLE[1:7], 128, H - 79, 222, size=10, leading=13.6)
        rule(c, 54, 55, W - 54, SAND, .5)
    else:
        color(c, SKY); c.rect(0, 0, 24, H, fill=1, stroke=0); color(c, YELLOW); c.rect(W - 13, 95, 13, 184, fill=1, stroke=0)
        color(c, INK); c.setFont(SANS_BOLD, 6.5); c.drawString(52, H - 31, "05 / CAPABILITY IS NOT DEPLOYMENT")
        rule(c, 52, H - 43, W - 39, COBALT, 1.1)
        color(c, BLUSH); c.rect(52, H - 111, 68, 44, fill=1, stroke=0); color(c, INK); c.setFont(SANS_BOLD, 22); c.drawString(65, H - 96, "01")
        paragraphs(c, ARTICLE[1:7], 142, H - 69, W - 181, size=9.6, leading=13)
    folio(c, 5, direction.name, OXBLOOD if key == "D" else (FOREST if key == "F" else COBALT))


def back_new(c: canvas.Canvas, direction: Direction) -> None:
    key = direction.key
    color(c, PAPER if key in {"D", "F", "H"} else WHITE); c.rect(0, 0, W, H, fill=1, stroke=0)
    quote = "Intelligence does not govern itself. The boundaries we build around it will decide who learns, who owns, and who answers."
    if key == "D":
        color(c, INK); c.rect(0, H - 64, W, 64, fill=1, stroke=0); color(c, OXBLOOD); c.rect(30, 92, 80, 260, fill=1, stroke=0)
        text_lines(c, quote, 143, H - 150, W - 179, SANS_BOLD, 16, 19, INK, 8)
    elif key == "E":
        framed_art(c, 0, 0, W, H, crop_x=.82, crop_y=.54)
        color(c, WHITE); c.setFillAlpha(.94); c.rect(36, 49, W - 72, 190, fill=1, stroke=0); c.setFillAlpha(1)
        text_lines(c, quote, 56, 208, W - 112, DISPLAY, 16, 20, INK, 8)
    elif key == "F":
        color(c, INK); c.rect(0, H - 48, W, 48, fill=1, stroke=0); color(c, FOREST); c.rect(0, 0, W, 104, fill=1, stroke=0)
        color(c, INK); c.setFont(SANS_BOLD, 43); c.drawString(27, H - 110, "THE") ; c.drawString(27, H - 150, "LAST") ; c.drawString(27, H - 190, "WORD")
        text_lines(c, quote, 207, H - 105, W - 234, DISPLAY, 13.5, 17, INK, 10)
    elif key == "G":
        color(c, INK); c.setFont(SANS_BOLD, 6.5); c.drawString(56, H - 37, "BERRETA FUTURA / ISSUE 001")
        text_lines(c, quote, 105, H * .61, W - 161, DISPLAY, 17.5, 22, INK, 9)
        rule(c, 105, 89, W - 56, SAND, .5)
    else:
        color(c, SKY); c.rect(0, H - 120, W, 120, fill=1, stroke=0); color(c, YELLOW); c.rect(0, 0, W, 91, fill=1, stroke=0); color(c, BLUSH); c.rect(0, 91, 56, H - 211, fill=1, stroke=0)
        text_lines(c, quote, 91, H - 186, W - 130, SANS_BOLD, 17, 20, INK, 8)
    color(c, INK); c.setFont(SANS_BOLD, 6.2); c.drawString(30 if key != "G" else 105, 31, "BERRETA FUTURA / ISSUE 001")


ROUND3_ACCENTS = {
    "I": OXBLOOD,
    "J": ORANGE,
    "K": COBALT,
    "L": OXBLOOD,
    "M": FOREST,
}


ROUND3_ENTRIES = [
    ("02", "Editorial", "The Last Mile Is the Whole World", "The editors"),
    ("03", "Feature 01", "What will be left for us to work on?", "Arvind Narayanan"),
    ("06", "Feature 02", "DSLs Enable Reliable Use of LLMs", "Unmesh Joshi"),
    ("11", "Feature 03", "The Reverse Information Paradox", "Satya Nadella"),
    ("15", "Feature 04", "A Framework for Frontier AI", "Demis Hassabis"),
]


def round3_page(c: canvas.Canvas, direction: Direction, number: int, *, paper=PAPER) -> Round3Page:
    color(c, paper); c.rect(0, 0, W, H, fill=1, stroke=0)
    return Round3Page(c, number, direction.name, ROUND3_ACCENTS[direction.key])


def round3_footer(page: Round3Page) -> None:
    box = page.reserve("cover metadata", Box(page.left, 17, page.live_width, 18), gap=0)
    color(page.c, INK); page.c.setFont(SANS_MEDIUM, CAPTION_SIZE)
    page.c.drawString(box.x, box.y, "ISSUE 001 / 16 JULY 2026")
    page.c.drawRightString(box.right, box.y, "THE WORK LEFT TO US")


def round3_running(page: Round3Page, text: str) -> None:
    box = page.reserve("running matter", Box(page.left, H - 37, page.live_width, 15), gap=0)
    color(page.c, INK); page.c.setFont(SANS_MEDIUM, CAPTION_SIZE)
    page.c.drawString(box.x, box.y + 3, "BERRETA FUTURA / ISSUE 001")
    page.c.drawRightString(box.right, box.y + 3, text.upper())


def round3_contents_register(page: Round3Page, box: Box, *, accent, numbered_plates: bool = False) -> None:
    page.reserve("contents register", box)
    row_height = box.height / len(ROUND3_ENTRIES)
    for index, (folio_value, label, title, author) in enumerate(ROUND3_ENTRIES):
        row_top = box.top - index * row_height
        if index:
            rule(page.c, box.x, row_top, box.right, SAND, .75)
        color(page.c, accent); page.c.setFont(SANS_MEDIUM, CAPTION_SIZE)
        index_text = f"PLATE {index + 1:02d}" if numbered_plates else f"{index + 1:02d} / {label.upper()}"
        page.c.drawString(box.x, row_top - 13, index_text)
        color(page.c, INK); page.c.setFont(SANS_SEMIBOLD, 10.2)
        title_lines = wrap(title, SANS_SEMIBOLD, 10.2, box.width - 42)
        if len(title_lines) > 2:
            raise ValueError(f"{page.name}: contents title needs more than two lines: {title}")
        baseline = row_top - 29
        for line in title_lines:
            page.c.drawString(box.x, baseline, line); baseline -= 12.6
        color(page.c, SLATE); page.c.setFont(SANS_MEDIUM, CAPTION_SIZE)
        page.c.drawString(box.x, row_top - row_height + 11, author.upper())
        color(page.c, INK); page.c.setFont(SANS_SEMIBOLD, 9)
        page.c.drawRightString(box.right, row_top - 13, folio_value)


def cover_round3(c: canvas.Canvas, direction: Direction) -> None:
    key = direction.key
    page = round3_page(c, direction, 1, paper=WHITE if key in {"I", "K", "M"} else PAPER)
    accent = page.accent

    if key == "I":
        draw_label_box(page, "masthead", "Berreta Futura / Measured Wonder", Box(page.left, 551, page.live_width, 16), rgb=INK)
        draw_manual_title(page, "cover title", ["The Work", "Left to Us"], Box(page.left, 432, page.live_width, 92), font=SANS_SEMIBOLD, size=34, leading=34)
        draw_copy_box(page, "cover deck", ["Work, agency, ownership, and governance in the age of capable machines"], Box(page.left, 392, 238, 25), font=SANS, size=8.2, leading=10.2)
        art = Box(136, 55, 250, 320)
        print_safe_art(page, "cover artwork", art, crop_x=.50, crop_y=.43)
        color(c, accent, stroke=True); c.setLineWidth(.8)
        c.line(122, art.y, 122, art.top); c.line(116, art.y, 128, art.y); c.line(116, art.top, 128, art.top)
        for y in range(int(art.y), int(art.top) + 1, 32): c.line(118, y, 126, y)
        color(c, accent); c.setFont(SANS_MEDIUM, CAPTION_SIZE); c.drawRightString(116, art.top - 7, "320")
    elif key == "J":
        draw_label_box(page, "masthead", "Berreta Futura / Issue 001", Box(page.left, 551, page.live_width, 16))
        draw_manual_title(page, "cover title", ["The Work", "Left to Us"], Box(page.left, 444, page.live_width, 82), font=DISPLAY, size=33, leading=32)
        art = Box(85, 235, 250, 128)
        print_safe_art(page, "cover artwork", art, crop_x=.52, crop_y=.46)
        color(c, accent, stroke=True); c.setLineWidth(1.1)
        c.line(0, 299, art.x + 28, 299); c.line(art.x + 28, 299, art.right - 24, 299); c.line(art.right - 24, 299, W, 299)
        color(c, accent); c.circle(art.right - 24, 299, 3.2, fill=1, stroke=0)
        draw_copy_box(page, "cover deck", ["A private reader about the work that remains ours to choose."], Box(page.left, 169, page.live_width, 32), font=SERIF_ITALIC, size=10.4, leading=13)
    elif key == "K":
        draw_label_box(page, "masthead", "Berreta Futura / Collection Register 001", Box(page.left, 551, page.live_width, 16))
        draw_manual_title(page, "cover title", ["The Work", "Left to Us"], Box(page.left, 462, page.live_width, 70), font=DISPLAY, size=29, leading=28)
        art = Box(135, 180, 210, 260)
        print_safe_art(page, "specimen artwork", art, crop_x=.48, crop_y=.47)
        color(c, INK, stroke=True); c.setLineWidth(.8); c.rect(art.x, art.y, art.width, art.height, fill=0, stroke=1)
        draw_label_box(page, "plate caption", "Plate 001 — Work / agency / infrastructure", Box(135, 151, 210, 18), rgb=COBALT)
        color(c, SAND); c.setFont(SANS_BOLD, 57); c.drawString(page.left, 62, "001")
    elif key == "L":
        draw_label_box(page, "masthead", "Berreta Futura / Scale Shift", Box(page.left, 551, page.live_width, 16))
        draw_manual_title(page, "cover title", ["The Work", "Left to Us"], Box(page.left, 470, page.live_width, 62), font=DISPLAY, size=30, leading=29)
        art = Box(95, 139, 250, 320)
        print_safe_art(page, "cover artwork", art, crop_x=.51, crop_y=.48)
        color(c, accent, stroke=True); c.setLineWidth(.8); c.rect(art.x, art.y, art.width, art.height, fill=0, stroke=1)
        color(c, accent); c.setFont(SANS_MEDIUM, 10); c.drawString(page.left, 107, "1 : 100")
        color(c, INK); c.setFont(SANS_MEDIUM, CAPTION_SIZE); c.drawString(page.left + 58, 109, "THE HUMAN MEASURE OF CAPABLE MACHINES")
    else:
        draw_label_box(page, "masthead", "Berreta Futura / Three Apertures", Box(page.left, 551, page.live_width, 16))
        draw_manual_title(page, "cover title", ["The Work", "Left to Us"], Box(page.left, 445, page.live_width, 82), font=DISPLAY, size=33, leading=32)
        circles = [
            (Box(44, 273, 118, 118), .23, .38),
            (Box(190, 316, 98, 98), .52, .50),
            (Box(307, 258, 78, 78), .77, .62),
        ]
        for index, (box, crop_x, crop_y) in enumerate(circles, 1):
            print_safe_art(page, f"aperture {index}", box, crop_x=crop_x, crop_y=crop_y, circle=True)
            color(c, FOREST, stroke=True); c.setLineWidth(.8); c.circle(box.x + box.width / 2, box.y + box.height / 2, box.width / 2, fill=0, stroke=1)
        draw_copy_box(page, "cover deck", ["Three views onto one question: what remains ours to understand, contest, and own?"], Box(page.left, 184, page.live_width, 42), font=SERIF_ITALIC, size=10.2, leading=13)
    round3_footer(page)


def contents_round3(c: canvas.Canvas, direction: Direction) -> None:
    key = direction.key
    page = round3_page(c, direction, 2, paper=WHITE)
    page.folio()
    accent = page.accent
    draw_label_box(page, "contents kicker", "Issue 001 / Contents", Box(page.left, 548, page.live_width, 16), rgb=accent)
    draw_manual_title(page, "contents title", ["Contents"], Box(page.left, 503, page.live_width, 35), font=DISPLAY if key in {"J", "K", "L", "M"} else SANS_SEMIBOLD, size=27, leading=27)

    if key == "I":
        art = Box(page.left, 357, 92, 122)
        print_safe_art(page, "contents artwork", art, crop_x=.72, crop_y=.33)
        color(c, accent, stroke=True); c.setLineWidth(.8); c.line(140, 98, 140, 479)
        for y in range(111, 480, 26): c.line(136, y, 144, y)
        round3_contents_register(page, Box(158, 85, W - page.right - 158, 394), accent=accent)
    elif key == "J":
        thread_x = page.left + 44
        color(c, accent, stroke=True); c.setLineWidth(1.1); c.line(thread_x, 82, thread_x, 482)
        entries_box = Box(thread_x + 27, 82, W - page.right - thread_x - 27, 400)
        round3_contents_register(page, entries_box, accent=accent)
        row_height = entries_box.height / 5
        color(c, accent)
        for index in range(5): c.circle(thread_x, entries_box.top - index * row_height - 13, 3, fill=1, stroke=0)
    elif key == "K":
        round3_contents_register(page, Box(page.left, 82, page.live_width, 400), accent=accent, numbered_plates=True)
    elif key == "L":
        color(c, SAND); c.setFont(SANS_BOLD, 45); c.drawString(page.left, 427, "1:4")
        round3_contents_register(page, Box(page.left + 96, 82, page.live_width - 96, 400), accent=accent)
    else:
        for index, (diameter, x, y, cx, cy) in enumerate(((62, page.left, 414, .2, .32), (52, page.left + 78, 430, .5, .5), (42, page.left + 146, 408, .8, .7)), 1):
            box = Box(x, y, diameter, diameter)
            print_safe_art(page, f"contents aperture {index}", box, crop_x=cx, crop_y=cy, circle=True)
        round3_contents_register(page, Box(page.left, 76, page.live_width, 310), accent=accent)


def opener_round3(c: canvas.Canvas, direction: Direction, *, editorial: bool) -> None:
    key = direction.key
    number = 3 if editorial else 4
    page = round3_page(c, direction, number, paper=WHITE)
    page.folio()
    accent = page.accent
    label = "Original editorial / An original argument" if editorial else "Feature 01 / Faithful synthesis"
    title_lines = ["The Last Mile", "Is the Whole World"] if editorial else ["What will be left", "for us to work on?"]
    author = "The editors" if editorial else "Arvind Narayanan"
    copy = EDITORIAL if editorial else ARTICLE
    round3_running(page, label)

    if key == "I":
        title_box = page.columns(0, 4, 409, 104)
        measured_lines = ["The Last Mile", "Is the Whole", "World"] if editorial else ["What will be", "left for us", "to work on?"]
        draw_manual_title(page, "opener title", measured_lines, title_box, font=SANS_SEMIBOLD, size=25, leading=26)
        draw_label_box(page, "opener credit", author, page.columns(0, 3, 380, 16), rgb=INK)
        art = page.columns(4, 2, 390, 123)
        print_safe_art(page, "opener artwork", art, crop_x=.67 if editorial else .47, crop_y=.35 if editorial else .54)
        color(c, accent, stroke=True); c.setLineWidth(.8); c.line(page.left, 357, W - page.right, 357)
        for x in (page.left, page.columns(2, 1, 0, 1).x, page.columns(4, 1, 0, 1).x, W - page.right): c.line(x, 352, x, 362)
        copy_box = page.columns(1, 5, 76, 257)
        draw_copy_box(page, "opener lead", [copy[0]], copy_box, size=10.1, leading=BASE * 5)
    elif key == "J":
        thread_x = page.left + page.column_width
        color(c, accent, stroke=True); c.setLineWidth(1.1); c.line(thread_x, 74, thread_x, 516); c.line(thread_x, 516, W - page.right, 516)
        color(c, accent); c.circle(thread_x, 516, 3.2, fill=1, stroke=0)
        draw_manual_title(page, "opener title", title_lines, page.columns(2, 4, 407, 101), font=DISPLAY, size=27, leading=28)
        draw_label_box(page, "opener credit", author, page.columns(2, 3, 378, 16))
        draw_copy_box(page, "opener lead", [copy[0]], page.columns(2, 4, 86, 260), size=10.1, leading=BASE * 5)
        rail_label = page.reserve("thread label", Box(page.left, 172, 28, 151))
        color(c, accent); c.setFont(SANS_MEDIUM, CAPTION_SIZE)
        c.saveState(); c.translate(rail_label.x + 7, rail_label.y); c.rotate(90)
        c.drawString(0, 0, "CAPABILITY TO CONSEQUENCE")
        c.restoreState()
    elif key == "K":
        art = page.columns(0, 2, 366, 147)
        print_safe_art(page, "opener specimen", art, crop_x=.25 if editorial else .58, crop_y=.42)
        color(c, INK, stroke=True); c.setLineWidth(.8); c.rect(art.x, art.y, art.width, art.height, fill=0, stroke=1)
        draw_label_box(page, "plate number", f"Plate {'E' if editorial else '01'}", page.columns(0, 2, 337, 18), rgb=accent)
        draw_manual_title(page, "opener title", title_lines, page.columns(2, 4, 403, 110), font=DISPLAY, size=25, leading=26)
        draw_label_box(page, "opener credit", author, page.columns(2, 3, 371, 16))
        draw_copy_box(page, "opener lead", [copy[0]], page.columns(2, 4, 82, 257), size=9.8, leading=BASE * 4)
    elif key == "L":
        art = Box(page.left + 45, 403, 250, 112)
        print_safe_art(page, "scale artwork", art, crop_x=.50, crop_y=.51 if editorial else .66)
        color(c, accent, stroke=True); c.setLineWidth(.8); c.rect(art.x, art.y, art.width, art.height, fill=0, stroke=1)
        draw_label_box(page, "scale ratio", "1 : 10 / Human judgment", Box(page.left, 371, page.live_width, 18), rgb=accent)
        draw_manual_title(page, "opener title", title_lines, page.columns(1, 5, 277, 80), font=DISPLAY, size=25, leading=26)
        draw_label_box(page, "opener credit", author, page.columns(1, 3, 251, 16))
        draw_copy_box(page, "opener lead", [copy[0]], page.columns(1, 5, 69, 161), size=9.8, leading=BASE * 4)
    else:
        aperture_size = 112
        art = Box(W - page.right - aperture_size, 394, aperture_size, aperture_size)
        print_safe_art(page, "opener aperture", art, crop_x=.32 if editorial else .61, crop_y=.41 if editorial else .57, circle=True)
        color(c, accent, stroke=True); c.setLineWidth(.8); c.circle(art.x + aperture_size / 2, art.y + aperture_size / 2, aperture_size / 2, fill=0, stroke=1)
        draw_manual_title(page, "opener title", title_lines, page.columns(0, 4, 403, 105), font=DISPLAY, size=25, leading=26)
        draw_label_box(page, "opener credit", author, page.columns(0, 3, 371, 16))
        draw_copy_box(page, "opener lead", [copy[0]], page.columns(1, 5, 78, 257), size=9.9, leading=BASE * 4)


def continuation_round3(c: canvas.Canvas, direction: Direction) -> None:
    key = direction.key
    page = round3_page(c, direction, 5, paper=WHITE)
    page.folio()
    accent = page.accent
    round3_running(page, "Arvind Narayanan / Capability is not deployment")

    if key == "I":
        rail = page.columns(0, 2, 92, 415)
        page.reserve("argument rail", rail)
        color(c, accent); c.setFont(SANS_MEDIUM, CAPTION_SIZE); c.drawString(rail.x, rail.top - 7, "EDITOR'S READING MAP")
        steps = ("CAPABILITY", "PRODUCT", "ADOPTION", "INSTITUTION")
        color(c, accent, stroke=True); c.setLineWidth(.8); c.line(rail.x + 9, rail.y + 42, rail.x + 9, rail.top - 36)
        for index, step in enumerate(steps):
            y = rail.top - 67 - index * 76
            color(c, accent); c.circle(rail.x + 9, y, 3, fill=1, stroke=0)
            color(c, INK); c.setFont(SANS_MEDIUM, CAPTION_SIZE); c.drawString(rail.x + 22, y - 3, step)
        draw_copy_box(page, "article body", ARTICLE[1:3], page.columns(2, 4, 66, 441), size=BODY_SIZE, leading=BODY_LEADING)
    elif key == "J":
        diagram = page.columns(0, 6, 444, 62)
        page.reserve("thread diagram", diagram)
        nodes = ("CAPABILITY", "PRODUCT", "ADOPTION", "INSTITUTION")
        color(c, accent, stroke=True); c.setLineWidth(1.1); c.line(diagram.x + 8, diagram.y + 29, diagram.right - 8, diagram.y + 29)
        for index, node in enumerate(nodes):
            x = diagram.x + 15 + index * (diagram.width - 30) / 3
            color(c, accent); c.circle(x, diagram.y + 29, 3.3, fill=1, stroke=0)
            color(c, INK); c.setFont(SANS_MEDIUM, CAPTION_SIZE); c.drawCentredString(x, diagram.y + 8, node)
        draw_copy_box(page, "article body", ARTICLE[1:3], page.columns(1, 5, 68, 352), size=BODY_SIZE, leading=BODY_LEADING)
        color(c, accent, stroke=True); c.setLineWidth(1.1); c.line(page.left, 68, page.columns(1, 1, 0, 1).x - BASE, 68)
    elif key == "K":
        art = page.columns(0, 2, 355, 152)
        print_safe_art(page, "evidence plate", art, crop_x=.78, crop_y=.28)
        color(c, INK, stroke=True); c.setLineWidth(.8); c.rect(art.x, art.y, art.width, art.height, fill=0, stroke=1)
        draw_label_box(page, "evidence caption", "Plate 02 — The work moves outward", page.columns(0, 2, 315, 28), rgb=accent)
        draw_copy_box(page, "article body", ARTICLE[1:3], page.columns(2, 4, 69, 438), size=9.45, leading=BODY_LEADING)
        draw_label_box(page, "source marker", "Source record / Narayanan ICML 2026 keynote", page.columns(0, 2, 278, 32), rgb=SLATE)
    elif key == "L":
        quote_box = page.columns(0, 6, 413, 91)
        draw_manual_title(page, "pull quote", ["The gap is", "the subject."], quote_box, font=DISPLAY, size=27, leading=28, rgb=accent)
        draw_label_box(page, "scale marker", "1 : 1 / Practical usefulness", page.columns(0, 2, 376, 18), rgb=accent)
        draw_copy_box(page, "article body", ARTICLE[1:3], page.columns(2, 4, 70, 323), size=BODY_SIZE, leading=BODY_LEADING)
    else:
        aperture_specs = ((66, page.left, 421, .18, .31), (57, page.left + 10, 330, .50, .50), (48, page.left + 19, 250, .80, .72))
        for index, (diameter, x, y, crop_x, crop_y) in enumerate(aperture_specs, 1):
            art = Box(x, y, diameter, diameter)
            print_safe_art(page, f"article aperture {index}", art, crop_x=crop_x, crop_y=crop_y, circle=True)
            color(c, accent, stroke=True); c.setLineWidth(.8); c.circle(x + diameter / 2, y + diameter / 2, diameter / 2, fill=0, stroke=1)
        draw_label_box(page, "sequence caption", "01 / Methods  02 / Products  03 / Institutions", page.columns(0, 2, 201, 28), rgb=accent)
        draw_copy_box(page, "article body", ARTICLE[1:3], page.columns(2, 4, 70, 437), size=BODY_SIZE, leading=BODY_LEADING)


def back_round3(c: canvas.Canvas, direction: Direction) -> None:
    key = direction.key
    page = round3_page(c, direction, 6, paper=PAPER if key in {"J", "L"} else WHITE)
    accent = page.accent
    quote = "Intelligence does not govern itself. The boundaries we build around it will decide who learns, who owns, and who answers."
    draw_label_box(page, "back masthead", "Berreta Futura / Issue 001", Box(page.left, 551, page.live_width, 16))

    if key == "I":
        art = Box(page.left, 286, 238, 238)
        print_safe_art(page, "back artwork", art, crop_x=.62, crop_y=.50)
        color(c, accent, stroke=True); c.setLineWidth(.8); c.line(art.right + 16, art.y, art.right + 16, art.top)
        for y in range(int(art.y), int(art.top) + 1, 34): c.line(art.right + 12, y, art.right + 20, y)
        draw_copy_box(page, "back quote", [quote], Box(page.left + 79, 116, page.live_width - 79, 116), font=DISPLAY, size=16.2, leading=20)
    elif key == "J":
        color(c, accent, stroke=True); c.setLineWidth(1.1); c.line(0, 422, page.left + 55, 422); c.line(page.left + 55, 422, page.left + 55, 91); c.line(page.left + 55, 91, W, 91)
        color(c, accent); c.circle(page.left + 55, 422, 3.2, fill=1, stroke=0)
        draw_copy_box(page, "back quote", [quote], Box(page.left + 94, 232, page.live_width - 94, 153), font=DISPLAY, size=17, leading=21)
        draw_label_box(page, "thread conclusion", "Capability is only the beginning", Box(page.left + 94, 197, page.live_width - 94, 18), rgb=accent)
    elif key == "K":
        art = Box(page.left + 16, 292, 205, 205)
        print_safe_art(page, "final specimen", art, crop_x=.54, crop_y=.58)
        color(c, INK, stroke=True); c.setLineWidth(.8); c.rect(art.x, art.y, art.width, art.height, fill=0, stroke=1)
        draw_label_box(page, "final plate caption", "Plate 005 — Boundaries / ownership / answerability", Box(art.x, 252, art.width, 28), rgb=accent)
        draw_copy_box(page, "back quote", [quote], Box(page.left + 91, 108, page.live_width - 91, 116), font=DISPLAY, size=15.8, leading=19.5)
    elif key == "L":
        art = Box(page.left + 87, 270, 185, 236)
        print_safe_art(page, "scale figure", art, crop_x=.51, crop_y=.48)
        color(c, accent, stroke=True); c.setLineWidth(.8); c.rect(art.x, art.y, art.width, art.height, fill=0, stroke=1)
        color(c, accent); c.setFont(SANS_MEDIUM, 10); c.drawString(page.left, 238, "1 : ∞")
        draw_copy_box(page, "back quote", [quote], Box(page.left + 66, 102, page.live_width - 66, 113), font=DISPLAY, size=16, leading=20)
    else:
        art = Box(page.left + 57, 286, 220, 220)
        print_safe_art(page, "final aperture", art, crop_x=.50, crop_y=.48, circle=True)
        color(c, accent, stroke=True); c.setLineWidth(.8); c.circle(art.x + 110, art.y + 110, 110, fill=0, stroke=1)
        draw_copy_box(page, "back quote", [quote], Box(page.left + 71, 106, page.live_width - 71, 126), font=DISPLAY, size=16.4, leading=20)
    round3_footer(page)


ROUND4_ACCENTS = {"N": ACID, "O": VIOLET, "P": ORANGE}


def round4_page(c: canvas.Canvas, direction: Direction, number: int) -> Round3Page:
    color(c, WHITE); c.rect(0, 0, W, H, fill=1, stroke=0)
    return Round3Page(c, number, direction.name, ROUND4_ACCENTS[direction.key])


def round4_footer(page: Round3Page) -> None:
    box = page.reserve("cover metadata", Box(page.left, 17, page.live_width, 18), gap=0)
    color(page.c, INK); page.c.setFont(SANS_MEDIUM, CAPTION_SIZE)
    page.c.drawString(box.x, box.y, "ISSUE 001 / 16 JULY 2026")
    page.c.drawRightString(box.right, box.y, "THE WORK LEFT TO US")


def round4_folio(page: Round3Page) -> None:
    box = page.reserve("folio", Box(page.left, 17, page.live_width, 18), gap=0)
    color(page.c, page.accent, stroke=True); page.c.setLineWidth(.8)
    outer_x = page.left if page.number % 2 == 0 else W - page.right
    page.c.line(outer_x, box.top, outer_x + (17 if page.number % 2 == 0 else -17), box.top)
    color(page.c, INK); page.c.setFont(SANS_MEDIUM, CAPTION_SIZE)
    if page.number % 2 == 0:
        page.c.drawString(page.left, box.y, f"{page.number:02d}")
        page.c.drawRightString(W - page.right, box.y, "BERRETA FUTURA / THE WORK LEFT TO US")
    else:
        page.c.drawString(page.left, box.y, "BERRETA FUTURA / THE WORK LEFT TO US")
        page.c.drawRightString(W - page.right, box.y, f"{page.number:02d}")


def round4_running(page: Round3Page, right: str) -> None:
    box = page.reserve("running matter", Box(page.left, H - 37, page.live_width, 15), gap=0)
    color(page.c, INK); page.c.setFont(SANS_MEDIUM, CAPTION_SIZE)
    page.c.drawString(box.x, box.y + 3, "BERRETA FUTURA / ISSUE 001")
    page.c.drawRightString(box.right, box.y + 3, right.upper())


def salon_contents(page: Round3Page) -> None:
    rail = page.columns(0, 1, 86, 393)
    register = page.columns(1, 5, 86, 393)
    page.reserve("number rail", rail); page.reserve("contents register", register)
    row_height = register.height / 5
    for index, (folio_value, label, title, author) in enumerate(ROUND3_ENTRIES):
        row_top = register.top - index * row_height
        if index:
            rule(page.c, register.x, row_top, register.right, COOL_GRAY, .7)
        color(page.c, ACID); page.c.setFont(SANS_SEMIBOLD, 25)
        page.c.drawRightString(rail.right, row_top - 24, folio_value)
        color(page.c, INK); page.c.setFont(SANS_MEDIUM, CAPTION_SIZE)
        page.c.drawString(register.x, row_top - 12, label.upper())
        page.c.setFont(DISPLAY, 11.5); page.c.drawString(register.x, row_top - 33, title)
        color(page.c, SLATE); page.c.setFont(SANS_MEDIUM, CAPTION_SIZE)
        page.c.drawString(register.x, row_top - 51, author.upper())


def monument_contents(page: Round3Page) -> None:
    box = page.columns(0, 6, 86, 393)
    page.reserve("contents register", box)
    row_height = box.height / 5
    for index, (folio_value, label, title, author) in enumerate(ROUND3_ENTRIES):
        indent = 0 if index % 2 == 0 else page.column_width + page.gutter
        x = box.x + indent
        usable = box.width - indent
        row_top = box.top - index * row_height
        color(page.c, VIOLET); page.c.setFont(SANS_SEMIBOLD, 28)
        page.c.drawString(x, row_top - 28, folio_value)
        color(page.c, INK); page.c.setFont(SANS_MEDIUM, CAPTION_SIZE)
        page.c.drawString(x + 55, row_top - 12, label.upper())
        page.c.setFont(DISPLAY, 11.5); page.c.drawString(x + 55, row_top - 33, title)
        color(page.c, SLATE); page.c.setFont(SANS_MEDIUM, CAPTION_SIZE)
        page.c.drawString(x + 55, row_top - 51, author.upper())
        if index < 4:
            rule(page.c, x, row_top - row_height, box.x + box.width, COOL_GRAY, .7)


def paired_contents(page: Round3Page) -> None:
    left = page.columns(0, 3, 86, 274)
    right = page.columns(3, 3, 86, 274)
    page.reserve("left contents room", left); page.reserve("right contents room", right)
    for room, entries in ((left, ROUND3_ENTRIES[:3]), (right, ROUND3_ENTRIES[3:])):
        row_height = room.height / 3
        for index, (folio_value, label, title, author) in enumerate(entries):
            row_top = room.top - index * row_height
            color(page.c, ORANGE); page.c.setFont(SANS_SEMIBOLD, 21)
            page.c.drawString(room.x, row_top - 22, folio_value)
            color(page.c, INK); page.c.setFont(SANS_MEDIUM, CAPTION_SIZE)
            page.c.drawString(room.x + 42, row_top - 10, label.upper())
            title_lines = wrap(title, DISPLAY, 10.8, room.width - 42)
            page.c.setFont(DISPLAY, 10.8); baseline = row_top - 28
            for line in title_lines[:2]: page.c.drawString(room.x + 42, baseline, line); baseline -= 12.6
            color(page.c, SLATE); page.c.setFont(SANS_MEDIUM, CAPTION_SIZE)
            page.c.drawString(room.x + 42, row_top - row_height + 11, author.upper())


def cover_round4(c: canvas.Canvas, direction: Direction) -> None:
    key = direction.key
    page = round4_page(c, direction, 1)
    accent = page.accent
    draw_tracked_label(page, "masthead", "Berreta Futura / Issue 001", Box(page.left, 558, page.live_width, 15))

    if key == "N":
        draw_manual_title(page, "cover title", ["The Work", "Left to Us"], Box(page.left, 480, page.live_width, 64), font=DISPLAY, size=31, leading=31)
        draw_copy_box(page, "cover deck", ["Work, agency, ownership, and governance in the age of capable machines"], Box(page.left, 447, 225, 20), font=SANS, size=7.8, leading=9.5)
        art = Box(103, 92, 250, 341)
        print_safe_art(page, "cover artwork", art, crop_x=.50, crop_y=.47)
        color(c, INK, stroke=True); c.setLineWidth(.7); c.rect(art.x, art.y, art.width, art.height, fill=0, stroke=1)
        rail = Box(367, 92, 18, 341)
        color(c, accent)
        for y in range(int(rail.y), int(rail.top), 26): c.rect(rail.x + 7, y, 8, 3, fill=1, stroke=0)
        draw_rotated_label(page, "issue rail label", "Issue / Number one", Box(370, 121, 12, 180), rgb=INK)
    elif key == "O":
        draw_manual_title(page, "cover title", ["The Work", "Left to Us"], page.columns(0, 4, 461, 77), font=DISPLAY, size=35, leading=34)
        medallion = page.reserve("issue medallion", page.columns(4, 2, 484, 54))
        color(c, VIOLET); c.circle(medallion.x + medallion.width / 2, medallion.y + medallion.height / 2, 24, fill=1, stroke=0)
        color(c, WHITE); c.setFont(SANS_SEMIBOLD, 15); c.drawCentredString(medallion.x + medallion.width / 2, medallion.y + 20, "01")
        art = Box(135, 177, 250, 250)
        print_safe_art(page, "cover artwork", art, crop_x=.51, crop_y=.50)
        color(c, INK, stroke=True); c.setLineWidth(.7); c.rect(art.x, art.y, art.width, art.height, fill=0, stroke=1)
        draw_rotated_label(page, "subject rail", "Work / agency / ownership / governance", page.columns(0, 1, 177, 250), rgb=VIOLET)
        draw_tracked_label(page, "art caption", "Cover study / The human measure", Box(135, 146, 250, 18), rgb=VIOLET)
    else:
        art = Box(44, 257, 250, 278)
        print_safe_art(page, "cover artwork", art, crop_x=.48, crop_y=.44)
        color(c, INK, stroke=True); c.setLineWidth(.7); c.rect(art.x, art.y, art.width, art.height, fill=0, stroke=1)
        draw_rotated_label(page, "plate rail", "Cover plate 001 / Artwork changes by issue", Box(312, 257, 18, 278), rgb=ORANGE)
        draw_manual_title(page, "cover title", ["The Work", "Left to Us"], page.columns(1, 5, 157, 73), font=DISPLAY, size=34, leading=33)
        draw_copy_box(page, "cover deck", ["A private reader on work, agency, ownership, and governance."], page.columns(1, 4, 112, 26), font=SERIF_ITALIC, size=9.2, leading=12.6)
    round4_footer(page)


def contents_round4(c: canvas.Canvas, direction: Direction) -> None:
    key = direction.key
    page = round4_page(c, direction, 2)
    round4_folio(page)
    draw_tracked_label(page, "contents kicker", "Issue 001 / Contents", Box(page.left, 548, page.live_width, 15), rgb=INK)
    draw_manual_title(page, "contents title", ["Contents"], page.columns(0, 4, 503, 34), font=DISPLAY, size=27, leading=27)
    if key == "N":
        mark = page.reserve("entry count", page.columns(5, 1, 503, 34))
        color(c, ACID); c.setFont(SANS_SEMIBOLD, 27); c.drawRightString(mark.right, mark.y + 5, "05")
        salon_contents(page)
    elif key == "O":
        medallion = page.reserve("contents medallion", page.columns(5, 1, 497, 40))
        color(c, VIOLET); c.circle(medallion.x + medallion.width / 2, medallion.y + medallion.height / 2, 18, fill=1, stroke=0)
        color(c, WHITE); c.setFont(SANS_SEMIBOLD, 10); c.drawCentredString(medallion.x + medallion.width / 2, medallion.y + 16, "01")
        monument_contents(page)
    else:
        paired_contents(page)


def opener_round4(c: canvas.Canvas, direction: Direction, *, editorial: bool) -> None:
    key = direction.key
    number = 3 if editorial else 4
    page = round4_page(c, direction, number)
    round4_folio(page)
    label = "Original editorial / An original argument" if editorial else "Feature 01 / Faithful synthesis"
    author = "The editors" if editorial else "Arvind Narayanan"
    round4_running(page, label)

    if key == "N":
        if editorial:
            title_box = page.columns(0, 5, 431, 105)
            rail_box = page.columns(5, 1, 431, 105)
            credit_box = page.columns(0, 3, 399, 16)
            lead_box = page.columns(1, 4, 78, 301)
        else:
            rail_box = page.columns(0, 1, 431, 105)
            title_box = page.columns(1, 5, 431, 105)
            credit_box = page.columns(1, 3, 399, 16)
            lead_box = page.columns(1, 4, 78, 301)
        title_lines = ["The Last Mile", "Is the Whole World"] if editorial else ["What will be left", "for us to work on?"]
        draw_manual_title(page, "opener title", title_lines, title_box, font=DISPLAY, size=29, leading=29)
        draw_tracked_label(page, "opener credit", author, credit_box)
        rail = page.reserve("outer numeral", rail_box)
        color(c, ACID); c.setFont(SANS_SEMIBOLD, 39)
        if editorial: c.drawRightString(rail.right, rail.top - 39, "E")
        else: c.drawString(rail.x, rail.top - 39, "01")
        draw_copy_box(page, "opener lead", [EDITORIAL[0] if editorial else ARTICLE[0]], lead_box, size=9.55, leading=BODY_LEADING)
    elif key == "O":
        if editorial:
            draw_tracked_label(page, "editorial label", label, page.columns(0, 4, 510, 15), rgb=VIOLET)
            draw_manual_title(page, "editorial title", ["The Last Mile", "Is the Whole World"], page.columns(0, 5, 432, 66), font=DISPLAY, size=26, leading=26)
            draw_tracked_label(page, "editorial credit", author, page.columns(0, 3, 400, 15))
            draw_manual_title(page, "monumental sentence", ["Every important", "technology arrives", "twice."], page.columns(1, 5, 132, 218), font=DISPLAY, size=32, leading=34, rgb=VIOLET)
            draw_tracked_label(page, "sentence source", "Opening sentence / Original editorial", page.columns(1, 4, 102, 16), rgb=INK)
        else:
            group = page.reserve("feature title composition", page.columns(1, 5, 302, 216))
            color(c, INK); c.setFont(SANS_MEDIUM, 17); c.drawString(group.x, group.top - 19, "WHAT WILL BE")
            color(c, VIOLET); c.setFont(SANS_SEMIBOLD, 54); c.drawString(group.x, group.top - 82, "LEFT")
            color(c, INK); c.setFont(DISPLAY, 25); c.drawString(group.x, group.top - 124, "for us to work on?")
            draw_tracked_label(page, "feature credit", author, page.columns(1, 3, 274, 15))
            draw_copy_box(page, "feature lead", [ARTICLE[0]], page.columns(1, 4, 59, 189), size=9.3, leading=BODY_LEADING)
            medallion = page.reserve("feature medallion", page.columns(0, 1, 430, 56))
            color(c, VIOLET); c.circle(medallion.x + medallion.width / 2, medallion.y + medallion.height / 2, 21, fill=1, stroke=0)
            color(c, WHITE); c.setFont(SANS_SEMIBOLD, 11); c.drawCentredString(medallion.x + medallion.width / 2, medallion.y + 24, "01")
    else:
        if editorial:
            title_box = page.columns(0, 5, 411, 125)
            outer_box = page.columns(5, 1, 411, 125)
            credit_box = page.columns(0, 3, 380, 16)
        else:
            outer_box = page.columns(0, 1, 411, 125)
            title_box = page.columns(1, 5, 411, 125)
            credit_box = page.columns(1, 3, 380, 16)
        title_lines = ["The Last Mile", "Is the Whole World"] if editorial else ["What will be left", "for us to work on?"]
        draw_manual_title(page, "opener title", title_lines, title_box, font=DISPLAY, size=31, leading=31)
        draw_tracked_label(page, "opener credit", author, credit_box)
        draw_rotated_label(page, "outer label", "Original editorial" if editorial else "Faithful synthesis", outer_box, rgb=ORANGE)
        color(c, ORANGE, stroke=True); c.setLineWidth(1.1); c.line(page.columns(1, 1, 0, 1).x, 354, W - page.right, 354)
        draw_copy_box(page, "opener lead", [EDITORIAL[0] if editorial else ARTICLE[0]], page.columns(1, 4, 75, 251), size=9.55, leading=BODY_LEADING)


def continuation_round4(c: canvas.Canvas, direction: Direction) -> None:
    key = direction.key
    page = round4_page(c, direction, 5)
    round4_folio(page)
    round4_running(page, "Arvind Narayanan / Continued")

    if key == "N":
        draw_copy_box(page, "article body", ARTICLE[1:3], page.columns(1, 4, 76, 441), size=BODY_SIZE, leading=BODY_LEADING)
        rail = page.columns(5, 1, 76, 441)
        page.reserve("section rail", rail)
        color(c, ACID); c.rect(rail.x, rail.top - 18, rail.width, 18, fill=1, stroke=0)
        color(c, INK); c.setFont(SANS_MEDIUM, CAPTION_SIZE)
        c.saveState(); c.translate(rail.x + 9, rail.y + 15); c.rotate(90)
        c.drawString(0, 0, "CAPABILITY IS NOT DEPLOYMENT")
        c.restoreState()
        for y in range(int(rail.y + 68), int(rail.top - 42), 31):
            color(c, INK); c.rect(rail.x + rail.width - 8, y, 8, 1.2, fill=1, stroke=0)
    elif key == "O":
        draw_manual_title(page, "section bridge", ["Capability is not deployment"], page.columns(0, 5, 438, 45), font=DISPLAY, size=20, leading=21, rgb=VIOLET)
        draw_copy_box(page, "left article column", [ARTICLE[1]], page.columns(0, 3, 73, 337), size=9.1, leading=BODY_LEADING)
        draw_copy_box(page, "right article column", [ARTICLE[2]], page.columns(3, 3, 73, 337), size=9.1, leading=BODY_LEADING)
        rail = page.reserve("progress rail", page.columns(5, 1, 421, 61))
        color(c, VIOLET); c.circle(rail.x + rail.width / 2, rail.y + 31, 19, fill=1, stroke=0)
        color(c, WHITE); c.setFont(SANS_SEMIBOLD, 10); c.drawCentredString(rail.x + rail.width / 2, rail.y + 27, "2/4")
    else:
        draw_manual_title(page, "section bridge", ["Capability is not deployment"], page.columns(0, 5, 435, 48), font=DISPLAY, size=21, leading=21, rgb=INK)
        color(c, ORANGE); c.rect(page.columns(5, 1, 441, 26).x, 441, page.column_width, 26, fill=1, stroke=0)
        draw_two_column_flow(page, "article columns", ARTICLE[1:3], page.columns(0, 5, 74, 333), size=9.1, leading=BODY_LEADING)
        draw_rotated_label(page, "outer reading rail", "Decide / Execute / Deliver", page.columns(5, 1, 74, 333), rgb=ORANGE)


def back_round4(c: canvas.Canvas, direction: Direction) -> None:
    key = direction.key
    page = round4_page(c, direction, 6)
    draw_tracked_label(page, "back masthead", "Berreta Futura / Issue 001", Box(page.left, 558, page.live_width, 15))

    if key == "N":
        mark = page.reserve("back mark", page.columns(0, 1, 223, 167))
        color(c, ACID); c.rect(mark.x, mark.y, mark.width, mark.height, fill=1, stroke=0)
        quote = "Intelligence does not govern itself. The boundaries we build around it will decide who learns, who owns, and who answers."
        draw_copy_box(page, "back quote", [quote], page.columns(1, 4, 223, 167), font=DISPLAY, size=16.8, leading=21)
        draw_tracked_label(page, "back credit", "Issue statement / The editors", page.columns(1, 4, 194, 16), rgb=INK)
    elif key == "O":
        quote = "If AI performs more of the rowing, we must spend more effort steering the ship."
        draw_copy_box(page, "back quote", [quote], page.columns(1, 4, 205, 210), font=DISPLAY, size=20, leading=25, rgb=INK)
        medallion = page.reserve("back medallion", page.columns(0, 1, 205, 210))
        color(c, VIOLET); c.circle(medallion.x + medallion.width / 2, medallion.top - 26, 18, fill=1, stroke=0)
        color(c, WHITE); c.setFont(SANS_SEMIBOLD, 9); c.drawCentredString(medallion.x + medallion.width / 2, medallion.top - 29, "END")
        draw_tracked_label(page, "back credit", "Arvind Narayanan / Faithful synthesis", page.columns(1, 4, 176, 16), rgb=VIOLET)
    else:
        quote = "The future of work will not be decided by a final list of tasks machines cannot perform. It will be decided by what we insist people must continue to understand, contest, authorize, and own."
        group = page.columns(0, 6, 204, 205)
        draw_copy_box(page, "back quote", [quote], group, font=DISPLAY, size=17.2, leading=22)
        color(c, ORANGE); c.rect(group.x, group.top + 18, 23, 8, fill=1, stroke=0)
        draw_tracked_label(page, "back credit", "Original editorial / The editors", page.columns(0, 4, 175, 16), rgb=ORANGE)
    round4_footer(page)


def build_pdf(direction: Direction) -> Path:
    path = PREVIEWS / f"{direction.slug}.pdf"
    c = canvas.Canvas(
        str(path),
        pagesize=A5,
        pageCompression=1,
        invariant=1,
        initialFontName=SANS,
        initialFontSize=10,
        initialLeading=BODY_LEADING,
    )
    c.setTitle(f"BERRETA FUTURA design prototype — {direction.name}")
    if direction.key in {"A", "B", "C"}:
        for draw in (cover, contents): draw(c, direction); c.showPage()
        opener(c, direction, editorial=True); c.showPage()
        opener(c, direction, editorial=False); c.showPage()
        continuation(c, direction); c.showPage()
        back(c, direction); c.save()
    elif direction.key in {"D", "E", "F", "G", "H"}:
        for draw in (cover_new, contents_new): draw(c, direction); c.showPage()
        opener_new(c, direction, editorial=True); c.showPage()
        opener_new(c, direction, editorial=False); c.showPage()
        continuation_new(c, direction); c.showPage()
        back_new(c, direction); c.save()
    elif direction.key in {"I", "J", "K", "L", "M"}:
        for draw in (cover_round3, contents_round3): draw(c, direction); c.showPage()
        opener_round3(c, direction, editorial=True); c.showPage()
        opener_round3(c, direction, editorial=False); c.showPage()
        continuation_round3(c, direction); c.showPage()
        back_round3(c, direction); c.save()
    else:
        for draw in (cover_round4, contents_round4): draw(c, direction); c.showPage()
        opener_round4(c, direction, editorial=True); c.showPage()
        opener_round4(c, direction, editorial=False); c.showPage()
        continuation_round4(c, direction); c.showPage()
        back_round4(c, direction); c.save()
    return path


def render_pngs(direction: Direction, pdf: Path) -> None:
    target = PREVIEWS / direction.key
    if target.exists(): shutil.rmtree(target)
    target.mkdir(parents=True)
    subprocess.run(["pdftoppm", "-png", "-r", "144", str(pdf), str(target / "render")], check=True)
    for index, source in enumerate(sorted(target.glob("render-*.png")), 1):
        source.rename(target / f"page-{index:02d}.png")


def main() -> None:
    register_fonts(); PREVIEWS.mkdir(parents=True, exist_ok=True)
    for direction in DIRECTIONS:
        pdf = build_pdf(direction); render_pngs(direction, pdf)
        print(f"{direction.key}: {pdf.relative_to(ROOT)}")
    print(f"Gallery: {(HERE / 'index.html').relative_to(ROOT)}?variant=N")


if __name__ == "__main__":
    main()
