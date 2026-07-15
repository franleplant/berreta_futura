from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .catalog import render_sources
from .fidelity import fidelity_report
from .io import load_structured
from .manifest import Edition, load_edition
from .package import package_release
from .records import SourceRecord, load_records
from .render import render_a5


@dataclass(frozen=True)
class BuildResult:
    edition_id: str
    output_dir: Path
    reader_pdf: Path
    booklet_pdf: Path
    files: tuple[Path, ...]


class Magazine:
    """Deep module: capture, catalog, validate, and compile through one interface."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        config_path = self.root / "magazine.toml"
        self.config = tomllib.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
        paths = self.config.get("paths", {})
        self.sources_dir = self.root / paths.get("sources", "library/sources")
        self.editions_dir = self.root / paths.get("editions", "editions")
        self.output_dir = self.root / paths.get("output", "output")

    def capture(self, url: str, **metadata: Any) -> SourceRecord:
        """Normalize and store source metadata without performing network access."""
        candidate = SourceRecord.create(url, **metadata)
        for existing in load_records(self.sources_dir):
            if existing.canonical_url == candidate.canonical_url:
                return existing
        candidate.write(self.sources_dir)
        return candidate

    def write_sources(self, destination: Path | None = None) -> Path:
        path = destination or self.root / "sources.md"
        path.write_text(render_sources(load_records(self.sources_dir)), encoding="utf-8")
        return path

    def validate(self, edition_id: str) -> Edition:
        records = load_records(self.sources_dir)
        edition = load_edition(self.root, edition_id, {record.id for record in records})
        for article in edition.articles:
            fidelity_report(article.fidelity)
        return edition

    def build(self, edition_id: str) -> BuildResult:
        edition = self.validate(edition_id)
        destination = self.output_dir / edition.id
        working_pdf = self.output_dir / ".build" / f"{edition.id}-reader.pdf"
        render_a5(edition, working_pdf)
        reports = [(article, fidelity_report(article.fidelity)) for article in edition.articles]
        if reports:
            fidelity_md = "# Fidelity report\n\n" + "\n\n".join(
                report.as_markdown(article.title) for article, report in reports
            ) + "\n"
        else:
            fidelity_md = _section_fidelity_report(self.root, edition)
        source_records = {record.id: record for record in load_records(self.sources_dir)}
        declared_source_ids = edition.raw.get("sources", [])
        used_source_ids = sorted(
            set(declared_source_ids)
            | {source_id for article in edition.articles for source_id in article.source_ids}
        )
        build_manifest = {
            "schema_version": 1,
            "compiler": "magazine-compiler/0.1.0",
            "edition": edition.raw,
            "inputs": {
                "editorial": _file_entry(edition.editorial, self.root) if edition.editorial else None,
                "cover_art": _file_entry(edition.cover_art, self.root) if edition.cover_art else None,
                "fidelity_status": _optional_file_entry(
                    self.editions_dir / edition.id / "fidelity" / "source-edition-status.yaml",
                    self.root,
                ),
                "sections": [
                    {"kind": section.kind, **_file_entry(section.path, self.root)}
                    for section in edition.sections
                ],
                "articles": [
                    {
                        "id": article.id,
                        "manuscript": _file_entry(article.manuscript, self.root),
                        "fidelity": _file_entry(article.fidelity, self.root),
                    }
                    for article in edition.articles
                ],
                "sources": [
                    {
                        "id": source_id,
                        "canonical_url": source_records[source_id].canonical_url,
                        "content_hash": source_records[source_id].content_hash,
                        "record": _file_entry(self.sources_dir / source_id / "record.yaml", self.root),
                        "rights": source_records[source_id].rights,
                    }
                    for source_id in used_source_ids
                ],
            },
            "studio_release_ready": False,
            "studio_blocker": "PDF/X-4 conversion requires the selected printer ICC profile and preflight.",
        }
        files = package_release(
            working_pdf,
            destination,
            build_manifest,
            fidelity_md,
            cover_art=edition.cover_art,
            source_rights=[source_records[source_id].to_dict() for source_id in used_source_ids],
        )
        return BuildResult(edition.id, destination, destination / "reader.pdf", destination / "home" / "booklet-a4.pdf", tuple(files))


def _file_entry(path: Path, root: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _optional_file_entry(path: Path, root: Path) -> dict[str, str] | None:
    return _file_entry(path, root) if path.is_file() else None


def _section_fidelity_report(root: Path, edition: Edition) -> str:
    path = root / "editions" / edition.id / "fidelity" / "source-edition-status.yaml"
    if not path.is_file():
        return "# Fidelity report\n\nNo faithful source article is present in this edition.\n"
    status = load_structured(path)
    lines = [
        "# Fidelity report",
        "",
        f"- Source: `{status.get('source_id', 'unknown')}`",
        f"- Content mode: `{status.get('content_mode', 'unknown')}`",
        f"- Status: **{status.get('status', 'unknown')}**",
    ]
    blockers = status.get("blockers", [])
    if blockers:
        lines.extend(["", "## Blockers", "", *[f"- {item}" for item in blockers]])
    metrics = status.get("metrics", {})
    if metrics:
        lines.extend(["", "## Metrics", ""])
        lines.extend(f"- {key.replace('_', ' ').title()}: {value if value is not None else 'not yet measured'}" for key, value in metrics.items())
    if status.get("note"):
        lines.extend(["", status["note"]])
    return "\n".join(lines) + "\n"
