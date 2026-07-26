from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .booklet import impose_a5_on_a4
from .errors import ValidationError
from .preflight import inspect_package
from .render_critic import inspect_render


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_release(
    reader_pdf: Path,
    destination: Path,
    manifest: dict[str, Any],
    fidelity_markdown: str,
    *,
    cover_art: Path | None = None,
    cover_art_size_points: tuple[float, float] | None = None,
    source_rights: list[dict[str, Any]] | None = None,
    figure_placements: list[Any] | tuple[Any, ...] | None = None,
    language: str = "en",
    toc: dict[str, int] | None = None,
    article_pages: dict[str, int] | None = None,
    editorial_pages: int | None = None,
    edition_id: str,
    recorded_review: dict[str, Any] | None = None,
) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    reader = destination / "reader.pdf"
    shutil.copyfile(reader_pdf, reader)
    booklet = impose_a5_on_a4(reader, destination / "home" / "booklet-a4.pdf")
    # The manifest is written as soon as the PDFs it describes exist, *before*
    # the render critic runs: the critic reads nothing from it (every fact it
    # judges arrives as an argument), and a crash or a critic failure anywhere
    # below must not leave fresh PDFs beside the previous build's manifest --
    # that pairing is what a release-time staleness check exists to catch, and
    # it should never be manufacturable by an interrupted build.
    edition_manifest = destination / "edition-manifest.json"
    edition_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    render_report, contact_sheets = inspect_render(
        reader,
        booklet,
        destination,
        language=language,
        toc=toc or {},
        article_pages=article_pages or {},
        editorial_pages=editorial_pages,
        edition_id=edition_id,
        recorded_review=recorded_review,
    )
    render_report_path = destination / "render-critic.json"
    render_report_path.write_text(
        json.dumps(render_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if render_report["result"] == "fail":
        codes = ", ".join(
            row["code"] for row in render_report["issues"] if row["severity"] == "error"
        )
        raise ValidationError(f"Render critic rejected {language} reader: {codes}")
    instructions = destination / "home" / "printing-instructions.md"
    instructions.write_text(_printing_instructions(language), encoding="utf-8")
    fidelity = destination / "fidelity.md"
    fidelity.write_text(fidelity_markdown, encoding="utf-8")
    studio = destination / "studio" / "README.md"
    studio.parent.mkdir(parents=True, exist_ok=True)
    studio.write_text(_studio_note(language), encoding="utf-8")
    preflight = destination / "preflight.json"
    preflight.write_text(
        json.dumps(
            inspect_package(
                reader,
                booklet,
                cover_art=cover_art,
                cover_art_size_points=cover_art_size_points,
                source_rights=source_rights or [],
                figure_placements=figure_placements or (),
                language=language,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    # Keep each language package self-contained. The primary English package may
    # have translated sibling directories beneath it, which must not leak into
    # its checksum inventory.
    files = sorted(
        [
            reader,
            booklet,
            instructions,
            fidelity,
            studio,
            preflight,
            edition_manifest,
            render_report_path,
            *contact_sheets,
        ],
        key=lambda path: path.relative_to(destination).as_posix(),
    )
    checksums = destination / "SHA256SUMS"
    checksums.write_text("".join(f"{sha256(path)}  {path.relative_to(destination).as_posix()}\n" for path in files), encoding="utf-8")
    return files + [checksums]


def _printing_instructions(language: str) -> str:
    if language.split("-", 1)[0] == "es":
        return (
            "# Impresión doméstica\n\nImprimir al 100 % en A4 horizontal, a doble cara y "
            "volteando por el borde corto. En una impresora de una sola cara, imprimir primero "
            "las páginas impares del PDF y después las pares en orden inverso. Doblar el bloque "
            "por la mitad y graparlo a caballete. Hacer primero una prueba para confirmar la "
            "orientación de alimentación de la impresora.\n"
        )
    return (
        "# Home printing\n\nPrint at 100% on A4 landscape, duplex, flipping on the short edge. "
        "On a simplex printer, print odd PDF pages first, then even PDF pages in reverse order. "
        "Fold the stack in half and saddle-staple. First run a test to confirm your printer's "
        "feed direction.\n"
    )


def _studio_note(language: str) -> str:
    if language.split("-", 1)[0] == "es":
        return (
            "# Entrega a imprenta pendiente\n\nEl PDF de lectura tiene formato A5, pero no es "
            "PDF/X. Antes de imprimir hay que seleccionar el perfil ICC de la imprenta, añadir "
            "el sangrado requerido, convertir a PDF/X-4 y superar la verificación de preimpresión.\n"
        )
    return (
        "# Studio handoff pending\n\nThe reader PDF is A5, but it is not PDF/X. Select a printer ICC profile, "
        "add bleed where artwork requires it, convert to PDF/X-4, and pass the printer's preflight before release.\n"
    )
