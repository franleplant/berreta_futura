from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .booklet import impose_a5_on_a4
from .preflight import inspect_package


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
    source_rights: list[dict[str, Any]] | None = None,
) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    reader = destination / "reader.pdf"
    shutil.copyfile(reader_pdf, reader)
    booklet = impose_a5_on_a4(reader, destination / "home" / "booklet-a4.pdf")
    instructions = destination / "home" / "printing-instructions.md"
    instructions.write_text(
        "# Home printing\n\nPrint at 100% on A4 landscape, duplex, flipping on the short edge. "
        "Fold the stack in half and saddle-staple. First test four pages to confirm your printer's duplex direction.\n",
        encoding="utf-8",
    )
    fidelity = destination / "fidelity.md"
    fidelity.write_text(fidelity_markdown, encoding="utf-8")
    studio = destination / "studio" / "README.md"
    studio.parent.mkdir(parents=True, exist_ok=True)
    studio.write_text(
        "# Studio handoff pending\n\nThe reader PDF is A5, but it is not PDF/X. Select a printer ICC profile, "
        "add bleed where artwork requires it, convert to PDF/X-4, and pass the printer's preflight before release.\n",
        encoding="utf-8",
    )
    preflight = destination / "preflight.json"
    preflight.write_text(
        json.dumps(
            inspect_package(reader, booklet, cover_art=cover_art, source_rights=source_rights or []),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    edition_manifest = destination / "edition-manifest.json"
    edition_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    files = sorted(path for path in destination.rglob("*") if path.is_file() and path.name != "SHA256SUMS")
    checksums = destination / "SHA256SUMS"
    checksums.write_text("".join(f"{sha256(path)}  {path.relative_to(destination).as_posix()}\n" for path in files), encoding="utf-8")
    return files + [checksums]
