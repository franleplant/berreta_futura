from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageOps
from pypdf import PdfReader

from .booklet import A4_LANDSCAPE_POINTS, imposed_reader_page_plan, section_reader_pages
from .errors import DependencyError
from .render_review import visual_review_status


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
# Breathing room around a cropped subject, so a void crop shows the type
# that bounds it and a band crop shows the paper around the ornament.
CROP_MARGIN_POINTS = 24.0
# A figure's caption and credit sit under its box and are part of judging
# the placement, so figure crops extend this much further below the box.
CROP_CAPTION_ALLOWANCE_POINTS = 48.0
# An opener's running head, display title, byline block and QR all sit in
# the top 320 pt of the page on both languages' openers (the QR block's
# foot lands near 310 pt); the crop takes the full page width because the
# title runs to the outer margin.
OPENER_CROP_HEIGHT_POINTS = 320.0
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
    page_rows = [
        _inspect_page(page_path, reader.pages[index], index + 1)
        for index, page_path in enumerate(rendered_pages)
        if index < page_count
    ]
    booklet_rows = [
        _inspect_page(page_path, booklet.pages[index], index + 1)
        for index, page_path in enumerate(rendered_booklet)
        if index < len(booklet.pages)
    ]
    cover_booklet_rows = [
        _inspect_page(page_path, cover_booklet.pages[index], index + 1)
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
    spread_checks = _booklet_spread_checks(reader, booklet, expected_spreads)
    if not all(row["text_order_matches"] for row in spread_checks):
        issue(
            "booklet-page-order",
            "error",
            "One or more booklet sides do not contain the expected left/right reader page pair.",
        )
    interior_pages = section_reader_pages(page_count, "interior") if page_count >= 4 else ()
    interior_plan = imposed_reader_page_plan(interior_pages)
    interior_spread_checks = _booklet_spread_checks(reader, interior_booklet, interior_plan)
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
    cover_spread_checks = _booklet_spread_checks(reader, cover_booklet, cover_plan)
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

    cover_text = reader.pages[0].extract_text() if reader.pages else ""
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
            **visual_review_status(
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
                "Inspect every page on the contact sheets at useful zoom; automated checks do not judge "
                "typographic rhythm, visual hierarchy, or aesthetic quality. The crops/ set enlarges "
                "every opener block, placed figure, printed tail band, and flagged region at 300 ppi "
                "so type quality is judged at print resolution rather than from thumbnails."
            ),
        },
    }
    return report, review_artifacts


def _all_a4_landscape(document: PdfReader) -> bool:
    return bool(document.pages) and all(
        abs(float(page.mediabox.width) - A4_LANDSCAPE_POINTS[0]) <= GEOMETRY_TOLERANCE
        and abs(float(page.mediabox.height) - A4_LANDSCAPE_POINTS[1]) <= GEOMETRY_TOLERANCE
        for page in document.pages
    )


def _booklet_spread_checks(
    reader: PdfReader,
    booklet: PdfReader,
    spreads: tuple[tuple[int | None, int | None], ...],
) -> list[dict[str, Any]]:
    """Confirm each imposed side carries exactly its planned reader page pair.

    ``spreads`` is a plan in *reader* page numbers, so the same check serves the
    all-in-one booklet, the interior, and the cover wrap: whichever pages a
    section selects, its side ``n`` must extract the left page's text followed by
    the right page's. ``None`` is a padded blank half-side.
    """

    def normalized(page: Any) -> str:
        return " ".join((page.extract_text() or "").split())

    rows: list[dict[str, Any]] = []
    for side_index, (left, right) in enumerate(spreads, 1):
        expected = " ".join(
            text
            for page_number in (left, right)
            if page_number is not None and page_number <= len(reader.pages)
            for text in [normalized(reader.pages[page_number - 1])]
            if text
        )
        actual = normalized(booklet.pages[side_index - 1]) if side_index <= len(booklet.pages) else ""
        rows.append(
            {
                "side": side_index,
                "sheet": (side_index + 1) // 2,
                "face": "outside" if side_index % 2 else "inside",
                "left_reader_page": left if left is not None and left <= len(reader.pages) else None,
                "right_reader_page": (
                    right if right is not None and right <= len(reader.pages) else None
                ),
                "text_order_matches": actual == expected,
            }
        )
    return rows


def _render_pages(reader_pdf: Path, output_dir: Path) -> list[Path]:
    executable = shutil.which("pdftoppm")
    if not executable:
        raise DependencyError("Render criticism requires Poppler's pdftoppm executable.")
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / "page"
    completed = subprocess.run(
        [executable, "-png", "-r", str(RASTER_DPI), str(reader_pdf), str(prefix)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown Poppler error"
        raise DependencyError(f"Could not rasterize reader PDF for criticism: {detail}")

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


def _inspect_page(path: Path, pdf_page: Any, page_number: int) -> dict[str, Any]:
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
    text = pdf_page.extract_text() or ""
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
        width, _ = page_size(page)
        specs.append(
            clamped(page, "opener", opening, (0.0, 0.0, width, OPENER_CROP_HEIGHT_POINTS))
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
    """

    if not specs:
        return [], []
    crops_dir.mkdir(parents=True, exist_ok=True)
    scratch = crops_dir / "pages-at-300"
    scale = CROP_DPI / 72.0
    rendered: dict[int, Path] = {}
    outputs: list[Path] = []
    rows: list[dict[str, Any]] = []
    used_names: set[str] = set()
    try:
        for spec in specs:
            page = int(spec["page"])
            if page not in rendered:
                rendered[page] = _render_crop_page(reader_pdf, page, scratch)
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
