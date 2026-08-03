from __future__ import annotations

import json
import hashlib
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageOps
from pypdf import PdfReader

from .booklet import A4_LANDSCAPE_POINTS, imposed_reader_page_plan, section_reader_pages
from .concurrency import ordered_map, worker_count
from .errors import DependencyError


RASTER_DPI = 144
CONTACT_COLUMNS = 4
CONTACT_ROWS = 4
THUMBNAIL_WIDTH = 260
LABEL_HEIGHT = 24
WHITE_THRESHOLD = 245
# SPARSE_INK_RATIO has never fired on a real page: the emptiest page edition
# 003 printed (two closing lines above a tail ornament) still inks 0.028 of
# its raster, seven times this bar.  The constant and the ``sparse`` field it
# feeds stay for schema stability, but the working whitespace judgment now
# lives in the void geometry below, which asks *where* the paper shows
# through rather than merely how much of it does.
SPARSE_INK_RATIO = 0.004
GEOMETRY_TOLERANCE = 0.75
# ``ink_ratio`` judges legibility, so WHITE_THRESHOLD deliberately ignores
# near-white ink; the price is that pale ornament work -- the tail-art bands
# render around grey 254 -- contributes zero ink and is invisible to it.
# ``presence_ratio`` therefore counts every pixel that is anything but
# untouched paper: pdftoppm renders unprinted stock as exactly 255, so
# "below 255" is precisely "the press touched it", with no tolerance band to
# tune and no change to what ``ink_ratio`` means downstream.
PAPER_WHITE = 255
# The void critic hunts unmotivated whitespace: full-measure white blocks a
# reader falls into mid-page.  It searches the presence mask, so a pale
# ornament terminates a void exactly the way dark type does, and it runs on
# a raster downsampled by 8 (one cell is 4 pt at 144 dpi) because a
# maximal-rectangle sweep at full resolution would buy sub-point precision
# that no threshold here can use.  8 is also safely inside the rounding
# margin that keeps a reduced cell at zero only when *every* source pixel
# was empty: one presence pixel in an 8x8 cell averages to 255/64 =~ 4.
VOID_DOWNSAMPLE = 8
# Calibrated on edition 003, both languages, and re-measured after the
# opener byline fix and the centered tail bands landed.  The stranded dead
# bands the first calibration named (148 pt and 224 pt between an END mark
# and a foot-anchored ornament) no longer exist -- the ornament now centers
# in its room, and its margins are excused by the tail-band check below --
# so what remains guilty is the closing plate's dead skirt (108 pt) and a
# body column running dry above an opener's fold (96 pt, the bar exactly).
# The largest *honest* whitespace on an ordinary page stops at 84 pt at
# full measure (a mid-article trailing shortfall), or 100 pt at 61 % of it
# (an opener's ragged byline column).  96 pt and 90 % still separate the
# two populations, though the height bar now touches the shortest guilty
# reading rather than sitting midway -- worth re-measuring if a future
# edition flags nothing.
VOID_MIN_HEIGHT_POINTS = 96.0
VOID_MIN_WIDTH_FRACTION = 0.9
# One excused giant used to be able to hide a second, reportable void: the
# sweep recorded only the largest rectangle per page, so on an article's
# final page the excused trailing void shadowed the (say) 106.5 pt void
# above the tail band.  A short ranked list -- each found rectangle masked
# and the sweep re-run -- keeps every void that clears the bars above on the
# record, so the excuses below can be argued per void rather than per page.
# Three is one more than any edition-003 page has ever needed.
VOID_REPORT_LIMIT = 3
# A void whose bottom edge reaches the bottom of the live area -- nothing
# beneath it but the folio line -- is the natural shortfall of an article's
# final page, so article last pages are excused from trailing voids (a
# too-empty final page is the stub check's business, below).  16 pt of
# slack is enough to read "only the folio below" as "nothing below" at any
# plausible folio size, while every mid-page void observed clears it by
# hundreds of points.
VOID_TRAILING_TOLERANCE_POINTS = 16.0
# A printed tail ornament stands centered in whatever room the article's end
# mark left it: by design, half the surplus above and half below (ornaments
# cap at 214 pt, so edition 003's rooms leave 60-100 pt of margin a side).
# Those margins are full-measure voids to the sweep -- 106.5 pt and
# 128.5 pt above the edition's two capped bands -- but they are the design's
# own centering, not dead paper, so a void that abuts the printed band is
# excused *when the band's margins agree with each other*.  Locating the
# band needs no new contract: the manifest's ``layout.tail_arts`` says what
# height printed on which article, and the presence rows show a run of that
# height.  The three tolerances, in order: the 4 pt void grid plus the
# anti-aliased edge measure a 214.0 pt ledger band as 214.5 pt of presence,
# so 12 pt matches a run to its ledger height with room to spare while no
# text block on either language's tail pages comes within it; adjacency is
# two grid cells, since a maximal void ends exactly where the band's
# presence starts; and the symmetry bar covers the structural skew between
# the two margins -- the foot side carries the 24 pt foot inset plus about
# 20.5 pt of frame relief against the head side's 31 pt end-mark clearance,
# about 13.5 pt of designed asymmetry -- so 32 pt accepts every centered
# band observed (skews of 13-14 pt) while an ornament left stranded at its
# foot, the old renderer's defect with all surplus above, misses by ~90 pt.
# An article that ends absurdly high above its ornament is still caught:
# that page carries almost no running text, which is the stub check's call.
TAIL_BAND_HEIGHT_TOLERANCE_POINTS = 12.0
TAIL_BAND_ADJACENCY_TOLERANCE_POINTS = 8.0
TAIL_BAND_SYMMETRY_TOLERANCE_POINTS = 32.0
# An article whose last page carries fewer than five lines of running text
# ends on a stub -- edition 003 strands two lines of signatories above a
# tail ornament -- while the leanest healthy closer observed still lands
# seven.  A running-text line is one containing any lowercase letter:
# folios, running heads and END marks are set in caps and digits in both
# publication languages, so they never inflate the count.
STUB_BODY_LINE_MINIMUM = 5
# The editorial cap when the packaged manifest is unreachable: the
# publication ceiling, which edition 001's two-page editorial legitimately
# used.  When ``layout.maximum_editorial_pages`` is readable from the
# build's own edition-manifest.json -- written beside the PDFs before this
# critic runs -- the edition's tighter declaration replaces it, so the
# critic is never looser than the contract the edition set for itself.
DEFAULT_EDITORIAL_PAGE_CAP = 2
# The zoom crops are the evidence the contact sheets cannot carry: a 260 px
# thumbnail shows composition, not type, and the independent reviewer was
# being asked to judge letterforms from it.  Each opener block, each placed
# figure, each printed tail band and each flagged region is therefore also
# cut from a 300 ppi raster of just its own page -- print resolution, so
# what the crop shows is what the press will set.  The regions come from
# facts the critic already holds (contents folios, the manifest's figure
# boxes and tail ledger, the void geometry), never from new measurement.
CROP_DPI = 300
# The illustrated opener's orange rectangle is not a border. It is a 4.1pt
# copy of the black frame translated right and down. At the critic's 144 DPI
# this is 8.2 pixels. A flush padding/background treatment has the same outer
# bounds, so resemblance is not enough: the orange must begin after both the
# top-right and bottom-left corners.
OPENER_OFFSET_POINTS = 4.1
OPENER_FRAME_RGB = (23, 25, 28)
OPENER_OFFSET_RGB = (240, 87, 56)
OPENER_OFFSET_TOLERANCE_PIXELS = 2.0
OPENER_FRAME_MIN_RUN_FRACTION = 0.65
OPENER_CROP_FIDELITY_MAX_RGB_MAE = 8.0
OPENER_CROP_FRAME_MAX_EDGE_DELTA_INCHES = 0.01
# Breathing room around a cropped subject, so a void crop shows the type
# that bounds it and a band crop shows the paper around the ornament.
CROP_MARGIN_POINTS = 24.0
# A figure's caption and credit sit under its box and are part of judging
# the placement, so figure crops extend this much further below the box.
CROP_CAPTION_ALLOWANCE_POINTS = 48.0
# An article opener is a full-page composition: illustration, display title,
# byline, QR, rule, and intro all participate in the visual decision. Its
# evidence crop therefore takes the complete media box, not only the old
# title-and-byline head.
# A stub page's evidence is its head: running head, the remnant lines and
# the END mark all land inside 220 pt on any page stubby enough to flag
# (fewer than five lines of running text below a ~65 pt head area).
STUB_CROP_HEIGHT_POINTS = 220.0
# When the manifest says a band printed but no presence run matches its
# height, the crop still ships -- the mismatch is exactly what a reviewer
# should see -- covering the bottom of the page where the band belongs.
TAIL_FALLBACK_CROP_HEIGHT_POINTS = 300.0

_STANDALONE_PUNCTUATION = re.compile(r"^[,.;:!?\u2026]+$")
_COVER_PLACEHOLDER = re.compile(r"(?:\.\.\.|\b(?:TODO|TBD)\b|\[insert\b)", re.IGNORECASE)


class _PageTexts:
    """One document's extracted page text, asked of ``pypdf`` at most once.

    ``extract_text`` is the most expensive thing this critic asks of pypdf:
    measured warm and single-threaded on edition 003, 8.5 ms a page on the
    English reader and 8.6 ms on the Spanish, rising to 17.2 ms a page on the
    imposed interior, the dearest of the four documents. Warm and
    single-threaded is the honest way to read those figures, because the build
    extracts alongside the rasterizer threads. A build used to pay that cost
    three times over for the same reader page: once for the page's own row in
    ``_inspect_page``, once in the ``_booklet_spread_checks`` pass that imposes
    the all-in-one booklet, and once in whichever of the interior and cover-wrap
    passes covers it. Those two never both cover it -- ``section_reader_pages``
    partitions the reader, the cover wrap taking pages 1, 2, ``n - 1`` and
    ``n`` and the interior 3 through ``n - 2`` -- so only page 1 was read a
    fourth time, and its fourth reader is the cover-placeholder check rather
    than a third imposition. The saving therefore lives *between* those passes,
    which is why the store is built once per document in ``inspect_render`` and
    handed down rather than created inside the function that does the comparing:
    a store owned by ``_booklet_spread_checks`` could only ever dedupe the two
    halves of one side, and the pass after it would re-extract what the passes
    before it had already read.

    At that price the sharing is worth on the order of one and a half to two
    seconds of a thirty-seven-second build, so it is the small one of the three
    changes and the rasterizer fan-outs are where the wall clock actually went.
    It still earns its place -- one extraction per page instead of three, 165
    calls down to 72 on a 36-page fixture, at no cost to anything -- but it is
    not what made the build fast.

    Pages are extracted on first ask, never up front. A document whose checks
    short-circuit -- a plan shorter than the booklet it is checked against, a
    section that selects four of thirty-six pages -- must go on paying nothing
    for the pages nobody looked at, and eager extraction would only move that
    cost rather than remove it, making the smallest editions slower.

    Both shapes the checks want come off the one extraction: the raw text whose
    lines ``_inspect_page`` counts, and the whitespace-collapsed text that
    imposition order is compared on. Page numbers are 1-indexed, as they are in
    every report row and every check in this module, so no call site translates.
    """

    def __init__(self, document: PdfReader) -> None:
        self._document = document
        self._raw: dict[int, str] = {}
        self._normalized: dict[int, str] = {}

    @property
    def page_count(self) -> int:
        return len(self._document.pages)

    def raw(self, page_number: int) -> str:
        """The page's text as ``extract_text`` gives it, or ``""`` where it gives nothing."""

        if page_number not in self._raw:
            self._raw[page_number] = self._document.pages[page_number - 1].extract_text() or ""
        return self._raw[page_number]

    def normalized(self, page_number: int) -> str:
        """The same text with every run of whitespace collapsed to a single space."""

        if page_number not in self._normalized:
            self._normalized[page_number] = " ".join(self.raw(page_number).split())
        return self._normalized[page_number]


def _page_texts(document: PdfReader | _PageTexts) -> _PageTexts:
    """A document's text store, wrapping a bare ``PdfReader`` when that is what arrived.

    ``inspect_render`` passes stores it built itself, so its three imposition
    passes share one extraction per reader page; ``tools/compare_pipelines.py``
    still hands ``_booklet_spread_checks`` plain readers, and a caller checking
    one document once has nothing to share with anybody anyway.
    """

    return document if isinstance(document, _PageTexts) else _PageTexts(document)


def inspect_render(
    reader_pdf: Path,
    booklet_pdf: Path,
    destination: Path,
    *,
    interior_booklet_pdf: Path,
    cover_booklet_pdf: Path,
    language: str,
    toc: dict[str, int],
    article_pages: dict[str, int],
    editorial_pages: int | None,
    edition_id: str,
    recorded_review: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[Path]]:
    """Rasterize and audit a reader PDF, returning a stable review bundle.

    Structural defects are machine blockers. Whitespace judgments -- sparse
    pages, unmotivated voids, articles ending on stubs, dropped tail arts --
    remain review prompts because covers, section openers, and signature
    plates may be sparse by design, and only a human can say whether a given
    stretch of paper is doing design work.

    Three imposed documents are gated. The all-in-one booklet keeps its full
    treatment: every side rasterized, plus exact left/right text pairing against
    the declared plan. The split cover wrap is rasterized too -- it is one sheet,
    two sides, so the blank inside-cover contract is checked on real pixels for
    the price of two rasters. The interior is checked structurally only (side
    count, A4 landscape geometry, exact left/right text pairing) and is
    deliberately *not* rasterized: it would add roughly one raster per interior
    sheet per language on top of the ~20 this function already renders, and it
    would buy nothing new. Every interior reader page is already rasterized and
    judged for blankness and sparseness in the reader pass, and the imposition is
    the same ``pypdf`` merge the main booklet uses over the same pages, with
    order proven by text pairing rather than by looking at it.
    """

    reader = PdfReader(str(reader_pdf))
    booklet = PdfReader(str(booklet_pdf))
    interior_booklet = PdfReader(str(interior_booklet_pdf))
    cover_booklet = PdfReader(str(cover_booklet_pdf))
    # One text store per document, built here and handed to every check that
    # needs a page's words: the three imposition passes below all read the same
    # reader pages, so sharing one store across them is what keeps each page's
    # extraction to one.  See ``_PageTexts`` for why this cannot live inside
    # ``_booklet_spread_checks`` and why nothing is extracted until it is asked for.
    reader_texts = _PageTexts(reader)
    booklet_texts = _PageTexts(booklet)
    interior_booklet_texts = _PageTexts(interior_booklet)
    cover_booklet_texts = _PageTexts(cover_booklet)
    page_count = len(reader.pages)
    review_dir = destination / "render-review"
    if review_dir.exists():
        shutil.rmtree(review_dir)
    review_dir.mkdir(parents=True, exist_ok=True)

    rendered_pages = _render_pages(reader_pdf, review_dir / "reader-pages")
    rendered_booklet = _render_pages(booklet_pdf, review_dir / "booklet-sides")
    rendered_cover_booklet = _render_pages(
        cover_booklet_pdf, review_dir / "cover-booklet-sides"
    )
    # The build's own manifest sits beside the PDFs before this critic runs
    # (package_release writes it first, precisely so an interrupted build
    # cannot pair fresh PDFs with a stale manifest), so declared layout
    # contracts -- the edition's own editorial cap, the tail-art ledger --
    # are read from it rather than re-hardcoded here more loosely.
    manifest_layout = _manifest_layout(destination)
    illustrated_articles = _manifest_opener_article_ids(destination)
    page_rows = [
        _inspect_page(page_path, reader.pages[index], index + 1, texts=reader_texts)
        for index, page_path in enumerate(rendered_pages)
        if index < page_count
    ]
    booklet_rows = [
        _inspect_page(page_path, booklet.pages[index], index + 1, texts=booklet_texts)
        for index, page_path in enumerate(rendered_booklet)
        if index < len(booklet.pages)
    ]
    cover_booklet_rows = [
        _inspect_page(page_path, cover_booklet.pages[index], index + 1, texts=cover_booklet_texts)
        for index, page_path in enumerate(rendered_cover_booklet)
        if index < len(cover_booklet.pages)
    ]
    reader_contact_sheets = _write_contact_sheets(
        rendered_pages, review_dir, prefix="reader-contact-sheet"
    )
    booklet_contact_sheets = _write_contact_sheets(
        rendered_booklet, review_dir, prefix="booklet-contact-sheet"
    )
    review_artifacts = (
        rendered_pages
        + rendered_booklet
        + rendered_cover_booklet
        + reader_contact_sheets
        + booklet_contact_sheets
    )

    issues: list[dict[str, Any]] = []

    def issue(code: str, severity: str, message: str, *, page: int | None = None) -> None:
        row: dict[str, Any] = {"code": code, "severity": severity, "message": message}
        if page is not None:
            row["page"] = page
        issues.append(row)

    if len(rendered_pages) != page_count:
        issue(
            "raster-page-count",
            "error",
            f"Rasterizer produced {len(rendered_pages)} pages for a {page_count}-page PDF.",
        )
    if len(rendered_booklet) != len(booklet.pages):
        issue(
            "booklet-raster-page-count",
            "error",
            f"Rasterizer produced {len(rendered_booklet)} sides for a {len(booklet.pages)}-side booklet.",
        )
    expected_spreads = imposed_reader_page_plan(section_reader_pages(page_count, "all"))
    spread_checks = _booklet_spread_checks(reader_texts, booklet_texts, expected_spreads)
    if not all(row["text_order_matches"] for row in spread_checks):
        issue(
            "booklet-page-order",
            "error",
            "One or more booklet sides do not contain the expected left/right reader page pair.",
        )
    interior_pages = section_reader_pages(page_count, "interior") if page_count >= 4 else ()
    interior_plan = imposed_reader_page_plan(interior_pages)
    interior_spread_checks = _booklet_spread_checks(
        reader_texts, interior_booklet_texts, interior_plan
    )
    if len(interior_booklet.pages) != len(interior_plan):
        issue(
            "interior-booklet-side-count",
            "error",
            f"Interior booklet has {len(interior_booklet.pages)} sides; "
            f"{len(interior_plan)} are expected for reader pages 3-{page_count - 2}.",
        )
    if not _all_a4_landscape(interior_booklet):
        issue(
            "interior-booklet-geometry",
            "error",
            "Every interior booklet side must be landscape A4.",
        )
    if not all(row["text_order_matches"] for row in interior_spread_checks):
        issue(
            "interior-booklet-page-order",
            "error",
            "One or more interior booklet sides do not contain the expected left/right reader page pair.",
        )
    cover_pages = section_reader_pages(page_count, "cover") if page_count >= 4 else ()
    cover_plan = imposed_reader_page_plan(cover_pages)
    cover_spread_checks = _booklet_spread_checks(reader_texts, cover_booklet_texts, cover_plan)
    if len(cover_booklet.pages) != len(cover_plan):
        issue(
            "cover-booklet-side-count",
            "error",
            f"Cover booklet has {len(cover_booklet.pages)} sides; "
            f"{len(cover_plan)} are expected for a single wrap sheet.",
        )
    if not _all_a4_landscape(cover_booklet):
        issue(
            "cover-booklet-geometry",
            "error",
            "Every cover booklet side must be landscape A4.",
        )
    if not all(row["text_order_matches"] for row in cover_spread_checks):
        issue(
            "cover-booklet-page-order",
            "error",
            "The cover booklet must impose the back cover beside the front cover, "
            "then the two inside covers.",
        )
    if len(rendered_cover_booklet) != len(cover_booklet.pages):
        issue(
            "cover-booklet-raster-side-count",
            "error",
            f"Rasterizer produced {len(rendered_cover_booklet)} sides for a "
            f"{len(cover_booklet.pages)}-side cover booklet.",
        )
    if page_count % 4:
        issue(
            "signature-page-count",
            "error",
            f"Reader page count {page_count} is not a multiple of four.",
        )

    opener_offset_checks: list[dict[str, Any]] = []
    for article_id in illustrated_articles:
        page = toc.get(article_id)
        if page is None or not 1 <= page <= len(rendered_pages):
            offset_check = {
                "article": article_id,
                "page": page,
                "pass": False,
                "message": (
                    "The packaged opener declaration has no valid article start "
                    "page in the contents map."
                ),
            }
            opener_offset_checks.append(offset_check)
            issue(
                "article-opener-offset-shadow",
                "error",
                f"Article '{article_id}' declares opener art but has no valid reader "
                "page on which to verify its offset.",
                page=page,
            )
            continue
        offset_check = {
            "article": article_id,
            "page": page,
            **_inspect_opener_offset(rendered_pages[page - 1]),
        }
        opener_offset_checks.append(offset_check)
        if not offset_check["pass"]:
            issue(
                "article-opener-offset-shadow",
                "error",
                f"Article '{article_id}' does not have a true {OPENER_OFFSET_POINTS:g}pt "
                "down-right orange illustration offset. "
                f"{offset_check['message']}",
                page=page,
            )

    # Both directions of blankness are checked, at different strictness: an
    # inside cover must be *completely* blank (pure-white raster, no text), so
    # near-white ink fails it; an unintended blank body page is one with no
    # ink a reader could see, so near-white ink fails that too.
    inside_cover_pages = {2, page_count - 1}
    expected_contents_pages = max(1, math.ceil(len(toc) / 8))
    first_body_page = min(toc.values(), default=3 + expected_contents_pages)
    actual_contents_pages = first_body_page - 3
    # The pages whose whitespace is anyone's business: covers and inside
    # covers are sparse or blank by contract, and the contents page carries
    # however few entries the edition has, so only the run of body pages
    # between contents and the inside back cover is judged for voids.
    contents_pages = set(range(3, 3 + max(actual_contents_pages, 0)))
    body_pages = {
        page
        for page in range(3, page_count - 1)
        if page not in inside_cover_pages and page not in contents_pages
    }
    # Where each article sets its final line, from the same declared facts the
    # page-cap checks already trust: its contents folio plus its page count.
    article_last_pages = {
        slug: toc[slug] + int(count) - 1
        for slug, count in article_pages.items()
        if slug in toc and int(count) > 0
    }
    last_page_numbers = set(article_last_pages.values())
    # Which pages should show a printed tail ornament, and at what height:
    # the ledger names the article, the contents arithmetic above names its
    # last page.  The void annotation uses this to find each band's presence
    # run, so the review loop can tell its centered margins from dead paper.
    printed_tail_bands: dict[int, float] = {}
    for entry in manifest_layout.get("tail_arts") or ():
        if not isinstance(entry, dict) or not entry.get("printed"):
            continue
        height = entry.get("height_points")
        band_page = article_last_pages.get(str(entry.get("article")))
        if isinstance(height, (int, float)) and band_page is not None:
            printed_tail_bands[band_page] = float(height)
    live_area_points = _annotate_void_geometry(
        rendered_pages, page_rows, body_pages, printed_tail_bands
    )
    # Regions the reviewer will want enlarged, gathered as their review items
    # are raised so each crop shows exactly what its item is about.
    flag_crops: list[dict[str, Any]] = []
    for row in page_rows:
        page = int(row["page"])
        if page in inside_cover_pages:
            if not row["blank"]:
                issue(
                    "inside-cover-reader-not-blank",
                    "error",
                    "Inside front and inside back covers must be completely blank "
                    "(a pure-white raster with no extractable text).",
                    page=page,
                )
        elif row["ink_free"]:
            issue("blank-page", "error", "Rendered page is completely blank.", page=page)
        elif row["sparse"]:
            issue(
                "sparse-page",
                "review",
                f"Ink coverage is only {row['ink_ratio']:.4f}; confirm that the whitespace is intentional.",
                page=page,
            )
            flag_crops.append({"page": page, "kind": "sparse", "span": None})
        if row["standalone_punctuation_lines"]:
            issue(
                "orphan-punctuation",
                "error",
                "A line contains only punctuation, which usually indicates a broken display title.",
                page=page,
            )
        # Every reportable void answers for itself: the excuses that used to
        # be applied to the page's single largest rectangle are argued per
        # void, so an excused giant can no longer shadow a smaller void that
        # deserves the reviewer's eye.
        for void in row["voids"]:
            if void["trailing"] and page in last_page_numbers:
                # A trailing void on an article's final page is the article
                # simply ending; anywhere else -- mid-article, or under a
                # closing plate that should fill its page -- it is dead paper.
                continue
            band = row["tail_band"]
            if band is not None and band["centered"] and _abuts_tail_band(void, band):
                # The void is a centered tail ornament's own margin -- the
                # calibration at TAIL_BAND_SYMMETRY_TOLERANCE_POINTS argues
                # why agreement between the two margins is the design's
                # signature and disagreement is a stranded band.
                continue
            issue(
                "whitespace-void",
                "review",
                f"A {void['width_points']:.0f}x{void['height_points']:.0f} pt white void "
                f"starts {void['y_points']:.0f} pt down the live area; confirm the "
                "whitespace is doing design work.",
                page=page,
            )
            flag_crops.append(
                {
                    "page": page,
                    "kind": "void",
                    "span": (
                        void["y_points"] - CROP_MARGIN_POINTS,
                        void["y_points"] + void["height_points"] + CROP_MARGIN_POINTS,
                    ),
                }
            )

    # A machine can hear an article end on a stub even though it cannot judge
    # the prose: the last declared page carrying almost no running text means
    # the break upstream left a remnant, and a human should re-cut it.
    for slug in sorted(article_last_pages):
        last_page = article_last_pages[slug]
        if not 1 <= last_page <= len(page_rows):
            continue
        line_count = int(page_rows[last_page - 1]["body_text_lines"])
        if line_count < STUB_BODY_LINE_MINIMUM:
            issue(
                "article-stub-last-page",
                "review",
                f"The final page of '{slug}' carries only {line_count} line(s) of running "
                "text; consider re-cutting the break so the article does not end on a stub.",
                page=last_page,
            )
            flag_crops.append(
                {"page": last_page, "kind": "stub", "span": (0.0, STUB_CROP_HEIGHT_POINTS)}
            )

    # Tail-art reconciliation, a forward contract: when the manifest starts
    # declaring ``layout.tail_arts``, every ornament an article declared but
    # the typesetter dropped becomes a review prompt.  Builds that predate
    # the key simply have nothing to reconcile.
    for entry in manifest_layout.get("tail_arts") or ():
        if not isinstance(entry, dict):
            continue
        if entry.get("declared") and not entry.get("printed"):
            article = entry.get("article") or "unknown article"
            reason = entry.get("drop_reason") or "no drop reason recorded"
            issue(
                "tail-art-dropped",
                "review",
                f"Tail art declared for '{article}' was not printed ({reason}); "
                "confirm the drop is intentional.",
            )

    crop_specs = _review_crop_plan(
        reader,
        toc=toc,
        manifest_layout=manifest_layout,
        printed_tail_bands=printed_tail_bands,
        page_rows=page_rows,
        flag_crops=flag_crops,
        page_count=page_count,
    )
    crop_paths, crop_rows = _write_review_crops(
        reader_pdf, review_dir / "crops", destination, crop_specs
    )
    review_artifacts = review_artifacts + crop_paths
    opener_crop_fidelity: list[dict[str, Any]] = []
    for crop in crop_rows:
        if crop["kind"] != "opener":
            continue
        page = int(crop["page"])
        if not 1 <= page <= len(rendered_pages):
            continue
        with Image.open(rendered_pages[page - 1]) as reference:
            expected_width = round(float(crop["region_points"][2]) * RASTER_DPI / 72)
            expected_height = round(float(crop["region_points"][3]) * RASTER_DPI / 72)
            if (
                abs(reference.width - expected_width) > 1
                or abs(reference.height - expected_height) > 1
            ):
                # Synthetic critic tests may substitute reduced rasters. Real
                # package rasters are always emitted at RASTER_DPI.
                continue
        fidelity = {
            "page": page,
            "path": crop["path"],
            **_inspect_opener_crop_fidelity(
                destination / crop["path"], rendered_pages[page - 1]
            ),
        }
        opener_crop_fidelity.append(fidelity)
        if not fidelity["pass"]:
            issue(
                "article-opener-crop-fidelity",
                "error",
                f"Full-page opener crop for reader page {page} does not match "
                f"the final-PDF page raster. {fidelity['message']}",
                page=page,
            )

    inside_cover_sides = {
        int(row["side"])
        for row in spread_checks
        if {row["left_reader_page"], row["right_reader_page"]} == inside_cover_pages
    }
    for row in booklet_rows:
        side = int(row["page"])
        if side in inside_cover_sides:
            if not row["blank"]:
                issue(
                    "inside-cover-booklet-not-blank",
                    "error",
                    "The imposed side containing both inside covers must be completely blank "
                    "(a pure-white raster with no extractable text).",
                    page=side,
                )
        elif row["ink_free"]:
            issue(
                "blank-booklet-side",
                "error",
                "Rendered home-booklet side is completely blank.",
                page=side,
            )

    cover_booklet_inside_sides = {
        int(row["side"])
        for row in cover_spread_checks
        if {row["left_reader_page"], row["right_reader_page"]} == inside_cover_pages
    }
    for row in cover_booklet_rows:
        side = int(row["page"])
        if side in cover_booklet_inside_sides:
            if not row["blank"]:
                issue(
                    "cover-booklet-inside-not-blank",
                    "error",
                    "The cover booklet's inside side must be completely blank "
                    "(a pure-white raster with no extractable text).",
                    page=side,
                )
        elif row["ink_free"]:
            issue(
                "blank-cover-booklet-side",
                "error",
                "The cover booklet's outer side carries no ink; it must print the back "
                "cover beside the front cover.",
                page=side,
            )

    # The cover's own row already read page 1, so this comes out of the store.
    cover_text = reader_texts.raw(1) if reader_texts.page_count else ""
    if _COVER_PLACEHOLDER.search(str(cover_text)):
        issue(
            "cover-placeholder-copy",
            "error",
            "Cover typography contains placeholder or ellipsis copy.",
            page=1,
        )

    if actual_contents_pages != expected_contents_pages:
        issue(
            "contents-pagination",
            "error",
            f"Contents uses {actual_contents_pages} pages; {expected_contents_pages} are expected for {len(toc)} entries.",
        )
    if any(page < 4 or page > page_count for page in toc.values()):
        issue("contents-folio-range", "error", "A contents folio points outside the body page range.")
    if any(count > 7 for count in article_pages.values()):
        issue("article-page-cap", "error", "A source article exceeds the seven-page reader cap.")
    editorial_page_cap = _declared_editorial_cap(manifest_layout)
    if editorial_pages is not None and editorial_pages > editorial_page_cap:
        issue(
            "editorial-page-cap",
            "error",
            f"The opening editorial occupies {editorial_pages} reader pages; "
            f"this edition allows {editorial_page_cap}.",
        )

    errors = [row for row in issues if row["severity"] == "error"]
    review_items = [row for row in issues if row["severity"] == "review"]
    report: dict[str, Any] = {
        "schema_version": 1,
        "result": "fail" if errors else "pass",
        "language": language,
        "reader": str(reader_pdf.name),
        "page_count": page_count,
        "raster_dpi": RASTER_DPI,
        "checks": {
            "raster_page_count_matches": len(rendered_pages) == page_count,
            "page_count_multiple_of_four": page_count % 4 == 0,
            "contents_pages": actual_contents_pages,
            "expected_contents_pages": expected_contents_pages,
            "inside_cover_pages": sorted(inside_cover_pages),
            "article_page_cap": 7,
            "editorial_page_cap": editorial_page_cap,
            "live_area_points": live_area_points,
            "void_min_height_points": VOID_MIN_HEIGHT_POINTS,
            "void_min_width_fraction": VOID_MIN_WIDTH_FRACTION,
            "void_report_limit": VOID_REPORT_LIMIT,
            "tail_band_symmetry_tolerance_points": TAIL_BAND_SYMMETRY_TOLERANCE_POINTS,
            "stub_body_line_minimum": STUB_BODY_LINE_MINIMUM,
            "article_opener_offsets": opener_offset_checks,
            "article_opener_offset_count_matches": (
                len(opener_offset_checks) == len(illustrated_articles)
            ),
            "article_opener_crop_fidelity": opener_crop_fidelity,
        },
        "issues": issues,
        "summary": {
            "errors": len(errors),
            "review_items": len(review_items),
        },
        "pages": page_rows,
        "home_booklet": {
            "path": booklet_pdf.relative_to(destination).as_posix(),
            "sheet_sides": len(booklet.pages),
            "raster_page_count_matches": len(rendered_booklet) == len(booklet.pages),
            "binding": "saddle_stitch",
            "duplex_flip": "short_edge",
            "orientation": "upright",
            "spreads": spread_checks,
            "pages": booklet_rows,
        },
        "home_booklet_interior": {
            "path": interior_booklet_pdf.relative_to(destination).as_posix(),
            "reader_pages": list(interior_pages),
            "sheet_sides": len(interior_booklet.pages),
            "sheets": len(interior_booklet.pages) // 2,
            "expected_sheet_sides": len(interior_plan),
            "all_sides_a4_landscape": _all_a4_landscape(interior_booklet),
            "binding": "saddle_stitch",
            "duplex_flip": "short_edge",
            "rasterized": False,
            "rasterization_rationale": (
                "Interior sides re-impose reader pages that the reader pass already "
                "rasterizes and judges; imposition order is proven by exact left/right "
                "text pairing, so per-side rasters would only add build time."
            ),
            "spreads": interior_spread_checks,
        },
        "home_booklet_cover": {
            "path": cover_booklet_pdf.relative_to(destination).as_posix(),
            "reader_pages": list(cover_pages),
            "sheet_sides": len(cover_booklet.pages),
            "sheets": len(cover_booklet.pages) // 2,
            "expected_sheet_sides": len(cover_plan),
            "all_sides_a4_landscape": _all_a4_landscape(cover_booklet),
            "binding": "saddle_stitch_wrap",
            "duplex_flip": "short_edge",
            "rasterized": True,
            "raster_page_count_matches": len(rendered_cover_booklet) == len(cover_booklet.pages),
            "inside_cover_sides": sorted(cover_booklet_inside_sides),
            "spreads": cover_spread_checks,
            "pages": cover_booklet_rows,
        },
        "visual_review": {
            **_visual_review_status(
                recorded_review,
                edition_id=edition_id,
                language=language,
                reader_pdf=reader_pdf,
                booklet_pdf=booklet_pdf,
            ),
            "reader_contact_sheets": [
                path.relative_to(destination).as_posix() for path in reader_contact_sheets
            ],
            "booklet_contact_sheets": [
                path.relative_to(destination).as_posix() for path in booklet_contact_sheets
            ],
            "reader_pages": [
                path.relative_to(destination).as_posix() for path in rendered_pages
            ],
            "booklet_sides": [
                path.relative_to(destination).as_posix() for path in rendered_booklet
            ],
            "cover_booklet_sides": [
                path.relative_to(destination).as_posix() for path in rendered_cover_booklet
            ],
            "crops": crop_rows,
            "instructions": (
                "Inspect every page on the contact sheets, then reopen every crop from its exact file "
                "path at original resolution. Do not approve from a resized preview. Automated checks "
                "do not judge typographic rhythm, visual hierarchy, or aesthetic quality. For an "
                "illustrated opener, verify the orange rectangle begins down and right: white remains "
                "outside the black frame at the top-right before the shadow begins and at the "
                "bottom-left before it begins. The crops/ set enlarges every opener block, placed "
                "figure, printed tail band, and flagged region at 300 ppi so type quality and locked "
                "geometry are judged from source pixels rather than thumbnails."
            ),
        },
    }
    return report, review_artifacts


def _visual_review_status(
    review: dict[str, Any] | None,
    *,
    edition_id: str,
    language: str,
    reader_pdf: Path,
    booklet_pdf: Path,
) -> dict[str, Any]:
    """Describe review freshness without reading or writing review authority.

    The retained renderer receives no workflow review record.  This local
    projection is retained only so its critic report tells the TypeScript
    visual-review offer which exact bytes require inspection.
    """

    def digest(path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    status: dict[str, Any] = {
        "status": "required_before_release",
        "reviewer": None,
        "reviewed_at": None,
        "result": None,
        "findings": [],
        "reader_sha256": digest(reader_pdf),
        "booklet_sha256": digest(booklet_pdf),
    }
    if review is None:
        return status
    row = review.get("languages", {}).get(language)
    status.update(
        {
            "reviewer": review.get("reviewer"),
            "reviewed_at": review.get("reviewed_at"),
            "result": review.get("result"),
            "findings": list(review.get("findings", [])),
        }
    )
    if review.get("edition_id") != edition_id or not isinstance(row, dict):
        status["status"] = "stale"
    elif (
        row.get("reader_sha256") != status["reader_sha256"]
        or row.get("booklet_sha256") != status["booklet_sha256"]
    ):
        status["status"] = "stale"
    elif review.get("result") == "approved":
        status["status"] = "approved"
    else:
        status["status"] = "changes_required"
    return status


def _all_a4_landscape(document: PdfReader) -> bool:
    return bool(document.pages) and all(
        abs(float(page.mediabox.width) - A4_LANDSCAPE_POINTS[0]) <= GEOMETRY_TOLERANCE
        and abs(float(page.mediabox.height) - A4_LANDSCAPE_POINTS[1]) <= GEOMETRY_TOLERANCE
        for page in document.pages
    )


def _booklet_spread_checks(
    reader: PdfReader | _PageTexts,
    booklet: PdfReader | _PageTexts,
    spreads: tuple[tuple[int | None, int | None], ...],
) -> list[dict[str, Any]]:
    """Confirm each imposed side carries exactly its planned reader page pair.

    ``spreads`` is a plan in *reader* page numbers, so the same check serves the
    all-in-one booklet, the interior, and the cover wrap: whichever pages a
    section selects, its side ``n`` must extract the left page's text followed by
    the right page's. ``None`` is a padded blank half-side.

    Either document may arrive as a ``PdfReader`` or as the ``_PageTexts`` store
    ``inspect_render`` shares between its three passes over one reader; a bare
    reader is wrapped in a store of its own, which costs nothing and reads the
    same, but only the shared one spares the second and third pass the
    extraction the first already paid for.
    """

    reader_texts = _page_texts(reader)
    booklet_texts = _page_texts(booklet)
    reader_pages = reader_texts.page_count
    rows: list[dict[str, Any]] = []
    for side_index, (left, right) in enumerate(spreads, 1):
        expected = " ".join(
            text
            for page_number in (left, right)
            if page_number is not None and page_number <= reader_pages
            for text in [reader_texts.normalized(page_number)]
            if text
        )
        actual = (
            booklet_texts.normalized(side_index)
            if side_index <= booklet_texts.page_count
            else ""
        )
        rows.append(
            {
                "side": side_index,
                "sheet": (side_index + 1) // 2,
                "face": "outside" if side_index % 2 else "inside",
                "left_reader_page": left if left is not None and left <= reader_pages else None,
                "right_reader_page": (
                    right if right is not None and right <= reader_pages else None
                ),
                "text_order_matches": actual == expected,
            }
        )
    return rows


def _render_pages(reader_pdf: Path, output_dir: Path) -> list[Path]:
    """Rasterize every page of a PDF to ``page-001.png``, in document order.

    ``pdftoppm`` is single-threaded and this is the most expensive thing the
    build does, so the document is cut into contiguous page ranges rendered at
    once.  Sharding cannot move a pixel or a name, but that rests on two
    Poppler behaviours which nothing in this repository pins and which Poppler
    does not document as guarantees; both were verified empirically against the
    installed Poppler (25.08.0), and an upgrade is worth re-checking on both
    counts.  First, a page's rendered bytes do not depend on whether it was
    asked for alone or as part of the whole document.  Second, Poppler pads
    each file name to the width of the *document's* page count rather than the
    requested range's, so a 36-page document names its fifth page
    ``page-05.png`` under ``-f 5 -l 5`` exactly as it does under a single-shot
    run.  A future Poppler that padded to the requested range's width instead
    would break this silently rather than loudly: that same page would arrive
    as ``page-5.png`` from a one-page shard and as ``page-05.png`` from a wider
    one, and the normalization below would sort a set of names that no longer
    reflects the document and renumber the pages into the wrong order.

    Given those two, the normalization is looking at the same directory of
    files either way, and it -- not any shard -- is what decides the returned
    names and their order.  Sorting by page number only after every shard has
    finished is what keeps that order owing nothing to which shard finished
    first.
    """

    executable = shutil.which("pdftoppm")
    if not executable:
        raise DependencyError("Render criticism requires Poppler's pdftoppm executable.")
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / "page"

    def rasterize(window: tuple[int, int] | None) -> None:
        """Render one inclusive page range, or the whole document for ``None``."""
        selection = [] if window is None else ["-f", str(window[0]), "-l", str(window[1])]
        completed = subprocess.run(
            [
                executable,
                "-png",
                "-r",
                str(RASTER_DPI),
                *selection,
                str(reader_pdf),
                str(prefix),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode:
            detail = (
                completed.stderr.strip() or completed.stdout.strip() or "unknown Poppler error"
            )
            raise DependencyError(f"Could not rasterize reader PDF for criticism: {detail}")

    # Every shard pays its own process startup and document setup -- spawning
    # pdftoppm, reading the xref and the catalog, preparing the output device --
    # before it renders anything, and none of that is shared between shards, so
    # a shard is only worth its process once it has a couple of pages to render;
    # holding each to two keeps the cover wrap's two sides, and any document on
    # a single-core machine, on the unsharded command that has always run here.
    try:
        page_count = len(PdfReader(str(reader_pdf)).pages)
    except Exception:
        # A page count that cannot be read is not an error to raise here, only a
        # split that cannot be planned: sharding is an optimization, so when the
        # plan is unavailable this falls back to the unsharded command that has
        # always run here and lets Poppler judge the file.  A truncated or
        # malformed PDF then fails as it always did, with the ``DependencyError``
        # carrying Poppler's own diagnosis, rather than with whatever pypdf
        # raised on its way to a number this function only wanted in order to
        # divide it.  ``tools/compare_pipelines.py`` is the one caller that
        # reaches this function directly, without ``inspect_render``'s prior
        # ``PdfReader`` construction to fail first, so it is the only path where
        # this fallback is observable at all -- and the error it observes should
        # be this module's own, not a pypdf internal.  Zero plans no shards, so
        # the branch below is the one that runs.
        page_count = 0
    shard_count = worker_count(page_count // 2)
    if shard_count < 2:
        rasterize(None)
    else:
        # Cutting at ``page_count * index // shard_count`` gives contiguous
        # ranges that between them cover every page exactly once and leave none
        # empty, so long as there are no more shards than pages; it is
        # ``worker_count``'s clamp to the work that exists that guarantees that,
        # and without it the arithmetic degenerates into windows that run
        # backwards and windows that repeat a page.
        #
        # The two ways the cuts could be wrong are not equally visible, and only
        # one of them is caught anywhere.  A gap loses pages, which
        # ``inspect_render``'s raster-page-count check does report: a 118-page
        # reader shards into eight windows of fourteen or fifteen pages, and
        # dropping one of them -- ``(30, 44)`` -- left 103 of the 118 rasters,
        # which the check fired on.  An overlap is the more dangerous one exactly
        # because nothing reports it -- every page is still covered, so the count
        # matches and the check stays silent, while two ``pdftoppm`` processes
        # write the same PNG at the same time and leave a torn file that no count
        # can see.  ``cuts[index] + 1``
        # is the whole of what rules the overlap out, by opening each window one
        # page past where the previous one closed.
        cuts = [page_count * index // shard_count for index in range(shard_count + 1)]
        windows = [(cuts[index] + 1, cuts[index + 1]) for index in range(shard_count)]
        ordered_map(rasterize, windows)

    def page_number(path: Path) -> int:
        try:
            return int(path.stem.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            return 0

    ordered = sorted(output_dir.glob("page-*.png"), key=page_number)
    normalized: list[Path] = []
    for index, path in enumerate(ordered, 1):
        target = output_dir / f"page-{index:03d}.png"
        if path != target:
            path.rename(target)
        normalized.append(target)
    return normalized


def _inspect_page(
    path: Path, pdf_page: Any, page_number: int, *, texts: _PageTexts | None = None
) -> dict[str, Any]:
    with Image.open(path) as opened:
        gray = ImageOps.grayscale(opened)
        ink_mask = gray.point(lambda value: 255 if value < WHITE_THRESHOLD else 0)
        histogram = ink_mask.histogram()
        ink_pixels = histogram[255]
        total_pixels = gray.width * gray.height
        bbox = ink_mask.getbbox()
        # Two masks, two questions.  ``ink_ratio`` counts a pixel as ink below
        # WHITE_THRESHOLD (245), so a 246-254 tint or hairline has a ratio of
        # exactly 0.0 -- it asks what a reader can *read*.  ``presence_ratio``
        # counts everything below pure paper white, so the same pale tint is
        # fully visible to it -- it asks what the press *printed*, which is
        # what the void geometry must honour lest a pale ornament read as
        # empty paper.  "Blank" is held to the stricter standard
        # tools/compare_pipelines.py uses: a pure-white raster and zero
        # extracted characters.
        presence_mask = gray.point(lambda value: 255 if value < PAPER_WHITE else 0)
        presence_pixels = presence_mask.histogram()[255]
        presence_bbox = presence_mask.getbbox()
        pure_white = gray.getextrema() == (255, 255)
        width, height = gray.size
    # The words come from the document's shared store when ``inspect_render``
    # supplies one, so this row and the imposition passes do not each pay pypdf
    # for the same page; a caller holding only the page object -- the synthetic
    # pages in the tests, tools/compare_pipelines.py -- extracts it here as this
    # function always did.
    text = texts.raw(page_number) if texts is not None else (pdf_page.extract_text() or "")
    punctuation = [
        line.strip()
        for line in text.splitlines()
        if _STANDALONE_PUNCTUATION.fullmatch(line.strip())
    ]
    # Running text has lowercase letters; folios, running heads and END marks
    # are set in caps and digits, in both publication languages, so counting
    # only lines with any lowercase measures how much *body* a page carries.
    body_text_lines = sum(
        1
        for line in (raw.strip() for raw in text.splitlines())
        if line and any(character.islower() for character in line)
    )
    ratio = ink_pixels / total_pixels if total_pixels else 0.0
    presence_ratio = presence_pixels / total_pixels if total_pixels else 0.0
    return {
        "page": page_number,
        "pixel_dimensions": [width, height],
        "ink_ratio": round(ratio, 6),
        "ink_bbox": list(bbox) if bbox else None,
        "presence_ratio": round(presence_ratio, 6),
        "presence_bbox": list(presence_bbox) if presence_bbox else None,
        "body_text_lines": body_text_lines,
        # Filled in by ``_annotate_void_geometry`` for reader body pages; the
        # keys are present on every row so the schema does not shift per
        # page.  ``largest_void`` is the single largest empty rectangle
        # whether or not it is worth reporting; ``voids`` ranks every
        # rectangle tall and wide enough to matter; ``tail_band`` is the
        # located presence run of a printed tail ornament, where the
        # manifest declares one for this page.
        "largest_void": None,
        "voids": [],
        "tail_band": None,
        "text_characters": len(text.strip()),
        "blank": pure_white and not text.strip(),
        "ink_free": ink_pixels == 0 and not text.strip(),
        "sparse": 0 < ratio < SPARSE_INK_RATIO,
        "standalone_punctuation_lines": punctuation,
    }


def _manifest_layout(destination: Path) -> dict[str, Any]:
    """The ``layout`` block of the package's own edition-manifest.json, or {}.

    ``package_release`` writes the manifest before it calls the critic, so on
    a real build the file is always there; the tolerance is for the critic's
    synthetic-test harnesses and for hand-assembled packages, where a missing
    or malformed manifest must degrade to "nothing declared" rather than
    block the raster checks that need no manifest at all.
    """

    path = destination / "edition-manifest.json"
    if not path.is_file():
        return {}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    layout = manifest.get("layout") if isinstance(manifest, dict) else None
    return layout if isinstance(layout, dict) else {}


def _manifest_opener_article_ids(destination: Path) -> tuple[str, ...]:
    """Article ids whose packaged inputs declare first-class opener art."""

    path = destination / "edition-manifest.json"
    if not path.is_file():
        return ()
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    inputs = manifest.get("inputs") if isinstance(manifest, dict) else None
    articles = inputs.get("articles") if isinstance(inputs, dict) else None
    if not isinstance(articles, list):
        return ()
    return tuple(
        str(row["id"])
        for row in articles
        if isinstance(row, dict)
        and isinstance(row.get("id"), str)
        and isinstance(row.get("opener_art"), dict)
    )


def _opener_frame_bbox(
    image: Image.Image, *, color_tolerance: int = 0
) -> tuple[int, int, int, int] | None:
    """Locate the long near-black illustration frame in a page raster."""

    pixels = image.load()
    minimum_run = int(image.width * OPENER_FRAME_MIN_RUN_FRACTION)
    frame_runs: list[tuple[int, int, int]] = []
    for y in range(image.height // 2):
        start: int | None = None
        for x in range(image.width + 1):
            is_frame = x < image.width and all(
                abs(channel - target) <= color_tolerance
                for channel, target in zip(
                    pixels[x, y], OPENER_FRAME_RGB, strict=True
                )
            )
            if is_frame and start is None:
                start = x
            elif not is_frame and start is not None:
                if x - start >= minimum_run:
                    frame_runs.append((start, x, y))
                start = None
    if not frame_runs:
        return None
    longest = max(end - start for start, end, _y in frame_runs)
    border_rows = [
        (start, end, y)
        for start, end, y in frame_runs
        if end - start >= longest - 2
    ]
    return (
        min(start for start, _end, _y in border_rows),
        min(y for _start, _end, y in border_rows),
        max(end for _start, end, _y in border_rows),
        max(y for _start, _end, y in border_rows) + 1,
    )


def _inspect_opener_crop_fidelity(crop_path: Path, reader_page_path: Path) -> dict[str, Any]:
    """Compare 300 ppi review evidence with its 144 dpi final-PDF raster."""

    with Image.open(reader_page_path) as opened:
        reference = opened.convert("RGB")
    with Image.open(crop_path) as opened:
        normalized = opened.convert("RGB").resize(
            reference.size, Image.Resampling.LANCZOS
        )

    histogram = ImageChops.difference(normalized, reference).histogram()
    channel_values = reference.width * reference.height * 3
    rgb_mae = sum((index % 256) * count for index, count in enumerate(histogram))
    rgb_mae /= channel_values

    # Lanczos normalization softens the long frame rows even when the two
    # rasters describe the same physical page. A 24-channel tolerance keeps
    # those rows detectable without admitting the much lighter artwork.
    crop_frame = _opener_frame_bbox(normalized, color_tolerance=24)
    reference_frame = _opener_frame_bbox(reference, color_tolerance=24)
    frame_delta: float | None
    frames_match = crop_frame is not None and reference_frame is not None
    if frames_match:
        frame_delta = max(
            abs(crop_edge - reference_edge)
            for crop_edge, reference_edge in zip(crop_frame, reference_frame, strict=True)
        ) / RASTER_DPI
    elif crop_frame is None and reference_frame is None:
        frame_delta = None
        frames_match = True
    else:
        frame_delta = None

    passed = (
        rgb_mae <= OPENER_CROP_FIDELITY_MAX_RGB_MAE
        and frames_match
        and (
            frame_delta is None
            or frame_delta <= OPENER_CROP_FRAME_MAX_EDGE_DELTA_INCHES
        )
    )
    frame_text = (
        "no illustration frame detected in either raster"
        if frame_delta is None and frames_match
        else (
            f"frame edge delta {frame_delta:.4f}in"
            if frame_delta is not None
            else "illustration frame detected in only one raster"
        )
    )
    return {
        "pass": passed,
        "rgb_mae": round(rgb_mae, 4),
        "maximum_rgb_mae": OPENER_CROP_FIDELITY_MAX_RGB_MAE,
        "frame_edge_delta_inches": (
            None if frame_delta is None else round(frame_delta, 4)
        ),
        "maximum_frame_edge_delta_inches": OPENER_CROP_FRAME_MAX_EDGE_DELTA_INCHES,
        "normalized_pixels": [reference.width, reference.height],
        "message": f"RGB MAE {rgb_mae:.2f}/255; {frame_text}.",
    }


def _inspect_opener_offset(path: Path) -> dict[str, Any]:
    """Measure the translated orange rectangle from a finished page raster."""

    with Image.open(path) as opened:
        image = opened.convert("RGB")
    pixels = image.load()
    minimum_run = int(image.width * OPENER_FRAME_MIN_RUN_FRACTION)
    frame_runs: list[tuple[int, int, int]] = []
    for y in range(image.height // 2):
        start: int | None = None
        for x in range(image.width + 1):
            is_frame = x < image.width and pixels[x, y] == OPENER_FRAME_RGB
            if is_frame and start is None:
                start = x
            elif not is_frame and start is not None:
                if x - start >= minimum_run:
                    frame_runs.append((start, x, y))
                start = None
    if not frame_runs:
        return {
            "pass": False,
            "message": "The critic could not locate the long near-black illustration frame.",
        }

    longest = max(end - start for start, end, _y in frame_runs)
    border_rows = [
        (start, end, y)
        for start, end, y in frame_runs
        if end - start >= longest - 2
    ]
    frame_left = min(start for start, _end, _y in border_rows)
    frame_right = max(end for _start, end, _y in border_rows)
    frame_top = min(y for _start, _end, y in border_rows)
    frame_bottom = max(y for _start, _end, y in border_rows) + 1
    search = max(4, round(OPENER_OFFSET_POINTS * RASTER_DPI / 72 * 3))

    right_orange = [
        (x, y)
        for y in range(frame_top, min(image.height, frame_bottom + search))
        for x in range(frame_right, min(image.width, frame_right + search))
        if pixels[x, y] == OPENER_OFFSET_RGB
    ]
    bottom_orange = [
        (x, y)
        for y in range(frame_bottom, min(image.height, frame_bottom + search))
        for x in range(frame_left, min(image.width, frame_right + search))
        if pixels[x, y] == OPENER_OFFSET_RGB
    ]
    if not right_orange or not bottom_orange:
        return {
            "pass": False,
            "frame_bbox_pixels": [
                frame_left,
                frame_top,
                frame_right,
                frame_bottom,
            ],
            "message": "The critic could not locate orange beyond both the frame's right and bottom edges.",
        }

    offset_x = min(x for x, _y in bottom_orange) - frame_left
    offset_y = min(y for _x, y in right_orange) - frame_top
    extension_x = max(x for x, _y in right_orange) + 1 - frame_right
    extension_y = max(y for _x, y in bottom_orange) + 1 - frame_bottom
    expected = OPENER_OFFSET_POINTS * RASTER_DPI / 72
    values = (offset_x, offset_y, extension_x, extension_y)
    passed = all(
        abs(value - expected) <= OPENER_OFFSET_TOLERANCE_PIXELS
        for value in values
    )
    return {
        "pass": passed,
        "frame_bbox_pixels": [frame_left, frame_top, frame_right, frame_bottom],
        "offset_pixels": [offset_x, offset_y],
        "extension_pixels": [extension_x, extension_y],
        "expected_offset_pixels": round(expected, 2),
        "tolerance_pixels": OPENER_OFFSET_TOLERANCE_PIXELS,
        "message": (
            f"Measured orange start {offset_x}px right and {offset_y}px down, "
            f"with {extension_x}px right and {extension_y}px bottom extension; "
            f"expected {expected:.1f}px on every edge."
        ),
    }


def _declared_editorial_cap(manifest_layout: dict[str, Any]) -> int:
    """The editorial page cap this edition declared for itself, if readable.

    ``layout.maximum_editorial_pages`` is the value the build resolved through
    ``reader_layout.declared_editorial_page_cap`` -- already clamped to the
    publication ceiling -- but a hand-assembled package could declare any
    number, so the critic re-clamps to the publication default rather than
    letting a manifest loosen the ERROR below it; anything unreadable falls
    back to the publication default rather than failing the build over a
    manifest field the raster checks never needed.
    """

    declared = manifest_layout.get("maximum_editorial_pages")
    if isinstance(declared, int) and not isinstance(declared, bool) and declared >= 1:
        return min(declared, DEFAULT_EDITORIAL_PAGE_CAP)
    return DEFAULT_EDITORIAL_PAGE_CAP


def _annotate_void_geometry(
    rendered_pages: list[Path],
    page_rows: list[dict[str, Any]],
    body_pages: set[int],
    tail_bands: dict[int, float],
) -> list[float] | None:
    """Fill each body page's void geometry rows; return the live area in points.

    The live area is the union of the body pages' presence boxes -- the frame
    the design actually types into, discovered from the pages themselves so a
    margin change never needs a constant retuned here.  Within that frame,
    each body page is downsampled and swept for its all-paper rectangles:
    voids are judged in page geometry (points, and a fraction of the live
    measure) precisely so thresholds read like typography rather than pixel
    counts.  The sweep repeats, masking each rectangle it finds, so one
    excused giant cannot shadow a second reportable void -- ``voids`` is the
    ranked list of every rectangle clearing the size bars, ``largest_void``
    the single largest whether or not it clears them (schema stability).
    ``tail_bands`` maps an article's last page to the ornament height the
    manifest says printed there; the matching presence run is recorded as
    ``tail_band`` so the review loop can tell a centered ornament's margins
    from dead paper.  Pages with no presence at all are skipped; total
    blankness is the blank-page check's verdict, not a void.
    """

    scale = 72.0 / RASTER_DPI
    boxes = [
        row["presence_bbox"]
        for row in page_rows
        if row["page"] in body_pages and row["presence_bbox"]
    ]
    if not boxes:
        return None
    live = (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )
    live_width = live[2] - live[0]
    if live_width < VOID_DOWNSAMPLE or (live[3] - live[1]) < VOID_DOWNSAMPLE:
        return [round(value * scale, 1) for value in live]
    for row in page_rows:
        page = int(row["page"])
        if page not in body_pages or not row["presence_bbox"] or page > len(rendered_pages):
            continue
        with Image.open(rendered_pages[page - 1]) as opened:
            gray = ImageOps.grayscale(opened)
            presence = gray.point(lambda value: 255 if value < PAPER_WHITE else 0)
            cells = presence.crop(live).reduce(VOID_DOWNSAMPLE)
            columns, rows_count = cells.size
            data = cells.tobytes()
        grid = bytearray(data)
        voids: list[dict[str, Any]] = []
        largest: dict[str, Any] | None = None
        for _ in range(VOID_REPORT_LIMIT):
            area, cell_width, cell_height, cell_x, cell_y = _largest_empty_rectangle(
                grid, columns, rows_count
            )
            if not area:
                break
            # ``reduce`` ceils a partial trailing cell into existence, so a
            # void spanning the whole measure can compute a hair over the
            # live width; clamping keeps the fraction an honest "share of
            # the measure".
            width_px = min(cell_width * VOID_DOWNSAMPLE, live_width)
            height_px = cell_height * VOID_DOWNSAMPLE
            x_px = live[0] + cell_x * VOID_DOWNSAMPLE
            y_px = live[1] + cell_y * VOID_DOWNSAMPLE
            trailing_gap = (live[3] - (y_px + height_px)) * scale
            void = {
                "x_points": round(x_px * scale, 1),
                "y_points": round(y_px * scale, 1),
                "width_points": round(width_px * scale, 1),
                "height_points": round(height_px * scale, 1),
                "width_fraction": round(width_px / live_width, 3),
                "trailing": trailing_gap <= VOID_TRAILING_TOLERANCE_POINTS,
            }
            if largest is None:
                largest = void
            if (
                void["height_points"] >= VOID_MIN_HEIGHT_POINTS
                and void["width_fraction"] >= VOID_MIN_WIDTH_FRACTION
            ):
                voids.append(void)
            for masked_row in range(cell_y, cell_y + cell_height):
                offset = masked_row * columns
                for masked_column in range(cell_x, cell_x + cell_width):
                    grid[offset + masked_column] = 255
        row["largest_void"] = largest
        row["voids"] = voids
        declared_height = tail_bands.get(page)
        if declared_height is not None:
            row["tail_band"] = _locate_tail_band(
                data, columns, rows_count, live, scale, declared_height
            )
    return [round(value * scale, 1) for value in live]


def _locate_tail_band(
    data: bytes,
    columns: int,
    rows_count: int,
    live: tuple[int, int, int, int],
    scale: float,
    declared_height: float,
) -> dict[str, Any] | None:
    """The presence run matching a page's declared tail ornament, or nothing.

    The manifest's ledger says an ornament of ``declared_height`` printed on
    this page; on the downsampled presence grid that ornament is a run of
    consecutive occupied cell rows of the same height (the tolerance's own
    comment argues why no text block collides).  The bottommost matching run
    wins -- the ornament stands below the article's last line by
    construction, and the folio's own run is a few points tall and can never
    match a >=96 pt band.  The gaps to the neighbouring runs (or the live
    edges) are the band's actual margins, and ``centered`` is the design's
    signature: the two margins agreeing within the calibrated skew.
    """

    runs: list[tuple[int, int]] = []
    start: int | None = None
    for row_index in range(rows_count):
        offset = row_index * columns
        occupied = any(data[offset : offset + columns])
        if occupied and start is None:
            start = row_index
        elif not occupied and start is not None:
            runs.append((start, row_index))
            start = None
    if start is not None:
        runs.append((start, rows_count))
    cell_points = VOID_DOWNSAMPLE * scale
    match: int | None = None
    for index, (run_start, run_end) in enumerate(runs):
        height = (run_end - run_start) * cell_points
        if abs(height - declared_height) <= TAIL_BAND_HEIGHT_TOLERANCE_POINTS:
            match = index
    if match is None:
        return None
    run_start, run_end = runs[match]
    above_end = runs[match - 1][1] if match else 0
    below_start = runs[match + 1][0] if match + 1 < len(runs) else rows_count
    gap_above = (run_start - above_end) * cell_points
    gap_below = (below_start - run_end) * cell_points
    return {
        "y_points": round((live[1] + run_start * VOID_DOWNSAMPLE) * scale, 1),
        "height_points": round((run_end - run_start) * cell_points, 1),
        "declared_height_points": round(float(declared_height), 4),
        "gap_above_points": round(gap_above, 1),
        "gap_below_points": round(gap_below, 1),
        "centered": abs(gap_above - gap_below) <= TAIL_BAND_SYMMETRY_TOLERANCE_POINTS,
    }


def _abuts_tail_band(void: dict[str, Any], band: dict[str, Any]) -> bool:
    """Whether a void is one of the band's own margins.

    A maximal void ends exactly where presence begins, so a margin void's
    bottom edge sits on the band's top edge (or its top edge on the band's
    bottom); the tolerance is two grid cells of measurement slack, far under
    the height of anything reportable.
    """

    band_top = band["y_points"]
    band_bottom = band["y_points"] + band["height_points"]
    void_bottom = void["y_points"] + void["height_points"]
    return (
        abs(void_bottom - band_top) <= TAIL_BAND_ADJACENCY_TOLERANCE_POINTS
        or abs(void["y_points"] - band_bottom) <= TAIL_BAND_ADJACENCY_TOLERANCE_POINTS
    )


def _largest_empty_rectangle(
    data: bytes | bytearray, columns: int, rows_count: int
) -> tuple[int, int, int, int, int]:
    """Largest all-zero rectangle in a row-major byte grid.

    The classic histogram-of-heights sweep: each row extends a column-height
    histogram of consecutive empty cells, and a monotonic stack finds the
    best rectangle ending on that row, so the whole search is linear in the
    number of cells.  Returns ``(area, width, height, x, y)`` in cells; a
    fully occupied grid returns all zeros.
    """

    heights = [0] * columns
    best = (0, 0, 0, 0, 0)
    for row_index in range(rows_count):
        offset = row_index * columns
        for column in range(columns):
            heights[column] = 0 if data[offset + column] else heights[column] + 1
        stack: list[tuple[int, int]] = []
        for column in range(columns + 1):
            height = heights[column] if column < columns else 0
            start = column
            while stack and stack[-1][1] >= height:
                start, stacked_height = stack.pop()
                area = stacked_height * (column - start)
                if area > best[0]:
                    best = (
                        area,
                        column - start,
                        stacked_height,
                        start,
                        row_index - stacked_height + 1,
                    )
            stack.append((start, height))
    return best


def _write_contact_sheets(
    page_paths: list[Path], destination: Path, *, prefix: str = "contact-sheet"
) -> list[Path]:
    if not page_paths:
        return []
    with Image.open(page_paths[0]) as first:
        ratio = first.height / first.width
    thumb_height = round(THUMBNAIL_WIDTH * ratio)
    cell_width = THUMBNAIL_WIDTH
    cell_height = thumb_height + LABEL_HEIGHT
    per_sheet = CONTACT_COLUMNS * CONTACT_ROWS
    outputs: list[Path] = []
    for sheet_index in range(0, len(page_paths), per_sheet):
        chunk = page_paths[sheet_index : sheet_index + per_sheet]
        sheet = Image.new(
            "RGB",
            (CONTACT_COLUMNS * cell_width, CONTACT_ROWS * cell_height),
            "#e8e7e2",
        )
        draw = ImageDraw.Draw(sheet)
        for offset, page_path in enumerate(chunk):
            column = offset % CONTACT_COLUMNS
            row = offset // CONTACT_COLUMNS
            x = column * cell_width
            y = row * cell_height
            with Image.open(page_path) as opened:
                thumbnail = ImageOps.fit(opened.convert("RGB"), (THUMBNAIL_WIDTH, thumb_height))
                sheet.paste(thumbnail, (x, y))
            page_number = sheet_index + offset + 1
            draw.text((x + 7, y + thumb_height + 5), f"PAGE {page_number:03d}", fill="#272528")
        output = destination / f"{prefix}-{sheet_index // per_sheet + 1:02d}.png"
        sheet.save(output, format="PNG", optimize=True)
        outputs.append(output)
    return outputs


def _review_crop_plan(
    reader: PdfReader,
    *,
    toc: dict[str, int],
    manifest_layout: dict[str, Any],
    printed_tail_bands: dict[int, float],
    page_rows: list[dict[str, Any]],
    flag_crops: list[dict[str, Any]],
    page_count: int,
) -> list[dict[str, Any]]:
    """Every region the 300 ppi crop set must cover, in page points.

    Four families, all derived from facts the critic already holds: each
    contents entry's opener block (folio from ``toc``), each placed figure
    (page and box from the manifest, whose ``box_points`` y runs from the
    page *bottom*, PDF-fashion), each printed tail ornament (the band the
    void annotation located, or the foot of the page when the raster shows
    no band of the declared height -- a discrepancy the reviewer should
    see), and each flagged review item's own region.  Regions are clamped
    to the page here, so the writer only converts and cuts.
    """

    def page_size(page: int) -> tuple[float, float]:
        box = reader.pages[page - 1].mediabox
        return float(box.width), float(box.height)

    def clamped(page: int, kind: str, subject: str | None, region) -> dict[str, Any]:
        width, height = page_size(page)
        x0, y0, x1, y1 = region if region is not None else (0.0, 0.0, width, height)
        return {
            "page": page,
            "kind": kind,
            "subject": subject,
            "region": (
                max(0.0, min(x0, width)),
                max(0.0, min(y0, height)),
                max(0.0, min(x1, width)),
                max(0.0, min(y1, height)),
            ),
        }

    specs: list[dict[str, Any]] = []
    for page in sorted(set(toc.values())):
        if not 1 <= page <= page_count:
            continue
        opening = ", ".join(sorted(slug for slug, folio in toc.items() if folio == page))
        width, height = page_size(page)
        specs.append(
            clamped(page, "opener", opening, (0.0, 0.0, width, height))
        )
    for entry in manifest_layout.get("figures") or ():
        if not isinstance(entry, dict):
            continue
        page = entry.get("page")
        box = entry.get("box_points")
        if not isinstance(page, int) or not 1 <= page <= page_count:
            continue
        if not (isinstance(box, (list, tuple)) and len(box) == 4):
            continue
        x, y, box_width, box_height = (float(value) for value in box)
        _, height = page_size(page)
        top = height - y - box_height
        specs.append(
            clamped(
                page,
                "figure",
                str(entry.get("id") or entry.get("figure_id") or ""),
                (
                    x - CROP_MARGIN_POINTS,
                    top - CROP_MARGIN_POINTS,
                    x + box_width + CROP_MARGIN_POINTS,
                    top + box_height + CROP_MARGIN_POINTS + CROP_CAPTION_ALLOWANCE_POINTS,
                ),
            )
        )
    for page in sorted(printed_tail_bands):
        if not 1 <= page <= min(page_count, len(page_rows)):
            continue
        width, height = page_size(page)
        band = page_rows[page - 1].get("tail_band")
        if band is None:
            region = (0.0, height - TAIL_FALLBACK_CROP_HEIGHT_POINTS, width, height)
        else:
            region = (
                0.0,
                band["y_points"] - CROP_MARGIN_POINTS,
                width,
                band["y_points"] + band["height_points"] + CROP_MARGIN_POINTS,
            )
        specs.append(clamped(page, "tail", None, region))
    for flag in flag_crops:
        page = flag["page"]
        if not 1 <= page <= page_count:
            continue
        width, _ = page_size(page)
        span = flag["span"]
        region = None if span is None else (0.0, span[0], width, span[1])
        specs.append(clamped(page, flag["kind"], None, region))
    return specs


def _write_review_crops(
    reader_pdf: Path, crops_dir: Path, destination: Path, specs: list[dict[str, Any]]
) -> tuple[list[Path], list[dict[str, Any]]]:
    """Cut each planned region from a 300 ppi raster of its own page.

    Only the pages actually being cropped are rasterized at print
    resolution, each exactly once however many crops it feeds, and the full
    -page rasters are scratch -- removed once cut, so the review directory
    carries ~20 focused crops rather than a second full set of pages five
    times the size.  Names say what they show (``crop-p05-opener.png``),
    with a numeric suffix only when one page flags the same kind twice.

    The rasters are taken all at once on threads, because thirty-odd Poppler
    invocations waited on in turn were a fifth of the build a human sits
    through between asking for a review and reading it.
    """

    if not specs:
        return [], []
    crops_dir.mkdir(parents=True, exist_ok=True)
    scratch = crops_dir / "pages-at-300"
    scale = CROP_DPI / 72.0
    outputs: list[Path] = []
    rows: list[dict[str, Any]] = []
    used_names: set[str] = set()

    def rasterize(page: int) -> Path:
        return _render_crop_page(reader_pdf, page, scratch)

    try:
        # Every page a spec names, including one whose box the loop below finds
        # degenerate and skips: that spec costs its page a raster today, before
        # the box is even computed, so keeping it in the set is what makes this
        # rasterize neither more nor fewer pages -- and therefore report neither
        # more nor fewer Poppler failures -- than the serial version did.
        # Sorting is what makes a failure deterministic: ``ordered_map`` raises
        # for the lowest-index item that failed, so lowest index has to mean
        # lowest page number rather than whichever page a thread reached first.
        pages = sorted({int(spec["page"]) for spec in specs})
        rasters = ordered_map(rasterize, pages, workers=worker_count(len(pages)))
        rendered = dict(zip(pages, rasters, strict=True))
        # Walking ``specs`` rather than ``pages`` from here on, because the
        # ``-2`` suffix is assigned in the order the specs arrive; consuming the
        # prepared rasters in page order instead would move suffixes between two
        # crops of one page and rename files a review has already accepted.  The
        # cropping itself stays on this thread: it is a quarter of the cost and
        # pure-Python pixel work, so threads would contend for the interpreter
        # rather than overlap, and the PNGs are written in one fixed order.
        for spec in specs:
            page = int(spec["page"])
            base = f"crop-p{page:02d}-{spec['kind']}"
            name = base
            suffix = 2
            while name in used_names:
                name = f"{base}-{suffix}"
                suffix += 1
            used_names.add(name)
            target = crops_dir / f"{name}.png"
            x0, y0, x1, y1 = spec["region"]
            with Image.open(rendered[page]) as opened:
                box = (
                    max(0, math.floor(x0 * scale)),
                    max(0, math.floor(y0 * scale)),
                    min(opened.width, math.ceil(x1 * scale)),
                    min(opened.height, math.ceil(y1 * scale)),
                )
                if box[2] <= box[0] or box[3] <= box[1]:
                    continue
                opened.crop(box).save(target, format="PNG", optimize=True)
            outputs.append(target)
            rows.append(
                {
                    "path": target.relative_to(destination).as_posix(),
                    "page": page,
                    "kind": spec["kind"],
                    "subject": spec["subject"],
                    "region_points": [round(value, 1) for value in (x0, y0, x1, y1)],
                    "ppi": CROP_DPI,
                }
            )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return outputs, rows


def _render_crop_page(reader_pdf: Path, page_number: int, output_dir: Path) -> Path:
    """One reader page as a 300 ppi raster, for cropping."""

    executable = shutil.which("pdftoppm")
    if not executable:
        raise DependencyError("Render criticism requires Poppler's pdftoppm executable.")
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / f"page-{page_number:03d}"
    completed = subprocess.run(
        [
            executable,
            "-png",
            "-r",
            str(CROP_DPI),
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            str(reader_pdf),
            str(prefix),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    matches = sorted(output_dir.glob(f"page-{page_number:03d}-*.png"))
    if completed.returncode or not matches:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown Poppler error"
        raise DependencyError(
            f"Could not rasterize reader page {page_number} for crops: {detail}"
        )
    return matches[0]
