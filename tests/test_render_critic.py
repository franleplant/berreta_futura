import hashlib
import json
import subprocess
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw
from pypdf import PageObject, PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from magazine.booklet import impose_a5_on_a4, imposed_reader_page_plan, section_reader_pages
from magazine.errors import DependencyError
from magazine.render_critic import (
    _COVER_PLACEHOLDER,
    _PageTexts,
    _booklet_spread_checks,
    _inspect_opener_crop_fidelity,
    _inspect_opener_offset,
    _inspect_page,
    _render_crop_page,
    _render_pages,
    _review_crop_plan,
    _write_review_crops,
    inspect_render,
)

A5 = (419.5276, 595.2756)
A4_LANDSCAPE = (841.8898, 595.2756)


def _eight_page_pdf(path: Path) -> None:
    writer = PdfWriter()
    for _ in range(8):
        writer.add_blank_page(width=A5[0], height=A5[1])
    with path.open("wb") as handle:
        writer.write(handle)


def _a4_landscape_pdf(path: Path, sides: int) -> Path:
    writer = PdfWriter()
    for _ in range(sides):
        writer.add_blank_page(width=A4_LANDSCAPE[0], height=A4_LANDSCAPE[1])
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def _split_documents(tmp_path: Path) -> dict[str, Path]:
    """Structurally correct split documents for an eight-page reader."""
    return {
        "interior_booklet_pdf": _a4_landscape_pdf(tmp_path / "interior.pdf", 2),
        "cover_booklet_pdf": _a4_landscape_pdf(tmp_path / "cover.pdf", 2),
    }


def _opener_shadow_raster(path: Path, *, offset: int) -> Path:
    image = Image.new("RGB", (840, 1191), "white")
    draw = ImageDraw.Draw(image)
    left, top, width, height, extension = 70, 60, 696, 406, 8
    draw.rectangle(
        (
            left + offset,
            top + offset,
            left + width + extension - 1,
            top + height + extension - 1,
        ),
        fill=(240, 87, 56),
    )
    draw.rectangle(
        (left, top, left + width - 1, top + height - 1),
        fill="white",
        outline=(23, 25, 28),
        width=5,
    )
    image.save(path)
    return path


def test_opener_offset_critic_distinguishes_translation_from_flush_padding(
    tmp_path: Path,
):
    translated = _inspect_opener_offset(
        _opener_shadow_raster(tmp_path / "translated.png", offset=8)
    )
    flush = _inspect_opener_offset(
        _opener_shadow_raster(tmp_path / "flush.png", offset=0)
    )

    assert translated["pass"] is True
    assert translated["offset_pixels"] == [8, 8]
    assert translated["extension_pixels"] == [8, 8]
    assert flush["pass"] is False
    assert flush["offset_pixels"] == [0, 0]
    assert flush["extension_pixels"] == [8, 8]


def _opener_fidelity_raster(path: Path, size: tuple[int, int]) -> Path:
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    sx, sy = size[0] / 840, size[1] / 1191
    frame = (
        round(70 * sx),
        round(60 * sy),
        round(766 * sx),
        round(466 * sy),
    )
    draw.rectangle(
        (
            frame[0] + round(8 * sx),
            frame[1] + round(8 * sy),
            frame[2] + round(8 * sx),
            frame[3] + round(8 * sy),
        ),
        fill=(240, 87, 56),
    )
    draw.rectangle(
        frame,
        fill=(211, 225, 232),
        outline=(23, 25, 28),
        width=max(1, round(5 * sx)),
    )
    draw.rectangle(
        (round(120 * sx), round(520 * sy), round(650 * sx), round(548 * sy)),
        fill=(49, 93, 140),
    )
    image.save(path)
    return path


def test_full_page_opener_crop_fidelity_normalizes_dpi(tmp_path: Path):
    reference = _opener_fidelity_raster(tmp_path / "page.png", (840, 1191))
    crop = tmp_path / "crop.png"
    with Image.open(reference) as opened:
        opened.resize((1750, 2481), Image.Resampling.LANCZOS).save(crop)

    result = _inspect_opener_crop_fidelity(crop, reference)

    assert result["pass"] is True, result
    assert result["rgb_mae"] <= 8
    assert result["frame_edge_delta_inches"] <= 0.01


def test_full_page_opener_crop_fidelity_rejects_shift_and_scale(tmp_path: Path):
    reference = _opener_fidelity_raster(tmp_path / "page.png", (840, 1191))
    with Image.open(reference) as opened:
        source = opened.convert("RGB").resize((1750, 2481), Image.Resampling.LANCZOS)
    shifted = Image.new("RGB", source.size, "white")
    shifted.paste(source, (12, 12))
    shifted_path = tmp_path / "shifted.png"
    shifted.save(shifted_path)
    scaled_source = source.resize(
        (round(source.width * 0.98), round(source.height * 0.98)),
        Image.Resampling.LANCZOS,
    )
    scaled = Image.new("RGB", source.size, "white")
    scaled.paste(
        scaled_source,
        (
            (source.width - scaled_source.width) // 2,
            (source.height - scaled_source.height) // 2,
        ),
    )
    scaled_path = tmp_path / "scaled.png"
    scaled.save(scaled_path)

    assert _inspect_opener_crop_fidelity(shifted_path, reference)["pass"] is False
    assert _inspect_opener_crop_fidelity(scaled_path, reference)["pass"] is False


def _numbered_reader(path: Path, page_count: int) -> Path:
    """An A5 reader that names each page, leaving both inside covers blank."""
    canvas = Canvas(str(path), pagesize=A5)
    for page in range(1, page_count + 1):
        if page not in {2, page_count - 1}:
            canvas.setFont("Helvetica", 24)
            canvas.drawString(60, 300, f"READERPAGE{page}")
        canvas.showPage()
    canvas.save()
    return path


def _rasters(blank: dict[str, set[int]], tint: dict[str, set[int]] | None = None):
    """Fake ``_render_pages``: one raster per real PDF page, blank where asked."""

    def stub(pdf: Path, output: Path) -> list[Path]:
        output.mkdir(parents=True, exist_ok=True)
        paths = []
        blank_sides = blank.get(output.name, set())
        tinted_sides = (tint or {}).get(output.name, set())
        for page_number in range(1, len(PdfReader(str(pdf)).pages) + 1):
            path = output / f"page-{page_number}.png"
            image = Image.new("RGB", (560, 794), "white")
            if page_number in tinted_sides:
                ImageDraw.Draw(image).rectangle((70, 70, 490, 720), fill=(250, 250, 250))
            elif page_number not in blank_sides:
                ImageDraw.Draw(image).rectangle((70, 70, 490, 720), fill="#36333a")
            image.save(path)
            paths.append(path)
        return paths

    return stub


_CLEAN = {"reader-pages": {2, 7}, "booklet-sides": {2}, "cover-booklet-sides": {2}}


def test_render_critic_emits_contact_sheet_and_passes_structural_checks(tmp_path: Path):
    reader = tmp_path / "reader.pdf"
    _eight_page_pdf(reader)
    booklet = tmp_path / "booklet.pdf"
    _eight_page_pdf(booklet)

    with patch("magazine.render_critic._render_pages", side_effect=_rasters(_CLEAN)):
        report, artifacts = inspect_render(
            reader,
            booklet,
            tmp_path,
            **_split_documents(tmp_path),
            language="en",
            toc={"article": 4},
            article_pages={"article": 1},
            editorial_pages=None,
            edition_id="issue-001",
        )

    assert report["result"] == "pass"
    assert report["checks"]["contents_pages"] == 1
    assert report["visual_review"]["status"] == "required_before_release"
    relative_artifacts = {path.relative_to(tmp_path).as_posix() for path in artifacts}
    assert "render-review/reader-pages/page-1.png" in relative_artifacts
    assert "render-review/booklet-sides/page-1.png" in relative_artifacts
    assert "render-review/cover-booklet-sides/page-1.png" in relative_artifacts
    assert "render-review/reader-contact-sheet-01.png" in relative_artifacts
    assert "render-review/booklet-contact-sheet-01.png" in relative_artifacts
    # The 300 ppi crop set rides along with the contact sheets: the sole
    # contents entry earns an opener crop, and the blank fixture's stub
    # review item earns its evidence crop.
    assert "render-review/crops/crop-p04-opener.png" in relative_artifacts
    assert "render-review/crops/crop-p04-stub.png" in relative_artifacts
    assert len(artifacts) == 22
    assert all(path.is_file() for path in artifacts)
    crops = report["visual_review"]["crops"]
    assert [(row["kind"], row["page"]) for row in crops] == [("opener", 4), ("stub", 4)]
    assert all(row["ppi"] == 300 for row in crops)
    assert crops[0]["path"] == "render-review/crops/crop-p04-opener.png"
    assert crops[0]["region_points"] == [0.0, 0.0, 419.5, 595.3]


def test_declared_opener_without_a_toc_page_is_a_machine_error(tmp_path: Path):
    reader = _numbered_reader(tmp_path / "reader.pdf", 8)
    booklet = _numbered_reader(tmp_path / "booklet.pdf", 8)
    (tmp_path / "edition-manifest.json").write_text(
        json.dumps(
            {
                "inputs": {
                    "articles": [
                        {
                            "id": "missing-opener",
                            "opener_art": {"path": "art/missing.png"},
                        }
                    ]
                },
                "layout": {},
            }
        ),
        encoding="utf-8",
    )

    with patch("magazine.render_critic._render_pages", side_effect=_rasters(_CLEAN)):
        report, _artifacts = inspect_render(
            reader,
            booklet,
            tmp_path,
            **_split_documents(tmp_path),
            language="en",
            toc={"article": 4},
            article_pages={"article": 1},
            editorial_pages=None,
            edition_id="issue-001",
        )

    assert report["result"] == "fail"
    offset_rows = report["checks"]["article_opener_offsets"]
    assert offset_rows == [
        {
            "article": "missing-opener",
            "page": None,
            "pass": False,
            "message": (
                "The packaged opener declaration has no valid article start "
                "page in the contents map."
            ),
        }
    ]
    assert report["checks"]["article_opener_offset_count_matches"] is True
    assert any(
        issue["code"] == "article-opener-offset-shadow"
        and issue["severity"] == "error"
        for issue in report["issues"]
    )


def test_opener_crop_uses_each_page_full_media_box_and_clamps_non_a5_pages(tmp_path: Path):
    reader_path = tmp_path / "mixed-pages.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=A5[0], height=A5[1])
    writer.add_blank_page(width=300.0, height=400.0)
    with reader_path.open("wb") as handle:
        writer.write(handle)

    specs = _review_crop_plan(
        PdfReader(str(reader_path)),
        toc={"a5-opener": 1, "small-opener": 2},
        manifest_layout={},
        printed_tail_bands={},
        page_rows=[],
        flag_crops=[],
        page_count=2,
    )

    assert [spec["region"] for spec in specs] == [
        (0.0, 0.0, A5[0], A5[1]),
        (0.0, 0.0, 300.0, 400.0),
    ]


def test_render_critic_reports_the_split_documents_sheet_counts_and_geometry(tmp_path: Path):
    reader = tmp_path / "reader.pdf"
    _eight_page_pdf(reader)
    booklet = tmp_path / "booklet.pdf"
    _eight_page_pdf(booklet)

    with patch("magazine.render_critic._render_pages", side_effect=_rasters(_CLEAN)):
        report, _ = inspect_render(
            reader,
            booklet,
            tmp_path,
            **_split_documents(tmp_path),
            language="en",
            toc={"article": 4},
            article_pages={"article": 1},
            editorial_pages=None,
            edition_id="issue-001",
        )

    interior = report["home_booklet_interior"]
    cover = report["home_booklet_cover"]
    assert interior["reader_pages"] == [3, 4, 5, 6]
    assert interior["sheet_sides"] == 2
    assert interior["sheets"] == 1
    assert interior["all_sides_a4_landscape"] is True
    assert interior["rasterized"] is False
    assert [(row["left_reader_page"], row["right_reader_page"]) for row in interior["spreads"]] == [
        (6, 3),
        (4, 5),
    ]
    assert cover["reader_pages"] == [1, 2, 7, 8]
    assert cover["sheets"] == 1
    assert cover["all_sides_a4_landscape"] is True
    assert cover["rasterized"] is True
    assert cover["inside_cover_sides"] == [2]
    assert [(row["left_reader_page"], row["right_reader_page"]) for row in cover["spreads"]] == [
        (8, 1),
        (2, 7),
    ]


def test_render_critic_blocks_split_documents_of_the_wrong_length_or_page_size(tmp_path: Path):
    reader = tmp_path / "reader.pdf"
    _eight_page_pdf(reader)
    booklet = tmp_path / "booklet.pdf"
    _eight_page_pdf(booklet)
    interior = _a4_landscape_pdf(tmp_path / "interior.pdf", 4)  # one sheet too many
    cover = tmp_path / "cover.pdf"
    _eight_page_pdf(cover)  # A5 pages, and eight of them

    with patch("magazine.render_critic._render_pages", side_effect=_rasters(_CLEAN)):
        report, _ = inspect_render(
            reader,
            booklet,
            tmp_path,
            interior_booklet_pdf=interior,
            cover_booklet_pdf=cover,
            language="en",
            toc={"article": 4},
            article_pages={"article": 1},
            editorial_pages=None,
            edition_id="issue-001",
        )

    codes = {issue["code"] for issue in report["issues"] if issue["severity"] == "error"}
    assert report["result"] == "fail"
    assert "interior-booklet-side-count" in codes
    assert "cover-booklet-side-count" in codes
    assert "cover-booklet-geometry" in codes


def test_render_critic_checks_split_imposition_order_against_the_reader(tmp_path: Path):
    """Real impositions pass; a cover wrap folded the other way round does not."""
    reader = _numbered_reader(tmp_path / "reader.pdf", 8)
    booklet = impose_a5_on_a4(reader, tmp_path / "booklet.pdf")
    interior = impose_a5_on_a4(reader, tmp_path / "interior.pdf", section="interior")
    cover = impose_a5_on_a4(reader, tmp_path / "cover.pdf", section="cover")
    blank = {"reader-pages": {2, 7}, "booklet-sides": {2}, "cover-booklet-sides": {2}}

    with patch("magazine.render_critic._render_pages", side_effect=_rasters(blank)):
        report, _ = inspect_render(
            reader,
            booklet,
            tmp_path,
            interior_booklet_pdf=interior,
            cover_booklet_pdf=cover,
            language="en",
            toc={"article": 4},
            article_pages={"article": 1},
            editorial_pages=None,
            edition_id="issue-001",
        )

    codes = {issue["code"] for issue in report["issues"] if issue["severity"] == "error"}
    assert codes == set()
    assert all(row["text_order_matches"] for row in report["home_booklet_interior"]["spreads"])
    assert all(row["text_order_matches"] for row in report["home_booklet_cover"]["spreads"])

    swapped = PdfWriter()
    for side in reversed(PdfReader(str(cover)).pages):
        swapped.add_page(side)
    misfolded = tmp_path / "cover-misfolded.pdf"
    with misfolded.open("wb") as handle:
        swapped.write(handle)
    blank_swapped = {**blank, "cover-booklet-sides": {1}}

    with patch("magazine.render_critic._render_pages", side_effect=_rasters(blank_swapped)):
        report, _ = inspect_render(
            reader,
            booklet,
            tmp_path,
            interior_booklet_pdf=interior,
            cover_booklet_pdf=misfolded,
            language="en",
            toc={"article": 4},
            article_pages={"article": 1},
            editorial_pages=None,
            edition_id="issue-001",
        )

    codes = {issue["code"] for issue in report["issues"] if issue["severity"] == "error"}
    assert report["result"] == "fail"
    assert "cover-booklet-page-order" in codes


def test_render_critic_blocks_blank_pages_and_layout_contract_violations(tmp_path: Path):
    reader = tmp_path / "reader.pdf"
    _eight_page_pdf(reader)
    booklet = tmp_path / "booklet.pdf"
    _eight_page_pdf(booklet)
    all_blank = {name: set(range(1, 9)) for name in _CLEAN}

    with patch("magazine.render_critic._render_pages", side_effect=_rasters(all_blank)):
        report, _ = inspect_render(
            reader,
            booklet,
            tmp_path,
            **_split_documents(tmp_path),
            language="en",
            toc={"article": 5},
            article_pages={"article": 8},
            editorial_pages=3,
            edition_id="issue-001",
        )

    codes = {issue["code"] for issue in report["issues"] if issue["severity"] == "error"}
    assert report["result"] == "fail"
    assert codes == {
        "article-page-cap",
        "blank-page",
        "blank-booklet-side",
        "blank-cover-booklet-side",
        "contents-pagination",
        "editorial-page-cap",
    }


def test_render_critic_requires_blank_inside_covers_and_imposed_sides(tmp_path: Path):
    reader = tmp_path / "reader.pdf"
    _eight_page_pdf(reader)
    booklet = tmp_path / "booklet.pdf"
    _eight_page_pdf(booklet)

    def marked_inside_cover_rasters(pdf: Path, output: Path) -> list[Path]:
        paths = _rasters(_CLEAN)(pdf, output)
        targets = (paths[1], paths[6]) if output.name == "reader-pages" else (paths[1],)
        for path in targets:
            with Image.open(path) as opened:
                image = opened.copy()
            ImageDraw.Draw(image).rectangle((70, 70, 76, 76), fill="#f05738")
            image.save(path)
        return paths

    with patch("magazine.render_critic._render_pages", side_effect=marked_inside_cover_rasters):
        report, _ = inspect_render(
            reader,
            booklet,
            tmp_path,
            **_split_documents(tmp_path),
            language="en",
            toc={"article": 4},
            article_pages={"article": 1},
            editorial_pages=None,
            edition_id="issue-001",
        )

    codes = {issue["code"] for issue in report["issues"] if issue["severity"] == "error"}
    assert report["result"] == "fail"
    assert codes == {
        "inside-cover-booklet-not-blank",
        "inside-cover-reader-not-blank",
        "cover-booklet-inside-not-blank",
    }


def test_near_white_ink_fails_inside_covers_and_still_blanks_a_body_page(tmp_path: Path):
    """246-254 ink is below WHITE_THRESHOLD's notice but is not blankness.

    Both directions of the blank check must hold: a tint on an inside cover is
    ink the contract forbids, and a body page carrying only that tint is still
    an unintended blank page, not a printed one.
    """
    reader = tmp_path / "reader.pdf"
    _eight_page_pdf(reader)
    booklet = tmp_path / "booklet.pdf"
    _eight_page_pdf(booklet)
    tinted = {"reader-pages": {2, 5}, "booklet-sides": {2}, "cover-booklet-sides": {2}}

    with patch(
        "magazine.render_critic._render_pages", side_effect=_rasters(_CLEAN, tint=tinted)
    ):
        report, _ = inspect_render(
            reader,
            booklet,
            tmp_path,
            **_split_documents(tmp_path),
            language="en",
            toc={"article": 4},
            article_pages={"article": 1},
            editorial_pages=None,
            edition_id="issue-001",
        )

    errors = [issue for issue in report["issues"] if issue["severity"] == "error"]
    assert report["result"] == "fail"
    assert {issue["code"] for issue in errors} == {
        "inside-cover-reader-not-blank",
        "inside-cover-booklet-not-blank",
        "cover-booklet-inside-not-blank",
        "blank-page",
    }
    assert [issue["page"] for issue in errors if issue["code"] == "blank-page"] == [5]
    tinted_row = next(row for row in report["pages"] if row["page"] == 2)
    assert tinted_row["ink_ratio"] == 0.0
    assert tinted_row["ink_free"] is True
    assert tinted_row["blank"] is False


def _lined_reader(path: Path, page_count: int, lines: dict[int, list[str]]) -> Path:
    """An A5 reader carrying the given text lines per page, blanks elsewhere."""
    canvas = Canvas(str(path), pagesize=A5)
    for page in range(1, page_count + 1):
        canvas.setFont("Helvetica", 12)
        for index, line in enumerate(lines.get(page, [])):
            canvas.drawString(60, 500 - 16 * index, line)
        canvas.showPage()
    canvas.save()
    return path


def _imposed_documents(reader: Path, tmp_path: Path) -> dict[str, Path]:
    return {
        "interior_booklet_pdf": impose_a5_on_a4(reader, tmp_path / "interior.pdf", section="interior"),
        "cover_booklet_pdf": impose_a5_on_a4(reader, tmp_path / "cover.pdf", section="cover"),
    }


def test_page_inspection_measures_pale_presence_the_ink_ratio_cannot_see(tmp_path: Path):
    """A grey-250 band is zero ink but full presence, so pale tails are measurable."""
    raster = tmp_path / "page-1.png"
    image = Image.new("L", (400, 600), 255)
    ImageDraw.Draw(image).rectangle((50, 300, 350, 500), fill=250)
    image.save(raster)
    page = SimpleNamespace(extract_text=lambda: "")

    row = _inspect_page(raster, page, 1)

    assert row["ink_ratio"] == 0.0
    assert row["ink_bbox"] is None
    assert row["presence_ratio"] > 0.2
    assert row["presence_bbox"] == [50, 300, 351, 501]
    assert row["largest_void"] is None


def test_render_critic_flags_unmotivated_voids_but_excuses_an_articles_final_page(tmp_path: Path):
    """Full-measure voids are review prompts, except where an article just ends.

    Page 4 opens a three-page article with a dead band between two content
    blocks; page 5 runs dry halfway despite the article continuing; page 6 is
    the article's final page and may end wherever the prose does.
    """
    body_lines = [f"the running text keeps the page honest, line {index}" for index in range(6)]
    reader = _lined_reader(
        tmp_path / "reader.pdf", 8, {4: body_lines, 5: body_lines, 6: body_lines}
    )
    booklet = impose_a5_on_a4(reader, tmp_path / "booklet.pdf")

    def geometry_rasters(pdf: Path, output: Path) -> list[Path]:
        blank_sides = {"reader-pages": {2, 7}, "booklet-sides": {2}, "cover-booklet-sides": {2}}[
            output.name
        ]
        output.mkdir(parents=True, exist_ok=True)
        paths = []
        for page_number in range(1, len(PdfReader(str(pdf)).pages) + 1):
            image = Image.new("RGB", (560, 794), "white")
            draw = ImageDraw.Draw(image)
            if output.name == "reader-pages" and page_number == 4:
                draw.rectangle((70, 70, 490, 200), fill="#36333a")
                draw.rectangle((70, 600, 490, 720), fill="#36333a")
            elif output.name == "reader-pages" and page_number in {5, 6}:
                draw.rectangle((70, 70, 490, 300), fill="#36333a")
            elif page_number not in blank_sides:
                draw.rectangle((70, 70, 490, 720), fill="#36333a")
            path = output / f"page-{page_number}.png"
            image.save(path)
            paths.append(path)
        return paths

    with patch("magazine.render_critic._render_pages", side_effect=geometry_rasters):
        report, _ = inspect_render(
            reader,
            booklet,
            tmp_path,
            **_imposed_documents(reader, tmp_path),
            language="en",
            toc={"article": 4},
            article_pages={"article": 3},
            editorial_pages=None,
            edition_id="issue-001",
        )

    assert report["result"] == "pass"
    voids = [issue for issue in report["issues"] if issue["code"] == "whitespace-void"]
    assert [issue["page"] for issue in voids] == [4, 5]
    assert all(issue["severity"] == "review" for issue in voids)
    internal = next(row for row in report["pages"] if row["page"] == 4)["largest_void"]
    assert internal["trailing"] is False
    assert internal["width_fraction"] == 1.0
    assert 190 <= internal["height_points"] <= 210
    assert next(row for row in report["pages"] if row["page"] == 4)["voids"][0] == internal
    final_page = next(row for row in report["pages"] if row["page"] == 6)["largest_void"]
    assert final_page["trailing"] is True
    assert report["checks"]["live_area_points"] == [35.0, 35.0, 245.5, 360.5]
    # Each flagged void ships its evidence crop; the excused final page none.
    crop_kinds = [(row["kind"], row["page"]) for row in report["visual_review"]["crops"]]
    assert ("void", 4) in crop_kinds
    assert ("void", 5) in crop_kinds
    assert ("void", 6) not in crop_kinds
    assert (tmp_path / "render-review" / "crops" / "crop-p04-void.png").is_file()
    assert (tmp_path / "render-review" / "crops" / "crop-p05-void.png").is_file()


def test_a_trailing_excuse_no_longer_shadows_a_reportable_void_above_it(tmp_path: Path):
    """Every qualifying void answers for itself, not just the page's largest.

    Page 4 is the article's final page: its largest void is the trailing
    shortfall (excused, the article simply ends), but a second full-measure
    void sits higher, between two text blocks.  Recording only the largest
    void let that second void ride out of the report in the excused one's
    shadow.
    """
    body_lines = [f"the running text keeps the page honest, line {index}" for index in range(6)]
    reader = _lined_reader(tmp_path / "reader.pdf", 8, {4: body_lines})
    booklet = impose_a5_on_a4(reader, tmp_path / "booklet.pdf")

    def shadowing_rasters(pdf: Path, output: Path) -> list[Path]:
        blank_sides = {"reader-pages": {2, 7}, "booklet-sides": {2}, "cover-booklet-sides": {2}}[
            output.name
        ]
        output.mkdir(parents=True, exist_ok=True)
        paths = []
        for page_number in range(1, len(PdfReader(str(pdf)).pages) + 1):
            image = Image.new("RGB", (560, 794), "white")
            draw = ImageDraw.Draw(image)
            if output.name == "reader-pages" and page_number == 4:
                # Text, a 130 pt dead band, one more line, then the page
                # runs dry: the 135 pt trailing void is the largest.
                draw.rectangle((70, 70, 490, 160), fill="#36333a")
                draw.rectangle((70, 420, 490, 450), fill="#36333a")
            elif page_number not in blank_sides:
                draw.rectangle((70, 70, 490, 720), fill="#36333a")
            path = output / f"page-{page_number}.png"
            image.save(path)
            paths.append(path)
        return paths

    with patch("magazine.render_critic._render_pages", side_effect=shadowing_rasters):
        report, _ = inspect_render(
            reader,
            booklet,
            tmp_path,
            **_imposed_documents(reader, tmp_path),
            language="en",
            toc={"article": 4},
            article_pages={"article": 1},
            editorial_pages=None,
            edition_id="issue-001",
        )

    assert report["result"] == "pass"
    voids = [issue for issue in report["issues"] if issue["code"] == "whitespace-void"]
    assert [issue["page"] for issue in voids] == [4]
    row = next(row for row in report["pages"] if row["page"] == 4)
    assert row["largest_void"]["trailing"] is True
    assert len(row["voids"]) == 2
    assert row["voids"][1]["trailing"] is False
    assert 120 <= row["voids"][1]["height_points"] <= 140
    assert (tmp_path / "render-review" / "crops" / "crop-p04-void.png").is_file()


def test_a_centered_tail_bands_margins_are_design_but_a_stranded_bands_are_not(tmp_path: Path):
    """The ornament's symmetric margins pass; a foot-anchored band flags.

    Both variants print a 100 pt band on the article's final page.  Centered,
    the ~100 pt void above it mirrors the ~80 pt gap below -- the design's
    own centering -- so nothing is flagged.  Stranded at the foot, the same
    band leaves a 180 pt void above and nothing below: dead paper.
    """
    body_lines = [f"the running text keeps the page honest, line {index}" for index in range(6)]
    reader = _lined_reader(tmp_path / "reader.pdf", 8, {4: body_lines})
    booklet = impose_a5_on_a4(reader, tmp_path / "booklet.pdf")
    _manifest_with_layout(
        tmp_path,
        {
            "tail_arts": [
                {"article": "article", "declared": True, "printed": True,
                 "height_points": 100.0, "drop_reason": None},
            ]
        },
    )

    def rasters_with_band(band_top: int):
        def stub(pdf: Path, output: Path) -> list[Path]:
            blank_sides = {
                "reader-pages": {2, 7}, "booklet-sides": {2}, "cover-booklet-sides": {2}
            }[output.name]
            output.mkdir(parents=True, exist_ok=True)
            paths = []
            for page_number in range(1, len(PdfReader(str(pdf)).pages) + 1):
                image = Image.new("RGB", (560, 794), "white")
                draw = ImageDraw.Draw(image)
                if output.name == "reader-pages" and page_number == 4:
                    draw.rectangle((70, 70, 490, 160), fill="#36333a")
                    # The 100 pt tail band (200 px), pale as the press sets it.
                    draw.rectangle((70, band_top, 490, band_top + 199), fill=(250, 250, 250))
                elif page_number not in blank_sides:
                    draw.rectangle((70, 70, 490, 720), fill="#36333a")
                path = output / f"page-{page_number}.png"
                image.save(path)
                paths.append(path)
            return paths

        return stub

    def inspect(band_top: int):
        with patch(
            "magazine.render_critic._render_pages", side_effect=rasters_with_band(band_top)
        ):
            report, _ = inspect_render(
                reader,
                booklet,
                tmp_path,
                **_imposed_documents(reader, tmp_path),
                language="en",
                toc={"article": 4},
                article_pages={"article": 1},
                editorial_pages=None,
                edition_id="issue-001",
            )
        return report

    # Centered: 100 pt margin above (rows 160-360), 80 pt below (560-720).
    centered = inspect(360)
    assert centered["result"] == "pass"
    assert not [row for row in centered["issues"] if row["code"] == "whitespace-void"]
    band = next(row for row in centered["pages"] if row["page"] == 4)["tail_band"]
    assert band is not None
    assert band["centered"] is True
    assert 96 <= band["height_points"] <= 104
    assert abs(band["gap_above_points"] - band["gap_below_points"]) <= 32
    assert (tmp_path / "render-review" / "crops" / "crop-p04-tail.png").is_file()

    # Stranded at the foot: 180 pt of dead paper above, nothing below.
    stranded = inspect(520)
    voids = [row for row in stranded["issues"] if row["code"] == "whitespace-void"]
    assert [row["page"] for row in voids] == [4]
    band = next(row for row in stranded["pages"] if row["page"] == 4)["tail_band"]
    assert band is not None
    assert band["centered"] is False


def test_render_critic_flags_an_article_ending_on_a_stub(tmp_path: Path):
    """Two lines of running text on an article's declared last page is a remnant."""
    reader = _lined_reader(
        tmp_path / "reader.pdf",
        8,
        {
            4: ["the article ends here, on a remnant", "of just two lines"],
            5: [f"a healthy closing page, line {index}" for index in range(6)],
        },
    )
    booklet = impose_a5_on_a4(reader, tmp_path / "booklet.pdf")

    with patch("magazine.render_critic._render_pages", side_effect=_rasters(_CLEAN)):
        report, _ = inspect_render(
            reader,
            booklet,
            tmp_path,
            **_imposed_documents(reader, tmp_path),
            language="en",
            toc={"stubby": 4, "healthy": 5},
            article_pages={"stubby": 1, "healthy": 1},
            editorial_pages=None,
            edition_id="issue-001",
        )

    assert report["result"] == "pass"
    stubs = [issue for issue in report["issues"] if issue["code"] == "article-stub-last-page"]
    assert len(stubs) == 1
    assert stubs[0]["severity"] == "review"
    assert stubs[0]["page"] == 4
    assert "stubby" in stubs[0]["message"]
    assert next(row for row in report["pages"] if row["page"] == 4)["body_text_lines"] == 2


def _manifest_with_layout(tmp_path: Path, layout: dict) -> None:
    (tmp_path / "edition-manifest.json").write_text(
        json.dumps({"layout": layout}), encoding="utf-8"
    )


def test_render_critic_reconciles_declared_tail_arts_when_the_manifest_exposes_them(tmp_path: Path):
    reader = tmp_path / "reader.pdf"
    _eight_page_pdf(reader)
    booklet = tmp_path / "booklet.pdf"
    _eight_page_pdf(booklet)
    _manifest_with_layout(
        tmp_path,
        {
            "tail_arts": [
                {"article": "kept", "declared": True, "printed": True,
                 "height_points": 44.0, "drop_reason": None},
                {"article": "dropped", "declared": True, "printed": False,
                 "height_points": None, "drop_reason": "band fell below the minimum height"},
                {"article": "undeclared", "declared": False, "printed": False,
                 "height_points": None, "drop_reason": None},
            ]
        },
    )

    with patch("magazine.render_critic._render_pages", side_effect=_rasters(_CLEAN)):
        report, _ = inspect_render(
            reader,
            booklet,
            tmp_path,
            **_split_documents(tmp_path),
            language="en",
            toc={"article": 4},
            article_pages={"article": 1},
            editorial_pages=None,
            edition_id="issue-001",
        )

    assert report["result"] == "pass"
    dropped = [issue for issue in report["issues"] if issue["code"] == "tail-art-dropped"]
    assert len(dropped) == 1
    assert dropped[0]["severity"] == "review"
    assert "'dropped'" in dropped[0]["message"]
    assert "band fell below the minimum height" in dropped[0]["message"]


def test_render_critic_ignores_tail_arts_when_the_manifest_predates_the_key(tmp_path: Path):
    reader = tmp_path / "reader.pdf"
    _eight_page_pdf(reader)
    booklet = tmp_path / "booklet.pdf"
    _eight_page_pdf(booklet)
    _manifest_with_layout(tmp_path, {"editorial_pages": 1})

    with patch("magazine.render_critic._render_pages", side_effect=_rasters(_CLEAN)):
        report, _ = inspect_render(
            reader,
            booklet,
            tmp_path,
            **_split_documents(tmp_path),
            language="en",
            toc={"article": 4},
            article_pages={"article": 1},
            editorial_pages=None,
            edition_id="issue-001",
        )

    assert not [issue for issue in report["issues"] if issue["code"] == "tail-art-dropped"]


def test_render_critic_enforces_the_editions_own_editorial_cap_from_the_manifest(tmp_path: Path):
    """A one-page edition contract beats the two-page publication default."""
    reader = tmp_path / "reader.pdf"
    _eight_page_pdf(reader)
    booklet = tmp_path / "booklet.pdf"
    _eight_page_pdf(booklet)
    _manifest_with_layout(tmp_path, {"maximum_editorial_pages": 1})

    def inspect(editorial_pages):
        with patch("magazine.render_critic._render_pages", side_effect=_rasters(_CLEAN)):
            report, _ = inspect_render(
                reader,
                booklet,
                tmp_path,
                **_split_documents(tmp_path),
                language="en",
                toc={"article": 4},
                article_pages={"article": 1},
                editorial_pages=editorial_pages,
                edition_id="issue-001",
            )
        return report

    within = inspect(1)
    assert within["result"] == "pass"
    assert within["checks"]["editorial_page_cap"] == 1

    over = inspect(2)
    assert over["result"] == "fail"
    assert "editorial-page-cap" in {
        issue["code"] for issue in over["issues"] if issue["severity"] == "error"
    }

    # Without a readable manifest the publication default of two pages holds.
    (tmp_path / "edition-manifest.json").unlink()
    default = inspect(2)
    assert default["result"] == "pass"
    assert default["checks"]["editorial_page_cap"] == 2


def test_page_inspection_detects_orphan_display_punctuation(tmp_path: Path):
    raster = tmp_path / "page-1.png"
    Image.new("RGB", (100, 100), "#333333").save(raster)
    page = SimpleNamespace(extract_text=lambda: "Title\n,\nBody")

    result = _inspect_page(raster, page, 1)

    assert result["standalone_punctuation_lines"] == [","]


def _recorded_run(commands: list[list[str]]):
    """Wrap ``subprocess.run`` so a test can read the argv the critic built."""
    real_run = subprocess.run

    def run(command, *args, **kwargs):
        commands.append([str(part) for part in command])
        return real_run(command, *args, **kwargs)

    return run


def _window(command: list[str]) -> tuple[int, int] | None:
    """The inclusive ``-f``/``-l`` page range of a pdftoppm argv, if it has one."""
    if "-f" not in command:
        return None
    return int(command[command.index("-f") + 1]), int(command[command.index("-l") + 1])


def test_sharded_rasterization_is_byte_identical_to_one_pdftoppm_run(tmp_path: Path):
    """The pages a build reviews must not depend on how the raster was split.

    Recorded review decisions bind the SHA-256 of the packaged rasters, so the
    sharded render has to agree with the single-command render on every name,
    on their order, and on every byte.
    """
    reader = _numbered_reader(tmp_path / "reader.pdf", 12)

    commands: list[list[str]] = []
    with patch("magazine.render_critic.subprocess.run", side_effect=_recorded_run(commands)):
        sharded = _render_pages(reader, tmp_path / "sharded")
    with patch("magazine.render_critic.worker_count", return_value=1):
        single = _render_pages(reader, tmp_path / "single")

    windows = [_window(command) for command in commands]
    assert len(windows) > 1 and all(window is not None for window in windows)
    # Contiguous, gapless, and covering all twelve pages exactly once.
    assert [page for first, last in windows for page in range(first, last + 1)] == list(
        range(1, 13)
    )

    def digests(pages: list[Path]) -> list[tuple[str, str]]:
        return [(page.name, hashlib.sha256(page.read_bytes()).hexdigest()) for page in pages]

    assert [page.name for page in single] == [f"page-{number:03d}.png" for number in range(1, 13)]
    assert digests(sharded) == digests(single)


def test_a_short_document_rasterizes_with_a_single_unwindowed_command(tmp_path: Path):
    """One or two pages keep the exact command this function has always run."""
    for page_count in (1, 2):
        reader = _numbered_reader(tmp_path / f"reader-{page_count}.pdf", page_count)
        commands: list[list[str]] = []
        with patch("magazine.render_critic.subprocess.run", side_effect=_recorded_run(commands)):
            pages = _render_pages(reader, tmp_path / f"pages-{page_count}")

        assert len(commands) == 1
        assert "-f" not in commands[0] and "-l" not in commands[0]
        assert [page.name for page in pages] == [
            f"page-{number:03d}.png" for number in range(1, page_count + 1)
        ]


def test_the_lowest_shard_owns_the_error_whichever_shard_failed_first(tmp_path: Path):
    """A Poppler failure must read the same however the threads were scheduled."""
    reader = _numbered_reader(tmp_path / "reader.pdf", 12)

    def run(command, *args, **kwargs):
        window = _window(command)
        if window == (4, 6):
            # Loses the race deliberately: the last shard has already failed by
            # the time this one reports, so only ordering can pick this message.
            time.sleep(0.2)
            return subprocess.CompletedProcess(command, 1, "", "second shard broke")
        if window == (10, 12):
            return subprocess.CompletedProcess(command, 1, "", "last shard broke")
        return subprocess.CompletedProcess(command, 0, "", "")

    with patch("magazine.render_critic.worker_count", return_value=4):
        with patch("magazine.render_critic.subprocess.run", side_effect=run):
            with pytest.raises(DependencyError) as raised:
                _render_pages(reader, tmp_path / "pages")

    assert str(raised.value) == (
        "Could not rasterize reader PDF for criticism: second shard broke"
    )


def test_rasterizing_without_pdftoppm_raises_a_dependency_error(tmp_path: Path):
    reader = _numbered_reader(tmp_path / "reader.pdf", 4)

    with patch("magazine.render_critic.shutil.which", return_value=None):
        with pytest.raises(DependencyError, match="Poppler's pdftoppm executable"):
            _render_pages(reader, tmp_path / "pages")


def test_an_unreadable_pdf_still_fails_with_popplers_own_diagnosis(tmp_path: Path):
    """A document too broken to plan a split for must fail as it always did.

    Planning the shards reads the page count with ``pypdf``, which puts a second
    parser in front of Poppler's.  An unreadable file must not start raising
    that parser's ``PdfStreamError``: the error this module owes a caller for a
    file Poppler cannot read is a ``DependencyError`` quoting Poppler, and the
    fallback to the unsharded command is what keeps it so.
    ``tools/compare_pipelines.py`` is the one caller that reaches this function
    directly, without ``inspect_render``'s prior ``PdfReader`` construction to
    fail first, so it is the only path where the difference is observable.
    """
    import shutil

    if shutil.which("pdftoppm") is None:  # pragma: no cover - Poppler is a build requirement
        pytest.skip("Only Poppler can refuse the broken PDF this test hands it")

    readable = _numbered_reader(tmp_path / "reader.pdf", 12).read_bytes()
    truncated = tmp_path / "truncated.pdf"
    truncated.write_bytes(readable[: len(readable) // 2])
    # The premise of the test: a file pypdf can still read would exercise the
    # ordinary sharded path and prove nothing about the fallback.
    with pytest.raises(Exception):
        len(PdfReader(str(truncated)).pages)

    with pytest.raises(DependencyError) as raised:
        _render_pages(truncated, tmp_path / "pages")

    assert type(raised.value).__module__.startswith("magazine")
    assert "Could not rasterize reader PDF for criticism" in str(raised.value)
    assert "Syntax Error" in str(raised.value)


def test_cover_placeholder_pattern_rejects_ellipsis_and_drafting_markers():
    assert _COVER_PLACEHOLDER.search("AGENT SWARMS...")
    assert _COVER_PLACEHOLDER.search("TBD")
    assert not _COVER_PLACEHOLDER.search("Reusable blocks")


def _extraction_log(log: list[tuple[int, int, str]]):
    """Wrap pypdf's own extraction so a test sees every real call the critic makes.

    A call is identified by the document object it came from and the page's PDF
    object number, which is what "the same page of the same document" means
    underneath the critic's own 1-indexed numbering. The collapsed text rides
    along because it names the page: a reader page of ``_numbered_reader``
    carries one token, an imposed side carries the two it pairs.
    """
    real_extract_text = PageObject.extract_text

    def extract_text(self, *args, **kwargs):
        text = real_extract_text(self, *args, **kwargs)
        reference = self.indirect_reference
        log.append((id(reference.pdf), reference.idnum, " ".join((text or "").split())))
        return text

    return extract_text


def _fake_document(*texts: str):
    """A document of literal page texts, plus the log of pages actually extracted."""
    calls: list[int] = []

    def page(number: int) -> SimpleNamespace:
        def extract_text() -> str:
            calls.append(number)
            return texts[number - 1]

        return SimpleNamespace(extract_text=extract_text)

    return SimpleNamespace(pages=[page(number) for number in range(1, len(texts) + 1)]), calls


class _UncachedPageTexts(_PageTexts):
    """The critic as it behaved before the store cached: every ask re-extracts.

    Only the memoization is defeated -- the real extraction and the real
    whitespace collapse still run -- so a report built through this store
    differs from a cached one in nothing but how many times pypdf was asked.
    """

    def raw(self, page_number: int) -> str:
        self._raw.pop(page_number, None)
        return super().raw(page_number)

    def normalized(self, page_number: int) -> str:
        self._normalized.pop(page_number, None)
        return super().normalized(page_number)


def test_no_page_of_any_document_is_extracted_twice_in_one_inspection(tmp_path: Path):
    """Extraction is the critic's most expensive call, so a page pays it once.

    A reader page used to be pulled from pypdf up to four times in one run --
    once for its own row, then again by each of the three imposition passes,
    which between them re-cover every page -- and the shared ``_PageTexts``
    store exists to make the second, third and fourth ask free. Reader page 3
    is the case that proves the sharing: the all-in-one booklet and the
    interior both impose it, so a store built inside the comparing function
    would extract it twice. Page 1 is read three times over, by the all-in-one
    booklet, the cover wrap and the cover placeholder check.
    """
    reader = _numbered_reader(tmp_path / "reader.pdf", 8)
    booklet = impose_a5_on_a4(reader, tmp_path / "booklet.pdf")
    imposed = _imposed_documents(reader, tmp_path)
    log: list[tuple[int, int, str]] = []

    with patch("magazine.render_critic._render_pages", side_effect=_rasters(_CLEAN)):
        with patch.object(PageObject, "extract_text", _extraction_log(log)):
            report, _ = inspect_render(
                reader,
                booklet,
                tmp_path,
                **imposed,
                language="en",
                toc={"article": 4},
                article_pages={"article": 1},
                editorial_pages=None,
                edition_id="issue-001",
            )

    assert report["result"] == "pass"
    assert all(row["text_order_matches"] for row in report["home_booklet"]["spreads"])
    extractions = Counter((document, page) for document, page, _ in log)
    assert extractions and max(extractions.values()) == 1
    # Reader pages 2 and 7 are the blank inside covers, so the six that carry a
    # single token are every reader page with words on it -- each extracted once.
    reader_pages = Counter(text for _, _, text in log if text and " " not in text)
    assert reader_pages == Counter(f"READERPAGE{page}" for page in (1, 3, 4, 5, 6, 8))


def test_page_text_is_extracted_only_when_a_check_asks_for_it(tmp_path: Path):
    """Nothing is pre-extracted: an unasked page costs a run nothing at all.

    The interior here carries four sides where the plan reaches two, the shape a
    mis-imposed section really takes, and the two sides no check looks at must
    stay unread. Extracting a document up front would only move that cost.
    """
    reader = _numbered_reader(tmp_path / "reader.pdf", 8)
    booklet = impose_a5_on_a4(reader, tmp_path / "booklet.pdf")
    interior = _a4_landscape_pdf(tmp_path / "interior.pdf", 4)
    cover = impose_a5_on_a4(reader, tmp_path / "cover.pdf", section="cover")
    log: list[tuple[int, int, str]] = []

    with patch("magazine.render_critic._render_pages", side_effect=_rasters(_CLEAN)):
        with patch.object(PageObject, "extract_text", _extraction_log(log)):
            report, _ = inspect_render(
                reader,
                booklet,
                tmp_path,
                interior_booklet_pdf=interior,
                cover_booklet_pdf=cover,
                language="en",
                toc={"article": 4},
                article_pages={"article": 1},
                editorial_pages=None,
                edition_id="issue-001",
            )

    assert "interior-booklet-side-count" in {issue["code"] for issue in report["issues"]}
    # Eight reader pages, four all-in-one sides, two cover sides and the two
    # interior sides the plan reaches: the extra two interior sides are absent.
    assert len(log) == 16
    assert len(set((document, page) for document, page, _ in log)) == 16


def test_the_cached_report_is_identical_to_one_extracted_page_by_page(tmp_path: Path):
    """The store is a pure optimization: same rows, same fields, same order.

    Recorded review decisions bind the SHA-256 of the packaged artifacts, so
    render-critic.json has to serialize byte for byte as it did when every check
    extracted its own text. The comparison runs the same fixture through a store
    that never caches -- the old behaviour exactly -- and compares the serialized
    reports, which catches a reordered key as well as a changed value.
    """
    body_lines = [f"the running text keeps the page honest, line {index}" for index in range(6)]
    reader = _lined_reader(tmp_path / "reader.pdf", 8, {4: body_lines, 5: body_lines})
    booklet = impose_a5_on_a4(reader, tmp_path / "booklet.pdf")
    imposed = _imposed_documents(reader, tmp_path)

    def inspect() -> dict:
        with patch("magazine.render_critic._render_pages", side_effect=_rasters(_CLEAN)):
            report, _ = inspect_render(
                reader,
                booklet,
                tmp_path,
                **imposed,
                language="en",
                toc={"article": 4},
                article_pages={"article": 3},
                editorial_pages=None,
                edition_id="issue-001",
            )
        return report

    cached_log: list[tuple[int, int, str]] = []
    with patch.object(PageObject, "extract_text", _extraction_log(cached_log)):
        cached = inspect()
    uncached_log: list[tuple[int, int, str]] = []
    with patch.object(PageObject, "extract_text", _extraction_log(uncached_log)):
        with patch("magazine.render_critic._PageTexts", _UncachedPageTexts):
            uncached = inspect()

    assert json.dumps(cached, indent=2) == json.dumps(uncached, indent=2)
    # The comparison only means something if the uncached run really did the
    # work twice over, which is the work the store removes.
    assert len(uncached_log) > len(cached_log)


def test_page_texts_serves_the_raw_and_collapsed_shapes_from_one_extraction():
    """Both shapes the checks want come off a single ask, whatever the whitespace.

    ``_inspect_page`` counts lines, so it needs the text as pypdf gives it;
    imposition order is compared on whitespace-collapsed text. Deriving the
    second from the first is what keeps a page from being extracted twice for
    the two shapes.
    """
    document, calls = _fake_document("Title \n\n  two   spaces \n", "never asked for")
    texts = _PageTexts(document)

    assert texts.raw(1) == "Title \n\n  two   spaces \n"
    assert texts.normalized(1) == "Title two spaces"
    assert texts.raw(1) == "Title \n\n  two   spaces \n"
    assert texts.normalized(1) == "Title two spaces"
    assert calls == [1]
    assert texts.page_count == 2


def test_spread_checks_still_accept_bare_readers_for_the_comparison_tool(tmp_path: Path):
    """``tools/compare_pipelines.py`` passes two ``PdfReader``s and must keep working."""
    reader = _numbered_reader(tmp_path / "reader.pdf", 8)
    booklet = impose_a5_on_a4(reader, tmp_path / "booklet.pdf")
    plan = imposed_reader_page_plan(section_reader_pages(8, "all"))

    from_readers = _booklet_spread_checks(PdfReader(str(reader)), PdfReader(str(booklet)), plan)
    from_stores = _booklet_spread_checks(
        _PageTexts(PdfReader(str(reader))), _PageTexts(PdfReader(str(booklet))), plan
    )

    assert from_readers == from_stores
    assert all(row["text_order_matches"] for row in from_readers)


def _crop_specs() -> list[dict]:
    """Crop specs whose awkward cases the concurrent rasterization must survive.

    Page 3 is asked for twice with one kind, so the ``-2`` suffix depends on the
    order the specs are walked; page 4 carries a degenerate box, which the serial
    version still rasterized its page for before discarding the crop; and page 5
    is reached before page 4 is, so spec order and page order disagree.
    """
    width, height = A5

    def spec(page: int, kind: str, subject: str | None, region: tuple[float, ...]) -> dict:
        return {"page": page, "kind": kind, "subject": subject, "region": region}

    return [
        spec(3, "opener", "Opening block", (0.0, 40.0, width, 320.0)),
        spec(5, "tail", None, (0.0, 300.0, width, height)),
        spec(3, "opener", "Byline column", (0.0, 210.0, width, 500.0)),
        spec(4, "figure", "Collapsed box", (12.0, 12.0, 12.0, 12.0)),
        spec(7, "void", "Dead skirt", (0.0, 0.0, width, 240.0)),
    ]


def test_review_crops_are_byte_identical_however_wide_the_rasterization_was(tmp_path: Path):
    """The crops a human signs off on must not depend on the raster fan-out.

    Recorded review decisions bind the SHA-256 of the packaged crops, so the
    threaded run has to agree with a one-thread run on every file name, on the
    manifest rows including their rounded ``region_points``, and on every byte.
    """
    reader = _numbered_reader(tmp_path / "reader.pdf", 8)

    threaded_root = tmp_path / "threaded"
    serial_root = tmp_path / "serial"
    threaded, threaded_rows = _write_review_crops(
        reader, threaded_root / "crops", threaded_root, _crop_specs()
    )
    with patch("magazine.render_critic.worker_count", return_value=1):
        serial, serial_rows = _write_review_crops(
            reader, serial_root / "crops", serial_root, _crop_specs()
        )

    # The degenerate box writes nothing, and page 3's second crop earns the
    # suffix because it is the later of the two *specs*, not the later page.
    assert [path.name for path in threaded] == [
        "crop-p03-opener.png",
        "crop-p05-tail.png",
        "crop-p03-opener-2.png",
        "crop-p07-void.png",
    ]
    assert [path.name for path in threaded] == [path.name for path in serial]
    assert threaded_rows == serial_rows
    assert [row["region_points"][2] for row in threaded_rows] == [419.5] * 4

    def digests(paths: list[Path]) -> list[tuple[str, str]]:
        return [(path.name, hashlib.sha256(path.read_bytes()).hexdigest()) for path in paths]

    assert digests(threaded) == digests(serial)


def test_every_cropped_page_is_rasterized_once_including_a_degenerate_box(tmp_path: Path):
    """Pre-rendering may not change which pages Poppler is asked for.

    A page feeding two crops still costs one raster, and the page whose box
    collapses still costs one -- dropping it would quietly stop reporting a
    Poppler failure that a build reports today.
    """
    reader = _numbered_reader(tmp_path / "reader.pdf", 8)
    requested: list[int] = []

    def render(reader_pdf: Path, page_number: int, output_dir: Path) -> Path:
        requested.append(page_number)
        return _render_crop_page(reader_pdf, page_number, output_dir)

    review = tmp_path / "review"
    with patch("magazine.render_critic._render_crop_page", side_effect=render):
        _write_review_crops(reader, review / "crops", review, _crop_specs())

    assert sorted(requested) == [3, 4, 5, 7]


def test_the_lowest_cropped_page_owns_the_error_whichever_page_failed_first(tmp_path: Path):
    """A Poppler failure must read the same however the threads were scheduled.

    Page 5 is named before page 4 in the spec list and fails first, so only
    handing the pages over in page order picks page 4's message: completion order
    and spec order both choose page 5's.
    """
    reader = _numbered_reader(tmp_path / "reader.pdf", 8)

    def render(reader_pdf: Path, page_number: int, output_dir: Path) -> Path:
        if page_number == 4:
            # Loses the race deliberately: page 5 has already failed by the time
            # this one reports, so only input ordering can pick this message.
            time.sleep(0.2)
            raise DependencyError("Could not rasterize reader page 4 for crops: lower page broke")
        if page_number == 5:
            raise DependencyError("Could not rasterize reader page 5 for crops: higher page broke")
        return _render_crop_page(reader_pdf, page_number, output_dir)

    with patch("magazine.render_critic.worker_count", return_value=4):
        with patch("magazine.render_critic._render_crop_page", side_effect=render):
            with pytest.raises(DependencyError) as raised:
                _write_review_crops(
                    reader, tmp_path / "review" / "crops", tmp_path / "review", _crop_specs()
                )

    assert str(raised.value) == "Could not rasterize reader page 4 for crops: lower page broke"


def test_the_full_page_rasters_are_gone_whether_the_cropping_finished_or_raised(tmp_path: Path):
    """300 ppi full pages are five times the size of the crops they feed.

    Leaving them behind on a failure would ship them in the review directory
    the next time a build got further than this one did.
    """
    reader = _numbered_reader(tmp_path / "reader.pdf", 8)

    done_root = tmp_path / "done"
    _write_review_crops(reader, done_root / "crops", done_root, _crop_specs())
    assert not (done_root / "crops" / "pages-at-300").exists()

    failed_root = tmp_path / "failed"

    def render(reader_pdf: Path, page_number: int, output_dir: Path) -> Path:
        path = _render_crop_page(reader_pdf, page_number, output_dir)
        if page_number == 7:
            raise DependencyError("Could not rasterize reader page 7 for crops: broke late")
        return path

    with patch("magazine.render_critic._render_crop_page", side_effect=render):
        with pytest.raises(DependencyError):
            _write_review_crops(reader, failed_root / "crops", failed_root, _crop_specs())
    assert not (failed_root / "crops" / "pages-at-300").exists()

    # An edition with nothing to crop touches the filesystem not at all.
    empty_root = tmp_path / "none"
    assert _write_review_crops(reader, empty_root / "crops", empty_root, []) == ([], [])
    assert not empty_root.exists()
