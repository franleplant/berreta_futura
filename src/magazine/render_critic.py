from __future__ import annotations

import json
import hashlib
import math
import re
import shutil
import types
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageOps
from pypdf import PdfReader

from .booklet import (
    A4_LANDSCAPE_POINTS,
    cover_wrap_plan,
    imposed_reader_page_plan,
    section_reader_pages,
)
from .concurrency import ordered_map, worker_count
from .errors import DependencyError


RASTER_DPI = 144
CONTACT_COLUMNS = 4
CONTACT_ROWS = 4
THUMBNAIL_WIDTH = 260
LABEL_HEIGHT = 24
WHITE_THRESHOLD = 245


SPARSE_INK_RATIO = 0.004
GEOMETRY_TOLERANCE = 0.75


PAPER_WHITE = 255


VOID_DOWNSAMPLE = 8


VOID_MIN_HEIGHT_POINTS = 96.0
VOID_MIN_WIDTH_FRACTION = 0.9


VOID_REPORT_LIMIT = 3


VOID_TRAILING_TOLERANCE_POINTS = 16.0


TAIL_GAP_MIN_LIVE_FRACTION = 0.35


TAIL_BAND_HEIGHT_TOLERANCE_POINTS = 12.0
TAIL_BAND_ADJACENCY_TOLERANCE_POINTS = 8.0
TAIL_BAND_SYMMETRY_TOLERANCE_POINTS = 32.0


STUB_BODY_LINE_MINIMUM = 5


DEFAULT_EDITORIAL_PAGE_CAP = 2


CROP_DPI = 300


OPENER_OFFSET_POINTS = 4.1
OPENER_FRAME_RGB = (23, 25, 28)
OPENER_OFFSET_RGB = (240, 87, 56)
OPENER_OFFSET_TOLERANCE_PIXELS = 2.0
OPENER_FRAME_MIN_RUN_FRACTION = 0.65
OPENER_CROP_FIDELITY_MAX_RGB_MAE = 8.0
OPENER_CROP_FRAME_MAX_EDGE_DELTA_INCHES = 0.01


CROP_MARGIN_POINTS = 24.0


CROP_CAPTION_ALLOWANCE_POINTS = 48.0


STUB_CROP_HEIGHT_POINTS = 220.0


TAIL_FALLBACK_CROP_HEIGHT_POINTS = 300.0

_STANDALONE_PUNCTUATION = re.compile(r"^[,.;:!?\u2026]+$")
_COVER_PLACEHOLDER = re.compile(r"(?:\.\.\.|\b(?:TODO|TBD)\b|\[insert\b)", re.IGNORECASE)


class _PageTexts:
    def __init__(self, document: PdfReader) -> None:
        self._document = document
        self._raw: dict[int, str] = {}
        self._normalized: dict[int, str] = {}

    @property
    def page_count(self) -> int:
        return len(self._document.pages)

    def raw(self, page_number: int) -> str:

        if page_number not in self._raw:
            self._raw[page_number] = self._document.pages[page_number - 1].extract_text() or ""
        return self._raw[page_number]

    def normalized(self, page_number: int) -> str:

        if page_number not in self._normalized:
            self._normalized[page_number] = " ".join(self.raw(page_number).split())
        return self._normalized[page_number]


def _page_texts(document: PdfReader | _PageTexts) -> _PageTexts:

    return document if isinstance(document, _PageTexts) else _PageTexts(document)


def _issue_recorder(issues: list[dict[str, Any]]):
    def issue(code: str, severity: str, message: str, *, page: int | None = None) -> None:
        row: dict[str, Any] = {"code": code, "severity": severity, "message": message}
        if page is not None:
            row["page"] = page
        issues.append(row)

    return issue


def _imposition_checks(issue, r):
    reader_texts, booklet_texts, interior_booklet_texts, cover_booklet_texts = r.texts
    reader, booklet, interior_booklet, cover_booklet = r.pdfs
    rendered_pages, rendered_booklet, rendered_cover_booklet = r.rendered
    page_count = r.page_count
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
    cover_plan = cover_wrap_plan(page_count) if page_count >= 4 else ()
    cover_spread_checks = _booklet_spread_checks(reader_texts, cover_booklet_texts, cover_plan)
    if len(cover_booklet.pages) != len(cover_plan):
        issue(
            "cover-booklet-side-count",
            "error",
            f"Cover booklet has {len(cover_booklet.pages)} sides; "
            f"{len(cover_plan)} are expected for the single-sided wrap.",
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
            "The cover booklet must impose the back cover beside the front cover "
            "on its single outside side.",
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

    return types.SimpleNamespace(
        spread_checks=spread_checks,
        interior_pages=interior_pages,
        interior_plan=interior_plan,
        interior_spread_checks=interior_spread_checks,
        cover_pages=cover_pages,
        cover_plan=cover_plan,
        cover_spread_checks=cover_spread_checks,
    )


def _opener_offset_checks(issue, illustrated_articles, toc, rendered_pages):
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

    return opener_offset_checks


def _printed_tail_bands(manifest_layout, article_last_pages):
    printed_tail_bands: dict[int, float] = {}
    for entry in manifest_layout.get("tail_arts") or ():
        if not isinstance(entry, dict) or not entry.get("printed"):
            continue
        height = entry.get("height_points")
        band_page = article_last_pages.get(str(entry.get("article")))
        if isinstance(height, (int, float)) and band_page is not None:
            printed_tail_bands[band_page] = float(height)
    return printed_tail_bands


def _page_row_issues(
    issue, page_rows, inside_cover_pages, last_page_numbers, live_area_points, article_last_pages
):
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

        for void in row["voids"]:
            if void["trailing"] and page in last_page_numbers:
                if (
                    live_area_points is not None
                    and row["tail_band"] is None
                    and void["height_points"]
                    >= TAIL_GAP_MIN_LIVE_FRACTION * (live_area_points[3] - live_area_points[1])
                ):
                    live_height = live_area_points[3] - live_area_points[1]
                    slug = next(
                        (name for name, last in article_last_pages.items() if last == page),
                        "unknown article",
                    )
                    issue(
                        "article-tail-gap",
                        "review",
                        f"'{slug}' ends leaving a {void['height_points']:.0f} pt "
                        f"trailing blank ({void['height_points'] / live_height:.0%} "
                        "of the live area) with no tail art printed; consider "
                        "approving tail art for this article.",
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
                continue
            band = row["tail_band"]
            if band is not None and _abuts_tail_band(void, band):
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

    return flag_crops


def _stub_and_tail_issues(issue, article_last_pages, page_rows, manifest_layout, flag_crops):
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


def _opener_crop_fidelity_checks(issue, crop_rows, rendered_pages, destination):
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
                continue
        fidelity = {
            "page": page,
            "path": crop["path"],
            **_inspect_opener_crop_fidelity(destination / crop["path"], rendered_pages[page - 1]),
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

    return opener_crop_fidelity


def _booklet_side_issues(
    issue, spread_checks, booklet_rows, cover_spread_checks, cover_booklet_rows, inside_cover_pages
):
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

    return cover_booklet_inside_sides


def _contents_issues(
    issue,
    reader_texts,
    toc,
    page_count,
    article_pages,
    editorial_pages,
    manifest_layout,
    actual_contents_pages,
    maximum_contents_pages,
):
    cover_text = reader_texts.raw(1) if reader_texts.page_count else ""
    if _COVER_PLACEHOLDER.search(str(cover_text)):
        issue(
            "cover-placeholder-copy",
            "error",
            "Cover typography contains placeholder or ellipsis copy.",
            page=1,
        )

    if not 1 <= actual_contents_pages <= maximum_contents_pages:
        issue(
            "contents-pagination",
            "error",
            f"Contents uses {actual_contents_pages} pages; between 1 and "
            f"{maximum_contents_pages} are expected for {len(toc)} entries.",
        )
    if any(page < 4 or page > page_count for page in toc.values()):
        issue(
            "contents-folio-range", "error", "A contents folio points outside the body page range."
        )
    page_caps = manifest_layout.get("article_page_caps") or {}
    if any(count > int(page_caps.get(slug, 7)) for slug, count in article_pages.items()):
        issue("article-page-cap", "error", "A source article exceeds its reader page cap.")
    editorial_page_cap = _declared_editorial_cap(manifest_layout)
    if editorial_pages is not None and editorial_pages > editorial_page_cap:
        issue(
            "editorial-page-cap",
            "error",
            f"The opening editorial occupies {editorial_pages} reader pages; "
            f"this edition allows {editorial_page_cap}.",
        )

    return editorial_page_cap


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
    reader = PdfReader(str(reader_pdf))
    booklet = PdfReader(str(booklet_pdf))
    interior_booklet = PdfReader(str(interior_booklet_pdf))
    cover_booklet = PdfReader(str(cover_booklet_pdf))

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
    rendered_cover_booklet = _render_pages(cover_booklet_pdf, review_dir / "cover-booklet-sides")

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
    issue = _issue_recorder(issues)
    imposition = _imposition_checks(
        issue,
        types.SimpleNamespace(
            texts=(reader_texts, booklet_texts, interior_booklet_texts, cover_booklet_texts),
            pdfs=(reader, booklet, interior_booklet, cover_booklet),
            rendered=(rendered_pages, rendered_booklet, rendered_cover_booklet),
            page_count=page_count,
        ),
    )
    spread_checks = imposition.spread_checks
    interior_pages, interior_plan = imposition.interior_pages, imposition.interior_plan
    interior_spread_checks = imposition.interior_spread_checks
    cover_pages, cover_plan = imposition.cover_pages, imposition.cover_plan
    cover_spread_checks = imposition.cover_spread_checks
    opener_offset_checks = _opener_offset_checks(issue, illustrated_articles, toc, rendered_pages)

    inside_cover_pages = {2, page_count - 1}

    maximum_contents_pages = max(1, math.ceil(len(toc) / 8))
    first_body_page = min(toc.values(), default=3 + maximum_contents_pages)
    actual_contents_pages = first_body_page - 3

    contents_pages = set(range(3, 3 + max(actual_contents_pages, 0)))
    body_pages = {
        page
        for page in range(3, page_count - 1)
        if page not in inside_cover_pages and page not in contents_pages
    }

    article_last_pages = {
        slug: toc[slug] + int(count) - 1
        for slug, count in article_pages.items()
        if slug in toc and int(count) > 0
    }
    last_page_numbers = set(article_last_pages.values())
    printed_tail_bands = _printed_tail_bands(manifest_layout, article_last_pages)
    live_area_points = _annotate_void_geometry(
        rendered_pages, page_rows, body_pages, printed_tail_bands
    )
    flag_crops = _page_row_issues(
        issue,
        page_rows,
        inside_cover_pages,
        last_page_numbers,
        live_area_points,
        article_last_pages,
    )
    _stub_and_tail_issues(issue, article_last_pages, page_rows, manifest_layout, flag_crops)
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
    opener_crop_fidelity = _opener_crop_fidelity_checks(
        issue, crop_rows, rendered_pages, destination
    )
    cover_booklet_inside_sides = _booklet_side_issues(
        issue,
        spread_checks,
        booklet_rows,
        cover_spread_checks,
        cover_booklet_rows,
        inside_cover_pages,
    )
    editorial_page_cap = _contents_issues(
        issue,
        reader_texts,
        toc,
        page_count,
        article_pages,
        editorial_pages,
        manifest_layout,
        actual_contents_pages,
        maximum_contents_pages,
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
            "maximum_contents_pages": maximum_contents_pages,
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
            "sheets": len(cover_booklet.pages),
            "expected_sheet_sides": len(cover_plan),
            "all_sides_a4_landscape": _all_a4_landscape(cover_booklet),
            "binding": "saddle_stitch_wrap",
            "duplex_flip": "none (single-sided)",
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
            "reader_pages": [path.relative_to(destination).as_posix() for path in rendered_pages],
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
            booklet_texts.normalized(side_index) if side_index <= booklet_texts.page_count else ""
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

    executable = shutil.which("pdftoppm")
    if not executable:
        raise DependencyError("Render criticism requires Poppler's pdftoppm executable.")
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / "page"

    def rasterize(window: tuple[int, int] | None) -> None:
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
            detail = completed.stderr.strip() or completed.stdout.strip() or "unknown Poppler error"
            raise DependencyError(f"Could not rasterize reader PDF for criticism: {detail}")

    try:
        page_count = len(PdfReader(str(reader_pdf)).pages)
    except Exception:
        page_count = 0
    shard_count = worker_count(page_count // 2)
    if shard_count < 2:
        rasterize(None)
    else:
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

        presence_mask = gray.point(lambda value: 255 if value < PAPER_WHITE else 0)
        presence_pixels = presence_mask.histogram()[255]
        presence_bbox = presence_mask.getbbox()
        pure_white = gray.getextrema() == (255, 255)
        width, height = gray.size

    text = texts.raw(page_number) if texts is not None else (pdf_page.extract_text() or "")
    punctuation = [
        line.strip()
        for line in text.splitlines()
        if _STANDALONE_PUNCTUATION.fullmatch(line.strip())
    ]

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

    pixels = image.load()
    minimum_run = int(image.width * OPENER_FRAME_MIN_RUN_FRACTION)
    frame_runs: list[tuple[int, int, int]] = []
    for y in range(image.height // 2):
        start: int | None = None
        for x in range(image.width + 1):
            is_frame = x < image.width and all(
                abs(channel - target) <= color_tolerance
                for channel, target in zip(pixels[x, y], OPENER_FRAME_RGB, strict=True)
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
    border_rows = [(start, end, y) for start, end, y in frame_runs if end - start >= longest - 2]
    return (
        min(start for start, _end, _y in border_rows),
        min(y for _start, _end, y in border_rows),
        max(end for _start, end, _y in border_rows),
        max(y for _start, _end, y in border_rows) + 1,
    )


def _inspect_opener_crop_fidelity(crop_path: Path, reader_page_path: Path) -> dict[str, Any]:

    with Image.open(reader_page_path) as opened:
        reference = opened.convert("RGB")
    with Image.open(crop_path) as opened:
        normalized = opened.convert("RGB").resize(reference.size, Image.Resampling.LANCZOS)

    histogram = ImageChops.difference(normalized, reference).histogram()
    channel_values = reference.width * reference.height * 3
    rgb_mae = sum((index % 256) * count for index, count in enumerate(histogram))
    rgb_mae /= channel_values

    crop_frame = _opener_frame_bbox(normalized, color_tolerance=24)
    reference_frame = _opener_frame_bbox(reference, color_tolerance=24)
    frame_delta: float | None
    frames_match = crop_frame is not None and reference_frame is not None
    if frames_match:
        frame_delta = (
            max(
                abs(crop_edge - reference_edge)
                for crop_edge, reference_edge in zip(crop_frame, reference_frame, strict=True)
            )
            / RASTER_DPI
        )
    elif crop_frame is None and reference_frame is None:
        frame_delta = None
        frames_match = True
    else:
        frame_delta = None

    passed = (
        rgb_mae <= OPENER_CROP_FIDELITY_MAX_RGB_MAE
        and frames_match
        and (frame_delta is None or frame_delta <= OPENER_CROP_FRAME_MAX_EDGE_DELTA_INCHES)
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
        "frame_edge_delta_inches": (None if frame_delta is None else round(frame_delta, 4)),
        "maximum_frame_edge_delta_inches": OPENER_CROP_FRAME_MAX_EDGE_DELTA_INCHES,
        "normalized_pixels": [reference.width, reference.height],
        "message": f"RGB MAE {rgb_mae:.2f}/255; {frame_text}.",
    }


def _inspect_opener_offset(path: Path) -> dict[str, Any]:

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
    border_rows = [(start, end, y) for start, end, y in frame_runs if end - start >= longest - 2]
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
    passed = all(abs(value - expected) <= OPENER_OFFSET_TOLERANCE_PIXELS for value in values)
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


def _figure_crop_regions(manifest_layout, page_count: int, page_size):
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
        yield (
            page,
            str(entry.get("id") or entry.get("figure_id") or ""),
            (
                x - CROP_MARGIN_POINTS,
                top - CROP_MARGIN_POINTS,
                x + box_width + CROP_MARGIN_POINTS,
                top + box_height + CROP_MARGIN_POINTS + CROP_CAPTION_ALLOWANCE_POINTS,
            ),
        )


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
        specs.append(clamped(page, "opener", opening, (0.0, 0.0, width, height)))
    for page, subject, region in _figure_crop_regions(manifest_layout, page_count, page_size):
        specs.append(clamped(page, "figure", subject, region))
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
        pages = sorted({int(spec["page"]) for spec in specs})
        rasters = ordered_map(rasterize, pages, workers=worker_count(len(pages)))
        rendered = dict(zip(pages, rasters, strict=True))

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
        raise DependencyError(f"Could not rasterize reader page {page_number} for crops: {detail}")
    return matches[0]
