from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .errors import DependencyError, ValidationError
from .manifest import Edition


MAX_ARTICLE_PAGES = 7
MAX_EDITORIAL_PAGES = 2
DESIGN_MONUMENT = "monument"
DESIGN_LABEL = "O / Monument"

BASE = 3.15
GRID_GUTTER = BASE * 3
BODY_SIZE = 9.55
BODY_LEADING = BASE * 4
CAPTION_SIZE = 7.0
COVER_ART_SIZE_POINTS = (250.0, 250.0)

# Monument uses the sheet itself as the paper color. Violet is reserved for
# hierarchy and typographic furniture so interiors remain economical to print.
INK = (.055, .075, .085)
VIOLET = (.25, .10, .43)
SLATE = (.31, .35, .37)
COOL_GRAY = (.88, .89, .90)
PALE_VIOLET = (.955, .945, .975)
WHITE = (1, 1, 1)

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
        "selected_extracts": "Selected extracts",
        "content_original_synthesis": "Original synthesis",
        "original_editorial": "ORIGINAL EDITORIAL",
        "source_introduction": "THE SOURCE",
        "original_synthesis": "READING MAP",
        "source_record": "SOURCE RECORD",
        "production_note": "PRODUCTION NOTE",
        "colophon": "COLOPHON",
        "back_text_default": "A private anthology of writing worth keeping.",
        "opening_sentence": "Opening sentence / Original editorial",
        "issue_statement": "Issue statement / The editors",
        "continued": "Continued",
        "end": "End",
        "closing_plate": "Closing plate / Private edition",
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
        "selected_extracts": "Extractos seleccionados",
        "content_original_synthesis": "Síntesis original",
        "original_editorial": "EDITORIAL ORIGINAL",
        "source_introduction": "LA FUENTE",
        "original_synthesis": "MAPA DE LECTURA",
        "source_record": "REGISTRO DE FUENTE",
        "production_note": "NOTA DE PRODUCCIÓN",
        "colophon": "COLOFÓN",
        "back_text_default": "Una antología privada de textos que vale la pena conservar.",
        "opening_sentence": "Frase inicial / Editorial original",
        "issue_statement": "Declaración del número / La redacción",
        "continued": "Continuación",
        "end": "Fin",
        "closing_plate": "Lámina final / Edición privada",
    },
}


@dataclass(frozen=True)
class RenderLayout:
    toc: dict[str, int]
    article_pages: dict[str, int]
    editorial_pages: int | None
    design: str
    cover_art_size_points: tuple[float, float] | None


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


def _content_mode_label(edition: Edition, mode: str) -> str:
    if mode not in {
        "faithful_edit",
        "faithful_synthesis",
        "selected_extracts",
        "original_synthesis",
    }:
        raise ValidationError(f"Unsupported article content mode: {mode}")
    key = "content_original_synthesis" if mode == "original_synthesis" else mode
    return _ui(edition, key)


def _opening_sentence(text: str) -> tuple[str, str]:
    """Split the exact first sentence for Monument's editorial display."""
    match = re.search(r"(?<=[.!?])(?:[\"'»”)]*)\s+", text)
    if not match:
        return text.strip(), ""
    return text[: match.start()].strip(), text[match.end() :].strip()


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
    def __init__(self, pdf, edition: Edition, pagesize, metrics, *, design: str):
        self.pdf, self.edition, self.width, self.height, self.metrics = pdf, edition, *pagesize, metrics
        self.design = design
        self.inner, self.outer, self.top, self.bottom = 44.0, 34.0, 52.0, 45.0
        self.left, self.right = self.inner, self.outer
        self.page = 0
        self.section = ""
        self.toc: dict[str, int] = {}
        self.article_pages: dict[str, int] = {}
        self.editorial_pages: int | None = None
        self.cover_art_size_points: tuple[float, float] | None = None
        self.reading_size = BODY_SIZE
        self.reading_leading = BODY_LEADING
        self.paragraph_after = 5.4
        self.continuation_columns = 1
        self.frame_count = 1
        self.frame_index = 0
        self.frame_left = self.left
        self.frame_width = self.live_width
        self.frame_top = self.height - self.top
        self.frame_bottom = self.bottom
        self.y = self.frame_top

    @property
    def live_width(self) -> float:
        return self.width - self.left - self.right

    @property
    def column_width(self) -> float:
        return self.frame_width

    @property
    def grid_column_width(self) -> float:
        return (self.live_width - 5 * GRID_GUTTER) / 6

    def grid_box(self, start: int, span: int) -> tuple[float, float]:
        x = self.left + start * (self.grid_column_width + GRID_GUTTER)
        width = span * self.grid_column_width + (span - 1) * GRID_GUTTER
        return x, width

    def _set_page_margins(self) -> None:
        if self.page % 2:
            self.left, self.right = self.inner, self.outer
        else:
            self.left, self.right = self.outer, self.inner

    def _configure_frames(
        self,
        columns: int,
        *,
        top: float | None = None,
        bottom: float | None = None,
    ) -> None:
        self.frame_count = columns
        self.frame_index = 0
        default_top = self.height - (44 if columns == 2 else self.top)
        default_bottom = 40 if columns == 2 else self.bottom
        self.frame_top = default_top if top is None else top
        self.frame_bottom = default_bottom if bottom is None else bottom
        self._select_frame(0)

    def _select_frame(self, index: int) -> None:
        self.frame_index = index
        if self.frame_count == 1:
            self.frame_left = self.left
            self.frame_width = self.live_width
        else:
            self.frame_width = (self.live_width - GRID_GUTTER) / 2
            self.frame_left = self.left + index * (self.frame_width + GRID_GUTTER)
        self.y = self.frame_top

    def _set_custom_frame(self, x: float, width: float, *, top: float, bottom: float | None = None) -> None:
        self.frame_count = 1
        self.frame_index = 0
        self.frame_left = x
        self.frame_width = width
        self.frame_top = top
        self.frame_bottom = self.bottom if bottom is None else bottom
        self.y = top

    def _advance_frame(self) -> None:
        if self.frame_index + 1 < self.frame_count:
            self._select_frame(self.frame_index + 1)
            return
        self.new_page(columns=self.continuation_columns)

    def _folio(self):
        outer_x = self.left if self.page % 2 == 0 else self.width - self.right
        direction = 17 if self.page % 2 == 0 else -17
        self.pdf.setStrokeColorRGB(*VIOLET)
        self.pdf.setLineWidth(.8)
        self.pdf.line(outer_x, 35, outer_x + direction, 35)
        self.pdf.setFillColorRGB(*INK)
        self.pdf.setFont(SANS_MEDIUM, CAPTION_SIZE)
        label = f"{self.page:02d}"
        running = _plain(
            f"{self.edition.publication_name.upper()} / {self.edition.title.upper()}"
        )
        if self.page % 2:
            self.pdf.drawString(self.left, 17, self.fit_text(running, SANS_MEDIUM, CAPTION_SIZE, self.live_width - 35))
            self.pdf.drawRightString(self.width - self.right, 17, label)
        else:
            self.pdf.drawString(self.left, 17, label)
            self.pdf.drawRightString(
                self.width - self.right,
                17,
                self.fit_text(running, SANS_MEDIUM, CAPTION_SIZE, self.live_width - 35),
            )

    def _running_header(self) -> None:
        y = self.height - 31
        publication = _plain(
            f"{self.edition.publication_name.upper()} / {_ui(self.edition, 'issue').upper()} "
            f"{self.edition.issue_number}"
        )
        section = _plain(f"{self.section.upper()} / {_ui(self.edition, 'continued').upper()}")
        self.pdf.setFillColorRGB(*INK)
        self.pdf.setFont(SANS_MEDIUM, CAPTION_SIZE)
        self.pdf.drawString(
            self.left,
            y,
            self.fit_text(publication, SANS_MEDIUM, CAPTION_SIZE, self.live_width * .46),
        )
        self.pdf.drawRightString(
            self.width - self.right,
            y,
            self.fit_text(section, SANS_MEDIUM, CAPTION_SIZE, self.live_width * .49),
        )
        outer_x = self.outer / 2 if self.page % 2 == 0 else self.width - self.outer / 2
        self.pdf.setFillColorRGB(*VIOLET)
        self.pdf.circle(outer_x, y + 2, 3.2, fill=1, stroke=0)

    def new_page(
        self,
        section: str = "",
        *,
        blank_header: bool = False,
        opener: bool = False,
        columns: int | None = None,
    ):
        if self.page:
            self.pdf.showPage()
        self.page += 1
        self._set_page_margins()
        self.section = section or self.section
        self._configure_frames(1 if opener else (columns or self.continuation_columns))
        if self.page > 2 and not blank_header:
            self._folio()
            if not opener:
                self._running_header()

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
            "h2": (SERIF_DISPLAY, 17.5, 20.5, 10),
            "h3": (SANS_SEMIBOLD, 8.7, 12, 7),
            "lead": (SERIF, 11.6, 15.2, 11),
            "body": (SERIF, self.reading_size, self.reading_leading, self.paragraph_after),
            "bullet": (SERIF, 9.45, self.reading_leading, 5),
            "quote": (SERIF_ITALIC, 10.1, 13.7, 9),
        }
        font, size, leading, after = styles[kind]
        if kind == "h3":
            text = text.upper()
        indent = 14 if kind in {"bullet", "quote"} else 0
        lines = self.lines(text, font, size, self.column_width - indent)
        if kind in {"h1", "h2", "h3"}:
            self.y = min(self.y, self.height - self.top)
            needed = len(lines) * leading + after
            if self.y - needed - 25 < self.frame_bottom:
                self._advance_frame()
                lines = self.lines(text, font, size, self.column_width - indent)
                needed = len(lines) * leading + after
            if self.y - needed < self.frame_bottom:
                raise ValidationError(
                    f"A {kind} block is too tall for the Monument text frame"
                )
            self.pdf.setFillColorRGB(*(VIOLET if kind in {"h2", "h3"} else INK))
            self.pdf.setFont(font, size)
            for line in lines:
                self.pdf.drawString(self.frame_left, self.y, line)
                self.y -= leading
            self.y -= after
            return

        remaining_text = text
        first_line = True
        while remaining_text:
            current_lines = self.lines(
                remaining_text,
                font,
                size,
                self.column_width - indent,
            )
            capacity = int((self.y - self.frame_bottom) // leading)
            minimum = 1 if len(current_lines) == 1 else 2
            if capacity < minimum:
                self._advance_frame()
                continue
            take = min(capacity, len(current_lines))
            if len(current_lines) - take == 1 and take > 2:
                take -= 1
            chunk = current_lines[:take]
            remaining_text = " ".join(current_lines[take:])
            if kind == "quote":
                self.pdf.setStrokeColorRGB(*VIOLET)
                self.pdf.setLineWidth(1.5)
                self.pdf.line(
                    self.frame_left + 1,
                    self.y + 3,
                    self.frame_left + 1,
                    self.y - len(chunk) * leading + 5,
                )
            self.pdf.setFillColorRGB(*INK)
            self.pdf.setFont(font, size)
            for line in chunk:
                if kind == "bullet" and first_line:
                    self.pdf.setFillColorRGB(*VIOLET)
                    self.pdf.circle(self.frame_left + 2.5, self.y + 4, 2.5, fill=1, stroke=0)
                    self.pdf.setFillColorRGB(*INK)
                self.pdf.drawString(self.frame_left + indent, self.y, line)
                self.y -= leading
                first_line = False
            if remaining_text:
                self._advance_frame()
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
        if self.frame_count != 1 or self.frame_width != self.live_width:
            self.new_page(columns=1)
        column_width = self.live_width
        lines = self.code_lines(text, font, size, column_width - 2 * padding_x)
        remaining = lines
        while remaining:
            available = self.y - self.frame_bottom
            capacity = int((available - 2 * padding_y) // leading)
            if capacity < 1:
                self.new_page(columns=1)
                continue
            chunk, remaining = remaining[:capacity], remaining[capacity:]
            height = 2 * padding_y + len(chunk) * leading
            bottom = self.y - height
            self.pdf.setFillColorRGB(*PALE_VIOLET)
            self.pdf.rect(self.frame_left, bottom, column_width, height, fill=1, stroke=0)
            self.pdf.setStrokeColorRGB(*VIOLET)
            self.pdf.setLineWidth(.8)
            self.pdf.line(self.frame_left, bottom, self.frame_left, self.y)
            self.pdf.setFillColorRGB(.10, .10, .10)
            self.pdf.setFont(font, size)
            baseline = self.y - padding_y - size
            for line in chunk:
                self.pdf.drawString(self.frame_left + padding_x, baseline, line)
                baseline -= leading
            self.y = bottom - after
            if remaining:
                self.new_page(columns=1)

    def markdown(self, path: Path, *, lead: bool = False):
        self._render_blocks(list(_markdown_blocks(path.read_text(encoding="utf-8"))), lead=lead)

    def _render_blocks(self, blocks: list[tuple[str, str]], *, lead: bool = False) -> None:
        for index, (kind, value) in enumerate(blocks):
            if kind == "code":
                self.code_block(value)
            else:
                if lead and index == 0 and kind == "body":
                    kind = "lead"
                self.block(kind, value)

    def _tracked_label(
        self,
        text: str,
        x: float,
        y: float,
        width: float,
        *,
        color=INK,
        tracking: float = .45,
        align: str = "left",
    ) -> None:
        value = _plain(text.upper())

        def measured(candidate: str) -> float:
            return sum(
                self.metrics.stringWidth(character, SANS_MEDIUM, CAPTION_SIZE)
                for character in candidate
            ) + tracking * max(0, len(candidate) - 1)

        if measured(value) > width:
            suffix = "..."
            while value and measured(value.rstrip() + suffix) > width:
                value = value[:-1]
            value = value.rstrip() + suffix
        total = measured(value)
        cursor = x + width - total if align == "right" else x
        self.pdf.setFillColorRGB(*color)
        label = self.pdf.beginText()
        label.setTextOrigin(cursor, y)
        label.setFont(SANS_MEDIUM, CAPTION_SIZE)
        label.setCharSpace(tracking)
        label.textLine(value)
        self.pdf.drawText(label)

    def _rotated_label(self, text: str, x: float, y: float, height: float, *, color=VIOLET) -> None:
        self.pdf.saveState()
        self.pdf.translate(x + CAPTION_SIZE, y)
        self.pdf.rotate(90)
        self._tracked_label(text, 0, 0, height, color=color, tracking=.35)
        self.pdf.restoreState()

    def _label(self, text: str, *, right: str = ""):
        half = (self.live_width - GRID_GUTTER) / 2
        self._tracked_label(text, self.left, self.y, half, color=VIOLET)
        if right:
            self._tracked_label(
                right,
                self.width - self.right - half,
                self.y,
                half,
                color=INK,
                align="right",
            )
        self.y -= 25

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
            self.pdf.drawString(self.frame_left, self.y, line)
            self.y -= leading
        self.y -= 11

    def _credit(self, author: str, note: str = "", *, author_note: str = ""):
        self.pdf.setFillColorRGB(*INK)
        self.pdf.setFont(SANS_SEMIBOLD, 7.4)
        self.pdf.drawString(
            self.frame_left,
            self.y,
            self.fit_text(
                _plain(_ui(self.edition, "by").upper()) + " " + _plain(author.upper()),
                SANS_SEMIBOLD,
                7.4,
                self.column_width * .57,
            ),
        )
        if note:
            self.pdf.setFillColorRGB(*VIOLET)
            self.pdf.setFont(SANS_MEDIUM, CAPTION_SIZE)
            self.pdf.drawRightString(
                self.frame_left + self.column_width,
                self.y,
                self.fit_text(_plain(note.upper()), SANS_MEDIUM, CAPTION_SIZE, self.column_width * .4),
            )
        self.y -= 12
        if author_note:
            self.pdf.setFillColorRGB(*SLATE)
            self.pdf.setFont(SANS, CAPTION_SIZE)
            note_lines = self.lines(author_note, SANS, CAPTION_SIZE, self.column_width)
            if len(note_lines) > 2:
                raise ValidationError(
                    f"Author note for {author} is too long for the article opener"
                )
            for line in note_lines:
                self.pdf.drawString(self.frame_left, self.y, _plain(line))
                self.y -= BASE * 3
            self.y -= BASE
        self.y -= 13

    def _fitted_title_box(
        self,
        text: str,
        x: float,
        top: float,
        width: float,
        height: float,
        *,
        maximum: float,
        minimum: float,
        maximum_lines: int,
        color=INK,
        leading_ratio: float = 1.0,
    ) -> float:
        size = maximum
        while size >= minimum:
            lines = self.lines(text, SERIF_DISPLAY, size, width)
            leading = size * leading_ratio
            if len(lines) <= maximum_lines and size + (len(lines) - 1) * leading <= height:
                break
            size -= .5
        else:
            raise ValidationError(f"Title cannot fit the Monument display box: {text}")
        self.pdf.setFillColorRGB(*color)
        self.pdf.setFont(SERIF_DISPLAY, size)
        baseline = top - size
        for line in lines:
            self.pdf.drawString(x, baseline, line)
            baseline -= leading
        return baseline

    def _monument_parts(self, title: str, emphasis: str) -> tuple[str, str, str]:
        if emphasis:
            match = re.search(re.escape(emphasis), title, flags=re.IGNORECASE)
        else:
            stopwords = {
                "a", "an", "and", "for", "of", "on", "the", "to", "us", "use", "what", "will",
                "de", "del", "el", "en", "la", "las", "los", "nos", "para", "por", "que", "un", "una", "uso", "y",
            }
            candidates = [
                item
                for item in re.finditer(r"[^\W\d_][\w'-]*", title, flags=re.UNICODE)
                if item.group(0).casefold() not in stopwords
            ]
            match = max(candidates, key=lambda item: (len(item.group(0)), -item.start()), default=None)
        if not match:
            return "", title, ""
        return title[: match.start()].strip(), match.group(0), title[match.end() :].strip()

    def _monument_title(
        self,
        title: str,
        emphasis: str,
        x: float,
        top: float,
        width: float,
        height: float,
    ) -> float:
        prefix, focus, suffix = self._monument_parts(_plain(title), _plain(emphasis))
        bottom = top - height
        cursor = top
        if prefix:
            prefix_lines = self.lines(prefix.upper(), SANS_MEDIUM, 13, width)
            if len(prefix_lines) > 2:
                prefix_lines = self.lines(prefix.upper(), SANS_MEDIUM, 11.5, width)
                prefix_size, prefix_leading = 11.5, 14
            else:
                prefix_size, prefix_leading = 13, 15.5
            self.pdf.setFillColorRGB(*INK)
            self.pdf.setFont(SANS_MEDIUM, prefix_size)
            for line in prefix_lines:
                self.pdf.drawString(x, cursor - prefix_size, line)
                cursor -= prefix_leading
            cursor -= 5
        focus_size = 54.0
        while focus_size > 28 and self.metrics.stringWidth(focus.upper(), SANS_SEMIBOLD, focus_size) > width:
            focus_size -= .5
        self.pdf.setFillColorRGB(*VIOLET)
        self.pdf.setFont(SANS_SEMIBOLD, focus_size)
        self.pdf.drawString(x, cursor - focus_size, focus.upper())
        cursor -= focus_size + 8
        if suffix:
            remaining = cursor - bottom
            if remaining < 28:
                raise ValidationError(f"Monument title has no room for its suffix: {title}")
            cursor = self._fitted_title_box(
                suffix,
                x,
                cursor,
                width,
                remaining,
                maximum=22,
                minimum=14,
                maximum_lines=4,
                leading_ratio=1.04,
            )
        return cursor

    def _draw_image_fill(self, path: Path, x: float, y: float, width: float, height: float) -> None:
        from reportlab.lib.utils import ImageReader

        image = ImageReader(str(path))
        image_width, image_height = image.getSize()
        scale = max(width / image_width, height / image_height)
        draw_width, draw_height = image_width * scale, image_height * scale
        clip = self.pdf.beginPath()
        clip.rect(x, y, width, height)
        self.pdf.saveState()
        self.pdf.clipPath(clip, stroke=0, fill=0)
        self.pdf.drawImage(
            image,
            x + (width - draw_width) / 2,
            y + (height - draw_height) / 2,
            draw_width,
            draw_height,
            preserveAspectRatio=True,
            mask="auto",
        )
        self.pdf.restoreState()
        self.cover_art_size_points = (width, height)

    def cover(self):
        self.new_page(blank_header=True)
        self.pdf.setFillColorRGB(*WHITE)
        self.pdf.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        masthead = (
            f"{self.edition.publication_name} / {_ui(self.edition, 'issue')} "
            f"{self.edition.issue_number}"
        )
        self._tracked_label(masthead, self.left, self.height - 29, self.live_width)

        title_x, title_width = self.grid_box(0, 4)
        self._fitted_title_box(
            str(self.edition.cover.get("headline", self.edition.title)),
            title_x,
            self.height - 57,
            title_width,
            84,
            maximum=35,
            minimum=23,
            maximum_lines=3,
            leading_ratio=.98,
        )
        medallion_x, medallion_width = self.grid_box(4, 2)
        center_x, center_y = medallion_x + medallion_width / 2, self.height - 84
        self.pdf.setFillColorRGB(*VIOLET)
        self.pdf.circle(center_x, center_y, 24, fill=1, stroke=0)
        issue_mark = str(self.edition.issue_number).zfill(2)[-2:]
        self.pdf.setFillColorRGB(*WHITE)
        self.pdf.setFont(SANS_SEMIBOLD, 15)
        self.pdf.drawCentredString(center_x, center_y - 5, issue_mark)

        art_width, art_height = COVER_ART_SIZE_POINTS
        art_x, art_y = self.width - self.right - art_width, 177.0
        if self.edition.cover_art:
            self._draw_image_fill(self.edition.cover_art, art_x, art_y, art_width, art_height)
        else:
            self.pdf.setFillColorRGB(*VIOLET)
            self.pdf.rect(art_x, art_y, art_width, art_height, fill=1, stroke=0)
            self.pdf.setStrokeColorRGB(*WHITE)
            self.pdf.setLineWidth(1)
            self.pdf.circle(art_x + art_width / 2, art_y + art_height / 2, 56, fill=0, stroke=1)
        self.pdf.setStrokeColorRGB(*INK)
        self.pdf.setLineWidth(.7)
        self.pdf.rect(art_x, art_y, art_width, art_height, fill=0, stroke=1)

        subject = str(self.edition.raw.get("subtitle") or self.edition.cover.get("deck") or self.edition.title)
        subject = re.split(r"\s+(?:in the age|en la era)\s+", subject, maxsplit=1, flags=re.IGNORECASE)[0]
        subject = re.sub(r",?\s+(?:and|y)\s+", " / ", subject, flags=re.IGNORECASE).replace(",", " / ")
        self._rotated_label(subject, self.left, art_y, art_height, color=VIOLET)
        self._tracked_label(
            f"Cover / {self.edition.publication_date}",
            art_x,
            art_y - 25,
            art_width,
            color=VIOLET,
        )

        deck = str(self.edition.cover.get("deck", "")).strip()
        if deck:
            deck_lines = self.lines(deck, SANS, 7.8, art_width)
            if len(deck_lines) > 5:
                raise ValidationError("Cover deck is too long for the Monument cover")
            self.pdf.setFillColorRGB(*INK)
            self.pdf.setFont(SANS, 7.8)
            baseline = art_y - 48
            for line in deck_lines:
                self.pdf.drawString(art_x, baseline, line)
                baseline -= BASE * 3

        self.pdf.setFillColorRGB(*INK)
        self.pdf.setFont(SANS_MEDIUM, CAPTION_SIZE)
        label = _plain(_edition_label(self.edition)).upper()
        self.pdf.drawString(
            self.left,
            17,
            f"{_plain(_ui(self.edition, 'issue').upper())} {self.edition.issue_number}"
            f" / {self.edition.publication_date}",
        )
        self.pdf.drawRightString(
            self.width - self.right,
            17,
            self.fit_text(label, SANS_MEDIUM, CAPTION_SIZE, self.live_width * .55),
        )

    def contents(self, toc_pages: dict[str, int]):
        contents_label = _ui(self.edition, "contents")
        entries: list[tuple[str, str, str, int]] = []
        if self.edition.articles:
            if self.edition.editorial:
                entries.append((_ui(self.edition, "editorial"), self.edition.editorial.title, self.edition.editorial.byline, toc_pages.get("editorial", 0)))
            entries.extend((f"{_ui(self.edition, 'feature')} {index:02d}", article.title, article.author, toc_pages.get(article.id, 0)) for index, article in enumerate(self.edition.articles, 1))
            entries.extend((_section_label(self.edition, section.kind), section.title, "", toc_pages.get(f"section-{index}", 0)) for index, section in enumerate(self.edition.sections))
        elif self.edition.sections:
            entries.extend((_section_label(self.edition, section.kind), section.title, "", toc_pages.get(f"section-{index}", 0)) for index, section in enumerate(self.edition.sections))
        chunks = [entries[index : index + 6] for index in range(0, len(entries), 6)] or [[]]
        for sheet_index, chunk in enumerate(chunks):
            self.new_page(contents_label, blank_header=True)
            self._folio()
            kicker = (
                f"{_ui(self.edition, 'issue')} {self.edition.issue_number} / {contents_label}"
            )
            if sheet_index:
                kicker += f" / {sheet_index + 1:02d}"
            self._tracked_label(kicker, self.left, self.height - 31, self.live_width)
            title_x, title_width = self.grid_box(0, 4)
            self._fitted_title_box(
                contents_label,
                title_x,
                self.height - 57,
                title_width,
                40,
                maximum=27,
                minimum=22,
                maximum_lines=2,
            )
            medallion_x, medallion_width = self.grid_box(5, 1)
            center_x, center_y = medallion_x + medallion_width / 2, self.height - 78
            self.pdf.setFillColorRGB(*VIOLET)
            self.pdf.circle(center_x, center_y, 18, fill=1, stroke=0)
            self.pdf.setFillColorRGB(*WHITE)
            self.pdf.setFont(SANS_SEMIBOLD, 10)
            self.pdf.drawCentredString(
                center_x,
                center_y - 4,
                str(self.edition.issue_number).zfill(2)[-2:],
            )

            row_top = 479.0
            row_height = 393.0 / 6
            for row_index, (label, title, author, page_number) in enumerate(chunk):
                indent = 0 if row_index % 2 == 0 else self.grid_column_width + GRID_GUTTER
                x = self.left + indent
                available = self.live_width - indent
                top = row_top - row_index * row_height
                folio = f"{page_number:02d}" if page_number else "--"
                self.pdf.setFillColorRGB(*VIOLET)
                self.pdf.setFont(SANS_SEMIBOLD, 28)
                self.pdf.drawString(x, top - 28, folio)
                text_x = x + 55
                text_width = available - 55
                self.pdf.setFillColorRGB(*INK)
                self.pdf.setFont(SANS_MEDIUM, CAPTION_SIZE)
                self.pdf.drawString(text_x, top - 12, _plain(label.upper()))
                title_lines = self.lines(title, SERIF_DISPLAY, 10.8, text_width)
                if len(title_lines) > 2:
                    raise ValidationError(f"Contents title is too long for Monument: {title}")
                self.pdf.setFont(SERIF_DISPLAY, 10.8)
                baseline = top - 32
                for line in title_lines:
                    self.pdf.drawString(text_x, baseline, line)
                    baseline -= BODY_LEADING
                if author:
                    self.pdf.setFillColorRGB(*SLATE)
                    self.pdf.setFont(SANS_MEDIUM, CAPTION_SIZE)
                    self.pdf.drawString(
                        text_x,
                        top - 57,
                        self.fit_text(_plain(author.upper()), SANS_MEDIUM, CAPTION_SIZE, text_width),
                    )
                if row_index < len(chunk) - 1:
                    self.pdf.setStrokeColorRGB(*COOL_GRAY)
                    self.pdf.setLineWidth(.7)
                    self.pdf.line(x, top - row_height, self.width - self.right, top - row_height)

    def body(self):
        if self.edition.articles:
            if self.edition.editorial:
                self.continuation_columns = 2
                self.reading_size = BODY_SIZE
                self.reading_leading = 12.0
                self.paragraph_after = 4.4
                self.new_page(_ui(self.edition, "editorial"), opener=True)
                start_page = self.page
                self.toc["editorial"] = self.page
                self._label(
                    self.edition.editorial.label,
                    right=_ui(self.edition, "original_argument"),
                )
                title_x, title_width = self.grid_box(0, 5)
                title_bottom = self._fitted_title_box(
                    self.edition.editorial.title,
                    title_x,
                    self.y + 5,
                    title_width,
                    72,
                    maximum=26,
                    minimum=20,
                    maximum_lines=3,
                    leading_ratio=1.0,
                )
                self._set_custom_frame(title_x, title_width, top=title_bottom - 3)
                self._credit(self.edition.editorial.byline)

                blocks = list(
                    _markdown_blocks(
                        self.edition.editorial.path.read_text(encoding="utf-8")
                    )
                )
                first_body = next(
                    (index for index, (kind, _) in enumerate(blocks) if kind == "body"),
                    None,
                )
                if first_body is None:
                    raise ValidationError("Opening editorial requires prose for the Monument opener")
                sentence, remainder = _opening_sentence(blocks[first_body][1])
                if remainder:
                    blocks[first_body] = ("body", remainder)
                else:
                    blocks.pop(first_body)
                hero_x, hero_width = self.grid_box(1, 5)
                hero_top = self.y - 10
                hero_bottom = self._fitted_title_box(
                    sentence,
                    hero_x,
                    hero_top,
                    hero_width,
                    112,
                    maximum=28,
                    minimum=18,
                    maximum_lines=4,
                    color=VIOLET,
                    leading_ratio=1.04,
                )
                self._tracked_label(
                    _ui(self.edition, "opening_sentence"),
                    hero_x,
                    hero_bottom - 2,
                    hero_width,
                )
                self._set_custom_frame(
                    self.left,
                    self.live_width,
                    top=hero_bottom - 25,
                )
                self._render_blocks(blocks)
                self.reading_leading = BODY_LEADING
                self.paragraph_after = 5.4
                self.editorial_pages = self.page - start_page + 1
                if self.editorial_pages > MAX_EDITORIAL_PAGES:
                    raise ValidationError(
                        f"Editorial spans {self.editorial_pages} reader pages; the hard cap is "
                        f"{MAX_EDITORIAL_PAGES}. Condense it before building."
                    )
            article_total = len(self.edition.articles)
            for article_index, article in enumerate(self.edition.articles, 1):
                self.continuation_columns = 2
                self.reading_size = BODY_SIZE
                self.reading_leading = BODY_LEADING
                self.paragraph_after = 5.4
                self.new_page(article.title, opener=True)
                start_page = self.page
                self.toc[article.id] = self.page
                mode = _content_mode_label(self.edition, article.content_mode)
                self._label(
                    f"{_ui(self.edition, 'feature')} {article_index:02d}",
                    right=mode,
                )
                outer_column = 0 if self.page % 2 == 0 else 5
                title_start = 1 if self.page % 2 == 0 else 0
                title_x, title_width = self.grid_box(title_start, 5)
                medallion_x, medallion_width = self.grid_box(outer_column, 1)
                medallion_y = self.y - 28
                self.pdf.setFillColorRGB(*VIOLET)
                self.pdf.circle(
                    medallion_x + medallion_width / 2,
                    medallion_y,
                    21,
                    fill=1,
                    stroke=0,
                )
                self.pdf.setFillColorRGB(*WHITE)
                self.pdf.setFont(SANS_SEMIBOLD, 11)
                self.pdf.drawCentredString(
                    medallion_x + medallion_width / 2,
                    medallion_y - 4,
                    f"{article_index:02d}",
                )
                self._monument_title(
                    article.title,
                    article.display_emphasis,
                    title_x,
                    self.y + 5,
                    title_width,
                    210,
                )
                credit_x, credit_width = self.grid_box(1, 4)
                self._set_custom_frame(credit_x, credit_width, top=self.y - 205)
                self._credit(
                    article.author,
                    f"{article_index} / {article_total}",
                    author_note=article.author_note,
                )
                self._set_custom_frame(
                    credit_x,
                    credit_width,
                    top=min(self.y, 238),
                )
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
        self.continuation_columns = 2
        self.new_page(section.title, opener=True)
        self.toc[f"section-{index}"] = self.page
        label = _section_label(self.edition, section.kind)
        self._label(label, right=_ui(self.edition, "issue") + " " + str(self.edition.issue_number))
        title_x, title_width = self.grid_box(1, 5)
        title_bottom = self._monument_title(
            section.title,
            "",
            title_x,
            self.y + 5,
            title_width,
            190,
        )
        self._set_custom_frame(
            self.left,
            self.live_width,
            top=title_bottom - 25,
        )
        self.markdown(section.path, lead=True)

    def _closing_plate(self, index: int, total: int) -> None:
        self.new_page(blank_header=True)
        self.pdf.setFillColorRGB(*WHITE)
        self.pdf.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        self._tracked_label(
            f"{self.edition.publication_name} / {_ui(self.edition, 'issue')} {self.edition.issue_number}",
            self.left,
            self.height - 29,
            self.live_width,
        )
        words = _plain(self.edition.title).split()
        chunk_count = min(total, len(words)) or 1
        chunks: list[str] = []
        cursor = 0
        for chunk_index in range(chunk_count):
            remaining_words = len(words) - cursor
            remaining_chunks = chunk_count - chunk_index
            take = (remaining_words + remaining_chunks - 1) // remaining_chunks
            chunks.append(" ".join(words[cursor : cursor + take]))
            cursor += take
        phrase = chunks[min(index, len(chunks) - 1)] if chunks else self.edition.title
        title_x, title_width = self.grid_box(1, 4)
        self._fitted_title_box(
            phrase,
            title_x,
            390,
            title_width,
            170,
            maximum=42,
            minimum=24,
            maximum_lines=4,
            color=VIOLET,
            leading_ratio=1.0,
        )
        medallion_x, medallion_width = self.grid_box(0, 1)
        self.pdf.setFillColorRGB(*VIOLET)
        self.pdf.circle(medallion_x + medallion_width / 2, 364, 18, fill=1, stroke=0)
        self.pdf.setFillColorRGB(*WHITE)
        self.pdf.setFont(SANS_SEMIBOLD, 8)
        self.pdf.drawCentredString(
            medallion_x + medallion_width / 2,
            361,
            f"{index + 1}/{total}",
        )
        self._tracked_label(
            _ui(self.edition, "closing_plate"),
            title_x,
            176,
            title_width,
            color=VIOLET,
        )
        self._folio()

    def back_cover(self):
        self.continuation_columns = 1
        configured = self.edition.raw.get("format", {}).get("target_pages")
        minimum_total = self.page + 1
        target = int(configured) if configured else ((minimum_total + 3) // 4) * 4
        target = max(target, minimum_total)
        target = ((target + 3) // 4) * 4
        closing_pages = target - 1 - self.page
        for index in range(closing_pages):
            self._closing_plate(index, closing_pages)
        self.new_page(blank_header=True)
        self.pdf.setFillColorRGB(*WHITE)
        self.pdf.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        self._tracked_label(
            f"{self.edition.publication_name} / {_ui(self.edition, 'issue')} {self.edition.issue_number}",
            self.left,
            self.height - 29,
            self.live_width,
        )
        text = str(self.edition.cover.get("back_text", _ui(self.edition, "back_text_default")))
        quote_x, quote_width = self.grid_box(1, 4)
        self._fitted_title_box(
            text,
            quote_x,
            415,
            quote_width,
            210,
            maximum=20,
            minimum=14,
            maximum_lines=8,
            leading_ratio=1.24,
        )
        medallion_x, medallion_width = self.grid_box(0, 1)
        self.pdf.setFillColorRGB(*VIOLET)
        self.pdf.circle(medallion_x + medallion_width / 2, 389, 18, fill=1, stroke=0)
        self.pdf.setFillColorRGB(*WHITE)
        self.pdf.setFont(SANS_SEMIBOLD, 9)
        self.pdf.drawCentredString(
            medallion_x + medallion_width / 2,
            386,
            _plain(_ui(self.edition, "end").upper()),
        )
        self._tracked_label(
            _ui(self.edition, "issue_statement"),
            quote_x,
            176,
            quote_width,
            color=VIOLET,
        )
        self.pdf.setFillColorRGB(*INK)
        self.pdf.setFont(SANS_MEDIUM, CAPTION_SIZE)
        self.pdf.drawString(self.left, 17, _plain(_edition_label(self.edition)).upper())
        self.pdf.drawRightString(
            self.width - self.right,
            17,
            self.fit_text(_plain(self.edition.title.upper()), SANS_MEDIUM, CAPTION_SIZE, self.live_width * .55),
        )


def _render_pass(
    target,
    edition: Edition,
    toc: dict[str, int] | None = None,
    *,
    design: str,
) -> RenderLayout:
    A5, metrics, canvas = _reportlab()
    pdf = canvas.Canvas(
        target,
        pagesize=A5,
        pageCompression=1,
        invariant=1,
        initialFontName=SANS,
        initialFontSize=10,
        initialLeading=BODY_LEADING,
    )
    pdf.setTitle(_plain(edition.title))
    pdf.setAuthor(_plain(edition.publication_name))
    pdf.setCreator("magazine-compiler")
    typesetter = _Typesetter(pdf, edition, A5, metrics, design=design)
    typesetter.cover()
    typesetter.contents(toc or {})
    typesetter.body()
    typesetter.back_cover()
    pdf.save()
    return RenderLayout(
        dict(typesetter.toc),
        dict(typesetter.article_pages),
        typesetter.editorial_pages,
        DESIGN_LABEL,
        typesetter.cover_art_size_points,
    )


def render_a5(
    edition: Edition,
    output: Path,
    *,
    design: str = DESIGN_MONUMENT,
) -> RenderLayout:
    """Render an edition twice so the deterministic contents page has folios."""
    if design != DESIGN_MONUMENT:
        raise ValidationError(
            f"Unsupported render design {design!r}; expected {DESIGN_MONUMENT!r}"
        )
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
    draft = _render_pass(io.BytesIO(), edition, design=design)
    final = _render_pass(str(output), edition, draft.toc, design=design)
    if (
        draft.article_pages != final.article_pages
        or draft.editorial_pages != final.editorial_pages
    ):
        raise ValidationError("Content pagination changed between deterministic render passes")
    return final
