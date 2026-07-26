from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from .errors import DependencyError, ValidationError
from .image_contrast import prepare_print_image
from .manifest import Edition
from .reader_layout import FigurePlacement, FrameUsage, RenderLayout


MAX_ARTICLE_PAGES = 7
MAX_EDITORIAL_PAGES = 2
DESIGN_MONUMENT = "monument"
DESIGN_LABEL = "A / Quiet Standard"

BASE = 3.15
GRID_GUTTER = BASE * 3
BODY_SIZE = 10.0
BODY_LEADING = 13.0
CAPTION_SIZE = 6.8
COVER_ART_SIZE_POINTS = (249.35, 248.65)
MIN_FIGURE_PPI = 300.0
FIGURE_BAND_MAX_IMAGE_HEIGHT = 205.0
OPENER_FIGURE_MAX_IMAGE_HEIGHT = 270.0
ADAPTIVE_FIGURE_MIN_IMAGE_HEIGHT = 155.0
COMPACT_FIGURE_WIDTH = 260.0
COMPACT_FIGURE_MAX_IMAGE_HEIGHT = 170.0
FIGURE_COLUMN_MAX_IMAGE_HEIGHT = 190.0
FIGURE_TEXT_LEADING = 8.6
FIGURE_GAP = BASE * 5
INNER_MARGIN = 44.0
OUTER_MARGIN = 15 * 72 / 25.4
TEXT_TOP_INSET = 52.0
READING_MEASURE = 325.0
FOLIO_BASELINE = 19.5
ARTICLE_TAIL_ORNAMENT_MIN_HEIGHT = 118.0
ARTICLE_TAIL_ORNAMENT_MAX_HEIGHT = 214.0
RUNNING_HEADER_BASELINE_INSET = 20.0
HEADING_SPACE_BEFORE = {
    "h1": 18.0,
    "h2": 15.0,
    "h3": 10.0,
}

# Quiet Standard uses the sheet itself as the paper color. Violet is reserved for
# hierarchy and typographic furniture so interiors remain economical to print.
INK = (.055, .075, .085)
VIOLET = (.25, .10, .43)
SLATE = (.31, .35, .37)
COOL_GRAY = (.88, .89, .90)
PALE_VIOLET = (.955, .945, .975)
WHITE = (1, 1, 1)

# The Canto vivo cover is calibrated to the selected browser proof. These are
# cover inks, not substitutions for the cooler Quiet Standard interior palette.
COVER_PAPER = WHITE
COVER_INK = tuple(value / 255 for value in (10, 11, 13))
COVER_VIOLET = tuple(value / 255 for value in (75, 33, 192))
SIGNAL_ORANGE = tuple(value / 255 for value in (240, 87, 56))
COVER_ORANGE = SIGNAL_ORANGE
RUNNING_HEADER_SIGNAL_LENGTH = 14.0


@lru_cache(maxsize=16)
def _cover_graded_art(path_value: str) -> bytes:
    """Grade the two process inks without changing the source artwork file."""
    from PIL import Image

    image = Image.open(path_value).convert("RGB")
    graded = []
    for red, green, blue in image.get_flattened_data():
        if blue > 120 and blue > red * 1.7 and blue > green * 1.7:
            graded.append(
                (round(red * .96), min(255, round(green * 1.12)), round(blue * .953))
            )
        elif red > 170 and red > green * 1.8 and green > blue * 1.5:
            graded.append(
                (round(red * .916), min(255, round(green * 1.146)), min(255, blue + 45))
            )
        else:
            graded.append((red, green, blue))
    image.putdata(graded)
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=False)
    return output.getvalue()


@dataclass(frozen=True)
class CoverLayout:
    tab_width: float = 21.0
    tab_overdraw: float = 1.5
    issue_top: float = 26.5
    identity_top: float = 433.5
    wordmark_x: float = 38.0
    wordmark_top: float = 53.0
    title_x: float = 44.0
    title_top: float = 122.0
    title_width: float = 302.0
    art_x: float = 85.25
    art_top: float = 221.85
    footer_x: float = 44.0
    footer_y: float = 19.5


CANTO_VIVO_COVER = CoverLayout()
COVER_EDGE_TAB_WIDTH = CANTO_VIVO_COVER.tab_width

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
        "back_text_default": "Una antología independiente de textos que vale la pena conservar.",
        "opening_sentence": "Frase inicial / Editorial original",
        "issue_statement": "Declaración del número / La redacción",
        "continued": "Continuación",
        "end": "Fin",
        "closing_plate": "Lámina final",
        "figure": "Figura",
    },
}


def _article_tail_ornament_box(
    frame_left: float,
    frame_width: float,
    frame_bottom: float,
    endmark_baseline: float,
) -> tuple[float, float, float, float] | None:
    """Reserve a restrained motif only when an article ends with real open space."""
    bottom = frame_bottom + 24.0
    available_top = endmark_baseline - 31.0
    available_height = available_top - bottom
    if available_height < ARTICLE_TAIL_ORNAMENT_MIN_HEIGHT:
        return None
    height = min(available_height, ARTICLE_TAIL_ORNAMENT_MAX_HEIGHT)
    return frame_left, bottom, frame_width, height


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


def _cover_date(value: str) -> str:
    """Render ISO publication dates as the cover's compact numeric register."""
    parts = str(value).split("-")
    return " ".join(parts) if len(parts) == 3 and all(parts) else str(value)


def _section_label(edition: Edition, kind: str) -> str:
    if kind in {
        "original_editorial",
        "source_introduction",
        "original_synthesis",
        "source_record",
        "production_note",
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
    """Split an exact first sentence for deterministic editorial treatments."""
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
        enforce_page_caps: bool = True,
    ):
        self.pdf, self.edition, self.width, self.height, self.metrics = pdf, edition, *pagesize, metrics
        self.design = design
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
    def reading_width(self) -> float:
        return min(READING_MEASURE, self.live_width)

    @property
    def reading_left(self) -> float:
        return self.left + (self.live_width - self.reading_width) / 2

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
        if columns == 1 and role == "continuation":
            self.frame_left = self.reading_left
            self.frame_width = self.reading_width

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

    def _set_reading_frame(self, *, top: float, bottom: float | None = None) -> None:
        self._set_custom_frame(
            self.reading_left,
            self.reading_width,
            top=top,
            bottom=bottom,
        )
        self.frame_role = "continuation"

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
        self.pdf.setFillColorRGB(*INK)
        self.pdf.setFont(SANS_MEDIUM, CAPTION_SIZE)
        label = f"{self.page:02d}"
        running = _plain(
            self.edition.publication_name.upper()
        )
        self.pdf.drawString(
            OUTER_MARGIN,
            FOLIO_BASELINE,
            self.fit_text(running, SANS_MEDIUM, CAPTION_SIZE, self.live_width - 35),
        )
        self.pdf.drawRightString(self.width - OUTER_MARGIN, FOLIO_BASELINE, label)

    def _running_header(self) -> None:
        y = self.height - RUNNING_HEADER_BASELINE_INSET
        publication = _plain(self.edition.publication_name.upper())
        section = _plain(self.section.upper())
        right_width = self.live_width * .49
        if self.metrics.stringWidth(section, SANS_MEDIUM, CAPTION_SIZE) > right_width:
            raise ValidationError(
                f"Curated running title does not fit the Quiet Standard header: {self.section}"
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
        self.pdf.setStrokeColorRGB(*COOL_GRAY)
        self.pdf.setLineWidth(.55)
        self.pdf.line(self.left, y - 8, self.width - self.right, y - 8)
        # A tiny continuation signal carries the Canto vivo ink into the
        # reading pages without turning orange into a decorative palette.
        self.pdf.setStrokeColorRGB(*SIGNAL_ORANGE)
        self.pdf.setLineWidth(1.15)
        self.pdf.line(
            self.left,
            y - 8,
            self.left + RUNNING_HEADER_SIGNAL_LENGTH,
            y - 8,
        )

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
        # Quiet Standard has one reading column everywhere. Keep the argument
        # for call-site compatibility, but never allow a layout path to revive
        # the old double-column interior.
        selected_columns = 1
        if opener:
            role = "opener"
        elif self.active_article_id:
            role = "continuation"
        else:
            role = "standard"
        self._configure_frames(
            selected_columns,
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
        prepared = prepare_print_image(path)
        self.pdf.drawImage(
            ImageReader(prepared.image),
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
                f"Curated figure {figure_id} resolves to {ppi:.1f} ppi at its Quiet Standard "
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
                "for a Quiet Standard column plate"
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
        layout = str(self._figure_value(figure, "layout"))
        band_width = COMPACT_FIGURE_WIDTH if layout == "compact_band" else self.live_width
        band_x = self.left + (self.live_width - band_width) / 2
        draw_max_image_height = (
            COMPACT_FIGURE_MAX_IMAGE_HEIGHT
            if layout == "compact_band"
            else FIGURE_BAND_MAX_IMAGE_HEIGHT
        )
        figure_geometry = self._figure_geometry(
            figure,
            band_width,
            draw_max_image_height,
        )
        figure_height = figure_geometry[-1]
        bridge_top = min(self.y, self.height - self.top)
        can_bridge_current_page = (
            self.frame_count == 1
            and bridge_top - heading_height - figure_height >= self.bottom
        )
        if (
            not can_bridge_current_page
            and layout == "adaptive_band"
            and self.frame_count == 1
        ):
            fixed_height = figure_height - figure_geometry[1]
            available_image_height = (
                bridge_top - heading_height - self.bottom - fixed_height
            )
            if available_image_height >= ADAPTIVE_FIGURE_MIN_IMAGE_HEIGHT:
                draw_max_image_height = min(
                    FIGURE_BAND_MAX_IMAGE_HEIGHT,
                    available_image_height,
                )
                figure_height = self._figure_geometry(
                    figure,
                    band_width,
                    draw_max_image_height,
                )[-1]
                can_bridge_current_page = (
                    bridge_top - heading_height - figure_height >= self.bottom
                )
        if can_bridge_current_page:
            self._record_active_frame()
        else:
            self.new_page(columns=1)
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
            x=band_x,
            top=self.y,
            width=band_width,
            max_image_height=draw_max_image_height,
        )
        if layout == "compact_band":
            band_bottom += max(0.0, FIGURE_GAP - 12.0)
        if band_bottom - 4 * self.reading_leading < self.bottom:
            self.new_page(columns=1)
        else:
            self._set_reading_frame(top=band_bottom, bottom=self.bottom)

    def _opener_evidence_band(
        self,
        figure,
        *,
        article_id: str,
        figure_index: int,
    ) -> None:
        required = self._figure_geometry(
            figure,
            self.live_width,
            OPENER_FIGURE_MAX_IMAGE_HEIGHT,
        )[-1] - FIGURE_GAP
        bridge_top = self.y
        if bridge_top - required < self.bottom:
            self.new_page(columns=1)
            bridge_top = self.height - self.top
        self._set_custom_frame(
            self.left,
            self.live_width,
            top=bridge_top,
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
            max_image_height=OPENER_FIGURE_MAX_IMAGE_HEIGHT,
        ) + FIGURE_GAP
        if band_bottom - 4 * self.reading_leading < self.bottom:
            self.new_page(columns=1)
        else:
            self._set_reading_frame(top=band_bottom, bottom=self.bottom)

    def _landscape_plate(
        self,
        kind: str,
        heading: str,
        figure,
        *,
        article_id: str,
        figure_index: int,
    ) -> None:
        """Give a wide, label-dense source diagram a dedicated sideways plate."""
        from reportlab.lib.utils import ImageReader

        self.new_page(columns=1)
        path = Path(self._figure_value(figure, "path"))
        pixel_width, pixel_height = self._figure_dimensions(figure)
        local_width = self.height - self.top - self.bottom
        local_height = self.live_width
        heading_text = heading.upper() if kind == "h3" else heading
        heading_font = SANS_SEMIBOLD if kind == "h3" else SERIF_DISPLAY
        heading_size = 9.0 if kind == "h3" else 17.5
        heading_leading = 12.0 if kind == "h3" else 20.5
        heading_lines = self.lines(
            heading_text,
            heading_font,
            heading_size,
            local_width,
        )
        label_y = local_height - len(heading_lines) * heading_leading - 10
        image_top = label_y - CAPTION_SIZE - BASE * 2

        caption = str(self._figure_value(figure, "caption")).strip()
        credit = str(self._figure_value(figure, "credit")).strip()
        if not caption or not credit:
            raise ValidationError(
                f"Curated figure {self._figure_value(figure, 'id', '<unknown>')} requires "
                "a caption and credit"
            )
        caption_lines = self.lines(caption, SERIF, CAPTION_SIZE, local_width)
        credit_lines = self.lines(credit, SANS_MEDIUM, CAPTION_SIZE, local_width)
        notes_height = (len(caption_lines) + len(credit_lines)) * FIGURE_TEXT_LEADING
        image_bottom = notes_height + BASE * 3
        available_image_height = image_top - image_bottom
        scale = min(
            (local_width - 10) / pixel_width,
            available_image_height / pixel_height,
            72 / MIN_FIGURE_PPI,
        )
        image_width = pixel_width * scale
        image_height = pixel_height * scale
        image_x = (local_width - image_width) / 2
        image_y = image_top - image_height
        prepared = prepare_print_image(path)

        self.pdf.saveState()
        try:
            self.pdf.translate(self.left, self.height - self.top)
            self.pdf.rotate(-90)
            self.pdf.setFillColorRGB(*INK)
            self.pdf.setFont(heading_font, heading_size)
            baseline = local_height - heading_size
            for line in heading_lines:
                self.pdf.drawString(0, baseline, line)
                baseline -= heading_leading
            self._tracked_label(
                f"{_ui(self.edition, 'figure').upper()} {figure_index:02d}",
                0,
                label_y,
                local_width,
                color=VIOLET,
                tracking=.25,
            )
            self.pdf.drawImage(
                ImageReader(prepared.image),
                image_x,
                image_y,
                image_width,
                image_height,
                preserveAspectRatio=True,
                mask="auto",
            )
            self.pdf.setStrokeColorRGB(*INK)
            self.pdf.setLineWidth(.55)
            self.pdf.rect(image_x, image_y, image_width, image_height, fill=0, stroke=1)
            baseline = image_y - BASE * 2 - CAPTION_SIZE
            self.pdf.setFillColorRGB(*INK)
            self.pdf.setFont(SERIF, CAPTION_SIZE)
            for line in caption_lines:
                self.pdf.drawString(0, baseline, line)
                baseline -= FIGURE_TEXT_LEADING
            self.pdf.setFillColorRGB(*SLATE)
            self.pdf.setFont(SANS_MEDIUM, CAPTION_SIZE)
            for line in credit_lines:
                self.pdf.drawString(0, baseline, line)
                baseline -= FIGURE_TEXT_LEADING
        finally:
            self.pdf.restoreState()

        ppi = min(
            pixel_width / (image_width / 72),
            pixel_height / (image_height / 72),
        )
        figure_id = str(self._figure_value(figure, "id", f"figure-{figure_index}"))
        if ppi < MIN_FIGURE_PPI:
            raise ValidationError(
                f"Curated figure {figure_id} resolves to {ppi:.1f} ppi at its Quiet "
                f"Standard placement; the minimum is {MIN_FIGURE_PPI:.0f} ppi"
            )
        self.figure_placements.append(
            FigurePlacement(
                figure_id=figure_id,
                article_id=article_id,
                page=self.page,
                path=path,
                pixel_dimensions=(pixel_width, pixel_height),
                box_points=(
                    round(self.left + image_y, 3),
                    round(self.height - self.top - image_x - image_width, 3),
                    round(image_height, 3),
                    round(image_width, 3),
                ),
                effective_ppi=round(ppi, 1),
                caption=caption,
                credit=credit,
                rights_status=str(self._figure_value(figure, "rights_status", "unknown")),
            )
        )
        self.y = self.frame_bottom

    def block(self, kind: str, text: str, *, keep_together: bool = False):
        styles = {
            "h1": (SERIF_DISPLAY, 22, 25, HEADING_SPACE_BEFORE["h1"], 13),
            "h2": (SERIF_DISPLAY, 18.5, 21.5, HEADING_SPACE_BEFORE["h2"], 11),
            "h3": (SANS_SEMIBOLD, 8.5, 12, HEADING_SPACE_BEFORE["h3"], 8),
            "lead": (SERIF, 12.0, 16.4, 0, 13),
            "body": (SERIF, self.reading_size, self.reading_leading, 0, self.paragraph_after),
            "bullet": (SERIF, 10.0, self.reading_leading, 0, 6),
            "source_note": (SERIF, 7.2, 9.4, 0, 3),
            "quote": (SERIF_ITALIC, 11.0, 15.2, 0, 11),
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
                    f"A {kind} block is too tall for the Quiet Standard text frame"
                )
            self.y -= before
            self.pdf.setFillColorRGB(*(VIOLET if kind == "h3" else INK))
            self.pdf.setFont(font, size)
            for line in lines:
                self.pdf.drawString(self.frame_left, self.y, line)
                self.y -= leading
            self.y -= after
            return

        remaining_text = text
        first_line = True
        if keep_together:
            complete_lines = self.lines(text, font, size, self.column_width - indent)
            full_capacity = int((self.frame_top - self.frame_bottom) // leading)
            current_capacity = int((self.y - self.frame_bottom) // leading)
            if len(complete_lines) <= full_capacity and current_capacity < len(complete_lines):
                self._advance_frame()
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
        column_width = self.column_width
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
            if layout not in {
                "evidence_band",
                "evidence_band_prose",
                "adaptive_band",
                "compact_band",
                "column_plate",
                "landscape_plate",
                "landscape_plate_after",
            }:
                raise ValidationError(
                    f"Curated figure {self._figure_value(row, 'id', '<unknown>')} has invalid "
                    f"Quiet Standard layout {layout!r}"
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
            if layout in {"evidence_band", "evidence_band_prose", "adaptive_band"}:
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

        reference_notes = False
        deferred_landscape = None
        for index, (kind, value) in enumerate(blocks):
            if kind in {"h1", "h2", "h3"} and deferred_landscape is not None:
                deferred_kind, deferred_heading, deferred_figure, deferred_number = (
                    deferred_landscape
                )
                self._landscape_plate(
                    deferred_kind,
                    deferred_heading,
                    deferred_figure,
                    article_id=article_id,
                    figure_index=deferred_number,
                )
                deferred_landscape = None
            if kind in {"h1", "h2", "h3"}:
                reference_notes = value.strip().casefold() in {"references", "referencias"}
            figure = anchored.get(value.strip().casefold()) if kind in {"h2", "h3"} else None
            layout = str(self._figure_value(figure, "layout")) if figure is not None else ""
            if figure is not None and layout == "landscape_plate":
                figure_number += 1
                self._landscape_plate(
                    kind,
                    value,
                    figure,
                    article_id=article_id,
                    figure_index=figure_number,
                )
                continue
            if figure is not None and layout in {
                "evidence_band",
                "evidence_band_prose",
                "adaptive_band",
                "compact_band",
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
            if figure is not None and layout != "landscape_plate_after":
                self._keep_heading_with_column_figure(kind, value, figure)
            if kind == "code":
                self.code_block(value)
            else:
                if lead and index == 0 and kind == "body":
                    kind = "lead"
                elif reference_notes and kind == "bullet":
                    kind = "source_note"
                self.block(kind, value)
            if figure is not None and layout == "landscape_plate_after":
                figure_number += 1
                deferred_landscape = (kind, value, figure, figure_number)
            elif figure is not None:
                figure_number += 1
                self._column_figure(
                    figure,
                    article_id=article_id,
                    figure_index=figure_number,
                )
        if deferred_landscape is not None:
            deferred_kind, deferred_heading, deferred_figure, deferred_number = (
                deferred_landscape
            )
            self._landscape_plate(
                deferred_kind,
                deferred_heading,
                deferred_figure,
                article_id=article_id,
                figure_index=deferred_number,
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

    def _scaled_word(
        self,
        text: str,
        x: float,
        y: float,
        *,
        size: float,
        color,
        horizontal_scale: float = 100,
        tracking: float = 0,
        stroke_width: float = 0,
    ) -> None:
        self.pdf.saveState()
        try:
            self.pdf.setFillColorRGB(*color)
            if stroke_width:
                self.pdf.setStrokeColorRGB(*color)
                self.pdf.setLineWidth(stroke_width)
            word = self.pdf.beginText()
            word.setTextOrigin(x, y)
            word.setFont(SANS_BOLD, size)
            word.setHorizScale(horizontal_scale)
            word.setCharSpace(tracking)
            if stroke_width:
                word.setTextRenderMode(2)
            word.textLine(_plain(text))
            self.pdf.drawText(word)
        finally:
            self.pdf.restoreState()

    def _publication_wordmark(self, name: str, x: float, y: float, width: float) -> None:
        """Draw the selected Corte bruto wordmark as live cover typography."""
        value = _plain(name.upper()).strip()
        head, separator, tail = value.rpartition(" ")
        if not separator:
            head, tail = value, ""

        size = 42.0
        tracking = -3.6
        head_scale = 89.9
        tail_scale = 105.1

        def measured(text: str, font_size: float, horizontal_scale: float) -> float:
            unscaled = self.metrics.stringWidth(text, SANS_BOLD, font_size)
            unscaled += tracking * max(0, len(text) - 1)
            return unscaled * horizontal_scale / 100

        while size >= 25:
            head_width = measured(head, size, head_scale)
            tail_width = measured(tail, size, tail_scale) if tail else 0
            tail_offset = size * (97 / 42)
            box_width = tail_width + (13 if tail else 0)
            if max(head_width, tail_offset + box_width) <= width:
                break
            size -= .5
        else:
            raise ValidationError(f"Publication name cannot fit the cover wordmark: {name}")

        self._scaled_word(
            head,
            x + .36,
            y - 1.65,
            size=size,
            color=COVER_INK,
            horizontal_scale=head_scale,
            tracking=tracking,
            stroke_width=.30,
        )
        if not tail:
            return

        tail_x = x + tail_offset
        tail_y = y - size * .91
        box_x = -7.0
        box_y = -7.0
        slug_y = box_y - 1
        box_height = size * 1.04 - 1
        slug_height = box_height + .65
        slant = 0.0
        center_x = box_x + box_width / 2
        center_y = box_y + box_height / 2
        self.pdf.saveState()
        try:
            self.pdf.translate(tail_x, tail_y)
            self.pdf.translate(center_x, center_y)
            # PDF's Y axis points up, opposite to CSS: +10 reproduces skewX(-10deg).
            self.pdf.skew(0, 10)
            self.pdf.translate(-center_x, -center_y)
            slug = self.pdf.beginPath()
            slug.moveTo(box_x + slant, slug_y)
            slug.lineTo(box_x + box_width + slant, slug_y)
            slug.lineTo(box_x + box_width, slug_y + slug_height)
            slug.lineTo(box_x, slug_y + slug_height)
            slug.close()
            self.pdf.setFillColorRGB(*COVER_INK)
            self.pdf.drawPath(slug, fill=1, stroke=0)

            # A deliberately misregistered orange impression sits beneath the white type.
            self._scaled_word(
                tail,
                -13,
                1.65,
                size=size,
                color=COVER_ORANGE,
                horizontal_scale=106.6,
                tracking=tracking,
                stroke_width=.15,
            )
            self._scaled_word(
                tail,
                0,
                1.65,
                size=size,
                color=COVER_PAPER,
                horizontal_scale=tail_scale,
                tracking=tracking,
                stroke_width=.30,
            )
        finally:
            self.pdf.restoreState()

    def _cover_title(self, text: str, x: float, top: float, width: float) -> None:
        size = 29.0
        horizontal_scale = 79.5
        while size >= 20:
            value = _plain(text.upper())
            maximum_unscaled_width = width / (horizontal_scale / 100)
            words = value.split()
            candidates = []
            if len(words) >= 3:
                for split in range(1, len(words)):
                    pair = (" ".join(words[:split]), " ".join(words[split:]))
                    pair_widths = tuple(
                        self.metrics.stringWidth(line, SANS_BOLD, size) for line in pair
                    )
                    if max(pair_widths) <= maximum_unscaled_width:
                        candidates.append((abs(pair_widths[0] - pair_widths[1]), pair))
            lines = list(min(candidates, key=lambda item: item[0])[1]) if candidates else self.lines(
                value,
                SANS_BOLD,
                size,
                maximum_unscaled_width,
            )
            if len(lines) <= 3:
                break
            size -= .5
        else:
            raise ValidationError(f"Cover title cannot fit the Canto vivo title zone: {text}")

        baseline = top - size
        leading = size * .78
        colors = (COVER_INK, COVER_VIOLET, COVER_INK)
        for index, line in enumerate(lines):
            line_size = 28.0 if index % 2 else size
            self._scaled_word(
                line,
                x + (23 if index % 2 else -.65),
                baseline - (1 if index % 2 else 0),
                size=line_size,
                color=colors[index],
                horizontal_scale=80.9 if index % 2 else 79.83,
                tracking=-1.35,
                stroke_width=.09 if index % 2 == 0 else 0,
            )
            baseline -= leading

    def _cover_edge_tab(self) -> None:
        layout = CANTO_VIVO_COVER
        tab_x = self.width - layout.tab_width
        self.pdf.setFillColorRGB(*COVER_ORANGE)
        # Paint beyond every trim edge. The page box clips the overdraw and the
        # raster cannot expose a one-pixel paper hairline at the fore edge.
        self.pdf.rect(
            tab_x,
            -layout.tab_overdraw,
            layout.tab_width + layout.tab_overdraw * 2,
            self.height + layout.tab_overdraw * 2,
            fill=1,
            stroke=0,
        )

        def vertical_label(
            value: str,
            *,
            top: float,
            font_size: float,
            tracking: float,
            horizontal_scale: float = 100,
        ) -> None:
            ascent = self.metrics.getAscent(SANS_BOLD, font_size)
            descent = self.metrics.getDescent(SANS_BOLD, font_size)
            baseline_x = tab_x + layout.tab_width / 2 - (ascent + descent) / 2
            self.pdf.saveState()
            self.pdf.translate(baseline_x, self.height - top)
            self.pdf.rotate(-90)
            self.pdf.setFillColorRGB(*COVER_INK)
            label = self.pdf.beginText()
            label.setTextOrigin(0, 0)
            label.setFont(SANS_BOLD, font_size)
            label.setHorizScale(horizontal_scale)
            label.setCharSpace(tracking)
            label.textLine(value)
            self.pdf.drawText(label)
            self.pdf.restoreState()

        issue = f"{_plain(_ui(self.edition, 'issue').upper())} {str(self.edition.issue_number).zfill(3)}"
        vertical_label(issue, top=layout.issue_top, font_size=7.4, tracking=1.6)

        identity = f"{_plain(self.edition.publication_name.upper())} / BUENOS AIRES"
        vertical_label(
            identity,
            top=layout.identity_top,
            font_size=4.8,
            tracking=1.6,
            horizontal_scale=103.0,
        )

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
            raise ValidationError(f"Title cannot fit the Quiet Standard display box: {text}")
        self.pdf.setFillColorRGB(*color)
        self.pdf.setFont(SERIF_DISPLAY, size)
        baseline = top - size
        for line in lines:
            self._draw_aligned_string(line, x, baseline, width, align=align)
            baseline -= leading
        return baseline

    def _draw_image_fill(
        self,
        path: Path,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        record_cover_size: bool = False,
    ) -> None:
        from reportlab.lib.utils import ImageReader

        image = ImageReader(
            io.BytesIO(_cover_graded_art(str(path))) if record_cover_size else str(path)
        )
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
        if record_cover_size:
            self.cover_art_size_points = (width, height)

    def cover(self):
        layout = CANTO_VIVO_COVER
        self.new_page(blank_header=True)
        self.pdf.setFillColorRGB(*COVER_PAPER)
        self.pdf.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        self._cover_edge_tab()
        self._publication_wordmark(
            self.edition.publication_name,
            layout.wordmark_x,
            self.height - layout.wordmark_top,
            self.width - COVER_EDGE_TAB_WIDTH - 78,
        )

        self._cover_title(
            str(self.edition.cover.get("headline", self.edition.title)),
            layout.title_x,
            self.height - layout.title_top,
            layout.title_width,
        )

        art_width, art_height = COVER_ART_SIZE_POINTS
        art_x = layout.art_x
        art_y = self.height - layout.art_top - art_height
        if self.edition.cover_art:
            self._draw_image_fill(
                self.edition.cover_art,
                art_x,
                art_y,
                art_width,
                art_height,
                record_cover_size=True,
            )
        else:
            self.pdf.setFillColorRGB(*VIOLET)
            self.pdf.rect(art_x, art_y, art_width, art_height, fill=1, stroke=0)
            self.pdf.setStrokeColorRGB(*WHITE)
            self.pdf.setLineWidth(1)
            self.pdf.circle(art_x + art_width / 2, art_y + art_height / 2, 56, fill=0, stroke=1)
        self.pdf.setStrokeColorRGB(*COVER_INK)
        self.pdf.setLineWidth(.7)
        self.pdf.rect(art_x, art_y, art_width, art_height, fill=0, stroke=1)

        deck = str(self.edition.cover.get("deck", "")).strip()
        if deck:
            deck_x = art_x
            deck_width = art_width
            deck_size = 6.4
            deck_scale = 121.5
            # Preserve the approved two-line break independently of the small
            # optical size/width correction used for the drawn text.
            deck_lines = self.lines(deck, SANS, 7.8, deck_width)
            if len(deck_lines) > 5:
                raise ValidationError("Cover deck is too long for the Canto vivo cover")
            self.pdf.setFillColorRGB(*COVER_INK)
            baseline = self.height - 493 - deck_size
            for index, line in enumerate(deck_lines):
                line_text = self.pdf.beginText()
                line_text.setTextOrigin(deck_x - (.65 if index == 0 else 0), baseline)
                line_text.setFont(SANS, deck_size)
                line_text.setHorizScale(deck_scale)
                line_text.textLine(line)
                self.pdf.drawText(line_text)
                baseline -= 10.6

        self.pdf.setFillColorRGB(*COVER_INK)
        self.pdf.setFont(SANS_BOLD, CAPTION_SIZE)
        self.pdf.saveState()
        try:
            footer = self.pdf.beginText()
            footer.setTextOrigin(layout.footer_x, layout.footer_y)
            footer.setFont(SANS_BOLD, CAPTION_SIZE)
            footer.setCharSpace(.8)
            footer.textLine(_cover_date(self.edition.publication_date))
            self.pdf.drawText(footer)
        finally:
            self.pdf.restoreState()

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
            row_top = 479.0
            row_height = 393.0 / max(6, len(chunk))
            for row_index, (label, title, author, page_number) in enumerate(chunk):
                x = self.left
                available = self.live_width
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
                    raise ValidationError(
                        f"Contents title is too long for Quiet Standard: {title}"
                    )
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
        opener_has_figure = any(
            str(self._figure_value(figure, "anchor")).strip() == "__opener__"
            for figure in getattr(article, "figures", ())
        )
        self._label(
            f"{_ui(self.edition, 'feature')} {article_index:02d}",
            right=mode,
        )
        title_bottom = self._fitted_title_box(
            article.title,
            self.left,
            self.y - 12,
            self.live_width,
            165,
            maximum=30 if opener_has_figure else 35,
            minimum=24,
            maximum_lines=4,
            leading_ratio=.96,
        )
        self._set_custom_frame(self.left, self.live_width, top=title_bottom - 10)
        self._credit(
            article.author,
            author_note="" if opener_has_figure else article.author_note,
        )
        if opener_has_figure:
            self.y += 13
        # Without an opener figure, the opening paragraph acts as a standfirst
        # on a shared baseline zone. With one, the figure uses the available
        # space immediately after the credit instead of wasting a new page.
        self._set_reading_frame(top=self.y if opener_has_figure else 238)

    def _article_endmark(self, article_index: int, tail_art: Path | None) -> None:
        baseline = max(self.frame_bottom + 5, self.y - 1)
        self.pdf.setStrokeColorRGB(*SIGNAL_ORANGE)
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
        self._article_tail_ornament(baseline, tail_art)

    def _article_tail_ornament(
        self,
        endmark_baseline: float,
        tail_art: Path | None,
    ) -> None:
        if tail_art is None:
            return
        box = _article_tail_ornament_box(
            self.frame_left,
            self.frame_width,
            self.frame_bottom,
            endmark_baseline,
        )
        if box is None:
            return
        left, bottom, width, height = box
        from reportlab.lib.utils import ImageReader

        image = ImageReader(str(tail_art))
        pixel_width, pixel_height = image.getSize()
        effective_ppi = min(
            pixel_width / (width / 72),
            pixel_height / (height / 72),
        )
        if effective_ppi < MIN_FIGURE_PPI:
            raise ValidationError(
                f"Article tail art {tail_art} resolves to {effective_ppi:.1f} ppi; "
                f"the minimum is {MIN_FIGURE_PPI:.0f} ppi"
            )
        self._draw_image_fill(tail_art, left, bottom, width, height)

    def body(self):
        if self.edition.articles:
            if self.edition.editorial:
                self.continuation_columns = 1
                self.reading_size = BODY_SIZE
                self.reading_leading = BODY_LEADING
                self.paragraph_after = 6.2
                self.new_page(_ui(self.edition, "editorial"), opener=True)
                start_page = self.page
                self.toc["editorial"] = self.page
                self._label(
                    self.edition.editorial.label,
                    right=_ui(self.edition, "original_argument"),
                )
                title_bottom = self._fitted_title_box(
                    self.edition.editorial.title,
                    self.left,
                    self.y - 12,
                    self.live_width,
                    135,
                    maximum=35,
                    minimum=25,
                    maximum_lines=4,
                    leading_ratio=.96,
                )
                self._set_custom_frame(self.left, self.live_width, top=title_bottom - 10)
                self._credit(self.edition.editorial.byline)

                blocks = list(
                    _markdown_blocks(
                        self.edition.editorial.path.read_text(encoding="utf-8")
                    )
                )
                if not any(kind == "body" for kind, _ in blocks):
                    raise ValidationError(
                        "Opening editorial requires prose for the Quiet Standard opener"
                    )
                self._set_reading_frame(top=min(self.y, 390), bottom=self.bottom)
                self._render_blocks(blocks, lead=True)
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
                self.continuation_columns = 1
                self.reading_size = BODY_SIZE
                has_landscape_plate = any(
                    str(self._figure_value(figure, "layout")).startswith(
                        "landscape_plate"
                    )
                    for figure in getattr(article, "figures", ())
                )
                self.reading_leading = 12.2 if has_landscape_plate else BODY_LEADING
                self.paragraph_after = (
                    4.0
                    if has_landscape_plate
                    else 5.4
                )
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
                self._article_endmark(article_index, article.tail_art)
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
        self.continuation_columns = 1
        self.new_page(section.title, opener=True)
        self.toc[f"section-{index}"] = self.page
        label = _section_label(self.edition, section.kind)
        self._label(label, right=_ui(self.edition, "issue") + " " + str(self.edition.issue_number))
        title_bottom = self._fitted_title_box(
            section.title,
            self.left,
            self.y - 12,
            self.live_width,
            150,
            maximum=35,
            minimum=25,
            maximum_lines=4,
            leading_ratio=.96,
        )
        self._set_reading_frame(top=title_bottom - 25)
        self.markdown(section.path, lead=True)

    def _closing_plate(self, index: int, total: int) -> None:
        if index >= len(self.edition.closing_plates):
            raise ValidationError(
                f"Edition requires {total} unique closing plates for signature padding, but only "
                f"{len(self.edition.closing_plates)} are configured"
            )
        plate = self.edition.closing_plates[index]
        self.new_page(blank_header=True)
        self.pdf.setFillColorRGB(*WHITE)
        self.pdf.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        art_x, art_width = self.grid_box(0, 6)
        art_y = 205.0
        art_height = self.height - art_y
        self._draw_image_fill(plate.art_path, art_x, art_y, art_width, art_height)
        title_x, title_width = self.grid_box(0, 5)
        self._fitted_title_box(
            plate.title,
            title_x,
            168,
            title_width,
            92,
            maximum=32,
            minimum=22,
            maximum_lines=2,
            color=VIOLET,
            leading_ratio=1.0,
        )

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
        # Page -2 is the blank inside back cover. The final page is a blank
        # placeholder replaced by the canonical back-cover PDF after layout.
        self.new_page(blank_header=True)
        self.new_page(blank_header=True)
        # ReportLab drops a final page that has no drawing operations at all.
        # Materialize this replace-only placeholder without reimplementing the
        # back design; replace_outer_pages removes it before packaging.
        self.pdf.setFillColorRGB(*WHITE)
        self.pdf.rect(0, 0, self.width, self.height, fill=1, stroke=0)


def _render_pass(
    target,
    edition: Edition,
    toc: dict[str, int] | None = None,
    *,
    design: str,
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
        enforce_page_caps=enforce_page_caps,
    )
    # The cover is compiled once by CoverCompiler and spliced into this
    # placeholder. ReportLab owns interiors only; it must not reimplement the
    # cover design or create a second approval surface.
    typesetter.new_page(blank_header=True)
    # Page 2 is the completely blank inside front cover.
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
        # A legacy layout fact, permanently empty: the terminal balancer is
        # gone, and the field survives only because the packaged manifest key
        # derived from it must not change bytes.  See reader_layout.RenderLayout.
        {},
        tuple(typesetter.figure_placements),
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
    probe = _render_pass(io.BytesIO(), edition, design=design)
    # Full-height continuation frames keep prose moving naturally. The former
    # terminal balancer shortened the last two frames and manufactured large
    # white fields in the middle of an article; it has been removed, and
    # genuine tail space is handled by the small article-end ornament instead.
    draft = _render_pass(
        io.BytesIO(),
        edition,
        probe.toc,
        design=design,
        enforce_page_caps=False,
    )
    final = _render_pass(
        str(output),
        edition,
        draft.toc,
        design=design,
    )
    if (
        draft.article_pages != final.article_pages
        or draft.editorial_pages != final.editorial_pages
    ):
        raise ValidationError("Content pagination changed between deterministic render passes")
    return final
