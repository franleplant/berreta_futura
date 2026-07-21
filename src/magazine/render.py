from __future__ import annotations

import io
import math
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
MIN_FIGURE_PPI = 300.0
FIGURE_BAND_MAX_IMAGE_HEIGHT = 150.0
FIGURE_COLUMN_MAX_IMAGE_HEIGHT = 220.0
FIGURE_TEXT_LEADING = 8.6
FIGURE_GAP = BASE * 5
INNER_MARGIN = 44.0
OUTER_MARGIN = 15 * 72 / 25.4
TEXT_TOP_INSET = 52.0
TERMINAL_BALANCE_FRAMES = 4
TERMINAL_BALANCE_THRESHOLD = .35
RUNNING_HEADER_BASELINE_INSET = 20.0
RUNNING_HEADER_SECONDARY_OFFSET = 11.0
HEADING_SPACE_BEFORE = {
    "h1": 16.0,
    "h2": 13.0,
    "h3": 10.0,
}

# Monument uses the sheet itself as the paper color. Violet is reserved for
# hierarchy and typographic furniture so interiors remain economical to print.
INK = (.055, .075, .085)
VIOLET = (.25, .10, .43)
SIGNAL_ORANGE = (1.0, .27, .04)
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
        "back_text_default": "An independent anthology of writing worth keeping.",
        "opening_sentence": "Opening sentence / Original editorial",
        "issue_statement": "Issue statement / The editors",
        "continued": "Continued",
        "end": "End",
        "closing_plate": "Closing plate",
        "figure": "Figure",
    },
    "es": {
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
        "back_text_default": "Una antología independiente de textos que vale la pena conservar.",
        "opening_sentence": "Frase inicial / Editorial original",
        "issue_statement": "Declaración del número / La redacción",
        "continued": "Continuación",
        "end": "Fin",
        "closing_plate": "Lámina final",
        "figure": "Figura",
    },
}


@dataclass(frozen=True)
class RenderLayout:
    toc: dict[str, int]
    article_pages: dict[str, int]
    editorial_pages: int | None
    design: str
    cover_art_size_points: tuple[float, float] | None
    article_frame_usage: dict[str, tuple["FrameUsage", ...]]
    article_terminal_balance: dict[str, float]
    figure_placements: tuple["FigurePlacement", ...] = ()


@dataclass(frozen=True)
class FigurePlacement:
    figure_id: str
    article_id: str
    page: int
    path: Path
    pixel_dimensions: tuple[int, int]
    box_points: tuple[float, float, float, float]
    effective_ppi: float
    caption: str
    credit: str
    rights_status: str


@dataclass(frozen=True)
class FrameUsage:
    relative_page: int
    frame_index: int
    used: float
    capacity: float


@dataclass(frozen=True)
class ArticleBalancePlan:
    page_count: int
    frame_height: float


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
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2192": "->",
        "\u2026": "...",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("cp1252", errors="replace").decode("cp1252")


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
    def __init__(
        self,
        pdf,
        edition: Edition,
        pagesize,
        metrics,
        *,
        design: str,
        balance_plans: dict[str, ArticleBalancePlan] | None = None,
        enforce_page_caps: bool = True,
    ):
        self.pdf, self.edition, self.width, self.height, self.metrics = pdf, edition, *pagesize, metrics
        self.design = design
        self.balance_plans = balance_plans or {}
        self.enforce_page_caps = enforce_page_caps
        self.inner, self.outer, self.top, self.bottom = INNER_MARGIN, OUTER_MARGIN, TEXT_TOP_INSET, 45.0
        self.left, self.right = self.inner, self.outer
        self.page = 0
        self.section = ""
        self.toc: dict[str, int] = {}
        self.article_pages: dict[str, int] = {}
        self.article_frame_usage: dict[str, tuple[FrameUsage, ...]] = {}
        self.figure_placements: list[FigurePlacement] = []
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
        self.frame_role = "standard"
        self.frame_recorded = False
        self.y = self.frame_top
        self.active_article_id: str | None = None
        self.active_article_start_page: int | None = None
        self.active_article_frames: list[FrameUsage] = []

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
        role: str = "standard",
    ) -> None:
        self.frame_count = columns
        self.frame_index = 0
        self.frame_role = role
        default_top = self.height - self.top
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
        self.frame_recorded = False

    def _set_custom_frame(self, x: float, width: float, *, top: float, bottom: float | None = None) -> None:
        self.frame_count = 1
        self.frame_index = 0
        self.frame_left = x
        self.frame_width = width
        self.frame_top = top
        self.frame_bottom = self.bottom if bottom is None else bottom
        self.y = top
        self.frame_recorded = False

    def _begin_article(self, article_id: str) -> None:
        self.active_article_id = article_id
        self.active_article_start_page = self.page + 1
        self.active_article_frames = []

    def _record_active_frame(self) -> None:
        if (
            not self.active_article_id
            or self.active_article_start_page is None
            or self.frame_role != "continuation"
            or self.frame_recorded
        ):
            return
        self.active_article_frames.append(
            FrameUsage(
                self.page - self.active_article_start_page + 1,
                self.frame_index,
                max(0.0, self.frame_top - self.y),
                self.frame_top - self.frame_bottom,
            )
        )
        self.frame_recorded = True

    def _finish_article(self) -> tuple[FrameUsage, ...]:
        self._record_active_frame()
        if (
            self.active_article_id
            and self.active_article_start_page is not None
            and self.frame_role == "continuation"
            and self.frame_count == 2
            and self.frame_index == 0
        ):
            self.active_article_frames.append(
                FrameUsage(
                    self.page - self.active_article_start_page + 1,
                    1,
                    0.0,
                    self.frame_top - self.frame_bottom,
                )
            )
        frames = tuple(self.active_article_frames)
        if self.active_article_id:
            self.article_frame_usage[self.active_article_id] = frames
        self.active_article_id = None
        self.active_article_start_page = None
        self.active_article_frames = []
        return frames

    def _advance_frame(self) -> None:
        self._record_active_frame()
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
        y = self.height - RUNNING_HEADER_BASELINE_INSET
        publication = _plain(
            f"{self.edition.publication_name.upper()} / {_ui(self.edition, 'issue').upper()} "
            f"{self.edition.issue_number}"
        )
        section = _plain(self.section.upper())
        continued = _plain(_ui(self.edition, "continued").upper())
        right_width = self.live_width * .49
        if self.metrics.stringWidth(section, SANS_MEDIUM, CAPTION_SIZE) > right_width:
            raise ValidationError(
                f"Curated running title does not fit the Monument header: {self.section}"
            )
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
            section,
        )
        self._tracked_label(
            continued,
            self.width - self.right - right_width,
            y - RUNNING_HEADER_SECONDARY_OFFSET,
            right_width,
            color=VIOLET,
            tracking=.25,
            align="right",
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
            self._record_active_frame()
            self.pdf.showPage()
        self.page += 1
        self._set_page_margins()
        self.section = section or self.section
        selected_columns = 1 if opener else (columns or self.continuation_columns)
        if opener:
            role = "opener"
        elif self.active_article_id and selected_columns == 2:
            role = "continuation"
        elif self.active_article_id:
            role = "fullwidth"
        else:
            role = "standard"
        balance_bottom = None
        if (
            role == "continuation"
            and self.active_article_id
            and self.active_article_start_page is not None
        ):
            plan = self.balance_plans.get(self.active_article_id)
            relative_page = self.page - self.active_article_start_page + 1
            if plan and relative_page >= plan.page_count - 1:
                balance_bottom = self.height - self.top - plan.frame_height
        self._configure_frames(
            selected_columns,
            bottom=balance_bottom,
            role=role,
        )
        if self.page > 2 and not blank_header:
            self._folio()
            if not opener:
                self._running_header()

    def lines(self, text: str, font: str, size: float, width: float) -> list[str]:
        words: list[str] = []
        for word in _plain(re.sub(r"[*`]", "", text)).split():
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

    @staticmethod
    def _figure_value(figure, name: str, default=""):
        if isinstance(figure, dict):
            return figure.get(name, default)
        return getattr(figure, name, default)

    def _figure_dimensions(self, figure) -> tuple[int, int]:
        from reportlab.lib.utils import ImageReader

        path = Path(self._figure_value(figure, "path"))
        if not path.is_file():
            raise ValidationError(f"Curated figure file does not exist: {path}")
        try:
            width, height = ImageReader(str(path)).getSize()
        except Exception as exc:
            raise ValidationError(f"Cannot decode curated figure {path}: {exc}") from exc
        if width <= 0 or height <= 0:
            raise ValidationError(f"Curated figure has invalid dimensions: {path}")
        return int(width), int(height)

    def _figure_geometry(
        self,
        figure,
        width: float,
        max_image_height: float,
    ) -> tuple[float, float, list[str], list[str], float]:
        pixel_width, pixel_height = self._figure_dimensions(figure)
        scale = min(width / pixel_width, max_image_height / pixel_height)
        image_width = pixel_width * scale
        image_height = pixel_height * scale
        caption = str(self._figure_value(figure, "caption")).strip()
        credit = str(self._figure_value(figure, "credit")).strip()
        if not caption:
            raise ValidationError(
                f"Curated figure {self._figure_value(figure, 'id', '<unknown>')} requires a caption"
            )
        if not credit:
            raise ValidationError(
                f"Curated figure {self._figure_value(figure, 'id', '<unknown>')} requires a credit"
            )
        caption_lines = self.lines(caption, SERIF, CAPTION_SIZE, width)
        credit_lines = self.lines(credit, SANS_MEDIUM, CAPTION_SIZE, width)
        text_height = (len(caption_lines) + len(credit_lines)) * FIGURE_TEXT_LEADING
        total_height = CAPTION_SIZE + BASE * 2 + image_height + BASE * 2 + text_height + FIGURE_GAP
        return image_width, image_height, caption_lines, credit_lines, total_height

    def _draw_contained_image(
        self,
        path: Path,
        x: float,
        top: float,
        box_width: float,
        image_width: float,
        image_height: float,
    ) -> tuple[float, float]:
        from reportlab.lib.utils import ImageReader

        draw_x = x + (box_width - image_width) / 2
        draw_y = top - image_height
        self.pdf.drawImage(
            ImageReader(str(path)),
            draw_x,
            draw_y,
            image_width,
            image_height,
            preserveAspectRatio=True,
            mask="auto",
        )
        self.pdf.setStrokeColorRGB(*INK)
        self.pdf.setLineWidth(.55)
        self.pdf.rect(draw_x, draw_y, image_width, image_height, fill=0, stroke=1)
        return draw_x, draw_y

    def _draw_figure(
        self,
        figure,
        *,
        article_id: str,
        figure_index: int,
        x: float,
        top: float,
        width: float,
        max_image_height: float,
    ) -> float:
        path = Path(self._figure_value(figure, "path"))
        pixel_dimensions = self._figure_dimensions(figure)
        image_width, image_height, caption_lines, credit_lines, total_height = self._figure_geometry(
            figure, width, max_image_height
        )
        label = f"{_ui(self.edition, 'figure').upper()} {figure_index:02d}"
        self._tracked_label(label, x, top - CAPTION_SIZE, width, color=VIOLET, tracking=.25)
        image_top = top - CAPTION_SIZE - BASE * 2
        image_x, image_y = self._draw_contained_image(
            path, x, image_top, width, image_width, image_height
        )
        baseline = image_top - image_height - BASE * 2 - CAPTION_SIZE
        self.pdf.setFillColorRGB(*INK)
        self.pdf.setFont(SERIF, CAPTION_SIZE)
        for line in caption_lines:
            self.pdf.drawString(x, baseline, line)
            baseline -= FIGURE_TEXT_LEADING
        self.pdf.setFillColorRGB(*SLATE)
        self.pdf.setFont(SANS_MEDIUM, CAPTION_SIZE)
        for line in credit_lines:
            self.pdf.drawString(x, baseline, line)
            baseline -= FIGURE_TEXT_LEADING

        ppi = min(
            pixel_dimensions[0] / (image_width / 72),
            pixel_dimensions[1] / (image_height / 72),
        )
        figure_id = str(self._figure_value(figure, "id", f"figure-{figure_index}"))
        if ppi < MIN_FIGURE_PPI:
            raise ValidationError(
                f"Curated figure {figure_id} resolves to {ppi:.1f} ppi at its Monument "
                f"placement; the minimum is {MIN_FIGURE_PPI:.0f} ppi"
            )
        self.figure_placements.append(
            FigurePlacement(
                figure_id=figure_id,
                article_id=article_id,
                page=self.page,
                path=path,
                pixel_dimensions=pixel_dimensions,
                box_points=(
                    round(image_x, 3),
                    round(image_y, 3),
                    round(image_width, 3),
                    round(image_height, 3),
                ),
                effective_ppi=round(ppi, 1),
                caption=str(self._figure_value(figure, "caption")).strip(),
                credit=str(self._figure_value(figure, "credit")).strip(),
                rights_status=str(self._figure_value(figure, "rights_status", "unknown")),
            )
        )
        return top - total_height

    def _column_figure_height(self, figure) -> float:
        return self._figure_geometry(
            figure,
            self.column_width,
            FIGURE_COLUMN_MAX_IMAGE_HEIGHT,
        )[-1]

    def _column_figure(self, figure, *, article_id: str, figure_index: int) -> None:
        required = self._column_figure_height(figure)
        if self.y - required < self.frame_bottom:
            self._advance_frame()
            required = self._column_figure_height(figure)
        if self.y - required < self.frame_bottom:
            raise ValidationError(
                f"Curated figure {self._figure_value(figure, 'id', '<unknown>')} is too tall "
                "for a Monument column plate"
            )
        self.y = self._draw_figure(
            figure,
            article_id=article_id,
            figure_index=figure_index,
            x=self.frame_left,
            top=self.y,
            width=self.column_width,
            max_image_height=FIGURE_COLUMN_MAX_IMAGE_HEIGHT,
        )

    def _evidence_band(
        self,
        kind: str,
        heading: str,
        figure,
        *,
        article_id: str,
        figure_index: int,
    ) -> None:
        heading_style = {
            "h2": (SERIF_DISPLAY, 17.5, 20.5, 10),
            "h3": (SANS_SEMIBOLD, 8.7, 12, 7),
        }[kind]
        heading_font, heading_size, heading_leading, heading_after = heading_style
        heading_text = heading.upper() if kind == "h3" else heading
        heading_height = (
            len(self.lines(heading_text, heading_font, heading_size, self.live_width))
            * heading_leading
            + heading_after
        )
        figure_height = self._figure_geometry(
            figure,
            self.live_width,
            FIGURE_BAND_MAX_IMAGE_HEIGHT,
        )[-1]
        bridge_top = min(self.y, self.height - self.top)
        can_bridge_current_page = (
            (self.frame_count == 1 or self.frame_index == 0)
            and bridge_top - heading_height - figure_height - 6 * self.reading_leading
            >= self.bottom
        )
        if can_bridge_current_page:
            self._record_active_frame()
        else:
            self.new_page(columns=2)
            bridge_top = self.height - self.top
        self._set_custom_frame(
            self.left,
            self.live_width,
            top=bridge_top,
            bottom=self.bottom,
        )
        self.frame_role = "continuation"
        self.block(kind, heading)
        band_bottom = self._draw_figure(
            figure,
            article_id=article_id,
            figure_index=figure_index,
            x=self.left,
            top=self.y,
            width=self.live_width,
            max_image_height=FIGURE_BAND_MAX_IMAGE_HEIGHT,
        )
        if band_bottom - 6 * self.reading_leading < self.bottom:
            raise ValidationError(
                f"Curated figure {self._figure_value(figure, 'id', '<unknown>')} leaves too "
                "little reading space below its Monument evidence band"
            )
        if str(self._figure_value(figure, "layout")) == "evidence_band_prose":
            prose_x, prose_width = self.grid_box(1, 4)
            self._set_custom_frame(
                prose_x,
                prose_width,
                top=band_bottom,
                bottom=self.bottom,
            )
            self.frame_role = "continuation"
        else:
            self._configure_frames(2, top=band_bottom, role="continuation")

    def _opener_evidence_band(
        self,
        figure,
        *,
        article_id: str,
        figure_index: int,
    ) -> None:
        self.new_page(columns=2)
        self._set_custom_frame(
            self.left,
            self.live_width,
            top=self.height - self.top,
            bottom=self.bottom,
        )
        self.frame_role = "continuation"
        band_bottom = self._draw_figure(
            figure,
            article_id=article_id,
            figure_index=figure_index,
            x=self.left,
            top=self.y,
            width=self.live_width,
            max_image_height=FIGURE_BAND_MAX_IMAGE_HEIGHT,
        )
        if band_bottom - 6 * self.reading_leading < self.bottom:
            raise ValidationError(
                f"Curated figure {self._figure_value(figure, 'id', '<unknown>')} leaves too "
                "little reading space below its Monument opener evidence band"
            )
        if str(self._figure_value(figure, "layout")) == "evidence_band_prose":
            prose_x, prose_width = self.grid_box(1, 4)
            self._set_custom_frame(
                prose_x,
                prose_width,
                top=band_bottom,
                bottom=self.bottom,
            )
            self.frame_role = "continuation"
        else:
            self._configure_frames(2, top=band_bottom, role="continuation")

    def block(self, kind: str, text: str):
        styles = {
            "h1": (SERIF_DISPLAY, 22, 25, HEADING_SPACE_BEFORE["h1"], 13),
            "h2": (SERIF_DISPLAY, 17.5, 20.5, HEADING_SPACE_BEFORE["h2"], 10),
            "h3": (SANS_SEMIBOLD, 8.7, 12, HEADING_SPACE_BEFORE["h3"], 7),
            "lead": (SERIF, 11.6, 15.2, 0, 11),
            "body": (SERIF, self.reading_size, self.reading_leading, 0, self.paragraph_after),
            "bullet": (SERIF, 9.45, self.reading_leading, 0, 5),
            "quote": (SERIF_ITALIC, 10.1, 13.7, 0, 9),
        }
        font, size, leading, before, after = styles[kind]
        if kind == "h3":
            text = text.upper()
        indent = 14 if kind in {"bullet", "quote"} else 0
        lines = self.lines(text, font, size, self.column_width - indent)
        if kind in {"h1", "h2", "h3"}:
            self.y = min(self.y, self.height - self.top)
            if math.isclose(self.y, self.frame_top):
                before = 0
            needed = before + len(lines) * leading + after
            if self.y - needed - 25 < self.frame_bottom:
                self._advance_frame()
                before = 0
                lines = self.lines(text, font, size, self.column_width - indent)
                needed = len(lines) * leading + after
            if self.y - needed < self.frame_bottom:
                raise ValidationError(
                    f"A {kind} block is too tall for the Monument text frame"
                )
            self.y -= before
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

    def markdown(self, path: Path, *, lead: bool = False, figures=(), article_id: str = ""):
        self._render_blocks(
            list(_markdown_blocks(path.read_text(encoding="utf-8"))),
            lead=lead,
            figures=figures,
            article_id=article_id,
        )

    def _validated_figures(
        self,
        blocks: list[tuple[str, str]],
        figures,
        article_id: str,
    ) -> tuple[list, dict[str, object]]:
        rows = list(figures or ())
        if len(rows) > 3:
            raise ValidationError(
                f"Article {article_id} has {len(rows)} curated figures; the maximum is 3"
            )
        identifiers = [str(self._figure_value(row, "id")) for row in rows]
        if len(set(identifiers)) != len(identifiers):
            raise ValidationError(f"Article {article_id} has duplicate curated figure ids")
        anchors = [str(self._figure_value(row, "anchor")).strip() for row in rows]
        if len(set(anchor.casefold() for anchor in anchors)) != len(anchors):
            raise ValidationError(f"Article {article_id} has multiple figures at one semantic anchor")
        headings: dict[str, int] = {}
        for kind, value in blocks:
            if kind in {"h2", "h3"}:
                key = value.strip().casefold()
                headings[key] = headings.get(key, 0) + 1
        by_anchor: dict[str, object] = {}
        opener: list = []
        for row, anchor in zip(rows, anchors, strict=True):
            layout = str(self._figure_value(row, "layout", "column_plate"))
            if layout not in {"evidence_band", "evidence_band_prose", "column_plate"}:
                raise ValidationError(
                    f"Curated figure {self._figure_value(row, 'id', '<unknown>')} has invalid "
                    f"Monument layout {layout!r}"
                )
            if anchor == "__opener__":
                opener.append(row)
                continue
            matches = headings.get(anchor.casefold(), 0)
            if matches != 1:
                raise ValidationError(
                    f"Curated figure {self._figure_value(row, 'id', '<unknown>')} semantic "
                    f"anchor {anchor!r} matched {matches} article headings; expected exactly 1"
                )
            by_anchor[anchor.casefold()] = row
        return opener, by_anchor

    def _keep_heading_with_column_figure(self, kind: str, value: str, figure) -> None:
        style = {
            "h2": (SERIF_DISPLAY, 17.5, 20.5, HEADING_SPACE_BEFORE["h2"], 10),
            "h3": (SANS_SEMIBOLD, 8.7, 12, HEADING_SPACE_BEFORE["h3"], 7),
        }[kind]
        font, size, leading, before, after = style
        lines = self.lines(value.upper() if kind == "h3" else value, font, size, self.column_width)
        if math.isclose(self.y, self.frame_top):
            before = 0
        required = before + len(lines) * leading + after + self._column_figure_height(figure)
        if self.y - required < self.frame_bottom:
            self._advance_frame()

    def _render_blocks(
        self,
        blocks: list[tuple[str, str]],
        *,
        lead: bool = False,
        figures=(),
        article_id: str = "",
    ) -> None:
        opener_figures, anchored = self._validated_figures(blocks, figures, article_id)
        figure_number = 0
        for figure in opener_figures:
            figure_number += 1
            layout = str(self._figure_value(figure, "layout", "column_plate"))
            if layout in {"evidence_band", "evidence_band_prose"}:
                self._opener_evidence_band(
                    figure,
                    article_id=article_id,
                    figure_index=figure_number,
                )
            else:
                self._column_figure(
                    figure,
                    article_id=article_id,
                    figure_index=figure_number,
                )

        for index, (kind, value) in enumerate(blocks):
            figure = anchored.get(value.strip().casefold()) if kind in {"h2", "h3"} else None
            if figure is not None and str(self._figure_value(figure, "layout")) in {
                "evidence_band", "evidence_band_prose"
            }:
                figure_number += 1
                self._evidence_band(
                    kind,
                    value,
                    figure,
                    article_id=article_id,
                    figure_index=figure_number,
                )
                continue
            if figure is not None:
                self._keep_heading_with_column_figure(kind, value, figure)
            if kind == "code":
                self.code_block(value)
            else:
                if lead and index == 0 and kind == "body":
                    kind = "lead"
                self.block(kind, value)
            if figure is not None:
                figure_number += 1
                self._column_figure(
                    figure,
                    article_id=article_id,
                    figure_index=figure_number,
                )

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
        self.pdf.saveState()
        try:
            self.pdf.setFillColorRGB(*color)
            label = self.pdf.beginText()
            label.setTextOrigin(cursor, y)
            label.setFont(SANS_MEDIUM, CAPTION_SIZE)
            label.setCharSpace(tracking)
            label.textLine(value)
            self.pdf.drawText(label)
        finally:
            self.pdf.restoreState()

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
                self.column_width * .76,
            ),
        )
        if note:
            self.pdf.setFillColorRGB(*VIOLET)
            self.pdf.setFont(SANS_MEDIUM, CAPTION_SIZE)
            self.pdf.drawRightString(
                self.frame_left + self.column_width,
                self.y,
                self.fit_text(_plain(note.upper()), SANS_MEDIUM, CAPTION_SIZE, self.column_width * .2),
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

    def _draw_aligned_string(
        self,
        text: str,
        x: float,
        y: float,
        width: float,
        *,
        align: str,
    ) -> None:
        if align == "right":
            self.pdf.drawRightString(x + width, y, text)
        elif align == "center":
            self.pdf.drawCentredString(x + width / 2, y, text)
        else:
            self.pdf.drawString(x, y, text)

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
        align: str = "left",
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
            self._draw_aligned_string(line, x, baseline, width, align=align)
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
        prefix = title[: match.start()].strip()
        suffix = title[match.end() :].strip()
        # Monument openers treat the emphasized word as a standalone display
        # object. Leading punctuation therefore becomes an orphaned glyph on
        # the subtitle line; omit that separator in the composed title while
        # keeping the complete title intact in metadata and contents.
        suffix = re.sub(r"^[,;:]\s*", "", suffix)
        return prefix, match.group(0), suffix

    def _monument_title(
        self,
        title: str,
        emphasis: str,
        x: float,
        top: float,
        width: float,
        height: float,
        *,
        variant: str = "edge_medallion",
    ) -> float:
        prefix, focus, suffix = self._monument_parts(_plain(title), _plain(emphasis))
        bottom = top - height
        cursor = top
        if variant == "split_axis":
            prefix_align = focus_align = suffix_align = "right"
            axis_x = x - GRID_GUTTER / 2 if self.page % 2 == 0 else x + width + GRID_GUTTER / 2
            self.pdf.setStrokeColorRGB(*VIOLET)
            self.pdf.setLineWidth(.8)
            self.pdf.line(axis_x, bottom + 8, axis_x, top - 5)
        elif variant == "stepped_title":
            prefix_align, focus_align, suffix_align = "left", "center", "right"
            self.pdf.setStrokeColorRGB(*VIOLET)
            self.pdf.setLineWidth(1.2)
            rule_width = min(width, self.grid_column_width * 1.4)
            rule_x = x + width - rule_width if self.page % 2 else x
            self.pdf.line(rule_x, top - 2, rule_x + rule_width, top - 2)
            cursor -= 9
        else:
            prefix_align = focus_align = suffix_align = "left"
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
                self._draw_aligned_string(
                    line,
                    x,
                    cursor - prefix_size,
                    width,
                    align=prefix_align,
                )
                cursor -= prefix_leading
            cursor -= 5
        focus_size = 50.0 if variant == "stepped_title" else 54.0
        while focus_size > 28 and self.metrics.stringWidth(focus.upper(), SANS_SEMIBOLD, focus_size) > width:
            focus_size -= .5
        self.pdf.setFillColorRGB(*VIOLET)
        self.pdf.setFont(SANS_SEMIBOLD, focus_size)
        self._draw_aligned_string(
            focus.upper(),
            x,
            cursor - focus_size,
            width,
            align=focus_align,
        )
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
                align=suffix_align,
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
        art_x, art_y = (self.width - art_width) / 2, 177.0
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
        self.pdf.drawString(
            self.left,
            17,
            f"{_plain(_ui(self.edition, 'issue').upper())} {self.edition.issue_number}"
            f" / {self.edition.publication_date}",
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
        chunks = [entries[index : index + 8] for index in range(0, len(entries), 8)] or [[]]
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
            row_height = 393.0 / max(6, len(chunk))
            for row_index, (label, title, author, page_number) in enumerate(chunk):
                indent = 0 if row_index % 2 == 0 else self.grid_column_width + GRID_GUTTER
                x = self.left + indent
                available = self.live_width - indent
                top = row_top - row_index * row_height
                folio = f"{page_number:02d}" if page_number else "--"
                self.pdf.setFillColorRGB(*VIOLET)
                self.pdf.setFont(SANS_SEMIBOLD, 23)
                self.pdf.drawString(x, top - 23, folio)
                text_x = x + 47
                text_width = available - 47
                self.pdf.setFillColorRGB(*INK)
                self.pdf.setFont(SANS_MEDIUM, CAPTION_SIZE)
                self.pdf.drawString(text_x, top - 8, _plain(label.upper()))
                title_lines = self.lines(title, SERIF_DISPLAY, 9.8, text_width)
                if len(title_lines) > 2:
                    raise ValidationError(f"Contents title is too long for Monument: {title}")
                self.pdf.setFont(SERIF_DISPLAY, 9.8)
                baseline = top - 23
                for line in title_lines:
                    self.pdf.drawString(text_x, baseline, line)
                    baseline -= 10.2
                if author:
                    self.pdf.setFillColorRGB(*SLATE)
                    self.pdf.setFont(SANS_MEDIUM, CAPTION_SIZE)
                    self.pdf.drawString(
                        text_x,
                        top - 43,
                        self.fit_text(_plain(author.upper()), SANS_MEDIUM, CAPTION_SIZE, text_width),
                    )
                if row_index < len(chunk) - 1:
                    self.pdf.setStrokeColorRGB(*COOL_GRAY)
                    self.pdf.setLineWidth(.7)
                    self.pdf.line(x, top - row_height, self.width - self.right, top - row_height)

    def _render_article_opener(self, article, article_index: int, article_total: int) -> None:
        mode = _content_mode_label(self.edition, article.content_mode)
        self._label(
            f"{_ui(self.edition, 'feature')} {article_index:02d}",
            right=mode,
        )
        outer_column = 0 if self.page % 2 == 0 else 5
        title_start = 1 if self.page % 2 == 0 else 0
        title_x, title_width = self.grid_box(title_start, 5)
        medallion_x, medallion_width = self.grid_box(outer_column, 1)
        center_x = medallion_x + medallion_width / 2
        center_y = self.y - 28
        variant = article.opener_variant

        self.pdf.setStrokeColorRGB(*VIOLET)
        self.pdf.setFillColorRGB(*VIOLET)
        if variant == "split_axis":
            self.pdf.setLineWidth(1.4)
            self.pdf.circle(center_x, center_y, 21, fill=0, stroke=1)
            number_color = VIOLET
            number_size = 10
        elif variant == "stepped_title":
            self.pdf.setLineWidth(.8)
            self.pdf.circle(center_x, center_y, 22, fill=0, stroke=1)
            self.pdf.circle(center_x, center_y, 15, fill=1, stroke=0)
            number_color = WHITE
            number_size = 8.5
        else:
            self.pdf.circle(center_x, center_y, 21, fill=1, stroke=0)
            number_color = WHITE
            number_size = 11
        self.pdf.setFillColorRGB(*number_color)
        self.pdf.setFont(SANS_SEMIBOLD, number_size)
        self.pdf.drawCentredString(
            center_x,
            center_y - number_size * .34,
            f"{article_index:02d}",
        )

        self._monument_title(
            article.title,
            article.display_emphasis,
            title_x,
            self.y + 5,
            title_width,
            210,
            variant=variant,
        )
        if variant == "split_axis":
            credit_start = 2 if self.page % 2 == 0 else 0
        else:
            credit_start = 1
        credit_x, credit_width = self.grid_box(credit_start, 4)
        self._set_custom_frame(credit_x, credit_width, top=302)
        self._credit(
            article.author,
            f"{article_index} / {article_total}",
            author_note=article.author_note,
        )
        self._set_custom_frame(credit_x, credit_width, top=238)

    def _article_endmark(self, article_index: int) -> None:
        baseline = max(self.frame_bottom + 5, self.y - 1)
        self.pdf.setStrokeColorRGB(*VIOLET)
        self.pdf.setLineWidth(1.1)
        self.pdf.line(self.frame_left, baseline + 2, self.frame_left + 17, baseline + 2)
        self._tracked_label(
            f"{_ui(self.edition, 'end')} / {article_index:02d}",
            self.frame_left + 24,
            baseline,
            max(1, self.frame_width - 24),
            color=VIOLET,
            tracking=.25,
        )

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
                hero_top = self.y - 4
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
                    top=hero_bottom - 14,
                )
                self._render_blocks(blocks)
                self.reading_leading = BODY_LEADING
                self.paragraph_after = 5.4
                self.editorial_pages = self.page - start_page + 1
                if self.enforce_page_caps and self.editorial_pages > MAX_EDITORIAL_PAGES:
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
                self._begin_article(article.id)
                self.new_page(article.short_title, opener=True)
                start_page = self.page
                self.toc[article.id] = self.page
                self._render_article_opener(article, article_index, article_total)
                self.markdown(
                    article.manuscript,
                    lead=True,
                    figures=getattr(article, "figures", ()),
                    article_id=article.id,
                )
                self._article_endmark(article_index)
                page_count = self.page - start_page + 1
                self._finish_article()
                self.article_pages[article.id] = page_count
                if self.enforce_page_caps and page_count > MAX_ARTICLE_PAGES:
                    raise ValidationError(
                        f"Article {article.id} spans {page_count} reader pages; the hard cap is "
                        f"{MAX_ARTICLE_PAGES}. Condense it as a faithful_synthesis before building."
                    )
                if self.enforce_page_caps and page_count < article.minimum_reader_pages:
                    raise ValidationError(
                        f"Article {article.id} spans {page_count} reader pages; its editorial minimum is "
                        f"{article.minimum_reader_pages}. Restore substantive source detail before building."
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
        # Signature padding should look intentional, not like a title broken
        # into arbitrary word fragments. A compact systems diagram echoes the
        # edition's visual grammar while leaving the approved cover untouched.
        art_x, art_width = self.grid_box(0, 6)
        art_y = 260.0
        art_height = 126.0
        progress = (index + 1) / (total + 1)
        gate_x = art_x + art_width * (.28 + .44 * progress)
        signal_y = art_y + 34
        self.pdf.setFillColorRGB(*PALE_VIOLET)
        self.pdf.rect(art_x, art_y, art_width, art_height, fill=1, stroke=0)
        self.pdf.setFillColorRGB(*INK)
        self.pdf.rect(art_x, signal_y, gate_x - art_x, 58, fill=1, stroke=0)
        self.pdf.setFillColorRGB(*SIGNAL_ORANGE)
        self.pdf.rect(gate_x - 5, art_y + 17, 10, art_height - 34, fill=1, stroke=0)
        output_x = gate_x + 18
        output_width = max(8.0, (art_x + art_width - output_x - 18) / 4)
        self.pdf.setFillColorRGB(*VIOLET)
        for output_index in range(4):
            x = output_x + output_index * output_width
            self.pdf.rect(x, signal_y, max(4.0, output_width - 5), 58, fill=1, stroke=0)

        title_x, title_width = self.grid_box(1, 4)
        self._fitted_title_box(
            self.edition.title,
            title_x,
            218,
            title_width,
            88,
            maximum=30,
            minimum=20,
            maximum_lines=3,
            color=VIOLET,
            leading_ratio=1.0,
        )
        medallion_x, medallion_width = self.grid_box(0, 1)
        self.pdf.setFillColorRGB(*VIOLET)
        self.pdf.circle(medallion_x + medallion_width / 2, 193, 18, fill=1, stroke=0)
        self.pdf.setFillColorRGB(*WHITE)
        self.pdf.setFont(SANS_SEMIBOLD, 8)
        self.pdf.drawCentredString(
            medallion_x + medallion_width / 2,
            190,
            f"{index + 1}/{total}",
        )
        self._tracked_label(
            _ui(self.edition, "closing_plate"),
            title_x,
            104,
            title_width,
            color=VIOLET,
        )
        self._folio()

    def back_cover(self):
        self.continuation_columns = 1
        configured = self.edition.raw.get("format", {}).get("target_pages")
        # Reserve the inside back cover as a completely blank page, then keep
        # the designed back cover as the final page of the signature.
        minimum_total = self.page + 2
        target = int(configured) if configured else ((minimum_total + 3) // 4) * 4
        target = max(target, minimum_total)
        target = ((target + 3) // 4) * 4
        closing_pages = target - 2 - self.page
        for index in range(closing_pages):
            self._closing_plate(index, closing_pages)
        self.new_page(blank_header=True)
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
    balance_plans: dict[str, ArticleBalancePlan] | None = None,
    enforce_page_caps: bool = True,
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
    typesetter = _Typesetter(
        pdf,
        edition,
        A5,
        metrics,
        design=design,
        balance_plans=balance_plans,
        enforce_page_caps=enforce_page_caps,
    )
    typesetter.cover()
    # Page 2 is the inside front cover and must remain completely blank.
    typesetter.new_page(blank_header=True)
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
        dict(typesetter.article_frame_usage),
        {
            article_id: round(plan.frame_height, 3)
            for article_id, plan in (balance_plans or {}).items()
        },
        tuple(typesetter.figure_placements),
    )


def _terminal_balance_plans(layout: RenderLayout) -> dict[str, ArticleBalancePlan]:
    plans: dict[str, ArticleBalancePlan] = {}
    for article_id, page_count in layout.article_pages.items():
        if page_count < 3:
            continue
        tail_pages = {page_count - 1, page_count}
        frames = [
            frame
            for frame in layout.article_frame_usage.get(article_id, ())
            if frame.relative_page in tail_pages
        ]
        if len(frames) != TERMINAL_BALANCE_FRAMES:
            continue
        frames.sort(key=lambda frame: (frame.relative_page, frame.frame_index))
        if [(frame.relative_page, frame.frame_index) for frame in frames] != [
            (page_count - 1, 0),
            (page_count - 1, 1),
            (page_count, 0),
            (page_count, 1),
        ]:
            continue
        full_height = max(frame.capacity for frame in frames)
        final_page_use = frames[2].used + frames[3].used
        if (
            frames[3].used > .01
            or final_page_use / (2 * full_height) >= TERMINAL_BALANCE_THRESHOLD
        ):
            continue
        average = sum(frame.used for frame in frames) / TERMINAL_BALANCE_FRAMES
        frame_height = math.ceil(average / BODY_LEADING) * BODY_LEADING
        frame_height = max(frame_height, 8 * BODY_LEADING)
        if frame_height >= full_height - BODY_LEADING:
            continue
        plans[article_id] = ArticleBalancePlan(page_count, frame_height)
    return plans


def _balanced_draft(
    edition: Edition,
    probe: RenderLayout,
    *,
    design: str,
) -> tuple[dict[str, ArticleBalancePlan], RenderLayout]:
    plans = _terminal_balance_plans(probe)
    maximum_capacity = {
        article_id: max((frame.capacity for frame in frames), default=0.0)
        for article_id, frames in probe.article_frame_usage.items()
    }
    for _ in range(64):
        draft = _render_pass(
            io.BytesIO(),
            edition,
            probe.toc,
            design=design,
            balance_plans=plans,
            enforce_page_caps=False,
        )
        mismatched = [
            article_id
            for article_id, page_count in probe.article_pages.items()
            if draft.article_pages.get(article_id) != page_count
        ]
        if not mismatched:
            return plans, draft
        changed = False
        for article_id in mismatched:
            plan = plans.get(article_id)
            if not plan:
                raise ValidationError(
                    f"Article {article_id} pagination changed during terminal balancing"
                )
            enlarged = plan.frame_height + BODY_LEADING
            if enlarged >= maximum_capacity.get(article_id, 0.0):
                del plans[article_id]
            else:
                plans[article_id] = ArticleBalancePlan(plan.page_count, enlarged)
            changed = True
        if not changed:
            break
    raise ValidationError("Terminal-page balancing did not converge deterministically")


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
    probe = _render_pass(io.BytesIO(), edition, design=design)
    balance_plans, draft = _balanced_draft(edition, probe, design=design)
    final = _render_pass(
        str(output),
        edition,
        draft.toc,
        design=design,
        balance_plans=balance_plans,
    )
    if (
        draft.article_pages != final.article_pages
        or draft.editorial_pages != final.editorial_pages
    ):
        raise ValidationError("Content pagination changed between deterministic render passes")
    return final
