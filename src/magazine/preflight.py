from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader

from .booklet import A4_LANDSCAPE_POINTS, section_reader_pages
from .image_contrast import prepare_print_image


A5_POINTS = (419.5276, 595.2756)

__all__ = ["A4_LANDSCAPE_POINTS", "A5_POINTS", "inspect_package"]


def _page_size(page) -> tuple[float, float]:
    return float(page.mediabox.width), float(page.mediabox.height)


def _near(
    actual: tuple[float, float], expected: tuple[float, float], tolerance: float = 0.75
) -> bool:
    return all(abs(left - right) <= tolerance for left, right in zip(actual, expected, strict=True))


def _raster_dimensions(path: Path | None) -> tuple[int, int] | None:
    if path is None or path.suffix.lower() not in {".png", ".jpg", ".jpeg"} or not path.is_file():
        return None
    try:
        from PIL import Image

        with Image.open(path) as image:
            return int(image.width), int(image.height)
    except (OSError, ValueError):
        return None


def _png_dimensions(path: Path | None) -> tuple[int, int] | None:
    return _raster_dimensions(path)


def _effective_image_ppi(
    pixel_dimensions: tuple[int, int],
    placement_points: tuple[float, float],
) -> float:
    return min(
        pixel_dimensions[0] / (placement_points[0] / 72),
        pixel_dimensions[1] / (placement_points[1] / 72),
    )


def _booklet_section_facts(
    document: PdfReader, reader: PdfReader, section: str, *, stock: str
) -> dict[str, Any]:
    sizes = [_page_size(page) for page in document.pages]
    page_count = len(reader.pages)
    expected = section_reader_pages(page_count, section) if page_count >= 4 else ()
    single_sided = section == "cover"
    return {
        "reader_pages": list(expected),
        "sheet_sides": len(document.pages),
        "sheets": len(document.pages) if single_sided else len(document.pages) // 2,
        "expected_sheets": 1 if single_sided else (len(expected) + (-len(expected) % 4)) // 4,
        "all_pages_a4_landscape": all(_near(size, A4_LANDSCAPE_POINTS) for size in sizes),
        "encrypted": document.is_encrypted,
        "print_scale": "100%",
        "duplex_flip": "none (single-sided)" if single_sided else "short edge",
        "stock": stock,
    }


def _cover_facts(cover_art, cover_art_size_points):
    cover_dimensions = _raster_dimensions(cover_art)
    cover_info: dict[str, Any] = {
        "path": str(cover_art) if cover_art else None,
        "pixel_dimensions": cover_dimensions,
    }
    if cover_dimensions:
        effective_at_a5 = _effective_image_ppi(cover_dimensions, A5_POINTS)
        placement = cover_art_size_points or A5_POINTS
        effective_at_placement = _effective_image_ppi(cover_dimensions, placement)
        cover_info["effective_ppi_at_a5"] = round(effective_at_a5, 1)
        cover_info["placement_points"] = [round(value, 3) for value in placement]
        cover_info["effective_ppi_at_placement"] = round(effective_at_placement, 1)
        cover_info["studio_300ppi_target_met"] = effective_at_placement >= 300
    return cover_info


def _placement_value(placement, name: str, default=None):
    if isinstance(placement, dict):
        return placement.get(name, default)
    return getattr(placement, name, default)


def _figure_row(placement) -> tuple[dict[str, Any], Any]:
    def value(name: str, default=None):
        return _placement_value(placement, name, default)

    path = Path(value("path"))
    dimensions = value("pixel_dimensions") or _raster_dimensions(path)
    box = tuple(value("box_points") or ())
    placement_size = tuple(box[-2:]) if len(box) == 4 else tuple(box)
    ppi = value("effective_ppi")
    if ppi is None and dimensions and len(placement_size) == 2:
        ppi = _effective_image_ppi(tuple(dimensions), tuple(placement_size))
    contrast = None
    prepared = None
    if dimensions:
        prepared = prepare_print_image(path)
        contrast = {
            **prepared.before.to_dict(),
            "treatment": "contrast_strengthened" if prepared.adjusted else "none",
            "post_treatment_minimum_mark_contrast_ratio": (
                prepared.after.minimum_mark_contrast_ratio
            ),
        }
    row = {
        "figure_id": str(value("figure_id", "")),
        "article_id": str(value("article_id", "")),
        "page": int(value("page", 0)),
        "path": str(path),
        "pixel_dimensions": list(dimensions) if dimensions else None,
        "box_points": [round(float(item), 3) for item in box],
        "effective_ppi": round(float(ppi), 1) if ppi is not None else None,
        "caption": str(value("caption", "")),
        "credit": str(value("credit", "")),
        "print_contrast": contrast,
    }
    return row, prepared


def _figure_facts(figure_placements):
    figure_rows: list[dict[str, Any]] = []
    low_resolution: list[dict[str, Any]] = []
    contrast_adjusted: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for placement in figure_placements or ():
        row, prepared = _figure_row(placement)
        contrast = row["print_contrast"]
        figure_rows.append(row)
        if row["effective_ppi"] is None or row["effective_ppi"] < 300:
            low_resolution.append(
                {"figure_id": row["figure_id"], "effective_ppi": row["effective_ppi"]}
            )
        if contrast and contrast["treatment"] == "contrast_strengthened":
            contrast_adjusted.append(
                {
                    "figure_id": row["figure_id"],
                    "minimum_mark_contrast_ratio": contrast["minimum_mark_contrast_ratio"],
                    "post_treatment_minimum_mark_contrast_ratio": (
                        contrast["post_treatment_minimum_mark_contrast_ratio"]
                    ),
                }
            )
        if contrast and prepared.after.needs_treatment:
            unresolved.append(
                {
                    "figure_id": row["figure_id"],
                    "post_treatment_minimum_mark_contrast_ratio": (
                        contrast["post_treatment_minimum_mark_contrast_ratio"]
                    ),
                }
            )
    return figure_rows, low_resolution, contrast_adjusted, unresolved


def _box_invalid(row, page_count: int) -> bool:
    x, y, width, height = row["box_points"]
    return (
        row["page"] < 1
        or row["page"] > page_count
        or width <= 0
        or height <= 0
        or x < 0
        or y < 0
        or x + width > A5_POINTS[0] + 0.75
        or y + height > A5_POINTS[1] + 0.75
    )


def _figure_geometry(figure_rows, page_count: int):
    invalid: list[dict[str, Any]] = []
    collisions: list[dict[str, Any]] = []
    by_page: dict[int, list[dict[str, Any]]] = {}
    for row in figure_rows:
        box = row["box_points"]
        if len(box) != 4 or _box_invalid(row, page_count):
            invalid.append({"figure_id": row["figure_id"], "box_points": box})
            continue
        x, y, width, height = box
        for previous in by_page.setdefault(row["page"], []):
            left = max(x, previous["box_points"][0])
            bottom = max(y, previous["box_points"][1])
            right = min(x + width, previous["box_points"][0] + previous["box_points"][2])
            top = min(y + height, previous["box_points"][1] + previous["box_points"][3])
            if right > left and top > bottom:
                collisions.append(
                    {"figure_ids": [previous["figure_id"], row["figure_id"]], "page": row["page"]}
                )
        by_page[row["page"]].append(row)
    return invalid, collisions


def inspect_package(
    reader_pdf: Path,
    booklet_pdf: Path,
    *,
    interior_booklet_pdf: Path,
    cover_booklet_pdf: Path,
    cover_art: Path | None,
    cover_art_size_points: tuple[float, float] | None = None,
    figure_placements: list[Any] | tuple[Any, ...] | None = None,
    language: str = "en",
) -> dict[str, Any]:
    reader = PdfReader(str(reader_pdf))
    booklet = PdfReader(str(booklet_pdf))
    interior_booklet = PdfReader(str(interior_booklet_pdf))
    cover_booklet = PdfReader(str(cover_booklet_pdf))
    reader_sizes = [_page_size(page) for page in reader.pages]
    booklet_sizes = [_page_size(page) for page in booklet.pages]
    cover_info = _cover_facts(cover_art, cover_art_size_points)
    (
        figure_rows,
        low_resolution_figures,
        contrast_adjusted_figures,
        unresolved_low_contrast_figures,
    ) = _figure_facts(figure_placements)
    invalid_figure_boxes, figure_collisions = _figure_geometry(figure_rows, len(reader.pages))
    messages = _MESSAGES.get(language.split("-", 1)[0], _MESSAGES["en"])
    studio_blockers = [messages["pdfx"], messages["bleed"]]
    if cover_info.get("studio_300ppi_target_met") is False:
        studio_blockers.append(messages["cover_resolution"])
    if low_resolution_figures:
        studio_blockers.append(messages["figure_resolution"])
    if invalid_figure_boxes or figure_collisions:
        studio_blockers.append(messages["figure_geometry"])
    if unresolved_low_contrast_figures:
        studio_blockers.append(messages["figure_contrast"])
    return {
        "schema_version": 1,
        "result": "home_ready_studio_blocked" if studio_blockers else "ready",
        "reader": {
            "page_count": len(reader.pages),
            "page_count_multiple_of_four": len(reader.pages) % 4 == 0,
            "all_pages_a5": all(_near(size, A5_POINTS) for size in reader_sizes),
            "encrypted": reader.is_encrypted,
        },
        "home_booklet": {
            "sheet_sides": len(booklet.pages),
            "sheets": len(booklet.pages) // 2,
            "all_pages_a4_landscape": all(
                _near(size, A4_LANDSCAPE_POINTS) for size in booklet_sizes
            ),
            "encrypted": booklet.is_encrypted,
            "print_scale": "100%",
            "duplex_flip": "short edge",
        },
        "home_booklet_interior": _booklet_section_facts(
            interior_booklet, reader, "interior", stock="text"
        ),
        "home_booklet_cover": _booklet_section_facts(cover_booklet, reader, "cover", stock="cover"),
        "cover_art": cover_info,
        "figures": figure_rows,
        "low_resolution_figures": low_resolution_figures,
        "contrast_adjusted_figures": contrast_adjusted_figures,
        "unresolved_low_contrast_figures": unresolved_low_contrast_figures,
        "invalid_figure_boxes": invalid_figure_boxes,
        "figure_collisions": figure_collisions,
        "studio": {"ready": not studio_blockers, "blockers": studio_blockers},
    }


_MESSAGES = {
    "en": {
        "pdfx": "PDF/X-4 conversion and printer output intent are not configured.",
        "bleed": "Trim bleed is not configured for the selected printer.",
        "cover_resolution": "Cover artwork is below the 300 ppi studio target at its rendered placement.",
        "figure_resolution": "One or more curated figures are below 300 ppi at their rendered placement.",
        "figure_geometry": "One or more curated figure placements are invalid or collide.",
        "figure_contrast": "One or more curated figures remain too faint after print-contrast treatment.",
    },
    "es": {
        "pdfx": "No están configurados la conversión a PDF/X-4 ni el propósito de salida de la imprenta.",
        "bleed": "No está configurado el sangrado de corte para la imprenta seleccionada.",
        "cover_resolution": "La ilustración de cubierta no alcanza el objetivo de 300 ppp en su tamaño de reproducción.",
        "figure_resolution": "Una o más figuras seleccionadas no alcanzan 300 ppp en su tamaño de reproducción.",
        "figure_geometry": "Una o más ubicaciones de figuras seleccionadas son inválidas o se superponen.",
        "figure_contrast": "Una o más figuras seleccionadas siguen siendo demasiado tenues después del ajuste de contraste para impresión.",
    },
}
