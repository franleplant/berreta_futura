from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from .booklet import impose_a5_on_a4
from .errors import ValidationError
from .preflight import inspect_package
from .render_critic import inspect_render


RENDERED_TAIL_ARTS_KEY = "_rendered_tail_arts"


def _adopt_rendered_layout(manifest: dict[str, Any]) -> None:
    edition = manifest.get("edition")
    if not isinstance(edition, dict):
        return
    ledger = edition.pop(RENDERED_TAIL_ARTS_KEY, None)
    if ledger is None:
        return
    layout = manifest.setdefault("layout", {})
    layout["tail_arts"] = ledger


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
    *,
    cover_art: Path | None = None,
    cover_art_size_points: tuple[float, float] | None = None,
    figure_placements: list[Any] | tuple[Any, ...] | None = None,
    language: str = "en",
    toc: dict[str, int] | None = None,
    article_pages: dict[str, int] | None = None,
    editorial_pages: int | None = None,
    edition_id: str,
    recorded_review: dict[str, Any] | None = None,
) -> list[Path]:
    _adopt_rendered_layout(manifest)
    destination.mkdir(parents=True, exist_ok=True)
    reader = destination / "reader.pdf"
    shutil.copyfile(reader_pdf, reader)

    booklet = impose_a5_on_a4(reader, destination / "booklet-a4.pdf")
    interior_booklet = impose_a5_on_a4(
        reader, destination / "booklet-a4-interior.pdf", section="interior"
    )
    cover_booklet = impose_a5_on_a4(reader, destination / "booklet-a4-cover.pdf", section="cover")

    edition_manifest = destination / "edition-manifest.json"
    edition_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    render_report, contact_sheets = inspect_render(
        reader,
        booklet,
        destination,
        interior_booklet_pdf=interior_booklet,
        cover_booklet_pdf=cover_booklet,
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
    instructions = destination / "booklet-a4-printing-instructions.md"
    instructions.write_text(
        _printing_instructions(
            language,
            reader_page_count=len(PdfReader(str(reader)).pages),
            all_in_one_sheets=len(PdfReader(str(booklet)).pages) // 2,
            interior_sheets=len(PdfReader(str(interior_booklet)).pages) // 2,
            cover_sheets=len(PdfReader(str(cover_booklet)).pages),
        ),
        encoding="utf-8",
    )
    studio = destination / "studio" / "README.md"
    studio.parent.mkdir(parents=True, exist_ok=True)
    studio.write_text(_studio_note(language), encoding="utf-8")
    preflight = destination / "preflight.json"
    preflight.write_text(
        json.dumps(
            inspect_package(
                reader,
                booklet,
                interior_booklet_pdf=interior_booklet,
                cover_booklet_pdf=cover_booklet,
                cover_art=cover_art,
                cover_art_size_points=cover_art_size_points,
                figure_placements=figure_placements or (),
                language=language,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    files = sorted(
        [
            reader,
            booklet,
            interior_booklet,
            cover_booklet,
            instructions,
            studio,
            preflight,
            edition_manifest,
            render_report_path,
            *contact_sheets,
        ],
        key=lambda path: path.relative_to(destination).as_posix(),
    )
    checksums = destination / "SHA256SUMS"
    checksums.write_text(
        "".join(f"{sha256(path)}  {path.relative_to(destination).as_posix()}\n" for path in files),
        encoding="utf-8",
    )
    return files + [checksums]


def _printing_instructions(
    language: str,
    *,
    reader_page_count: int,
    all_in_one_sheets: int,
    interior_sheets: int,
    cover_sheets: int,
) -> str:
    first_interior = 3
    last_interior = reader_page_count - 2
    if language.split("-", 1)[0] == "es":
        return (
            "# Impresión doméstica\n\nImprimir al 100 % en A4 horizontal, a doble cara y "
            "volteando por el borde corto. En una impresora de una sola cara, imprimir primero "
            "las páginas impares del PDF y después las pares en orden inverso. Doblar el bloque "
            "por la mitad y graparlo a caballete. Hacer primero una prueba para confirmar la "
            "orientación de alimentación de la impresora.\n\n"
            "Hay tres imposiciones de la misma revista. Imprimir el cuadernillo completo o bien "
            "la pareja de interior y cubierta, no ambas cosas.\n\n"
            "## booklet-a4.pdf — todo en uno\n\n"
            f"La revista entera, cubierta incluida: {all_in_one_sheets} hojas A4 en un solo papel. "
            "Es la opción para imprimir con un único gramaje y sin nada que intercalar.\n\n"
            "## booklet-a4-interior.pdf — interior en papel de texto\n\n"
            f"Las páginas {first_interior} a {last_interior} del PDF de lectura: la revista sin la "
            "cubierta y sin las páginas en blanco de su cara interior. Son "
            f"{interior_sheets} hojas A4 en papel corriente de 80 a 100 g/m².\n\n"
            "## booklet-a4-cover.pdf — cubierta en papel más grueso\n\n"
            f"{cover_sheets} hoja A4, a una sola cara: la contracubierta junto a la cubierta. "
            "El PDF es esa única página — no hay cara interior que imprimir. Usar papel más "
            "grueso —de 160 a 250 g/m², que dobla bien— y dejar secar la tinta antes de doblar.\n\n"
            "## Montaje de la impresión en dos papeles\n\n"
            "Doblar por separado el bloque interior y la hoja de cubierta, encajar el interior "
            "dentro de la cubierta doblada y grapar a caballete atravesando ambos por el lomo.\n"
        )
    return (
        "# Home printing\n\nPrint at 100% on A4 landscape, duplex, flipping on the short edge. "
        "On a simplex printer, print odd PDF pages first, then even PDF pages in reverse order. "
        "Fold the stack in half and saddle-staple. First run a test to confirm your printer's "
        "feed direction.\n\n"
        "Three impositions of the same magazine are included. Print either the all-in-one "
        "booklet or the interior-and-cover pair, not both.\n\n"
        "## booklet-a4.pdf — all in one\n\n"
        f"The whole magazine, cover included: {all_in_one_sheets} A4 sheets on one stock. This is "
        "the single-stock print, with nothing to collate.\n\n"
        "## booklet-a4-interior.pdf — interior on text stock\n\n"
        f"Reader pages {first_interior} to {last_interior}: the magazine without the cover and "
        f"without the blank inside covers. {interior_sheets} A4 sheets on ordinary 80-100 gsm "
        "text stock.\n\n"
        "## booklet-a4-cover.pdf — cover wrap on heavier stock\n\n"
        f"{cover_sheets} A4 sheet, printed single-sided: the back cover beside the front cover. "
        "The PDF is that one page — there is no inside face to print. "
        "Use heavier stock — 160-250 gsm folds well — and let the ink dry before folding.\n\n"
        "## Assembling the two-stock print\n\n"
        "Fold the interior stack and the cover sheet separately, nest the interior inside the "
        "folded cover, then saddle-staple through the spine of both.\n"
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
