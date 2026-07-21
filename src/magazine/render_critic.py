from __future__ import annotations

import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageOps
from pypdf import PdfReader

from .booklet import booklet_spreads
from .errors import DependencyError
from .render_review import visual_review_status


RASTER_DPI = 144
CONTACT_COLUMNS = 4
CONTACT_ROWS = 4
THUMBNAIL_WIDTH = 260
LABEL_HEIGHT = 24
WHITE_THRESHOLD = 245
SPARSE_INK_RATIO = 0.004

_STANDALONE_PUNCTUATION = re.compile(r"^[,.;:!?\u2026]+$")
_COVER_PLACEHOLDER = re.compile(r"(?:\.\.\.|\b(?:TODO|TBD)\b|\[insert\b)", re.IGNORECASE)


def inspect_render(
    reader_pdf: Path,
    booklet_pdf: Path,
    destination: Path,
    *,
    language: str,
    toc: dict[str, int],
    article_pages: dict[str, int],
    editorial_pages: int | None,
    edition_id: str,
    recorded_review: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[Path]]:
    """Rasterize and audit a reader PDF, returning a stable review bundle.

    Structural defects are machine blockers. Sparse-page notices remain review
    prompts because covers, section openers, and signature plates may be sparse
    by design.
    """

    reader = PdfReader(str(reader_pdf))
    booklet = PdfReader(str(booklet_pdf))
    page_count = len(reader.pages)
    review_dir = destination / "render-review"
    if review_dir.exists():
        shutil.rmtree(review_dir)
    review_dir.mkdir(parents=True, exist_ok=True)

    rendered_pages = _render_pages(reader_pdf, review_dir / "reader-pages")
    rendered_booklet = _render_pages(booklet_pdf, review_dir / "booklet-sides")
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
    reader_contact_sheets = _write_contact_sheets(
        rendered_pages, review_dir, prefix="reader-contact-sheet"
    )
    booklet_contact_sheets = _write_contact_sheets(
        rendered_booklet, review_dir, prefix="booklet-contact-sheet"
    )
    review_artifacts = (
        rendered_pages + rendered_booklet + reader_contact_sheets + booklet_contact_sheets
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
    expected_spreads = booklet_spreads(page_count)
    spread_checks = _booklet_spread_checks(reader, booklet, expected_spreads)
    if not all(row["text_order_matches"] for row in spread_checks):
        issue(
            "booklet-page-order",
            "error",
            "One or more booklet sides do not contain the expected left/right reader page pair.",
        )
    if page_count % 4:
        issue(
            "signature-page-count",
            "error",
            f"Reader page count {page_count} is not a multiple of four.",
        )

    for row in page_rows:
        page = int(row["page"])
        if row["blank"]:
            issue("blank-page", "error", "Rendered page is completely blank.", page=page)
        elif row["sparse"]:
            issue(
                "sparse-page",
                "review",
                f"Ink coverage is only {row['ink_ratio']:.4f}; confirm that the whitespace is intentional.",
                page=page,
            )

    for row in booklet_rows:
        if row["blank"]:
            issue(
                "blank-booklet-side",
                "error",
                "Rendered home-booklet side is completely blank.",
                page=int(row["page"]),
            )
        if row["standalone_punctuation_lines"]:
            issue(
                "orphan-punctuation",
                "error",
                "A line contains only punctuation, which usually indicates a broken display title.",
                page=page,
            )

    cover_text = reader.pages[0].extract_text() if reader.pages else ""
    if _COVER_PLACEHOLDER.search(str(cover_text)):
        issue(
            "cover-placeholder-copy",
            "error",
            "Cover typography contains placeholder or ellipsis copy.",
            page=1,
        )

    expected_contents_pages = max(1, math.ceil(len(toc) / 8))
    first_body_page = min(toc.values(), default=2 + expected_contents_pages)
    actual_contents_pages = first_body_page - 2
    if actual_contents_pages != expected_contents_pages:
        issue(
            "contents-pagination",
            "error",
            f"Contents uses {actual_contents_pages} pages; {expected_contents_pages} are expected for {len(toc)} entries.",
        )
    if any(page < 3 or page > page_count for page in toc.values()):
        issue("contents-folio-range", "error", "A contents folio points outside the body page range.")
    if any(count > 7 for count in article_pages.values()):
        issue("article-page-cap", "error", "A source article exceeds the seven-page reader cap.")
    if editorial_pages is not None and editorial_pages > 2:
        issue("editorial-page-cap", "error", "The opening editorial exceeds its two-page reader cap.")

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
            "article_page_cap": 7,
            "editorial_page_cap": 2,
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
            "instructions": (
                "Inspect every page on the contact sheets at useful zoom; automated checks do not judge "
                "typographic rhythm, visual hierarchy, or aesthetic quality."
            ),
        },
    }
    return report, review_artifacts


def _booklet_spread_checks(
    reader: PdfReader,
    booklet: PdfReader,
    spreads: tuple[tuple[int, int], ...],
) -> list[dict[str, Any]]:
    def normalized(page: Any) -> str:
        return " ".join((page.extract_text() or "").split())

    rows: list[dict[str, Any]] = []
    for side_index, (left, right) in enumerate(spreads, 1):
        expected = " ".join(
            text
            for page_number in (left, right)
            if page_number <= len(reader.pages)
            for text in [normalized(reader.pages[page_number - 1])]
            if text
        )
        actual = normalized(booklet.pages[side_index - 1]) if side_index <= len(booklet.pages) else ""
        rows.append(
            {
                "side": side_index,
                "sheet": (side_index + 1) // 2,
                "face": "outside" if side_index % 2 else "inside",
                "left_reader_page": left if left <= len(reader.pages) else None,
                "right_reader_page": right if right <= len(reader.pages) else None,
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
        width, height = gray.size
    text = pdf_page.extract_text() or ""
    punctuation = [
        line.strip()
        for line in text.splitlines()
        if _STANDALONE_PUNCTUATION.fullmatch(line.strip())
    ]
    ratio = ink_pixels / total_pixels if total_pixels else 0.0
    return {
        "page": page_number,
        "pixel_dimensions": [width, height],
        "ink_ratio": round(ratio, 6),
        "ink_bbox": list(bbox) if bbox else None,
        "text_characters": len(text.strip()),
        "blank": ink_pixels == 0 and not text.strip(),
        "sparse": 0 < ratio < SPARSE_INK_RATIO,
        "standalone_punctuation_lines": punctuation,
    }


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
