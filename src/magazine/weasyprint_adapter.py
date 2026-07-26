"""Experimental, isolated A5 reader-PDF adapter backed by WeasyPrint.

This module deliberately does not participate in the compiler or CLI.  Its
single public interface turns the renderer-neutral semantic HTML edition into
an A5 reading-order PDF whose first/last pages are replace-only cover slots.
The existing cover compiler and A4 booklet imposition remain authoritative.
"""

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
from typing import Any, NamedTuple
from urllib.parse import quote
from xml.etree.ElementTree import Element, SubElement

from .errors import DependencyError, ValidationError
from .html_edition import HtmlAsset, render_html_edition
from .manifest import Edition
from .reader_text import fold_reader_characters
from .render import FigurePlacement, RenderLayout


WEASYPRINT_DESIGN = "WeasyPrint / A5 fold proof"

SHAPING_SCAFFOLDS: tuple[str, ...] = ()
"""What this renderer gives up to line-break identically to ``render.render_a5``.

Nothing, as of the re-baseline.  Three measures used to live here -- ``font-
kerning: none``, ``font-variant-ligatures: none`` and one ``white-space:
nowrap`` box per whitespace token -- and they held Pango down to what ReportLab
could do so that the two renderers were interchangeable.  They were an
equivalence scaffold, not a design decision, and they came out together; this
renderer now kerns, ligates and takes Pango's own intra-token break
opportunities.  See "Re-enable shaping and re-baseline" in
``docs/RENDERER_MIGRATION.md``.

The tuple itself stays, empty, because it is the artifact's contract: a build
records it in its manifest whenever it is non-empty, so anything a future change
holds down to match another producer has to be declared here and becomes visible
in the packaged edition rather than only in a document.
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


# ``_article_tail_ornament_box`` (render.py:218-231), as much of it as still
# decides anything.  The motif does not print -- the source code took the slot --
# and two of its four numbers went with it, deliberately:
#
# ``ARTICLE_TAIL_ORNAMENT_MIN_HEIGHT`` (118) was the height under which a
# *decorative* band was not worth printing, and refusing a tight fit is the right
# instinct for ornament.  It is the wrong instinct for a functional element: a
# code three points inside its budget scans exactly as well as one with a page to
# spare, and the two pages this threshold turned away -- en p18 and es p31 -- were
# carrying the close-up code under 70mm of visible white.  ``_CODE_TAIL_MIN_ROOM``
# replaces it with the test the code actually has: is there room for a square at
# least twice the foot slot's, so that the two sizes stay two classes.
#
# ``ARTICLE_TAIL_ORNAMENT_FOOT_INSET`` (24) was how far a band had to stop above
# the frame's foot so as not to crowd the page's own foot.  The code is anchored
# to the *top* of the slot (see ``_apply_source_codes``) and so never stands on
# the slot's foot at all; what bounds it below is ``_END_MARK_FLOOR_POINTS``, the
# floor the publication already gives the last piece of type on a page.
#
# The two that survive are the two that were never about ornament.
_TAIL_ORNAMENT_MAX_HEIGHT = 214.0
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

# THE SOURCE CODE.
#
# A print magazine cannot hyperlink, so every article carries the address of the
# source it was built from as a QR square.  The numbers below decide what that
# square is and where it stands, and each is a print decision rather than a taste:
#
# ``_CODE_HOUSE_MODULE_POINTS`` is the module -- one cell of the symbol -- at the
# size the publication sets a code it has room for.  0.85mm is comfortably above
# every published floor for a code read by a phone off uncoated stock, and it is
# what makes the largest symbol this publication can produce (a 71-character URL
# at ECC-H, 49 modules across the quiet zone) land at 41.65mm.  The house size is
# therefore not a point size: the *module* is fixed and the square is
# `modules * module`, so a short URL genuinely prints a smaller code than a long
# one.
#
# ``_CODE_MIN_MODULE_POINTS`` is the floor, and it is the number the design gives
# way at.  0.35mm is 4.1 dots of a 300 dpi inkjet and about where a phone camera
# held at an angle over uncoated paper stops being reliable.  A build whose code
# cannot be set at this module at any error correction level refuses rather than
# printing something that will not scan.
#
# ``_CODE_QUIET_MODULES`` is the QR standard's own four-module quiet zone, and it
# is inside the element rather than assumed of the page.  The foot slot's code
# stands two points under the last line of a full page; borrowing its quiet zone
# from whatever happens to be there is the one way this feature fails silently.
# It is also why the element's edges are not the symbol's: everything the eye
# lines the code up against below is measured to the *first dark module*, four
# modules inside the box.
#
# ``_CODE_FOOT_CLEARANCE_POINTS`` is how far above the sheet's own foot the small
# code's box may come.  The reader is folded from A4 at home and the A5 page foot
# *is* the sheet's physical edge, so that edge is a real edge and not a trim: the
# 4mm this used to be is inside what many domestic printers reserve on the
# trailing edge before duplex feed skew of 1-2mm is added, and nothing occupied
# that band before the code did.  5mm on the box, and the folio pin below puts the
# nearest dark module 6.9mm up.
_CODE_HOUSE_MODULE_POINTS = 0.85 * 72 / 25.4
_CODE_MIN_MODULE_POINTS = 0.35 * 72 / 25.4
_CODE_QUIET_MODULES = 4
_CODE_FOOT_CLEARANCE_POINTS = 5.0 * 72 / 25.4
# Highest first, which is the tie-break and no longer the choice.
# ``_fitted_source_code`` takes the level whose symbol comes out with the *widest
# cell* in the room it has, and only where two levels tie -- which is every slot
# roomy enough to set the house module -- does the higher correction win.  That is
# what the comment here always claimed and what the code did not do: it took the
# first level clearing the floor, i.e. the highest correction that fit, which for
# this edition's 51-character URLs meant ECC-M at a 375um module where ECC-L sets
# the same square at 415um.  For a small printed code module width buys more read
# reliability than redundancy does, so the rule now matches the reasoning.
_CODE_ERROR_LEVELS = ("H", "Q", "M", "L")
# The reading measure's own left edge inside the page area, as ``.article-tail``
# has it: the article box is 325pt centred in the 333.0079pt live width.
_CODE_MEASURE_LEFT_POINTS = 4.004
_CODE_MEASURE_POINTS = 325.0
# The page's content-box foot, from the page's own foot: below this the reading
# flow sets no type at all, and it is the ceiling on the foot slot.
_CODE_CONTENT_FOOT_POINTS = _PAGE_MARGIN_BOTTOM_POINTS - _RASTER_NUDGE_POINTS
# FOLIO_BASELINE (render.py:565-577), and the foot slot's own pin.  The small code
# shares its band with the folio, and the folio is a *line*: the publication name
# at one end and the page number at the other, both on 19.5.  A square dropped
# into that band with its dark modules ending 1.65pt under that line does not read
# as the third item on it -- it reads as a code that slipped off the foot.  So the
# module is chosen to land the symbol's own bottom edge exactly on the folio
# baseline, and the four light modules below it fall into the sheet's foot margin
# where they cost nothing: white quiet zone is the one part of a symbol a
# printer's unprintable margin may safely eat.
_FOLIO_BASELINE_POINTS = 19.5
_CODE_FOOT_DROP_POINTS = _CODE_CONTENT_FOOT_POINTS - _FOLIO_BASELINE_POINTS
# The ceiling on the small code's box, kept as an independent guard: whichever of
# the folio pin and the sheet-edge clearance is tighter is the one that binds.
_CODE_FOOT_ROOM_POINTS = _CODE_CONTENT_FOOT_POINTS - _CODE_FOOT_CLEARANCE_POINTS
# The tail slot is admitted only where it can hold a square at least twice the
# foot slot's.  Two sizes of code on one edition is a legible system; a continuum
# between them is not, and the ratio is what stops a page with barely enough room
# from printing a code that is neither.
_CODE_TAIL_MIN_ROOM_POINTS = 2.0 * _CODE_FOOT_ROOM_POINTS
# AND THE TAIL SLOT HAS A CEILING AS WELL AS A FLOOR, because "is there room?" was
# never the right question on its own.  ``_CODE_TAIL_MIN_ROOM`` asks whether the
# page *can* carry the large code; this asks whether the page is the kind of page
# that should.  A 41.6mm square reads as furniture under an article that ran to
# the foot of its last page and as a poster on an article that ended after six
# lines -- on en p24 the code carried 59.5% of the page's ink at 51.9% local
# coverage, and the rest of the sheet was a black square and half a page of
# nothing.  Residual white below the code box, on the nine large codes of edition
# 002, sorts as
#
#   18.0 18.3 34.4 64.1 | 89.0 98.2 98.2 102.8 107.4  (mm)
#
# and the four on the left are the pages where the square closes the page.  60mm
# is inside the 29.7mm gap that separates them from the rest, 25.6mm above the
# largest of the four; it is not a tuned number and would classify this edition
# identically anywhere between 35mm and 88mm.
#
# Where the ceiling bites the code takes the foot slot instead -- it joins the
# folio's own line, where the publication's other foot chrome already lives,
# instead of standing alone in the void.  The preference is a preference and not
# a refusal: a URL whose symbol cannot be set in the foot band at
# ``_CODE_MIN_MODULE_POINTS`` keeps the tail slot it had already earned, because
# an unscannable small code is worse than an over-large legible one.
_CODE_TAIL_MAX_FOOT_WHITE_POINTS = 60.0 * 72 / 25.4
# The code's label, in the house's own tracked-caps idiom -- `FEATURE nn`,
# `FIGURE nn`, `END / nn` -- set on the symbol's own bottom edge, one gap to its
# right.  It is what makes the square furniture rather than a sticker applied
# after printing: an unlabelled black square is the only element on the page that
# does not say what it is.  It is a *name* and not the address -- the URL is set
# nowhere, in print or in the margin.
_CODE_LABEL_SIZE_POINTS = 6.8
_CODE_LABEL_TRACKING_POINTS = .25
# Its gap from the square is ``_CODE_LABEL_GAP_POINTS``, which is the end mark's
# own and is therefore declared with the end mark, below.
# The resolution the decode gate rasterises at.  300 ppi is the publication's own
# print floor -- ``_MIN_FIGURE_PPI`` -- so the gate reads the code off the page at
# the density the page is judged to be printable at, and not at a density chosen
# to make a code pass.
_CODE_DECODE_DPI = 300
# The four corners a decoded symbol reports must land on the box the adapter
# placed, or the gate has read some other mark and proved nothing.  Two points is
# under one device pixel at 300 ppi, doubled for the binariser's own edge.
_CODE_POSITION_TOLERANCE_POINTS = 2.0
# Two modules are the same width when they differ by less than this, which is a
# ten-thousandth of the smallest cell this module will print.  It exists so that
# "the widest cell wins, highest correction breaks the tie" is decided on the
# geometry and not on the last bit of a float division.
_MODULE_EPSILON = 1e-9
# What an article puts on its last page *after* its flow has ended, and which
# ``_article_flow_bottom`` therefore may not measure: all three are positioned
# from the very number that walk produces.
_OUT_OF_FLOW_CODA_CLASSES = frozenset({"article-tail", "source-code", "source-label"})
# ``render.py``'s own INK and the sheet, written as the percentages those tuples
# are, exactly as the stylesheet writes them, so the code's ink is the
# publication's and not a colour invented for a barcode.  ONE INK, deliberately:
# see ``_source_code_source``.
_CODE_INK = "rgb(5.5%,7.5%,8.5%)"
_CODE_PAPER = "rgb(100%,100%,100%)"

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
# ``_closing_plate``'s own fit: 32pt down to 22, at most two lines of
# ``grid_box(0, 5)``, standing no taller than 92pt.
_PLATE_TITLE_BOX_HEIGHT = 92.0
_PLATE_TITLE_MAX = 32.0
_PLATE_TITLE_MIN = 22.0
_PLATE_TITLE_MAX_LINES = 2

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
# ``baseline = max(self.frame_bottom + 5, self.y - 1)``.  The reader's own floor,
# and it is the *frame's* number and not the mark's: it stops the mark running
# into the bottom margin and says nothing at all about the type above it.  See
# ``_end_mark_baseline`` for what happens on the one page where it bites.
_END_MARK_FLOOR_POINTS = _FRAME_BOTTOM_POINTS + 5.0
_END_MARK_DROP_POINTS = 1.0
# How far `END / nn` stands in from the frame's left edge, past its own rule
# (render.py:2008-2021, `.end-mark`'s `padding-left`), and how wide that rule is.
# The inset is borrowed as the house's own answer to "how far apart are two
# pieces of furniture on the same line", which is what the foot slot's code needs
# to hold itself off a clamped mark.
_END_MARK_TEXT_INSET_POINTS = 24.0
_END_MARK_RULE_WIDTH_POINTS = 17.0
# The lowest baseline the mark may take before the build is refused -- the folio's
# own line plus one reading leading.  It is a floor against *collision*, which is
# the only thing a floor down here can honestly be about: `END / nn` and the
# folio are both 6.8pt tracked caps, and two of them closer than the distance the
# reader sets two lines of prose at read as one line of chrome rather than as an
# article ending above a page number.  See ``_end_mark_baseline``.
_END_MARK_HARD_FLOOR_POINTS = _FOLIO_BASELINE_POINTS + _READING_LEADING
# And the difference between them is the house's answer to the narrower question
# "how far from a mark does the mark's own name set?" -- 7pt, ink to ink.  The
# source label is the same kind of thing naming the same kind of thing, so it
# takes the same gap, measured from the square's last dark module and not from
# the element's edge: the quiet zone lives inside the element, so a gap stated on
# the box is a gap plus four light modules on the page.  At 12pt from the box
# that put `SOURCE / nn` 7.9mm from anything visible, three times what `END / nn`
# gets, and the two stopped reading as one idiom.
_CODE_LABEL_GAP_POINTS = _END_MARK_TEXT_INSET_POINTS - _END_MARK_RULE_WIDTH_POINTS

_FONT_FILES = {
    "serif": "source-serif-4/SourceSerif4SmText-Regular.ttf",
    "serif-display": "source-serif-4/SourceSerif4Display-Semibold.ttf",
    "sans-medium": "inter/Inter-Medium.ttf",
    "sans-semibold": "inter/Inter-SemiBold.ttf",
}

_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MARKDOWN_EMPHASIS = re.compile(r"[*`]")

# A line box is over its measure only when it exceeds it by more than float
# noise; 0.01 CSS px is four thousandths of a point.
_TOKEN_MEASURE_EPSILON = 0.01

# A fitted block has outgrown its reserved field only past float noise.  A real
# overflow is a whole line of display type -- tens of points -- so a hundredth of
# a point is not a threshold anything can be tuned against.
_FIELD_OVERFLOW_EPSILON = 0.01

# RUNT CONTROL.  A paragraph whose last line is one short word leaves a word
# stranded over white space, and a reader notices it without knowing why.  CSS
# has no primitive for it: `orphans` and `widows` count *lines across a page
# break* and say nothing about the shape of a paragraph's own last line.  The
# typesetter's fix is older than CSS -- bind the last two words with a
# non-breaking space so they wrap together -- and it is applied here, on the
# print tree, from a measurement of the laid-out page.
#
# THE THRESHOLD IS MEASURED, NOT CHOSEN.  A single-word last line is only a
# defect when the word is *short*; a long final word filling a fifth of the
# measure reads as an ordinary short line.  Every single-word last line in
# edition 002, as a fraction of its own measure, sorts as
#
#   3.2 7.5 7.8 7.8 9.9 10.3 10.3 10.5 11.6 13.3 13.7 13.9 14.6 | 16.4 16.8
#   17.6 18.0 18.2 18.9 21.0 21.4  (percent, both languages, 21 paragraphs)
#
# and the independent review put its own line inside that gap: it refused
# `context.` at 11.6% and accepted `irreversible.` at 17.6%.  There is no
# observation at all between 14.6% and 16.4%, so 15% is not a tuned number --
# it can move by +/-0.7 points without reclassifying a single paragraph.
_RUNT_MEASURE_FRACTION = .15
#
# AND THE CURE HAS ITS OWN THRESHOLD.  The bind moves the penultimate line's last
# word down with the stranded one, so the line above pays for the repair with
# whatever that word was wide.  Where the bound word is long enough the payment
# really is worse than the defect, and this is the refusal that says so.
#
# IT WAS SET AT A FIFTH AND A FIFTH WAS TOO TIGHT.  The distribution argument for
# 20% was sound -- 4.2 points is the widest gap in the observed rags -- and the
# conclusion drawn from it was still wrong, because the two sides of that gap are
# not the same *kind* of thing.  A penultimate line 22-30% short of the measure
# is rag; this column is set unjustified and every page of it carries lines
# shorter than that.  A last line of one seven-letter word is a runt whatever
# stands above it.  Trading the second for the first is not a trade at all, and
# an independent review measured what the trade actually shipped:
#
#              penultimate rag        last line
#   en p11     23.7% -> 7.3%     99.4pt -> 45.3pt   `packages.`
#   en p29     30.5% -> 12.0%    98.6pt -> 37.8pt   `context.`
#   p31 ref 4  24.5% -> 6.5%     76.5pt -> 17.1pt   `2025.`   (both languages)
#   p31 ref 6  23.8% -> 5.8%     76.5pt -> 17.1pt   `2023.`   (both languages)
#
# `surrounding context.` at 98.6pt was a good last line and `context.` at 37.8pt
# is a runt; on en p11 the refusal put three one-word last lines -- `packages.`,
# `distribution.`, `and fixes.` -- inside twenty lines of one column.  Every
# paragraph the refusal touched came out worse than if it had never fired.
#
# So it moves to a third, which is above every bind this edition asks for.  Every
# bind, as the rag its penultimate line would be left with, sorts as
#
#   4.9 8.4 9.7 9.8 10.3 10.3 10.7 11.6 12.3 12.7 17.3 17.8 18.4
#   22.6 23.8 23.8 24.6 24.6 29.5 | (percent, both languages, 18 binds)
#
# and 33% clears the largest of them by 3.5 points.  That is deliberate and is
# the honest description of the rule now: on edition 002 it refuses nothing, and
# what it still guards is the case the observations do not reach -- a final word
# so long that carrying it down would halve the line above it.  The number can
# move by -3.5 or by as much as one likes upward without reclassifying a single
# paragraph in this edition, which is another way of saying this edition no
# longer measures it.  A future edition that lands a bind in the twenties should
# leave it alone; one that lands a bind past a third should re-read this note
# before moving the number again.
#
# What the earlier value cost, and what going back to it would cost again: the
# two reference-list entries ending on a bare year, in each language, were among
# the binds it refused.  Those turn lines now hang under `ul[data-reference-list]`'s
# own indent, so a reference ending on `2025.` is ordinary bibliography setting
# and no longer depends on this rule at all -- but the bind is what keeps the
# year on the line its citation ends on, and it is allowed again.
_RUNT_MAX_RAG_FRACTION = .33

# The tag names that can carry the reading flow's own prose.  A heading is
# deliberately absent: an opener title and a plate title are auto-fitted, and
# `_validate_fitted_display` checks the laid-out line count against the count
# the fit reserved room for -- binding words inside one would move that line
# count out from under its own guard.
_BINDABLE_TAGS = frozenset({"p", "li", "span"})
# Chrome is not prose.  Each of these is drawn with its own fixed metrics inside
# a field whose height the adapter states, so a bind that changed its line count
# would change a reserved field rather than a rag.
_UNBINDABLE_CLASSES = frozenset(
    {
        "author-note", "byline", "content-label", "contents-kicker", "end-mark",
        "entry-author", "entry-folio", "entry-label", "entry-title", "folio-name",
        "issue-number", "label-primary", "label-secondary", "provenance",
        "publication-name", "running-head", "source-label", "subtitle",
    }
)
# Subtrees the reading flow does not include at all: opener chrome, the contents
# sheet, the hidden edition header, and preformatted text, whose whitespace is
# authored content that no pass here may rewrite.
_UNBINDABLE_SUBTREES = frozenset({"header", "nav", "pre", "code"})
_RUNT_KEY = "data-runt-key"
_NO_BREAK_SPACE = "\u00a0"


@lru_cache(maxsize=None)
def _advance_widths(face: str) -> dict[str, float]:
    """Each character's advance in ems, as ``pdfmetrics.stringWidth`` sums them.

    Reading the advances straight out of the bundled face is what lets this
    module answer "how many lines, at what size?" for the places the reader
    auto-fits display type -- an opener, a closing plate -- and for the block
    heights ``_evidence_band`` decides on, without a second typesetter having to
    lay the text out.

    This is ``lines``'s measure (render.py:658-685): a plain sum of advances,
    kerning and ligatures ignored.  Since the shaping scaffolds came out it is no
    longer the measure Pango uses to set the same text, and **it is not an upper
    bound on it**.  Ligatures do only ever narrow in these faces, but kerning
    goes both ways: restricted to cp1252 pairs of the ``kern`` feature, 12,794
    pairs tighten and 3,019 loosen in ``SourceSerif4Display-Semibold``, 10,252 /
    1,164 in ``SourceSerif4SmText-Regular``, 5,254 / 911 in ``Inter-SemiBold``.
    ``Lo`` +17, ``La`` +21, ``Có`` +11, ``tr`` +10, ``oo`` +9 units per 1000 are
    ordinary pairs, and five edition-002 title lines already set wider shaped
    than summed.  A fitted size can therefore be one Pango wraps.

    It is still deliberately not corrected by shaping here: the fitted sizes and
    the band arithmetic are reproductions of ``render.py``'s own decisions, and
    those are made on unshaped advances -- shaping this would change the
    publication rather than fix it.  What catches the divergence instead is
    ``_validate_fitted_display``, which measures the laid-out boxes and refuses a
    build whose display type outgrew the room fitted for it.  Any new caller of
    this function that reserves space on a prediction needs a clause there too.
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
    _validate_layout_caps(edition, layout)
    _validate_cover_slots(document)
    _validate_contents_page(document)
    _validate_reader_measures(document)
    _validate_fitted_display(document, edition)
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
    # After the bytes exist and before they reach the disk: the source codes are
    # the one thing here that can only be judged on the rasterised page, so the
    # gate is given the finished PDF rather than the box tree, and a reader that
    # fails it is never written.
    _validate_source_codes(
        pdf_bytes, edition, plan.source_codes, _measured_source_code_boxes(document)
    )
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


@dataclass(frozen=True, slots=True, order=True)
class SourceCode:
    """One article's printed way back to the source it was built from.

    Everything here is decided from a laid-out page and a URL, and nothing from
    what an author committed: ``slot`` is ``"tail"`` where the article's last
    page has the open space ``_tail_code_slot`` demands and ``"foot"`` where it
    has not, ``error`` is the QR error correction that comes out with the widest
    cell in that room, ``modules`` is the symbol's width in cells *including* its
    four-module quiet zone, and ``module`` is one cell in points.  The square is
    ``modules * module`` on a side, so an edition that committed no art at all
    still prints a code in every slot that fits one.

    ``left`` and ``top`` are the placement the same measurement implies, in the
    page content box's own coordinates: ``left`` from its left edge, ``top`` from
    its foot, positive upward.  They are carried on the plan rather than
    recomputed at paint time because both are read off a laid-out page -- ``top``
    from where the end mark landed, ``left`` from how wide the end mark's own
    line came out -- and the plan is what the settle check compares.
    """

    article_id: str
    slot: str
    error: str
    modules: int
    module: float
    url: str
    left: float = _CODE_MEASURE_LEFT_POINTS
    top: float = 0.0

    @property
    def side(self) -> float:
        return self.modules * self.module

    @property
    def quiet(self) -> float:
        """The quiet zone, in points: four light modules on every side."""
        return _CODE_QUIET_MODULES * self.module

    @property
    def symbol_bottom(self) -> float:
        """The first dark module's own lower edge, in the same coordinates.

        Not ``top - side``: four light modules of quiet zone stand below the
        symbol, and every alignment the page is judged on -- the folio's
        baseline, the label's -- is an alignment to ink.
        """
        return self.top - self.side + self.quiet

    @property
    def symbol_left(self) -> float:
        """The first dark module's own left edge, in the same coordinates.

        The same correction as ``symbol_bottom`` and for the same reason.  A
        column is flush when its *ink* is flush: the tail slot's square is set
        against the reading measure's own origin, which is where the END rule
        and every line of the article above it start, and the element therefore
        stands one quiet zone to the left of it.
        """
        return self.left + self.quiet

    @property
    def symbol_right(self) -> float:
        """The last dark module's own right edge, in the same coordinates."""
        return self.left + self.side - self.quiet


@dataclass(frozen=True, slots=True)
class ReaderPlan:
    """The placement decisions that no stylesheet can reach on its own.

    ``closing_plates`` is the number of plates the signature arithmetic in
    ``render.back_cover`` asks for, which is a function of where the content
    happens to end.  ``source_codes`` is one :class:`SourceCode` per article that
    has a source to point at, sized and slotted from where that article's own
    flow ended.  ``adaptive_images`` maps a figure id to the image height an
    ``adaptive_band`` has been shrunk to so that it can still bridge the page it
    started on (render.py:901-922), and omits every band that fits at its full
    height.  ``band_offsets`` maps a figure id to the margin mirror a band
    inherited from the page it was dispatched from, and omits every band that
    stayed there.  ``end_marks`` maps an article id to the distance its end mark
    is painted back down by, which is a constant except where the reader's own
    clamp bites.  ``runt_binds`` names the prose blocks whose last two words are
    bound together because the block's last line came out as one short word; see
    ``_RUNT_MEASURE_FRACTION``.  All six are *measured* facts, so a plan is the
    output of one layout and the input to the next.
    """

    closing_plates: int
    source_codes: tuple[SourceCode, ...] = ()
    adaptive_images: tuple[tuple[str, float], ...] = ()
    band_offsets: tuple[tuple[str, float], ...] = ()
    end_marks: tuple[tuple[str, float], ...] = ()
    runt_binds: tuple[str, ...] = ()

    @property
    def codes_by_article(self) -> dict[str, SourceCode]:
        return {code.article_id: code for code in self.source_codes}

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

    Two of the reader's placement rules read the finished page rather than the
    content: the closing-plate count comes from where the body stopped, and an
    article's source code takes the large slot only when its last page really has
    ``ARTICLE_TAIL_ORNAMENT_MIN_HEIGHT`` of open space below the end mark.
    Neither question can be asked in CSS, so this renders a probe pass carrying
    neither, measures it, and renders the answer.  A third pass then has nothing
    left to change: closing plates land after the body and a source code is out
    of flow, so neither decision can move the content that both were derived
    from -- which is asserted rather than assumed.

    Runt control is measured the same way and one step earlier, because unlike
    the other two it *does* move the content everything else is derived from: a
    bound pair can cost a paragraph's penultimate line its last word, and can
    give a paragraph back a whole line.  So the bare pass below carries no binds
    at all, only to be read for which last lines came out as a single short
    word; every pass after it -- and the painted pass in ``_painted_reader``,
    which is handed the same plan -- carries the answer.
    """
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

    ``plan.runt_binds`` is the one thing here that *does* change what is laid
    out, and deliberately: it binds the last two words of the named prose blocks
    so Pango cannot strand the final word on a line of its own.
    """
    source = HTML(string=html, base_url=Path.cwd().as_uri() + "/")
    tree = source.etree_element
    # First, so that a block's key is the semantic edition's own document order
    # and cannot be renumbered by a plate moving or a closing plate being cut.
    _key_prose_blocks(tree)
    _bind_paragraph_tails(tree, plan.runt_binds)
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
    # After ``_rewrite_landscape_plates``, which reads the tail figure this
    # removes: a deferred plate is released by the article's coda, and the coda
    # has to still be there when that decision is taken.
    _apply_source_codes(tree, plan.codes_by_article)
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


def _key_prose_blocks(tree: Element) -> None:
    """Name every block of reading-flow prose, in the edition's own order.

    A runt is measured on one layout and repaired on the next, so the two passes
    need a name for the same paragraph.  The name cannot be the paragraph's text
    (two blocks may read the same) and cannot be a box identity (the tree is
    reparsed for every pass), so it is the block's ordinal among the prose blocks
    of the semantic edition.  That ordinal is assigned before any structural pass
    runs, which is what keeps it stable across a plan that moves a deferred plate
    or cuts a closing plate.
    """
    for index, block in enumerate(_prose_blocks(tree)):
        block.set(_RUNT_KEY, str(index))


def _prose_blocks(element: Element, *, inside_main: bool = False) -> Iterable[Element]:
    """The innermost blocks of reading-flow prose, in document order.

    "Innermost" is what keeps a loose list item from being counted twice: a
    markdown ``li`` that holds a ``p`` is not itself the text block, the ``p``
    is, and binding both would bind the same words twice.  A block is prose when
    it is not opener chrome, contents furniture, an end mark or preformatted
    text -- each of those is drawn to its own fixed metrics inside a field whose
    height the adapter states, and a rag is not what they are judged on.
    """
    tag = str(element.tag).rsplit("}", 1)[-1].lower()
    if tag in _UNBINDABLE_SUBTREES or _element_classes(element) & _UNBINDABLE_CLASSES:
        return
    if tag == "main":
        inside_main = True
    if tag == "figure" and "closing-plate" in _element_classes(element):
        # A plate caption is auto-fitted display type; `_validate_fitted_display`
        # checks the line count it was fitted to, so nothing may rewrap it.
        return
    nested = [block for child in element for block in _prose_blocks(child, inside_main=inside_main)]
    if nested:
        yield from nested
        return
    if inside_main and tag in _BINDABLE_TAGS and "".join(element.itertext()).strip():
        yield element


def _bind_paragraph_tails(tree: Element, keys: Iterable[str]) -> None:
    """Bind the last two words of each named block with a non-breaking space.

    This is the whole of the runt repair, and it is one character: replacing the
    space before a paragraph's final word with ``U+00A0`` makes Pango carry the
    two words to the next line together rather than strand the last one.  Under
    greedy line breaking -- which is what Pango does here, and what ``lines``
    did before it -- the bind can only ever *fit* into the line the pair now
    shares or move both down one line, so it never adds a line to a paragraph
    and sometimes gives one back.

    ``U+00A0`` and not markup, deliberately.  A ``white-space: nowrap`` span
    around the pair would do the same to the layout and break the *text layer*:
    WeasyPrint gives each inline box its own text matrix and emits no space
    glyph between two of them, which is how one box per token used to extract as
    ``Theoriginalarticle.``  Keeping the pair inside a single text run keeps the
    separator in the PDF's own text.  Every bundled face carries the glyph, so
    nothing falls back to a host font, and the reader is set ragged right, so
    there is no justification for a bound space to distort.
    """
    wanted = frozenset(keys)
    if not wanted:
        return
    for element in tree.iter():
        if element.get(_RUNT_KEY) in wanted:
            _bind_last_two_words(element)


def _bind_last_two_words(block: Element) -> None:
    """Replace the whitespace before ``block``'s final word with ``U+00A0``.

    The final word may sit inside an ``em`` or an ``a``, and the whitespace
    before it may sit in a different text node again, so the block's text nodes
    are addressed as one string and only the one that carries the separator is
    rewritten.  A separator split across two nodes is left alone rather than
    guessed at: no markup this edition contains produces one, and rewriting
    across an element boundary would move authored text between elements.
    """
    slots = list(_text_slots(block))
    joined = "".join(getattr(owner, attribute) or "" for owner, attribute in slots)
    trimmed = joined.rstrip()
    end = len(trimmed)
    while end and not trimmed[end - 1].isspace():
        end -= 1
    if not end:  # One word, or no whitespace to bind on.
        return
    start = end
    while start and trimmed[start - 1].isspace():
        start -= 1
    if not trimmed[:start].strip():  # Two words in total; nothing to strand.
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
    """Every text node of ``element``'s subtree, in document order, as a slot."""
    yield element, "text"
    for child in element:
        yield from _text_slots(child)
        yield child, "tail"


def _measured_runt_binds(document: Any) -> tuple[str, ...]:
    """The prose blocks whose last line came out as one short word.

    Both halves of the test are read off the finished page rather than predicted:
    the last line's text, so a single word is a single word after shaping and
    after every intra-token break Pango took, and the line's width against *its
    own* block's measure, which differs between the 325pt reading column, the
    333pt a band escapes to, and the 311pt inside a list item's indent.  A block
    of one line is not a paragraph with a runt -- it is a short paragraph.
    """
    lines: dict[str, list[tuple[float, str]]] = {}
    boxes: dict[str, tuple[float, float]] = {}
    for page in document.pages:
        for box in _walk_boxes(page._page_box):
            element = getattr(box, "element", None)
            key = getattr(element, "attrib", {}).get(_RUNT_KEY) if element is not None else None
            # The block box only: WeasyPrint hands a line box its originating
            # element too, and counting both would count every line twice.
            if key is None or type(box).__name__ != "BlockBox":
                continue
            boxes[key] = (float(box.width), float(box.style["font_size"]))
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


def _is_runt(set_lines: list[tuple[float, str]], measure: float, size: float) -> bool:
    """Whether this block's last line is a short word stranded on its own, *and*
    whether binding it would be an improvement.

    The last two clauses are not about the defect but about the cure.

    The bound pair has to fit a line of its own, or Pango has no break left to
    take and ``_validate_reader_measures`` refuses the build over a repair this
    module chose.

    And the line the bound word leaves has to still read as a line.  Under greedy
    breaking nothing above the penultimate line moves, so the penultimate comes
    out exactly as wide as it is now less its own final word -- predictable from
    the measured line without laying the paragraph out again.  Where that leaves
    more than ``_RUNT_MAX_RAG_FRACTION`` of white the repair has traded one short
    line for two, which is the worse defect, and the bind is refused.

    Both predictions are summed unkerned in the reading face, as everything else
    this module predicts is -- they need to be right about a word, not about a
    tenth of a point.
    """
    if len(set_lines) < 2:
        return False
    width, text = set_lines[-1]
    previous_width, previous_text = set_lines[-2]
    words = text.split()
    previous = previous_text.split()
    if len(words) != 1 or not previous:
        return False
    if width > measure * _RUNT_MEASURE_FRACTION:
        return False
    pair = f"{previous[-1]}{_NO_BREAK_SPACE}{words[0]}"
    if _string_width(pair, "serif", size) > measure:
        return False
    opened = measure - (previous_width - _string_width(f" {previous[-1]}", "serif", size))
    return opened <= measure * _RUNT_MAX_RAG_FRACTION


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
        size, _lines = _fitted_plate_title(titles[index])
        top = _PLATE_TITLE_CONTENT_TOP_POINTS + _DISPLAY_SOLID_BASELINE_HEAD * size
        for caption in plate.iter("figcaption"):
            caption.set(
                "style",
                f"font-size: {size:.4f}pt; line-height: {size:.4f}pt; top: {top:.4f}pt",
            )


def _fitted_plate_title(title: str) -> tuple[float, list[str]]:
    """The size and lines ``_closing_plate`` fits a plate title to.

    Stated once because two passes need the same answer: ``_fit_closing_plate_titles``
    sets it, and ``_validate_fitted_display`` checks the laid-out caption against
    it.  A guard that carried its own copy of the fit range would stop being a
    guard the first time the range moved.
    """
    return _fitted_display(
        title,
        _PLATE_TITLE_WIDTH_POINTS,
        _PLATE_TITLE_BOX_HEIGHT,
        maximum=_PLATE_TITLE_MAX,
        minimum=_PLATE_TITLE_MIN,
        maximum_lines=_PLATE_TITLE_MAX_LINES,
        leading_ratio=1.0,
    )


def _apply_source_codes(tree: Element, codes: Mapping[str, SourceCode]) -> None:
    """Stand each article's source code in the slot its own page earned.

    The tail motif comes out here rather than in ``html_edition``, and that is
    the seam being kept: the semantic edition still offers the motif and the
    link, because a screen adapter can use both, and this is the one place that
    knows the code has taken the motif's slot.

    Like the figure frames and like the motif before it, the code is an
    absolutely positioned replaced element, so it takes nothing out of any box
    and cannot displace a line.  Every one of its four edges is stated inline
    because every one of them is a measurement.

    THE CODE HANGS FROM THE TOP OF ITS SLOT, NOT FROM THE BOTTOM.  A slot is
    guaranteed room and not a frame to fill, and a 41mm square dropped to the
    foot of a 214pt one put 84-93mm of nothing between the end mark and the code
    -- the page read "article ends, silence, black square", and the square read
    as applied after printing rather than set with the page.  Anchored to the
    slot's own top the void is ``_TAIL_ORNAMENT_ENDMARK_CLEARANCE`` on every page
    that carries a code, the same 31pt the ornament was always given, and the
    white that is left falls at the page foot where an article ending high on
    its last page has always left it.

    Flush left on the reading measure, not centred in it.  Every other element on
    these pages is flush to one edge or the other; a square centred on the
    measure agrees with none of them.

    And labelled.  ``.source-label`` sets the code's name in the same tracked
    violet caps as ``END / nn``, on the symbol's own bottom edge, one
    ``_CODE_LABEL_GAP_POINTS`` to its right -- the same relation in both slots,
    which is what makes the 41mm code and the 14mm code read as two sizes of one
    thing.  In the foot slot that bottom edge is the folio's baseline, so the
    label, the square and the two ends of the folio all sit on one line.
    """
    for article in tree.iter("article"):
        for child in [child for child in article if "article-tail" in _element_classes(child)]:
            article.remove(child)
        code = codes.get(article.get("data-article-id") or "")
        if code is None:
            continue
        side = code.side
        bottom = code.top - side
        image = SubElement(article, "img")
        image.set("class", "source-code")
        image.set("alt", "")
        image.set("aria-hidden", "true")
        image.set("data-source-code", code.slot)
        image.set("src", _source_code_source(code))
        image.set(
            "style",
            f"left: {code.left:.4f}pt; bottom: {bottom:.4f}pt; "
            f"width: {side:.4f}pt; height: {side:.4f}pt",
        )
        _label_source_code(article, code)


def _label_source_code(article: Element, code: SourceCode) -> None:
    """Name the square, in the publication's own voice, beside its foot.

    The text is the semantic edition's, read off the very anchor the code
    encodes: ``html_edition`` owns the reader-facing vocabulary in both
    languages, and an adapter that invented ``SOURCE`` for itself would have
    invented it in English only.  A code with no name to print is a build
    failure and not a bare square -- the unlabelled square is the defect this
    exists to repair.
    """
    link = next(
        (element for element in article.iter("a") if "source-link" in _element_classes(element)),
        None,
    )
    text = ((link.get("data-source-label") if link is not None else None) or "").strip()
    if not text:
        raise ValidationError(
            f"Article {article.get('data-article-id')} prints a source code but its "
            "semantic edition carries no data-source-label for it; an unlabelled "
            "square on the page is the defect the label exists to repair."
        )
    left = code.symbol_right + _CODE_LABEL_GAP_POINTS
    width = _string_width(text.upper(), "sans-medium", _CODE_LABEL_SIZE_POINTS) + (
        _CODE_LABEL_TRACKING_POINTS * len(text)
    )
    if left + width > _CODE_MEASURE_LEFT_POINTS + _CODE_MEASURE_POINTS:
        raise ValidationError(
            f"Article {article.get('data-article-id')}'s source code label {text!r} "
            f"runs {left + width:.2f}pt into a "
            f"{_CODE_MEASURE_LEFT_POINTS + _CODE_MEASURE_POINTS:.2f}pt measure; the "
            "square is too wide for its own name to stand beside it."
        )
    label = SubElement(article, "p")
    label.set("class", "source-label")
    label.text = text
    label.set(
        "style",
        f"left: {left:.4f}pt; "
        f"bottom: {code.symbol_bottom + _ZERO_LEADING_SANS_BASELINE:.4f}pt",
    )


def _fitted_source_code(
    article_id: str, slot: str, url: str, room: float, *, top: float = 0.0
) -> SourceCode | None:
    """The widest-celled code ``room`` points of slot can carry.

    Two knobs, taken in the order that survives a phone camera.  The module is
    the house one wherever the slot can hold it, so a code with space is set at
    ``_CODE_HOUSE_MODULE_POINTS`` and simply comes out as wide as its own symbol
    needs -- which is what makes the printed size a property of the URL and not a
    constant.  Where the slot is tighter than that, the module is whatever the
    slot's own geometry leaves, and the level chosen is the one that leaves the
    most: a lower error correction is a shorter symbol, a shorter symbol is a
    wider cell in the same square, and a wider cell is worth more to a real scan
    than redundancy behind cells too small to resolve.  Measured on this
    edition's 51-character URLs, ECC-L sets a 415um module where ECC-M sets
    375um in the identical 15.36mm square -- 11% of cell width for nothing.

    HIGHEST CORRECTION WINS A TIE, and every roomy slot is a tie: there the
    module is capped at the house one for every level, so the extra cells of
    ECC-H cost only square inches the slot already has.  That is why the tail
    codes are ECC-H and the foot codes ECC-L without either being a special case.

    The trade is not free and is not pretended to be: ECC-L carries 7% codeword
    redundancy against ECC-M's 15%, so a creased or thumbed code recovers less.
    The measured failure mode of a code this size is optical rather than
    physical -- its tolerance to ink damage is already four to six times a real
    inkjet's spread -- so cell width is where the margin is worth spending.

    ``None`` means no level fits, which is a build failure and not a smaller
    code: the caller refuses.  There is no floor-breaking fallback on purpose --
    an unscannable square printed on paper is worse than nothing, and it looks
    exactly like a working one.
    """
    import segno

    best: SourceCode | None = None
    for level in _CODE_ERROR_LEVELS:
        symbol = segno.make(url, error=level, micro=False)
        modules = int(symbol.symbol_size(border=_CODE_QUIET_MODULES)[0])
        module = _slot_module(slot, modules, room)
        if module < _CODE_MIN_MODULE_POINTS:
            continue
        if best is None or module > best.module + _MODULE_EPSILON:
            side = modules * module
            # The tail square is flush left on the reading measure, and flush
            # means its ink is: the element is pulled one quiet zone further left
            # so the first dark module stands on the same origin as the END rule
            # and every line of the article above it.  The four light modules
            # that then sit outside the measure cost nothing -- white quiet zone
            # in a page margin is exactly what a margin is for.  The foot square
            # is centred instead, and the quiet zones are symmetric, so centring
            # the element centres the ink.
            left = (
                _CODE_MEASURE_LEFT_POINTS - _CODE_QUIET_MODULES * module
                if slot == "tail"
                else _CODE_MEASURE_LEFT_POINTS + (_CODE_MEASURE_POINTS - side) / 2
            )
            best = SourceCode(article_id, slot, level, modules, module, url, left, top)
    return best


def _slot_module(slot: str, modules: int, room: float) -> float:
    """One cell of a ``modules``-wide symbol, as this slot's geometry allows it.

    The tail slot is a height and nothing else: the square hangs from the slot's
    top and the module is whatever fits, capped at the house one.

    The foot slot is a *line*, and that is the whole difference.  Its ceiling is
    the page's content-box foot, below which no type is set, and its pin is the
    folio's baseline, which the symbol's own bottom edge has to land on -- so the
    module divides ``_CODE_FOOT_DROP_POINTS`` between the symbol and the single
    quiet zone above it, ``modules - _CODE_QUIET_MODULES`` cells in all, and the
    remaining four cells of quiet zone hang below the folio line into the sheet's
    foot margin.  ``_CODE_FOOT_ROOM_POINTS`` then holds independently, so a
    square that would reach the sheet's edge is refused even if the pin is happy.
    """
    if slot == "tail":
        return min(_CODE_HOUSE_MODULE_POINTS, room / modules)
    return min(
        _CODE_HOUSE_MODULE_POINTS,
        _CODE_FOOT_DROP_POINTS / (modules - _CODE_QUIET_MODULES),
        room / modules,
    )


def _source_code_matrix(code: SourceCode) -> list[list[bool]]:
    import segno

    symbol = segno.make(code.url, error=code.error, micro=False)
    return [[bool(cell) for cell in row] for row in symbol.matrix]


def _source_code_source(code: SourceCode) -> str:
    """The code as an SVG data URI, in the publication's own ink on its paper.

    SVG and not PNG.  A raster would have to be generated at some density and
    would then be judged against ``_MIN_FIGURE_PPI`` like any other placed
    image; vector modules are exact at whatever density the sheet is printed at,
    and the adapter already proves it can put genuine vector geometry through
    WeasyPrint -- the figure frame had to be an SVG ``rect`` for the same reason.
    One SVG user unit is one point, as it is there.

    ONE INK, AND THE HOUSE VIOLET MOVED TO THE LABEL.  The three finder patterns
    used to print in VIOLET, the colour this publication reserves for structure,
    and on a colour device that is exactly right: measured off the 1200 dpi page,
    violet renders at gray 0.180 against the ink's 0.071, the LocalAverage
    binariser is untroubled by the difference, and the symbol survives a 140%
    illumination gradient.  The case it does not cover is the one this magazine
    is actually printed on.  A **monochrome** printer does not reproduce a 0.18
    gray as gray; it halftones it, and at a 0.38mm module a 0.38mm halftone cell
    puts white holes through a ring one module thick.  The finders are the part
    of a symbol detection depends on before error correction can help with
    anything, so that is the one place in the code where a screen cannot be
    dithered.  It is untestable here without a mono laser, the fix costs nothing,
    and so the symbol is set entirely in INK.  The house voice is not lost: it
    moved to ``.source-label``, which is violet tracked caps and is *type* -- a
    glyph that halftones is still a glyph, and it is not what the scanner reads.

    The ground is *painted* rather than left transparent, which is the one place
    robustness beats fidelity: the quiet zone is only a quiet zone if nothing
    shows through it, and the foot slot's code stands a couple of points below a
    full page of type.

    One path of touching subpaths and not a field of separate rectangles.  A PDF
    fill computes coverage once over the whole path, so modules that share an
    edge merge cleanly; drawn as individual rectangles they would each antialias
    against their neighbour and lay a grid of pale hairlines through the symbol
    at exactly the scale a binariser is looking at.  Runs are merged along the
    row first for the same reason, and to keep the URI small.  With one ink there
    is no second path for the first to antialias against either, which is the
    hairline argument's own conclusion taken one step further.

    No centred publication mark.  ECC-H would carry one, but the foot slot's
    codes are set at whatever level their room affords and that is regularly not
    H; a mark on some codes and not others is not a house style, and occluding a
    code that has already traded away redundancy for cell size is the trade made
    twice.  Nothing here forecloses it -- an authored artwork pass would replace
    this function, not extend it.
    """
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
    """Where a source code's square actually landed, in PDF page coordinates.

    ``left``/``bottom`` are points from the page's lower-left corner, which is
    the origin the decode gate's raster is measured against and the origin
    ``FigurePlacement`` already uses.
    """

    page: int
    left: float
    bottom: float
    side: float


def _measured_source_code_boxes(document: Any) -> dict[str, PlacedCode]:
    """Every source code the laid-out reader actually placed, by article.

    Read off the box tree rather than trusted from the plan, because the whole
    of the decode gate rests on knowing which page to rasterise and where on it
    the square should be.  A code that silently failed to place is the failure
    mode the gate exists for, and a plan cannot report it.
    """
    placed: dict[str, PlacedCode] = {}
    for page_number, page in enumerate(document.pages, start=1):
        for article_id, box in _walk_source_code_images(page._page_box):
            width = float(box.width) * _POINTS_PER_CSS_PIXEL
            height = float(box.height) * _POINTS_PER_CSS_PIXEL
            found = PlacedCode(
                page_number,
                round(float(box.content_box_x()) * _POINTS_PER_CSS_PIXEL, 4),
                round(
                    _reader_y_points(
                        float(box.content_box_y()) * _POINTS_PER_CSS_PIXEL, height
                    ),
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


def _measured_plan(
    document: Any, edition: Edition, runt_binds: Iterable[str] = ()
) -> ReaderPlan:
    """Read a laid-out reader back as the plan its own pages imply.

    ``runt_binds`` is the one field that accumulates rather than being measured
    afresh: a bound paragraph no longer *has* a runt, so re-measuring alone would
    unbind it on the next pass and oscillate.  Carrying the binds forward and
    adding whatever the document still shows makes the plan monotone, which is
    what lets the settle check above be an equality.
    """
    content_pages = _content_page_count(document)
    codes: list[SourceCode] = []
    end_marks: list[tuple[str, float]] = []
    for article in edition.articles:
        flow_bottom = _article_flow_bottom(document, article.id)
        end_marks.append((article.id, _end_mark_offset(flow_bottom)))
        code = _measured_source_code(
            article, flow_bottom, _end_mark_extent(document, article.id)
        )
        if code is not None:
            codes.append(code)
    return ReaderPlan(
        closing_plates=_signature_closing_plates(edition, content_pages),
        source_codes=tuple(sorted(codes)),
        adaptive_images=_measured_adaptive_images(document, edition),
        band_offsets=_measured_band_offsets(document),
        end_marks=tuple(end_marks),
        runt_binds=tuple(
            sorted({*runt_binds, *_measured_runt_binds(document)}, key=int)
        ),
    )


def _measured_source_code(
    article: Any, flow_bottom: float, end_mark_extent: float = 0.0
) -> SourceCode | None:
    """Which slot this article's code takes, how large it is set, and where.

    The slot is a property of the laid-out page and of nothing else.
    ``_tail_code_slot`` is the test for an article that ended high enough to
    carry a large element under its end mark: an edition whose author committed
    no art at all still prints a large code wherever a page has the room, and an
    edition full of art prints no more of them than its pages earn.

    AND ROOM IS NOT A REASON ON ITS OWN.  An article that ends very high leaves
    the most room and is the page least able to absorb what the room buys: the
    square drops in under the end mark and then a half-page of nothing follows
    it, and a 41.6mm black rectangle is the loudest thing on a sheet holding six
    lines of type.  So the large slot is also given up where the white left below
    the square would run past ``_CODE_TAIL_MAX_FOOT_WHITE_POINTS``, and the code
    joins the folio's line instead.  The give-up is conditional on the foot band
    being able to hold the symbol at all: where the URL is too long to set there
    at ``_CODE_MIN_MODULE_POINTS``, the tail slot the page already earned stands,
    because a code that does not scan is not the smaller of two evils.

    ``end_mark_extent`` is how far the article's own end mark reaches across the
    measure, and it is what keeps the foot slot's code out of the mark's way.
    The mark rests on the reader's floor on a page the article fills, which is
    one of the pages the foot slot is used on, so on a full last page the two
    share the foot band whether or not anyone intended it.  They cannot be
    separated vertically -- the square needs the whole band and the mark cannot
    rise into the type -- so the separation is horizontal and is *stated*: the
    square's first dark module never stands closer to the end mark's line than
    the 24pt the mark already holds its own text off the frame's edge by.  Ink to
    ink, like every other clearance the code is judged on.

    An article with no ``source_url`` prints no code and is not an error -- a
    source record need not carry a canonical URL, and the editorial has no
    source at all.
    """
    url = str(getattr(article, "source_url", "") or "").strip()
    if not url:
        return None
    slot_top = _tail_code_slot(flow_bottom)
    slot = "foot" if slot_top is None else "tail"
    room = _CODE_FOOT_ROOM_POINTS if slot_top is None else _tail_code_room(flow_bottom)
    code = _fitted_source_code(
        str(article.id), slot, url, room, top=0.0 if slot_top is None else slot_top
    )
    if code is None:
        raise ValidationError(
            f"Article {article.id} cannot carry a scannable source code for {url}: "
            f"the {slot} slot offers {room:.2f}pt, and even at the lowest error "
            f"correction the symbol's module would fall under "
            f"{_CODE_MIN_MODULE_POINTS * 25.4 / 72:.2f}mm. Shorten the canonical URL, "
            "or let the article end higher on its last page."
        )
    if code.slot == "tail" and _tail_code_foot_white(code) > _CODE_TAIL_MAX_FOOT_WHITE_POINTS:
        smaller = _fitted_source_code(
            str(article.id), "foot", url, _CODE_FOOT_ROOM_POINTS, top=0.0
        )
        if smaller is not None:
            code = smaller
    if code.slot == "foot":
        clear = (
            _CODE_MEASURE_LEFT_POINTS
            + end_mark_extent
            + _END_MARK_TEXT_INSET_POINTS
            - code.quiet
        )
        left = max(code.left, clear)
        if left + code.side > _CODE_MEASURE_LEFT_POINTS + _CODE_MEASURE_POINTS:
            raise ValidationError(
                f"Article {article.id}'s foot-slot source code cannot stand "
                f"{_END_MARK_TEXT_INSET_POINTS:.0f}pt clear of an end mark reaching "
                f"{end_mark_extent:.2f}pt across a {_CODE_MEASURE_POINTS:.0f}pt "
                "measure without running off the measure's own right edge."
            )
        code = replace(code, left=left)
    return code


def _end_mark_extent(document: Any, article_id: str) -> float:
    """How far the article's end mark reaches across its own measure, in points.

    Measured off the laid-out mark rather than predicted from ``END / nn``: the
    text is localized, tracked, and set in a face this module only sums unkerned,
    and the number it feeds is a clearance.  Zero for an article whose mark has
    not been laid out, which is every fragment the unit tests build by hand.
    """
    reach = 0.0
    for page_number, page in enumerate(document.pages, start=1):
        for box in _article_flow_boxes(page._page_box, article_id):
            element = getattr(box, "element", None)
            if element is None or "end-mark" not in _element_classes(element):
                continue
            for text_box in _walk_boxes(box):
                if not isinstance(getattr(text_box, "text", None), str):
                    continue
                right = (
                    float(text_box.position_x) + float(text_box.width)
                ) * _POINTS_PER_CSS_PIXEL
                reach = max(
                    reach,
                    right - _live_area_left(page_number) - _CODE_MEASURE_LEFT_POINTS,
                )
    return reach


def _end_mark_baseline(flow_bottom: float) -> float:
    """Where ``END / nn`` sets on its page, in points up from the sheet's foot.

    The mark closes a paragraph, so it stands under one, one point below the
    ``self.y`` ``_article_flow_bottom`` measures (render.py:2009).  The space
    that leaves above its rule is the house's own and is not a budget anyone
    chose: it is whatever a line of prose and its space-after come to, 11.2-16.9pt
    of clear paper on every article in edition 002.

    ``max(self.frame_bottom + 5, ...)`` IS NOT A FLOOR FOR THE MARK'S SAKE, and
    reproducing it was the defect.  It is the *frame's* number, and on an article
    whose last page over-runs it does not lower anything -- it *raises* the mark
    into the type it is meant to stand under.  On es p9 it raised it 7.5pt and
    left 5.0pt between the descenders and the rule, against 11.2-16.9pt on the
    other eleven article endings in the edition; the mark took whatever the page
    had left instead of taking its own space.  The horizontal clearance
    ``_measured_source_code`` states cannot see that, because the crowding was
    never horizontal.

    So the mark keeps its own space and the floor becomes a real one.  Below
    ``_END_MARK_HARD_FLOOR_POINTS`` its rule and its label would reach the band
    the folio and the small source code share and the two would read as one line
    of chrome; that is refused rather than squeezed, because a page that cannot
    hold its own ending is a pagination fault and not something to absorb
    silently.  Nothing in edition 002 comes within 10pt of it -- es p9, the one
    page the old clamp fired on, sets at 42.48 against a floor of 32.5.

    The mark is out of flow in both engines, so moving it moves no line: what
    changes on that one page is where a zero-height block is painted.
    """
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
    """How far ``_article_endmark``'s mark is painted below its own flow box."""
    baseline = _end_mark_baseline(flow_bottom)
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
    carries the same copy.  The article's out-of-flow coda is excluded from the
    walk because it is exactly what this measurement decides: both the tail
    motif and the source code are placed *from* this number, so counting either
    of them into it would make the plan measure its own output and never settle.
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


def _tail_code_room(flow_bottom: float) -> float:
    """The clear page under an article's end mark, as a height in points.

    From the top of the tail slot -- ``_TAIL_ORNAMENT_ENDMARK_CLEARANCE`` below
    the mark's own baseline, where the ornament's head always was -- down to
    ``_END_MARK_FLOOR_POINTS``, the floor the reader gives the last piece of type
    on a page.  The ornament stopped ``ARTICLE_TAIL_ORNAMENT_FOOT_INSET`` higher
    than that so as not to crowd the page's foot; the code is anchored to the top
    of the slot and so does not reach the floor at all unless the slot is nearly
    the size of the square, which is the only case where the difference bites --
    and it is exactly the case the ornament's instinct was wrong about.

    Capped at the ornament's own maximum, which is not a constraint on any code
    this publication can produce but keeps the slot a slot.
    """
    top = _end_mark_baseline(flow_bottom) - _TAIL_ORNAMENT_ENDMARK_CLEARANCE
    return min(top - _END_MARK_FLOOR_POINTS, _TAIL_ORNAMENT_MAX_HEIGHT)


def _tail_code_slot(flow_bottom: float) -> float | None:
    """The tail slot's own top, in page-content-box points, or nothing.

    This is the publication's test for "the last page has room", and it is the
    code's rather than the ornament's: room for a square at least twice the foot
    slot's, which is what keeps the two printed sizes two classes and not a
    continuum.  The decision stays a property of the laid-out page and not of
    what an author happened to commit -- an edition with no art at all still
    earns the large code wherever a page ends high enough.

    Whatever stands in the slot never displaces a line: the slot occupies the
    frame's foot, which is why the stylesheet takes it out of flow entirely.
    """
    if _tail_code_room(flow_bottom) < _CODE_TAIL_MIN_ROOM_POINTS:
        return None
    endmark_baseline = _end_mark_baseline(flow_bottom)
    return (
        endmark_baseline
        - _TAIL_ORNAMENT_ENDMARK_CLEARANCE
        - _CODE_CONTENT_FOOT_POINTS
    )


def _tail_code_foot_white(code: SourceCode) -> float:
    """The clear page left under a tail square, from its box to the sheet's foot.

    Read from the *box* and not from the last dark module, because what is being
    judged is emptiness and a quiet zone is empty too.  The square hangs from the
    top of its slot, so this is everything the slot did not need plus the whole
    foot margin -- which on the imposed booklet is the physical sheet edge, and
    which is exactly the band the eye reads as "the page stopped here".
    """
    return _CODE_CONTENT_FOOT_POINTS + code.top - code.side


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

    An edition's inventory offers every closing plate; the plan decides how many
    of them the signature needs, so the inventory alone cannot say what should
    have been found.  A tail motif is never placed at all any more -- the source
    code has its slot -- and the inventory still offers it because the semantic
    edition is not a print tree.
    """
    if asset.role == "article_tail":
        return False
    if plan is None:
        return True
    if asset.role == "closing_plate":
        return int(str(asset.id).rsplit("-", 1)[-1]) <= plan.closing_plates
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
    # ``minimum_reader_pages`` is an editorial floor per article, declared in the
    # edition manifest and carried through translation, so it is a rule of the
    # publication and not of one typesetter: an article that came out shorter
    # than its editor allowed has lost source detail whichever engine set it.
    # ``render.py`` has enforced it since the field existed; this path did not,
    # which made the floor disappear when WeasyPrint became the default.
    short = [
        f"{article.id} ({layout.article_pages[article.id]} pages, "
        f"editorial minimum {article.minimum_reader_pages})"
        for article in edition.articles
        if article.id in layout.article_pages
        and layout.article_pages[article.id] < article.minimum_reader_pages
    ]
    if short:
        raise ValidationError(
            "WeasyPrint article editorial minimum not met: " + ", ".join(short)
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


def _validate_source_codes(
    pdf_bytes: bytes,
    edition: Edition,
    codes: Iterable[SourceCode],
    placed: Mapping[str, PlacedCode],
) -> None:
    """Read every source code back off the rasterised page and refuse a bad one.

    THIS IS THE ONLY THING THAT MAKES THE FEATURE REAL.  Every other guard in
    this module checks that a decision was carried out; this one checks that the
    result works.  A QR code is the one element on the page whose correctness a
    human proof-reader cannot judge -- it looks exactly the same whether it
    carries the right URL, the wrong URL or nothing a scanner can resolve -- so
    the only honest test is to be a scanner.

    Off the *rasterised page*, not off the SVG.  Reading the symbol back out of
    the source that produced it proves nothing but that the encoder is
    self-consistent; everything that can actually go wrong happens after that,
    in the layout, the vector fill, the PDF and the raster.  So the gate takes
    the finished PDF bytes -- the exact ones about to be written -- rasterises
    the page the code landed on at ``_CODE_DECODE_DPI``, and asks a general
    barcode reader to find whatever QR symbols are on that page.  The reader is
    not told where to look, which is why finding it is part of the result: a code
    whose quiet zone is dirty, whose modules have merged, or which is sitting
    under something else, is a code the reader will not locate.

    Three things are asserted, and the second and third are what stop a pass from
    being an accident.  Every planned code is decoded; its text is the article's
    canonical URL character for character; and the symbol's own reported corners
    land on the box the adapter placed.  Without the last one a page carrying two
    codes, or a code left behind from another article, could satisfy the first
    two.

    The gate runs on the bytes before they reach the disk, so a reader that would
    ship an unscannable code is never written at all.
    """
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
            (
                found
                for found in decoded
                if _code_box_matches(found[1], box)
            ),
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
    """Whether a decoded symbol's corners stand inside the square that was placed.

    The corners a reader reports are the *symbol's*, so they sit one quiet zone
    -- four modules -- inside the element on every side.  Rather than reproduce
    that inset, the test is containment with a tolerance: the symbol must lie
    within the placed square, and it must not be trivially small inside it.
    """
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
    """The named reader pages as images at ``_CODE_DECODE_DPI``, via Poppler.

    Poppler's ``pdftoppm`` is the same rasteriser ``render_critic`` judges every
    build with, so the gate reads the page the critic sees rather than a second
    interpretation of the PDF.  Only the pages carrying a code are rendered.
    """
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
                    executable, "-png", "-r", str(_CODE_DECODE_DPI),
                    "-f", str(page), "-l", str(page), str(reader), str(prefix),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            rendered = sorted(root.glob(f"page-{page}-*.png"))
            if completed.returncode or not rendered:
                detail = (
                    completed.stderr.strip()
                    or completed.stdout.strip()
                    or "no raster was produced"
                )
                raise DependencyError(
                    f"Could not rasterize reader page {page} to read its source code: {detail}"
                )
            with Image.open(rendered[0]) as image:
                rasters[page] = image.convert("L").copy()
    return rasters


def _decoded_codes(raster: Any) -> tuple[tuple[str, tuple[tuple[float, float], ...]], ...]:
    """Every QR symbol a general reader finds on ``raster``, with its corners.

    Corners come back in points from the page's lower-left corner, so they can be
    compared with the box the adapter placed.  ``zxing-cpp`` is deliberately an
    independent decoder and not this module's own encoder run backwards: it
    locates the finder patterns itself, corrects the perspective and applies the
    symbol's error correction, which is what a phone does and what a check
    written against ``segno``'s matrix would not.
    """
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
    """Refuse a line the measure cannot hold rather than letting it overflow.

    This guard predates the shaping re-baseline and narrowed when the nowrap
    boxes came out, but it did not become redundant.  What it caught then was
    *every* token wider than the measure, because a nowrap box forbade breaking
    inside one.  What it catches now is the residue: a token with no break
    opportunity Pango will take.  Hyphens, en dashes and em dashes are break
    opportunities, so a hyphenated identifier or a hyphen-bearing URL now breaks
    and never reaches here; an unbroken run of letters and digits still
    overflows the column silently, and silently is the part this refuses.

    It is deliberately not repaired with ``overflow-wrap: anywhere``.  A
    magazine measure is a design decision, and a word that cannot fit it is an
    editorial problem -- a mis-set identifier, a raw URL that should have been a
    footnote -- not something to break arbitrarily mid-syllable on the reader's
    behalf.  Failing loudly puts the decision back with the editor.  Measured on
    edition 002: nothing in the reader's flow comes close.  The widest token set
    anywhere in the document is 57 characters of source id inside the
    ``display: none`` provenance line, no URL is set at all, and no line box on
    any of the 36 pages exceeds its own measure by so much as float noise.
    """
    overlong: list[str] = []
    for page_number, page in enumerate(document.pages, start=1):
        _collect_overlong_lines(page._page_box, None, page_number, overlong)
    if overlong:
        raise ValidationError(
            "WeasyPrint set a reader line wider than its own measure, which means a "
            "token with no break opportunity is overflowing the column: "
            + "; ".join(overlong[:5])
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
    """Refuse a build whose display type outgrew the room that was fitted for it.

    Every auto-fitted size in this module -- an opener title, a closing-plate
    title -- is chosen from ``_advance_widths``, which sums *unkerned* advances
    because that is the measure ``render.py`` makes its decisions on.  Pango
    kerns, and kerning is not one-sided.  Measured over the cp1252 pairs of the
    ``kern`` feature in ``SourceSerif4Display-Semibold``, the face every fitted
    title is set in: 12,794 pairs pull glyphs together and **3,019 push them
    apart**.  The loosening pairs are ordinary -- ``Lo`` +17, ``La`` +21,
    ``Có`` +11, ``tr`` +10, ``ru`` +10, ``oo`` +9 units per 1000.  Five real
    edition-002 title lines already set wider shaped than summed, the worst
    ``'Cómo construimos'`` at 35pt by 1.2568pt.  Ligatures do only ever narrow in
    these faces; kerning is what breaks the bound.

    So a prediction can come out short, Pango can take a line the fit did not
    budget for, and the title can run out of the white field the opener reserved
    below it -- on an opener carrying a figure, straight into the figure.  Nothing
    else catches that: ``_validate_reader_measures`` refuses a *line box* wider
    than its own measure, and a title that merely wrapped is not one.

    This reads both decisions back off the laid-out boxes instead of trying to
    predict better.  A shape-accurate predictor would be right more often and
    still silently wrong at the margin; a guard on the finished page is right
    always, and refuses loudly.

    * An opener's ``h1`` margin box must end inside the header field -- the field
      ``_pin_opener_fields`` states, or the constant the stylesheet holds for an
      opener without a figure.  Its foot is where the prose, or the opener
      figure, begins.
    * A closing plate's caption must be set on the same number of lines
      ``_fitted_plate_title`` chose its size for.  The caption is positioned from
      that size alone, so an extra line hangs below the plate's title box.

    Measured on edition 002 as authored, both languages: every opener clears its
    field, the tightest by 16.69pt, and every plate caption is set on its fitted
    line count.
    """
    failures: list[str] = []
    for page_number, page in enumerate(document.pages, start=1):
        _collect_field_overflows(page._page_box, page_number, failures)
        _collect_plate_title_overruns(page._page_box, page_number, edition, failures)
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
        field = float(header.height) * _POINTS_PER_CSS_PIXEL
        field_bottom = float(header.content_box_y()) * _POINTS_PER_CSS_PIXEL + field
        title_bottom = (
            float(title.position_y) + float(title.margin_height())
        ) * _POINTS_PER_CSS_PIXEL
        if title_bottom <= field_bottom + _FIELD_OVERFLOW_EPSILON:
            continue
        failures.append(
            f"opener {piece!r} title {_box_text(title)!r} was fitted at "
            f"{float(title.style['font_size']) * _POINTS_PER_CSS_PIXEL:.4g}pt into a "
            f"{field:.4f}pt header field, whose foot is {field_bottom:.4f}pt down "
            f"page {page_number}; Pango set it on {_line_box_count(title)} lines "
            f"reaching {title_bottom:.4f}pt, overflowing the field by "
            f"{title_bottom - field_bottom:.4f}pt"
        )


def _collect_plate_title_overruns(
    box: Any, page_number: int, edition: Edition, failures: list[str]
) -> None:
    titles = [str(plate.title) for plate in edition.closing_plates]
    for index, caption in _closing_plate_captions(box):
        if not 0 <= index < len(titles):  # `_fit_closing_plate_titles` already refused this.
            continue
        size, fitted = _fitted_plate_title(titles[index])
        set_lines = _line_box_count(caption)
        if set_lines == len(fitted):
            continue
        failures.append(
            f"closing plate {index + 1} title {titles[index]!r} was fitted at "
            f"{size:.4g}pt over {len(fitted)} line(s), but Pango set it on "
            f"{set_lines} on page {page_number}"
        )


def _opener_title_boxes(box: Any, piece: str | None = None) -> Iterable[tuple[str, Any, Any]]:
    """Every laid-out opener header, paired with the ``h1`` it reserves room for.

    ``piece`` is carried down because the failure has to name the article an
    editor would go and shorten, and the header box itself does not know it.  A
    ``header`` outside any article or section -- the edition header, which the
    print stylesheet hides -- is not an opener and is not yielded.
    """
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


def _closing_plate_captions(box: Any) -> Iterable[tuple[int, Any]]:
    """Every laid-out closing-plate caption, with its zero-based plate index."""
    element = getattr(box, "element", None)
    attributes = getattr(element, "attrib", {}) if element is not None else {}
    plate = attributes.get("data-closing-plate")
    if plate is not None and getattr(box, "element_tag", None) == "figure":
        try:
            index = int(str(plate)) - 1
        except ValueError:  # `_fit_closing_plate_titles` already refused this.
            return
        for inner in _walk_boxes(box):
            if getattr(inner, "element_tag", None) == "figcaption" and hasattr(inner, "children"):
                yield index, inner
                return
        return
    for child in getattr(box, "children", ()) or ():
        yield from _closing_plate_captions(child)


def _line_box_count(box: Any) -> int:
    return sum(1 for child in _walk_boxes(box) if type(child).__name__ == "LineBox")


def _box_text(box: Any) -> str:
    """The text of a laid-out block, reassembled line by line.

    Pango trims the space a line broke on, so concatenating text boxes across
    lines welds the words either side of every break together.  A failure message
    naming ``'Current Court LocusLocus'`` sends an editor looking for a typo that
    is not in the manuscript, so the breaks come back as spaces.
    """
    lines = (
        "".join(
            child.text for child in _walk_boxes(line) if type(child).__name__ == "TextBox"
        ).strip()
        for line in _walk_boxes(box)
        if type(line).__name__ == "LineBox"
    )
    return " ".join(line for line in lines if line)


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
