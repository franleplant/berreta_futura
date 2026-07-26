"""Experimental, isolated A5 reader-PDF adapter backed by WeasyPrint.

This module deliberately does not participate in the compiler or CLI.  Its
single public interface turns the renderer-neutral semantic HTML edition into
an A5 reading-order PDF whose first/last pages are replace-only cover slots.
The existing cover compiler and A4 booklet imposition remain authoritative.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from html import unescape
from importlib import resources
import os
from pathlib import Path
import platform
import re
from typing import Any, NamedTuple
from urllib.parse import quote
from xml.etree.ElementTree import Element, SubElement

from .errors import ValidationError
from .html_edition import HtmlAsset, render_html_edition
from .manifest import Edition
from .reader_text import fold_reader_characters
from .render import FigurePlacement, RenderLayout


WEASYPRINT_DESIGN = "WeasyPrint / A5 fold proof"

SHAPING_SCAFFOLDS: tuple[str, ...] = (
    "font-kerning: none",
    "font-variant-ligatures: none",
    ".reader-token { white-space: nowrap } with _suppress_intra_token_breaks",
)
"""What this renderer gives up to line-break identically to ``render.render_a5``.

Pango kerns and ligates by default and will break inside a hyphenated token;
ReportLab does none of those things.  These three measures hold Pango down to
that behaviour, which is what makes the two renderers interchangeable.  They are
an equivalence scaffold, not a design decision, they come out together, and
until they do this renderer is deliberately setting type worse than it can --
see "Re-enable shaping and re-baseline" in ``docs/RENDERER_MIGRATION.md``.  A
build records this tuple in its manifest so the state is visible in the artifact
rather than only in a document.
"""

_CSS_PIXELS_PER_POINT = 96 / 72
_POINTS_PER_CSS_PIXEL = 72 / 96
_MAX_ARTICLE_PAGES = 7
_MAX_EDITORIAL_PAGES = 2

_PAGE_HEIGHT_POINTS = 595.2756
"""A5 trim height; the reader's own vertical datum, as in ``render.A5``."""

# The reader's text frame, from ``render.py``: TEXT_TOP_INSET 52 to bottom 45.
_FRAME_BOTTOM_POINTS = 45.0
# ``@page``'s margin-top is derived from the *first baseline*, not the frame top,
# so a page's CSS content box starts this far above ReportLab's frame top.  Every
# conversion between a measured CSS flow position and a ReportLab ``self.y``
# carries the same constant; see the stylesheet's own note on 41.9954pt.
#
# This is *not* the typographic datum, and the two are easy to conflate.  The
# datum -- half-leading plus ascent for 10pt Source Serif SmText on 13pt leading,
# which is what actually decides where the first baseline lands -- measures
# 10.0050, not 10.0046: on en reader p17 and p21 the first 10pt baseline is
# 543.270186 against a margin-top of 42.0004, and 553.2801906 - 543.275186 =
# 10.0050046 once the stylesheet's +0.005pt rasteriser nudge is taken back out.
# 10.0046 is exact for what it names -- ``595.2755906 - 41.9954 - 543.2756`` --
# and the 0.0004pt between the two is the stylesheet's margin-top being that much
# larger than its own derivation, which leaves the first baseline 0.0004pt low.
# The residual is deliberately not chased: closing it means moving margin-top,
# margin-bottom and every constant derived from this one (the opener title top,
# the header height 305.2756, the editorial 153.2756, the figure's own 10.0046pt
# paint offset) by 0.0008 of a device pixel at 144 DPI, in the same truncation
# regime where the measured +0.005pt nudge moved roughly one line in four.
_FIRST_BASELINE_INSET_POINTS = 10.0046

# The stylesheet ships ``margin: 42.0004pt ... 54.9996pt``, i.e. the derived
# 41.9954 / 55.0046 with a +0.005pt nudge added to the top and taken off the
# bottom.  It is a *rasteriser* correction and nothing typographic: poppler
# truncates a glyph origin to a device pixel, and the nudge keeps the reader's
# baselines off that boundary (see the stylesheet's own note above ``@page``).
#
# Top and bottom move by the same amount in opposite directions, so the content
# box's *height* -- and therefore line capacity, fragmentation and flow -- is
# untouched.  What the nudge does do is translate every measured CSS position
# down the page by 0.005pt, and geometry the adapter *reports* rather than
# consumes must not carry it: ``RenderLayout.figure_placements`` is read by
# ``preflight`` and written into the edition manifest, and an adaptive band's
# shrink limit is measured off a bridge datum in the same coordinates.  The
# nudge is therefore taken back out at the one place CSS y becomes reader y,
# ``_reader_y_points``, and nowhere else -- a correction applied in CSS space
# (a paint offset, an end-mark clamp) is re-applied in the nudged frame it was
# measured in and must keep the nudge.
_RASTER_NUDGE_POINTS = 0.005


def _reader_y_points(css_top_points: float, height_points: float) -> float:
    """A box's PDF ``y`` from its CSS top, both in points, nudge removed.

    CSS y runs down from the page's top edge; PDF y runs up from its foot.  The
    subtraction flips the sign of the rasteriser nudge, so it is *added* back.
    """
    return _PAGE_HEIGHT_POINTS - css_top_points - height_points + _RASTER_NUDGE_POINTS


# ``_article_tail_ornament_box`` (render.py:218-231).
_TAIL_ORNAMENT_MIN_HEIGHT = 118.0
_TAIL_ORNAMENT_MAX_HEIGHT = 214.0
_TAIL_ORNAMENT_FOOT_INSET = 24.0
_TAIL_ORNAMENT_ENDMARK_CLEARANCE = 31.0

_PLATE_ANCHOR_TAGS = frozenset({"h1", "h2", "h3"})
_LANDSCAPE_PLATE_LAYOUTS = frozenset({"landscape_plate", "landscape_plate_after"})
_PLATE_FRAME_ACROSS_POINTS = 333.008
"""The live width, which is the plate frame's own height before it is rotated."""

# The live area, from ``render.py``: A5 width less INNER_MARGIN and OUTER_MARGIN.
_LIVE_WIDTH_POINTS = 333.0079
# ``@page``'s own margin-bottom.  Every CSS box's static top stands
# ``_FIRST_BASELINE_INSET_POINTS`` above the ``self.y`` it means, because the
# page's content box is derived from the first baseline and not from the frame
# top, so the content box's foot lands on ReportLab's frame bottom and any rule
# stated against ``self.bottom`` needs no relief at all.  Stated as the
# arithmetic rather than as zero: it is zero only while the stylesheet keeps the
# two frames on the same edge.
_PAGE_MARGIN_BOTTOM_POINTS = 55.0046
_FRAME_BOTTOM_RELIEF_POINTS = _FRAME_BOTTOM_POINTS - (
    _PAGE_MARGIN_BOTTOM_POINTS - _FIRST_BASELINE_INSET_POINTS
)

# ``_figure_geometry`` (render.py:716-739).
_CAPTION_SIZE = 6.8
_FIGURE_TEXT_LEADING = 8.6
_FIGURE_GAP = 15.75
_FIGURE_LABEL_ZONE_POINTS = _CAPTION_SIZE + 6.3
_FIGURE_BAND_MAX_IMAGE_HEIGHT = 205.0
_ADAPTIVE_FIGURE_MIN_IMAGE_HEIGHT = 155.0
_MIN_FIGURE_PPI = 300.0
# ``_evidence_band`` measures its anchor heading with metrics that ``block``
# does not draw it with (render.py:871-874 against render.py:1120): the band's
# fit decision uses 20.5pt lines plus 10pt after for an h2, and 12pt lines plus
# 7pt after for an h3.  Reproducing the quirk is what puts an adaptive band's
# shrink on the same point as the reader's.
_BAND_HEADING_MEASURE = {"h2": ("serif-display", 17.5, 20.5, 10.0), "h3": ("sans-semibold", 8.7, 12.0, 7.0)}
# ``_evidence_band`` (render.py:947-950) and ``_opener_evidence_band``
# (render.py:984-987) both demand four reading lines below a band or open a new
# page for whatever follows.  The reading leading is 12.2pt in an article that
# carries a landscape plate and 13pt everywhere else (render.py:2112-2116).
_EVIDENCE_BAND_LAYOUTS = frozenset(
    {"evidence_band", "evidence_band_prose", "adaptive_band", "compact_band"}
)
# INNER_MARGIN and OUTER_MARGIN, which `_set_page_margins` (render.py:453-457)
# swaps by page parity: an odd page's live area starts on the inner margin.
_INNER_MARGIN_POINTS = 44.0
_OUTER_MARGIN_POINTS = 15 * 72 / 25.4
_BAND_CLEARANCE_LINES = 4
_PLATE_ARTICLE_READING_LEADING = 12.2
_READING_LEADING = 13.0
# ``block`` (render.py:1133-1137) reserves this much below every heading it sets
# before it will leave the heading on the page.
_HEADING_CLEARANCE_POINTS = 25.0

# The figure frame: ``INK`` and ``setLineWidth(.55)`` from ``render.py``:766 and
# :1070, which both stroke a rectangle on the fitted image's own edge.
_FIGURE_RULE_WIDTH_POINTS = .55
_FIGURE_RULE_INK = "rgb(5.5%,7.5%,8.5%)"
# The frame is centred on the image edge, so half of it falls outside the image.
# A replaced element's painting is clipped to its own box, so the rule image is
# grown by this much on every side to keep the whole stroke inside the clip.
_FIGURE_RULE_BLEED_POINTS = 1.0

# ``_closing_plate`` (render.py:2183-2196): the title box is ``grid_box(0, 5)``
# and its first baseline is one size below y 168, which from the page's own
# content box is ``385.2802 + size``.  Magazine Serif Display on a solid leading
# carries its baseline ``(1 - 1.371) / 2 + 1.036`` = 0.8505 of the size below
# its box, so the box's head is ``385.2802 + 0.1495 * size``.
#
# ``grid_box(0, 5)`` on the reader's own live width of
# ``419.5275590551 - 44 - 15mm`` = 333.0078740157 is
# ``5 * (live - 5 * 9.45) / 6 + 4 * 9.45`` = 275.93156167979, so the fourth
# decimal is a 6.
_PLATE_TITLE_WIDTH_POINTS = 275.9316
_PLATE_TITLE_CONTENT_TOP_POINTS = 385.2802
_DISPLAY_SOLID_BASELINE_HEAD = 1.0 - ((1.0 - 1.371) / 2 + 1.036)

# ``_fitted_title_box`` (render.py:1762-1791) on an opener: the reader steps
# SERIF_DISPLAY down half a point at a time, sets the first baseline one ``size``
# below a pinned top and leads the rest at ``0.96 * size``.
_OPENER_TITLE_LEADING_RATIO = .96
# Where that pinned top stands below the page's *content box*: ``_label`` takes
# 25 from the frame top and ``_fitted_title_box`` is entered 12 lower
# (render.py:1708, 1990), and the content box stands 10.0046 above the frame top.
_OPENER_TITLE_TOP_POINTS = _FIRST_BASELINE_INSET_POINTS + 25.0 + 12.0
# ``.content-label``'s own box height in the stylesheet: 7.53085pt of padding
# over a zero-leading line, which puts the kicker's baseline on the frame top.
_OPENER_LABEL_BOX_POINTS = 7.53085
# A zero-leading line carries its baseline ``(ascent + descent) / 2`` of the size
# below its own box.  Magazine Sans is 0.96875 / -0.2412109375, so the ratio is
# 0.36376953125 -- and the byline is set at 7.4pt, not at the 6.8pt CAPTION_SIZE
# the rest of the opener chrome uses, which is 0.21814pt of difference and was
# the whole of the byline's residual.
_SANS_ZERO_LEADING_RATIO = (0.96875 - 0.2412109375) / 2
_ZERO_LEADING_SANS_BASELINE = 2.47375
_BYLINE_SIZE_POINTS = 7.4
_BYLINE_ZERO_LEADING_BASELINE = _BYLINE_SIZE_POINTS * _SANS_ZERO_LEADING_RATIO
# ``_set_custom_frame(top=title_bottom - 10)`` then ``_credit``'s own 12pt pad.
_OPENER_TITLE_TO_CREDIT_POINTS = 10.0
_OPENER_BYLINE_PAD_POINTS = 12.0
# A Magazine Serif Display line on a ``0.96`` leading ratio carries its baseline
# ``0.96 / 2 + 0.3505`` of the size below its own box.
_OPENER_TITLE_BASELINE_RATIO = _OPENER_TITLE_LEADING_RATIO / 2 + .3505
# ReportLab's frame top, which every pinned field is measured down to.
_FRAME_TOP_POINTS = _PAGE_HEIGHT_POINTS - 52.0
# ``_render_article_opener`` (render.py:1975-2006) and ``body`` (render.py:2065-2091)
# read down from the frame top identically until the credit: label 25, title
# entered 12 lower and consuming ``size * (1 + 0.96 * lines)``, custom frame 10,
# credit 12 + 13.  An opener figure then hands 13 back (render.py:2001), and the
# editorial does not.  The residue is the field's *flow* height.
_OPENER_FIGURE_FIELD_BASE = 25.0 + 12.0 + 10.0 + 12.0 + 13.0 - 13.0
_EDITORIAL_FIELD_BASE = 25.0 + 12.0 + 10.0 + 12.0 + 13.0
# ``_section`` (render.py:2150-2168) sets no credit at all and ends on
# ``_set_reading_frame(top=title_bottom - 25)``.
_SECTION_FIELD_BASE = 25.0 + 12.0 + 25.0
# ``_set_reading_frame(top=min(self.y, 390))`` (render.py:2091) is a clamp; the
# stylesheet holds the floor as ``min-height`` and this is what it is.
_EDITORIAL_FIELD_FLOOR = _FRAME_TOP_POINTS - 390.0
# ``_fitted_title_box``'s own box on each opener (render.py:1985-1994, 2070-2079).
_ARTICLE_TITLE_BOX = (165.0, 24.0)
_EDITORIAL_TITLE_BOX = (135.0, 25.0)
_SECTION_TITLE_BOX = (150.0, 25.0)
_ARTICLE_TITLE_MAX_WITH_FIGURE = 30.0
_ARTICLE_TITLE_MAX = 35.0
_EDITORIAL_TITLE_MAX = 35.0
_SECTION_TITLE_MAX = 35.0
_OPENER_TITLE_MAX_LINES = 4

# ``_article_endmark`` (render.py:2008-2021).  The mark is hoisted 20pt out of
# the flow by its own negative margin so that it can never open a page, and
# painted back down by this much: the hoist, plus the 10.0046 between the flow
# edge and ``self.y``, less the 2.47375 its own zero-leading line already
# carries, plus the 1pt the reader drops below ``self.y``.
_END_MARK_HOIST_POINTS = 20.0
_END_MARK_PAINT_POINTS = (
    _END_MARK_HOIST_POINTS
    + _FIRST_BASELINE_INSET_POINTS
    - _ZERO_LEADING_SANS_BASELINE
    + 1.0
)
# ``baseline = max(self.frame_bottom + 5, self.y - 1)``.
_END_MARK_FLOOR_POINTS = _FRAME_BOTTOM_POINTS + 5.0
_END_MARK_DROP_POINTS = 1.0

_FONT_FILES = {
    "serif": "source-serif-4/SourceSerif4SmText-Regular.ttf",
    "serif-display": "source-serif-4/SourceSerif4Display-Semibold.ttf",
    "sans-medium": "inter/Inter-Medium.ttf",
    "sans-semibold": "inter/Inter-SemiBold.ttf",
}

_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MARKDOWN_EMPHASIS = re.compile(r"[*`]")

# ``lines`` (render.py:658-685) splits a paragraph with ``str.split``, so the
# only place the reader can end a line is a run of whitespace.  Pango also
# breaks *inside* a token -- after a hyphen, an en dash or an em dash -- and in
# English it takes those opportunities on `with-- implementing`, `compile-
# checked`, `Opus- planner`, `differed-- some`, `planner-executor-synthesis` and
# `trade- offs`, which is the whole of the residual line-break disagreement.
# Measured (PIXEL-FLOOR.md): `word-break: keep-all`, `line-break: strict`,
# `hyphens: none` and `overflow-wrap: normal` are all no-ops against it, so the
# only lever is markup -- one ``white-space: nowrap`` box per whitespace token.
# It is print-only structure in the same sense a plate page is: the semantic
# edition keeps whole text nodes, and a future web adapter never sees a span.
_READER_TOKEN_CLASS = "reader-token"
_TOKEN_SPLIT = re.compile(r"(\S+)")
# ``white-space: pre-wrap`` content is laid out on its own authored line
# structure, and a nowrap box inside it would suppress breaks the reader does
# take.  The remaining tags simply hold no reader prose.
_PRESERVED_TEXT_TAGS = frozenset({"pre", "textarea", "script", "style"})
# A line box is over its measure only when it exceeds it by more than float
# noise; 0.01 CSS px is four thousandths of a point.
_TOKEN_MEASURE_EPSILON = 0.01


@lru_cache(maxsize=None)
def _advance_widths(face: str) -> dict[str, float]:
    """Each character's advance in ems, as ``pdfmetrics.stringWidth`` sums them.

    The reader measures a line as the plain sum of glyph advances with neither
    kerning nor ligatures (render.py:658-685), which is the same measure the
    stylesheet asks Pango for.  Reading the advances straight out of the
    bundled face is what lets this module answer "how many lines, at what
    size?" for the two places the reader auto-fits display type -- an opener
    that carries its own figure, and a closing plate -- without a second
    typesetter having to lay the text out.
    """
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
    """``render._plain``: markdown links stripped, then the reader's repertoire."""
    return fold_reader_characters(_MARKDOWN_LINK.sub(r"\1", text))


def _string_width(text: str, face: str, size: float) -> float:
    widths = _advance_widths(face)
    return sum(widths.get(character, 0.0) for character in text) * size


def _wrap(text: str, face: str, size: float, width: float) -> list[str]:
    """``Reader.lines`` (render.py:658-685): greedy, whitespace-only, no hyphenation."""
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
    """``_fitted_title_box`` (render.py:1762-1791), as a size and its lines.

    The reader steps the size down by half a point until the title fits both
    the declared line count and the declared box, and raises when nothing does.
    """
    size = maximum
    while size >= minimum:
        lines = _wrap(text, "serif-display", size, width)
        leading = size * leading_ratio
        if len(lines) <= maximum_lines and size + (len(lines) - 1) * leading <= height:
            return size, lines
        size -= .5
    raise ValidationError(f"Title cannot fit the Quiet Standard display box: {text}")


def render_a5_weasyprint(
    edition: Edition,
    output: Path,
    *,
    design: str = WEASYPRINT_DESIGN,
) -> RenderLayout:
    """Write an experimental A5 reader PDF and return measured layout facts.

    The resulting reader has logical A5 pages.  Page 1 and its final page are
    intentionally blank outer-cover placeholders, while page 2 and the
    penultimate page are blank inside covers.  A caller may splice canonical
    cover PDFs over the two outer placeholders before ordinary A4 imposition.

    ``weasyprint`` is imported lazily so projects that have not installed its
    native text dependencies receive a useful, actionable validation error
    instead of an import-time failure across the entire magazine package.
    """
    if design != WEASYPRINT_DESIGN:
        raise ValidationError(
            f"Unsupported WeasyPrint design {design!r}; expected {WEASYPRINT_DESIGN!r}"
        )
    _validate_caps(edition)
    HTML, CSS, FontConfiguration = _weasyprint_types()

    # The semantic edition already folds every text and attribute value into the
    # publication's reader repertoire, one value at a time.  This adapter must
    # not re-fold the assembled document: character rules applied to finished
    # markup rewrite tag and attribute syntax, not prose.
    semantic = render_html_edition(edition)
    # A @font-face rule is only installed when the stylesheet is parsed with a
    # font configuration, and only usable when layout receives the same one.
    # Without this the reader silently falls back to whatever host fonts
    # fontconfig prefers, and every line break is measured on the wrong face.
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
    _validate_layout_caps(layout)
    _validate_cover_slots(document)
    _validate_contents_page(document)
    _validate_reader_measures(document)
    document = _painted_reader(
        HTML, html, stylesheet, edition, plan, document, font_config=font_config
    )
    try:
        # A fixed identifier avoids a volatile trailer identifier in otherwise
        # deterministic builds.  The content hash lets distinct editions remain
        # distinct without introducing a timestamp.
        identifier = hashlib.sha256(html.encode("utf-8")).digest()[:16]
        pdf_bytes = document.write_pdf(pdf_identifier=identifier)
    except TypeError:  # Defensive compatibility with older WeasyPrint releases.
        pdf_bytes = document.write_pdf()
    except Exception as exc:
        raise ValidationError(f"WeasyPrint could not write edition {edition.id}: {exc}") from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(pdf_bytes)
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
    """Expose conventional Homebrew libraries to WeasyPrint's lazy CFFI load.

    The PyPI wheel contains the Python bindings but macOS obtains Pango and
    GLib from the host.  Homebrew installs those libraries outside the dynamic
    loader's default lookup path.  This small, process-local adjustment leaves
    an existing user path intact and makes no assumptions about user fonts or
    a project-specific native dependency directory.
    """
    if platform.system() != "Darwin":
        return
    candidates = [
        str(path)
        for path in (Path("/opt/homebrew/lib"), Path("/usr/local/lib"))
        if path.is_dir()
    ]
    if not candidates:
        return
    existing = [entry for entry in os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "").split(":") if entry]
    additions = [entry for entry in candidates if entry not in existing]
    if additions:
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join([*additions, *existing])


def _read_print_css() -> str:
    return resources.files("magazine").joinpath("assets", "weasyprint-a5.css").read_text(
        encoding="utf-8"
    )


def _with_print_slots(html: str) -> str:
    """Add print-only page slots without contaminating semantic HTML output."""
    main_open = '<main data-edition-id='
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


@dataclass(frozen=True, slots=True)
class ReaderPlan:
    """The placement decisions that no stylesheet can reach on its own.

    ``closing_plates`` is the number of plates the signature arithmetic in
    ``render.back_cover`` asks for, which is a function of where the content
    happens to end.  ``tail_ornaments`` maps an article id to the height of the
    tail motif that article has earned, and omits every article whose last page
    does not have the open space ``_article_tail_ornament_box`` demands.
    ``adaptive_images`` maps a figure id to the image height an ``adaptive_band``
    has been shrunk to so that it can still bridge the page it started on
    (render.py:901-922), and omits every band that fits at its full height.
    ``band_offsets`` maps a figure id to the margin mirror a band inherited from
    the page it was dispatched from, and omits every band that stayed there.
    ``end_marks`` maps an article id to the distance its end mark is painted back
    down by, which is a constant except where the reader's own clamp bites.
    All five are *measured* facts, so a plan is the output of one layout and the
    input to the next.
    """

    closing_plates: int
    tail_ornaments: tuple[tuple[str, float], ...]
    adaptive_images: tuple[tuple[str, float], ...] = ()
    band_offsets: tuple[tuple[str, float], ...] = ()
    end_marks: tuple[tuple[str, float], ...] = ()

    @property
    def tail_heights(self) -> dict[str, float]:
        return dict(self.tail_ornaments)

    @property
    def end_mark_offsets(self) -> dict[str, float]:
        return dict(self.end_marks)

    @property
    def adaptive_image_heights(self) -> dict[str, float]:
        return dict(self.adaptive_images)

    @property
    def band_offset_points(self) -> dict[str, float]:
        return dict(self.band_offsets)


class MeasuredRule(NamedTuple):
    """Where a curated figure's fitted image box was laid out.

    ``left`` and ``top`` are measured from the figure's own padding box, which
    is the coordinate the frame image is positioned in, and ``page`` is the
    reader page the figure landed on -- carried because the other four are blind
    to the figure moving.
    """

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
    """Measure one layout, then lay the reader out again against what it measured.

    Two of ReportLab's placement rules read the finished page rather than the
    content: the closing-plate count comes from where the body stopped, and a
    tail ornament appears only when its article's last page really has
    ``ARTICLE_TAIL_ORNAMENT_MIN_HEIGHT`` of open space below the end mark.
    Neither question can be asked in CSS, so this renders a probe pass that
    over-provides both, measures it, and renders the answer.  A third pass then
    has nothing left to change: closing plates land after the body and the tail
    ornament is out of flow, so neither decision can move the content that both
    were derived from -- which is asserted rather than assumed.
    """
    html = _with_print_slots(semantic_html)
    probe = ReaderPlan(
        closing_plates=len(edition.closing_plates),
        tail_ornaments=tuple(
            (article.id, _TAIL_ORNAMENT_MAX_HEIGHT)
            for article in edition.articles
            if article.tail_art is not None
        ),
    )
    document = _lay_out(HTML, html, stylesheet, edition, probe, font_config=font_config)
    plan = _measured_plan(document, edition)
    if plan != probe:
        document = _lay_out(HTML, html, stylesheet, edition, plan, font_config=font_config)
        settled = _measured_plan(document, edition)
        if settled != plan:
            raise ValidationError(
                f"WeasyPrint pagination for edition {edition.id} did not settle: the "
                f"plan measured from the probe pass ({plan}) is not the plan the "
                f"laid-out reader measures ({settled})"
            )
    if len(document.pages) % 4:
        # The reader closes its signature with closing plates, never with a blank
        # filler page; the equivalence contract bans the latter outright.  The
        # coda such a page used to print is named here so the arithmetic that
        # replaced it is checkable against the artifact it replaced.
        signature_coda = f"{edition.publication_name} — {edition.title}"
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
    """The settled reader, laid out once more with its figure frames painted.

    ``_draw_contained_image`` (render.py:765-767) and ``_landscape_plate``
    (render.py:1069-1071) both *stroke* a 0.55pt rectangle on the fitted image's
    edge, and poppler gives a thin stroke its own pixel-snapping treatment: a
    0.55pt stroke rasterises to whole pixels at full ink, while the same ink laid
    down as a *fill* is antialiased across twice as many pixels.  WeasyPrint has
    no property that strokes -- ``outline``, ``border`` and ``border-image`` are
    all filled by ``draw_rect_border`` -- so the frame is drawn by the one part
    of WeasyPrint that does emit ``RG``/``S``: its SVG renderer, as a rule image
    laid over the image box.  A background image is not equivalent; WeasyPrint
    wraps one in a transparency group, and poppler does not snap a stroke inside
    a group.

    A rule image needs its box, which is only knowable once the reader is laid
    out, so this pass re-lays the settled plan with the boxes the settled plan
    measured.  Every rule is absolutely positioned, so it cannot move a line --
    which is asserted here rather than assumed, and asserted as literally as the
    sentence reads: the page count, every curated figure's page and fitted box,
    and the ``(page, position_x, position_y)`` of *every text box in the
    document* -- 9,047 of them in English and 10,007 in Spanish -- must be
    identical before and after.  A guard over the figures alone would not be
    that claim: ``_box_inside`` measures inside the figure's own padding box, a
    coordinate that does not move when the figure does.
    """
    declared = _declared_figure_ids(html)
    rules = _measured_figure_rules(document)
    if set(rules) != declared:
        # An empty ``rules`` used to mean both "this edition curates no figures"
        # and "the ``data-figure-id`` selector no longer matches anything", and
        # the second is silent frame loss: every stroke would simply be missing
        # from the delivered PDF, and G4 would land at about 0.0021 against a
        # 0.002 tolerance -- a soft failure a hair over the line.  The semantic
        # HTML is the independent witness, so the two cases are separated here.
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
            f"{len(after)} after, {len(moved)} of them displaced. "
            + "; ".join(moved[:5])
        )
    _validate_figure_rules(painted, rules)
    return painted


def _declared_figure_ids(html: str) -> set[str]:
    """Every curated figure the semantic HTML declares, read from the source.

    Deliberately a scan of the HTML text and not of the laid-out box tree: it
    exists to catch the box walk finding nothing, so it cannot share the box
    walk's own assumptions.  Attribute values are escaped on the way out of
    ``html_edition``, which is also what keeps a ``data-figure-id`` quoted inside
    a manuscript's prose from being read as a declaration: its quotes are
    ``&quot;`` there, and the pattern wants real ones.
    """
    return {unescape(value) for value in re.findall(r'data-figure-id="([^"]+)"', html)}


def _measured_flow_positions(document: Any) -> tuple[tuple[int, str, float, float], ...]:
    """Every text box in ``document`` as ``(page, text, position_x, position_y)``.

    Text boxes are the leaves the reader is judged on, and their positions are
    absolute page coordinates, so a box that changed page, line or column shows
    up here even when its container's internal geometry is unchanged.
    """
    positions: list[tuple[int, str, float, float]] = []
    for page_number, page in enumerate(document.pages, start=1):
        for box in _walk_boxes(page._page_box):
            text = getattr(box, "text", None)
            if not isinstance(text, str):
                continue
            positions.append(
                (page_number, text, round(float(box.position_x), 6), round(float(box.position_y), 6))
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
    """Lay out one reader variant of ``plan`` from the semantic document tree.

    The print-only structure a plate page needs -- a rotated frame holding the
    heading its figure consumes -- is not expressible as a stylesheet rule, and
    the plan's two counts are not expressible at all.  Both are applied to the
    parsed document tree rather than to the HTML text, so the semantic edition
    stays exactly what ``html_edition`` emitted.

    ``figure_rules`` paints the figure frames over image boxes an earlier pass
    measured; it is out of flow and never changes what this pass lays out.
    """
    source = HTML(string=html, base_url=Path.cwd().as_uri() + "/")
    tree = source.etree_element
    _suppress_intra_token_breaks(tree)
    _install_page_chrome(tree, edition)
    _rewrite_landscape_plates(tree)
    _pin_opener_fields(tree, edition)
    _mark_band_bridges(tree)
    _apply_adaptive_images(tree, plan.adaptive_image_heights)
    _apply_band_offsets(tree, plan.band_offset_points)
    _install_flow_clearances(tree)
    _limit_closing_plates(tree, plan.closing_plates)
    _fit_closing_plate_titles(tree, edition)
    _apply_print_contrast(tree)
    _apply_end_marks(tree, plan.end_mark_offsets)
    _apply_tail_ornaments(tree, plan.tail_heights)
    # Last, so that nothing downstream rewrites the rule images' own geometry.
    _apply_figure_rules(tree, figure_rules or {})
    try:
        return source.render(stylesheets=[stylesheet], font_config=font_config)
    except Exception as exc:  # Weasy's native-library errors differ by platform.
        raise ValidationError(
            f"WeasyPrint could not lay out edition {edition.id}: {exc}"
        ) from exc


def _element_classes(element: Element) -> frozenset[str]:
    return frozenset((element.get("class") or "").split())


def _suppress_intra_token_breaks(tree: Element) -> None:
    """Give the reader's own line-break opportunities to the print document.

    The reader can only end a line where ``lines`` found whitespace, so every
    whitespace token becomes one ``white-space: nowrap`` box and the whitespace
    between tokens is left exactly as it was.  Nothing is inserted, removed or
    reordered -- the concatenated text of the tree is unchanged, which is what
    keeps G3's extracted text a comparison of *placement* and not of content.

    Two things this deliberately does not do.  It never uses a zero-width joiner
    or word joiner: those glyphs are absent from both bundled faces and fall
    back to a host font without saying so.  And it does not pair the nowrap box
    with ``overflow-wrap: anywhere`` for a token wider than the measure --
    measured, ``overflow-wrap`` is inert inside ``white-space: nowrap``, so the
    pairing buys nothing and the token would simply overflow.  A token that wide
    is refused by ``_validate_reader_measures`` instead of being set wrong.
    """
    for main in tree.iter("main"):
        _wrap_reader_tokens(main)


def _wrap_reader_tokens(element: Element) -> None:
    tag = str(element.tag).rsplit("}", 1)[-1].lower()
    if tag in _PRESERVED_TEXT_TAGS:
        return
    children = list(element)
    for child in children:
        _wrap_reader_tokens(child)
    element.text, rebuilt = _reader_token_spans(element.text)
    for child in children:
        child.tail, spans = _reader_token_spans(child.tail)
        rebuilt.append(child)
        rebuilt.extend(spans)
    element[:] = rebuilt


def _reader_token_spans(text: str | None) -> tuple[str | None, list[Element]]:
    """``text`` split into the whitespace it opens with and one span per token.

    Each span carries the whitespace that follows its token as its tail, so
    joining the parts back together reproduces ``text`` character for character.
    """
    if not text or not text.strip():
        return text, []
    leading, *parts = _TOKEN_SPLIT.split(text)
    spans: list[Element] = []
    for token, following in zip(parts[0::2], parts[1::2]):
        span = Element("span", {"class": _READER_TOKEN_CLASS})
        span.text = token
        span.tail = following or None
        spans.append(span)
    return leading or None, spans


def _install_page_chrome(tree: Element, edition: Edition) -> None:
    """Give every piece the head its continuation pages run, and name the folio.

    The reader's page furniture repeats content that belongs to no single page:
    the publication's name on every folio, and each piece's own curated short
    title on every page of that piece after the first.  A margin box can only
    repeat what a *running element* offers it, and a running element is a real
    element in the document -- which the semantic edition, being renderer
    neutral, has no reason to carry.  Both are therefore print-only structure,
    inserted here from the edition's own metadata, exactly as a plate page is.

    A piece's head is inserted as its first child so that the assignment lands on
    the page the piece opens on, which is what makes ``first-except`` suppress the
    header there and print it everywhere after.
    """
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
        # The rule and its signal tick are drawn boxes, not backgrounds of the
        # head: WeasyPrint 69 ignores `background-size` for a gradient and floods
        # the whole element, and a margin box forces its running element static,
        # so the tick needs a positioned box of its own to hang from.
        SubElement(SubElement(head, "div", {"class": "running-head-rule"}), "i")
        piece.insert(0, head)


def _rewrite_landscape_plates(tree: Element) -> None:
    """Turn every ``landscape_plate*`` figure into its own sideways plate page.

    ``_landscape_plate`` (render.py:989-1115) opens a page before it draws
    anything, so a plate is a page and not a block in the column.  Which heading
    that page carries, and where the page falls, differ by layout:

    ``landscape_plate`` is dispatched from the anchor heading itself
    (render.py:1384-1393), which is never set in the column -- the plate consumes
    it.  ``landscape_plate_after`` is deferred (render.py:1419-1439): the anchor
    heading *is* set in the column, and the plate -- repeating that heading --
    surfaces at the next heading of the article, or at the article's end.
    """
    for article in tree.iter("article"):
        _rewrite_article_plates(article)


def _rewrite_article_plates(article: Element) -> None:
    ordered: list[Element] = []
    deferred: Element | None = None
    for child in article:
        layout = child.get("data-layout", "") if child.tag == "figure" else ""
        if layout not in _LANDSCAPE_PLATE_LAYOUTS:
            # A heading releases a deferred plate, and so does the tail ornament:
            # the plate belongs to the article's prose, ahead of its coda.
            releases = child.tag in _PLATE_ANCHOR_TAGS or "article-tail" in _element_classes(child)
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
    """A full-page plate: one rotated frame holding the heading and the figure."""
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
    """The figure ``_opener_evidence_band`` draws in the opener's own space."""
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


def _set_opener_title(header: Element, size: float) -> None:
    """State the auto-fitted display size, and the two margins that follow it.

    ``_fitted_title_box`` puts the first baseline one ``size`` below a top that
    stands ``_OPENER_TITLE_TOP_POINTS`` under the page's content box, and leads
    the rest at ``0.96 * size``.  A CSS line box instead carries its baseline
    ``_OPENER_TITLE_BASELINE_RATIO * size`` below its own top, so the margin above
    the title is the distance from the label's box to *that* top, and the margin
    below is what puts the byline's baseline back on ``title_bottom - 10``.  Both
    fall out of the size alone -- neither depends on the line count, because the
    lines themselves are on the reader's own leading.
    """
    baseline_head = _OPENER_TITLE_BASELINE_RATIO * size
    margin_top = (
        _OPENER_TITLE_TOP_POINTS - _OPENER_LABEL_BOX_POINTS + size - baseline_head
    )
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
    """Set every opener's auto-fitted title, and pin the white field below it.

    Two things in an opener are measurements rather than rules.  The title's size
    is chosen by stepping down until the text fits its declared box and line
    count, which no stylesheet can do; and the field the opener reserves for the
    prose below it is a function of where that title ended.

    Reading down from ``new_page``'s frame top at ``595.2756 - TEXT_TOP_INSET``:
    ``_label`` takes 25 (render.py:1708), ``_fitted_title_box`` is entered 12
    lower (render.py:1990) and consumes ``size + lines * size * 0.96``,
    ``_set_custom_frame`` takes another 10 (render.py:1998) and ``_credit`` takes
    12 + 13 with no author note (render.py:1732, 1741).

    What the three openers then do with that differs.  An article without a
    figure ignores it and pins ``top=238``, so the stylesheet holds a constant.
    An article *with* one ends on ``_set_reading_frame(top=self.y)`` after
    handing 13 back (render.py:2001-2003).  The editorial clamps,
    ``top=min(self.y, 390)`` (render.py:2091), so its natural height is stated
    here and the stylesheet's ``min-height`` is the ``min``.  Every field is a
    *flow* height, measured from the page's content box in the same convention as
    every other box: a CSS box top stands ``_FIRST_BASELINE_INSET_POINTS`` above
    the ``self.y`` it means.
    """
    titles = {article.id: str(article.title) for article in edition.articles}
    for article in tree.iter("article"):
        header = _opener_header(article)
        title = titles.get(article.get("data-article-id") or "")
        if title is None:
            raise ValidationError(
                f"No edition article matches opener {article.get('data-article-id')!r}"
            )
        has_figure = _opener_figure(article) is not None
        height, minimum = _ARTICLE_TITLE_BOX
        size, lines = _fitted_display(
            title,
            _LIVE_WIDTH_POINTS,
            height,
            maximum=_ARTICLE_TITLE_MAX_WITH_FIGURE if has_figure else _ARTICLE_TITLE_MAX,
            minimum=minimum,
            maximum_lines=_OPENER_TITLE_MAX_LINES,
            leading_ratio=_OPENER_TITLE_LEADING_RATIO,
        )
        _set_opener_title(header, size)
        if has_figure:
            field = _OPENER_FIGURE_FIELD_BASE + _opener_title_flow(size, len(lines))
            header.set("style", f"height: {field:.4f}pt")
    sections = {
        f"section-{index}": (
            str(section.title), _SECTION_TITLE_BOX, _SECTION_TITLE_MAX, _SECTION_FIELD_BASE
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
    """``size + lines * size * 0.96``, the room ``_fitted_title_box`` consumes."""
    return size * (1 + _OPENER_TITLE_LEADING_RATIO * lines)


def _band_clearance_height(article: Element) -> float:
    """The room ``_evidence_band`` demands below a band, as a CSS box.

    ``band_bottom - 4 * reading_leading < self.bottom`` opens a new page for
    whatever follows the band, and leaves the band itself where it is.  An
    unbreakable box of that height, laid out after the figure and then pulled
    back out of the flow by its own negative bottom margin, moves to the next
    page under exactly that condition and costs nothing when it stays.  Its
    height carries the relief between ReportLab's frame bottom and the CSS page
    content box, so that "the box fits" and "four reading lines fit above
    ``self.bottom``" are the same test.
    """
    layouts = (article.get("data-figure-layouts") or "").split()
    leading = (
        _PLATE_ARTICLE_READING_LEADING
        if any(layout.startswith("landscape_plate") for layout in layouts)
        else _READING_LEADING
    )
    return _BAND_CLEARANCE_LINES * leading + _FRAME_BOTTOM_RELIEF_POINTS


def _install_flow_clearances(tree: Element) -> None:
    """Insert the two pieces of room the reader reserves and then gives back.

    ``block`` reserves 25pt below every heading it sets (render.py:1133-1137)
    and ``_evidence_band`` reserves four reading lines below every band.  Both
    are decisions about a page rather than about the content, and both leave the
    block they guard exactly where it was; a box of the reserved height, kept
    with that block and then removed from the flow by its own negative bottom
    margin, is the same decision expressed where the fragmenter can see it.
    """
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
                # A band's anchor heading is exempt: the band's own decision has
                # already placed it, and its clearance guards the pair.
                rebuilt.append(_clearance("heading-clearance", _HEADING_CLEARANCE_POINTS))
        piece[:] = rebuilt


def _clearance(name: str, height: float) -> Element:
    return Element(
        "div",
        {"class": name, "style": f"height: {height:.4f}pt; margin-bottom: {-height:.4f}pt"},
    )


def _evidence_bands(article: Element) -> Iterable[tuple[Element, Element | None, Element | None]]:
    """Every band ``_evidence_band`` dispatches, with its anchor heading and the block above it."""
    children = list(article)
    for index, child in enumerate(children):
        if child.tag != "figure" or child.get("data-layout") not in _EVIDENCE_BAND_LAYOUTS:
            continue
        heading = children[index - 1] if index and children[index - 1].tag in _PLATE_ANCHOR_TAGS else None
        bridge = children[index - 2] if heading is not None and index >= 2 else None
        yield child, heading, bridge


def _mark_band_bridges(tree: Element) -> None:
    """Name the block whose foot is ``self.y`` when ``_evidence_band`` is entered.

    Two of the band's decisions read the page it was dispatched from rather than
    the page it lands on: how far an ``adaptive_band`` may shrink its image, and
    which margin parity ``band_x`` was computed against.  Both are laid-out facts
    and not properties of the content, so the block above the band's anchor
    heading is marked and the measuring pass reads them off the finished pages.
    """
    for article in tree.iter("article"):
        for figure, _heading, bridge in _evidence_bands(article):
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
            image.set("style", f"max-height: {height:.4f}pt")


def _apply_figure_rules(tree: Element, rules: Mapping[str, MeasuredRule]) -> None:
    """Lay a stroked frame image over every figure image box that was measured.

    The rule is a lone SVG ``rect``: ``fill="none"``, ``stroke-width`` 0.55, on
    the image's own edge.  It is absolutely positioned inside the figure -- which
    the stylesheet already positions -- so it takes nothing out of the box the
    fit was computed for and cannot displace a line.
    """
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
    """A ``width`` x ``height`` frame as an SVG data URI, bled on every side.

    WeasyPrint clips a replaced element to its own box, and half of a centred
    stroke falls outside the rectangle it is drawn on, so the image is grown by
    ``_FIGURE_RULE_BLEED_POINTS`` and the rectangle inset by the same amount.
    One SVG user unit is one point, so ``stroke-width`` is the reader's own.
    """
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
    """Every curated figure's page and fitted image box, in points, inside its figure.

    The page number is part of the measurement and not decoration: ``_box_inside``
    is relative to the figure's own padding box, so a figure that moved to another
    page measures exactly the same box there.  Without the page, the settled
    comparison in ``_painted_reader`` could not see that move at all.
    """
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
    """Every measured image box carries its frame, on the edge and nowhere else.

    Keyed on ``(figure_id, page)``, so a rule painted twice -- once where it
    belongs and once on the wrong page -- is a surplus frame rather than a
    silent overwrite of the correct one.
    """
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
            misplaced.append(
                f"{figure_id}: expected {expected} on page {rule.page}, found {found}"
            )
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
    """``inner``'s content box in points, from ``outer``'s padding box corner."""
    return (
        round((float(inner.content_box_x()) - float(outer.padding_box_x())) * _POINTS_PER_CSS_PIXEL, 4),
        round((float(inner.content_box_y()) - float(outer.padding_box_y())) * _POINTS_PER_CSS_PIXEL, 4),
        round(float(inner.width) * _POINTS_PER_CSS_PIXEL, 4),
        round(float(inner.height) * _POINTS_PER_CSS_PIXEL, 4),
    )


def _is_figure_rule(box: Any) -> bool:
    element = getattr(box, "element", None)
    return element is not None and "figure-rule" in _element_classes(element)


def _walk_figure_images(box: Any, figure: Any = None) -> Iterable[tuple[Any, Any]]:
    """Every image box, paired with the curated figure it is laid out inside.

    The outermost ``figure`` on the path wins, so a pseudo-element box that
    reports its originating element's tag can never stand in for the figure.
    """
    if figure is None and getattr(box, "element_tag", None) == "figure":
        element = getattr(box, "element", None)
        if element is not None and element.get("data-figure-id"):
            figure = box
    if figure is not None and getattr(box, "element_tag", None) == "img":
        yield figure, box
    for child in getattr(box, "children", ()):
        yield from _walk_figure_images(child, figure)


def _figure_block_geometry(figure: Any, width: float, max_image_height: float) -> tuple[float, float]:
    """``_figure_geometry`` (render.py:716-739) as (image height, total height)."""
    try:
        from PIL import Image

        with Image.open(figure.path) as image:
            pixel_width, pixel_height = int(image.width), int(image.height)
    except (OSError, ValueError) as exc:
        raise ValidationError(
            f"Cannot decode curated figure {figure.path}: {exc}"
        ) from exc
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
    """``_evidence_band``'s own measurement of its anchor heading (render.py:868-877)."""
    face, size, leading, after = _BAND_HEADING_MEASURE[tag]
    measured = text.upper() if tag == "h3" else text
    return len(_wrap(measured, face, size, _LIVE_WIDTH_POINTS)) * leading + after


def _measured_adaptive_images(document: Any, edition: Edition) -> tuple[tuple[str, float], ...]:
    """Which adaptive bands the reader would shrink, and to what image height.

    ``_evidence_band`` (render.py:896-922) first asks whether the anchor heading
    and the whole figure still clear ``self.bottom`` on the page the band was
    dispatched from.  When they do not, an ``adaptive_band`` -- and only an
    ``adaptive_band`` -- gives the image back whatever height that page can still
    hold, down to ``ADAPTIVE_FIGURE_MIN_IMAGE_HEIGHT``, rather than carrying the
    band forward.

    What this is load-bearing *for* is geometry, and only geometry -- stated
    because the obvious guess is pagination, and an integrator who tests that
    guess will find it false and may delete a live mechanism.  Measured by
    ablating this function to ``()``: every article span is unchanged in both
    languages (5/3/6/3/3/7 plus the editorial's 1, with it and without it).  What
    moves is the one figure it touches on this edition.  With it, es
    ``swarm-model-cost`` is placed at ``(87.646, 90.85, 245.717, 194.526)``,
    which is the frozen manifest's box exactly; without it the same figure is
    placed at ``(81.03, 80.371, 258.947, 205.0)``, a different size in a
    different place.  The bridge datum this reads is taken through
    ``_reader_y_points``, so the shrink limit is measured off the reader's own
    frame and not off the stylesheet's rasteriser nudge.
    """
    figures = {
        figure.id: figure
        for article in edition.articles
        for figure in getattr(article, "figures", ())
    }
    anchors = {
        figure.id: str(figure.anchor)
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
    """The tag of the heading a band is anchored to; h2 unless the document says h3."""
    folded = anchor.strip().casefold()
    for page in document.pages:
        for box in _walk_boxes(page._page_box):
            tag = getattr(box, "element_tag", None)
            if tag in {"h2", "h3"} and _element_text(getattr(box, "element", None)).strip().casefold() == folded:
                return tag
    return "h2"


def _element_text(element: Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext())


def _band_bridges(document: Any) -> dict[str, tuple[int, float]]:
    """Each marked band bridge as (page, ``self.y``), the reader's own datum.

    The bridge is the last block set before ``_evidence_band`` is entered, so its
    foot is ``self.y`` and the page it ends on is the page whose margin parity
    ``band_x`` was computed against.
    """
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


def _live_area_left(page_number: int) -> float:
    """``self.left`` on a page: the inner margin on a recto, the outer on a verso."""
    return _INNER_MARGIN_POINTS if page_number % 2 else _OUTER_MARGIN_POINTS


def _measured_band_offsets(document: Any) -> tuple[tuple[str, float], ...]:
    """The margin mirror a band carries over from the page it was dispatched from.

    ``_evidence_band`` computes ``band_x = self.left + (live_width - band_width)
    / 2`` (render.py:884-885) *before* it decides whether the band can bridge the
    current page, and ``new_page`` then mirrors the margins (render.py:453-457).
    A band that could not bridge is therefore drawn on the new page at the
    previous page's ``self.left``, which is 1.4803pt from where the new page's own
    live area starts.  The reader does this; reproducing it is what puts a band's
    ink on the baseline's column.
    """
    figure_pages = _figure_pages(document)
    offsets: list[tuple[str, float]] = []
    for figure_id, (bridge_page, _top) in _band_bridges(document).items():
        landed = figure_pages.get(figure_id)
        if landed is None or landed == bridge_page:
            continue
        offsets.append(
            (figure_id, _live_area_left(bridge_page) - _live_area_left(landed))
        )
    return tuple(sorted(offsets))


def _figure_pages(document: Any) -> dict[str, int]:
    pages: dict[str, int] = {}
    for page_number, page in enumerate(document.pages, start=1):
        for box in _walk_boxes(page._page_box):
            element = getattr(box, "element", None)
            figure_id = getattr(element, "attrib", {}).get("data-figure-id") if element is not None else None
            if figure_id and getattr(box, "element_tag", None) == "figure":
                pages.setdefault(figure_id, page_number)
    return pages


def _limit_closing_plates(tree: Element, count: int) -> None:
    """Keep exactly ``count`` closing plates, as ``back_cover`` renders exactly that many.

    A shortfall is the error ``_closing_plate`` (render.py:2170-2175) raises: the
    signature cannot be closed by plates that the edition does not have, and it
    must not be closed by anything else.
    """
    parents = {child: parent for parent in tree.iter() for child in parent}
    plates = [
        element
        for element in tree.iter("figure")
        if "closing-plate" in _element_classes(element)
    ]
    if count > len(plates):
        raise ValidationError(
            f"Edition requires {count} unique closing plates for signature padding, but only "
            f"{len(plates)} are configured"
        )
    for plate in plates[count:]:
        parents[plate].remove(plate)


def _apply_print_contrast(tree: Element) -> None:
    """Give every curated figure the print-safe derivative the reader prints.

    ``prepare_print_image`` (render.py:755 and :1040) measures paper dominance,
    mark coverage and median mark contrast, and escalates contrast until a pale
    diagram survives an uncoated press.  It reaches both figure paths -- a
    contained image and a landscape plate -- and nothing else: cover art, a tail
    motif and a closing plate are drawn with ``_draw_image_fill``, which never
    calls it.  A curated figure is exactly the set that carries a figure id.

    The treated raster only exists in memory, so it travels to the layout as a
    data URI.  The original source stays on the element, because a placement is
    reported against the file the edition curated and not against a derivative.
    """
    import base64

    from .image_contrast import prepare_print_image

    for figure in tree.iter("figure"):
        if not figure.get("data-figure-id"):
            continue
        for image in figure.iter("img"):
            source = image.get("src")
            if not source or source.startswith("data:"):
                continue
            path = Path(_path_from_uri(source))
            try:
                prepared = prepare_print_image(path)
            except Exception as exc:  # Pillow's failures differ by format.
                raise ValidationError(f"Cannot decode curated figure {path}: {exc}") from exc
            if not prepared.adjusted:
                continue
            payload = base64.b64encode(prepared.image.getvalue()).decode("ascii")
            image.set("data-print-source", source)
            image.set("src", f"data:image/png;base64,{payload}")


def _path_from_uri(source: str) -> str:
    from urllib.parse import unquote, urlparse

    parsed = urlparse(source)
    return unquote(parsed.path) if parsed.scheme == "file" else source


def _fit_closing_plate_titles(tree: Element, edition: Edition) -> None:
    """Set each surviving plate's title at the size ``_fitted_title_box`` chose.

    Auto-fitting is a measurement, not a rule a stylesheet can hold: the reader
    steps 32pt down to 22 until the title takes at most two lines of
    ``grid_box(0, 5)`` and stands no taller than 92pt.  The chosen size is
    stated on the element, together with the head its own first baseline needs;
    the stylesheet owns everything that does not depend on it.
    """
    titles = [str(plate.title) for plate in edition.closing_plates]
    for plate in tree.iter("figure"):
        if "closing-plate" not in _element_classes(plate):
            continue
        index = int(str(plate.get("data-closing-plate", "0"))) - 1
        if not 0 <= index < len(titles):
            raise ValidationError(
                f"Closing plate {plate.get('data-closing-plate')!r} matches no configured plate"
            )
        size, _lines = _fitted_display(
            titles[index],
            _PLATE_TITLE_WIDTH_POINTS,
            92.0,
            maximum=32.0,
            minimum=22.0,
            maximum_lines=2,
            leading_ratio=1.0,
        )
        top = _PLATE_TITLE_CONTENT_TOP_POINTS + _DISPLAY_SOLID_BASELINE_HEAD * size
        for caption in plate.iter("figcaption"):
            caption.set(
                "style",
                f"font-size: {size:.4f}pt; line-height: {size:.4f}pt; top: {top:.4f}pt",
            )


def _apply_tail_ornaments(tree: Element, heights: Mapping[str, float]) -> None:
    """Size each earned tail ornament, and remove the ones no page has room for."""
    for article in tree.iter("article"):
        height = heights.get(article.get("data-article-id") or "")
        for child in [child for child in article if "article-tail" in _element_classes(child)]:
            if height is None:
                article.remove(child)
            else:
                child.set("style", f"height: {height:.4f}pt")


def _measured_plan(document: Any, edition: Edition) -> ReaderPlan:
    """Read a laid-out reader back as the plan its own pages imply."""
    content_pages = _content_page_count(document)
    ornaments: list[tuple[str, float]] = []
    end_marks: list[tuple[str, float]] = []
    for article in edition.articles:
        flow_bottom = _article_flow_bottom(document, article.id)
        end_marks.append((article.id, _end_mark_offset(flow_bottom)))
        if article.tail_art is None:
            continue
        height = _tail_ornament_height(flow_bottom)
        if height is not None:
            ornaments.append((article.id, height))
    return ReaderPlan(
        closing_plates=_signature_closing_plates(edition, content_pages),
        tail_ornaments=tuple(ornaments),
        adaptive_images=_measured_adaptive_images(document, edition),
        band_offsets=_measured_band_offsets(document),
        end_marks=tuple(end_marks),
    )


def _end_mark_offset(flow_bottom: float) -> float:
    """How far ``_article_endmark``'s mark is painted below its own flow box.

    ``baseline = max(self.frame_bottom + 5, self.y - 1)`` (render.py:2009) reads a
    laid-out ``self.y``, which is exactly what ``_article_flow_bottom`` measures,
    so the clamp is reproduced here rather than approximated by a fixed budget in
    the stylesheet.  Below the clamp the offset is a constant; at it, the mark
    stops on the reader's own floor instead of running into the bottom margin.
    """
    baseline = max(_END_MARK_FLOOR_POINTS, flow_bottom - _END_MARK_DROP_POINTS)
    return flow_bottom + _END_MARK_PAINT_POINTS - _END_MARK_DROP_POINTS - baseline


def _apply_end_marks(tree: Element, offsets: Mapping[str, float]) -> None:
    """Paint each article's end mark at the offset its own page earned."""
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
    """Reader pages up to and including the last page of body content.

    This is ``self.page`` at the moment ``render.back_cover`` runs: everything
    from the two front cover slots through the last article page.  The first
    closing plate marks the boundary; with no plate left to mark it, the two
    trailing cover slots do.
    """
    for page_number, page in enumerate(document.pages, start=1):
        for box in _walk_boxes(page._page_box):
            element = getattr(box, "element", None)
            if element is not None and "closing-plate" in _element_classes(element):
                return page_number - 1
    return len(document.pages) - 2


def _signature_closing_plates(edition: Edition, content_pages: int) -> int:
    """The plate count ``render.back_cover`` (render.py:2198-2209) derives.

    The signature is closed by plates, so their number is arithmetic on where the
    body stopped: reserve the blank inside back cover and the back cover, round
    the total up to the fold's four pages, and fill the difference.
    """
    configured = edition.raw.get("format", {}).get("target_pages")
    minimum_total = content_pages + 2
    target = int(configured) if configured else ((minimum_total + 3) // 4) * 4
    target = max(target, minimum_total)
    target = ((target + 3) // 4) * 4
    return target - 2 - content_pages


def _article_flow_bottom(document: Any, article_id: str) -> float:
    """ReportLab's ``self.y`` where an article's flow ends, in points from the foot.

    ReportLab tracks a baseline and subtracts each block's leading and space-after
    from it; CSS stacks margin boxes.  The two agree exactly once the *margin* box
    is measured -- ``self.y`` after a block is that block's margin-box foot -- and
    once the difference between the frame top and a content box derived from the
    first baseline is removed.  Measured against ReportLab on both languages, this
    reproduces ``self.y`` to the third decimal on every article whose last page
    carries the same copy.  The tail ornament is excluded from the walk because it
    is exactly what this measurement decides.
    """
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
        raise ValidationError(
            f"WeasyPrint placed no in-flow content for article {article_id}"
        )
    return _PAGE_HEIGHT_POINTS - lowest - _FIRST_BASELINE_INSET_POINTS


def _article_flow_boxes(box: Any, article_id: str, *, inside: bool = False) -> Iterable[Any]:
    element = getattr(box, "element", None)
    if element is not None and "article-tail" in _element_classes(element):
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


def _tail_ornament_height(flow_bottom: float) -> float | None:
    """``_article_tail_ornament_box`` (render.py:218-231), as a height or nothing.

    The motif is drawn only where an article genuinely ends high on its page, and
    it never displaces a line: it occupies the frame's foot, which is why the
    stylesheet takes it out of flow entirely.
    """
    endmark_baseline = max(_FRAME_BOTTOM_POINTS + 5.0, flow_bottom - 1.0)
    available = (
        endmark_baseline
        - _TAIL_ORNAMENT_ENDMARK_CLEARANCE
        - (_FRAME_BOTTOM_POINTS + _TAIL_ORNAMENT_FOOT_INSET)
    )
    if available < _TAIL_ORNAMENT_MIN_HEIGHT:
        return None
    return min(available, _TAIL_ORNAMENT_MAX_HEIGHT)


def _validate_caps(edition: Edition) -> None:
    format_data = edition.raw.get("format", {})
    for key, expected in (
        ("max_article_pages", _MAX_ARTICLE_PAGES),
        ("max_editorial_pages", _MAX_EDITORIAL_PAGES),
    ):
        value = format_data.get(key, expected)
        try:
            value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"format.{key} must be the integer {expected}") from exc
        if value != expected:
            raise ValidationError(
                f"format.{key} is a hard publication rule and must remain {expected}"
            )


def _measure_layout(
    document: Any,
    assets: tuple[HtmlAsset, ...],
    design: str,
    plan: ReaderPlan | None = None,
) -> RenderLayout:
    article_pages: dict[str, set[int]] = {}
    editorial_pages: set[int] = set()
    destinations: dict[str, int] = {}
    image_boxes: list[tuple[HtmlAsset, int, Any, Any]] = []
    assets_by_source: dict[str, list[HtmlAsset]] = {}
    # Every raster the plan expects on a page is looked for, so that a plate or a
    # tail motif that silently failed to place is still an error here.
    placed_assets = tuple(
        asset
        for asset in assets
        if asset.role in {"figure", "article_tail", "closing_plate"}
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
            attributes = getattr(element, "attrib", {})
            article_id = attributes.get("data-article-id")
            if article_id and getattr(box, "element_tag", None) == "article":
                article_pages.setdefault(article_id, set()).add(page_number)
            if attributes.get("id") == "editorial" and getattr(box, "element_tag", None) == "section":
                editorial_pages.add(page_number)
            identifier = attributes.get("id")
            if identifier and identifier not in destinations:
                destinations[identifier] = page_number
            if getattr(box, "element_tag", None) == "img":
                # A contrast-treated figure carries a data URI, so the asset it
                # belongs to is named by the source the edition curated.
                source = attributes.get("data-print-source") or attributes.get("src")
                candidates = assets_by_source.get(source, [])
                occurrence = source_occurrences.get(source or "", 0)
                if occurrence < len(candidates):
                    image_boxes.append((candidates[occurrence], page_number, box, rotor))
                    source_occurrences[source or ""] = occurrence + 1

    toc: dict[str, int] = {}
    if "editorial" in destinations:
        toc["editorial"] = destinations["editorial"]
    # Keep the established RenderLayout convention: article ids are keys, while
    # auxiliary sections use their stable semantic destination ids.
    for article_id in article_pages:
        destination = f"article-{article_id}"
        if destination in destinations:
            toc[article_id] = destinations[destination]
    for identifier, page_number in destinations.items():
        if identifier.startswith("section-"):
            toc[identifier] = page_number

    # A ``FigurePlacement`` is the reader's record of a *curated figure* and of
    # nothing else: ``render.py`` appends one at :814 and :1096 only, both
    # curated-figure paths, and never for a tail motif or a closing plate.  The
    # distinction is not cosmetic downstream.  ``preflight`` (preflight.py:85-124)
    # raises a low-resolution finding for every placement under MIN_FIGURE_PPI and
    # writes a print-contrast row for each one; the closing plates resolve to about
    # 242 ppi at the full-bleed size the reader draws them, and neither plate nor
    # tail art is ever contrast-treated.  Admitting furniture here would therefore
    # manufacture three low-resolution findings per language the ReportLab reader
    # never raised.  No PDF gate can see this, which is why it is stated here.
    #
    # Measured against the frozen manifest's ``layout.figures``: 8 placements in
    # each language, in the same order, with the same id, article, page, pixel
    # dimensions and effective ppi.  14 of the 16 boxes are character-identical.
    # The two that are not are ``mcp-web-ui-comparison``, whose reported ``y``
    # is 295.331 against the manifest's 295.332 in English and 154.531 against
    # 154.532 in Spanish: the unrounded value is 295.331493, so the pipelines
    # differ by 0.0005pt on that one datum and the third decimal rounds the
    # other way.  It is not the rasteriser nudge -- ``_reader_y_points`` takes
    # that back out -- and no other figure carries it.
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
        toc=toc,
        article_pages={key: len(value) for key, value in article_pages.items()},
        editorial_pages=len(editorial_pages) if editorial_pages else None,
        design=design,
        cover_art_size_points=None,
        article_frame_usage={},
        article_terminal_balance={},
        figure_placements=placements,
    )


def _asset_is_placed(asset: HtmlAsset, plan: ReaderPlan | None) -> bool:
    """Whether the reader was laid out with this asset on a page at all.

    An edition's inventory offers every closing plate and every tail motif; the
    plan decides how many plates the signature needs and which tails the pages
    have room for, so the inventory alone cannot say what should have been found.
    """
    if plan is None:
        return True
    if asset.role == "closing_plate":
        return int(str(asset.id).rsplit("-", 1)[-1]) <= plan.closing_plates
    if asset.role == "article_tail":
        return asset.article_id in plan.tail_heights
    return True


def _walk_boxes(box: Any) -> Iterable[Any]:
    yield box
    for child in getattr(box, "children", ()):
        yield from _walk_boxes(child)


def _walk_boxes_in_frame(box: Any, rotor: Any = None) -> Iterable[tuple[Any, Any]]:
    """Every box, paired with the rotated plate frame it is laid out inside, if any.

    A plate's boxes are laid out upright and painted sideways, so their own
    ``position_x``/``position_y`` are frame coordinates rather than page
    coordinates.  Carrying the frame down the walk is what lets a placement be
    reported where the ink actually lands.
    """
    element = getattr(box, "element", None)
    if element is not None and "landscape-plate-rotor" in _element_classes(element):
        rotor = box
    yield box, rotor
    for child in getattr(box, "children", ()):
        yield from _walk_boxes_in_frame(child, rotor)


def _figure_placement(
    asset: HtmlAsset, page: int, box: Any, rotor: Any = None
) -> FigurePlacement:
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
    # Weasy box positions start at the physical page's top-left, and `position_x`
    # is the *margin* box corner while `width` is the content box -- so the image's
    # own rectangle is the content box.  Preflight uses PDF coordinates, whose
    # origin is the bottom-left of A5 (595.276 points).
    box_x = float(box.content_box_x()) * _POINTS_PER_CSS_PIXEL
    box_y = float(box.content_box_y()) * _POINTS_PER_CSS_PIXEL
    if rotor is None:
        x, y, width, height = box_x, _reader_y_points(box_y, box_height), box_width, box_height
    else:
        x, y, width, height = _rotated_plate_box(box_x, box_y, box_width, box_height, rotor)
    if width <= 0 or height <= 0:
        raise ValidationError(f"Curated figure {asset.figure_id} has an empty WeasyPrint image box")
    # Resolution is a property of the image, not of the page: a plate's rectangle
    # is reported turned a quarter turn, but its pixels are not.
    ppi = min(dimensions[0] / (box_width / 72), dimensions[1] / (box_height / 72))
    # ``_draw_figure`` (render.py:804-813) and ``_landscape_plate``
    # (render.py:1086-1095) both refuse a curated figure that resolves under
    # MIN_FIGURE_PPI at the placement it just received, in the same words.  It is
    # a placement rule and not an inventory rule: the same file is acceptable in a
    # smaller box.  Furniture drawn with ``_draw_image_fill`` -- a tail motif, a
    # closing plate -- is not checked at all, so neither is it here.
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
        rights_status=str(asset.rights_status or "unknown"),
    )


def _rotated_plate_box(
    box_x: float, box_y: float, box_width: float, box_height: float, rotor: Any
) -> tuple[float, float, float, float]:
    """A plate box's PDF rectangle, given its position inside the rotated frame.

    The stylesheet lays a plate out in an upright ``498.2756 x 333.008`` frame and
    then rotates it a quarter turn clockwise about its own head, so the frame's
    inline axis runs *down* the page and its block axis runs *right to left* from
    the live area's right edge.  Undoing that here is what makes a plate's
    reported placement the rectangle ReportLab records for the same figure.
    """
    rotor_x = float(rotor.position_x) * _POINTS_PER_CSS_PIXEL
    rotor_y = float(rotor.position_y) * _POINTS_PER_CSS_PIXEL
    along = box_x - rotor_x  # down the page, once rotated
    across = box_y - rotor_y  # leftward from the frame's right edge
    left = rotor_x + _PLATE_FRAME_ACROSS_POINTS - across - box_height
    top = rotor_y + _FIRST_BASELINE_INSET_POINTS + along
    return left, _reader_y_points(top, box_width), box_height, box_width


def _validate_layout_caps(layout: RenderLayout) -> None:
    overlong = [
        f"{article_id} ({count} pages)"
        for article_id, count in layout.article_pages.items()
        if count > _MAX_ARTICLE_PAGES
    ]
    if overlong:
        raise ValidationError(
            "WeasyPrint article page cap exceeded (maximum 7): " + ", ".join(overlong)
        )
    if layout.editorial_pages is not None and layout.editorial_pages > _MAX_EDITORIAL_PAGES:
        raise ValidationError(
            f"WeasyPrint editorial page cap exceeded: {layout.editorial_pages} pages (maximum 2)"
        )


def _validate_cover_slots(document: Any) -> None:
    if len(document.pages) < 4:
        raise ValidationError("WeasyPrint reader must contain cover and inside-cover placeholders")
    # Named pages provide a renderer-level assertion: no semantic content is
    # allowed in either inside cover, regardless of its extracted text.
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


def _validate_reader_measures(document: Any) -> None:
    """Refuse a token the measure cannot hold rather than letting it overflow.

    ``lines`` has a second, per-character pass for a token wider than the
    measure (render.py:664-673): it fills the *whole* measure greedily, one
    character at a time, and hands each chunk to the whitespace wrap as if it
    were a word.  Two things follow.  The chunk always opens a line, because any
    preceding copy plus a space already exceeds the measure; and the break falls
    wherever the next character no longer fits, never at a hyphen or a solidus.

    Measured against exactly that: with ``overflow-wrap: anywhere`` and no
    nowrap box, Pango reproduces the reader's chunks character for character on
    a token with no internal break opportunity, and *diverges* as soon as the
    token has one -- a 269-character hyphenated token breaks 68/67/67/66/1 in
    the reader and 66/66/66/66/5 in Pango, and a 164-character URL 62/56/46
    against 61/41/62.  So no stylesheet spelling reproduces the fallback for the
    tokens that would actually need it, and the honest thing is to fail loudly:
    this edition's widest set token is far inside its measure, and the day one
    is not, the fix is to pre-split it here on the reader's own chunks.
    """
    overlong: list[str] = []
    for page_number, page in enumerate(document.pages, start=1):
        _collect_overlong_lines(page._page_box, None, page_number, overlong)
    if overlong:
        raise ValidationError(
            "WeasyPrint set a reader token wider than its own measure, which the "
            "reader would have broken between characters: " + "; ".join(overlong[:5])
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


def _validate_contents_page(document: Any) -> None:
    """The print reader begins with contents after the two front-cover slots."""
    if len(document.pages) < 3:
        raise ValidationError("WeasyPrint reader has no logical contents page")
    for box in _walk_boxes(document.pages[2]._page_box):
        element = getattr(box, "element", None)
        if element is not None and getattr(element, "attrib", {}).get(
            "data-edition-navigation"
        ) == "contents":
            return
    raise ValidationError("WeasyPrint contents must begin on logical reader page 3")
