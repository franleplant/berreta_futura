from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .errors import DependencyError
from .manifest import Edition
from .errors import ValidationError


MAX_ARTICLE_PAGES = 7
MAX_EDITORIAL_PAGES = 2

# BERRETA FUTURA's print palette. The interior stays mostly uninked for economical
# home printing; color is reserved for navigation and hierarchy.
INK = (.075, .105, .125)
OXBLOOD = (.47, .13, .12)
SLATE = (.34, .38, .40)
SAND = (.86, .81, .71)
PALE_SAND = (.955, .935, .89)
PAPER = (.985, .975, .945)

SANS = "Inter"
SANS_MEDIUM = "Inter-Medium"
SANS_SEMIBOLD = "Inter-Semibold"
SANS_BOLD = "Inter-Bold"
SERIF = "SourceSerif4-SmText"
SERIF_ITALIC = "SourceSerif4-SmText-Italic"
SERIF_BOLD = "SourceSerif4-SmText-Bold"
SERIF_DISPLAY = "SourceSerif4-Display-Semibold"

UI_COPY = {
    "en": {
        "private_edition": "Private edition - Not for sale",
        "edition": "Edition",
        "issue": "Issue",
        "contents": "Contents",
        "editorial": "Editorial",
        "feature": "Feature",
        "by": "By",
        "original_argument": "An original argument",
        "faithful_synthesis": "Faithful synthesis",
        "faithful_edit": "Faithful edit",
        "original_editorial": "ORIGINAL EDITORIAL",
        "source_introduction": "THE SOURCE",
        "original_synthesis": "READING MAP",
        "source_record": "SOURCE RECORD",
        "production_note": "PRODUCTION NOTE",
        "colophon": "COLOPHON",
        "back_text_default": "A private anthology of writing worth keeping.",
    },
    "es": {
        "private_edition": "Edición privada - Prohibida su venta",
        "edition": "Edición",
        "issue": "Número",
        "contents": "Índice",
        "editorial": "Editorial",
        "feature": "Artículo",
        "by": "Por",
        "original_argument": "Un argumento original",
        "faithful_synthesis": "Síntesis fiel",
        "faithful_edit": "Edición fiel",
        "original_editorial": "EDITORIAL ORIGINAL",
        "source_introduction": "LA FUENTE",
        "original_synthesis": "MAPA DE LECTURA",
        "source_record": "REGISTRO DE FUENTE",
        "production_note": "NOTA DE PRODUCCIÓN",
        "colophon": "COLOFÓN",
        "back_text_default": "Una antología privada de textos que vale la pena conservar.",
    },
}


@dataclass(frozen=True)
class RenderLayout:
    toc: dict[str, int]
    article_pages: dict[str, int]
    editorial_pages: int | None


def _reportlab():
    try:
        from reportlab.lib.pagesizes import A5
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise DependencyError("PDF rendering requires ReportLab; run `uv sync --locked`.") from exc
    font_root = Path(__file__).with_name("assets") / "fonts"
    fonts = {
        SANS: font_root / "inter" / "Inter-Regular.ttf",
        SANS_MEDIUM: font_root / "inter" / "Inter-Medium.ttf",
        SANS_SEMIBOLD: font_root / "inter" / "Inter-SemiBold.ttf",
        SANS_BOLD: font_root / "inter" / "Inter-Bold.ttf",
        SERIF: font_root / "source-serif-4" / "SourceSerif4SmText-Regular.ttf",
        SERIF_ITALIC: font_root / "source-serif-4" / "SourceSerif4SmText-It.ttf",
        SERIF_BOLD: font_root / "source-serif-4" / "SourceSerif4SmText-Bold.ttf",
        SERIF_DISPLAY: font_root / "source-serif-4" / "SourceSerif4Display-Semibold.ttf",
    }
    registered = set(pdfmetrics.getRegisteredFontNames())
    for name, path in fonts.items():
        if name in registered:
            continue
        if not path.is_file():
            raise DependencyError(f"Bundled publication font is missing: {path}")
        pdfmetrics.registerFont(TTFont(name, str(path)))
    return A5, pdfmetrics, canvas


def _plain(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    replacements = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "--", "\u2026": "...", "\u00a0": " "}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("cp1252", errors="replace").decode("cp1252")


def _edition_label(edition: Edition) -> str:
    configured = str(edition.cover.get("edition_label", "")).strip()
    if configured:
        return configured
    if edition.raw.get("distribution") == "private":
        return _ui(edition, "private_edition")
    return _ui(edition, "edition")


def _ui(edition: Edition, key: str) -> str:
    language = str(getattr(edition, "language", "en")).split("-", 1)[0]
    return UI_COPY.get(language, UI_COPY["en"])[key]


def _section_label(edition: Edition, kind: str) -> str:
    if kind in {
        "original_editorial",
        "source_introduction",
        "original_synthesis",
        "source_record",
        "production_note",
        "colophon",
    }:
        return _ui(edition, kind)
    return kind.replace("_", " ").upper()


def _markdown_blocks(text: str) -> Iterable[tuple[str, str]]:
    if text.startswith("---\n"):
        _, _, text = text.partition("\n---\n")
    buffer: list[str] = []
    def flush():
        if buffer:
            value = " ".join(line.strip() for line in buffer).strip()
            buffer.clear()
            if value:
                return ("body", value)
        return None
    code: list[str] | None = None
    for line in text.splitlines():
        if code is not None:
            if line.strip().startswith("```"):
                yield "code", "\n".join(code)
                code = None
            else:
                code.append(line)
            continue
        stripped = line.strip()
        if stripped.startswith("```"):
            block = flush()
            if block:
                yield block
            code = []
        elif not stripped:
            block = flush()
            if block:
                yield block
        elif stripped.startswith("### "):
            block = flush()
            if block:
                yield block
            yield "h3", stripped[4:]
        elif stripped.startswith("## "):
            block = flush()
            if block:
                yield block
            yield "h2", stripped[3:]
        elif stripped.startswith("# "):
            block = flush()
            if block:
                yield block
            yield "h1", stripped[2:]
        elif re.match(r"^[-*] ", stripped):
            block = flush()
            if block:
                yield block
            yield "bullet", stripped[2:]
        elif stripped.startswith("> "):
            block = flush()
            if block:
                yield block
            yield "quote", stripped[2:]
        else:
            buffer.append(stripped)
    if code is not None:
        yield "code", "\n".join(code)
    block = flush()
    if block:
        yield block


class _Typesetter:
    def __init__(self, pdf, edition: Edition, pagesize, metrics):
        self.pdf, self.edition, self.width, self.height, self.metrics = pdf, edition, *pagesize, metrics
        self.left, self.right, self.top, self.bottom = 41, 37, 52, 45
        self.page = 0
        self.y = self.height - self.top
        self.section = ""
        self.toc: dict[str, int] = {}
        self.article_pages: dict[str, int] = {}
        self.editorial_pages: int | None = None

    @property
    def column_width(self) -> float:
        return self.width - self.left - self.right

    def _folio(self):
        self.pdf.setFillColorRGB(*SLATE)
        self.pdf.setFont(SANS_MEDIUM, 6.8)
        label = f"{self.page:02d}"
        if self.page % 2:
            self.pdf.drawRightString(self.width - self.right, 24, label)
        else:
            self.pdf.drawString(self.left, 24, label)

    def new_page(self, section: str = "", *, blank_header: bool = False, opener: bool = False):
        if self.page:
            self.pdf.showPage()
        self.page += 1
        self.section = section or self.section
        self.y = self.height - self.top
        if self.page > 2 and not blank_header:
            self._folio()
            if not opener:
                self.pdf.setFillColorRGB(*OXBLOOD)
                self.pdf.rect(self.left, self.height - 29, 5, 5, fill=1, stroke=0)
                self.pdf.setFillColorRGB(*SLATE)
                self.pdf.setFont(SANS_MEDIUM, 6.4)
                publication_label = (
                    self.edition.publication_name.upper()
                    + "  /  "
                    + str(self.edition.issue_number)
                )
                self.pdf.drawString(self.left + 12, self.height - 28, _plain(publication_label))
                publication_width = self.metrics.stringWidth(
                    _plain(publication_label), SANS_MEDIUM, 6.4
                )
                section_width = max(48, self.column_width - publication_width - 24)
                self.pdf.drawRightString(
                    self.width - self.right,
                    self.height - 28,
                    self.fit_text(self.section.upper(), SANS_MEDIUM, 6.4, section_width),
                )
                self.pdf.setStrokeColorRGB(*SAND)
                self.pdf.setLineWidth(.45)
                self.pdf.line(self.left, self.height - 36, self.width - self.right, self.height - 36)

    def lines(self, text: str, font: str, size: float, width: float) -> list[str]:
        words: list[str] = []
        for word in _plain(re.sub(r"[*_`]", "", text)).split():
            if self.metrics.stringWidth(word, font, size) <= width:
                words.append(word)
                continue
            chunk = ""
            for character in word:
                proposed = chunk + character
                if chunk and self.metrics.stringWidth(proposed, font, size) > width:
                    words.append(chunk)
                    chunk = character
                else:
                    chunk = proposed
            if chunk:
                words.append(chunk)
        result: list[str] = []
        current = ""
        for word in words:
            proposed = f"{current} {word}".strip()
            if current and self.metrics.stringWidth(proposed, font, size) > width:
                result.append(current)
                current = word
            else:
                current = proposed
        if current:
            result.append(current)
        return result or [""]

    def fit_text(self, text: str, font: str, size: float, width: float) -> str:
        value = _plain(text)
        if self.metrics.stringWidth(value, font, size) <= width:
            return value
        suffix = "..."
        while value and self.metrics.stringWidth(value + suffix, font, size) > width:
            value = value[:-1]
        return value.rstrip() + suffix

    def block(self, kind: str, text: str):
        styles = {
            "h1": (SERIF_DISPLAY, 22, 25, 13),
            "h2": (SERIF_DISPLAY, 14.5, 18, 8),
            "h3": (SANS_SEMIBOLD, 8.7, 12, 7),
            "lead": (SERIF, 11.6, 15.2, 11),
            "body": (SERIF, 9.55, 12.55, 5.4),
            "bullet": (SERIF, 9.45, 12.45, 5),
            "quote": (SERIF_ITALIC, 10.1, 13.7, 9),
        }
        font, size, leading, after = styles[kind]
        if kind == "h3":
            text = text.upper()
        indent = 14 if kind in {"bullet", "quote"} else 0
        lines = self.lines(text, font, size, self.column_width - indent)
        needed = len(lines) * leading + after
        keep_with_next = 25 if kind in {"h1", "h2", "h3"} else 0
        if self.y - needed - keep_with_next < self.bottom:
            self.new_page()
        if kind == "quote":
            self.pdf.setStrokeColorRGB(*OXBLOOD)
            self.pdf.setLineWidth(1.5)
            self.pdf.line(self.left + 1, self.y + 3, self.left + 1, self.y - len(lines) * leading + 5)
        self.pdf.setFillColorRGB(*(OXBLOOD if kind == "h3" else INK))
        self.pdf.setFont(font, size)
        for index, line in enumerate(lines):
            if kind == "bullet" and index == 0:
                self.pdf.setFillColorRGB(*OXBLOOD)
                self.pdf.rect(self.left + 1, self.y + 2.5, 3, 3, fill=1, stroke=0)
                self.pdf.setFillColorRGB(*INK)
            self.pdf.drawString(self.left + indent, self.y, line)
            self.y -= leading
        self.y -= after

    def code_lines(self, text: str, font: str, size: float, width: float) -> list[str]:
        """Preserve source lines and indentation, wrapping only to avoid clipping."""
        result: list[str] = []
        for source_line in text.expandtabs(4).split("\n"):
            if not source_line:
                result.append("")
                continue
            source_line = _plain(source_line)
            leading = source_line[: len(source_line) - len(source_line.lstrip())]
            continuation = leading + "  "
            if self.metrics.stringWidth(continuation + "mmmmmmmmmmmm", font, size) > width:
                continuation = ""
            remaining = source_line
            while remaining:
                end = len(remaining)
                while end > 1 and self.metrics.stringWidth(remaining[:end], font, size) > width:
                    end -= 1
                if end == len(remaining):
                    result.append(remaining)
                    break
                # Prefer a syntactic or whitespace boundary near the right edge;
                # hard character splitting is a last resort for unbroken tokens.
                minimum = max(1, end // 2)
                candidates = [
                    index + 1
                    for index, character in enumerate(remaining[:end])
                    if index + 1 >= minimum and (character.isspace() or character in ",.;(){}[]")
                ]
                split = candidates[-1] if candidates else end
                result.append(remaining[:split].rstrip())
                remaining = continuation + remaining[split:].lstrip()
        return result or [""]

    def code_block(self, text: str):
        font, size, leading = "Courier", 5.8, 7.6
        padding_x, padding_y, after = 7, 6, 8
        column_width = self.column_width
        lines = self.code_lines(text, font, size, column_width - 2 * padding_x)
        remaining = lines
        while remaining:
            available = self.y - self.bottom
            capacity = int((available - 2 * padding_y) // leading)
            if capacity < 1:
                self.new_page()
                continue
            chunk, remaining = remaining[:capacity], remaining[capacity:]
            height = 2 * padding_y + len(chunk) * leading
            bottom = self.y - height
            self.pdf.setFillColorRGB(*PALE_SAND)
            self.pdf.rect(self.left, bottom, column_width, height, fill=1, stroke=0)
            self.pdf.setStrokeColorRGB(*OXBLOOD)
            self.pdf.setLineWidth(.8)
            self.pdf.line(self.left, bottom, self.left, self.y)
            self.pdf.setFillColorRGB(.10, .10, .10)
            self.pdf.setFont(font, size)
            baseline = self.y - padding_y - size
            for line in chunk:
                self.pdf.drawString(self.left + padding_x, baseline, line)
                baseline -= leading
            self.y = bottom - after
            if remaining:
                self.new_page()

    def markdown(self, path: Path, *, lead: bool = False):
        blocks = list(_markdown_blocks(path.read_text(encoding="utf-8")))
        for index, (kind, value) in enumerate(blocks):
            if kind == "code":
                self.code_block(value)
            else:
                if lead and index == 0 and kind == "body":
                    kind = "lead"
                self.block(kind, value)

    def _label(self, text: str, *, right: str = ""):
        self.pdf.setFillColorRGB(*OXBLOOD)
        self.pdf.rect(self.left, self.y + 2, 22, 3, fill=1, stroke=0)
        self.pdf.setFont(SANS_SEMIBOLD, 6.6)
        self.pdf.drawString(self.left + 29, self.y, _plain(text.upper()))
        if right:
            self.pdf.setFillColorRGB(*SLATE)
            self.pdf.drawRightString(self.width - self.right, self.y, _plain(right.upper()))
        self.y -= 21

    def _display_title(self, title: str, *, maximum_lines: int = 5):
        size = 27.5
        lines = self.lines(title, SERIF_DISPLAY, size, self.column_width)
        while len(lines) > maximum_lines and size > 21:
            size -= .75
            lines = self.lines(title, SERIF_DISPLAY, size, self.column_width)
        leading = size * 1.04
        self.pdf.setFillColorRGB(*INK)
        self.pdf.setFont(SERIF_DISPLAY, size)
        for line in lines:
            self.pdf.drawString(self.left, self.y, line)
            self.y -= leading
        self.y -= 11

    def _credit(self, author: str, note: str = ""):
        self.pdf.setFillColorRGB(*INK)
        self.pdf.setFont(SANS_SEMIBOLD, 7.6)
        self.pdf.drawString(
            self.left,
            self.y,
            _plain(_ui(self.edition, "by").upper()) + " " + _plain(author.upper()),
        )
        if note:
            self.pdf.setFillColorRGB(*SLATE)
            self.pdf.setFont(SANS, 6.5)
            self.pdf.drawRightString(self.width - self.right, self.y, _plain(note.upper()))
        self.y -= 12
        self.pdf.setStrokeColorRGB(*SAND)
        self.pdf.setLineWidth(.65)
        self.pdf.line(self.left, self.y, self.width - self.right, self.y)
        self.y -= 18

    def cover(self):
        self.new_page(blank_header=True)
        if self.edition.cover_art:
            from reportlab.lib.utils import ImageReader
            image = ImageReader(str(self.edition.cover_art))
            image_width, image_height = image.getSize()
            scale = max(self.width / image_width, self.height / image_height)
            draw_width, draw_height = image_width * scale, image_height * scale
            self.pdf.drawImage(image, (self.width - draw_width) / 2, (self.height - draw_height) / 2,
                               draw_width, draw_height, preserveAspectRatio=True, mask="auto")
            self.pdf.setFillColorRGB(*PAPER, alpha=.94)
            self.pdf.rect(0, self.height - 203, self.width, 203, fill=1, stroke=0)
        else:
            self.pdf.setFillColorRGB(.07, .08, .09)
            self.pdf.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        ink = INK if self.edition.cover_art else PAPER
        self.pdf.setFillColorRGB(*ink)
        self.pdf.setFont(SANS_BOLD, 9.5)
        self.pdf.drawString(36, self.height - 31, _plain(self.edition.publication_name.upper()))
        self.pdf.setFillColorRGB(*OXBLOOD)
        self.pdf.rect(self.width - 57, self.height - 34, 21, 5, fill=1, stroke=0)
        self.pdf.setFillColorRGB(*ink)
        self.pdf.setFont(SERIF_DISPLAY, 30)
        title_lines = self.lines(str(self.edition.cover.get("headline", self.edition.title)), SERIF_DISPLAY, 30, self.width - 72)
        y = self.height - 72
        for line in title_lines:
            self.pdf.drawString(36, y, line)
            y -= 31
        deck = str(self.edition.cover.get("deck", "")).strip()
        if deck:
            y -= 5
            self.pdf.setFont(SANS, 8.2)
            for line in self.lines(deck, SANS, 8.2, self.width - 72):
                self.pdf.drawString(36, y, line)
                y -= 10.5
        self.pdf.setFillColorRGB(*INK)
        self.pdf.setFont(SANS_SEMIBOLD, 6.7)
        label = _plain(_edition_label(self.edition)).upper()
        self.pdf.drawString(
            36,
            27,
            f"{_plain(_ui(self.edition, 'issue').upper())} {self.edition.issue_number}"
            f"  /  {self.edition.publication_date}  /  {label}",
        )

    def contents(self, toc_pages: dict[str, int]):
        contents_label = _ui(self.edition, "contents")
        self.new_page(contents_label, blank_header=True)
        self.pdf.setFillColorRGB(*INK)
        self.pdf.rect(0, self.height - 116, self.width, 116, fill=1, stroke=0)
        self.pdf.setFillColorRGB(*PAPER)
        self.pdf.setFont(SANS_SEMIBOLD, 7)
        self.pdf.drawString(
            self.left,
            self.height - 32,
            _plain(self.edition.publication_name.upper())
            + "  /  "
            + _plain(_ui(self.edition, "issue").upper())
            + " "
            + str(self.edition.issue_number),
        )
        self.pdf.setFont(SERIF_DISPLAY, 28)
        self.pdf.drawString(self.left, self.height - 73, _plain(contents_label))
        self.pdf.setFont(SANS, 6.6)
        self.pdf.drawString(self.left, self.height - 96, _plain(str(self.edition.publication_date)).upper())
        self.y = self.height - 145
        entries = []
        if self.edition.articles:
            if self.edition.editorial:
                entries.append((_ui(self.edition, "editorial"), self.edition.editorial.title, self.edition.editorial.byline, toc_pages.get("editorial", 0)))
            entries.extend((f"{_ui(self.edition, 'feature')} {index:02d}", article.title, article.author, toc_pages.get(article.id, 0)) for index, article in enumerate(self.edition.articles, 1))
            entries.extend((_section_label(self.edition, section.kind), section.title, "", toc_pages.get(f"section-{index}", 0)) for index, section in enumerate(self.edition.sections))
        elif self.edition.sections:
            entries.extend((_section_label(self.edition, section.kind), section.title, "", toc_pages.get(f"section-{index}", 0)) for index, section in enumerate(self.edition.sections))
        for label, title, author, page in entries:
            if self.y < self.bottom + 34:
                self.new_page("Contents")
            self.pdf.setFillColorRGB(*OXBLOOD)
            self.pdf.setFont(SANS_SEMIBOLD, 6.1)
            self.pdf.drawString(self.left, self.y, _plain(label.upper()))
            self.pdf.setFillColorRGB(*INK)
            self.pdf.setFont(SERIF_DISPLAY, 10.8)
            title_lines = self.lines(title, SERIF_DISPLAY, 10.8, self.column_width - 31)
            title_lines = title_lines[:2]
            title_y = self.y - 12
            for line in title_lines:
                self.pdf.drawString(self.left, title_y, line)
                title_y -= 12
            self.pdf.setFont(SANS_SEMIBOLD, 8)
            self.pdf.drawRightString(self.width - self.right, self.y - 10, str(page) if page else "")
            if author:
                self.pdf.setFillColorRGB(*SLATE)
                self.pdf.setFont(SANS, 6.3)
                self.pdf.drawString(self.left, title_y - 1, _plain(author.upper()))
            row_height = max(43, 29 + 12 * (len(title_lines) - 1))
            self.y -= row_height

    def body(self):
        if self.edition.articles:
            if self.edition.editorial:
                self.new_page(_ui(self.edition, "editorial"), opener=True)
                start_page = self.page
                self.toc["editorial"] = self.page
                self._label(
                    self.edition.editorial.label,
                    right=_ui(self.edition, "issue") + " " + str(self.edition.issue_number),
                )
                self._display_title(self.edition.editorial.title, maximum_lines=3)
                self._credit(self.edition.editorial.byline, _ui(self.edition, "original_argument"))
                self.markdown(self.edition.editorial.path, lead=True)
                self.editorial_pages = self.page - start_page + 1
                if self.editorial_pages > MAX_EDITORIAL_PAGES:
                    raise ValidationError(
                        f"Editorial spans {self.editorial_pages} reader pages; the hard cap is "
                        f"{MAX_EDITORIAL_PAGES}. Condense it before building."
                    )
            article_total = len(self.edition.articles)
            for article_index, article in enumerate(self.edition.articles, 1):
                self.new_page(article.title, opener=True)
                start_page = self.page
                self.toc[article.id] = self.page
                mode = _ui(self.edition, "faithful_synthesis") if article.content_mode == "faithful_synthesis" else _ui(self.edition, "faithful_edit")
                self._label(f"{_ui(self.edition, 'feature')} {article_index:02d}", right=f"{article_index} / {article_total}")
                self._display_title(article.title)
                self._credit(article.author, mode)
                self.markdown(article.manuscript, lead=True)
                page_count = self.page - start_page + 1
                self.article_pages[article.id] = page_count
                if page_count > MAX_ARTICLE_PAGES:
                    raise ValidationError(
                        f"Article {article.id} spans {page_count} reader pages; the hard cap is "
                        f"{MAX_ARTICLE_PAGES}. Condense it as a faithful_synthesis before building."
                    )
            for index, section in enumerate(self.edition.sections):
                self._section(index, section)
            return
        if self.edition.sections:
            for index, section in enumerate(self.edition.sections):
                self._section(index, section)
            return

    def _section(self, index, section):
        self.new_page(section.title, opener=True)
        self.toc[f"section-{index}"] = self.page
        label = _section_label(self.edition, section.kind)
        self._label(label, right=_ui(self.edition, "issue") + " " + str(self.edition.issue_number))
        self._display_title(section.title, maximum_lines=3)
        self.markdown(section.path, lead=True)

    def back_cover(self):
        configured = self.edition.raw.get("format", {}).get("target_pages")
        minimum_total = self.page + 1
        target = int(configured) if configured else ((minimum_total + 3) // 4) * 4
        target = max(target, minimum_total)
        target = ((target + 3) // 4) * 4
        while self.page < target - 1:
            self.new_page(blank_header=True)
        self.new_page(blank_header=True)
        self.pdf.setFillColorRGB(*PAPER)
        self.pdf.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        self.pdf.setFillColorRGB(*OXBLOOD)
        self.pdf.rect(0, self.height - 14, self.width, 14, fill=1, stroke=0)
        self.pdf.setFillColorRGB(*INK)
        text = str(self.edition.cover.get("back_text", _ui(self.edition, "back_text_default")))
        y = self.height * .58
        self.pdf.setFont(SERIF_DISPLAY, 17)
        for line in self.lines(text, SERIF_DISPLAY, 17, self.width - 90):
            self.pdf.drawString(45, y, line)
            y -= 21.5
        self.pdf.setStrokeColorRGB(*SAND)
        self.pdf.line(45, 57, self.width - 45, 57)
        self.pdf.setFont(SANS_SEMIBOLD, 6.7)
        self.pdf.drawString(45, 40, _plain(_edition_label(self.edition)).upper())
        self.pdf.setFont(SANS, 7)
        self.pdf.drawString(45, 25, _plain(self.edition.title))


def _render_pass(target, edition: Edition, toc: dict[str, int] | None = None) -> RenderLayout:
    A5, metrics, canvas = _reportlab()
    pdf = canvas.Canvas(target, pagesize=A5, pageCompression=1, invariant=1)
    pdf.setTitle(_plain(edition.title))
    pdf.setAuthor(_plain(edition.publication_name))
    pdf.setCreator("magazine-compiler")
    typesetter = _Typesetter(pdf, edition, A5, metrics)
    typesetter.cover()
    typesetter.contents(toc or {})
    typesetter.body()
    typesetter.back_cover()
    pdf.save()
    return RenderLayout(
        dict(typesetter.toc), dict(typesetter.article_pages), typesetter.editorial_pages
    )


def render_a5(edition: Edition, output: Path) -> RenderLayout:
    """Render an edition twice so the deterministic contents page has folios."""
    configured_cap = edition.raw.get("format", {}).get("max_article_pages", MAX_ARTICLE_PAGES)
    try:
        configured_cap = int(configured_cap)
    except (TypeError, ValueError) as exc:
        raise ValidationError("format.max_article_pages must be the integer 7") from exc
    if configured_cap != MAX_ARTICLE_PAGES:
        raise ValidationError(
            f"format.max_article_pages is a hard publication rule and must remain {MAX_ARTICLE_PAGES}"
        )
    configured_editorial_cap = edition.raw.get("format", {}).get(
        "max_editorial_pages", MAX_EDITORIAL_PAGES
    )
    try:
        configured_editorial_cap = int(configured_editorial_cap)
    except (TypeError, ValueError) as exc:
        raise ValidationError("format.max_editorial_pages must be the integer 2") from exc
    if configured_editorial_cap != MAX_EDITORIAL_PAGES:
        raise ValidationError(
            f"format.max_editorial_pages is a hard publication rule and must remain "
            f"{MAX_EDITORIAL_PAGES}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    draft = _render_pass(io.BytesIO(), edition)
    final = _render_pass(str(output), edition, draft.toc)
    if (
        draft.article_pages != final.article_pages
        or draft.editorial_pages != final.editorial_pages
    ):
        raise ValidationError("Content pagination changed between deterministic render passes")
    return final
