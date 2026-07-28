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
from .evidence_review import (
    create_evidence_review,
    current_evidence_bindings,
    evidence_review_path,
    evidence_review_status as _evidence_review_status,
    load_evidence_review,
    rebind_articles,
    require_approved_evidence_review,
    write_evidence_review,
)
from .extraction import verify_ledger_source_extractions
from .fidelity import fidelity_report
from .io import load_structured
from .manifest import Edition, load_edition, load_translation
from .media_curator import curate_source, verify_source_curation
from .package import package_release
from .reader_layout import declared_editorial_page_cap
from .records import SourceRecord, load_records
from .release import (
    ReleaseState,
    ReleaseTransition,
    finalize_release,
    load_release_state,
    plan_release,
    sync_release_state,
)
from .render_engine import engine_name, reader_renderer
from .render_review import (
    check_recorded_review_embeddable,
    create_render_review,
    embed_recorded_review,
    load_render_review,
    require_approved_reports,
    sha256 as _artifact_sha256,
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


@dataclass(frozen=True)
class LanguageWebResult:
    language: str
    output_dir: Path
    index: Path


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
        # ``design`` is the ReportLab engine's design direction; the WeasyPrint
        # engine owns its own and never sees this value.  See render_engine.
        self.render_design = str(render.get("design") or "monument").strip()
        # Validated here rather than at build time so a typo fails at load.
        self.render_engine = engine_name(render.get("engine"))
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
        # The open edition is the only unreleased one, and the only one whose
        # sources can still be extracted; released editions' source pins
        # predate committed extractions and are verified opportunistically.
        release_state = self._require_release_state()
        require_extractions = edition_id == release_state.open_edition_id
        for article in edition.articles:
            ledger_mode = str(load_structured(article.fidelity).get("content_mode", "faithful_edit"))
            if ledger_mode != article.content_mode:
                raise ValidationError(
                    f"Article {article.id} content_mode {article.content_mode!r} does not match "
                    f"its fidelity ledger {ledger_mode!r}"
                )
            fidelity_report(article.fidelity, source_author=article.author)
            verify_ledger_source_extractions(
                article.fidelity,
                self.sources_dir,
                require_extractions=require_extractions,
                article_source_ids=article.source_ids,
            )
        editions = {edition.language: edition}
        for language in self.languages:
            if language == edition.language:
                continue
            editions[language] = load_translation(self.root, edition, language)
        return editions

    def _require_release_state(self) -> ReleaseState:
        """The release ledger, which must exist: it names the open edition.

        ``load_release_state`` defaults an absent file to an open edition id,
        which is right for a brand-new repository being captured into but wrong
        for validation: with the file missing, the real open edition would
        silently stop requiring extractions.  This repository always carries
        ``library/release-state.yaml``, so absence during validation is loss,
        not youth -- fail loudly.
        """

        if not self.release_state_path.is_file():
            raise ValidationError(
                f"Release state not found: {self.release_state_path}. The release "
                "ledger names the open edition, so validation cannot decide which "
                "edition the extraction gate applies to; restore the file rather "
                "than validating without it."
            )
        return load_release_state(
            self.release_state_path, default_open_id="001-the-work-left-to-us"
        )

    def _load_cover_languages(
        self,
        edition_id: str,
        languages: Iterable[str] | None = None,
        *,
        purpose: str = "Cover proof",
    ) -> dict[str, Edition]:
        """Load only the localized edition data a fast proof or measure needs.

        ``purpose`` names the caller in a refusal, because "Cover proof
        languages are not configured" sends someone running ``mag fit``
        looking at the wrong command.
        """

        if isinstance(languages, str):
            requested = (languages,)
        else:
            requested = tuple(dict.fromkeys(languages or self.languages))
        if not requested:
            raise ValidationError(f"{purpose} requires at least one language")
        unsupported = sorted(set(requested) - set(self.languages))
        if unsupported:
            raise ValidationError(
                f"{purpose} languages are not configured: {', '.join(unsupported)}"
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

    def measure(self, edition_id: str, *, language: str | None = None):
        """Measure the edition's real pagination without writing any artifact.

        The returned :class:`~.measure.EditionMeasurement` reports, per
        language, what a build would only learn deep inside the adapter --
        total reader pages, the editorial's span against its declared cap,
        every article's span against the seven-page rule, and the paragraph
        rag table -- using the adapter's own pagination path, so the verdict
        here is the build's verdict, minutes earlier.  ``language`` narrows
        the measurement to one configured language; the default measures all
        of them, English first, exactly as a build renders them.

        Loading mirrors ``cover_proof`` rather than ``build``: measurement is
        a layout question, so it must be askable *before* the fidelity
        ledgers, extractions and media triage that gate a build are finished
        -- learning the page count only after all of that is the failure mode
        this method exists to remove.

        Imported lazily for the same reason ``render_engine`` imports its
        engines lazily: selecting ReportLab must keep the WeasyPrint adapter
        deletable, and ``measure`` paginates with that adapter.
        """

        from .measure import measure_editions

        if self.render_engine != "weasyprint":
            raise ValidationError(
                f"Measurement paginates with the WeasyPrint reader, but [render] "
                f"engine is {self.render_engine!r}; a measured page count would "
                "not be the configured engine's. Measure with the weasyprint "
                "engine configured."
            )
        editions = self._load_cover_languages(
            edition_id,
            None if language is None else (language,),
            purpose="Measurement",
        )
        return measure_editions(edition_id, editions)

    def fit(self, edition_id: str, *, language: str | None = None) -> tuple[str, bool]:
        """The fast page-budget verdict: a compact table and whether it holds."""

        from .measure import fit_table

        measurement = self.measure(edition_id, language=language)
        return fit_table(measurement), measurement.ok

    def web(
        self,
        edition_id: str,
        *,
        language: str | None = None,
        destination: Path | None = None,
    ) -> tuple[LanguageWebResult, ...]:
        """Write the browsable web edition, one directory per language.

        Each directory is the screen adapter's self-contained output --
        ``index.html``, ``edition.css``, ``assets/``, ``fonts/`` -- written by
        :func:`~.web_edition.write_web_edition` under
        ``output/<edition_id>/web/<language>/``, or under ``destination`` when
        the caller owns the location.  ``language`` narrows to one configured
        language; the default writes all of them, in configuration order,
        exactly as a build renders them.

        Loading mirrors ``cover_proof`` and ``measure`` rather than ``build``:
        a browsable proof is a reading question, so it must be askable before
        the ledgers and pins that gate a build are finished.  The output is
        deliberately not part of a build, a package, or a release, and no
        render review binds to it -- it is a private screen profile, not a
        production artifact.
        """

        from .web_edition import write_web_edition

        editions = self._load_cover_languages(
            edition_id,
            None if language is None else (language,),
            purpose="Web edition",
        )
        root = destination or (self.output_dir / edition_id / "web")
        results: list[LanguageWebResult] = []
        for name, edition in editions.items():
            written = write_web_edition(edition, root / name)
            results.append(
                LanguageWebResult(
                    language=name, output_dir=written.root, index=written.index
                )
            )
        return tuple(results)

    def pin(self, edition_id: str):
        """Recompute every derivable hash pin in the edition's authored files.

        The digests this rewrites are all *derived* facts -- the overlay's
        base-copy hash, each article's source hash, figure caption and credit
        pins, ledger extraction-body pins -- so refreshing them is clerical,
        not editorial.  It is deliberately a separate, explicit command:
        ``validate`` never repins silently, because a stale pin is sometimes
        the only thing telling a reviewer that an input changed under an
        approval.  Run it after the change is understood, not instead of
        understanding it.
        """

        from .pin import refresh_pins

        return refresh_pins(self.root, edition_id)

    def stage_translation(self, edition_id: str, language: str):
        """Scaffold or reconcile one language overlay against the base edition.

        Everything derivable -- structure, pins, placeholder rows -- is
        generated or repaired; everything human -- the actual translated
        prose -- is reported as an explicit backlog so untranslated English
        can never ship silently as a finished translation.
        """

        from .translate_stage import stage_translation

        return stage_translation(self.root, edition_id, language)

    def build(self, edition_id: str, *, engine: str | None = None) -> BuildResult:
        """Render, impose, and package an edition in every configured language.

        ``engine`` overrides ``[render] engine`` for this build only; nothing is
        written back to configuration, so the next build reverts to the
        configured renderer.
        """
        renderer = reader_renderer(
            self.render_engine if engine is None else engine,
            design=self.render_design,
        )
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
            layout = renderer.render(variant, interior_pdf)
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
                            "tail_art": _optional_file_entry(article.tail_art, self.root),
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
                    "maximum_editorial_pages": declared_editorial_page_cap(variant.raw, 2),
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
            # ``design_direction`` already identifies the renderer, because the
            # two engines have disjoint design vocabularies.  What it cannot say
            # is that this renderer is holding its own typography down to match
            # the other one, so a scaffolded engine states that in the artifact.
            # No engine is scaffolded today -- WeasyPrint's three came out at the
            # re-baseline -- so no build writes the key.  The mechanism stays for
            # the next time something has to be held down.
            if renderer.shaping_scaffolds:
                build_manifest["layout"]["shaping_scaffolds"] = list(
                    renderer.shaping_scaffolds
                )
            files = package_release(
                working_pdf,
                language_destination,
                build_manifest,
                fidelity_md,
                cover_art=variant.cover_art,
                cover_art_size_points=layout.cover_art_size_points,
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
        engine: str | None = None,
        rebuild: bool = False,
    ) -> tuple[Path, Path]:
        """Bind an independent visual decision to the PDFs already on disk.

        The record hashes the exact reader and booklet bytes the reviewer just
        inspected; nothing is re-typeset.  The only package content that
        carries review state is ``render-critic.json``'s ``visual_review``
        block, so recording rewrites that block in place in every language
        package and refreshes its line in ``SHA256SUMS`` (see
        :func:`~.render_review.embed_recorded_review`).  The determinism
        guarantee the old rebuild-and-compare provided is now the binding
        itself: the decision names the bytes on disk, and any PDF that later
        disagrees surfaces as ``stale``.

        ``engine`` mirrors ``build``'s override for reviewing an off-config
        build; the record names it, checked against every built package's
        manifest, so a review cannot bind to another engine's pages.

        ``rebuild=True`` is the escape hatch to the old behaviour: re-typeset
        every language with the recorded engine after writing the record, and
        error if any byte differs from what the record binds to.
        """

        self.validate(edition_id)
        renderer = reader_renderer(
            self.render_engine if engine is None else engine,
            design=self.render_design,
        )
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
            engine=renderer.engine,
            design_direction=renderer.design_direction,
            findings=findings,
            notes=notes,
            reviewed_at=reviewed_at,
        )
        if not rebuild:
            # Refusals before the record exists: every language package must
            # accept the embed before any review is written, so a refusal
            # leaves neither an approved render.yaml beside a package that
            # exposes nothing, nor earlier languages embedded when a later
            # one fails.
            for language, package in language_packages.items():
                check_recorded_review_embeddable(
                    package, record, edition_id=edition_id, language=language
                )
        path = write_render_review(
            self.editions_dir / edition_id / "reviews" / "render.yaml",
            record,
        )
        if rebuild:
            # The old proof, kept on request: rebuild with the record's own
            # engine and require the deterministic build to reproduce the
            # recorded bytes, so a non-reproducing record is an error the
            # moment it is written rather than a `status: "stale"` refusal
            # at release time.
            built = self.build(edition_id, engine=renderer.engine)
            mismatched = []
            for item in built.languages:
                row = record["languages"].get(item.language, {})
                if row.get("reader_sha256") != _artifact_sha256(item.reader_pdf) or row.get(
                    "booklet_sha256"
                ) != _artifact_sha256(item.booklet_pdf):
                    mismatched.append(item.language)
            if mismatched:
                raise ValidationError(
                    f"Render review for {edition_id} was recorded against PDFs the rebuild "
                    f"did not reproduce ({', '.join(sorted(mismatched))}). The recorded "
                    "review is already stale; rebuild, re-review the current PDFs, and "
                    "record again."
                )
            return path, destination
        for language, package in language_packages.items():
            embed_recorded_review(
                package, record, edition_id=edition_id, language=language
            )
        return path, destination

    def record_evidence_review(
        self,
        edition_id: str,
        *,
        reviewer: str,
        result: str,
        findings: list[str] | tuple[str, ...] = (),
        notes: str = "",
        reviewed_at: str | None = None,
        articles: Iterable[str] | None = None,
    ) -> Path:
        """Bind an independent evidence audit to the exact bytes it compared.

        The record pins every manuscript, fidelity ledger, and extraction body
        the audit covered.  Recording requires a committed extraction for every
        ledger source: an audit cannot have compared a manuscript against
        evidence that does not exist.

        ``articles`` narrows a re-record to the articles actually re-audited:
        only those are re-bound from current disk state, and every other
        article keeps the existing record's binding and per-article
        ``reviewed_at``.  One changed article no longer costs a full-edition
        re-audit -- edition 003's evidence record was re-recorded three times
        in a day for exactly that reason.  Omitted, the record binds the whole
        edition afresh, as it always has.
        """

        edition = self.validate(edition_id)
        bindings = current_evidence_bindings(
            edition, self.sources_dir, require_extractions=True
        )
        if articles is not None:
            bindings = rebind_articles(
                load_evidence_review(
                    evidence_review_path(self.editions_dir, edition_id),
                    edition_id=edition_id,
                ),
                bindings=bindings,
                article_ids=articles,
            )
        record = create_evidence_review(
            edition_id=edition_id,
            reviewer=reviewer,
            result=result,
            bindings=bindings,
            findings=findings,
            notes=notes,
            reviewed_at=reviewed_at,
        )
        return write_evidence_review(
            evidence_review_path(self.editions_dir, edition_id), record
        )

    def evidence_review_status(self, edition_id: str) -> dict[str, Any]:
        """Hash-bound evidence review status, resilient enough for diagnosis.

        Status is a diagnostic surface, so an edition that cannot even be
        loaded reports its errors instead of aborting the whole command; the
        release gate goes through :func:`require_approved_evidence_review`
        with a fully validated edition instead.
        """

        try:
            release_state = self._require_release_state()
            records = load_records(self.sources_dir)
            edition = load_edition(
                self.root,
                edition_id,
                {record.id for record in records},
                publication_name=self.publication_name,
                source_records={record.id: record for record in records},
            )
            bindings = current_evidence_bindings(
                edition, self.sources_dir, require_extractions=False
            )
            record = load_evidence_review(
                evidence_review_path(self.editions_dir, edition_id),
                edition_id=edition_id,
            )
        except ValidationError as exc:
            return {"status": "unavailable", "errors": list(exc.errors)}
        status = _evidence_review_status(record, edition_id=edition_id, bindings=bindings)
        # Only the open edition can still be released, so only it can *owe* an
        # evidence review; a released edition without one is simply outside the
        # gate's jurisdiction, not delinquent.
        if (
            edition_id != release_state.open_edition_id
            and status["status"] == "required_before_release"
        ):
            status["status"] = "not_required"
        return status

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
        # The evidence audit binds to manuscripts, ledgers, and extraction
        # bodies rather than built artifacts, so it can refuse before the
        # expensive render, mirroring require_approved_reports after it.
        require_approved_evidence_review(
            load_evidence_review(
                evidence_review_path(self.editions_dir, edition.id),
                edition_id=edition.id,
            ),
            edition_id=edition.id,
            bindings=current_evidence_bindings(
                edition, self.sources_dir, require_extractions=False
            ),
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


def _optional_file_entry(path: Path | None, root: Path) -> dict[str, str] | None:
    return _file_entry(path, root) if path is not None and path.is_file() else None


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
