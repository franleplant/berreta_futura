from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from magazine.booklet import impose_a5_on_a4
from magazine.render_critic import _COVER_PLACEHOLDER, _inspect_page, inspect_render

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
    assert len(artifacts) == 20
    assert all(path.is_file() for path in artifacts)


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


def test_page_inspection_detects_orphan_display_punctuation(tmp_path: Path):
    raster = tmp_path / "page-1.png"
    Image.new("RGB", (100, 100), "#333333").save(raster)
    page = SimpleNamespace(extract_text=lambda: "Title\n,\nBody")

    result = _inspect_page(raster, page, 1)

    assert result["standalone_punctuation_lines"] == [","]


def test_cover_placeholder_pattern_rejects_ellipsis_and_drafting_markers():
    assert _COVER_PLACEHOLDER.search("AGENT SWARMS...")
    assert _COVER_PLACEHOLDER.search("TBD")
    assert not _COVER_PLACEHOLDER.search("Reusable blocks")
