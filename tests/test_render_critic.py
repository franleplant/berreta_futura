from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw
from pypdf import PdfWriter

from magazine.render_critic import _COVER_PLACEHOLDER, _inspect_page, inspect_render


def _eight_page_pdf(path: Path) -> None:
    writer = PdfWriter()
    for _ in range(8):
        writer.add_blank_page(width=419.5276, height=595.2756)
    with path.open("wb") as handle:
        writer.write(handle)


def _inked_rasters(_reader: Path, output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    pages = []
    for page_number in range(1, 9):
        path = output / f"page-{page_number}.png"
        image = Image.new("RGB", (560, 794), "white")
        if not (
            (output.name == "reader-pages" and page_number in {2, 7})
            or (output.name == "booklet-sides" and page_number == 2)
        ):
            ImageDraw.Draw(image).rectangle((70, 70, 490, 720), fill="#36333a")
        image.save(path)
        pages.append(path)
    return pages


def test_render_critic_emits_contact_sheet_and_passes_structural_checks(tmp_path: Path):
    reader = tmp_path / "reader.pdf"
    _eight_page_pdf(reader)
    booklet = tmp_path / "booklet.pdf"
    _eight_page_pdf(booklet)

    with patch("magazine.render_critic._render_pages", side_effect=_inked_rasters):
        report, artifacts = inspect_render(
            reader,
            booklet,
            tmp_path,
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
    assert "render-review/reader-contact-sheet-01.png" in relative_artifacts
    assert "render-review/booklet-contact-sheet-01.png" in relative_artifacts
    assert len(artifacts) == 18
    assert all(path.is_file() for path in artifacts)


def test_render_critic_blocks_blank_pages_and_layout_contract_violations(tmp_path: Path):
    reader = tmp_path / "reader.pdf"
    _eight_page_pdf(reader)
    booklet = tmp_path / "booklet.pdf"
    _eight_page_pdf(booklet)

    def blank_rasters(_reader: Path, output: Path) -> list[Path]:
        output.mkdir(parents=True, exist_ok=True)
        paths = []
        for page_number in range(1, 9):
            path = output / f"page-{page_number}.png"
            Image.new("RGB", (560, 794), "white").save(path)
            paths.append(path)
        return paths

    with patch("magazine.render_critic._render_pages", side_effect=blank_rasters):
        report, _ = inspect_render(
            reader,
            booklet,
            tmp_path,
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
        "contents-pagination",
        "editorial-page-cap",
    }


def test_render_critic_requires_blank_inside_covers_and_imposed_side(tmp_path: Path):
    reader = tmp_path / "reader.pdf"
    _eight_page_pdf(reader)
    booklet = tmp_path / "booklet.pdf"
    _eight_page_pdf(booklet)

    def marked_inside_cover_rasters(_reader: Path, output: Path) -> list[Path]:
        paths = _inked_rasters(_reader, output)
        if output.name == "reader-pages":
            targets = (paths[1], paths[6])
        else:
            targets = (paths[1],)
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
            language="en",
            toc={"article": 4},
            article_pages={"article": 1},
            editorial_pages=None,
            edition_id="issue-001",
        )

    codes = {issue["code"] for issue in report["issues"] if issue["severity"] == "error"}
    assert report["result"] == "fail"
    assert codes == {"inside-cover-booklet-not-blank", "inside-cover-reader-not-blank"}


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

    def tint(path: Path) -> None:
        image = Image.new("RGB", (560, 794), "white")
        ImageDraw.Draw(image).rectangle((70, 70, 490, 720), fill=(250, 250, 250))
        image.save(path)

    def near_white_rasters(_reader: Path, output: Path) -> list[Path]:
        paths = _inked_rasters(_reader, output)
        if output.name == "reader-pages":
            tint(paths[1])  # inside front cover
            tint(paths[4])  # body page 5
        else:
            tint(paths[1])  # imposed inside-cover side
        return paths

    with patch("magazine.render_critic._render_pages", side_effect=near_white_rasters):
        report, _ = inspect_render(
            reader,
            booklet,
            tmp_path,
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
