from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

from .capture import archive_snapshot, index_existing_captures, verify_snapshots
from .catalog import render_sources
from .cover import CoverArtifact, CoverCompiler, replace_outer_pages
from .errors import ValidationError
from .fidelity import fidelity_report
from .io import load_structured
from .manifest import Edition, load_edition, load_translation
from .media_curator import curate_source, verify_source_curation
from .package import package_release
from .records import SourceRecord, load_records
from .release import (
    ReleaseState,
    ReleaseTransition,
    finalize_release,
    plan_release,
    sync_release_state,
)
from .render import render_a5
from .render_review import (
    create_render_review,
    load_render_review,
    require_approved_reports,
    visual_review_status,
    write_render_review,
)


@dataclass(frozen=True)
class LanguageBuildResult:
    language: str
    output_dir: Path
    reader_pdf: Path
    booklet_pdf: Path
    files: tuple[Path, ...]


@dataclass(frozen=True)
class BuildResult:
    edition_id: str
    output_dir: Path
    reader_pdf: Path
    booklet_pdf: Path
    files: tuple[Path, ...]
    languages: tuple[LanguageBuildResult, ...]


class Magazine:
    """Deep module: capture, catalog, validate, and compile through one interface."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        config_path = self.root / "magazine.toml"
        self.config = tomllib.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
        paths = self.config.get("paths", {})
        publication = self.config.get("publication", {})
        self.publication_name = str(publication.get("name") or "Magazine").strip()
        self.primary_language = str(publication.get("language") or "en").strip()
        render = self.config.get("render", {})
        self.render_design = str(render.get("design") or "monument").strip()
        configured_languages = publication.get("languages", [self.primary_language])
        if not isinstance(configured_languages, list) or not configured_languages:
            raise ValidationError("publication.languages must be a non-empty list")
        self.languages = tuple(dict.fromkeys(str(item).strip() for item in configured_languages))
        if self.primary_language not in self.languages:
            raise ValidationError("publication.languages must include publication.language")
        self.sources_dir = self.root / paths.get("sources", "library/sources")
        self.editions_dir = self.root / paths.get("editions", "editions")
        self.output_dir = self.root / paths.get("output", "output")
        self.release_state_path = self.root / paths.get("release_state", "library/release-state.yaml")

    def capture(
        self,
        url: str,
        *,
        snapshot: Path,
        capture_method: str = "caller_supplied",
        **metadata: Any,
    ) -> SourceRecord:
        """Archive raw evidence, then store and queue its normalized source record."""
        candidate = SourceRecord.create(url, **metadata)
        for existing in load_records(self.sources_dir):
            if existing.canonical_url == candidate.canonical_url:
                previous_captures = {
                    str(row.get("id")) for row in existing.raw_captures if row.get("id")
                }
                existing = archive_snapshot(
                    existing, self.sources_dir, snapshot, method=capture_method,
                    captured_at=candidate.captured_at,
                )
                added = {
                    str(row.get("id")) for row in existing.raw_captures if row.get("id")
                } - previous_captures
                existing, _ = curate_source(
                    existing, self.sources_dir, refresh_capture_ids=added
                )
                existing.write(self.sources_dir)
                self.sync_release_queue()
                return existing
        candidate = archive_snapshot(
            candidate, self.sources_dir, snapshot, method=capture_method
        )
        candidate, _ = curate_source(
            candidate,
            self.sources_dir,
            refresh_capture_ids={str(row["id"]) for row in candidate.raw_captures},
        )
        candidate.write(self.sources_dir)
        self.sync_release_queue()
        return candidate

    def write_sources(self, destination: Path | None = None) -> Path:
        path = destination or self.root / "sources.md"
        records = load_records(self.sources_dir)
        release_state = self.sync_release_queue(records)
        path.write_text(render_sources(records, release_state), encoding="utf-8")
        return path

    def index_media(self) -> tuple[Path, ...]:
        """Regenerate inventories and automatic curation for committed captures."""

        records = load_records(self.sources_dir)
        paths = list(index_existing_captures(records, self.sources_dir))
        for record in records:
            curated, plans = curate_source(record, self.sources_dir)
            if curated != record:
                curated.write(self.sources_dir)
            paths.extend(plans)
        return tuple(paths)

    def sync_release_queue(self, records: list[SourceRecord] | None = None) -> ReleaseState:
        current = records if records is not None else load_records(self.sources_dir)
        for record in current:
            verify_snapshots(record, self.sources_dir)
        return sync_release_state(
            self.release_state_path,
            {record.id for record in current},
            default_open_id="001-the-work-left-to-us",
        )

    def validate(self, edition_id: str) -> Edition:
        return self._validate_languages(edition_id)[self.primary_language]

    def _validate_languages(self, edition_id: str) -> dict[str, Edition]:
        records = load_records(self.sources_dir)
        for record in records:
            verify_snapshots(record, self.sources_dir)
            verify_source_curation(record, self.sources_dir)
        _require_media_triage(records)
        edition = load_edition(
            self.root,
            edition_id,
            {record.id for record in records},
            publication_name=self.publication_name,
            source_records={record.id: record for record in records},
        )
        if edition.language != self.primary_language:
            raise ValidationError(
                f"Edition language {edition.language!r} does not match publication.language "
                f"{self.primary_language!r}"
            )
        for article in edition.articles:
            ledger_mode = str(load_structured(article.fidelity).get("content_mode", "faithful_edit"))
            if ledger_mode != article.content_mode:
                raise ValidationError(
                    f"Article {article.id} content_mode {article.content_mode!r} does not match "
                    f"its fidelity ledger {ledger_mode!r}"
                )
            fidelity_report(article.fidelity, source_author=article.author)
        editions = {edition.language: edition}
        for language in self.languages:
            if language == edition.language:
                continue
            editions[language] = load_translation(self.root, edition, language)
        return editions

    def _load_cover_languages(
        self,
        edition_id: str,
        languages: Iterable[str] | None = None,
    ) -> dict[str, Edition]:
        """Load only the localized edition data needed by a cover proof."""

        if isinstance(languages, str):
            requested = (languages,)
        else:
            requested = tuple(dict.fromkeys(languages or self.languages))
        if not requested:
            raise ValidationError("Cover proof requires at least one language")
        unsupported = sorted(set(requested) - set(self.languages))
        if unsupported:
            raise ValidationError(
                f"Cover proof languages are not configured: {', '.join(unsupported)}"
            )

        records = load_records(self.sources_dir)
        record_map = {record.id: record for record in records}
        edition = load_edition(
            self.root,
            edition_id,
            set(record_map),
            publication_name=self.publication_name,
            source_records=record_map,
        )
        if edition.language != self.primary_language:
            raise ValidationError(
                f"Edition language {edition.language!r} does not match publication.language "
                f"{self.primary_language!r}"
            )

        editions: dict[str, Edition] = {}
        for language in requested:
            editions[language] = (
                edition
                if language == edition.language
                else load_translation(self.root, edition, language)
            )
        return editions

    def cover_proof(
        self,
        edition_id: str,
        *,
        languages: Iterable[str] | None = None,
        reference: Path | None = None,
        check: bool = False,
    ) -> tuple[CoverArtifact, ...]:
        """Compile fast browser/PDF cover proofs without typesetting interiors."""

        editions = self._load_cover_languages(edition_id, languages)
        compiler = CoverCompiler(self.root)
        artifacts: list[CoverArtifact] = []
        for language, edition in editions.items():
            approved_reference = reference or (
                self.root
                / "design"
                / "covers"
                / "canto-vivo"
                / "references"
                / f"{language}.png"
            )
            artifacts.append(
                compiler.compile(
                    edition,
                    self.output_dir / edition_id / "cover-proof" / language,
                    reference=approved_reference,
                    check=check,
                )
            )
        return tuple(artifacts)

    def back_cover_proof(
        self,
        edition_id: str,
        *,
        languages: Iterable[str] | None = None,
        reference: Path | None = None,
        check: bool = False,
    ) -> tuple[CoverArtifact, ...]:
        """Compile fast localized Signal fold back-cover proofs."""

        editions = self._load_cover_languages(edition_id, languages)
        compiler = CoverCompiler(self.root)
        artifacts: list[CoverArtifact] = []
        for language, edition in editions.items():
            approved_reference = reference or (
                self.root
                / "design"
                / "covers"
                / "canto-vivo"
                / "back-references"
                / f"{language}.png"
            )
            artifacts.append(
                compiler.compile_back(
                    edition,
                    self.output_dir / edition_id / "back-cover-proof" / language,
                    reference=approved_reference,
                    check=check,
                )
            )
        return tuple(artifacts)

    def build(self, edition_id: str) -> BuildResult:
        editions = self._validate_languages(edition_id)
        edition = editions[self.primary_language]
        destination = self.output_dir / edition.id
        review_path = self.editions_dir / edition.id / "reviews" / "render.yaml"
        recorded_review = load_render_review(review_path, edition_id=edition.id)
        reports = [fidelity_report(article.fidelity) for article in edition.articles]
        source_records = {record.id: record for record in load_records(self.sources_dir)}
        declared_source_ids = edition.raw.get("sources", [])
        used_source_ids = sorted(
            set(declared_source_ids)
            | {source_id for article in edition.articles for source_id in article.source_ids}
        )
        language_results: list[LanguageBuildResult] = []
        all_files: list[Path] = []
        cover_compiler = CoverCompiler(self.root)
        for language in self.languages:
            variant = editions[language]
            language_destination = destination if language == self.primary_language else destination / language
            working_pdf = self.output_dir / ".build" / f"{edition.id}-{language}-reader.pdf"
            interior_pdf = self.output_dir / ".build" / f"{edition.id}-{language}-interior.pdf"
            cover = cover_compiler.compile(
                variant,
                self.output_dir / ".build" / "covers" / edition.id / language,
            )
            back_cover = cover_compiler.compile_back(
                variant,
                self.output_dir / ".build" / "back-covers" / edition.id / language,
            )
            layout = render_a5(variant, interior_pdf, design=self.render_design)
            replace_outer_pages(interior_pdf, cover.pdf, back_cover.pdf, working_pdf)
            if cover.cover_art_size_points is not None:
                layout = replace(
                    layout,
                    cover_art_size_points=cover.cover_art_size_points,
                )
            if reports:
                heading = "# Informe de fidelidad" if language == "es" else "# Fidelity report"
                intro = (
                    "\n\nLa traducción se deriva de la edición inglesa validada; el informe conserva "
                    "la trazabilidad de esa edición respecto de las fuentes."
                    if language == "es"
                    else ""
                )
                fidelity_md = heading + intro + "\n\n" + "\n\n".join(
                    report.as_markdown(article.title, language=language)
                    for article, report in zip(variant.articles, reports, strict=True)
                ) + "\n"
            else:
                fidelity_md = _section_fidelity_report(self.root, variant)
            build_manifest = {
                "schema_version": 1,
                "compiler": "magazine-compiler/0.1.0",
                "publication": {
                    "name": variant.publication_name,
                    "language": variant.language,
                    "locale": variant.locale,
                    "available_languages": list(self.languages),
                },
                "edition": variant.raw,
                "inputs": {
                    "cover_faces": {
                        "front": {
                            "input_sha256": cover.input_sha256,
                            "pdf_sha256": cover.pdf_sha256,
                            "png_sha256": cover.png_sha256,
                        },
                        "back": {
                            "input_sha256": back_cover.input_sha256,
                            "pdf_sha256": back_cover.pdf_sha256,
                            "png_sha256": back_cover.png_sha256,
                        },
                    },
                    "editorial": _file_entry(variant.editorial.path, self.root) if variant.editorial else None,
                    "cover_art": _file_entry(variant.cover_art, self.root) if variant.cover_art else None,
                    "translation_manifest": _optional_file_entry(
                        self.editions_dir / edition.id / "translations" / language / "edition.yaml",
                        self.root,
                    ) if language != self.primary_language else None,
                    "fidelity_status": _optional_file_entry(
                        self.editions_dir / edition.id / "fidelity" / "source-edition-status.yaml",
                        self.root,
                    ),
                    "sections": [
                        {"kind": section.kind, **_file_entry(section.path, self.root)}
                        for section in variant.sections
                    ],
                    "articles": [
                        {
                            "id": article.id,
                            "manuscript": _file_entry(article.manuscript, self.root),
                            "fidelity": _file_entry(article.fidelity, self.root),
                        }
                        for article in variant.articles
                    ],
                    "sources": [
                        {
                            "id": source_id,
                            "canonical_url": source_records[source_id].canonical_url,
                            "content_hash": source_records[source_id].content_hash,
                            "raw_captures": source_records[source_id].raw_captures,
                            "record": _file_entry(self.sources_dir / source_id / "record.yaml", self.root),
                            "rights": source_records[source_id].rights,
                        }
                        for source_id in used_source_ids
                    ],
                },
                "layout": {
                    "design_direction": layout.design,
                    "cover_art_size_points": layout.cover_art_size_points,
                    "article_terminal_balance": layout.article_terminal_balance,
                    "maximum_article_pages": 7,
                    "article_pages": layout.article_pages,
                    "maximum_editorial_pages": 2,
                    "editorial_pages": layout.editorial_pages,
                    "figures": [
                        {
                            "id": placement.figure_id,
                            "article_id": placement.article_id,
                            "page": placement.page,
                            "path": placement.path.relative_to(self.root).as_posix(),
                            "pixel_dimensions": list(placement.pixel_dimensions),
                            "box_points": list(placement.box_points),
                            "effective_ppi": placement.effective_ppi,
                            "caption": placement.caption,
                            "credit": placement.credit,
                            "rights_status": placement.rights_status,
                        }
                        for placement in layout.figure_placements
                    ],
                },
                "studio_release_ready": False,
                "studio_blocker": (
                    "La conversión a PDF/X-4 requiere el perfil ICC de la imprenta seleccionada "
                    "y una verificación de preimpresión."
                    if language == "es"
                    else "PDF/X-4 conversion requires the selected printer ICC profile and preflight."
                ),
            }
            files = package_release(
                working_pdf,
                language_destination,
                build_manifest,
                fidelity_md,
                cover_art=variant.cover_art,
                cover_art_size_points=layout.cover_art_size_points,
                source_rights=[source_records[source_id].to_dict() for source_id in used_source_ids],
                figure_placements=layout.figure_placements,
                language=language,
                toc=layout.toc,
                article_pages=layout.article_pages,
                editorial_pages=layout.editorial_pages,
                edition_id=edition.id,
                recorded_review=recorded_review,
            )
            language_result = LanguageBuildResult(
                language,
                language_destination,
                language_destination / "reader.pdf",
                language_destination / "home" / "booklet-a4.pdf",
                tuple(files),
            )
            language_results.append(language_result)
            all_files.extend(files)
        primary = language_results[self.languages.index(self.primary_language)]
        return BuildResult(
            edition.id,
            destination,
            primary.reader_pdf,
            primary.booklet_pdf,
            tuple(all_files),
            tuple(language_results),
        )

    def record_render_review(
        self,
        edition_id: str,
        *,
        reviewer: str,
        result: str,
        findings: list[str] | tuple[str, ...] = (),
        notes: str = "",
        reviewed_at: str | None = None,
    ) -> tuple[Path, BuildResult]:
        """Bind an independent visual decision to the current language PDFs."""

        self.validate(edition_id)
        destination = self.output_dir / edition_id
        language_packages = {
            language: destination if language == self.primary_language else destination / language
            for language in self.languages
        }
        record = create_render_review(
            edition_id=edition_id,
            reviewer=reviewer,
            result=result,
            language_packages=language_packages,
            findings=findings,
            notes=notes,
            reviewed_at=reviewed_at,
        )
        path = write_render_review(
            self.editions_dir / edition_id / "reviews" / "render.yaml",
            record,
        )
        # Rebuild so package reports and checksums carry the recorded decision.
        return path, self.build(edition_id)

    def render_review_status(self, edition_id: str) -> dict[str, Any]:
        destination = self.output_dir / edition_id
        record = load_render_review(
            self.editions_dir / edition_id / "reviews" / "render.yaml",
            edition_id=edition_id,
        )
        statuses: dict[str, Any] = {}
        for language in self.languages:
            package = destination if language == self.primary_language else destination / language
            report_path = package / "render-critic.json"
            reader = package / "reader.pdf"
            booklet = package / "home" / "booklet-a4.pdf"
            if not report_path.is_file() or not reader.is_file() or not booklet.is_file():
                statuses[language] = {"status": "not_built"}
                continue
            report = json.loads(report_path.read_text(encoding="utf-8"))
            visual = visual_review_status(
                record,
                edition_id=edition_id,
                language=language,
                reader_pdf=reader,
                booklet_pdf=booklet,
            )
            statuses[language] = {
                "machine_result": report.get("result"),
                "status": visual.get("status"),
                "reviewer": visual.get("reviewer"),
                "reviewed_at": visual.get("reviewed_at"),
                "result": visual.get("result"),
                "findings": list(visual.get("findings", [])),
                "reader_sha256": visual.get("reader_sha256"),
                "booklet_sha256": visual.get("booklet_sha256"),
            }
        return {"edition_id": edition_id, "languages": statuses}

    def release(
        self, edition_id: str, *, next_edition_id: str | None = None
    ) -> tuple[BuildResult, ReleaseTransition]:
        """Build and then freeze the complete open edition as one transaction."""

        edition = self.validate(edition_id)
        source_ids = _edition_source_ids(edition)
        # Reconcile records before planning so a stale/manual source record can
        # never be omitted merely because the release ledger was not refreshed.
        state = self.sync_release_queue()
        # Fail cheap before rendering, then repeat the check against current
        # on-disk state during finalization after the build has succeeded.
        plan_release(
            state,
            edition_id=edition.id,
            issue_number=edition.issue_number,
            source_ids=source_ids,
            publication_date=edition.publication_date,
            next_edition_id=next_edition_id,
        )
        result = self.build(edition_id)
        require_approved_reports(
            {
                item.language: item.output_dir
                for item in result.languages
            }
        )
        transition = finalize_release(
            self.release_state_path,
            self.editions_dir / edition.id / "edition.yaml",
            edition_id=edition.id,
            issue_number=edition.issue_number,
            source_ids=source_ids,
            publication_date=edition.publication_date,
            next_edition_id=next_edition_id,
            package_dir=result.output_dir,
        )
        return result, transition


def _file_entry(path: Path, root: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _require_media_triage(records: list[SourceRecord]) -> None:
    errors: list[str] = []
    for record in records:
        captures = {
            str(item.get("id"))
            for item in record.raw_captures
            if isinstance(item, dict) and item.get("id")
        }
        reviewed = {review.capture_id for review in record.media_reviews}
        for capture_id in sorted(captures - reviewed):
            errors.append(
                f"Source {record.id} capture {capture_id} has no media triage decision; "
                "review its generated inventory before building"
            )
    if errors:
        raise ValidationError(errors)


def _edition_source_ids(edition: Edition) -> set[str]:
    # Only provenance attached to rendered articles satisfies the all-sources
    # release gate. A bare manifest declaration is inventory, not publication.
    return {
        source_id for article in edition.articles for source_id in article.source_ids
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
