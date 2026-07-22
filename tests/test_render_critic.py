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
        if output.name == "reader-pages" and page_number == 2:
            ImageDraw.Draw(image).rectangle((70, 720, 76, 726), fill="#f05738")
        elif output.name == "reader-pages" and page_number == 7:
            ImageDraw.Draw(image).rectangle((484, 70, 490, 76), fill="#f05738")
        elif output.name == "booklet-sides" and page_number == 2:
            draw = ImageDraw.Draw(image)
            draw.rectangle((70, 720, 76, 726), fill="#f05738")
            draw.rectangle((484, 70, 490, 76), fill="#f05738")
        else:
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
        "inside-cover-booklet-ornament-missing",
        "inside-cover-reader-ornament-missing",
    }


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
