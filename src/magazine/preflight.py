from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader


A5_POINTS = (419.5276, 595.2756)
A4_LANDSCAPE_POINTS = (841.8898, 595.2756)


def _page_size(page) -> tuple[float, float]:
    return float(page.mediabox.width), float(page.mediabox.height)


def _near(actual: tuple[float, float], expected: tuple[float, float], tolerance: float = 0.75) -> bool:
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
    """Compatibility alias for callers that previously inspected cover PNGs."""
    return _raster_dimensions(path)


def _effective_image_ppi(
    pixel_dimensions: tuple[int, int],
    placement_points: tuple[float, float],
) -> float:
    return min(
        pixel_dimensions[0] / (placement_points[0] / 72),
        pixel_dimensions[1] / (placement_points[1] / 72),
    )


def inspect_package(
    reader_pdf: Path,
    booklet_pdf: Path,
    *,
    cover_art: Path | None,
    cover_art_size_points: tuple[float, float] | None = None,
    source_rights: list[dict[str, Any]],
    figure_placements: list[Any] | tuple[Any, ...] | None = None,
    language: str = "en",
) -> dict[str, Any]:
    reader = PdfReader(str(reader_pdf))
    booklet = PdfReader(str(booklet_pdf))
    reader_sizes = [_page_size(page) for page in reader.pages]
    booklet_sizes = [_page_size(page) for page in booklet.pages]
    cover_dimensions = _raster_dimensions(cover_art)
    cover_info: dict[str, Any] = {"path": str(cover_art) if cover_art else None, "pixel_dimensions": cover_dimensions}
    if cover_dimensions:
        effective_at_a5 = _effective_image_ppi(cover_dimensions, A5_POINTS)
        placement = cover_art_size_points or A5_POINTS
        effective_at_placement = _effective_image_ppi(cover_dimensions, placement)
        cover_info["effective_ppi_at_a5"] = round(effective_at_a5, 1)
        cover_info["placement_points"] = [round(value, 3) for value in placement]
        cover_info["effective_ppi_at_placement"] = round(effective_at_placement, 1)
        cover_info["studio_300ppi_target_met"] = effective_at_placement >= 300

    rights_blockers = [
        {"source_id": row["id"], "status": row.get("rights", {}).get("status", "unknown")}
        for row in source_rights
        if row.get("rights", {}).get("public_reprint_allowed") is not True
    ]
    figure_rows: list[dict[str, Any]] = []
    figure_rights_blockers: list[dict[str, Any]] = []
    low_resolution_figures: list[dict[str, Any]] = []
    for placement in figure_placements or ():
        def value(name: str, default=None):
            if isinstance(placement, dict):
                return placement.get(name, default)
            return getattr(placement, name, default)

        path = Path(value("path"))
        dimensions = value("pixel_dimensions") or _raster_dimensions(path)
        box = tuple(value("box_points") or ())
        placement_size = tuple(box[-2:]) if len(box) == 4 else tuple(box)
        ppi = value("effective_ppi")
        if ppi is None and dimensions and len(placement_size) == 2:
            ppi = _effective_image_ppi(tuple(dimensions), tuple(placement_size))
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
            "rights_status": str(value("rights_status", "unknown")),
        }
        figure_rows.append(row)
        if row["effective_ppi"] is None or row["effective_ppi"] < 300:
            low_resolution_figures.append(
                {"figure_id": row["figure_id"], "effective_ppi": row["effective_ppi"]}
            )
        if row["rights_status"] not in {"licensed", "permission", "public_domain", "author_owned"}:
            figure_rights_blockers.append(
                {"figure_id": row["figure_id"], "status": row["rights_status"]}
            )
    invalid_figure_boxes: list[dict[str, Any]] = []
    figure_collisions: list[dict[str, Any]] = []
    by_page: dict[int, list[dict[str, Any]]] = {}
    for row in figure_rows:
        box = row["box_points"]
        if len(box) != 4:
            invalid_figure_boxes.append({"figure_id": row["figure_id"], "box_points": box})
            continue
        x, y, width, height = box
        if (
            row["page"] < 1
            or row["page"] > len(reader.pages)
            or width <= 0
            or height <= 0
            or x < 0
            or y < 0
            or x + width > A5_POINTS[0] + .75
            or y + height > A5_POINTS[1] + .75
        ):
            invalid_figure_boxes.append({"figure_id": row["figure_id"], "box_points": box})
            continue
        for previous in by_page.setdefault(row["page"], []):
            left = max(x, previous["box_points"][0])
            bottom = max(y, previous["box_points"][1])
            right = min(x + width, previous["box_points"][0] + previous["box_points"][2])
            top = min(y + height, previous["box_points"][1] + previous["box_points"][3])
            if right > left and top > bottom:
                figure_collisions.append(
                    {"figure_ids": [previous["figure_id"], row["figure_id"]], "page": row["page"]}
                )
        by_page[row["page"]].append(row)
    messages = _MESSAGES.get(language.split("-", 1)[0], _MESSAGES["en"])
    studio_blockers = [messages["pdfx"], messages["bleed"]]
    if cover_info.get("studio_300ppi_target_met") is False:
        studio_blockers.append(messages["cover_resolution"])
    if low_resolution_figures:
        studio_blockers.append(messages["figure_resolution"])
    if invalid_figure_boxes or figure_collisions:
        studio_blockers.append(messages["figure_geometry"])
    if rights_blockers:
        studio_blockers.append(messages["rights"])
    if figure_rights_blockers:
        studio_blockers.append(messages["figure_rights"])

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
            "all_pages_a4_landscape": all(_near(size, A4_LANDSCAPE_POINTS) for size in booklet_sizes),
            "encrypted": booklet.is_encrypted,
            "print_scale": "100%",
            "duplex_flip": "short edge",
        },
        "cover_art": cover_info,
        "figures": figure_rows,
        "low_resolution_figures": low_resolution_figures,
        "figure_rights_blockers": figure_rights_blockers,
        "invalid_figure_boxes": invalid_figure_boxes,
        "figure_collisions": figure_collisions,
        "rights_blockers": rights_blockers,
        "studio": {"ready": not studio_blockers, "blockers": studio_blockers},
    }


_MESSAGES = {
    "en": {
        "pdfx": "PDF/X-4 conversion and printer output intent are not configured.",
        "bleed": "Trim bleed is not configured for the selected printer.",
        "cover_resolution": "Cover artwork is below the 300 ppi studio target at its rendered placement.",
        "figure_resolution": "One or more curated figures are below 300 ppi at their rendered placement.",
        "figure_geometry": "One or more curated figure placements are invalid or collide.",
        "rights": "One or more declared sources are not cleared for public reprint.",
        "figure_rights": "One or more curated figures are not cleared for public reprint.",
    },
    "es": {
        "pdfx": "No están configurados la conversión a PDF/X-4 ni el propósito de salida de la imprenta.",
        "bleed": "No está configurado el sangrado de corte para la imprenta seleccionada.",
        "cover_resolution": "La ilustración de cubierta no alcanza el objetivo de 300 ppp en su tamaño de reproducción.",
        "figure_resolution": "Una o más figuras seleccionadas no alcanzan 300 ppp en su tamaño de reproducción.",
        "figure_geometry": "Una o más ubicaciones de figuras seleccionadas son inválidas o se superponen.",
        "rights": "Una o más fuentes declaradas no están autorizadas para su reedición pública.",
        "figure_rights": "Una o más figuras seleccionadas no están autorizadas para su reedición pública.",
    },
}
