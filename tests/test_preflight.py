from pathlib import Path

from PIL import Image, ImageDraw
from pypdf import PdfWriter

from magazine.image_contrast import MIN_PRINT_CONTRAST_RATIO
from magazine.preflight import (
    A4_LANDSCAPE_POINTS,
    A5_POINTS,
    _effective_image_ppi,
    _raster_dimensions,
    inspect_package,
)


def test_cover_ppi_uses_the_rendered_monument_placement():
    assert round(_effective_image_ppi((1054, 1492), (250, 250)), 1) == 303.6


def test_raster_dimensions_support_png_and_jpeg(tmp_path: Path):
    png = tmp_path / "figure.png"
    jpg = tmp_path / "figure.jpg"
    Image.new("RGB", (900, 600), "white").save(png)
    Image.new("RGB", (1200, 800), "white").save(jpg)

    assert _raster_dimensions(png) == (900, 600)
    assert _raster_dimensions(jpg) == (1200, 800)


def _blank_pdf(path: Path, pagesize: tuple[float, float]) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=pagesize[0], height=pagesize[1])
    with path.open("wb") as handle:
        writer.write(handle)


def test_preflight_audits_curated_figure_resolution_geometry_and_rights(tmp_path: Path):
    reader = tmp_path / "reader.pdf"
    booklet = tmp_path / "booklet.pdf"
    figure = tmp_path / "figure.jpg"
    _blank_pdf(reader, A5_POINTS)
    _blank_pdf(booklet, A4_LANDSCAPE_POINTS)
    Image.new("RGB", (600, 400), "white").save(figure)

    result = inspect_package(
        reader,
        booklet,
        cover_art=None,
        source_rights=[],
        figure_placements=[
            {
                "figure_id": "evidence",
                "article_id": "article",
                "page": 1,
                "path": figure,
                "pixel_dimensions": (600, 400),
                "box_points": (40, 250, 180, 120),
                "caption": "Evidence.",
                "credit": "Source credit.",
                "rights_status": "private_reference",
            }
        ],
    )

    assert result["figures"][0]["effective_ppi"] == 240.0
    assert result["low_resolution_figures"] == [
        {"figure_id": "evidence", "effective_ppi": 240.0}
    ]
    assert result["figure_rights_blockers"] == [
        {"figure_id": "evidence", "status": "private_reference"}
    ]
    assert result["invalid_figure_boxes"] == []
    assert result["figure_collisions"] == []
    assert result["contrast_adjusted_figures"] == []
    assert result["unresolved_low_contrast_figures"] == []


def test_preflight_records_automatic_print_contrast_treatment(tmp_path: Path):
    reader = tmp_path / "reader.pdf"
    booklet = tmp_path / "booklet.pdf"
    figure = tmp_path / "faint-diagram.png"
    _blank_pdf(reader, A5_POINTS)
    _blank_pdf(booklet, A4_LANDSCAPE_POINTS)
    image = Image.new("RGB", (1200, 800), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 100, 1100, 700), outline="#efc9bc", width=5)
    draw.line((180, 400, 1020, 400), fill="#e6b09d", width=6)
    image.save(figure)

    result = inspect_package(
        reader,
        booklet,
        cover_art=None,
        source_rights=[],
        figure_placements=[
            {
                "figure_id": "faint-evidence",
                "article_id": "article",
                "page": 1,
                "path": figure,
                "pixel_dimensions": (1200, 800),
                "box_points": (40, 250, 180, 120),
                "caption": "Evidence.",
                "credit": "Source credit.",
                "rights_status": "author_owned",
            }
        ],
    )

    contrast = result["figures"][0]["print_contrast"]
    assert contrast["treatment"] == "contrast_strengthened"
    assert contrast["minimum_mark_contrast_ratio"] < MIN_PRINT_CONTRAST_RATIO
    assert (
        contrast["post_treatment_minimum_mark_contrast_ratio"]
        >= MIN_PRINT_CONTRAST_RATIO
    )
    assert result["contrast_adjusted_figures"][0]["figure_id"] == "faint-evidence"
    assert result["unresolved_low_contrast_figures"] == []
