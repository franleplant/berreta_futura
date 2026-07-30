from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw

from .article_stage import ArticleBrief, plan_article_stage, stage_article
from .capture import archive_snapshot, index_existing_captures, verify_snapshots
from .catalog import render_sources
from .cover import CoverArtifact, CoverCompiler, replace_outer_pages
from .cover_studio import CoverProofRequest, CoverStudio
from .cover_art_candidates import (
    cover_art_candidate_record_path,
    hydrate_cover_art_candidates,
    scaffold_cover_art_candidates,
    validate_cover_art_candidates,
    write_cover_art_prompt_package,
)
from .errors import DependencyError, ValidationError
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
from .illustration import (
    load_illustration_plan,
    validate_illustration_plan,
    write_illustration_package,
)
from .illustration_studio import (
    IllustrationBrief,
    IllustrationReviewPlan,
    IllustrationStudio,
)
from .manifest import Edition, load_edition, load_translation
from .media_curator import curate_source, verify_source_curation
from .package import package_release
from .reader_layout import declared_editorial_page_cap
from .records import AuthorProfile, SourceRecord, canonicalize_url, load_records
from .release import (
    ReleaseState,
    ReleaseTransition,
    finalize_release,
    load_release_state,
    open_collection,
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
from .workflow import Workflow


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


@dataclass(frozen=True)
class ArticleWorkflowReport:
    """One article scaffold plus every required language-overlay reconciliation."""

    edition_id: str
    article_id: str
    dry_run: bool
    changed: bool
    created: tuple[Path, ...]
    updated: tuple[Path, ...]
    kept: tuple[Path, ...]
    translations: tuple[dict[str, Any], ...]

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        def display(path: Path) -> str:
            if root is not None:
                try:
                    return path.relative_to(root).as_posix()
                except ValueError:
                    pass
            return path.as_posix()

        return {
            "schema_version": 1,
            "edition_id": self.edition_id,
            "article_id": self.article_id,
            "dry_run": self.dry_run,
            "changed": self.changed,
            "created": [display(path) for path in self.created],
            "updated": [display(path) for path in self.updated],
            "kept": [display(path) for path in self.kept],
            "translations": [
                {
                    **item,
                    "created": [display(path) for path in item["created"]],
                    "updated": [display(path) for path in item["updated"]],
                    "placeholders": [
                        {
                            **placeholder,
                            "path": display(placeholder["path"]),
                        }
                        for placeholder in item["placeholders"]
                    ],
                }
                for item in self.translations
            ],
        }


class _MagazineCoverProofAdapter:
    """Render one studio request through the production cover compiler."""

    def __init__(self, magazine: "Magazine") -> None:
        self.magazine = magazine

    def render(self, request: CoverProofRequest) -> dict[str, bytes]:
        editions = self.magazine.load_cover_languages(
            request.edition_dir.name,
            (request.language,),
            purpose="Cover Studio proof",
        )
        edition = editions[request.language]
        cover = {**edition.cover, **dict(request.cover_override)}
        edition = replace(
            edition,
            cover=cover,
            cover_art=request.art_path,
        )
        with tempfile.TemporaryDirectory(prefix="mag-cover-proof-") as temporary:
            artifact = CoverCompiler(self.magazine.root).compile(
                edition,
                Path(temporary),
            )
            return {
                "cover.svg": artifact.svg.read_bytes(),
                "cover.pdf": artifact.pdf.read_bytes(),
                "cover.png": artifact.png.read_bytes(),
                "proof.json": artifact.proof_json.read_bytes(),
            }


class _MagazineIllustrationReviewAdapter:
    """Create a compact, deterministic review sheet from registered assets."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def render(self, plan: IllustrationReviewPlan) -> dict[str, bytes]:
        cell_width = 480
        cell_height = 360
        label_height = 54
        rows = max(1, len(plan.assets))
        sheet = Image.new(
            "RGB",
            (cell_width, rows * (cell_height + label_height)),
            "white",
        )
        draw = ImageDraw.Draw(sheet)
        inventory: list[dict[str, Any]] = []
        for index, asset in enumerate(plan.assets):
            with Image.open(asset.art_path) as source:
                image = source.convert("RGB")
                image.thumbnail((cell_width, cell_height))
            top = index * (cell_height + label_height)
            left = (cell_width - image.width) // 2
            sheet.paste(image, (left, top))
            label = asset.id
            if asset.article_id:
                label += f" | article {asset.article_id}"
            if asset.plate_index is not None:
                label += f" | closing plate {asset.plate_index}"
            draw.text((12, top + cell_height + 12), label, fill="black")
            inventory.append(
                {
                    "id": asset.id,
                    "role": asset.role,
                    "article_id": asset.article_id,
                    "plate_index": asset.plate_index,
                    "art_path": asset.art_path.relative_to(self.root).as_posix(),
                    "asset_sha256": asset.asset_sha256,
                    "prompt_sha256": asset.prompt_sha256,
                }
            )
        import io

        stream = io.BytesIO()
        sheet.save(stream, format="PNG", optimize=False)
        payload = {
            "schema_version": 1,
            "edition_id": plan.edition_id,
            "revision": plan.revision,
            "assets": inventory,
        }
        return {
            "review.png": stream.getvalue(),
            "review.json": (
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8"),
        }


def _clear_web_language_dir(directory: Path) -> None:
    """Empty a web language directory before the adapter rewrites it.

    The adapter honours "the caller owns the destination" and never deletes,
    so stale assets from earlier contracts would otherwise accumulate and
    ride into any deploy gather.  Magazine.web owns ``output/``, so the
    clearing lives here -- with the same guard-rail spirit as
    ``deploy/web/assemble.py``: a non-empty directory that does not look like
    a prior web edition (no ``index.html``) is somebody else's data, and the
    answer is a refusal, not a wipe.
    """

    import shutil

    if not directory.exists():
        return
    if any(directory.iterdir()) and not (directory / "index.html").is_file():
        raise ValidationError(
            f"web output directory {directory} is non-empty and carries no "
            "index.html from a prior web edition; refusing to clear it -- "
            "move or empty it, or point the build elsewhere"
        )
    shutil.rmtree(directory)


def _archive_author_profile(
    record: SourceRecord,
    sources_dir: Path,
    *,
    note: str,
    evidence_inputs: tuple[tuple[str, Path], ...],
    captured_at: str,
) -> SourceRecord:
    evidence_rows: list[dict[str, str]] = []
    for source_url, snapshot in evidence_inputs:
        before = {
            str(row.get("id"))
            for row in record.raw_captures
            if isinstance(row, dict) and row.get("id")
        }
        record = archive_snapshot(
            record,
            sources_dir,
            snapshot,
            method="author_identity_profile",
            captured_at=captured_at,
            purpose="author_identity",
            source_url=source_url,
        )
        added = {
            str(row.get("id"))
            for row in record.raw_captures
            if isinstance(row, dict) and row.get("id")
        } - before
        if len(added) == 1:
            capture_id = added.pop()
        else:
            matching = [
                str(row.get("id"))
                for row in record.raw_captures
                if isinstance(row, dict)
                and str(row.get("purpose") or "article") == "author_identity"
                and str(row.get("source_url") or "") == source_url
                and row.get("id")
            ]
            if len(matching) != 1:
                raise ValidationError(
                    f"Could not bind author evidence {source_url} to one raw capture"
                )
            capture_id = matching[0]
        evidence_rows.append({"url": source_url, "capture_id": capture_id})
    raw_capture_ids = {
        str(row.get("id"))
        for row in record.raw_captures
        if isinstance(row, dict) and row.get("id")
    }
    profile = AuthorProfile.create(
        note,
        evidence=evidence_rows,
        raw_capture_ids=raw_capture_ids,
    )
    return replace(record, schema_version=2, author_profile=profile)


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
        author_note: str | None = None,
        author_evidence: Iterable[tuple[str, Path]] = (),
        institutional_author: bool = False,
        edition_id: str | None = None,
        **metadata: Any,
    ) -> SourceRecord:
        """Archive raw evidence, then store and queue its normalized source record."""
        evidence_inputs = tuple(
            (canonicalize_url(source_url), Path(evidence_snapshot))
            for source_url, evidence_snapshot in author_evidence
        )
        author = str(metadata.get("author") or "").strip()
        profile_requested = author_note is not None or institutional_author
        if institutional_author and author_note is not None:
            raise ValidationError(
                "institutional_author and author_note are mutually exclusive"
            )
        if profile_requested and not author:
            raise ValidationError("Author identity capture requires author")
        if author_note is not None and not evidence_inputs:
            raise ValidationError(
                "author_note requires at least one archived author_evidence snapshot"
            )
        if author_note is None and evidence_inputs:
            raise ValidationError("author_evidence requires author_note")
        if institutional_author and evidence_inputs:
            raise ValidationError(
                "institutional_author must not include author_evidence"
            )
        if author_note is not None:
            # Validate the copy before writing any raw bundle. The real capture
            # ids replace these placeholders after the evidence is archived.
            AuthorProfile.create(
                author_note,
                evidence=[
                    {"url": source_url, "capture_id": "0" * 64}
                    for source_url, _ in evidence_inputs
                ],
            )
        candidate = SourceRecord.create(url, **metadata)
        for existing in load_records(self.sources_dir):
            if existing.canonical_url == candidate.canonical_url:
                if profile_requested:
                    existing = replace(
                        existing,
                        author=candidate.author,
                        schema_version=2,
                    )
                previous_captures = {
                    str(row.get("id")) for row in existing.raw_captures if row.get("id")
                }
                existing = archive_snapshot(
                    existing, self.sources_dir, snapshot, method=capture_method,
                    captured_at=candidate.captured_at,
                )
                if profile_requested:
                    existing = _archive_author_profile(
                        existing,
                        self.sources_dir,
                        note=author_note or "",
                        evidence_inputs=evidence_inputs,
                        captured_at=candidate.captured_at,
                    )
                added = {
                    str(row.get("id")) for row in existing.raw_captures if row.get("id")
                } - previous_captures
                existing, _ = curate_source(
                    existing, self.sources_dir, refresh_capture_ids=added
                )
                existing.write(self.sources_dir)
                self.sync_release_queue(target_edition_id=edition_id)
                return existing
        if profile_requested:
            candidate = replace(candidate, schema_version=2)
        candidate = archive_snapshot(
            candidate, self.sources_dir, snapshot, method=capture_method
        )
        if profile_requested:
            candidate = _archive_author_profile(
                candidate,
                self.sources_dir,
                note=author_note or "",
                evidence_inputs=evidence_inputs,
                captured_at=candidate.captured_at,
            )
        candidate, _ = curate_source(
            candidate,
            self.sources_dir,
            refresh_capture_ids={str(row["id"]) for row in candidate.raw_captures},
        )
        candidate.write(self.sources_dir)
        self.sync_release_queue(target_edition_id=edition_id)
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

    def sync_release_queue(
        self,
        records: list[SourceRecord] | None = None,
        *,
        target_edition_id: str | None = None,
    ) -> ReleaseState:
        current = records if records is not None else load_records(self.sources_dir)
        for record in current:
            verify_snapshots(record, self.sources_dir)
        state = sync_release_state(
            self.release_state_path,
            {record.id for record in current},
            default_open_id="001-the-work-left-to-us",
            target_edition_id=target_edition_id,
        )
        self._scaffold_collecting_cover_records(state)
        return state

    def open_collection(
        self,
        edition_id: str,
        *,
        issue_number: str | int,
    ) -> ReleaseState:
        """Open and select an edition for subsequent source intake."""

        state = open_collection(
            self.release_state_path,
            edition_id=edition_id,
            issue_number=issue_number,
            default_open_id="001-the-work-left-to-us",
        )
        self._scaffold_collecting_cover_records(state)
        return state

    def workflow_status(self, edition_id: str):
        """Return the complete read-only workflow report for one edition."""

        return Workflow(self.root).status(edition_id)

    def workflow_run(self, edition_id: str):
        """Advance clerical checkpoints and stop before authorship or judgment."""

        return Workflow(self.root).run(edition_id)

    workflow_advance = workflow_run

    def stage_article(
        self,
        brief: ArticleBrief | dict[str, Any] | Path,
        *,
        dry_run: bool = False,
    ) -> ArticleWorkflowReport:
        """Stage an article and reconcile every configured translation as one unit.

        The article module validates the source-to-manifest plan first. An
        isolated copy then exercises the article and every configured overlay
        before the real edition is touched. A real run conditionally restores
        only files this invocation changed if a later overlay refuses.
        """

        if isinstance(brief, Path):
            brief = ArticleBrief.from_dict(load_structured(brief))
        elif isinstance(brief, dict):
            brief = ArticleBrief.from_dict(brief)
        plan = plan_article_stage(self.root, brief)
        preflight = _preflight_article_transaction(self, brief, plan)
        report = stage_article(self.root, brief, dry_run=True)
        if dry_run:
            return ArticleWorkflowReport(
                edition_id=report.edition_id,
                article_id=report.article_id,
                dry_run=True,
                changed=plan.changed
                or any(row["changed"] for row in preflight.translations),
                created=report.created,
                updated=report.updated,
                kept=report.kept,
                translations=tuple(
                    {**row, "dry_run": True}
                    for row in preflight.translations
                ),
            )

        tracker = _ArticleTransaction(
            self.root,
            preflight.committed,
        )
        try:
            report = stage_article(self.root, brief)
            tracker.commit(
                (*report.created, *report.updated),
            )
            translation_rows: list[dict[str, Any]] = []
            for language in self.languages:
                if language == self.primary_language:
                    continue
                staged = self.stage_translation(plan.edition_id, language)
                touched = _translation_touched_paths(staged)
                tracker.commit(touched)
                translation_rows.append(
                    _translation_report_row(
                        staged,
                        source_root=self.root,
                        destination_root=self.root,
                        dry_run=False,
                    )
                )
        except BaseException as exc:
            conflicts = tracker.rollback()
            if conflicts:
                original = (
                    list(exc.errors)
                    if isinstance(exc, ValidationError)
                    else [str(exc)]
                )
                raise ValidationError(
                    [
                        *original,
                        (
                            "Article integration preserved concurrently edited "
                            "touched files while rolling back every other safe "
                            "write: "
                            + ", ".join(
                                path.relative_to(self.root).as_posix()
                                for path in conflicts
                            )
                        ),
                    ]
                ) from exc
            raise
        return ArticleWorkflowReport(
            edition_id=report.edition_id,
            article_id=report.article_id,
            dry_run=False,
            changed=report.changed
            or any(row["changed"] for row in translation_rows),
            created=report.created,
            updated=report.updated,
            kept=report.kept,
            translations=tuple(translation_rows),
        )

    def cover_studio_status(self, edition_id: str):
        return self._cover_studio(edition_id).status()

    def cover_studio_scaffold(
        self,
        edition_id: str,
        *,
        editorial_reading: str | None = None,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ):
        return self._cover_studio(edition_id).scaffold_next_round(
            editorial_reading=editorial_reading,
            dry_run=dry_run,
            expected_revision=expected_revision,
        )

    def cover_studio_prompts(
        self,
        edition_id: str,
        round_number: int,
        *,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ):
        return self._cover_studio(edition_id).emit_prompt_package(
            round_number,
            dry_run=dry_run,
            expected_revision=expected_revision,
        )

    def cover_studio_register(
        self,
        edition_id: str,
        round_number: int,
        images: dict[str, Path],
        *,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ):
        return self._cover_studio(edition_id).register_round(
            round_number,
            images,
            dry_run=dry_run,
            expected_revision=expected_revision,
        )

    def cover_studio_proof_plan(
        self,
        edition_id: str,
        *,
        languages: Iterable[str] | None = None,
        rounds: Iterable[int] | None = None,
    ):
        requested = tuple(languages or self.languages)
        unsupported = sorted(set(requested) - set(self.languages))
        if unsupported:
            raise ValidationError(
                "Cover Studio proof languages are not configured: "
                + ", ".join(unsupported)
            )
        return self._cover_studio(edition_id).proof_plan(
            requested,
            rounds=rounds,
        )

    def cover_studio_render_proofs(
        self,
        edition_id: str,
        *,
        languages: Iterable[str] | None = None,
        rounds: Iterable[int] | None = None,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ) -> tuple[Any, Path]:
        requested = tuple(languages or self.languages)
        studio = self._cover_studio(edition_id, proofs=True)
        action = studio.render_proofs(
            requested,
            rounds=rounds,
            dry_run=dry_run,
            expected_revision=expected_revision,
        )
        comparison = (
            self.editions_dir
            / edition_id
            / "art"
            / "cover-rounds"
            / "full-cover-comparison.png"
        )
        if not dry_run:
            requests = studio.proof_plan(requested, rounds=rounds)
            _write_full_cover_comparison(requests, comparison)
        return action, comparison

    def cover_studio_compare(
        self,
        edition_id: str,
        *,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ):
        return self._cover_studio(edition_id).create_comparison_sheet(
            dry_run=dry_run,
            expected_revision=expected_revision,
        )

    def cover_studio_select(
        self,
        edition_id: str,
        round_number: int,
        variant: str,
        *,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ):
        return self._cover_studio(edition_id).select(
            round_number,
            variant,
            dry_run=dry_run,
            expected_revision=expected_revision,
        )

    def illustration_studio_status(self, edition_id: str):
        return self._illustration_studio().status(edition_id)

    def illustration_studio_scaffold(
        self,
        brief: IllustrationBrief | dict[str, Any] | Path,
        *,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ):
        return self._illustration_studio().scaffold(
            brief,
            dry_run=dry_run,
            expected_revision=expected_revision,
        )

    def illustration_studio_prompts(
        self,
        edition_id: str,
        *,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ):
        return self._illustration_studio().emit_prompt_package(
            edition_id,
            dry_run=dry_run,
            expected_revision=expected_revision,
        )

    def illustration_studio_register(
        self,
        edition_id: str,
        asset_id: str,
        source: Path,
        *,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ):
        return self._illustration_studio().register_asset(
            edition_id,
            asset_id,
            source,
            dry_run=dry_run,
            expected_revision=expected_revision,
        )

    def illustration_studio_review_plan(self, edition_id: str):
        return self._illustration_studio().review_plan(edition_id)

    def illustration_studio_review_sheet(
        self,
        edition_id: str,
        *,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ):
        return self._illustration_studio(review=True).create_review_sheet(
            edition_id,
            dry_run=dry_run,
            expected_revision=expected_revision,
        )

    def _cover_studio(self, edition_id: str, *, proofs: bool = False) -> CoverStudio:
        edition_dir = (self.editions_dir / edition_id).resolve()
        try:
            edition_dir.relative_to(self.editions_dir.resolve())
        except ValueError as exc:
            raise ValidationError(
                f"Cover Studio edition id escapes the editions directory: {edition_id}"
            ) from exc
        if not edition_dir.is_dir():
            raise ValidationError(f"Edition directory not found: {edition_dir}")
        return CoverStudio(
            edition_dir,
            proof_adapter=_MagazineCoverProofAdapter(self) if proofs else None,
        )

    def _illustration_studio(self, *, review: bool = False) -> IllustrationStudio:
        return IllustrationStudio(
            self.root,
            review_adapter=(
                _MagazineIllustrationReviewAdapter(self.root)
                if review
                else None
            ),
        )

    def _scaffold_collecting_cover_records(
        self, state: ReleaseState
    ) -> None:
        """Give every collecting edition the canonical three-branch brief."""

        for collecting_id in state.collecting_edition_ids:
            scaffold_cover_art_candidates(
                self.editions_dir / collecting_id
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
        validate_illustration_plan(self.root, edition)
        release_state = self._require_release_state()
        record_path = cover_art_candidate_record_path(
            self.editions_dir / edition.id
        )
        if edition_id in release_state.collecting_edition_ids:
            if not record_path.is_file():
                raise ValidationError(
                    f"Collecting edition {edition_id} requires the canonical "
                    f"three-branch cover-art record: {record_path}"
                )
            validate_cover_art_candidates(
                self.editions_dir / edition.id,
                record_path=record_path,
                selected_art_path=(
                    str((edition.raw.get("cover") or {}).get("art_path") or "")
                    if str(
                        load_structured(record_path).get("selection_status") or ""
                    ).strip()
                    == "selected"
                    else None
                ),
            )
        # Every collecting edition remains mutable and therefore owes the full
        # extraction chain. Released editions' source pins predate committed
        # extractions and are verified opportunistically.
        require_extractions = edition_id in release_state.collecting_edition_ids
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

    def illustration_package(self, edition_id: str) -> Path:
        """Compile generic cover prompts and any interior-art prompts."""

        records = load_records(self.sources_dir)
        edition = load_edition(
            self.root,
            edition_id,
            {record.id for record in records},
            publication_name=self.publication_name,
            source_records={record.id: record for record in records},
            allow_missing_art=True,
        )
        destination = self.output_dir / edition.id / "illustration-prompts"
        destination.mkdir(parents=True, exist_ok=True)
        for generated in destination.glob("*.txt"):
            generated.unlink()
        for name in ("illustrations.json", "cover-candidates.json"):
            generated = destination / name
            if generated.is_file():
                generated.unlink()
        if load_illustration_plan(self.root, edition) is not None:
            destination = write_illustration_package(
                self.root,
                self.output_dir,
                edition,
            )
        release_state = self._require_release_state()
        if edition.id in release_state.collecting_edition_ids:
            record_path = hydrate_cover_art_candidates(
                self.editions_dir / edition.id,
                editorial_reading=self._cover_editorial_reading(edition),
            )
            write_cover_art_prompt_package(
                self.editions_dir / edition.id,
                destination,
                record_path=record_path,
            )
        return destination

    @staticmethod
    def _cover_editorial_reading(edition: Edition) -> str:
        """Derive a useful first cover reading without manifest wiring."""

        cover = edition.cover or {}
        parts = [
            str(edition.title or "").strip(),
            str(
                cover.get("deck")
                or edition.raw.get("subtitle")
                or cover.get("back_text")
                or ""
            ).strip(),
        ]
        return ". ".join(part.rstrip(".") for part in parts if part) + "."

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

    def load_cover_languages(
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

    _load_cover_languages = load_cover_languages

    def cover_proof(
        self,
        edition_id: str,
        *,
        languages: Iterable[str] | None = None,
        reference: Path | None = None,
        check: bool = False,
    ) -> tuple[CoverArtifact, ...]:
        """Compile fast browser/PDF cover proofs without typesetting interiors."""

        editions = self.load_cover_languages(edition_id, languages)
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

        editions = self.load_cover_languages(edition_id, languages)
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
        editions = self.load_cover_languages(
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

        The cover page and every masthead carry the publication's Corte bruto
        lockup, materialized once per build as a standalone SVG through
        :func:`magazine.cover.materialize_wordmark_svg` -- the same outlined
        paths the printed cover sets, honouring the project's authored cover
        inks when a design file exists.  The lockup is publication identity,
        never translated, so one file at the web root serves every language
        and the adapter copies it into each.  Each article's opener source ids
        become working links: the mapping from source id to canonical URL is
        read from the source records here, where the records live, and handed
        to the adapter as data.
        """

        from .web_edition import write_web_edition

        editions = self.load_cover_languages(
            edition_id,
            None if language is None else (language,),
            purpose="Web edition",
        )
        root = destination or (self.output_dir / edition_id / "web")
        # Outlining needs only FontTools and the bundled faces -- CoverCompiler
        # falls back to built-in canto-vivo geometry without a design file --
        # so every project gets the lockup, fixtures included.  A missing
        # toolchain is the one reason to ship the text masthead instead, and
        # it is a degradation, never an error.
        wordmark: Path | None = None
        favicon: Path | None = None
        try:
            from .cover import materialize_favicon_svg, materialize_wordmark_svg

            publication = next(iter(editions.values())).publication_name
            lockup = materialize_wordmark_svg(publication, self.root)
            mark = materialize_favicon_svg(publication, self.root)
        except DependencyError:
            pass
        else:
            root.mkdir(parents=True, exist_ok=True)
            wordmark = root / "wordmark.svg"
            wordmark.write_text(lockup, encoding="utf-8")
            favicon = root / "favicon.svg"
            favicon.write_text(mark, encoding="utf-8")
        source_urls = {
            record.id: record.canonical_url
            for record in load_records(self.sources_dir)
            if record.canonical_url
        }
        results: list[LanguageWebResult] = []
        for name, edition in editions.items():
            directory = root / name
            _clear_web_language_dir(directory)
            # The printed face's own line construction, derived per language
            # because the headline is localized.  A headline no size fits, or
            # a project without the cover toolchain, sets as one run -- the
            # adapter's stated fallback, not an error.
            headline = str(edition.cover.get("headline") or edition.title)
            try:
                from .cover import CoverOverflowError, cover_headline_lines

                lines: tuple[str, ...] | None = cover_headline_lines(headline, self.root)
            except (DependencyError, CoverOverflowError):
                lines = None
            written = write_web_edition(
                edition,
                directory,
                wordmark=wordmark,
                favicon=favicon,
                source_urls=source_urls,
                headline_lines=lines,
                alternates={
                    other: f"../{other}/" for other in editions if other != name
                },
            )
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
        illustration_plan = load_illustration_plan(self.root, edition)
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
                    "illustration_plan": (
                        _file_entry(illustration_plan.path, self.root)
                        if illustration_plan is not None
                        else None
                    ),
                    "illustration_direction": (
                        _file_entry(illustration_plan.direction_path, self.root)
                        if illustration_plan is not None
                        and illustration_plan.direction_path is not None
                        else None
                    ),
                    "illustration_references": (
                        [
                            _file_entry(path, self.root)
                            for path in illustration_plan.direction.reference_paths
                        ]
                        if illustration_plan is not None
                        else []
                    ),
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
                    "closing_plates": [
                        {
                            "index": index,
                            "title": plate.title,
                            "art": _file_entry(plate.art_path, self.root),
                        }
                        for index, plate in enumerate(
                            variant.closing_plates, start=1
                        )
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
        # Only collecting editions can still be released, so only they can owe
        # an evidence review.
        if (
            edition_id not in release_state.collecting_edition_ids
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
        # `finalize_release` may open the next collecting edition implicitly.
        # Give that collection the same generic cover brief as `mag collect`;
        # neither path depends on a key in an edition manifest.
        self._scaffold_collecting_cover_records(
            self._require_release_state()
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


@dataclass(frozen=True)
class _ArticlePreflight:
    translations: tuple[dict[str, Any], ...]
    committed: dict[Path, bytes | None]


def _preflight_article_transaction(
    magazine: Magazine,
    brief: ArticleBrief,
    plan: Any,
) -> _ArticlePreflight:
    """Exercise article and overlay staging in an isolated project copy."""

    with tempfile.TemporaryDirectory(prefix="mag-article-preflight-") as temporary:
        sandbox = Path(temporary).resolve()
        _copy_preflight_project(
            magazine,
            sandbox,
            edition_id=plan.edition_id,
            source_ids=brief.source_ids,
        )
        article_updates = tuple(plan._updates)
        for path, content in article_updates:
            target = _map_preflight_path(path, magazine.root, sandbox)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        from .translate_stage import stage_translation as stage_overlay

        rows: list[dict[str, Any]] = []
        committed = {
            path.resolve(): content
            for path, content in article_updates
        }
        for language in magazine.languages:
            if language == magazine.primary_language:
                continue
            report = stage_overlay(sandbox, plan.edition_id, language)
            rows.append(
                _translation_report_row(
                    report,
                    source_root=sandbox,
                    destination_root=magazine.root,
                    dry_run=True,
                )
            )
            for path in _translation_touched_paths(report):
                real_path = _map_preflight_path(path, sandbox, magazine.root)
                committed[real_path] = _path_bytes(path)
        return _ArticlePreflight(
            translations=tuple(rows),
            committed=committed,
        )


def _copy_preflight_project(
    magazine: Magazine,
    sandbox: Path,
    *,
    edition_id: str,
    source_ids: Iterable[str],
) -> None:
    """Copy the minimum project state needed for a writing preflight."""

    config = magazine.root / "magazine.toml"
    if config.is_file():
        shutil.copy2(config, sandbox / "magazine.toml")

    sources_relative = _project_relative(
        magazine.root,
        magazine.sources_dir,
        label="Configured sources directory",
    )
    _copy_preflight_sources(
        magazine.sources_dir,
        sandbox / sources_relative,
        source_ids=source_ids,
    )

    edition_dir = magazine.editions_dir / edition_id
    editions_relative = _project_relative(
        magazine.root,
        magazine.editions_dir,
        label="Configured editions directory",
    )
    destination = sandbox / editions_relative / edition_id
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        edition_dir,
        destination,
        copy_function=_copy_preflight_edition_file,
    )

    release_relative = _project_relative(
        magazine.root,
        magazine.release_state_path,
        label="Configured release state",
    )
    release_destination = sandbox / release_relative
    release_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(magazine.release_state_path, release_destination)


def _copy_preflight_sources(
    sources_dir: Path,
    destination: Path,
    *,
    source_ids: Iterable[str],
) -> None:
    """Copy source metadata plus only the brief's extraction bodies."""

    sources_root = sources_dir.resolve()
    _require_plain_preflight_path(sources_dir, sources_dir, label="Sources directory")
    destination.mkdir(parents=True, exist_ok=True)

    records = sorted(sources_dir.glob("*/record.y*ml"))
    for record in records:
        _require_plain_preflight_path(record, sources_dir, label="Source record")
        relative = record.resolve().relative_to(sources_root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(record, target)

    for source_id in tuple(dict.fromkeys(source_ids)):
        source_dir = sources_dir / source_id
        extraction = source_dir / "extracted.md"
        _require_plain_preflight_path(
            extraction,
            sources_dir,
            label=f"Source {source_id} extraction",
        )
        relative = extraction.resolve().relative_to(sources_root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(extraction, target)


def _require_plain_preflight_path(
    path: Path,
    root: Path,
    *,
    label: str,
) -> None:
    """Reject missing, escaping, or symlinked preflight source inputs."""

    if path.is_symlink():
        raise ValidationError(f"{label} must not be a symbolic link: {path}")
    root_resolved = root.resolve()
    try:
        lexical = path.absolute().relative_to(root.absolute())
    except ValueError as exc:
        raise ValidationError(f"{label} escapes the sources directory: {path}") from exc
    current = root.absolute()
    for part in lexical.parts:
        current = current / part
        if current.is_symlink():
            raise ValidationError(
                f"{label} has a symbolic-link path component: {current}"
            )
    resolved = path.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValidationError(f"{label} escapes the sources directory: {path}") from exc
    if path.absolute() == root.absolute():
        if not path.is_dir():
            raise ValidationError(f"{label} is not a directory: {path}")
    elif not path.is_file():
        raise ValidationError(f"{label} is not a regular file: {path}")


def _hardlink_read_only(source: str, destination: str) -> str:
    try:
        os.link(source, destination)
    except OSError:
        return shutil.copy2(source, destination)
    return destination


def _copy_preflight_edition_file(source: str, destination: str) -> str:
    """Copy writable prose and hardlink immutable binary inputs."""

    if Path(source).suffix.lower() in {".yaml", ".yml", ".md", ".json"}:
        return shutil.copy2(source, destination)
    return _hardlink_read_only(source, destination)


def _project_relative(root: Path, path: Path, *, label: str) -> Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValidationError(f"{label} escapes the project root: {path}") from exc


def _map_preflight_path(path: Path, source_root: Path, destination_root: Path) -> Path:
    relative = _project_relative(
        source_root,
        path,
        label="Preflight output",
    )
    return destination_root / relative


def _translation_touched_paths(report: Any) -> tuple[Path, ...]:
    return tuple(
        dict.fromkeys(
            (
                *report.created,
                *report.updated,
                *(change.path for change in report.pin_changes),
            )
        )
    )


def _translation_report_row(
    report: Any,
    *,
    source_root: Path,
    destination_root: Path,
    dry_run: bool,
) -> dict[str, Any]:
    def mapped(path: Path) -> Path:
        return _map_preflight_path(path, source_root, destination_root)

    return {
        "language": report.language,
        "changed": report.changed,
        "dry_run": dry_run,
        "created": tuple(mapped(path) for path in report.created),
        "updated": tuple(mapped(path) for path in report.updated),
        "placeholders": tuple(
            {
                "path": mapped(field.path),
                "pointer": field.pointer,
            }
            for field in report.placeholders
        ),
        "advisories": tuple(
            {
                "pointer": advisory.pointer,
                "reason": advisory.reason,
            }
            for advisory in report.advisories
        ),
        "validation_errors": report.validation_errors,
    }


def _path_bytes(path: Path) -> bytes | None:
    if path.is_symlink():
        raise ValidationError(f"Article integration refuses symbolic links: {path}")
    if not path.exists():
        return None
    if not path.is_file():
        raise ValidationError(f"Article integration expected a file: {path}")
    return path.read_bytes()


class _ArticleTransaction:
    """Conditionally restore only files this integration invocation changed."""

    def __init__(
        self,
        root: Path,
        planned: dict[Path, bytes | None],
    ) -> None:
        self.root = root.resolve()
        self.before: dict[Path, bytes | None] = {}
        self.expected: dict[Path, bytes | None] = {}
        self.committed: dict[Path, bytes | None] = {}
        self.before_directories: set[Path] = set()
        for path, expected in planned.items():
            resolved = self._path(path)
            self.before.setdefault(resolved, _path_bytes(resolved))
            self.expected[resolved] = expected
            parent = resolved.parent
            while parent.is_relative_to(self.root):
                if parent.is_dir():
                    self.before_directories.add(parent)
                if parent == self.root:
                    break
                parent = parent.parent

    def commit(self, paths: Iterable[Path]) -> None:
        for path in paths:
            resolved = self._path(path)
            if resolved not in self.before:
                raise ValidationError(
                    "Article integration wrote a file its preflight did not plan: "
                    f"{resolved.relative_to(self.root)}"
                )
            current = _path_bytes(resolved)
            expected = self.expected[resolved]
            self.committed[resolved] = expected
            if current != expected:
                raise ValidationError(
                    "Article integration output changed after preflight; preserving "
                    f"the current bytes at {resolved.relative_to(self.root)}"
                )

    def rollback(self) -> tuple[Path, ...]:
        conflicts: list[Path] = []
        restored: list[Path] = []
        for path in sorted(self.committed):
            if _path_bytes(path) != self.committed[path]:
                conflicts.append(path)
                continue
            before = self.before[path]
            if before is None:
                path.unlink(missing_ok=True)
            else:
                _replace_file_bytes(path, before)
            restored.append(path)
        for directory in sorted(
            {
                parent
                for path in restored
                for parent in path.parents
                if parent.is_relative_to(self.root)
                and parent not in self.before_directories
            },
            key=lambda item: len(item.parts),
            reverse=True,
        ):
            if directory != self.root and directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        return tuple(conflicts)

    def _path(self, path: Path) -> Path:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise ValidationError(
                f"Article integration path escapes the project: {path}"
            ) from exc
        return resolved


def _replace_file_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.restore-",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary_path = Path(temporary)
        if temporary_path.exists():
            temporary_path.unlink()


def _write_full_cover_comparison(
    requests: Iterable[CoverProofRequest],
    destination: Path,
) -> None:
    """Write one deterministic contact sheet of every rendered full cover."""

    planned = tuple(requests)
    if not planned:
        raise ValidationError("A full-cover comparison requires at least one proof")
    cell_width = 300
    cell_height = 426
    label_height = 36
    columns = 3
    rows = (len(planned) + columns - 1) // columns
    sheet = Image.new(
        "RGB",
        (columns * cell_width, rows * (cell_height + label_height)),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    for index, request in enumerate(planned):
        proof = request.destination / "cover.png"
        if not proof.is_file():
            raise ValidationError(f"Cover Studio proof is missing: {proof}")
        with Image.open(proof) as source:
            image = source.convert("RGB")
            image.thumbnail((cell_width, cell_height))
        column = index % columns
        row = index // columns
        x = column * cell_width + (cell_width - image.width) // 2
        y = row * (cell_height + label_height)
        sheet.paste(image, (x, y))
        draw.text(
            (column * cell_width + 8, y + cell_height + 10),
            f"round {request.round_number} | {request.language} | {request.variant}",
            fill="black",
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        dir=destination.parent,
    )
    os.close(descriptor)
    try:
        sheet.save(temporary, format="PNG", optimize=False)
        os.replace(temporary, destination)
    finally:
        temporary_path = Path(temporary)
        if temporary_path.exists():
            temporary_path.unlink()


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
