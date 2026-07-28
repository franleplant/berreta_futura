import json
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
    final_page = next(row for row in report["pages"] if row["page"] == 6)["largest_void"]
    assert final_page["trailing"] is True
    assert report["checks"]["live_area_points"] == [35.0, 35.0, 245.5, 360.5]


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


def test_cover_placeholder_pattern_rejects_ellipsis_and_drafting_markers():
    assert _COVER_PLACEHOLDER.search("AGENT SWARMS...")
    assert _COVER_PLACEHOLDER.search("TBD")
    assert not _COVER_PLACEHOLDER.search("Reusable blocks")
