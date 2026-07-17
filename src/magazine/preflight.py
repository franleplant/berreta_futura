from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from pypdf import PdfReader


A5_POINTS = (419.5276, 595.2756)
A4_LANDSCAPE_POINTS = (841.8898, 595.2756)


def _page_size(page) -> tuple[float, float]:
    return float(page.mediabox.width), float(page.mediabox.height)


def _near(actual: tuple[float, float], expected: tuple[float, float], tolerance: float = 0.75) -> bool:
    return all(abs(left - right) <= tolerance for left, right in zip(actual, expected, strict=True))


def _png_dimensions(path: Path | None) -> tuple[int, int] | None:
    if path is None or path.suffix.lower() != ".png" or not path.is_file():
        return None
    data = path.read_bytes()[:24]
    if len(data) != 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", data[16:24])


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
    language: str = "en",
) -> dict[str, Any]:
    reader = PdfReader(str(reader_pdf))
    booklet = PdfReader(str(booklet_pdf))
    reader_sizes = [_page_size(page) for page in reader.pages]
    booklet_sizes = [_page_size(page) for page in booklet.pages]
    cover_dimensions = _png_dimensions(cover_art)
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
    messages = _MESSAGES.get(language.split("-", 1)[0], _MESSAGES["en"])
    studio_blockers = [messages["pdfx"], messages["bleed"]]
    if cover_info.get("studio_300ppi_target_met") is False:
        studio_blockers.append(messages["cover_resolution"])
    if rights_blockers:
        studio_blockers.append(messages["rights"])

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
        "rights_blockers": rights_blockers,
        "studio": {"ready": not studio_blockers, "blockers": studio_blockers},
    }


_MESSAGES = {
    "en": {
        "pdfx": "PDF/X-4 conversion and printer output intent are not configured.",
        "bleed": "Trim bleed is not configured for the selected printer.",
        "cover_resolution": "Cover artwork is below the 300 ppi studio target at its rendered placement.",
        "rights": "One or more declared sources are not cleared for public reprint.",
    },
    "es": {
        "pdfx": "No están configurados la conversión a PDF/X-4 ni el propósito de salida de la imprenta.",
        "bleed": "No está configurado el sangrado de corte para la imprenta seleccionada.",
        "cover_resolution": "La ilustración de cubierta no alcanza el objetivo de 300 ppp en su tamaño de reproducción.",
        "rights": "Una o más fuentes declaradas no están autorizadas para su reedición pública.",
    },
}
