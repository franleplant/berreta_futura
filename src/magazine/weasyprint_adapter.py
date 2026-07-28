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
import sys
from typing import Any, NamedTuple
from urllib.parse import quote
from xml.etree.ElementTree import Element, SubElement

from .errors import DependencyError, ValidationError
from .html_edition import HtmlAsset, render_html_edition
from .manifest import Edition
from .reader_layout import FigurePlacement, RenderLayout, declared_editorial_page_cap
from .reader_text import educate_reader_quotes, fold_reader_characters


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
# every stated opener field, the editorial 153.2756, the figure's own 10.0046pt
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


# THE TAIL ORNAMENT'S BOX.  ``_article_tail_ornament_box`` (render.py:177-190)
# is where three of these numbers come from, but the contract is no longer the
# reader's reproduced -- two of its rules are deliberately departed from, both
# measured on edition 003, and the departures are the point:
#
# ``_TAIL_ORNAMENT_FOOT_INSET`` and ``_TAIL_ORNAMENT_ENDMARK_CLEARANCE`` are the
# reader's own and are unchanged: the band never crowds the folio's chrome below
# it and never crowds the end mark's baseline above it.  Together they bound the
# *room* -- ``_end_mark_baseline - 31`` down to ``frame_bottom + 24`` -- and the
# room is what every decision below is made on.
#
# ``_TAIL_ORNAMENT_MIN_HEIGHT`` WAS 118 AND IS 96, and the number is not a
# taste, it is the render critic's own: ``render_critic.VOID_MIN_HEIGHT_POINTS``
# is the height at which a full-measure block of untouched paper stops reading
# as typography and starts reading as dead sheet (96pt, calibrated there against
# every honest and guilty void in edition 003).  An ornament floor above that
# bar is self-defeating -- it refuses the motif in exactly the rooms big enough
# to be mistaken for a defect -- so the floor *is* the bar: wherever the open
# room under an article could read as dead paper, the declared motif claims it,
# and a tighter ending than that is an article honestly ending, not a slot.
# Measured on edition 003 -- after the proportional opener field below moved
# the flow, so these are the rooms the shipped ledger actually records -- the
# six articles' rooms come out -42.6 / -27.9 / -22.2 / 154.2 / 335.1 / 410.9pt
# in English, so English prints 3 of 6 declared ornaments where the old 118
# floor (measured against the pre-change flow) printed 2, and the three
# negative rooms are not a floor's business at all: those articles end on a
# full last page with no slot, and the ledger says so.  Spanish prints 5 of 6
# -- the harness article's runt last page collapsed when the opener reclaimed
# its field, taking the article from six pages to five and its tail room to
# -53.6pt, a drop the ledger records where the old contract would have lost it
# silently.
#
# ``_TAIL_ORNAMENT_MAX_HEIGHT`` still caps a very high ending's motif at 214 so
# it cannot become a poster -- but the band is NO LONGER FOOT-ANCHORED when the
# cap bites.  ``_article_tail_ornament`` pinned the band's foot at the inset and
# let the whole surplus pool *above* it, between the end mark and the motif's
# head: on edition 003 that printed 121pt and 197pt of stranded white mid-page
# (en p19, p29), which the critic flags as exactly the voids they are.  A capped
# band now stands centred in its room -- ``(room - height) / 2`` below the end
# mark's clearance and the same above the foot inset -- so the surplus splits
# into two balanced margins that read as the band's own setting, the way a
# plate's art centres its overflow.  An uncapped band fills its room exactly and
# the question does not arise.
_TAIL_ORNAMENT_MIN_HEIGHT = 96.0
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
# ``@page``'s own margin-top, the stylesheet's 42.0004: the frame-top inset
# less the first-baseline datum, plus the rasteriser nudge.  It is what turns
# a measured page-absolute ``position_y`` into the content-box coordinate the
# adapter states absolute placements in.
_PAGE_MARGIN_TOP_POINTS = 52.0 - _FIRST_BASELINE_INSET_POINTS + _RASTER_NUDGE_POINTS
_FRAME_BOTTOM_RELIEF_POINTS = _FRAME_BOTTOM_POINTS - (
    _PAGE_MARGIN_BOTTOM_POINTS - _FIRST_BASELINE_INSET_POINTS
)

# THE SOURCE CODE.
#
# A print magazine cannot hyperlink, so every article carries the address of the
# source it was built from as a QR square, set into its opener's own title
# furniture.  The numbers below decide what that square is and where it stands,
# and each is a print decision rather than a taste:
#
# ``_CODE_OPENER_SIDE_POINTS`` is the square, and unlike the retired tail and
# foot slots it is a *constant*: every opener carries the same credit block --
# kicker, title, byline -- so the code that joins it has one size on every
# opener, the way the byline has one size.  55.5pt -- 19.6mm -- is chosen as a
# whole multiple of the symbol most of this publication's addresses set at: nine
# of the twelve codes editions 002 and 003 print come out 37 modules across the
# quiet zone, and 37 * 1.5 lands their cell on a round point and a half
# (0.5292mm) rather than on a division's remainder.  A cell that is a clean
# number is not decoration: the printer, the 300 ppi decode gate and the eye all
# quantise, and a module at 1.5pt is 6.25 device pixels at the gate's own
# density where the old 45pt square's 1.21622pt was 5.068.  The size was raised
# from 45pt (15.9mm), which was chosen to span the byline and a two-line author
# note and little more; at 19.6mm the square is a shade taller than that block
# and reads as the credit line's own opening mark rather than as a token beside
# it, and every module it prints is roughly a quarter wider than before, which
# is where a phone camera's margin lives.  What varies with the URL is still the
# *module*: a longer address is a denser symbol in the same square, never a
# larger square on a page that was not asked.
#
# ``_CODE_MIN_MODULE_POINTS`` is the floor, and it is the number the design gives
# way at.  0.35mm is 4.1 dots of a 300 dpi inkjet and about where a phone camera
# held at an angle over uncoated paper stops being reliable.  A build whose code
# cannot be set at this module at any error correction level refuses rather than
# printing something that will not scan; on the fixed opener square that binds a
# canonical URL at 154 characters -- QR version 7's byte-mode capacity at ECC-L,
# whose 53 modules across the quiet zone come out at 0.3694mm, over the floor,
# where version 8's 57 would come out at 0.3435mm and refuse.  Measured by
# lengthening a URL a character at a time: 154 sets, 155 refuses.  The 45pt
# square bound 106.  The longest this publication has printed is 75.
#
# ``_CODE_QUIET_MODULES`` is the QR standard's own four-module quiet zone, and it
# is inside the element rather than assumed of the page.  The opener's code
# stands at the head of the credit line with the byline and the author note
# beginning an inset to its right; borrowing its quiet zone from whatever happens
# to be there is the one way this feature fails silently.  It is also why the
# element's edges are not the symbol's: everything the eye lines the code up
# against is measured to the *first dark module*, four modules inside the box.
_CODE_OPENER_SIDE_POINTS = 55.5
_CODE_MIN_MODULE_POINTS = 0.35 * 72 / 25.4
_CODE_QUIET_MODULES = 4
# HOW FAR THE CREDIT COLUMN STANDS FROM THE SQUARE, ink to ink.  It borrowed the
# end mark's 24pt on the argument that ``END / nn`` is the house's own answer to
# "how far apart do two pieces of furniture sharing a band stand", and on the
# printed page it was the wrong loan: the end mark's rule is a hairline and its
# caps are 6.8pt, so 24pt there separates two thin marks, where the opener sets a
# 19.6mm block of solid modules against a 7.4pt cap line and the same 24pt reads
# as a hole between them.  4.5 * the 3.15pt base -- one and a half grid gutters,
# 14.175pt -- closes it to where the square and the name read as one row without
# the modules ever touching the type: the quiet zone is 5.4-6pt of that gap, so
# 8pt of plain paper still stands between the element's own edge and the byline.
# MEASURED AND NOT ASSUMED: rasterised at 1200 ppi across both editions and both
# languages, the last dark column to the byline's first ink comes out at
# 14.70-14.76pt, against 24.54-24.60pt before; the fraction over nominal is the
# byline's own left side bearing and nothing else.  The alternative prototyped
# against it was ``_FIGURE_GAP``'s 15.75pt (5 * base), which measured 16.32pt and
# still left a hole; both were rendered and looked at before this one was kept.
#
# AND THE QUIET ZONE IS NOT A SECOND GAP.  The inset is stated from the symbol's
# ink (``_credit_column_inset``), so the four light modules are spent inside it:
# enlarging the square from 45pt to 55.5pt grew the quiet zone by a quarter and
# moved the type right by exactly the same amount, printing the identical 24.6pt.
# Growing a code cannot loosen this row on its own, and closing it cannot be done
# by shrinking the square.  The two decisions are separate and are taken here.
#
# It is NOT derived from the module.  A gap stated in modules would be a
# different gap on every opener -- 37-module and 41-module codes set cells 0.15pt
# apart -- and the credit line is a row the reader sees six times in an edition.
_CODE_CREDIT_GAP_POINTS = 4.5 * 3.15
# Highest first, which is the tie-break and not the choice.
# ``_fitted_source_code`` takes the level whose symbol comes out with the *widest
# cell* in the square, and only where two levels tie -- the same module count at
# two corrections -- does the higher correction win.  For a small printed code
# module width buys more read reliability than redundancy does: on this
# publication's 44-75 character URLs ECC-L sets 37 or 41 modules across the
# quiet zone where ECC-H would set 45-57 in the identical square.
#
#
# A BIGGER SQUARE CHANGED NO LEVEL, AND COULD NOT HAVE.  At 45pt the floor did
# most of the excluding -- 49 to 57 modules came out at 0.2785-0.324mm and H was
# refused outright on all but the shortest URL, Q with it on the longest -- and at
# 55.5pt almost everything clears: H now sets at 0.3996mm on a 45-character
# address where it used to refuse.  The level taken is nevertheless identical on
# every code this publication prints, because the floor can only ever exclude a
# *loser*.  The winner is the level with the fewest modules; a level with fewer
# modules than the winner would have a wider cell than the winner and so could not
# have been below a floor the winner cleared.  Growing the square therefore
# widens every cell and reopens levels that lose anyway: it buys read margin, not
# redundancy, and if the publication ever wants the redundancy it has to be asked
# for here rather than hoped for from a size change.  Measured across editions
# 001-003: the level taken is L on ten of the sixteen codes and M on six, where M
# and L tie at 41 modules and the tie goes up -- the same sixteen at both sizes.
_CODE_ERROR_LEVELS = ("H", "Q", "M", "L")
# The reading measure's own left edge inside the page area, as ``.article-tail``
# has it: the article box is 325pt centred in the 333.0079pt live width.
_CODE_MEASURE_LEFT_POINTS = 4.004
_CODE_MEASURE_POINTS = 325.0
# FOLIO_BASELINE (render.py:565-577): the line the folio's two ends share.  The
# end mark's hard floor below is stated against it.
_FOLIO_BASELINE_POINTS = 19.5
# Inter's own cap height, from the bundled faces' OS/2 table.  The code joins
# the opener's credit line, and "on the line" is measured to ink: the symbol's
# first dark row aligns with the byline's cap top, not with a line box that a
# zero leading has already collapsed.
_INTER_CAP_RATIO = 1490 / 2048
# THE SQUARE PRINTS UNNAMED, AND NOTHING HANGS UNDER IT.  It carried a violet
# `SOURCE / nn` in the house's tracked-caps idiom, on the argument that an
# unlabelled black square does not say what it is.  On the page it did not read
# as furniture: a QR code is the one mark on a sheet that every reader already
# knows the name of, so the caption said nothing the symbol had not, and two
# pieces of chrome stacked in the credit line where one belonged.  The square is
# made furniture instead by *where it stands* -- flush on the live area's left
# edge, on the credit line's own origin, with the byline and the note set as a
# column beside it -- which is the same argument the kicker makes for `FEATURE
# nn` and costs the page no second voice.  The URL is still set nowhere.
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
# What the print adapter lays over an article out of its own flow, and which
# ``_article_flow_bottom`` therefore may not measure: the tail ornament is
# positioned from the very number that walk produces, and the opener's code,
# though it stands on the first page rather than the last, is an absolute box
# whose geometry says nothing about where the article's prose ended.
_OUT_OF_FLOW_CODA_CLASSES = frozenset({"article-tail", "source-code"})
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
# The stylesheet's own cap on an opener-anchored figure's image
# (`article > figure[data-anchor="__opener__"] > img { max-height: 270pt }`),
# restated here because the source code borrows depth against it: an opener
# that carries both a figure and a code deepens its field for the code's label
# and hands the same depth back out of this cap (see ``_pin_opener_fields``).
_OPENER_FIGURE_MAX_IMAGE_HEIGHT = 270.0

# THE FIGURELESS OPENER'S FIELD IS PROPORTIONAL NOW, and this is the one number
# that shapes it: how far the standfirst's flow edge stands below the credit
# block's lowest ink.  ``_render_article_opener`` pinned ``top=238`` -- a
# 305.2756pt field whatever the chrome above it -- and the constant was cut for
# exactly one opener: a four-line title at the 35pt maximum whose code sets at
# the house 1.5pt module, whose symbol's last dark row lands 264.5208pt down the
# content box and leaves 40.7548pt of paper before the prose.  On that opener
# the field reads deliberate (edition 003 en p5).  On every shallower stack the
# same constant pays the difference out as dead sheet between the credit line
# and the standfirst -- a 108pt full-measure void on a two-line title, which the
# render critic flags on en p20/p30 and es p33 -- because the white was never a
# decision, it was the remainder of someone else's.
#
# So the field follows the fitted title flow, exactly as a figure opener's
# already does, and the gap is the constant: the field's foot stands
# ``_OPENER_STANDFIRST_GAP_POINTS`` below the credit block's lowest ink --
# the code symbol's last dark row where there is a code, the credit column's
# own last line where there is not.  40.7548 is *measured, not chosen*:
# ``305.2756 - 264.5208``, the residual the retired constant left on the one
# opener class it was right for, so the deepest opener the old rule ever set is
# reproduced to the fourth decimal and every other opener now gets the same
# deliberate breath instead of the leftovers.  (Roughly three reading leadings,
# 39pt, plus the odd 1.75 -- stated as the derivation because the derivation is
# the reason.)
_OPENER_STANDFIRST_GAP_POINTS = 305.2756 - 264.5208
# The credit's own line advance below the byline's baseline, ``_credit``'s 13
# (render.py:1741): the room the reader itself kept under a credit before
# anything else, and therefore the floor the laid-out author note must keep
# above a stated field's foot (``_validate_opener_credit_depth``).
_OPENER_CREDIT_LINE_POINTS = 13.0
# The author note's own metrics, for the one field arithmetic that needs them:
# a figureless opener without a source code has no symbol to govern its credit
# depth, so the note's own last ink governs instead.  The note sets 6.8pt on a
# 9.45pt leading with its first baseline 12 below the byline's
# (render.py:1731-1735, and the stylesheet's ``.author-note`` margin states the
# same three numbers as a box gap); the descender is Magazine Sans's own
# 0.2412109375 of the size.  Line count is predicted with ``_wrap`` over the
# *Medium* face's advances although the note prints Regular -- Medium is the
# nearest bundled metric and it is wider stroke for stroke, so the prediction
# can only over-count, and over-counting a white field is the safe direction.
# No edition to date exercises this branch (every article carries a code, and
# the code's symbol is always the lower ink); the laid-out page is asked anyway,
# by ``_validate_opener_credit_depth``, because the note is measured type and
# the field is arithmetic, and two numbers for one line is the shape of every
# defect here.
_NOTE_SIZE_POINTS = 6.8
_NOTE_LEADING_POINTS = 9.45
_NOTE_BASELINE_DROP_POINTS = 12.0
_NOTE_DESCENT_POINTS = _NOTE_SIZE_POINTS * 0.2412109375

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
# (render.py:2008-2021, `.end-mark`'s `padding-left`).  It was once lent to the
# opener's credit column as the house's own answer to "how far apart are two
# pieces of furniture sharing a band"; that loan is withdrawn -- 24pt separates a
# hairline rule from 6.8pt caps, which is not the problem a 19.6mm block of solid
# modules beside a byline poses -- and the credit column now states its own
# ``_CODE_CREDIT_GAP_POINTS``.  This number is the end mark's alone again.
_END_MARK_TEXT_INSET_POINTS = 24.0
# The lowest baseline the mark may take before the build is refused -- the folio's
# own line plus one reading leading.  It is a floor against *collision*, which is
# the only thing a floor down here can honestly be about: `END / nn` and the
# folio are both 6.8pt tracked caps, and two of them closer than the distance the
# reader sets two lines of prose at read as one line of chrome rather than as an
# article ending above a page number.  See ``_end_mark_baseline``.
_END_MARK_HARD_FLOOR_POINTS = _FOLIO_BASELINE_POINTS + _READING_LEADING

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
#
# BOTH THRESHOLDS WERE RE-EXAMINED WHEN PROSE HYPHENATION CAME ON, AND NEITHER
# MOVED.  Hyphenation (the `hyphens: auto` prose rule in weasyprint-a5.css)
# changes what a last line and a penultimate rag *are*, so the calibrations
# above -- made on an unhyphenated reader -- had to be re-measured rather than
# trusted.  Measured on edition 003, both languages: the single-word last
# lines a hyphenated reader sets still sort into two populations with the .15
# line in the gap between them -- stranded word-tails and short words at
# 6-12% of their measures, whole long words from 16% up, nothing in the
# 12-16% gap -- and the seventeen binds the hyphenated reader asks for
# open between 2.2% and 22.6% of their measures, all clear of the .33 refusal
# by more than ten points.  What hyphenation *did* break is neither number
# but the bind's reach: see the word-tail clause in `_is_runt`.
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
        "publication-name", "running-head", "subtitle",
    }
)
# Subtrees the reading flow does not include at all: opener chrome, the contents
# sheet, the hidden edition header, and preformatted text, whose whitespace is
# authored content that no pass here may rewrite.
_UNBINDABLE_SUBTREES = frozenset({"header", "nav", "pre", "code"})
_RUNT_KEY = "data-runt-key"
_NO_BREAK_SPACE = "\u00a0"

# HYPHEN LADDERS ARE REPORTED, NOT REFUSED.  CSS names a guard for consecutive
# hyphen-ended lines -- `hyphenate-limit-lines` -- and WeasyPrint 69 does not
# implement it: the property appears nowhere in the package, so the stylesheet
# cannot hold a ladder down and this module cannot pretend it did.  What it
# can do is read the laid-out line boxes and say where the ladders are, which
# is `_report_hyphen_ladders`: any prose block that ends more than this many
# consecutive lines on a hyphen is written to stderr, page and text named, and
# the build proceeds.  Two is the classical ladder allowance and matches the
# `hyphenate-limit-lines: 2` this would be were it CSS.  A refusal would be
# wrong twice over -- typographic taste is not a structural defect, and the
# evidence of how often ladders happen is exactly what the report exists to
# gather (measured on edition 003: English's longest ladder is 2, Spanish sets
# five blocks at 3-4).  If a future edition finds them intolerable, the fix
# belongs in the stylesheet's hyphenation limits, argued from these reports.
_HYPHEN_LADDER_LIMIT = 2


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
    # A report, not a gate, and deliberately between the measure guard and the
    # display guards: it reads the same settled document they do, so the
    # ladders it names are the ladders the shipped reader sets.
    _report_hyphen_ladders(document, edition)
    _validate_fitted_display(document, edition)
    _validate_opener_code_clearance(document, plan.codes_by_article)
    _validate_opener_credit_depth(document)
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
    # The tail-art ledger, parked for the packaging step to move into the
    # manifest's ``layout.tail_arts`` (see ``_TAIL_ART_LEDGER_KEY`` for why it
    # rides the edition mapping and not the return value).  Written only once
    # the reader itself has been -- a refused build must leave no ledger claiming
    # its ornaments were decided.
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

    The symbol is decided from the edition alone: the square is the design
    constant ``_CODE_OPENER_SIDE_POINTS``, ``error`` is the QR error correction
    that comes out with the widest cell inside it, ``modules`` is the symbol's
    width in cells *including* its four-module quiet zone, and ``module`` is
    one cell in points.  ``slot`` names the furniture the square belongs to and
    is the value the element carries as ``data-source-code``; it is ``"opener"``
    on every code this publication prints, and it is kept because the retired
    tail and foot slots are what the opener's constant square is a decision
    against and a second slot would be that decision reopened, not a new field.

    WHERE IT STANDS IS A MEASUREMENT.  ``left`` is a constant, but ``top`` is
    read off the laid-out byline line box (``_opener_source_codes``): the credit
    line is wherever the fitted title actually ended, and the title's line count
    is Pango's answer and not the unkerned fit's.  So a code is one of the plan's
    measured facts, it takes part in the settle comparison in
    ``_render_to_signature`` like every other, and a code built without a
    laid-out page to read is not a code this class can carry.

    ``left`` and ``top`` are the element box's placement in the page content
    box's own coordinates, ``left`` from its left edge and ``top`` from its
    head, positive downward -- CSS's own convention, because the opener is
    measured down from the page's head where the retired tail slot was
    measured up from its foot.  ``left`` is *negative* by one quiet zone: the
    flush is to the ink, so a symbol standing on the live area's left edge puts
    its four light modules outside it.
    """

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
        """The quiet zone, in points: four light modules on every side."""
        return _CODE_QUIET_MODULES * self.module

    @property
    def symbol_top(self) -> float:
        """The first dark module's own upper edge, in the same coordinates.

        Not ``top``: four light modules of quiet zone stand above the symbol,
        and every alignment the page is judged on -- the byline's cap line,
        the label's -- is an alignment to ink.
        """
        return self.top + self.quiet

    @property
    def symbol_bottom(self) -> float:
        """The last dark module's own lower edge, in the same coordinates."""
        return self.top + self.side - self.quiet

    @property
    def symbol_left(self) -> float:
        """The first dark module's own left edge, in the same coordinates.

        A column is flush when its *ink* is flush: the opener's square is set
        against the live area's left edge, the credit line's own origin, where
        the kicker's ``FEATURE nn`` and the title's first character already
        flush, and the element therefore stands one quiet zone to the left of
        it.
        """
        return self.left + self.quiet

    @property
    def symbol_right(self) -> float:
        """The last dark module's own right edge, in the same coordinates.

        The edge the credit column's own inset is measured from
        (``_credit_column_inset``), because the gap between two pieces of
        furniture is a gap between their ink.
        """
        return self.left + self.side - self.quiet


@dataclass(frozen=True, slots=True)
class ReaderPlan:
    """The placement decisions that no stylesheet can reach on its own.

    ``closing_plates`` is the number of plates the signature arithmetic in
    ``render.back_cover`` asks for, which is a function of where the content
    happens to end.  ``source_codes`` is one :class:`SourceCode` per article
    that has a source to point at, sized from its URL and stood on its opener's
    credit line; its symbol is computed from the URL alone, but its ``top`` is
    measured off the laid-out byline, so it settles with the rest and it rides
    the plan so that the decode gate and the layout consume the same object.
    ``tail_arts`` carries one ``(article_id, height, lift)`` per printed tail
    ornament, measured from where that article's own flow ended: the height the
    band prints at, and how far its foot is lifted above the standing
    ``_TAIL_ORNAMENT_FOOT_INSET`` so a max-capped band stands centred in its
    room rather than pooling the surplus above its own head.  Articles whose
    last page earned no ornament are omitted here and accounted for in the
    packaged manifest's ``layout.tail_arts`` ledger (``_tail_art_ledger``),
    drop reason and all.  ``adaptive_images`` maps a figure id to the image height an
    ``adaptive_band`` has been shrunk to so that it can still bridge the page it
    started on (render.py:901-922), and omits every band that fits at its full
    height.  ``band_offsets`` maps a figure id to the margin mirror a band
    inherited from the page it was dispatched from, and omits every band that
    stayed there.  ``end_marks`` maps an article id to the distance its end mark
    is painted back down by, which is a constant except where the reader's own
    clamp bites.  ``runt_binds`` names the prose blocks whose last two words are
    bound together because the block's last line came out as one short word; see
    ``_RUNT_MEASURE_FRACTION``.  ``midpage_band_anchors`` names the bands whose
    anchor heading was set mid-page under prose, which is what earns the heading
    its paint-only clearance (see ``_measured_midpage_anchors``).  Every one of
    them is a *measured* fact, so a plan is the output of one layout and the
    input to the next.
    """

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
        """Height per printed ornament -- ``measure.py``'s view of the plan."""
        return {article_id: height for article_id, height, _ in self.tail_arts}

    @property
    def tail_art_bands(self) -> dict[str, "TailBand"]:
        return {
            article_id: TailBand(height, lift)
            for article_id, height, lift in self.tail_arts
        }

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
    """One printed tail ornament: its band height, and its foot's lift.

    ``lift`` is how far the band's foot stands above the constant
    ``_TAIL_ORNAMENT_FOOT_INSET``: zero for a band that fills its room, and
    half the surplus for one the 214pt cap stopped short, so the capped band
    is centred between the end mark's clearance and the foot inset instead of
    stranding all its surplus above its own head.
    """

    height: float
    lift: float


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
    article's tail ornament prints only when its last page really has
    ``_TAIL_ORNAMENT_MIN_HEIGHT`` of open space below the end mark.  Neither
    question can be asked in CSS, so this renders a probe pass carrying
    neither, measures it, and renders the answer.  A third pass then has nothing
    left to change: closing plates land after the body and the ornament is out
    of flow, so neither decision can move the content that both were derived
    from -- which is asserted rather than assumed.

    The source codes are measured the same way: the square is a constant and
    its right edge a constant, but the credit line it stands on is wherever the
    opener's title actually ended, and the title's laid-out line count is
    Pango's answer, not the unkerned prediction's -- a title the fit wraps at
    three lines can set on two.  So the code's ``top`` is read off the laid-out
    byline, like the end mark's offset is read off the laid-out flow.

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
    _apply_anchor_clearances(tree, plan.midpage_band_anchors)
    _apply_adaptive_images(tree, plan.adaptive_image_heights)
    _apply_band_offsets(tree, plan.band_offset_points)
    _install_flow_clearances(tree)
    _limit_closing_plates(tree, plan.closing_plates)
    _fit_closing_plate_titles(tree, edition)
    # After ``_rewrite_landscape_plates``, which reads the tail figure this may
    # remove: a deferred plate is released by the article's coda, and the coda
    # has to still be there when that decision is taken.  Before the contrast
    # pass, which prepares whatever ornament survives for the press.
    _apply_tail_arts(tree, plan.tail_art_bands)
    _apply_print_contrast(tree)
    _apply_end_marks(tree, plan.end_mark_offsets)
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
    boxes: dict[str, tuple[float, float, "_Hyphenation | None"]] = {}
    for page in document.pages:
        for box in _walk_boxes(page._page_box):
            element = getattr(box, "element", None)
            key = getattr(element, "attrib", {}).get(_RUNT_KEY) if element is not None else None
            # The block box only: WeasyPrint hands a line box its originating
            # element too, and counting both would count every line twice.
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
    """How a laid-out prose block hyphenates, read off its own computed style.

    Read from the box rather than restated from the stylesheet, for the same
    reason every other input to the runt decision is: the stylesheet decides
    *which* blocks hyphenate (prose does, chrome and bibliography do not), and
    a prediction made from a restated constant would go quietly wrong the day
    a selector moved.  ``None`` -- no auto-hyphenation, or no dictionary for
    the block's language -- restores the pre-hyphenation prediction exactly.
    """

    lang: str
    total: int
    left: int
    right: int
    character: str


def _measured_hyphenation(style: Any) -> _Hyphenation | None:
    """``style``'s auto-hyphenation, or ``None`` where Pango takes no part."""
    if style["hyphens"] != "auto" or not style["lang"]:
        return None
    import pyphen  # WeasyPrint's own dependency; deliberately its dictionaries.

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
    """Whether this block's last line is a short word stranded on its own, *and*
    whether binding it would be an improvement.

    All the clauses after the first two are not about the defect but about the
    cure.

    The bound pair has to fit a line of its own, or Pango has no break left to
    take and ``_validate_reader_measures`` refuses the build over a repair this
    module chose.

    A WORD'S OWN TAIL IS NOT A BINDABLE RUNT.  On a hyphenating block the last
    line can be the stranded tail of the block's *final word* -- edition 003
    sets ``...skipped when appro-`` / ``priate.``, a 9% last line -- because
    WeasyPrint has no ``hyphenate-limit-last`` to forbid a hyphen before the
    very last line.  The bind cannot touch that break: ``U+00A0`` removes the
    *space* break between the last two words, and the break that stranded the
    tail is a hyphenation point inside one word, which Pango takes on the bare
    pass and on the bound pass alike.  This was measured, not deduced: binding
    the fragment cases of edition 003 (two in English, five in Spanish)
    re-laid every one of them character for character, the tail still alone on
    its line.  So a single-word last line under a penultimate line that ends
    on the block's own hyphenate character is refused -- not because the
    defect is acceptable but because this repair provably does nothing to it,
    and a no-op bind would sit in the plan's ledger claiming a repair that
    never happened.  On an unhyphenated block (``hyphenation is None``) the
    clause never fires and the prediction is the pre-hyphenation one exactly.

    And the line the bound word leaves has to still read as a line.  Under greedy
    breaking nothing above the penultimate line moves, so the penultimate comes
    out exactly as wide as it is now less its own final word -- predictable from
    the measured line without laying the paragraph out again.  Where that leaves
    more than ``_RUNT_MAX_RAG_FRACTION`` of white the repair has traded one short
    line for two, which is the worse defect, and the bind is refused.

    All predictions are summed unkerned in the reading face, as everything else
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
    """One prose block's longest run of consecutive hyphen-ended lines.

    ``key`` is the block's runt key -- the same name a ``ReaderPlan`` bind or a
    ``mag measure`` paragraph row uses -- ``page`` is the reader page the run
    starts on, and ``sample`` is the run's first line, so the report puts an
    eye on the page without anyone re-deriving which paragraph it meant.
    """

    key: str
    page: int
    run: int
    sample: str


def _measured_hyphen_ladders(document: Any) -> tuple[HyphenLadder, ...]:
    """Every prose block whose hyphen-ended lines run past ``_HYPHEN_LADDER_LIMIT``.

    Measured, like the runt binds, off the finished page and never predicted:
    a line has ended on a hyphen when its laid-out text says so, whether Pango
    hyphenated a word there (it appends the block's own ``hyphenate-character``
    to the line) or the line broke after an explicit hyphen in a compound.
    Both count, because a reader scanning the rag sees hyphens and not their
    provenance.  Line boxes accumulate across a block's page fragments under
    the block's key, exactly as ``_measured_runt_binds`` gathers them, so a
    ladder that straddles a page break is still one ladder.
    """
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
            ladders.append(
                HyphenLadder(key, longest[0][1], len(longest), longest[0][0])
            )
    return tuple(ladders)


def _report_hyphen_ladders(document: Any, edition: Edition) -> tuple[HyphenLadder, ...]:
    """Say where the ladders are, on stderr, and refuse nothing.

    The report is the whole deliverable: WeasyPrint has no
    ``hyphenate-limit-lines`` for the stylesheet to state (see
    ``_HYPHEN_LADDER_LIMIT``), so whether the reader needs a real guard is an
    open question, and this is the measurement that will answer it edition by
    edition.  It rides the build log rather than the manifest because it is
    typographic evidence and not provenance -- and it returns what it wrote so
    the audit is callable as a measurement on its own.
    """
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

    What the three openers then do with that differs.  An article *with* a
    figure ends on ``_set_reading_frame(top=self.y)`` after handing 13 back
    (render.py:2001-2003).  An article *without* one used to ignore all of it
    and pin ``top=238`` -- the reader's rule, reproduced here as a stylesheet
    constant until edition 003 showed what the constant costs: the pinned field
    was cut for the deepest credit stack the opener can carry, and every
    shallower title paid the difference out as up to 96pt of dead sheet between
    its credit line and its standfirst (see ``_OPENER_STANDFIRST_GAP_POINTS``).
    So the figureless field is now stated here too, from the same fitted-title
    arithmetic the figure opener uses: the credit block's lowest ink -- the code
    symbol's last dark row, or the note's own last line where an article prints
    no code -- plus one constant, deliberate gap to the standfirst
    (``_opener_prose_field``).  The editorial keeps the reader's clamp,
    ``top=min(self.y, 390)`` (render.py:2091), so its natural height is stated
    here and the stylesheet's ``min-height`` is the ``min``.  Every field is a
    *flow* height, measured from the page's content box in the same convention as
    every other box: a CSS box top stands ``_FIRST_BASELINE_INSET_POINTS`` above
    the ``self.y`` it means.
    """
    by_id = {article.id: article for article in edition.articles}
    for article in tree.iter("article"):
        header = _opener_header(article)
        declared = by_id.get(article.get("data-article-id") or "")
        if declared is None:
            raise ValidationError(
                f"No edition article matches opener {article.get('data-article-id')!r}"
            )
        has_figure = _opener_figure(article) is not None
        height, minimum = _ARTICLE_TITLE_BOX
        size, lines = _fitted_display(
            str(declared.title),
            _LIVE_WIDTH_POINTS,
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
                # The code's depth comes out of the figure's own band, not out
                # of the page: the field deepens so the label clears the
                # figure, and the figure's height cap gives the same depth
                # back, so an opener that was full stays a page and not two.
                # A figure bound by its width rather than the cap cannot give
                # it back; then the flow simply moves, and an article that no
                # longer fits its own cap is refused loudly downstream.
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
            # The header's height and the *title's* reservation are the same
            # number until a code deepens the field, and then they are not: the
            # extra depth is the label's room, not the title's.  Both are stated
            # because `_validate_fitted_display` judges a title against what was
            # fitted for the title -- given the field it would hand a loosened
            # title the label's room, and the guard would pass a page where the
            # title has pushed the credit block, the code and the label into the
            # artwork.  `data-title-field` is that reservation, in points, stated
            # by the arithmetic that owns it.
            header.set("data-title-field", f"{title_field:.4f}")
        else:
            # The figureless field, stated from the same arithmetic: the credit
            # block's lowest ink plus the one deliberate gap.  The title's own
            # reservation is stated beside it for the same reason a figure
            # opener states both -- the field is deeper than the title's room
            # by the credit block and the gap, and a guard that judged the
            # title against the whole field would hand a Pango-loosened title
            # the credit's room and pass a page where the title has pushed the
            # byline, the note and the square down into the standfirst.
            header.set(
                "style", f"height: {_opener_prose_field(declared, size, len(lines)):.4f}pt"
            )
            header.set(
                "data-title-field",
                f"{_OPENER_FIGURE_FIELD_BASE + _opener_title_flow(size, len(lines)):.4f}",
            )
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


def _opener_code_field_floor(article: Any, size: float, lines: int) -> float:
    """The field an opener figure needs so its article's code clears the art.

    The figure's head is the field's foot, and the square's last dark row is the
    lowest ink the credit block now sets -- an opener figure hides the author
    note, and nothing hangs under the symbol -- so the field must run to the
    symbol's own foot plus the credit's 12pt pad.  It ran to a label's baseline
    while there was a label, which cost every figure opener a further 11.95pt of
    image cap; that depth is now given back to the artwork.

    Computed from the *fitted* line count rather than measured: the fit never
    under-counts a valid build's lines (``_validate_fitted_display`` refuses the
    one direction kerning can cheat), so a field stated from it is deep enough
    wherever Pango sets the title tighter -- and a field is white space, not an
    alignment, so deep enough is exact enough.  Zero for an article with no code
    to place.
    """
    code = _opener_credit_code(article)
    if code is None:
        return 0.0  # ``_opener_source_codes`` raises the loud refusal.
    return _opener_symbol_bottom(code, size, lines) + _OPENER_BYLINE_PAD_POINTS


def _opener_credit_code(article: Any) -> SourceCode | None:
    """The code this article's credit line opens with, fitted from its URL.

    ``None`` covers both an article with no ``source_url`` -- which prints no
    code and is not an error -- and a URL no error-correction level can set over
    the module floor, which *is* an error and stays ``_opener_source_codes``'s
    to raise loudly; the field arithmetic must not decide it quietly.
    """
    url = str(getattr(article, "source_url", "") or "").strip()
    if not url:
        return None
    return _fitted_source_code(str(article.id), url, _CODE_OPENER_SIDE_POINTS)


def _opener_byline_baseline(size: float, lines: int) -> float:
    """Where the credit line's byline baseline lands, from the fitted title."""
    return (
        _OPENER_TITLE_TOP_POINTS
        + _opener_title_flow(size, lines)
        + _OPENER_TITLE_TO_CREDIT_POINTS
    )


def _opener_symbol_bottom(code: SourceCode, size: float, lines: int) -> float:
    """The symbol's last dark row, from the fitted title: cap top plus the ink."""
    return (
        _opener_byline_baseline(size, lines)
        - _BYLINE_SIZE_POINTS * _INTER_CAP_RATIO
        + code.side
        - 2 * code.quiet
    )


def _opener_prose_field(article: Any, size: float, lines: int) -> float:
    """The white field a figureless opener reserves, from its own credit block.

    The field's foot is the standfirst's flow edge, and it stands one constant,
    deliberate ``_OPENER_STANDFIRST_GAP_POINTS`` below the credit block's lowest
    ink -- which of the block's three pieces that is depends on the article:

    * With a source code, the symbol's last dark row.  The square is a shade
      taller than a byline and a two-line note by design (see
      ``_CODE_OPENER_SIDE_POINTS``), so on every article this publication has
      printed it is the governing ink.
    * The author note's own last line, where a note out-rags the symbol or the
      article prints no code.  Predicted from ``_wrap`` like every fitted
      decision here, over the Medium face's advances, which only ever
      over-count the Regular the note prints in -- the safe direction for a
      white field (see ``_NOTE_SIZE_POINTS``).  The laid-out page is asked
      again by ``_validate_opener_credit_depth``.
    * The byline's own cap line, for an article with neither code nor note.

    Computed from the *fitted* line count rather than measured, exactly as
    ``_opener_code_field_floor``: the fit never under-counts a valid build's
    lines, so a field stated from it is deep enough wherever Pango sets the
    title tighter -- and a field is white space, not an alignment, so deep
    enough is exact enough.
    """
    baseline = _opener_byline_baseline(size, lines)
    ink_foot = baseline  # 7.4pt caps set no ink below their own baseline.
    code = _opener_credit_code(article)
    column = _LIVE_WIDTH_POINTS
    if code is not None:
        ink_foot = max(ink_foot, _opener_symbol_bottom(code, size, lines))
        column = _LIVE_WIDTH_POINTS - _credit_column_inset(code)
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

    The anchor heading itself is marked as well, because a third laid-out fact
    hangs off the pair: whether the heading was set mid-page under the bridge's
    last line, which is what decides its paint clearance (see
    ``_measured_midpage_anchors``).
    """
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
    """State each shrunk band's measured image height, keeping what is stated already.

    Merged onto the element's own style, the way ``_apply_band_offsets`` merges
    its own, and not written over it: an opener figure whose article carries a
    source code already states a ``max-height`` here -- the depth the field
    borrowed for the code's label, handed straight back out of the image's cap
    (``_pin_opener_fields``) -- and this pass runs after it.  No
    ``adaptive_band`` is anchored to an opener in any edition today, but
    ``media_schema`` permits ``layout: adaptive_band`` with ``anchor:
    __opener__``, and a giveback silently overwritten is a page taller than the
    adapter reserved.  Both declarations are ``max-height`` and the later one
    wins the cascade, which is the right way round: the shrink measured here is
    bounded by ``_FIGURE_BAND_MAX_IMAGE_HEIGHT``, under the 270pt cap the
    giveback reduces, so it is the tighter of the two.
    """
    for figure in tree.iter("figure"):
        height = heights.get(figure.get("data-figure-id") or "")
        if height is None:
            continue
        for image in figure.iter("img"):
            style = (image.get("style") or "").strip().rstrip(";")
            image.set(
                "style", f"{style + '; ' if style else ''}max-height: {height:.4f}pt"
            )


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
    # Educated like the heading itself: the laid-out page carries the educated
    # text, so an anchor authored with a straight quote must be compared -- and
    # measured -- as the marks the page actually sets.
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


def _measured_midpage_anchors(document: Any) -> tuple[str, ...]:
    """Each band whose anchor heading was set mid-page, under its bridge's last line.

    ``_set_custom_frame`` drops a band anchor's space-before because a band
    always sets a frame it then starts at (render.py:1135), and the stylesheet
    reproduces that with ``margin-top: 0``.  For an anchor that *opens* a page
    the two rules agree with the rest of the reader -- no heading gets space at
    a frame's own top.  For an anchor that lands mid-page they leave the heading
    2.65pt off the paragraph above it, against 17.65pt for every other prose
    heading; restoring the margin in flow was tried and repaginates the Spanish
    edition (see the stylesheet's band-anchor note), so the repair is a
    paint-only offset instead, and this is the measurement that gates it: an
    anchor is mid-page exactly when its heading starts on the page where the
    bridge block's last line ended.  The offset moves ink and never a box, so
    the plan that carries it cannot change the pages it was measured from.
    """
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
    """Class the measured mid-page band anchors so the stylesheet can clear them."""
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
    """Give every treated raster the print-safe derivative the reader prints.

    ``prepare_print_image`` (render.py:755 and :1040) measures paper dominance,
    mark coverage and median mark contrast, and escalates contrast until a pale
    image survives an uncoated press.  It reaches every curated figure -- a
    contained image and a landscape plate -- and, now that the ornament prints
    again, the tail art beside them: authored house artwork should never need
    the escalation, but "should never" is exactly what a preflight exists to
    verify, and an ornament that ships pale is as soft a page as a figure that
    does.  Cover art and a closing plate are drawn with ``_draw_image_fill``
    and stay untreated.

    The treated raster only exists in memory, so it travels to the layout as a
    data URI.  The original source stays on the element, because a placement is
    reported against the file the edition curated and not against a derivative.
    """
    import base64

    from .image_contrast import prepare_print_image

    for figure in tree.iter("figure"):
        figure_id = figure.get("data-figure-id")
        if not figure_id and "article-tail" not in _element_classes(figure):
            continue
        # The refusal has to name what the editor actually curated, and this pass
        # reaches two different kinds of artwork: a figure the edition placed by
        # id, and an article's own tail ornament, which has none.
        subject = f"curated figure {figure_id}" if figure_id else "article tail art"
        for image in figure.iter("img"):
            source = image.get("src")
            if not source or source.startswith("data:"):
                continue
            path = Path(_path_from_uri(source))
            try:
                prepared = prepare_print_image(path)
            except Exception as exc:  # Pillow's failures differ by format.
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
    """Stand each article's source code in its opener's own credit block.

    The code is opener furniture now, not a coda: it went in beside the title
    because the opener is where the article already states its provenance --
    the kicker names the mode, the byline names the author, and the square
    names the source.  The element is a child of the opener's ``header`` so it
    lands on the article's first page, and it is absolutely positioned like the
    figure frames and the tail ornament, so it takes nothing out of any box and
    cannot displace a line.  Every one of its four edges is stated inline
    because no stylesheet can reach any of them: three come from the square's
    own constant and the URL's module, and ``top`` is measured off the byline
    the page laid out.

    IT OPENS THE CREDIT LINE, FLUSH LEFT ON THE LIVE AREA.  The symbol's first
    dark column lands on the live area's left edge -- the credit line's own
    origin, where the kicker's ``FEATURE nn`` and the title's first character
    already flush -- and its first dark row stands on the byline's cap top.  The
    byline and the author note then set as one column an inset to its right
    (``_fit_credit_measure``), so the row reads left to right as the reader does:
    the square, then who wrote the piece and who they are.  Nothing hangs under
    the square; it is furniture because of where it stands, and the credit column
    beside it is the thing that says so.

    Unnamed on purpose.  A QR square is the one mark on the sheet whose name
    every reader already knows, so the retired ``SOURCE / nn`` said nothing the
    symbol had not and put a second voice in a line that has one.
    """
    for article in tree.iter("article"):
        code = codes.get(article.get("data-article-id") or "")
        if code is None:
            continue
        header = _opener_header(article)
        image = SubElement(header, "img")
        image.set("class", "source-code")
        image.set("alt", "")
        image.set("aria-hidden", "true")
        image.set("data-source-code", code.slot)
        image.set("src", _source_code_source(code))
        image.set(
            "style",
            f"left: {code.left:.4f}pt; top: {code.top:.4f}pt; "
            f"width: {code.side:.4f}pt; height: {code.side:.4f}pt",
        )
        _fit_credit_measure(article, header, code)


def _credit_column_inset(code: SourceCode) -> float:
    """Where the credit column's own type begins, beside the square.

    Ink to ink: one ``_CODE_CREDIT_GAP_POINTS`` to the right of the symbol's last
    dark module.  Measured from the *symbol* and not from the element, because the
    quiet zone lives inside the box: an inset stated on the box would print as the
    gap plus four light modules, and the four light modules are exactly the part
    of this distance that grows when the square does.  That is why enlarging the
    square did not widen the printed gap by itself, and why tightening it is a
    separate decision taken separately -- see ``_CODE_CREDIT_GAP_POINTS``.

    The column runs from here to the live area's right edge:
    ``_LIVE_WIDTH_POINTS - side + 2 * quiet - gap`` wide.  It is no longer the
    measure the retired right-flush arrangement gave the author note -- the square
    grew by 10.5pt and the gap closed by 9.825pt, and the gap won, so the column
    comes out 1.37-1.60pt *wider* than it was, depending on the URL's module (the
    quiet zone grew with the square and gave part of the closure back).  Wider is the safe
    direction: a wider measure can only shed a rag line, never take one, so no
    author note can gain a line and no opener can gain depth from this row.
    """
    return code.symbol_right + _CODE_CREDIT_GAP_POINTS


def _fit_credit_measure(article: Element, header: Element, code: SourceCode) -> None:
    """Set the byline and the author note as one column beside the code.

    Both are inset, and that is the whole of the new arrangement: the square
    stands on the credit line's own left origin, so the type that used to start
    there starts one inset to the right of the symbol's ink instead, and the
    byline and the note -- the author's name and who the author is -- read as a
    single block against the square rather than as two lines with a mark at one
    end.  The note is *also* given the column's width, because it is prose-length
    (up to 160 characters on a 9.45pt leading) and would otherwise run from the
    inset to the page's own edge and out past the live area.

    The line the note may take for it is free: an opener without a figure holds
    the note inside a white field stated deep enough for it (and for the
    symbol below it, which governs -- ``_opener_prose_field``), and an opener
    with one hides the note entirely, so no prose can move.  In fact none is
    taken -- the column comes out
    a fraction *wider* than the note's old right-flush measure, which is the
    direction that cannot cost a line (see ``_credit_column_inset``).

    THE BYLINE'S REFUSAL IS A DIFFERENT FAILURE NOW.  It used to run at the
    code from the left and could reach it; inset, it can no longer touch the
    square at all -- it starts past it and grows away from it.  What it can do is
    overrun the *measure's right edge*, where the old arrangement had the whole
    of the live width in hand, so the refusal is re-derived to that edge: a
    byline whose ink would pass the live area is refused rather than wrapped,
    because it is a single zero-leading line and a wrapped one stacks two rows
    of ink on one baseline.
    """
    column = _LIVE_WIDTH_POINTS - _credit_column_inset(code)
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
        if _string_width(text, "sans-semibold", _BYLINE_SIZE_POINTS) > column:
            raise ValidationError(
                f"Article {article.get('data-article-id')}'s byline {text!r} reaches "
                f"past the {column:.2f}pt credit column beside its own source code "
                "and out through the live area's right edge; shorten the byline "
                "rather than wrapping a zero-leading line."
            )


def _fitted_source_code(article_id: str, url: str, room: float) -> SourceCode | None:
    """The widest-celled code a square of ``room`` points can carry.

    One knob, taken in the direction that survives a phone camera.  The square
    is a constant, so the module is whatever ``room`` divided by the symbol's
    own width leaves, and the level chosen is the one that leaves the most: a
    lower error correction is a shorter symbol, a shorter symbol is a wider
    cell in the same square, and a wider cell is worth more to a real scan
    than redundancy behind cells too small to resolve.  Measured on this
    publication's URLs, ECC-L sets 37-41 modules across the quiet zone where
    ECC-H sets 45-57 in the identical square, so L wins on width and the outcome
    does not depend on the square's size at all: the floor below can only ever
    drop a level whose symbol is *longer* than the winner's, which is a level
    that would have lost the comparison anyway.  Enlarging the square from 45pt
    to 55.5pt changed the level on none of the sixteen codes editions 001-003
    print, and would not have.

    HIGHEST CORRECTION WINS A TIE -- two levels whose symbols come out the
    same width, which QR's stepped versions produce regularly -- because there
    the extra redundancy is free.

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
        module = room / modules
        if module < _CODE_MIN_MODULE_POINTS:
            continue
        if best is None or module > best.module + _MODULE_EPSILON:
            best = SourceCode(article_id, "opener", level, modules, module, url)
    return best


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

    ONE INK.  The three finder patterns
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
    and so the symbol is set entirely in INK.  The house violet is not spent on
    the square at all now: the label it moved to is retired, and what makes the
    square the publication's own is its place on the grid rather than a colour.

    The ground is *painted* rather than left transparent, which is the one place
    robustness beats fidelity: the quiet zone is only a quiet zone if nothing
    shows through it, and the opener's code stands an inset away from the
    credit column's own type.

    One path of touching subpaths and not a field of separate rectangles.  A PDF
    fill computes coverage once over the whole path, so modules that share an
    edge merge cleanly; drawn as individual rectangles they would each antialias
    against their neighbour and lay a grid of pale hairlines through the symbol
    at exactly the scale a binariser is looking at.  Runs are merged along the
    row first for the same reason, and to keep the URI small.  With one ink there
    is no second path for the first to antialias against either, which is the
    hairline argument's own conclusion taken one step further.

    No centred publication mark.  ECC-H would carry one, but the opener's
    codes are set at whatever level leaves the widest cell and that is
    regularly not H; a mark on some codes and not others is not a house style,
    and occluding a code that has already traded away redundancy for cell size
    is the trade made twice.
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
        runt_binds=tuple(
            sorted({*runt_binds, *_measured_runt_binds(document)}, key=int)
        ),
        midpage_band_anchors=_measured_midpage_anchors(document),
    )


def _opener_source_codes(edition: Edition, document: Any) -> tuple[SourceCode, ...]:
    """Every article's code, sized from its URL and placed in its opener.

    The square and its right edge are constants; where it stands vertically is
    a *measurement*, like the end mark's offset.  The code joins the credit
    line, and the credit line is wherever the opener's fitted title actually
    ended -- the title's laid-out line count is Pango's answer and not the
    unkerned prediction's, so the byline's baseline is read off the laid-out
    boxes rather than recomputed from a fit that can be one line generous.

    WHERE IT STANDS.  The symbol's first dark row lands on the byline's cap
    top -- ink to ink, like every alignment a code is judged on -- and its
    first dark column lands on the live area's left edge, the credit line's own
    origin, where the kicker's ``FEATURE nn`` and the title's first character
    already flush.  Square first, then the byline and the author note as one
    column beside it (``_fit_credit_measure``); below the byline the square runs
    down the side of that column and into the white field the opener reserves.

    CAP TOP AND NOT A CENTRING, and the alternative was built and rendered
    before this was kept.  Optically centring the symbol on the credit column's
    own ink -- byline cap top to the note's last baseline -- reads no better on a
    full opener and fails on the two openers that matter: a figure opener hides
    the note, so the block the symbol would centre on is a single 5.4pt cap band
    and a 35pt square centred on it rises 15pt into the fitted title, and on a
    prose opener the square's position becomes a function of how many lines the
    note happens to rag onto, so editing a biography moves the furniture.  The
    cap top is the same alignment the right-flush arrangement used, mirrored: one
    number, no measurement of the note, and the symbol's head on the line the
    reader's eye already has.

    An article with no ``source_url`` prints no code and is not an error -- a
    source record need not carry a canonical URL, and the editorial has no
    source at all.
    """
    baselines = _measured_byline_baselines(document)
    codes: list[SourceCode] = []
    for article in edition.articles:
        url = str(getattr(article, "source_url", "") or "").strip()
        if not url:
            continue
        code = _fitted_source_code(str(article.id), url, _CODE_OPENER_SIDE_POINTS)
        if code is None:
            raise ValidationError(
                f"Article {article.id} cannot carry a scannable source code for {url}: "
                f"the opener square offers {_CODE_OPENER_SIDE_POINTS:.2f}pt, and even "
                f"at the lowest error correction the symbol's module would fall under "
                f"{_CODE_MIN_MODULE_POINTS * 25.4 / 72:.2f}mm. Shorten the canonical URL."
            )
        baseline = baselines.get(str(article.id))
        if baseline is None:
            raise ValidationError(
                f"Article {article.id} carries a source code but its opener laid out "
                "no byline line; the code's credit-line anchor does not exist."
            )
        top = baseline - _BYLINE_SIZE_POINTS * _INTER_CAP_RATIO - code.quiet
        # Flush to the ink on the live area's left edge, so the element itself
        # stands one quiet zone outside it -- four light modules of painted paper
        # in the gutter margin, the exact mirror of the overhang the right-flush
        # arrangement put in the fore-edge.
        left = -code.quiet
        codes.append(replace(code, left=left, top=top))
    return tuple(sorted(codes))


def _measured_byline_baselines(document: Any) -> dict[str, float]:
    """Each opener byline's laid-out baseline, in page-content-box points.

    The byline is a single zero-leading line inside the opener's header, so its
    baseline is the line box's own, converted from page coordinates to the
    content box the code's ``top`` is stated against.
    """
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
    """The open room an article's last page offers its ornament, in points.

    From the end mark's ``_TAIL_ORNAMENT_ENDMARK_CLEARANCE`` down to the
    ``_TAIL_ORNAMENT_FOOT_INSET`` above the frame's foot.  Negative where the
    flow ends below the band's own head room, which is stated rather than
    clamped because the ledger's drop reason wants the measured number.

    ONE NUMBER IS DELIBERATELY NOT THE READER'S, and it is the datum the two
    bounds are measured from.  The reader took the end mark's baseline through
    its own ``max(frame_bottom + 5, y - 1)``; ``_end_mark_baseline`` refuses
    that clamp on purpose -- see the argument there -- so wherever the clamp
    would have fired, the baseline this measures from is lower than ReportLab's
    and the room it reports is shorter by the same amount.  Measured on edition
    002, the clamp fires on exactly one article ending, es
    ``software-factories`` on p9: 42.48 against the clamp's 50.0, 7.5pt.  That
    article declares no tail art, and a page ending that low has no ornament to
    lose either way.  The divergence is stated because it is one, not because
    it has reached the paper.
    """
    bottom = _FRAME_BOTTOM_POINTS + _TAIL_ORNAMENT_FOOT_INSET
    top = _end_mark_baseline(flow_bottom) - _TAIL_ORNAMENT_ENDMARK_CLEARANCE
    return top - bottom


def _measured_tail_art(article: Any, flow_bottom: float) -> TailBand | None:
    """The band this article's tail ornament prints as, or nothing.

    The rules and their numbers are argued at the constants themselves (see
    ``_TAIL_ORNAMENT_MIN_HEIGHT``): the band prints only where its room clears
    the floor a full-measure void starts reading as dead sheet at, fills that
    room exactly when the 214pt cap does not bite, and stands centred in it --
    half the surplus below, half above -- when it does.

    The 300 ppi floor is the reader's own (render.py:1985-1997): the committed
    raster must resolve at the crop-filled 325pt-wide band it prints across,
    or the build refuses rather than shipping a soft ornament.
    """
    if getattr(article, "tail_art", None) is None:
        return None
    available = _tail_art_room(flow_bottom)
    if available < _TAIL_ORNAMENT_MIN_HEIGHT:
        return None
    height = min(available, _TAIL_ORNAMENT_MAX_HEIGHT)
    try:
        from PIL import Image

        with Image.open(article.tail_art) as image:
            pixels = (int(image.width), int(image.height))
    except (OSError, ValueError) as exc:
        raise ValidationError(
            f"Article tail art needs a readable raster source: {article.tail_art}"
        ) from exc
    effective_ppi = min(
        pixels[0] / (_CODE_MEASURE_POINTS / 72),
        pixels[1] / (height / 72),
    )
    if effective_ppi < _MIN_FIGURE_PPI:
        raise ValidationError(
            f"Article tail art {article.tail_art} resolves to {effective_ppi:.1f} ppi; "
            f"the minimum is {_MIN_FIGURE_PPI:.0f} ppi"
        )
    return TailBand(height, (available - height) / 2)


# The private key ``render_a5_weasyprint`` parks the tail-art ledger under in
# ``edition.raw``, and ``package_release`` moves into the packaged manifest's
# ``layout.tail_arts``.  It rides the edition mapping because that mapping is
# the one object the renderer holds that reaches the packaging step whole: the
# render seam returns a ``RenderLayout``, whose fields the compiler maps to
# fixed manifest keys one by one, and the compiler sits between two agents'
# work and is not this change's to widen.  The literal is restated in
# ``package.py`` (``RENDERED_TAIL_ARTS_KEY``) rather than imported, because
# packaging must not import a renderer -- selecting ReportLab keeps this module
# deletable (see ``render_engine``'s isolation contract).
_TAIL_ART_LEDGER_KEY = "_rendered_tail_arts"


def _tail_art_ledger(
    document: Any, edition: Edition, plan: ReaderPlan
) -> list[dict[str, Any]]:
    """One row per article: what its declared ornament became on the page.

    This is the manifest's ``layout.tail_arts`` contract, the one the render
    critic reconciles (``render_critic.py``, ``tail-art-dropped``): every
    article appears, ``declared`` says whether the edition offered a motif,
    ``printed``/``height_points`` say what the pages did with it, and
    ``drop_reason`` names the measured shortfall when they did nothing.  The
    old behaviour -- ``article.remove(figure)`` and no record anywhere -- made
    the rarest element in the magazine also the only one that could vanish
    silently; the ledger is what makes a dropped ornament a decision someone
    can see and overrule.

    ``printed`` and ``height_points`` come from the settled plan rather than
    being re-decided here, so the ledger can never disagree with the pages the
    plan actually laid out; only a drop's *reason* re-measures the room, off
    the same flow bottoms the plan's own equality has already settled.
    """
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
            row["drop_reason"] = (
                f"the article's last page leaves {room:.1f}pt of open tail room "
                f"between the end mark's {_TAIL_ORNAMENT_ENDMARK_CLEARANCE:.0f}pt "
                f"clearance and the {_TAIL_ORNAMENT_FOOT_INSET:.0f}pt foot inset; "
                f"the ornament prints in {_TAIL_ORNAMENT_MIN_HEIGHT:.0f}pt or more"
            )
        rows.append(row)
    return rows


# ``.article-tail``'s own ``bottom`` -- the 24pt foot inset stated against the
# box the ornament is positioned in, whose foot stands
# ``_FIRST_BASELINE_INSET_POINTS`` below the page's content box.  A printed
# band's lift is added to it, so the stylesheet's constant and the page's
# decision meet in one inline declaration.
_TAIL_BAND_CSS_FOOT_POINTS = _TAIL_ORNAMENT_FOOT_INSET - _FIRST_BASELINE_INSET_POINTS


def _apply_tail_arts(tree: Element, bands: Mapping[str, TailBand]) -> None:
    """Print each article's tail ornament as the band its own page earned.

    The figure is the semantic edition's own; what the print adapter adds is
    the page's decision.  An article whose last page earned no ornament -- or
    which declared none -- loses the figure from the print tree, exactly as
    ``_article_tail_ornament`` simply drew nothing (the drop itself is recorded
    in ``_tail_art_ledger``, so losing the figure is no longer losing the
    fact); one that earned it keeps the figure with its measured height and
    foot stated inline.  The stylesheet owns everything that does not depend
    on the measurement: the band's 325pt measure and its crop-fill are
    ``.article-tail``'s own, and its ``bottom`` here is the stylesheet's own
    constant plus the lift that centres a max-capped band in its room.
    """
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
    had left instead of taking its own space.

    So the mark keeps its own space and the floor becomes a real one.  Below
    ``_END_MARK_HARD_FLOOR_POINTS`` its rule and its label would reach the
    folio's own band and the two would read as one line of chrome; that is
    refused rather than squeezed, because a page that cannot hold its own
    ending is a pagination fault and not something to absorb silently.
    Nothing in edition 002 comes within 10pt of it -- es p9, the one page the
    old clamp fired on, sets at 42.48 against a floor of 32.5.

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
    carries the same copy.  The article's out-of-flow furniture is excluded from
    the walk because the tail ornament is exactly what this measurement decides:
    it is placed *from* this number, so counting it into it would make the plan
    measure its own output and never settle.  The opener's code and label are
    excluded for the same reason and not as tidiness: their ``top`` is measured
    off the laid-out byline, so they too are placed from a measurement of the
    page they stand on -- and an absolute box says nothing about where an
    article's prose ended in any case.
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
    # The editorial cap is a ceiling an edition may tighten, not a constant it
    # must repeat; ``declared_editorial_page_cap`` owns that rule for both
    # engines and refuses anything looser than ``_MAX_EDITORIAL_PAGES``.
    declared_editorial_page_cap(edition.raw, _MAX_EDITORIAL_PAGES)


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
        # CSS owns its own fragmentation, so this engine has no frames to
        # measure; the balance field is permanently empty for every engine.
        # See reader_layout.RenderLayout.
        article_frame_usage={},
        article_terminal_balance={},
        figure_placements=placements,
    )


def _asset_is_placed(asset: HtmlAsset, plan: ReaderPlan | None) -> bool:
    """Whether the reader was laid out with this asset on a page at all.

    An edition's inventory offers every closing plate and every declared tail
    motif; the plan decides how many plates the signature needs and which last
    pages earned their ornament, so the inventory alone cannot say what should
    have been found.
    """
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
    editorial_cap = declared_editorial_page_cap(edition.raw, _MAX_EDITORIAL_PAGES)
    if layout.editorial_pages is not None and layout.editorial_pages > editorial_cap:
        raise ValidationError(
            f"WeasyPrint editorial page cap exceeded: {layout.editorial_pages} pages "
            f"(maximum {editorial_cap})"
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

    * An opener's ``h1`` margin box must end inside the room reserved for the
      title -- ``_opener_title_reservation``, which is the ``data-title-field``
      ``_pin_opener_fields`` states on every article opener, figure or not,
      except where a source code deepened it.  Its foot is where the prose, the
      credit block's own lowest ink, or the opener figure begins.
    * A closing plate's caption must be set on the same number of lines
      ``_fitted_plate_title`` chose its size for.  The caption is positioned from
      that size alone, so an extra line hangs below the plate's title box.

    Measured on edition 002 as authored, both languages: every opener clears its
    title's reservation, the tightest by 16.69pt, and every plate caption is set
    on its fitted line count.
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


def _opener_title_reservation(header: Any) -> float:
    """The room that was reserved for *this* opener's title, in points.

    Not the laid-out header's height, and the difference is the whole of this
    function.  An opener whose article carries a source code states a field
    deeper than its title's own reservation, because the square's last dark row
    is the lowest ink the credit block sets and it has to clear the artwork
    (``_opener_code_field_floor``).  On edition 002's knowledge-base opener that
    is 40.84pt of extra depth -- well over half a title line -- and a guard that
    measured the title against it would let a Pango-loosened title take a line
    the fit never budgeted for, silently, by spending the code's room on it.
    The title would then push the credit block and the square down into the
    figure it stands over, which is exactly the defect this guard exists for, and
    the decode gate would not notice: the square is painted over the artwork
    rather than under it, so it still scans.

    So the reservation is read from ``data-title-field``, which
    ``_pin_opener_fields`` states beside the field for this reason -- on every
    article opener now, figure or not, since the figureless field became
    per-article arithmetic instead of a stylesheet constant.  What still falls
    through to the laid-out box is exactly the editorial and the sections,
    whose field *is* the title's arithmetic and which state no attribute.
    """
    element = getattr(header, "element", None)
    attributes = getattr(element, "attrib", {}) if element is not None else {}
    stated = attributes.get("data-title-field")
    if stated is not None:
        return float(stated)
    return float(header.height) * _POINTS_PER_CSS_PIXEL


def _validate_opener_code_clearance(
    document: Any, codes: Mapping[str, SourceCode]
) -> None:
    """Refuse a page whose source code has come down into the opener's artwork.

    THE GUARD SURVIVES THE LABEL IT WAS WRITTEN FOR, because what it guards was
    never the label.  It is belt and braces over ``_opener_title_reservation``,
    and the belt is the other one: that guard holds the *title* inside the room
    fitted for it, and with the title held the credit block below it cannot move,
    so neither can the square.  But the code's ``top`` is a *measurement* -- read
    off the laid-out byline (``_opener_source_codes``) -- while the room it needs
    is stated by an arithmetic prediction of the same byline
    (``_opener_code_field_floor``).  Two numbers for one line is exactly the shape
    of the defect this pair exists to catch, and removing the label only moved
    which ink is lowest: with nothing hanging under it the square's own last dark
    row is the credit block's floor, so the finished page is asked the question
    the design now promises -- the symbol's foot plus the credit's own 12pt pad
    stands above the head of the figure the opener carries.

    MEASURED TO THE SYMBOL AND NOT TO THE ELEMENT, which is why the plan's codes
    are passed in: the quiet zone lives inside the box, so the element's foot is
    four light modules below the ink and a guard reading it would demand a
    clearance the field does not reserve and refuse a correct build.  The module
    is not recoverable from a laid-out box, so it comes from the ``SourceCode``
    the layout was built from -- which makes the pair a cross-check too, since a
    square on the page that the plan does not name is not measurable here and is
    the surplus the decode gate refuses.

    Measured on the laid-out boxes on the page they share -- an opener figure is
    on its article's first page with the header that reserves room for it, and a
    square that has landed on some other page is not a clearance question but a
    placement failure the decode gate will report.  The figure's head is its
    flow head, which is the field's foot; the artwork's own ink starts lower
    still, so the refusal fires before anything is painted over.
    """
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
    """Refuse a page whose author note has run down into the standfirst's gap.

    The figureless opener's field is stated by ``_opener_prose_field`` from an
    arithmetic prediction of the credit block's lowest ink, and the note is the
    one piece of that block whose depth is *predicted type* rather than module
    arithmetic: its line count comes from ``_wrap`` over the Medium face's
    advances, which is not an upper bound on what Pango sets (the same one-way
    honesty ``_validate_fitted_display`` exists for, argued at
    ``_advance_widths``).  So the finished page is asked: every laid-out author
    note inside an opener header must end at least the credit's own
    ``_OPENER_CREDIT_LINE_POINTS`` above the field's foot -- the room the
    reader itself kept under a credit before anything else.  An opener figure
    hides the note entirely and a section sets none, so the guard reaches
    exactly the openers whose field the note can threaten, and a failure is an
    editorial problem -- a biography that out-rags its own credit block -- put
    back where it can be fixed.
    """
    failures: list[str] = []
    for page_number, page in enumerate(document.pages, start=1):
        for piece, header, _title in _opener_title_boxes(page._page_box):
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
    """Each opener's laid-out source code and opener figure, named by article.

    Yielded as ``(article_id, "code" | "figure", box)`` from one walk rather
    than two, because the guard above compares them and a second traversal for
    the second box could pick it up from another page.  Neither is walked into:
    an absolutely positioned box reaches the tree wrapped in a placeholder whose
    type name is neither ``BlockBox`` nor anything else worth testing for.
    """
    element = getattr(box, "element", None)
    attributes = getattr(element, "attrib", {}) if element is not None else {}
    if getattr(box, "element_tag", None) == "article" and attributes.get("data-article-id"):
        article_id = str(attributes["data-article-id"])
    if element is not None and article_id is not None:
        if (
            getattr(box, "element_tag", None) == "img"
            and "source-code" in _element_classes(element)
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
