from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
from html import unescape
from importlib import resources
import os
from pathlib import Path
import platform
import re
import sys
from typing import Any, NamedTuple
from urllib.parse import quote
from xml.etree.ElementTree import Element, SubElement

from .errors import DependencyError, ValidationError
from .html_edition import HtmlAsset, render_html_edition
from .manifest import Edition, source_code_payload
from .reader_layout import FigurePlacement, RenderLayout, declared_editorial_page_cap
from .reader_text import educate_reader_quotes, fold_reader_characters


WEASYPRINT_DESIGN = "WeasyPrint / A5 fold proof"

SHAPING_SCAFFOLDS: tuple[str, ...] = ()

_CSS_PIXELS_PER_POINT = 96 / 72
_POINTS_PER_CSS_PIXEL = 72 / 96
_MAX_ARTICLE_PAGES = 7
_MAX_EDITORIAL_PAGES = 2

_PAGE_HEIGHT_POINTS = 595.2756


_FRAME_BOTTOM_POINTS = 45.0


_FIRST_BASELINE_INSET_POINTS = 10.0046


_RASTER_NUDGE_POINTS = 0.005


def _reader_y_points(css_top_points: float, height_points: float) -> float:
    return _PAGE_HEIGHT_POINTS - css_top_points - height_points + _RASTER_NUDGE_POINTS


_TAIL_ORNAMENT_MAX_HEIGHT = 214.0
_TAIL_ORNAMENT_FOOT_INSET = 0.0
_TAIL_ORNAMENT_ENDMARK_CLEARANCE = 12.0

_PLATE_ANCHOR_TAGS = frozenset({"h1", "h2", "h3"})
_LANDSCAPE_PLATE_LAYOUTS = frozenset({"landscape_plate", "landscape_plate_after"})
_PLATE_FRAME_ACROSS_POINTS = 333.008


_LIVE_WIDTH_POINTS = 333.0079


_PAGE_MARGIN_BOTTOM_POINTS = 55.0046


_PAGE_MARGIN_TOP_POINTS = 52.0 - _FIRST_BASELINE_INSET_POINTS + _RASTER_NUDGE_POINTS
_FRAME_BOTTOM_RELIEF_POINTS = _FRAME_BOTTOM_POINTS - (
    _PAGE_MARGIN_BOTTOM_POINTS - _FIRST_BASELINE_INSET_POINTS
)


_CODE_OPENER_SIDE_POINTS = 55.5
_CODE_MIN_MODULE_POINTS = 0.35 * 72 / 25.4
_CODE_QUIET_MODULES = 4


_CODE_CREDIT_GAP_POINTS = 4.5 * 3.15


_CODE_ERROR_LEVELS = ("H", "Q", "M", "L")


_CODE_MEASURE_LEFT_POINTS = 4.004
_CODE_MEASURE_POINTS = 325.0


_FOLIO_BASELINE_POINTS = 19.5


_INTER_CAP_RATIO = 1490 / 2048


_CODE_DECODE_DPI = 300


_CODE_POSITION_TOLERANCE_POINTS = 2.0


_MODULE_EPSILON = 1e-9


_OUT_OF_FLOW_CODA_CLASSES = frozenset({"article-tail", "source-code"})


_ARTICLE_CODA_CLASSES = frozenset({"article-tail", "key-ideas"})


_CODE_INK = "rgb(5.5%,7.5%,8.5%)"
_CODE_PAPER = "rgb(100%,100%,100%)"


_CAPTION_SIZE = 6.8
_FIGURE_TEXT_LEADING = 8.6
_FIGURE_GAP = 15.75
_FIGURE_LABEL_ZONE_POINTS = _CAPTION_SIZE + 6.3
_FIGURE_BAND_MAX_IMAGE_HEIGHT = 205.0
_ADAPTIVE_FIGURE_MIN_IMAGE_HEIGHT = 155.0
_MIN_FIGURE_PPI = 300.0


_BAND_HEADING_MEASURE = {
    "h2": ("serif-display", 17.5, 20.5, 10.0),
    "h3": ("sans-semibold", 8.7, 12.0, 7.0),
}


_EVIDENCE_BAND_LAYOUTS = frozenset(
    {"evidence_band", "evidence_band_prose", "adaptive_band", "compact_band"}
)


_INNER_MARGIN_POINTS = 44.0
_OUTER_MARGIN_POINTS = 15 * 72 / 25.4
_BAND_CLEARANCE_LINES = 4
_PLATE_ARTICLE_READING_LEADING = 12.2
_READING_LEADING = 13.0


_HEADING_CLEARANCE_POINTS = 25.0


_FIGURE_RULE_WIDTH_POINTS = 0.55
_FIGURE_RULE_INK = "rgb(5.5%,7.5%,8.5%)"


_FIGURE_RULE_BLEED_POINTS = 1.0


_OPENER_TITLE_LEADING_RATIO = 0.96


_OPENER_TITLE_TOP_POINTS = _FIRST_BASELINE_INSET_POINTS + 25.0 + 12.0


_OPENER_LABEL_BOX_POINTS = 7.53085


_SANS_ZERO_LEADING_RATIO = (0.96875 - 0.2412109375) / 2
_ZERO_LEADING_SANS_BASELINE = 2.47375
_BYLINE_SIZE_POINTS = 7.4
_BYLINE_MIN_HORIZONTAL_SCALE = 0.78
_BYLINE_ZERO_LEADING_BASELINE = _BYLINE_SIZE_POINTS * _SANS_ZERO_LEADING_RATIO

_OPENER_TITLE_TO_CREDIT_POINTS = 10.0
_OPENER_BYLINE_PAD_POINTS = 12.0


_OPENER_TITLE_BASELINE_RATIO = _OPENER_TITLE_LEADING_RATIO / 2 + 0.3505

_FRAME_TOP_POINTS = _PAGE_HEIGHT_POINTS - 52.0


_OPENER_FIGURE_FIELD_BASE = 25.0 + 12.0 + 10.0 + 12.0 + 13.0 - 13.0
_EDITORIAL_FIELD_BASE = 25.0 + 12.0 + 10.0 + 12.0 + 13.0


_SECTION_FIELD_BASE = 25.0 + 12.0 + 25.0


_EDITORIAL_FIELD_FLOOR = _FRAME_TOP_POINTS - 390.0

_ARTICLE_TITLE_BOX = (165.0, 24.0)
_EDITORIAL_TITLE_BOX = (135.0, 25.0)
_SECTION_TITLE_BOX = (150.0, 25.0)
_ARTICLE_TITLE_MAX_WITH_FIGURE = 30.0
_ARTICLE_TITLE_MAX = 35.0
_EDITORIAL_TITLE_MAX = 35.0
_SECTION_TITLE_MAX = 35.0
_OPENER_TITLE_MAX_LINES = 4


_ILLUSTRATED_OPENER_RAIL_POINTS = 348.0
_ILLUSTRATED_OPENER_TITLE_BOX = (64.0, 22.0)
_ILLUSTRATED_OPENER_TITLE_MAX = 32.5
_ILLUSTRATED_OPENER_TITLE_MAX_LINES = 2


_ILLUSTRATED_OPENER_COMPACT_TITLE_MAX = 30.0
_ILLUSTRATED_OPENER_META_MEASURE_POINTS = 293.0
_ILLUSTRATED_OPENER_PAGE_HEIGHT_POINTS = _PAGE_HEIGHT_POINTS - _PAGE_MARGIN_TOP_POINTS - 54.9996
_ILLUSTRATED_OPENER_STANDARD = {
    "art": 195.1,
    "label": 24.0 + 7.15,
    "title_gap": 8.0,
    "tick": 25.0 + 2.4,
    "meta_padding": 9.0,
    "standfirst_gap": 23.5 + 9.0,
    "standfirst_size": 10.2,
    "standfirst_leading": 14.4,
}
_ILLUSTRATED_OPENER_COMPACT = {
    "art": 195.1,
    "label": 20.0 + 7.15,
    "title_gap": 6.0,
    "tick": 18.0 + 2.4,
    "meta_padding": 7.0,
    "standfirst_gap": 16.0 + 6.0,
    "standfirst_size": 9.6,
    "standfirst_leading": 13.2,
}


_ILLUSTRATED_OPENER_PANGO_RESERVE_POINTS = 13.2


_ILLUSTRATED_OPENER_CODE_SIDE_POINTS = 41.0


_OPENER_FIGURE_MAX_IMAGE_HEIGHT = 270.0


_OPENER_STANDFIRST_GAP_POINTS = 305.2756 - 264.5208


_OPENER_CREDIT_LINE_POINTS = 13.0


_NOTE_SIZE_POINTS = 6.8
_NOTE_LEADING_POINTS = 9.45
_NOTE_BASELINE_DROP_POINTS = 12.0
_NOTE_DESCENT_POINTS = _NOTE_SIZE_POINTS * 0.2412109375


_END_MARK_HOIST_POINTS = 20.0
_END_MARK_PAINT_POINTS = (
    _END_MARK_HOIST_POINTS + _FIRST_BASELINE_INSET_POINTS - _ZERO_LEADING_SANS_BASELINE + 1.0
)


_END_MARK_FLOOR_POINTS = _FRAME_BOTTOM_POINTS + 5.0
_END_MARK_DROP_POINTS = 1.0


_END_MARK_TEXT_INSET_POINTS = 24.0


_END_MARK_HARD_FLOOR_POINTS = _FOLIO_BASELINE_POINTS + _READING_LEADING

_FONT_FILES = {
    "serif": "source-serif-4/SourceSerif4SmText-Regular.ttf",
    "serif-display": "source-serif-4/SourceSerif4Display-Semibold.ttf",
    "sans-medium": "inter/Inter-Medium.ttf",
    "sans-semibold": "inter/Inter-SemiBold.ttf",
}

_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MARKDOWN_EMPHASIS = re.compile(r"[*`]")


_TOKEN_MEASURE_EPSILON = 0.01


_FIELD_OVERFLOW_EPSILON = 0.01


_RUNT_MEASURE_FRACTION = 0.15


_RUNT_MAX_RAG_FRACTION = 0.33


_BINDABLE_TAGS = frozenset({"p", "li", "span"})


_UNBINDABLE_CLASSES = frozenset(
    {
        "author-note",
        "byline",
        "content-label",
        "contents-kicker",
        "end-mark",
        "entry-author",
        "entry-folio",
        "entry-label",
        "entry-title",
        "folio-name",
        "issue-number",
        "key-ideas-label",
        "label-primary",
        "label-secondary",
        "provenance",
        "publication-name",
        "running-head",
        "subtitle",
    }
)


_UNBINDABLE_SUBTREES = frozenset({"header", "nav", "pre", "code"})
_RUNT_KEY = "data-runt-key"
_NO_BREAK_SPACE = "\u00a0"


_HYPHEN_LADDER_LIMIT = 2


@lru_cache(maxsize=None)
def _advance_widths(face: str) -> dict[str, float]:
    try:
        from fontTools.ttLib import TTFont
    except ImportError as exc:  # pragma: no cover - fontTools ships with WeasyPrint
        raise ValidationError(
            "Measuring the reader's display type requires fontTools, which "
            f"WeasyPrint itself depends on. Run `uv sync --locked`. Original error: {exc}"
        ) from exc
    path = resources.files("magazine").joinpath("assets", "fonts", _FONT_FILES[face])
    with resources.as_file(path) as resolved:
        font = TTFont(str(resolved))
    units = font["head"].unitsPerEm
    metrics = font["hmtx"].metrics
    return {
        chr(codepoint): metrics[glyph][0] / units
        for codepoint, glyph in font.getBestCmap().items()
        if glyph in metrics
    }


def _plain(text: str) -> str:
    return fold_reader_characters(_MARKDOWN_LINK.sub(r"\1", text))


def _string_width(text: str, face: str, size: float) -> float:
    widths = _advance_widths(face)
    return sum(widths.get(character, 0.0) for character in text) * size


def _wrap(text: str, face: str, size: float, width: float) -> list[str]:
    words: list[str] = []
    for word in _plain(_MARKDOWN_EMPHASIS.sub("", text)).split():
        if _string_width(word, face, size) <= width:
            words.append(word)
            continue
        chunk = ""
        for character in word:
            proposed = chunk + character
            if chunk and _string_width(proposed, face, size) > width:
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
        if current and _string_width(proposed, face, size) > width:
            result.append(current)
            current = word
        else:
            current = proposed
    if current:
        result.append(current)
    return result or [""]


def _fitted_display(
    text: str,
    width: float,
    height: float,
    *,
    maximum: float,
    minimum: float,
    maximum_lines: int,
    leading_ratio: float,
) -> tuple[float, list[str]]:
    size = maximum
    while size >= minimum:
        lines = _wrap(text, "serif-display", size, width)
        leading = size * leading_ratio
        if len(lines) <= maximum_lines and size + (len(lines) - 1) * leading <= height:
            return size, lines
        size -= 0.5
    raise ValidationError(f"Title cannot fit the Quiet Standard display box: {text}")


def render_a5_weasyprint(
    edition: Edition,
    output: Path,
    *,
    design: str = WEASYPRINT_DESIGN,
) -> RenderLayout:
    if design != WEASYPRINT_DESIGN:
        raise ValidationError(
            f"Unsupported WeasyPrint design {design!r}; expected {WEASYPRINT_DESIGN!r}"
        )
    _validate_caps(edition)
    HTML, CSS, FontConfiguration = _weasyprint_types()

    semantic = render_html_edition(edition)

    font_config = FontConfiguration()
    stylesheet = CSS(
        string=_read_print_css(),
        base_url=resources.files("magazine").joinpath("assets").as_uri() + "/",
        font_config=font_config,
    )
    document, html, plan = _render_to_signature(
        HTML,
        semantic.html,
        stylesheet,
        edition,
        font_config=font_config,
    )

    layout = _measure_layout(document, semantic.assets, design, plan)
    _validate_layout_caps(edition, layout)
    _validate_cover_slots(document)
    _validate_contents_page(document)
    _validate_reader_measures(document)

    _report_hyphen_ladders(document, edition)
    _validate_fitted_display(document, edition)
    _validate_illustrated_opener_integrity(document)
    _validate_opener_code_clearance(document, plan.codes_by_article)
    _validate_opener_credit_depth(document)
    document = _painted_reader(
        HTML, html, stylesheet, edition, plan, document, font_config=font_config
    )
    try:
        identifier = hashlib.sha256(html.encode("utf-8")).digest()[:16]
        pdf_bytes = document.write_pdf(pdf_identifier=identifier)
    except TypeError:
        pdf_bytes = document.write_pdf()
    except Exception as exc:
        raise ValidationError(f"WeasyPrint could not write edition {edition.id}: {exc}") from exc

    _validate_source_codes(
        pdf_bytes, edition, plan.source_codes, _measured_source_code_boxes(document)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(pdf_bytes)

    edition.raw[_TAIL_ART_LEDGER_KEY] = _tail_art_ledger(document, edition, plan)
    return layout


def _weasyprint_types() -> tuple[Any, Any, Any]:
    _configure_macos_library_path()
    try:
        from weasyprint import CSS, HTML
        from weasyprint.text.fonts import FontConfiguration
    except (ImportError, OSError) as exc:
        raise ValidationError(
            "WeasyPrint is unavailable. Run `uv sync --locked` and install the "
            "platform libraries required by WeasyPrint before using the experimental adapter. "
            f"Original error: {exc}"
        ) from exc
    return HTML, CSS, FontConfiguration


def _configure_macos_library_path() -> None:
    if platform.system() != "Darwin":
        return
    candidates = [
        str(path) for path in (Path("/opt/homebrew/lib"), Path("/usr/local/lib")) if path.is_dir()
    ]
    if not candidates:
        return
    existing = [
        entry for entry in os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "").split(":") if entry
    ]
    additions = [entry for entry in candidates if entry not in existing]
    if additions:
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join([*additions, *existing])


def _read_print_css() -> str:
    return (
        resources.files("magazine")
        .joinpath("assets", "weasyprint-a5.css")
        .read_text(encoding="utf-8")
    )


def _with_print_slots(html: str) -> str:
    main_open = "<main data-edition-id="
    start = html.find(main_open)
    if start < 0:
        raise ValidationError("Semantic edition HTML did not contain its main element")
    close = html.rfind("  </main>")
    if close < 0:
        raise ValidationError("Semantic edition HTML did not contain a closing main element")
    opener_end = html.find(">", start) + 1
    if opener_end <= start:
        raise ValidationError("Semantic edition HTML has a malformed main element")
    before = html[:opener_end]
    body = html[opener_end:close]
    after = html[close:]
    slots = (
        '\n    <div class="outer-cover-slot" aria-hidden="true"></div>'
        '\n    <div class="inside-cover-slot" aria-hidden="true"></div>'
    )
    ending = (
        '\n    <div class="inside-back-cover-slot" aria-hidden="true"></div>'
        '\n    <div class="back-cover-slot" aria-hidden="true"></div>\n'
    )
    return before + slots + body + ending + after


@dataclass(frozen=True, slots=True, order=True)
class SourceCode:
    article_id: str
    slot: str
    error: str
    modules: int
    module: float
    url: str
    left: float = 0.0
    top: float = 0.0

    @property
    def side(self) -> float:
        return self.modules * self.module

    @property
    def quiet(self) -> float:
        return _CODE_QUIET_MODULES * self.module

    @property
    def symbol_top(self) -> float:
        return self.top + self.quiet

    @property
    def symbol_bottom(self) -> float:
        return self.top + self.side - self.quiet

    @property
    def symbol_left(self) -> float:
        return self.left + self.quiet

    @property
    def symbol_right(self) -> float:
        return self.left + self.side - self.quiet


@dataclass(frozen=True, slots=True)
class ReaderPlan:
    closing_plates: int
    source_codes: tuple[SourceCode, ...] = ()
    tail_arts: tuple[tuple[str, float, float], ...] = ()
    adaptive_images: tuple[tuple[str, float], ...] = ()
    band_offsets: tuple[tuple[str, float], ...] = ()
    end_marks: tuple[tuple[str, float], ...] = ()
    runt_binds: tuple[str, ...] = ()
    midpage_band_anchors: tuple[str, ...] = ()

    @property
    def codes_by_article(self) -> dict[str, SourceCode]:
        return {code.article_id: code for code in self.source_codes}

    @property
    def tail_art_heights(self) -> dict[str, float]:
        return {article_id: height for article_id, height, _ in self.tail_arts}

    @property
    def tail_art_bands(self) -> dict[str, "TailBand"]:
        return {article_id: TailBand(height, lift) for article_id, height, lift in self.tail_arts}

    @property
    def end_mark_offsets(self) -> dict[str, float]:
        return dict(self.end_marks)

    @property
    def adaptive_image_heights(self) -> dict[str, float]:
        return dict(self.adaptive_images)

    @property
    def band_offset_points(self) -> dict[str, float]:
        return dict(self.band_offsets)


class TailBand(NamedTuple):
    height: float
    lift: float


class MeasuredRule(NamedTuple):
    page: int
    left: float
    top: float
    width: float
    height: float


def _render_to_signature(
    HTML: Any,
    semantic_html: str,
    stylesheet: Any,
    edition: Edition,
    *,
    font_config: Any = None,
) -> tuple[Any, str, ReaderPlan]:
    html = _with_print_slots(semantic_html)
    bare = ReaderPlan(closing_plates=len(edition.closing_plates))
    document = _lay_out(HTML, html, stylesheet, edition, bare, font_config=font_config)
    probe = replace(bare, runt_binds=_measured_runt_binds(document))
    if probe != bare:
        document = _lay_out(HTML, html, stylesheet, edition, probe, font_config=font_config)
    plan = _measured_plan(document, edition, probe.runt_binds)
    if plan != probe:
        document = _lay_out(HTML, html, stylesheet, edition, plan, font_config=font_config)
        settled = _measured_plan(document, edition, plan.runt_binds)
        if settled != plan:
            raise ValidationError(
                f"WeasyPrint pagination for edition {edition.id} did not settle: the "
                f"plan measured from the probe pass ({plan}) is not the plan the "
                f"laid-out reader measures ({settled})"
            )
    if len(document.pages) % 4:
        signature_coda = f"{edition.publication_name} - {edition.title}"
        raise ValidationError(
            f"WeasyPrint reader for edition {edition.id} is {len(document.pages)} pages, "
            f"which is not an A4-fold signature. Closing plates close the signature; a "
            f"blank filler page printing {signature_coda!r} is not an allowed substitute."
        )
    return document, html, plan


def _painted_reader(
    HTML: Any,
    html: str,
    stylesheet: Any,
    edition: Edition,
    plan: ReaderPlan,
    document: Any,
    *,
    font_config: Any = None,
) -> Any:
    declared = _declared_figure_ids(html)
    rules = _measured_figure_rules(document)
    if set(rules) != declared:
        raise ValidationError(
            f"WeasyPrint measured figure frames for {sorted(rules)} in edition "
            f"{edition.id}, but its semantic HTML declares curated figures "
            f"{sorted(declared)}. A curated figure without a measured image box "
            f"would ship with no frame at all."
        )
    if not rules:
        return document
    before = _measured_flow_positions(document)
    painted = _lay_out(
        HTML, html, stylesheet, edition, plan, font_config=font_config, figure_rules=rules
    )
    settled = _measured_figure_rules(painted)
    if settled != rules or len(painted.pages) != len(document.pages):
        raise ValidationError(
            f"WeasyPrint figure frames moved edition {edition.id}: the reader measured "
            f"{len(document.pages)} pages and {rules} before the frames were painted, and "
            f"{len(painted.pages)} pages and {settled} after."
        )
    after = _measured_flow_positions(painted)
    if after != before:
        moved = [
            f"page {was[0]} {was[1]!r}: ({was[2]}, {was[3]}) -> ({now[2]}, {now[3]})"
            for was, now in zip(before, after)
            if was != now
        ]
        raise ValidationError(
            f"WeasyPrint figure frames moved text in edition {edition.id}: "
            f"{len(before)} text boxes before the frames were painted and "
            f"{len(after)} after, {len(moved)} of them displaced. " + "; ".join(moved[:5])
        )
    _validate_figure_rules(painted, rules)
    return painted


def _declared_figure_ids(html: str) -> set[str]:
    return {unescape(value) for value in re.findall(r'data-figure-id="([^"]+)"', html)}


def _measured_flow_positions(document: Any) -> tuple[tuple[int, str, float, float], ...]:
    positions: list[tuple[int, str, float, float]] = []
    for page_number, page in enumerate(document.pages, start=1):
        for box in _walk_boxes(page._page_box):
            text = getattr(box, "text", None)
            if not isinstance(text, str):
                continue
            positions.append(
                (
                    page_number,
                    text,
                    round(float(box.position_x), 6),
                    round(float(box.position_y), 6),
                )
            )
    return tuple(positions)


def _lay_out(
    HTML: Any,
    html: str,
    stylesheet: Any,
    edition: Edition,
    plan: ReaderPlan,
    *,
    font_config: Any = None,
    figure_rules: Mapping[str, MeasuredRule] | None = None,
) -> Any:
    source = HTML(string=html, base_url=Path.cwd().as_uri() + "/")
    tree = source.etree_element

    _key_prose_blocks(tree)
    _bind_paragraph_tails(tree, plan.runt_binds)
    _install_page_chrome(tree, edition)
    _rewrite_landscape_plates(tree)
    _pin_opener_fields(tree, edition)
    _mark_band_bridges(tree)
    _apply_anchor_clearances(tree, plan.midpage_band_anchors)
    _apply_adaptive_images(tree, plan.adaptive_image_heights)
    _apply_band_offsets(tree, plan.band_offset_points)
    _install_flow_clearances(tree)
    _place_closing_plates(tree, plan.closing_plates)

    _apply_tail_arts(tree, plan.tail_art_bands)
    _apply_print_contrast(tree)
    _apply_end_marks(tree, plan.end_mark_offsets)
    _apply_source_codes(tree, plan.codes_by_article)

    _apply_figure_rules(tree, figure_rules or {})
    try:
        return source.render(stylesheets=[stylesheet], font_config=font_config)
    except Exception as exc:
        raise ValidationError(f"WeasyPrint could not lay out edition {edition.id}: {exc}") from exc


def _element_classes(element: Element) -> frozenset[str]:
    return frozenset((element.get("class") or "").split())


def _key_prose_blocks(tree: Element) -> None:
    for index, block in enumerate(_prose_blocks(tree)):
        block.set(_RUNT_KEY, str(index))


def _prose_blocks(element: Element, *, inside_main: bool = False) -> Iterable[Element]:
    tag = str(element.tag).rsplit("}", 1)[-1].lower()
    if tag in _UNBINDABLE_SUBTREES or _element_classes(element) & _UNBINDABLE_CLASSES:
        return
    if tag == "main":
        inside_main = True
    if tag == "figure" and "closing-plate" in _element_classes(element):
        return
    nested = [block for child in element for block in _prose_blocks(child, inside_main=inside_main)]
    if nested:
        yield from nested
        return
    if inside_main and tag in _BINDABLE_TAGS and "".join(element.itertext()).strip():
        yield element


def _bind_paragraph_tails(tree: Element, keys: Iterable[str]) -> None:
    wanted = frozenset(keys)
    if not wanted:
        return
    for element in tree.iter():
        if element.get(_RUNT_KEY) in wanted:
            _bind_last_two_words(element)


def _bind_last_two_words(block: Element) -> None:
    slots = list(_text_slots(block))
    joined = "".join(getattr(owner, attribute) or "" for owner, attribute in slots)
    trimmed = joined.rstrip()
    end = len(trimmed)
    while end and not trimmed[end - 1].isspace():
        end -= 1
    if not end:
        return
    start = end
    while start and trimmed[start - 1].isspace():
        start -= 1
    if not trimmed[:start].strip():
        return
    offset = 0
    for owner, attribute in slots:
        value = getattr(owner, attribute) or ""
        if offset <= start and end <= offset + len(value):
            setattr(
                owner,
                attribute,
                value[: start - offset] + _NO_BREAK_SPACE + value[end - offset :],
            )
            return
        offset += len(value)


def _text_slots(element: Element) -> Iterable[tuple[Element, str]]:
    yield element, "text"
    for child in element:
        yield from _text_slots(child)
        yield child, "tail"


def _measured_runt_binds(document: Any) -> tuple[str, ...]:
    lines: dict[str, list[tuple[float, str]]] = {}
    boxes: dict[str, tuple[float, float, "_Hyphenation | None"]] = {}
    for page in document.pages:
        for box in _walk_boxes(page._page_box):
            element = getattr(box, "element", None)
            key = getattr(element, "attrib", {}).get(_RUNT_KEY) if element is not None else None

            if key is None or type(box).__name__ != "BlockBox":
                continue
            boxes[key] = (
                float(box.width),
                float(box.style["font_size"]),
                _measured_hyphenation(box.style),
            )
            lines.setdefault(key, []).extend(
                (float(line.width), _box_text(line))
                for line in _walk_boxes(box)
                if type(line).__name__ == "LineBox"
            )
    return tuple(
        sorted(
            (key for key, set_lines in lines.items() if _is_runt(set_lines, *boxes[key])),
            key=int,
        )
    )


class _Hyphenation(NamedTuple):
    lang: str
    total: int
    left: int
    right: int
    character: str


def _measured_hyphenation(style: Any) -> _Hyphenation | None:
    if style["hyphens"] != "auto" or not style["lang"]:
        return None
    import pyphen

    lang = pyphen.language_fallback(style["lang"])
    if not lang:
        return None
    total, left, right = style["hyphenate_limit_chars"]
    return _Hyphenation(lang, int(total), int(left), int(right), style["hyphenate_character"])


def _is_runt(
    set_lines: list[tuple[float, str]],
    measure: float,
    size: float,
    hyphenation: _Hyphenation | None = None,
) -> bool:
    if len(set_lines) < 2:
        return False
    width, text = set_lines[-1]
    previous_width, previous_text = set_lines[-2]
    words = text.split()
    previous = previous_text.split()
    if len(words) != 1 or not previous:
        return False
    if hyphenation and previous_text.rstrip().endswith(hyphenation.character):
        return False
    if width > measure * _RUNT_MEASURE_FRACTION:
        return False
    pair = f"{previous[-1]}{_NO_BREAK_SPACE}{words[0]}"
    if _string_width(pair, "serif", size) > measure:
        return False
    opened = measure - (previous_width - _string_width(f" {previous[-1]}", "serif", size))
    return opened <= measure * _RUNT_MAX_RAG_FRACTION


class HyphenLadder(NamedTuple):
    key: str
    page: int
    run: int
    sample: str


def _measured_hyphen_ladders(document: Any) -> tuple[HyphenLadder, ...]:
    lines: dict[str, list[tuple[str, int]]] = {}
    characters: dict[str, str] = {}
    for page_number, page in enumerate(document.pages, start=1):
        for box in _walk_boxes(page._page_box):
            element = getattr(box, "element", None)
            key = getattr(element, "attrib", {}).get(_RUNT_KEY) if element is not None else None
            if key is None or type(box).__name__ != "BlockBox":
                continue
            characters[key] = str(box.style["hyphenate_character"])
            lines.setdefault(key, []).extend(
                (_box_text(line), page_number)
                for line in _walk_boxes(box)
                if type(line).__name__ == "LineBox"
            )
    ladders: list[HyphenLadder] = []
    for key in sorted(lines, key=int):
        endings = (characters[key], "-")
        run: list[tuple[str, int]] = []
        longest: list[tuple[str, int]] = []
        for text, page_number in lines[key]:
            run = [*run, (text, page_number)] if text.rstrip().endswith(endings) else []
            if len(run) > len(longest):
                longest = run
        if len(longest) > _HYPHEN_LADDER_LIMIT:
            ladders.append(HyphenLadder(key, longest[0][1], len(longest), longest[0][0]))
    return tuple(ladders)


def _report_hyphen_ladders(document: Any, edition: Edition) -> tuple[HyphenLadder, ...]:
    ladders = _measured_hyphen_ladders(document)
    for ladder in ladders:
        print(
            f"hyphen ladder: edition {edition.id} reader page {ladder.page} sets "
            f"{ladder.run} consecutive hyphen-ended lines in prose block "
            f"{ladder.key} (allowed {_HYPHEN_LADDER_LIMIT}), starting "
            f"{ladder.sample[:60]!r}",
            file=sys.stderr,
        )
    return ladders


def _install_page_chrome(tree: Element, edition: Edition) -> None:
    publication = str(edition.publication_name)
    for slot in tree.iter("div"):
        if "outer-cover-slot" in _element_classes(slot):
            name = Element("p", {"class": "folio-name"})
            name.text = publication
            slot.insert(0, name)
            break
    for piece in (*tree.iter("article"), *tree.iter("section")):
        short_title = (piece.get("data-short-title") or "").strip()
        if not short_title:
            continue
        head = Element("div", {"class": "running-head"})
        row = SubElement(head, "div", {"class": "running-head-row"})
        SubElement(row, "span").text = publication
        SubElement(row, "span").text = short_title

        SubElement(SubElement(head, "div", {"class": "running-head-rule"}), "i")
        piece.insert(0, head)


def _rewrite_landscape_plates(tree: Element) -> None:
    for article in tree.iter("article"):
        _rewrite_article_plates(article)


def _rewrite_article_plates(article: Element) -> None:
    ordered: list[Element] = []
    deferred: Element | None = None
    for child in article:
        layout = child.get("data-layout", "") if child.tag == "figure" else ""
        if layout not in _LANDSCAPE_PLATE_LAYOUTS:
            releases = child.tag in _PLATE_ANCHOR_TAGS or bool(
                _element_classes(child) & _ARTICLE_CODA_CLASSES
            )
            if releases and deferred is not None:
                ordered.append(deferred)
                deferred = None
            ordered.append(child)
            continue
        anchor = ordered[-1] if ordered and ordered[-1].tag in _PLATE_ANCHOR_TAGS else None
        if layout == "landscape_plate":
            if anchor is not None:
                ordered.pop()
            ordered.append(_landscape_plate_page(child, anchor))
            continue
        deferred = _landscape_plate_page(child, None if anchor is None else deepcopy(anchor))
    if deferred is not None:
        ordered.append(deferred)
    article[:] = ordered


def _landscape_plate_page(figure: Element, heading: Element | None) -> Element:
    plate = Element(
        "div",
        {"class": "landscape-plate", "data-layout": figure.get("data-layout", "")},
    )
    rotor = SubElement(plate, "div", {"class": "landscape-plate-rotor"})
    if heading is not None:
        heading.tail = None
        rotor.append(heading)
    figure.tail = None
    rotor.append(figure)
    return plate


def _opener_figure(article: Element) -> Element | None:
    for child in article:
        if child.tag == "figure" and child.get("data-anchor") == "__opener__":
            return child
    return None


def _opener_header(piece: Element) -> Element:
    header = next((child for child in piece if child.tag == "header"), None)
    if header is None:
        raise ValidationError(
            f"Opener {piece.get('id') or piece.get('data-article-id')!r} has no header"
        )
    return header


def _is_illustrated_article(article: Any) -> bool:
    return getattr(article, "opener_art", None) is not None


def _is_illustrated_header(header: Any) -> bool:
    element = getattr(header, "element", None)
    if element is None and getattr(header, "tag", None) is not None:
        element = header
    return element is not None and "article-opener" in _element_classes(element)


def _set_illustrated_opener_title(header: Element, size: float) -> None:
    for title in header.iter("h1"):
        title.set(
            "style",
            f"font-size: {size:.4f}pt; line-height: {size * _OPENER_TITLE_LEADING_RATIO:.4f}pt",
        )
        return
    raise ValidationError("An illustrated opener header must carry the article title as an h1")


@dataclass(frozen=True)
class OpenerIntroBudget:
    lines: int
    safe_characters: int
    measure_points: float
    size_points: float

    def fits(self, intro: str) -> bool:

        return len(self.wrapped(intro)) <= self.lines

    def wrapped(self, intro: str) -> list[str]:

        return _wrap(intro, "serif", self.size_points, self.measure_points)


def illustrated_opener_intro_budget(
    *,
    title: str,
    byline: str,
    author_note: str = "",
    sample: str = "",
) -> OpenerIntroBudget | None:

    density = _ILLUSTRATED_OPENER_COMPACT
    try:
        title_size, title_lines = _fitted_display(
            title,
            _ILLUSTRATED_OPENER_RAIL_POINTS,
            _ILLUSTRATED_OPENER_TITLE_BOX[0],
            maximum=_ILLUSTRATED_OPENER_COMPACT_TITLE_MAX,
            minimum=_ILLUSTRATED_OPENER_TITLE_BOX[1],
            maximum_lines=_ILLUSTRATED_OPENER_TITLE_MAX_LINES,
            leading_ratio=_OPENER_TITLE_LEADING_RATIO,
        )
    except ValidationError:
        return None
    fixed = _opener_stack_height(
        title_size=title_size,
        title_lines=len(title_lines),
        byline_text=byline,
        note_text=author_note,
        standfirst_lines=0,
        density=density,
    )
    room = _ILLUSTRATED_OPENER_PAGE_HEIGHT_POINTS - _ILLUSTRATED_OPENER_PANGO_RESERVE_POINTS - fixed
    size = density["standfirst_size"]
    lines = max(int(room // density["standfirst_leading"]), 0)
    return OpenerIntroBudget(
        lines=lines,
        safe_characters=lines * _safe_characters_per_line(sample, size),
        measure_points=_ILLUSTRATED_OPENER_RAIL_POINTS,
        size_points=size,
    )


def _safe_characters_per_line(sample: str, size: float) -> int:

    text = _plain(" ".join(sample.split()))
    words = text.split()
    if not text or not words:
        return 0
    width = _string_width(text, "serif", size)
    if width <= 0:
        return 0
    long_word = sorted(_string_width(word, "serif", size) for word in words)[int(len(words) * 0.9)]
    usable = _ILLUSTRATED_OPENER_RAIL_POINTS - long_word
    if usable <= 0:
        return 0
    return int(usable // (width / len(text)))


def _illustrated_opener_height(
    header: Element,
    *,
    title_size: float,
    title_lines: int,
    density: Mapping[str, float],
) -> float:
    byline = next(
        (item for item in header.iter("p") if "byline" in _element_classes(item)),
        None,
    )
    note = next(
        (item for item in header.iter("p") if "author-note" in _element_classes(item)),
        None,
    )
    standfirst = next(
        (item for item in header.iter("p") if "standfirst" in _element_classes(item)),
        None,
    )
    if byline is None or standfirst is None:
        raise ValidationError(
            "An illustrated opener needs a byline and first paragraph inside its header"
        )

    standfirst_text = "".join(standfirst.itertext()).strip()
    return _opener_stack_height(
        title_size=title_size,
        title_lines=title_lines,
        byline_text="".join(byline.itertext()).strip(),
        note_text="".join(note.itertext()).strip() if note is not None else "",
        standfirst_lines=len(
            _wrap(
                standfirst_text,
                "serif",
                density["standfirst_size"],
                _ILLUSTRATED_OPENER_RAIL_POINTS,
            )
        ),
        density=density,
    )


def _opener_stack_height(
    *,
    title_size: float,
    title_lines: int,
    byline_text: str,
    note_text: str,
    standfirst_lines: int,
    density: Mapping[str, float],
) -> float:

    byline_lines = len(
        _wrap(
            byline_text,
            "sans-semibold",
            _BYLINE_SIZE_POINTS,
            _ILLUSTRATED_OPENER_META_MEASURE_POINTS,
        )
    )
    credit_height = byline_lines * 8.5
    if note_text:
        credit_height += (
            3.2
            + len(
                _wrap(
                    note_text,
                    "sans-medium",
                    6.8,
                    _ILLUSTRATED_OPENER_META_MEASURE_POINTS,
                )
            )
            * 9.4
        )
    meta_height = max(_ILLUSTRATED_OPENER_CODE_SIDE_POINTS, credit_height)
    meta_height += 2 * density["meta_padding"] + 1.0
    return (
        density["art"]
        + density["label"]
        + density["title_gap"]
        + title_lines * title_size * _OPENER_TITLE_LEADING_RATIO
        + density["tick"]
        + meta_height
        + density["standfirst_gap"]
        + standfirst_lines * density["standfirst_leading"]
    )


def _set_opener_title(header: Element, size: float) -> None:
    baseline_head = _OPENER_TITLE_BASELINE_RATIO * size
    margin_top = _OPENER_TITLE_TOP_POINTS - _OPENER_LABEL_BOX_POINTS + size - baseline_head
    margin_bottom = (
        baseline_head
        + _OPENER_TITLE_TO_CREDIT_POINTS
        - _OPENER_BYLINE_PAD_POINTS
        - _BYLINE_ZERO_LEADING_BASELINE
    )
    for title in header.iter("h1"):
        title.set(
            "style",
            f"font-size: {size:.4f}pt; line-height: "
            f"{size * _OPENER_TITLE_LEADING_RATIO:.4f}pt; "
            f"margin: {margin_top:.4f}pt 0 {margin_bottom:.4f}pt",
        )
        return
    raise ValidationError("An opener header must carry the piece's title as an h1")


def _pin_opener_fields(tree: Element, edition: Edition) -> None:
    by_id = {article.id: article for article in edition.articles}
    for article in tree.iter("article"):
        header = _opener_header(article)
        declared = by_id.get(article.get("data-article-id") or "")
        if declared is None:
            raise ValidationError(
                f"No edition article matches opener {article.get('data-article-id')!r}"
            )
        if _is_illustrated_article(declared):
            height, minimum = _ILLUSTRATED_OPENER_TITLE_BOX
            size, lines = _fitted_display(
                str(declared.title),
                _ILLUSTRATED_OPENER_RAIL_POINTS,
                height,
                maximum=_ILLUSTRATED_OPENER_TITLE_MAX,
                minimum=minimum,
                maximum_lines=_ILLUSTRATED_OPENER_TITLE_MAX_LINES,
                leading_ratio=_OPENER_TITLE_LEADING_RATIO,
            )
            natural_height = _illustrated_opener_height(
                header,
                title_size=size,
                title_lines=len(lines),
                density=_ILLUSTRATED_OPENER_STANDARD,
            )
            if (
                natural_height + _ILLUSTRATED_OPENER_PANGO_RESERVE_POINTS
                > _ILLUSTRATED_OPENER_PAGE_HEIGHT_POINTS
            ):
                size, lines = _fitted_display(
                    str(declared.title),
                    _ILLUSTRATED_OPENER_RAIL_POINTS,
                    height,
                    maximum=_ILLUSTRATED_OPENER_COMPACT_TITLE_MAX,
                    minimum=minimum,
                    maximum_lines=_ILLUSTRATED_OPENER_TITLE_MAX_LINES,
                    leading_ratio=_OPENER_TITLE_LEADING_RATIO,
                )
                compact_height = _illustrated_opener_height(
                    header,
                    title_size=size,
                    title_lines=len(lines),
                    density=_ILLUSTRATED_OPENER_COMPACT,
                )

                if (
                    compact_height + _ILLUSTRATED_OPENER_PANGO_RESERVE_POINTS
                    > _ILLUSTRATED_OPENER_PAGE_HEIGHT_POINTS
                ):
                    _split_standfirst_overflow(article, header, declared)
                header.set("data-opener-density", "compact")
            _set_illustrated_opener_title(header, size)

            header.set("data-title-lines", str(len(lines)))
            continue
        has_figure = _opener_figure(article) is not None
        height, minimum = _ARTICLE_TITLE_BOX
        size, lines = _fitted_display(
            str(declared.title),
            _CODE_MEASURE_POINTS,
            height,
            maximum=_ARTICLE_TITLE_MAX_WITH_FIGURE if has_figure else _ARTICLE_TITLE_MAX,
            minimum=minimum,
            maximum_lines=_OPENER_TITLE_MAX_LINES,
            leading_ratio=_OPENER_TITLE_LEADING_RATIO,
        )
        _set_opener_title(header, size)
        if has_figure:
            title_field = _OPENER_FIGURE_FIELD_BASE + _opener_title_flow(size, len(lines))
            field = title_field
            floor = _opener_code_field_floor(declared, size, len(lines))
            if floor > title_field:
                figure = _opener_figure(article)
                for image in () if figure is None else figure.iter("img"):
                    style = (image.get("style") or "").strip().rstrip(";")
                    image.set(
                        "style",
                        f"{style + '; ' if style else ''}max-height: "
                        f"{_OPENER_FIGURE_MAX_IMAGE_HEIGHT - (floor - title_field):.4f}pt",
                    )
                field = floor
            header.set("style", f"height: {field:.4f}pt")

            header.set("data-title-field", f"{title_field:.4f}")
        else:
            header.set("style", f"height: {_opener_prose_field(declared, size, len(lines)):.4f}pt")
            header.set(
                "data-title-field",
                f"{_OPENER_FIGURE_FIELD_BASE + _opener_title_flow(size, len(lines)):.4f}",
            )
    sections = {
        f"section-{index}": (
            str(section.title),
            _SECTION_TITLE_BOX,
            _SECTION_TITLE_MAX,
            _SECTION_FIELD_BASE,
        )
        for index, section in enumerate(getattr(edition, "sections", ()))
    }
    if edition.editorial is not None:
        sections["editorial"] = (
            str(edition.editorial.title),
            _EDITORIAL_TITLE_BOX,
            _EDITORIAL_TITLE_MAX,
            _EDITORIAL_FIELD_BASE,
        )
    for section in tree.iter("section"):
        opener = sections.get(section.get("id") or "")
        if opener is None:
            continue
        title, (height, minimum), maximum, base = opener
        size, lines = _fitted_display(
            title,
            _LIVE_WIDTH_POINTS,
            height,
            maximum=maximum,
            minimum=minimum,
            maximum_lines=_OPENER_TITLE_MAX_LINES,
            leading_ratio=_OPENER_TITLE_LEADING_RATIO,
        )
        header = _opener_header(section)
        _set_opener_title(header, size)
        header.set("style", f"height: {base + _opener_title_flow(size, len(lines)):.4f}pt")


def _opener_title_flow(size: float, lines: int) -> float:
    return size * (1 + _OPENER_TITLE_LEADING_RATIO * lines)


def _opener_code_field_floor(article: Any, size: float, lines: int) -> float:
    code = _opener_credit_code(article)
    if code is None:
        return 0.0
    return _opener_symbol_bottom(code, size, lines) + _OPENER_BYLINE_PAD_POINTS


def _opener_credit_code(article: Any) -> SourceCode | None:
    url = str(getattr(article, "source_url", "") or "").strip()
    if not url:
        return None
    return _fitted_source_code(str(article.id), url, _CODE_OPENER_SIDE_POINTS)


def _opener_byline_baseline(size: float, lines: int) -> float:
    return (
        _OPENER_TITLE_TOP_POINTS + _opener_title_flow(size, lines) + _OPENER_TITLE_TO_CREDIT_POINTS
    )


def _opener_symbol_bottom(code: SourceCode, size: float, lines: int) -> float:
    return (
        _opener_byline_baseline(size, lines)
        - _BYLINE_SIZE_POINTS * _INTER_CAP_RATIO
        + code.side
        - 2 * code.quiet
    )


def _opener_prose_field(article: Any, size: float, lines: int) -> float:
    baseline = _opener_byline_baseline(size, lines)
    ink_foot = baseline
    code = _opener_credit_code(article)
    column = _CODE_MEASURE_POINTS
    if code is not None:
        ink_foot = max(ink_foot, _opener_symbol_bottom(code, size, lines))
        column = _CODE_MEASURE_POINTS - _credit_column_inset(code)
    note = str(getattr(article, "author_note", "") or "").strip()
    if note:
        note_lines = len(_wrap(note, "sans-medium", _NOTE_SIZE_POINTS, column))
        ink_foot = max(
            ink_foot,
            baseline
            + _NOTE_BASELINE_DROP_POINTS
            + (note_lines - 1) * _NOTE_LEADING_POINTS
            + _NOTE_DESCENT_POINTS,
        )
    return ink_foot + _OPENER_STANDFIRST_GAP_POINTS


def _band_clearance_height(article: Element) -> float:
    layouts = (article.get("data-figure-layouts") or "").split()
    leading = (
        _PLATE_ARTICLE_READING_LEADING
        if any(layout.startswith("landscape_plate") for layout in layouts)
        else _READING_LEADING
    )
    return _BAND_CLEARANCE_LINES * leading + _FRAME_BOTTOM_RELIEF_POINTS


def _install_flow_clearances(tree: Element) -> None:
    for piece in (*tree.iter("article"), *tree.iter("section")):
        band = _band_clearance_height(piece)
        rebuilt: list[Element] = []
        children = list(piece)
        for index, child in enumerate(children):
            rebuilt.append(child)
            following = children[index + 1] if index + 1 < len(children) else None
            if child.tag == "figure" and child.get("data-figure-id"):
                rebuilt.append(_clearance("band-clearance", band))
            elif child.tag in _PLATE_ANCHOR_TAGS and (
                following is None or following.tag != "figure"
            ):
                rebuilt.append(_clearance("heading-clearance", _HEADING_CLEARANCE_POINTS))
        piece[:] = rebuilt


def _clearance(name: str, height: float) -> Element:
    return Element(
        "div",
        {"class": name, "style": f"height: {height:.4f}pt; margin-bottom: {-height:.4f}pt"},
    )


def _evidence_bands(article: Element) -> Iterable[tuple[Element, Element | None, Element | None]]:
    children = list(article)
    for index, child in enumerate(children):
        if child.tag != "figure" or child.get("data-layout") not in _EVIDENCE_BAND_LAYOUTS:
            continue
        heading = (
            children[index - 1] if index and children[index - 1].tag in _PLATE_ANCHOR_TAGS else None
        )
        bridge = children[index - 2] if heading is not None and index >= 2 else None
        yield child, heading, bridge


def _mark_band_bridges(tree: Element) -> None:
    for article in tree.iter("article"):
        for figure, heading, bridge in _evidence_bands(article):
            if heading is not None:
                heading.set("data-band-anchor", figure.get("data-figure-id") or "")
            if bridge is None:
                continue
            bridge.set("data-band-bridge", figure.get("data-figure-id") or "")


def _apply_band_offsets(tree: Element, offsets: Mapping[str, float]) -> None:
    for figure in tree.iter("figure"):
        offset = offsets.get(figure.get("data-figure-id") or "")
        if offset is None:
            continue
        style = (figure.get("style") or "").strip().rstrip(";")
        figure.set("style", f"{style + '; ' if style else ''}left: {offset:.4f}pt")


def _apply_adaptive_images(tree: Element, heights: Mapping[str, float]) -> None:
    for figure in tree.iter("figure"):
        height = heights.get(figure.get("data-figure-id") or "")
        if height is None:
            continue
        for image in figure.iter("img"):
            style = (image.get("style") or "").strip().rstrip(";")
            image.set("style", f"{style + '; ' if style else ''}max-height: {height:.4f}pt")


def _apply_figure_rules(tree: Element, rules: Mapping[str, MeasuredRule]) -> None:
    bleed = _FIGURE_RULE_BLEED_POINTS
    for figure in tree.iter("figure"):
        rule = rules.get(figure.get("data-figure-id") or "")
        if rule is None:
            continue
        left, top, width, height = rule.left, rule.top, rule.width, rule.height
        image = SubElement(figure, "img")
        image.set("class", "figure-rule")
        image.set("alt", "")
        image.set("aria-hidden", "true")
        image.set("src", _figure_rule_source(width, height))
        image.set(
            "style",
            f"left: {left - bleed:.4f}pt; top: {top - bleed:.4f}pt; "
            f"width: {width + 2 * bleed:.4f}pt; height: {height + 2 * bleed:.4f}pt",
        )


def _figure_rule_source(width: float, height: float) -> str:
    bleed = _FIGURE_RULE_BLEED_POINTS
    outer_width = width + 2 * bleed
    outer_height = height + 2 * bleed
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' "
        f"width='{outer_width:.4f}pt' height='{outer_height:.4f}pt' "
        f"viewBox='0 0 {outer_width:.4f} {outer_height:.4f}'>"
        f"<rect x='{bleed:.4f}' y='{bleed:.4f}' "
        f"width='{width:.4f}' height='{height:.4f}' fill='none' "
        f"stroke='{_FIGURE_RULE_INK}' stroke-width='{_FIGURE_RULE_WIDTH_POINTS}'/></svg>"
    )
    return "data:image/svg+xml," + quote(svg, safe="")


def _measured_figure_rules(document: Any) -> dict[str, MeasuredRule]:
    rules: dict[str, MeasuredRule] = {}
    for page_number, page in enumerate(document.pages, start=1):
        for figure, image in _walk_figure_images(page._page_box):
            if _is_figure_rule(image):
                continue
            figure_id = str(figure.element.get("data-figure-id"))
            measured = MeasuredRule(page_number, *_box_inside(figure, image))
            if rules.setdefault(figure_id, measured) != measured:
                raise ValidationError(
                    f"WeasyPrint laid out curated figure {figure_id} in two different "
                    f"boxes, {rules[figure_id]} and {measured}; a figure frame needs one."
                )
    return rules


def _validate_figure_rules(document: Any, rules: Mapping[str, MeasuredRule]) -> None:
    bleed = _FIGURE_RULE_BLEED_POINTS
    painted: dict[tuple[str, int], tuple[float, float, float, float]] = {}
    misplaced: list[str] = []
    for page_number, page in enumerate(document.pages, start=1):
        for figure, image in _walk_figure_images(page._page_box):
            if not _is_figure_rule(image):
                continue
            key = (str(figure.element.get("data-figure-id")), page_number)
            box = _box_inside(figure, image)
            if key in painted:
                misplaced.append(f"{key[0]}: a second frame on page {page_number} at {box}")
            painted[key] = box
    for figure_id, rule in rules.items():
        expected = (
            rule.left - bleed,
            rule.top - bleed,
            rule.width + 2 * bleed,
            rule.height + 2 * bleed,
        )
        found = painted.pop((figure_id, rule.page), None)
        if found is None or any(abs(a - b) > 1e-3 for a, b in zip(found, expected)):
            misplaced.append(f"{figure_id}: expected {expected} on page {rule.page}, found {found}")
    misplaced.extend(
        f"{figure_id}: unexpected frame on page {page} at {box}"
        for (figure_id, page), box in painted.items()
    )
    if misplaced:
        raise ValidationError(
            "WeasyPrint did not paint the figure frames on their image boxes: "
            + "; ".join(sorted(misplaced))
        )


def _box_inside(outer: Any, inner: Any) -> tuple[float, float, float, float]:
    return (
        round(
            (float(inner.content_box_x()) - float(outer.padding_box_x())) * _POINTS_PER_CSS_PIXEL, 4
        ),
        round(
            (float(inner.content_box_y()) - float(outer.padding_box_y())) * _POINTS_PER_CSS_PIXEL, 4
        ),
        round(float(inner.width) * _POINTS_PER_CSS_PIXEL, 4),
        round(float(inner.height) * _POINTS_PER_CSS_PIXEL, 4),
    )


def _is_figure_rule(box: Any) -> bool:
    element = getattr(box, "element", None)
    return element is not None and "figure-rule" in _element_classes(element)


def _walk_figure_images(box: Any, figure: Any = None) -> Iterable[tuple[Any, Any]]:
    if figure is None and getattr(box, "element_tag", None) == "figure":
        element = getattr(box, "element", None)
        if element is not None and element.get("data-figure-id"):
            figure = box
    if figure is not None and getattr(box, "element_tag", None) == "img":
        yield figure, box
    for child in getattr(box, "children", ()):
        yield from _walk_figure_images(child, figure)


def _figure_block_geometry(
    figure: Any, width: float, max_image_height: float
) -> tuple[float, float]:
    try:
        from PIL import Image

        with Image.open(figure.path) as image:
            pixel_width, pixel_height = int(image.width), int(image.height)
    except (OSError, ValueError) as exc:
        raise ValidationError(f"Cannot decode curated figure {figure.path}: {exc}") from exc
    scale = min(width / pixel_width, max_image_height / pixel_height)
    image_height = pixel_height * scale
    text_lines = len(_wrap(str(figure.caption), "serif", _CAPTION_SIZE, width)) + len(
        _wrap(str(figure.credit), "sans-medium", _CAPTION_SIZE, width)
    )
    total = (
        _FIGURE_LABEL_ZONE_POINTS
        + image_height
        + 6.3
        + text_lines * _FIGURE_TEXT_LEADING
        + _FIGURE_GAP
    )
    return image_height, total


def _band_heading_height(tag: str, text: str) -> float:
    face, size, leading, after = _BAND_HEADING_MEASURE[tag]
    measured = text.upper() if tag == "h3" else text
    return len(_wrap(measured, face, size, _LIVE_WIDTH_POINTS)) * leading + after


def _measured_adaptive_images(document: Any, edition: Edition) -> tuple[tuple[str, float], ...]:
    figures = {
        figure.id: figure
        for article in edition.articles
        for figure in getattr(article, "figures", ())
    }

    anchors = {
        figure.id: educate_reader_quotes(str(figure.anchor))
        for article in edition.articles
        for figure in getattr(article, "figures", ())
    }
    shrunk: list[tuple[str, float]] = []
    for figure_id, bridge_top in _band_bridge_tops(document).items():
        figure = figures.get(figure_id)
        if figure is None or str(figure.layout) != "adaptive_band":
            continue
        heading_height = _band_heading_height(
            _anchor_heading_tag(document, anchors.get(figure_id, "")),
            anchors.get(figure_id, ""),
        )
        image_height, total = _figure_block_geometry(
            figure, _LIVE_WIDTH_POINTS, _FIGURE_BAND_MAX_IMAGE_HEIGHT
        )
        if bridge_top - heading_height - total >= _FRAME_BOTTOM_POINTS:
            continue
        fixed = total - image_height
        available = bridge_top - heading_height - _FRAME_BOTTOM_POINTS - fixed
        if available < _ADAPTIVE_FIGURE_MIN_IMAGE_HEIGHT:
            continue
        limit = min(_FIGURE_BAND_MAX_IMAGE_HEIGHT, available)
        shrunk.append((figure_id, _figure_block_geometry(figure, _LIVE_WIDTH_POINTS, limit)[0]))
    return tuple(sorted(shrunk))


def _anchor_heading_tag(document: Any, anchor: str) -> str:
    folded = anchor.strip().casefold()
    for page in document.pages:
        for box in _walk_boxes(page._page_box):
            tag = getattr(box, "element_tag", None)
            if (
                tag in {"h2", "h3"}
                and _element_text(getattr(box, "element", None)).strip().casefold() == folded
            ):
                return tag
    return "h2"


def _element_text(element: Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext())


def _band_bridges(document: Any) -> dict[str, tuple[int, float]]:
    bottoms: dict[str, tuple[int, float]] = {}
    for page_number, page in enumerate(document.pages, start=1):
        for box in _walk_boxes(page._page_box):
            element = getattr(box, "element", None)
            if element is None:
                continue
            figure_id = getattr(element, "attrib", {}).get("data-band-bridge")
            if not figure_id or not hasattr(box, "margin_height"):
                continue
            bottom = (float(box.position_y) + float(box.margin_height())) * _POINTS_PER_CSS_PIXEL
            seen = bottoms.get(figure_id)
            if seen is None or page_number > seen[0]:
                bottoms[figure_id] = (page_number, bottom)
            elif page_number == seen[0]:
                bottoms[figure_id] = (page_number, max(seen[1], bottom))
    frame_top = _PAGE_HEIGHT_POINTS - 52.0
    return {
        figure_id: (
            page,
            min(_reader_y_points(bottom, _FIRST_BASELINE_INSET_POINTS), frame_top),
        )
        for figure_id, (page, bottom) in bottoms.items()
    }


def _band_bridge_tops(document: Any) -> dict[str, float]:
    return {figure_id: top for figure_id, (_page, top) in _band_bridges(document).items()}


def _measured_midpage_anchors(document: Any) -> tuple[str, ...]:
    anchor_pages: dict[str, int] = {}
    for page_number, page in enumerate(document.pages, start=1):
        for box in _walk_boxes(page._page_box):
            element = getattr(box, "element", None)
            if element is None:
                continue
            figure_id = getattr(element, "attrib", {}).get("data-band-anchor")
            if figure_id and getattr(box, "element_tag", None) in {"h2", "h3"}:
                anchor_pages.setdefault(figure_id, page_number)
    bridges = _band_bridges(document)
    return tuple(
        sorted(
            figure_id
            for figure_id, page in anchor_pages.items()
            if figure_id in bridges and bridges[figure_id][0] == page
        )
    )


def _apply_anchor_clearances(tree: Element, midpage: Iterable[str]) -> None:
    wanted = set(midpage)
    if not wanted:
        return
    for article in tree.iter("article"):
        for figure, heading, _bridge in _evidence_bands(article):
            if heading is None or (figure.get("data-figure-id") or "") not in wanted:
                continue
            classes = (heading.get("class") or "").split()
            heading.set("class", " ".join([*classes, "band-anchor-midpage"]))


def _live_area_left(page_number: int) -> float:
    return _INNER_MARGIN_POINTS if page_number % 2 else _OUTER_MARGIN_POINTS


def _measured_band_offsets(document: Any) -> tuple[tuple[str, float], ...]:
    figure_pages = _figure_pages(document)
    offsets: list[tuple[str, float]] = []
    for figure_id, (bridge_page, _top) in _band_bridges(document).items():
        landed = figure_pages.get(figure_id)
        if landed is None or landed == bridge_page:
            continue
        offsets.append((figure_id, _live_area_left(bridge_page) - _live_area_left(landed)))
    return tuple(sorted(offsets))


def _figure_pages(document: Any) -> dict[str, int]:
    pages: dict[str, int] = {}
    for page_number, page in enumerate(document.pages, start=1):
        for box in _walk_boxes(page._page_box):
            element = getattr(box, "element", None)
            figure_id = (
                getattr(element, "attrib", {}).get("data-figure-id")
                if element is not None
                else None
            )
            if figure_id and getattr(box, "element_tag", None) == "figure":
                pages.setdefault(figure_id, page_number)
    return pages


def _place_closing_plates(tree: Element, count: int) -> None:
    parents = {child: parent for parent in tree.iter() for child in parent}
    plates = [
        element for element in tree.iter("figure") if "closing-plate" in _element_classes(element)
    ]
    if count > len(plates):
        raise ValidationError(
            f"Edition needs {count} closing plates to close the signature but configures "
            f"{len(plates)}; add {count - len(plates)} more to closing_plates "
            "(mag art <edition> --only closing, then pick in art/showcase.html)"
        )
    for plate in plates:
        parents[plate].remove(plate)
    main = parents[plates[0]]
    articles = [child for child in main if child.tag == "article"]
    slots = [round(j * len(articles) / count) for j in range(1, count + 1)]
    for plate, slot in zip(plates[:count], slots):
        after = articles[slot - 1]
        main.insert(list(main).index(after) + 1, plate)


def _apply_print_contrast(tree: Element) -> None:
    import base64

    from .image_contrast import prepare_print_image

    for figure in tree.iter("figure"):
        figure_id = figure.get("data-figure-id")
        if not figure_id and "article-tail" not in _element_classes(figure):
            continue

        subject = f"curated figure {figure_id}" if figure_id else "article tail art"
        for image in figure.iter("img"):
            source = image.get("src")
            if not source or source.startswith("data:"):
                continue
            path = Path(_path_from_uri(source))
            try:
                prepared = prepare_print_image(path)
            except Exception as exc:
                raise ValidationError(f"Cannot decode {subject} {path}: {exc}") from exc
            if not prepared.adjusted:
                continue
            payload = base64.b64encode(prepared.image.getvalue()).decode("ascii")
            image.set("data-print-source", source)
            image.set("src", f"data:image/png;base64,{payload}")


def _path_from_uri(source: str) -> str:
    from urllib.parse import unquote, urlparse

    parsed = urlparse(source)
    return unquote(parsed.path) if parsed.scheme == "file" else source


def _apply_source_codes(tree: Element, codes: Mapping[str, SourceCode]) -> None:
    for article in tree.iter("article"):
        code = codes.get(article.get("data-article-id") or "")
        if code is None:
            continue
        header = _opener_header(article)
        illustrated = _is_illustrated_header(header)
        owner = header
        if illustrated:
            owner = next(
                (
                    link
                    for meta in header.iter()
                    if "opener-meta" in _element_classes(meta)
                    for link in meta.iter("a")
                    if "source-link" in _element_classes(link)
                ),
                None,
            )
            if owner is None:
                raise ValidationError(
                    f"Article {article.get('data-article-id')}'s illustrated opener "
                    "has no source link inside its metadata grid"
                )

            owner.text = None
        image = SubElement(owner, "img")
        image.set("class", "source-code")
        image.set("alt", "")
        image.set("aria-hidden", "true")
        image.set("data-source-code", code.slot)
        image.set("src", _source_code_source(code))
        if illustrated:
            image.set(
                "style",
                f"width: {code.side:.4f}pt; height: {code.side:.4f}pt",
            )
        else:
            image.set(
                "style",
                f"left: {code.left:.4f}pt; top: {code.top:.4f}pt; "
                f"width: {code.side:.4f}pt; height: {code.side:.4f}pt",
            )
            _fit_credit_measure(article, header, code)


def _credit_column_inset(code: SourceCode) -> float:

    return code.side - 2 * code.quiet + _CODE_CREDIT_GAP_POINTS


def _fit_credit_measure(article: Element, header: Element, code: SourceCode) -> None:
    column = _CODE_MEASURE_POINTS - _credit_column_inset(code)
    inset = f"margin-left: {_credit_column_inset(code):.4f}pt"
    for note in header.iter("p"):
        if "author-note" not in _element_classes(note):
            continue
        note.set("style", f"{inset}; width: {column:.4f}pt")
    for byline in header.iter("p"):
        if "byline" not in _element_classes(byline):
            continue
        byline.set("style", inset)
        text = "".join(byline.itertext()).strip().upper()
        width = _string_width(text, "sans-semibold", _BYLINE_SIZE_POINTS)
        scale = min(1.0, column / width) if width else 1.0
        if scale < _BYLINE_MIN_HORIZONTAL_SCALE:
            raise ValidationError(
                f"Article {article.get('data-article-id')}'s byline {text!r} reaches "
                f"past the {column:.2f}pt credit column beside its own source code "
                "and would require excessive horizontal compression; shorten the "
                "captured byline or redesign the credit row."
            )
        if scale < 1.0:
            tracking = (column - width) / max(1, len(text) - 1)
            byline.set(
                "style",
                f"{inset}; letter-spacing: {tracking:.6f}pt; white-space: nowrap",
            )


def _fitted_source_code(article_id: str, url: str, room: float) -> SourceCode | None:
    import segno

    payload = source_code_payload(url)
    best: SourceCode | None = None
    for level in _CODE_ERROR_LEVELS:
        symbol = segno.make(payload, error=level, micro=False)
        modules = int(symbol.symbol_size(border=_CODE_QUIET_MODULES)[0])
        module = room / modules
        if module < _CODE_MIN_MODULE_POINTS:
            continue
        if best is None or module > best.module + _MODULE_EPSILON:
            best = SourceCode(article_id, "opener", level, modules, module, payload)
    return best


def _source_code_matrix(code: SourceCode) -> list[list[bool]]:
    import segno

    symbol = segno.make(code.url, error=code.error, micro=False)
    return [[bool(cell) for cell in row] for row in symbol.matrix]


def _source_code_source(code: SourceCode) -> str:
    matrix = _source_code_matrix(code)
    size = len(matrix)
    unit = code.module
    side = code.side
    runs: list[str] = []
    for row, cells in enumerate(matrix):
        column = 0
        while column < size:
            if not cells[column]:
                column += 1
                continue
            end = column
            while end < size and cells[end]:
                end += 1
            x = (_CODE_QUIET_MODULES + column) * unit
            y = (_CODE_QUIET_MODULES + row) * unit
            width = (end - column) * unit
            runs.append(f"M{x:.4f} {y:.4f}h{width:.4f}v{unit:.4f}h{-width:.4f}z")
            column = end
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' "
        f"width='{side:.4f}pt' height='{side:.4f}pt' "
        f"viewBox='0 0 {side:.4f} {side:.4f}'>"
        f"<rect width='{side:.4f}' height='{side:.4f}' fill='{_CODE_PAPER}'/>"
        f"<path fill='{_CODE_INK}' d='{''.join(runs)}'/></svg>"
    )
    return "data:image/svg+xml," + quote(svg, safe="")


class PlacedCode(NamedTuple):
    page: int
    left: float
    bottom: float
    side: float


def _measured_source_code_boxes(document: Any) -> dict[str, PlacedCode]:
    placed: dict[str, PlacedCode] = {}
    for page_number, page in enumerate(document.pages, start=1):
        for article_id, box in _walk_source_code_images(page._page_box):
            width = float(box.width) * _POINTS_PER_CSS_PIXEL
            height = float(box.height) * _POINTS_PER_CSS_PIXEL
            found = PlacedCode(
                page_number,
                round(float(box.content_box_x()) * _POINTS_PER_CSS_PIXEL, 4),
                round(
                    _reader_y_points(float(box.content_box_y()) * _POINTS_PER_CSS_PIXEL, height),
                    4,
                ),
                round(width, 4),
            )
            if abs(width - height) > 1e-3:
                raise ValidationError(
                    f"Source code for article {article_id} was laid out "
                    f"{width:.4f}pt by {height:.4f}pt; a QR symbol is square."
                )
            if placed.setdefault(article_id, found) != found:
                raise ValidationError(
                    f"Source code for article {article_id} was laid out twice, at "
                    f"{placed[article_id]} and {found}; an article has one code."
                )
    return placed


def _walk_source_code_images(box: Any, article_id: str | None = None) -> Iterable[tuple[str, Any]]:
    element = getattr(box, "element", None)
    attributes = getattr(element, "attrib", {}) if element is not None else {}
    if getattr(box, "element_tag", None) == "article" and attributes.get("data-article-id"):
        article_id = str(attributes["data-article-id"])
    if (
        getattr(box, "element_tag", None) == "img"
        and element is not None
        and "source-code" in _element_classes(element)
        and article_id is not None
    ):
        yield article_id, box
    for child in getattr(box, "children", ()) or ():
        yield from _walk_source_code_images(child, article_id)


def _measured_plan(document: Any, edition: Edition, runt_binds: Iterable[str] = ()) -> ReaderPlan:
    content_pages = _content_page_count(document)
    end_marks: list[tuple[str, float]] = []
    tail_arts: list[tuple[str, float, float]] = []
    for article in edition.articles:
        flow_bottom = _article_flow_bottom(document, article.id)
        end_marks.append((article.id, _end_mark_offset(flow_bottom)))
        band = _measured_tail_art(article, flow_bottom)
        if band is not None:
            tail_arts.append((article.id, band.height, band.lift))
    return ReaderPlan(
        closing_plates=_signature_closing_plates(edition, content_pages),
        source_codes=_opener_source_codes(edition, document),
        tail_arts=tuple(tail_arts),
        adaptive_images=_measured_adaptive_images(document, edition),
        band_offsets=_measured_band_offsets(document),
        end_marks=tuple(end_marks),
        runt_binds=tuple(sorted({*runt_binds, *_measured_runt_binds(document)}, key=int)),
        midpage_band_anchors=_measured_midpage_anchors(document),
    )


def _opener_source_codes(edition: Edition, document: Any) -> tuple[SourceCode, ...]:
    baselines = _measured_byline_baselines(document)
    codes: list[SourceCode] = []
    for article in edition.articles:
        url = str(getattr(article, "source_url", "") or "").strip()
        if not url:
            continue
        illustrated = _is_illustrated_article(article)
        room = _ILLUSTRATED_OPENER_CODE_SIDE_POINTS if illustrated else _CODE_OPENER_SIDE_POINTS
        code = _fitted_source_code(str(article.id), url, room)
        if code is None:
            raise ValidationError(
                f"Article {article.id} cannot carry a scannable source code for {url}: "
                f"the opener square offers {room:.2f}pt, and even "
                f"at the lowest error correction the symbol's module would fall under "
                f"{_CODE_MIN_MODULE_POINTS * 25.4 / 72:.2f}mm. Shorten the canonical URL."
            )
        if illustrated:
            codes.append(code)
            continue
        baseline = baselines.get(str(article.id))
        if baseline is None:
            raise ValidationError(
                f"Article {article.id} carries a source code but its opener laid out "
                "no byline line; the code's credit-line anchor does not exist."
            )
        top = baseline - _BYLINE_SIZE_POINTS * _INTER_CAP_RATIO - code.quiet

        left = _CODE_MEASURE_LEFT_POINTS - code.quiet
        codes.append(replace(code, left=left, top=top))
    return tuple(sorted(codes))


def _measured_byline_baselines(document: Any) -> dict[str, float]:
    baselines: dict[str, float] = {}
    for page in document.pages:
        for article_id, byline in _walk_article_bylines(page._page_box):
            for line in _walk_boxes(byline):
                if type(line).__name__ != "LineBox":
                    continue
                baseline = (
                    float(line.position_y) + float(line.baseline)
                ) * _POINTS_PER_CSS_PIXEL - _PAGE_MARGIN_TOP_POINTS
                baselines.setdefault(article_id, baseline)
    return baselines


def _walk_article_bylines(box: Any, article_id: str | None = None) -> Iterable[tuple[str, Any]]:
    element = getattr(box, "element", None)
    attributes = getattr(element, "attrib", {}) if element is not None else {}
    if getattr(box, "element_tag", None) == "article" and attributes.get("data-article-id"):
        article_id = str(attributes["data-article-id"])
    if (
        element is not None
        and "byline" in _element_classes(element)
        and article_id is not None
        and type(box).__name__ == "BlockBox"
    ):
        yield article_id, box
    for child in getattr(box, "children", ()) or ():
        yield from _walk_article_bylines(child, article_id)


def _tail_art_room(flow_bottom: float) -> float:
    bottom = _FRAME_BOTTOM_POINTS + _TAIL_ORNAMENT_FOOT_INSET
    top = _end_mark_baseline(flow_bottom) - _TAIL_ORNAMENT_ENDMARK_CLEARANCE
    return top - bottom


def _tail_strip_pixels(tail_art: Any) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(tail_art) as image:
            return (int(image.width), int(image.height))
    except (OSError, ValueError) as exc:
        raise ValidationError(
            f"Article tail art needs a readable raster source: {tail_art}"
        ) from exc


def _tail_strip_height(pixels: tuple[int, int]) -> float:
    return min(
        _CODE_MEASURE_POINTS * pixels[1] / pixels[0],
        _TAIL_ORNAMENT_MAX_HEIGHT,
    )


def _measured_tail_art(article: Any, flow_bottom: float) -> TailBand | None:
    if getattr(article, "tail_art", None) is None:
        return None
    pixels = _tail_strip_pixels(article.tail_art)
    height = _tail_strip_height(pixels)
    if _tail_art_room(flow_bottom) < height:
        return None
    effective_ppi = min(
        pixels[0] / (_CODE_MEASURE_POINTS / 72),
        pixels[1] / (height / 72),
    )
    if effective_ppi < _MIN_FIGURE_PPI:
        raise ValidationError(
            f"Article tail art {article.tail_art} resolves to {effective_ppi:.1f} ppi; "
            f"the minimum is {_MIN_FIGURE_PPI:.0f} ppi"
        )
    return TailBand(height, 0.0)


_TAIL_ART_LEDGER_KEY = "_rendered_tail_arts"


def _tail_art_ledger(document: Any, edition: Edition, plan: ReaderPlan) -> list[dict[str, Any]]:
    bands = plan.tail_art_bands
    rows: list[dict[str, Any]] = []
    for article in edition.articles:
        declared = getattr(article, "tail_art", None) is not None
        row: dict[str, Any] = {
            "article": str(article.id),
            "declared": declared,
            "printed": False,
            "height_points": None,
            "drop_reason": None,
        }
        band = bands.get(article.id)
        if band is not None:
            row["printed"] = True
            row["height_points"] = round(band.height, 4)
        elif declared:
            room = _tail_art_room(_article_flow_bottom(document, article.id))
            strip = _tail_strip_height(_tail_strip_pixels(article.tail_art))
            row["drop_reason"] = (
                f"the article's last page leaves {room:.1f}pt of open tail room "
                f"below the end mark's {_TAIL_ORNAMENT_ENDMARK_CLEARANCE:.0f}pt "
                f"clearance; the strip prints at its one {strip:.1f}pt size or "
                f"not at all"
            )
        rows.append(row)
    return rows


_TAIL_BAND_CSS_FOOT_POINTS = _TAIL_ORNAMENT_FOOT_INSET - _FIRST_BASELINE_INSET_POINTS


def _apply_tail_arts(tree: Element, bands: Mapping[str, TailBand]) -> None:
    for article in tree.iter("article"):
        band = bands.get(article.get("data-article-id") or "")
        for figure in [child for child in article if "article-tail" in _element_classes(child)]:
            if band is None:
                article.remove(figure)
            else:
                figure.set(
                    "style",
                    f"height: {band.height:.4f}pt; "
                    f"bottom: {_TAIL_BAND_CSS_FOOT_POINTS + band.lift:.4f}pt",
                )


def _end_mark_baseline(flow_bottom: float) -> float:
    baseline = flow_bottom - _END_MARK_DROP_POINTS
    if baseline < _END_MARK_HARD_FLOOR_POINTS:
        raise ValidationError(
            f"An article's end mark would set {baseline:.2f}pt above the sheet's foot, "
            f"under the {_END_MARK_HARD_FLOOR_POINTS:.2f}pt floor that keeps it clear of "
            f"the folio's own line at {_FOLIO_BASELINE_POINTS:.1f}pt. Its last page "
            "over-runs by more than the mark can stand under; re-break the page rather "
            "than raising the mark into the type it closes."
        )
    return baseline


def _end_mark_offset(flow_bottom: float) -> float:
    baseline = _end_mark_baseline(flow_bottom)
    return flow_bottom + _END_MARK_PAINT_POINTS - _END_MARK_DROP_POINTS - baseline


def _apply_end_marks(tree: Element, offsets: Mapping[str, float]) -> None:
    for article in tree.iter("article"):
        offset = offsets.get(article.get("data-article-id") or "")
        if offset is None:
            continue
        for mark in article.iter("p"):
            if "end-mark" not in _element_classes(mark):
                continue
            style = (mark.get("style") or "").strip().rstrip(";")
            mark.set(
                "style",
                f"{style + '; ' if style else ''}transform: translateY({offset:.4f}pt)",
            )


def _content_page_count(document: Any) -> int:
    plates = sum(
        any(
            getattr(box, "element", None) is not None
            and "closing-plate" in _element_classes(box.element)
            for box in _walk_boxes(page._page_box)
        )
        for page in document.pages
    )
    return len(document.pages) - 2 - plates


def _signature_closing_plates(edition: Edition, content_pages: int) -> int:
    configured = edition.raw.get("format", {}).get("target_pages")
    minimum_total = content_pages + 2
    target = int(configured) if configured else ((minimum_total + 3) // 4) * 4
    target = max(target, minimum_total)
    target = ((target + 3) // 4) * 4
    count = target - 2 - content_pages
    if count < 4:
        target += 4
        count = target - 2 - content_pages
    return count


def _article_flow_bottom(document: Any, article_id: str) -> float:
    lowest = 0.0
    for page in document.pages:
        page_lowest = 0.0
        for box in _article_flow_boxes(page._page_box, article_id):
            if not hasattr(box, "margin_height"):
                continue
            bottom = (float(box.position_y) + float(box.margin_height())) * _POINTS_PER_CSS_PIXEL
            page_lowest = max(page_lowest, bottom)
        if page_lowest:
            lowest = page_lowest
    if not lowest:
        raise ValidationError(f"WeasyPrint placed no in-flow content for article {article_id}")
    return _PAGE_HEIGHT_POINTS - lowest - _FIRST_BASELINE_INSET_POINTS


def _article_flow_boxes(box: Any, article_id: str, *, inside: bool = False) -> Iterable[Any]:
    element = getattr(box, "element", None)
    if element is not None and _element_classes(element) & _OUT_OF_FLOW_CODA_CLASSES:
        return
    if not inside:
        attributes = getattr(element, "attrib", {}) if element is not None else {}
        inside = (
            getattr(box, "element_tag", None) == "article"
            and attributes.get("data-article-id") == article_id
        )
    if inside:
        yield box
    for child in getattr(box, "children", ()):
        yield from _article_flow_boxes(child, article_id, inside=inside)


def _validate_caps(edition: Edition) -> None:
    format_data = edition.raw.get("format", {})
    for key, expected in (("max_article_pages", _MAX_ARTICLE_PAGES),):
        value = format_data.get(key, expected)
        try:
            value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"format.{key} must be the integer {expected}") from exc
        if value != expected:
            raise ValidationError(
                f"format.{key} is a hard publication rule and must remain {expected}"
            )

    declared_editorial_page_cap(edition.raw, _MAX_EDITORIAL_PAGES)


def _note_box(
    box: Any,
    page_number: int,
    article_pages: dict[str, set[int]],
    article_opener_pages: dict[str, set[int]],
    editorial_pages: set[int],
    destinations: dict[str, int],
) -> None:
    element = box.element
    attributes = getattr(element, "attrib", {})
    tag = getattr(box, "element_tag", None)
    article_id = attributes.get("data-article-id")
    if article_id and tag == "article":
        article_pages.setdefault(article_id, set()).add(page_number)
    if article_id and tag == "header" and "article-opener" in _element_classes(element):
        article_opener_pages.setdefault(article_id, set()).add(page_number)
    if attributes.get("id") == "editorial" and tag == "section":
        editorial_pages.add(page_number)
    identifier = attributes.get("id")
    if identifier and identifier not in destinations:
        destinations[identifier] = page_number


def _toc_from(destinations: dict[str, int], article_pages: dict[str, set[int]]) -> dict[str, int]:
    toc: dict[str, int] = {}
    if "editorial" in destinations:
        toc["editorial"] = destinations["editorial"]
    for article_id in article_pages:
        destination = f"article-{article_id}"
        if destination in destinations:
            toc[article_id] = destinations[destination]
    for identifier, page_number in destinations.items():
        if identifier.startswith("section-"):
            toc[identifier] = page_number
    return toc


def _measure_layout(
    document: Any,
    assets: tuple[HtmlAsset, ...],
    design: str,
    plan: ReaderPlan | None = None,
) -> RenderLayout:
    article_pages: dict[str, set[int]] = {}
    article_opener_pages: dict[str, set[int]] = {}
    editorial_pages: set[int] = set()
    destinations: dict[str, int] = {}
    image_boxes: list[tuple[HtmlAsset, int, Any, Any]] = []
    assets_by_source: dict[str, list[HtmlAsset]] = {}

    placed_assets = tuple(
        asset
        for asset in assets
        if asset.role in {"figure", "article_opener", "article_tail", "closing_plate"}
        and _asset_is_placed(asset, plan)
    )
    for asset in placed_assets:
        assets_by_source.setdefault(asset.src, []).append(asset)
    source_occurrences: dict[str, int] = {}

    for page_number, page in enumerate(document.pages, start=1):
        for box, rotor in _walk_boxes_in_frame(page._page_box):
            element = getattr(box, "element", None)
            if element is None:
                continue
            _note_box(
                box, page_number, article_pages, article_opener_pages, editorial_pages, destinations
            )
            if getattr(box, "element_tag", None) == "img":
                attributes = getattr(element, "attrib", {})
                source = attributes.get("data-print-source") or attributes.get("src")
                candidates = assets_by_source.get(source, [])
                occurrence = source_occurrences.get(source or "", 0)
                if occurrence < len(candidates):
                    image_boxes.append((candidates[occurrence], page_number, box, rotor))
                    source_occurrences[source or ""] = occurrence + 1

    placements = tuple(
        _figure_placement(asset, page, box, rotor)
        for asset, page, box, rotor in image_boxes
        if asset.role == "figure"
    )
    missing = sorted(
        {asset.id for asset in placed_assets} - {asset.id for asset, _, _, _ in image_boxes}
    )
    if missing:
        raise ValidationError(
            "WeasyPrint did not place expected raster assets: " + ", ".join(missing)
        )
    return RenderLayout(
        toc=_toc_from(destinations, article_pages),
        article_pages={key: len(value) for key, value in article_pages.items()},
        editorial_pages=len(editorial_pages) if editorial_pages else None,
        design=design,
        cover_art_size_points=None,
        article_frame_usage={},
        article_terminal_balance={},
        figure_placements=placements,
        article_opener_fits={key: len(value) == 1 for key, value in article_opener_pages.items()},
    )


def _asset_is_placed(asset: HtmlAsset, plan: ReaderPlan | None) -> bool:
    if plan is None:
        return asset.role != "article_tail"
    if asset.role == "article_tail":
        return (asset.article_id or "") in plan.tail_art_heights
    if asset.role == "closing_plate":
        return int(str(asset.id).rsplit("-", 1)[-1]) <= plan.closing_plates
    return True


def _walk_boxes(box: Any) -> Iterable[Any]:
    yield box
    for child in getattr(box, "children", ()):
        yield from _walk_boxes(child)


def _walk_boxes_in_frame(box: Any, rotor: Any = None) -> Iterable[tuple[Any, Any]]:
    element = getattr(box, "element", None)
    if element is not None and "landscape-plate-rotor" in _element_classes(element):
        rotor = box
    yield box, rotor
    for child in getattr(box, "children", ()):
        yield from _walk_boxes_in_frame(child, rotor)


def _figure_placement(asset: HtmlAsset, page: int, box: Any, rotor: Any = None) -> FigurePlacement:
    try:
        from PIL import Image

        with Image.open(asset.path) as image:
            dimensions = (int(image.width), int(image.height))
    except (OSError, ValueError) as exc:
        raise ValidationError(
            f"Curated figure {asset.figure_id} needs a readable raster source for PPI preflight: {asset.path}"
        ) from exc
    box_width = float(box.width) * _POINTS_PER_CSS_PIXEL
    box_height = float(box.height) * _POINTS_PER_CSS_PIXEL

    box_x = float(box.content_box_x()) * _POINTS_PER_CSS_PIXEL
    box_y = float(box.content_box_y()) * _POINTS_PER_CSS_PIXEL
    if rotor is None:
        x, y, width, height = box_x, _reader_y_points(box_y, box_height), box_width, box_height
    else:
        x, y, width, height = _rotated_plate_box(box_x, box_y, box_width, box_height, rotor)
    if width <= 0 or height <= 0:
        raise ValidationError(f"Curated figure {asset.figure_id} has an empty WeasyPrint image box")

    ppi = min(dimensions[0] / (box_width / 72), dimensions[1] / (box_height / 72))

    if asset.role == "figure" and ppi < _MIN_FIGURE_PPI:
        raise ValidationError(
            f"Curated figure {asset.figure_id} resolves to {ppi:.1f} ppi at its Quiet "
            f"Standard placement; the minimum is {_MIN_FIGURE_PPI:.0f} ppi"
        )
    return FigurePlacement(
        figure_id=str(asset.figure_id or asset.id),
        article_id=str(asset.article_id or "closing-plate"),
        page=page,
        path=asset.path,
        pixel_dimensions=dimensions,
        box_points=tuple(round(value, 3) for value in (x, y, width, height)),
        effective_ppi=round(ppi, 1),
        caption=str(asset.caption or asset.alt_text),
        credit=str(asset.credit or ""),
    )


def _rotated_plate_box(
    box_x: float, box_y: float, box_width: float, box_height: float, rotor: Any
) -> tuple[float, float, float, float]:
    rotor_x = float(rotor.position_x) * _POINTS_PER_CSS_PIXEL
    rotor_y = float(rotor.position_y) * _POINTS_PER_CSS_PIXEL
    along = box_x - rotor_x
    across = box_y - rotor_y
    left = rotor_x + _PLATE_FRAME_ACROSS_POINTS - across - box_height
    top = rotor_y + _FIRST_BASELINE_INSET_POINTS + along
    return left, _reader_y_points(top, box_width), box_height, box_width


def _validate_layout_caps(edition: Edition, layout: RenderLayout) -> None:
    overlong = [
        f"{article_id} ({count} pages)"
        for article_id, count in layout.article_pages.items()
        if count > _MAX_ARTICLE_PAGES
    ]
    if overlong:
        raise ValidationError(
            "WeasyPrint article page cap exceeded (maximum 7): " + ", ".join(overlong)
        )

    short = [
        f"{article.id} ({layout.article_pages[article.id]} pages, "
        f"editorial minimum {article.minimum_reader_pages})"
        for article in edition.articles
        if article.id in layout.article_pages
        and layout.article_pages[article.id] < article.minimum_reader_pages
    ]
    if short:
        raise ValidationError("WeasyPrint article editorial minimum not met: " + ", ".join(short))
    editorial_cap = declared_editorial_page_cap(edition.raw, _MAX_EDITORIAL_PAGES)
    if layout.editorial_pages is not None and layout.editorial_pages > editorial_cap:
        raise ValidationError(
            f"WeasyPrint editorial page cap exceeded: {layout.editorial_pages} pages "
            f"(maximum {editorial_cap})"
        )


def _validate_cover_slots(document: Any) -> None:
    if len(document.pages) < 4:
        raise ValidationError("WeasyPrint reader must contain cover and inside-cover placeholders")

    named = []
    for page in document.pages:
        page_type = getattr(page._page_box, "page_type", None)
        named.append(getattr(page_type, "name", None))
    expected = ("outer-cover", "inside-cover", "inside-cover", "outer-cover")
    actual = (named[0], named[1], named[-2], named[-1])
    if actual != expected:
        raise ValidationError(
            "WeasyPrint cover placeholders lost their named-page geometry: "
            f"expected {expected!r}, got {actual!r}"
        )


def _validate_source_codes(
    pdf_bytes: bytes,
    edition: Edition,
    codes: Iterable[SourceCode],
    placed: Mapping[str, PlacedCode],
) -> None:
    wanted = {code.article_id: code for code in codes}
    if not wanted:
        return
    missing = sorted(set(wanted) - set(placed))
    if missing:
        raise ValidationError(
            f"WeasyPrint planned a source code for {', '.join(missing)} in edition "
            f"{edition.id} but laid out no square for it; the code would be absent "
            "from the printed page."
        )
    surplus = sorted(set(placed) - set(wanted))
    if surplus:
        raise ValidationError(
            f"WeasyPrint laid out a source code for {', '.join(surplus)} in edition "
            f"{edition.id}, which the plan does not carry."
        )
    failures: list[str] = []
    pages = sorted({placed[article_id].page for article_id in wanted})
    rasters = _rasterised_pages(pdf_bytes, pages)
    for article_id, code in sorted(wanted.items()):
        box = placed[article_id]
        decoded = _decoded_codes(rasters[box.page])
        match = next(
            (found for found in decoded if _code_box_matches(found[1], box)),
            None,
        )
        if match is None:
            failures.append(
                f"{article_id}: nothing decoded on the {box.side:.2f}pt square at "
                f"({box.left:.2f}, {box.bottom:.2f}) of page {box.page}; the page "
                f"yielded {[text for text, _ in decoded]}"
            )
            continue
        text, _corners = match
        if text != code.url:
            failures.append(
                f"{article_id}: page {box.page} decoded {text!r}, expected {code.url!r}"
            )
    if failures:
        raise ValidationError(
            "WeasyPrint printed a source code that does not read back off the page at "
            f"{_CODE_DECODE_DPI} ppi. An unscannable code is worse than none: "
            + "; ".join(failures[:5])
        )


def _code_box_matches(corners: tuple[tuple[float, float], ...], box: PlacedCode) -> bool:
    if len(corners) < 4:
        return False
    slack = _CODE_POSITION_TOLERANCE_POINTS
    xs = [x for x, _ in corners]
    ys = [y for _, y in corners]
    inside = (
        min(xs) >= box.left - slack
        and max(xs) <= box.left + box.side + slack
        and min(ys) >= box.bottom - slack
        and max(ys) <= box.bottom + box.side + slack
    )
    return inside and (max(xs) - min(xs)) >= box.side / 2


def _rasterised_pages(pdf_bytes: bytes, pages: Iterable[int]) -> dict[int, Any]:
    import shutil
    import subprocess
    import tempfile

    from PIL import Image

    executable = shutil.which("pdftoppm")
    if not executable:
        raise DependencyError(
            "Reading a printed source code back off the page requires Poppler's "
            "pdftoppm executable, the same one render criticism uses."
        )
    rasters: dict[int, Any] = {}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        reader = root / "reader.pdf"
        reader.write_bytes(pdf_bytes)
        for page in pages:
            prefix = root / f"page-{page}"
            completed = subprocess.run(
                [
                    executable,
                    "-png",
                    "-r",
                    str(_CODE_DECODE_DPI),
                    "-f",
                    str(page),
                    "-l",
                    str(page),
                    str(reader),
                    str(prefix),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            rendered = sorted(root.glob(f"page-{page}-*.png"))
            if completed.returncode or not rendered:
                detail = (
                    completed.stderr.strip() or completed.stdout.strip() or "no raster was produced"
                )
                raise DependencyError(
                    f"Could not rasterize reader page {page} to read its source code: {detail}"
                )
            with Image.open(rendered[0]) as image:
                rasters[page] = image.convert("L").copy()
    return rasters


def _decoded_codes(raster: Any) -> tuple[tuple[str, tuple[tuple[float, float], ...]], ...]:
    try:
        import zxingcpp
    except ImportError as exc:  # pragma: no cover - a declared dependency
        raise ValidationError(
            "Reading a printed source code back off the page requires zxing-cpp. "
            f"Run `uv sync --locked`. Original error: {exc}"
        ) from exc
    scale = 72 / _CODE_DECODE_DPI
    height = raster.height
    results = []
    for found in zxingcpp.read_barcodes(raster, formats=zxingcpp.BarcodeFormat.QRCode):
        position = found.position
        corners = tuple(
            (point.x * scale, (height - point.y) * scale)
            for point in (
                position.top_left,
                position.top_right,
                position.bottom_right,
                position.bottom_left,
            )
        )
        results.append((found.text, corners))
    return tuple(results)


def _validate_reader_measures(document: Any) -> None:
    overlong: list[str] = []
    for page_number, page in enumerate(document.pages, start=1):
        _collect_overlong_lines(page._page_box, None, page_number, overlong)
    if overlong:
        raise ValidationError(
            "WeasyPrint set a reader line wider than its own measure, which means a "
            "token with no break opportunity is overflowing the column: " + "; ".join(overlong[:5])
        )


def _collect_overlong_lines(
    box: Any, measure: float | None, page_number: int, overlong: list[str]
) -> None:
    if type(box).__name__ == "LineBox":
        width = float(box.width)
        if measure is not None and width > measure + _TOKEN_MEASURE_EPSILON:
            text = "".join(
                child.text for child in _walk_boxes(box) if type(child).__name__ == "TextBox"
            )
            overlong.append(
                f"page {page_number} sets {width * _POINTS_PER_CSS_PIXEL:.2f}pt into a "
                f"{measure * _POINTS_PER_CSS_PIXEL:.2f}pt measure: {text[:60]!r}"
            )
        return
    own = getattr(box, "width", None)
    if isinstance(own, (int, float)):
        measure = float(own)
    for child in getattr(box, "children", ()) or ():
        _collect_overlong_lines(child, measure, page_number, overlong)


def _validate_fitted_display(document: Any, edition: Edition) -> None:
    failures: list[str] = []
    for page_number, page in enumerate(document.pages, start=1):
        _collect_field_overflows(page._page_box, page_number, failures)
    if failures:
        raise ValidationError(
            "WeasyPrint set display type past the room the adapter fitted it into. "
            "Auto-fitting sums unkerned advances the way render.py does, and Pango's "
            "kerning does not only tighten, so a title can take a line the fit did not "
            "reserve. Shorten the title, or lower the fit range it is chosen from: "
            + "; ".join(failures[:5])
        )


def _collect_field_overflows(box: Any, page_number: int, failures: list[str]) -> None:
    for piece, header, title in _opener_title_boxes(box):
        element = getattr(header, "element", None)
        attributes = getattr(element, "attrib", {}) if element is not None else {}
        stated_lines = attributes.get("data-title-lines")
        if stated_lines is not None:
            fitted_lines = int(stated_lines)
            set_lines = _line_box_count(title)
            if set_lines <= fitted_lines:
                continue
            failures.append(
                f"opener {piece!r} title {_box_text(title)!r} was fitted at "
                f"{float(title.style['font_size']) * _POINTS_PER_CSS_PIXEL:.4g}pt "
                f"over {fitted_lines} line(s), but Pango set it on {set_lines} "
                f"on page {page_number}"
            )
            continue
        field = _opener_title_reservation(header)
        field_bottom = float(header.content_box_y()) * _POINTS_PER_CSS_PIXEL + field
        title_bottom = (
            float(title.position_y) + float(title.margin_height())
        ) * _POINTS_PER_CSS_PIXEL
        if title_bottom <= field_bottom + _FIELD_OVERFLOW_EPSILON:
            continue
        failures.append(
            f"opener {piece!r} title {_box_text(title)!r} was fitted at "
            f"{float(title.style['font_size']) * _POINTS_PER_CSS_PIXEL:.4g}pt into a "
            f"{field:.4f}pt title field, whose foot is {field_bottom:.4f}pt down "
            f"page {page_number}; Pango set it on {_line_box_count(title)} lines "
            f"reaching {title_bottom:.4f}pt, overflowing the field by "
            f"{title_bottom - field_bottom:.4f}pt"
        )


def _standfirst_keep_words(standfirst: Element, declared: Any) -> int:
    intro = " ".join("".join(standfirst.itertext()).split())
    budget = illustrated_opener_intro_budget(
        title=str(declared.title),
        byline=str(declared.author),
        author_note=str(declared.author_note or ""),
        sample=intro,
    )
    if budget is None or budget.lines < 1 or budget.fits(intro):
        return 0
    return sum(len(line.split()) for line in budget.wrapped(intro)[: budget.lines])


def _cut_words(text: str | None, remaining: int) -> tuple[str | None, str | None, int]:
    if text is None:
        return None, None, remaining
    parts = re.split(r"(\s+)", text)
    kept: list[str] = []
    for index, part in enumerate(parts):
        if part and not part.isspace():
            if remaining == 0:
                return "".join(kept).rstrip(), "".join(parts[index:]).lstrip(), 0
            remaining -= 1
        kept.append(part)
    return "".join(kept), None, remaining


def _move_children_after(
    standfirst: Element, remainder: Element, children: list[Element], remaining: int
) -> int | None:
    for index, child in enumerate(children):
        if remaining == 0:
            return index
        child_words = len("".join(child.itertext()).split())
        if child_words > remaining:
            return index
        remaining -= child_words
        kept, moved, remaining = _cut_words(child.tail, remaining)
        child.tail = kept
        if moved is not None:
            remainder.text = moved
            return index + 1
    return None


def _split_standfirst_overflow(article: Element, header: Element, declared: Any) -> None:
    standfirst = next(
        (el for el in header.iter("p") if "standfirst" in (el.get("class") or "").split()),
        None,
    )
    if standfirst is None:
        return
    remaining = _standfirst_keep_words(standfirst, declared)
    if remaining < 1:
        return

    remainder = Element("p")
    kept, moved, remaining = _cut_words(standfirst.text, remaining)
    standfirst.text = kept
    children = list(standfirst)
    if moved is not None:
        remainder.text = moved
        move_from: int | None = 0
    else:
        move_from = _move_children_after(standfirst, remainder, children, remaining)
    if move_from is not None:
        for child in children[move_from:]:
            standfirst.remove(child)
            remainder.append(child)
    if remainder.text is None and len(remainder) == 0:
        return
    article.insert(list(article).index(header) + 1, remainder)


def _illustrated_headers_by_page(document: Any) -> dict[int, dict[str, Any]]:
    headers: dict[int, dict[str, Any]] = {}
    for page_number, page in enumerate(document.pages, start=1):
        for box in _walk_boxes(page._page_box):
            element = getattr(box, "element", None)
            if (
                getattr(box, "element_tag", None) != "header"
                or type(box).__name__ != "BlockBox"
                or not _is_illustrated_header(box)
                or element is None
            ):
                continue
            entry = headers.setdefault(id(element), {"element": element, "pages": {}})
            entry["pages"].setdefault(page_number, []).append(box)
    return headers


def _chrome_fragmented(entry: dict[str, Any], pages: list[int]) -> bool:
    element = entry["element"]
    standfirst_ids = {
        id(descendant)
        for standfirst in element.iter()
        if "standfirst" in (standfirst.get("class") or "").split()
        for descendant in standfirst.iter()
    }
    fragmented = False
    for page_number in pages[1:]:
        for fragment in entry["pages"][page_number]:
            for box in _walk_boxes(fragment):
                boxed = getattr(box, "element", None)
                if boxed is None or boxed is element:
                    continue
                if id(boxed) not in standfirst_ids:
                    fragmented = True
    return fragmented


def _validate_illustrated_opener_integrity(document: Any) -> None:
    split = []
    for entry in _illustrated_headers_by_page(document).values():
        pages = sorted(entry["pages"])
        if len(pages) <= 1 or not _chrome_fragmented(entry, pages):
            continue
        title = next(
            ("".join(item.itertext()).strip() for item in entry["element"].iter("h1")),
            "untitled article",
        )
        split.append(f"{title!r} across pages {', '.join(str(page) for page in pages)}")
    if split:
        raise ValidationError(
            "An illustrated opener may only continue its first paragraph onto the "
            "next page; other header content fragmented: " + "; ".join(split)
        )


def _opener_title_reservation(header: Any) -> float:
    element = getattr(header, "element", None)
    attributes = getattr(element, "attrib", {}) if element is not None else {}
    stated = attributes.get("data-title-field")
    if stated is not None:
        return float(stated)
    return float(header.height) * _POINTS_PER_CSS_PIXEL


def _validate_opener_code_clearance(document: Any, codes: Mapping[str, SourceCode]) -> None:
    failures: list[str] = []
    for page_number, page in enumerate(document.pages, start=1):
        squares: dict[str, Any] = {}
        figures: dict[str, Any] = {}
        for article_id, kind, found in _walk_opener_code_furniture(page._page_box):
            (squares if kind == "code" else figures).setdefault(article_id, found)
        for article_id, square in sorted(squares.items()):
            figure = figures.get(article_id)
            code = codes.get(article_id)
            if figure is None or code is None:
                continue
            foot = (
                float(square.content_box_y()) + float(square.height)
            ) * _POINTS_PER_CSS_PIXEL - code.quiet
            head = float(figure.position_y) * _POINTS_PER_CSS_PIXEL
            if foot + _OPENER_BYLINE_PAD_POINTS <= head + _FIELD_OVERFLOW_EPSILON:
                continue
            failures.append(
                f"{article_id}: its source code's last dark row is {foot:.4f}pt down "
                f"page {page_number} and the opener figure's head is {head:.4f}pt, so "
                f"the square reaches {foot + _OPENER_BYLINE_PAD_POINTS - head:.4f}pt "
                "past the field the code's own depth was borrowed for"
            )
    if failures:
        raise ValidationError(
            "WeasyPrint laid a source code into the opener figure it stands over. "
            "The field an opener with a code reserves runs to the symbol's last dark "
            "row plus the credit's 12pt pad, and the figure's head is that field's "
            "foot; the square is placed from the byline the page laid out, so the two "
            "have to be checked against each other on the finished page: "
            + "; ".join(sorted(failures)[:5])
        )


def _validate_opener_credit_depth(document: Any) -> None:
    failures: list[str] = []
    for page_number, page in enumerate(document.pages, start=1):
        for piece, header, _title in _opener_title_boxes(page._page_box):
            if _is_illustrated_header(header):
                continue
            field_foot = (
                float(header.content_box_y()) + float(header.height)
            ) * _POINTS_PER_CSS_PIXEL
            for box in _walk_boxes(header):
                element = getattr(box, "element", None)
                if (
                    element is None
                    or "author-note" not in _element_classes(element)
                    or type(box).__name__ != "BlockBox"
                ):
                    continue
                note_foot = (
                    float(box.position_y) + float(box.margin_height())
                ) * _POINTS_PER_CSS_PIXEL
                clearance = field_foot - note_foot
                if clearance + _FIELD_OVERFLOW_EPSILON >= _OPENER_CREDIT_LINE_POINTS:
                    continue
                failures.append(
                    f"opener {piece!r} sets its author note down to {note_foot:.4f}pt "
                    f"on page {page_number}, {clearance:.4f}pt above its own field's "
                    f"foot at {field_foot:.4f}pt, under the credit's "
                    f"{_OPENER_CREDIT_LINE_POINTS:.0f}pt line"
                )
    if failures:
        raise ValidationError(
            "WeasyPrint set an opener's author note into the gap its field keeps "
            "for the standfirst. The field is stated from a predicted note depth "
            "and the note is measured type, so the finished page is asked; "
            "shorten the author note: " + "; ".join(sorted(failures)[:5])
        )


def _walk_opener_code_furniture(
    box: Any, article_id: str | None = None
) -> Iterable[tuple[str, str, Any]]:
    element = getattr(box, "element", None)
    attributes = getattr(element, "attrib", {}) if element is not None else {}
    if getattr(box, "element_tag", None) == "article" and attributes.get("data-article-id"):
        article_id = str(attributes["data-article-id"])
    if element is not None and article_id is not None:
        if getattr(box, "element_tag", None) == "img" and "source-code" in _element_classes(
            element
        ):
            yield article_id, "code", box
            return
        if (
            getattr(box, "element_tag", None) == "figure"
            and attributes.get("data-anchor") == "__opener__"
        ):
            yield article_id, "figure", box
            return
    for child in getattr(box, "children", ()) or ():
        yield from _walk_opener_code_furniture(child, article_id)


def _opener_title_boxes(box: Any, piece: str | None = None) -> Iterable[tuple[str, Any, Any]]:
    element = getattr(box, "element", None)
    attributes = getattr(element, "attrib", {}) if element is not None else {}
    tag = getattr(box, "element_tag", None)
    if tag in ("article", "section"):
        piece = attributes.get("data-article-id") or attributes.get("id") or piece
    if tag == "header" and type(box).__name__ == "BlockBox" and piece is not None:
        for inner in _walk_boxes(box):
            if getattr(inner, "element_tag", None) == "h1" and type(inner).__name__ == "BlockBox":
                yield piece, box, inner
        return
    for child in getattr(box, "children", ()) or ():
        yield from _opener_title_boxes(child, piece)


def _line_box_count(box: Any) -> int:
    return sum(1 for child in _walk_boxes(box) if type(child).__name__ == "LineBox")


def _box_text(box: Any) -> str:
    lines = (
        "".join(
            child.text for child in _walk_boxes(line) if type(child).__name__ == "TextBox"
        ).strip()
        for line in _walk_boxes(box)
        if type(line).__name__ == "LineBox"
    )
    return " ".join(line for line in lines if line)


def _validate_contents_page(document: Any) -> None:
    if len(document.pages) < 3:
        raise ValidationError("WeasyPrint reader has no logical contents page")
    for box in _walk_boxes(document.pages[2]._page_box):
        element = getattr(box, "element", None)
        if (
            element is not None
            and getattr(element, "attrib", {}).get("data-edition-navigation") == "contents"
        ):
            return
    raise ValidationError("WeasyPrint contents must begin on logical reader page 3")
