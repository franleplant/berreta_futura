"""Edition workflow inspection and safe deterministic advancement.

The workflow module is the orchestration seam promised by
``docs/ARCHITECTURE.md``. It concentrates state knowledge that would otherwise
leak into CLI commands and conversational callers:

* :class:`Workflow.status` returns one stable report for the whole edition;
* :class:`Workflow.run` performs idempotent, reversible clerical work until it
  reaches authorial work or a human decision.

Capture and decision recording remain owned by the publishing module. A later
``Magazine`` integration can delegate its ``run`` and ``status`` operations to
this module while retaining its existing ``capture`` and review-recording
methods. The adapter is accepted rather than constructed by callers so tests
and the eventual compiler integration cross the same seam without import
cycles.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import tomllib
from typing import Any, Mapping, Protocol

from .capture import verify_snapshots
from .cover_art_candidates import (
    COVER_ART_VARIANTS,
    cover_art_candidate_record_path,
    hydrate_cover_art_candidates,
    scaffold_cover_art_candidates,
    validate_cover_art_candidates,
)
from .errors import ValidationError
from .evidence_review import (
    current_evidence_bindings,
    evidence_review_path,
    evidence_review_status,
    load_evidence_review,
)
from .extraction import load_extraction, verify_ledger_source_extractions
from .illustration import load_illustration_plan, validate_illustration_plan
from .io import load_structured
from .manifest import Edition, load_edition, load_translation
from .records import load_records
from .release import load_release_state, sync_release_state
from .render_review import load_render_review, visual_review_status
from .translate_stage import (
    _pin_advisories,
    _structural_validation,
    _untranslated_fields,
    stage_translation,
)


CHECKPOINT_ORDER = (
    "assignment",
    "coverage",
    "evidence",
    "translations",
    "cover",
    "illustrations",
    "fit",
    "validation",
    "build",
    "evidence_review",
    "render_review",
    "release",
)
CHECKPOINT_STATUSES = {"complete", "blocked", "not_applicable"}
ACTION_CLASSIFICATIONS = {"deterministic", "authorial", "human-review"}
ACTION_KINDS = {
    "reconcile_assignment",
    "stage_translations",
    "scaffold_cover",
    "build",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PREFLIGHT_READY_RESULTS = {"ready", "home_ready_studio_blocked"}


@dataclass(frozen=True)
class NextAction:
    """One precise recovery at a blocked checkpoint."""

    classification: str
    instruction: str
    command: str | None = None
    action: str | None = None

    def __post_init__(self) -> None:
        if self.classification not in ACTION_CLASSIFICATIONS:
            raise ValueError(f"Unknown workflow action classification: {self.classification}")
        if not self.instruction.strip():
            raise ValueError("Workflow next action requires an instruction")
        if self.action is not None and self.action not in ACTION_KINDS:
            raise ValueError(f"Unknown workflow action: {self.action}")
        if self.action is not None and self.classification != "deterministic":
            raise ValueError("Only deterministic workflow actions can be dispatched")

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "instruction": self.instruction,
            "command": self.command,
            "action": self.action,
        }


@dataclass(frozen=True)
class Checkpoint:
    """A stable workflow checkpoint and the facts that produced its verdict."""

    id: str
    status: str
    summary: str
    details: Mapping[str, Any]
    next_action: NextAction | None = None

    def __post_init__(self) -> None:
        if self.status not in CHECKPOINT_STATUSES:
            raise ValueError(f"Unknown workflow checkpoint status: {self.status}")
        if self.status == "blocked" and self.next_action is None:
            raise ValueError(f"Blocked checkpoint {self.id} requires a next action")
        if self.status != "blocked" and self.next_action is not None:
            raise ValueError(f"Unblocked checkpoint {self.id} cannot have a next action")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "summary": self.summary,
            "details": dict(self.details),
            "next_action": self.next_action.to_dict() if self.next_action else None,
        }


@dataclass(frozen=True)
class WorkflowReport:
    """The complete, JSON-stable status of one named edition."""

    edition_id: str
    lifecycle: str
    release_ready: bool
    checkpoints: tuple[Checkpoint, ...]
    schema_version: int = 1

    @property
    def next_checkpoint(self) -> Checkpoint | None:
        return next(
            (checkpoint for checkpoint in self.checkpoints if checkpoint.status == "blocked"),
            None,
        )

    def checkpoint(self, checkpoint_id: str) -> Checkpoint:
        for checkpoint in self.checkpoints:
            if checkpoint.id == checkpoint_id:
                return checkpoint
        raise KeyError(checkpoint_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "edition_id": self.edition_id,
            "lifecycle": self.lifecycle,
            "release_ready": self.release_ready,
            "next_checkpoint": self.next_checkpoint.id if self.next_checkpoint else None,
            "checkpoints": [checkpoint.to_dict() for checkpoint in self.checkpoints],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"


@dataclass(frozen=True)
class ProbeResult:
    """A non-writing deterministic check supplied through the adapter seam."""

    ok: bool
    summary: str
    details: Mapping[str, Any]


@dataclass(frozen=True)
class AdvanceResult:
    """What ``run`` changed and the exact state where it stopped."""

    report: WorkflowReport
    actions: tuple[str, ...]

    @property
    def changed(self) -> bool:
        return bool(self.actions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed": self.changed,
            "actions": list(self.actions),
            "report": self.report.to_dict(),
        }


class WorkflowAdapter(Protocol):
    """Internal seam for compiler-backed checks and deterministic writes."""

    def fit(self, root: Path, edition_id: str) -> ProbeResult:
        ...

    def validate(self, root: Path, edition_id: str) -> ProbeResult:
        ...

    def advance(
        self,
        root: Path,
        edition_id: str,
        checkpoint: Checkpoint,
    ) -> tuple[str, ...]:
        ...


class DefaultWorkflowAdapter:
    """Adapter over existing modules, imported lazily where cycles are possible."""

    def fit(self, root: Path, edition_id: str) -> ProbeResult:
        from .compiler import Magazine

        try:
            measurement = Magazine(root).measure(edition_id)
        except ValidationError as exc:
            return ProbeResult(False, "Page-budget measurement failed.", {"errors": exc.errors})
        return ProbeResult(
            measurement.ok,
            (
                "Every configured language fits its page budgets."
                if measurement.ok
                else "One or more page budgets are breached."
            ),
            measurement.to_dict(),
        )

    def validate(self, root: Path, edition_id: str) -> ProbeResult:
        from .compiler import Magazine

        try:
            Magazine(root).validate(edition_id)
        except ValidationError as exc:
            return ProbeResult(False, "Edition validation failed.", {"errors": exc.errors})
        return ProbeResult(True, "Edition validation passes.", {"errors": []})

    def advance(
        self,
        root: Path,
        edition_id: str,
        checkpoint: Checkpoint,
    ) -> tuple[str, ...]:
        action = checkpoint.next_action.action if checkpoint.next_action else None
        if action == "reconcile_assignment":
            paths = _project_paths(root)
            records = {
                record.id: record for record in load_records(paths["sources"])
            }
            requested = {
                str(source_id)
                for source_id in checkpoint.details.get(
                    "unassigned_manifest_source_ids", ()
                )
            }
            missing = sorted(requested - records.keys())
            if missing:
                raise ValidationError(
                    "Cannot assign manifest sources without records: "
                    + ", ".join(missing)
                )
            for source_id in sorted(requested):
                verify_snapshots(records[source_id], paths["sources"])
            state_path = paths["release_state"]
            state = load_release_state(
                state_path,
                default_open_id="001-the-work-left-to-us",
            )
            sync_release_state(
                state_path,
                set(state.assignments()) | requested,
                default_open_id="001-the-work-left-to-us",
                target_edition_id=edition_id,
            )
            return (f"Reconciled unassigned sources into collecting edition {edition_id}.",)
        if action == "stage_translations":
            languages = tuple(checkpoint.details.get("clerical_languages", ()))
            actions: list[str] = []
            for language in languages:
                report = stage_translation(root, edition_id, str(language))
                verb = "Updated" if report.changed else "Checked"
                actions.append(f"{verb} the {language} translation overlay.")
            return tuple(actions)
        if action == "scaffold_cover":
            edition_dir = root / "editions" / edition_id
            path = scaffold_cover_art_candidates(edition_dir)
            reading = str(checkpoint.details.get("suggested_editorial_reading") or "").strip()
            if reading:
                hydrate_cover_art_candidates(edition_dir, editorial_reading=reading)
            return (f"Scaffolded or hydrated {path.relative_to(root).as_posix()}.",)
        if action == "build":
            from .compiler import Magazine

            Magazine(root).build(edition_id)
            return (f"Built every configured language for {edition_id}.",)
        raise ValidationError(
            f"Workflow checkpoint {checkpoint.id} has no safe deterministic advance operation"
        )


class Workflow:
    """Deep module for edition status and safe deterministic advancement."""

    def __init__(self, root: Path, *, adapter: WorkflowAdapter | None = None):
        self.root = root.resolve()
        self.adapter = adapter or DefaultWorkflowAdapter()

    def status(self, edition_id: str) -> WorkflowReport:
        """Inspect an edition without writing files or advancing workflow state."""

        edition_id = _clean_edition_id(edition_id)
        snapshot = _Snapshot(self.root, edition_id)
        checkpoints: list[Checkpoint] = []

        assignment = snapshot.assignment_checkpoint()
        checkpoints.append(assignment)
        coverage = snapshot.coverage_checkpoint(assignment)
        checkpoints.append(coverage)
        evidence = snapshot.evidence_checkpoint(coverage)
        checkpoints.append(evidence)
        translations = snapshot.translations_checkpoint(evidence)
        checkpoints.append(translations)
        cover = snapshot.cover_checkpoint(translations)
        checkpoints.append(cover)
        illustrations = snapshot.illustrations_checkpoint(cover)
        checkpoints.append(illustrations)

        if _all_complete(checkpoints):
            fit_probe = self.adapter.fit(self.root, edition_id)
            fit = _probe_checkpoint(
                "fit",
                fit_probe,
                failed_classification="authorial",
                instruction=(
                    "Revise the manuscripts or declared page minima named by the measurement, "
                    "then run the fit check again."
                ),
                command=f"uv run --locked mag fit {edition_id}",
            )
        else:
            fit = _waiting_checkpoint("fit", checkpoints)
        checkpoints.append(fit)

        if _all_complete(checkpoints):
            validation_probe = self.adapter.validate(self.root, edition_id)
            validation = _probe_checkpoint(
                "validation",
                validation_probe,
                failed_classification="authorial",
                instruction=(
                    "Correct every reported validation error, then validate the edition again."
                ),
                command=f"uv run --locked mag validate {edition_id}",
            )
        else:
            validation = _waiting_checkpoint("validation", checkpoints)
        checkpoints.append(validation)

        build = snapshot.build_checkpoint(validation)
        checkpoints.append(build)
        evidence_review = snapshot.evidence_review_checkpoint(build)
        checkpoints.append(evidence_review)
        render_review = snapshot.render_review_checkpoint(build, evidence_review)
        checkpoints.append(render_review)

        release_ready = (
            snapshot.lifecycle == "collecting"
            and all(
                checkpoint.status == "complete"
                for checkpoint in checkpoints
                if checkpoint.id not in {"release"}
            )
        )
        release = snapshot.release_checkpoint(
            checkpoints,
            release_ready=release_ready,
        )
        checkpoints.append(release)
        return WorkflowReport(
            edition_id=edition_id,
            lifecycle=snapshot.lifecycle,
            release_ready=release_ready,
            checkpoints=tuple(checkpoints),
        )

    def run(self, edition_id: str) -> AdvanceResult:
        """Safely advance deterministic work and stop before judgment or release.

        The operation is idempotent. It dispatches only checkpoints named in
        ``_ACTIONABLE_CHECKPOINTS`` and only while their classification is
        ``deterministic``. A repeated report after an adapter action is treated
        as a refusal to loop, so a faulty adapter cannot spin forever.
        """

        edition_id = _clean_edition_id(edition_id)
        actions: list[str] = []
        seen: set[str] = set()
        for _ in range(len(CHECKPOINT_ORDER) + 1):
            report = self.status(edition_id)
            if report.lifecycle == "released":
                return AdvanceResult(report, tuple(actions))
            checkpoint = report.next_checkpoint
            if (
                checkpoint is None
                or checkpoint.next_action is None
                or checkpoint.next_action.classification != "deterministic"
                or checkpoint.next_action.action is None
            ):
                return AdvanceResult(report, tuple(actions))
            digest = hashlib.sha256(report.to_json().encode("utf-8")).hexdigest()
            if digest in seen:
                return AdvanceResult(report, tuple(actions))
            seen.add(digest)
            performed = self.adapter.advance(
                self.root,
                edition_id,
                checkpoint,
            )
            if not performed:
                return AdvanceResult(report, tuple(actions))
            actions.extend(performed)
        raise ValidationError(
            f"Workflow run exceeded the checkpoint limit for {edition_id}"
        )


class _Snapshot:
    """Read-only implementation behind the public workflow report."""

    def __init__(self, root: Path, edition_id: str):
        self.root = root
        self.edition_id = edition_id
        self.paths = _project_paths(root)
        self.edition_dir = self.paths["editions"] / edition_id
        self.manifest_path = self.edition_dir / "edition.yaml"
        self.manifest, self.manifest_errors = _read_mapping(self.manifest_path)
        self.records = _record_ids(self.paths["sources"])
        self.primary_language, self.languages = _publication_languages(root)
        self.release_state, self.release_errors = self._release_state()
        self.lifecycle = self._lifecycle()
        self.queued_source_ids = self._queued_source_ids()
        self.article_rows = _article_rows(self.manifest)
        self.article_source_ids = {
            str(row.get("id") or f"article-{index}"): source_ids
            for index, row in enumerate(self.article_rows, start=1)
            if (source_ids := _row_source_ids(row)) is not None
        }
        self.covered_source_ids = tuple(
            dict.fromkeys(
                source_id
                for source_ids in self.article_source_ids.values()
                for source_id in source_ids
            )
        )
        self.edition, self.edition_errors = self._load_edition()

    def _release_state(self):
        try:
            return (
                load_release_state(
                    self.paths["release_state"],
                    default_open_id="001-the-work-left-to-us",
                ),
                (),
            )
        except ValidationError as exc:
            return None, tuple(exc.errors)

    def _lifecycle(self) -> str:
        if self.release_state is None:
            return "unknown"
        if self.edition_id in self.release_state.collecting_edition_ids:
            return "collecting"
        if any(
            str(row.get("id")) == self.edition_id
            for row in self.release_state.released_editions
        ):
            return "released"
        return "unassigned"

    def _queued_source_ids(self) -> tuple[str, ...]:
        if self.release_state is None or self.lifecycle != "collecting":
            if self.release_state is None:
                return ()
            for row in self.release_state.released_editions:
                if str(row.get("id")) == self.edition_id:
                    return _row_source_ids(row) or ()
            return ()
        return self.release_state.queued_source_ids_for(self.edition_id)

    def _load_edition(self) -> tuple[Edition | None, tuple[str, ...]]:
        if self.manifest is None:
            return None, self.manifest_errors
        try:
            source_records = {
                record.id: record for record in load_records(self.paths["sources"])
            }
            edition = load_edition(
                self.root,
                self.edition_id,
                self.records,
                publication_name=_publication_name(self.root),
                source_records=source_records,
                allow_missing_art=True,
            )
        except ValidationError as exc:
            return None, tuple(exc.errors)
        return edition, ()

    def assignment_checkpoint(self) -> Checkpoint:
        details = {
            "lifecycle": self.lifecycle,
            "intake_edition_id": (
                self.release_state.intake_edition_id if self.release_state else None
            ),
            "collecting_edition_ids": (
                list(self.release_state.collecting_edition_ids)
                if self.release_state
                else []
            ),
            "release_state_errors": list(self.release_errors),
        }
        if self.release_state is None:
            return _blocked(
                "assignment",
                "The release ledger cannot be inspected.",
                details,
                "authorial",
                "Repair the release ledger errors shown in this checkpoint, then inspect again.",
            )
        if self.lifecycle == "unassigned":
            return _blocked(
                "assignment",
                "The edition is neither collecting nor released.",
                details,
                "human-review",
                (
                    f"Explicitly open or select {self.edition_id} as a collecting edition "
                    "with its intended issue number."
                ),
                f"uv run --locked mag collect {self.edition_id} --issue-number <number>",
            )
        manifest_sources = set(_string_list(self.manifest, "sources"))
        unassigned = sorted(
            source_id
            for source_id in manifest_sources
            if source_id in self.records
            and source_id not in self.release_state.assignments()
        )
        details["unassigned_manifest_source_ids"] = unassigned
        if unassigned:
            if (
                self.lifecycle == "collecting"
                and self.release_state.intake_edition_id == self.edition_id
            ):
                return _blocked(
                    "assignment",
                    f"{len(unassigned)} manifest source(s) are not assigned.",
                    details,
                    "deterministic",
                    (
                        f"Reconcile the unassigned captured sources into intake edition "
                        f"{self.edition_id}."
                    ),
                    action="reconcile_assignment",
                )
            return _blocked(
                "assignment",
                f"{len(unassigned)} manifest source(s) are not assigned.",
                details,
                "human-review",
                (
                    "Choose the collecting edition that should own the unassigned sources, "
                    "then reconcile intake there."
                ),
            )
        return _complete(
            "assignment",
            f"Edition is {self.lifecycle} in the release ledger.",
            details,
        )

    def coverage_checkpoint(self, assignment: Checkpoint) -> Checkpoint:
        queued = set(self.queued_source_ids)
        covered = set(self.covered_source_ids)
        missing = sorted(queued - covered)
        extra = sorted(covered - queued)
        unknown = sorted(covered - self.records)
        details = {
            "queued_source_ids": sorted(queued),
            "covered_source_ids": sorted(covered),
            "article_source_ids": {
                key: list(value) for key, value in sorted(self.article_source_ids.items())
            },
            "uncovered_source_ids": missing,
            "unexpected_source_ids": extra,
            "unknown_source_ids": unknown,
            "manifest_errors": list(self.manifest_errors),
        }
        if assignment.status != "complete":
            return _waiting_checkpoint("coverage", (assignment,), details=details)
        if self.manifest is None:
            return _blocked(
                "coverage",
                "The edition manifest is missing or unreadable.",
                details,
                "authorial",
                f"Create or repair {self.manifest_path.relative_to(self.root).as_posix()}.",
            )
        if self.lifecycle == "collecting" and (missing or extra or unknown):
            parts = []
            if missing:
                parts.append(f"{len(missing)} queued source(s) lack article coverage")
            if extra:
                parts.append(f"{len(extra)} covered source(s) are outside the queue")
            if unknown:
                parts.append(f"{len(unknown)} covered source(s) have no record")
            return _blocked(
                "coverage",
                "; ".join(parts) + ".",
                details,
                "authorial",
                (
                    "Make the collecting queue exactly equal the union of "
                    "articles[].source_ids, assigning every source to one article."
                ),
            )
        return _complete(
            "coverage",
            f"{len(covered)} source(s) are represented by {len(self.article_source_ids)} article(s).",
            details,
        )

    def evidence_checkpoint(self, coverage: Checkpoint) -> Checkpoint:
        source_ids = sorted(set(self.queued_source_ids) | set(self.covered_source_ids))
        extraction_rows: dict[str, dict[str, Any]] = {}
        extraction_errors: list[str] = []
        for source_id in source_ids:
            try:
                extraction = load_extraction(self.paths["sources"], source_id)
            except ValidationError as exc:
                extraction = None
                extraction_errors.extend(exc.errors)
                extraction_rows[source_id] = {
                    "status": "invalid",
                    "path": _relative(
                        self.root,
                        self.paths["sources"] / source_id / "extracted.md",
                    ),
                    "errors": list(exc.errors),
                }
                continue
            extraction_rows[source_id] = {
                "status": "complete" if extraction else "missing",
                "path": _relative(
                    self.root,
                    self.paths["sources"] / source_id / "extracted.md",
                ),
                "body_sha256": extraction.body_sha256 if extraction else None,
                "file_sha256": extraction.file_sha256 if extraction else None,
            }

        ledger_rows: dict[str, dict[str, Any]] = {}
        ledger_errors: list[str] = []
        require_extractions = self.lifecycle == "collecting"
        for index, row in enumerate(self.article_rows, start=1):
            article_id = str(row.get("id") or f"article-{index}")
            ledger_path = _declared_path(self.root, self.edition_dir, row.get("fidelity"))
            source_tuple = _row_source_ids(row) or ()
            entry: dict[str, Any] = {
                "path": _relative(self.root, ledger_path),
                "status": "missing",
                "source_ids": list(source_tuple),
            }
            if ledger_path is None or not ledger_path.is_file():
                ledger_rows[article_id] = entry
                continue
            try:
                verify_ledger_source_extractions(
                    ledger_path,
                    self.paths["sources"],
                    require_extractions=require_extractions,
                    article_source_ids=source_tuple,
                )
            except ValidationError as exc:
                entry["status"] = "invalid"
                entry["errors"] = list(exc.errors)
                ledger_errors.extend(exc.errors)
            else:
                entry["status"] = "complete"
            ledger_rows[article_id] = entry
        missing_extractions = sorted(
            source_id
            for source_id, row in extraction_rows.items()
            if row["status"] != "complete"
        )
        incomplete_ledgers = sorted(
            article_id
            for article_id, row in ledger_rows.items()
            if row["status"] != "complete"
        )
        details = {
            "extractions": extraction_rows,
            "ledgers": ledger_rows,
            "missing_or_invalid_extractions": missing_extractions,
            "missing_or_invalid_ledgers": incomplete_ledgers,
            "errors": extraction_errors + ledger_errors,
        }
        if coverage.status != "complete":
            return _waiting_checkpoint("evidence", (coverage,), details=details)
        if require_extractions and (missing_extractions or incomplete_ledgers):
            return _blocked(
                "evidence",
                (
                    f"{len(missing_extractions)} extraction(s) and "
                    f"{len(incomplete_ledgers)} fidelity ledger(s) need work."
                ),
                details,
                "authorial",
                (
                    "Create each named extracted.md from its committed raw bundle, then "
                    "author or repair each fidelity ledger and refresh its derivable pins "
                    f"with `uv run --locked mag pin {self.edition_id}`."
                ),
            )
        return _complete(
            "evidence",
            "Source extractions and article fidelity ledgers are complete.",
            details,
        )

    def translations_checkpoint(self, evidence: Checkpoint) -> Checkpoint:
        per_language: dict[str, Any] = {}
        clerical: list[str] = []
        authorial: list[str] = []
        for language in self.languages:
            if language == self.primary_language:
                per_language[language] = {"status": "source_language"}
                continue
            overlay = self.edition_dir / "translations" / language / "edition.yaml"
            row: dict[str, Any] = {
                "manifest_path": _relative(self.root, overlay),
                "manifest_present": overlay.is_file(),
                "advisories": [],
                "placeholders": [],
                "validation_errors": [],
            }
            if not overlay.is_file() or self.edition is None:
                if not overlay.is_file():
                    row["status"] = "needs_staging"
                    clerical.append(language)
                else:
                    row["status"] = "unavailable"
                    row["validation_errors"] = list(self.edition_errors)
                    authorial.append(language)
                per_language[language] = row
                continue
            try:
                data = load_structured(overlay)
                advisories = _pin_advisories(self.edition, data)
                placeholders = _untranslated_fields(
                    self.root,
                    self.edition,
                    overlay.parent,
                )
                errors = _structural_validation(
                    self.root,
                    self.edition,
                    language,
                )
            except (OSError, ValidationError) as exc:
                messages = (
                    exc.errors if isinstance(exc, ValidationError) else [str(exc)]
                )
                row["status"] = "unavailable"
                row["validation_errors"] = list(messages)
                authorial.append(language)
                per_language[language] = row
                continue
            row["advisories"] = [
                {"pointer": item.pointer, "reason": item.reason} for item in advisories
            ]
            row["placeholders"] = [
                {
                    "pointer": item.pointer,
                    "path": _relative(self.root, item.path),
                    "english": item.english,
                }
                for item in placeholders
            ]
            row["validation_errors"] = list(errors)
            # A stale pin is evidence that English moved under translated
            # prose. Staging would refresh that pin and return an advisory,
            # but the advisory is not a durable artifact. Do not auto-stage
            # it here or the next status could mistake old prose for current
            # prose. Stop for the translator while the mismatch is still
            # visible. English-equal placeholders are also authorial even
            # when the translation loader reports a related validation
            # error: staging cannot translate that prose, so the exact
            # placeholder pointers must win over the generic structural
            # failure. Errors without placeholders remain safe to reconcile.
            if advisories:
                row["status"] = "needs_retranslation"
                authorial.append(language)
            elif placeholders:
                row["status"] = "needs_translation"
                authorial.append(language)
            elif errors:
                row["status"] = "needs_staging"
                clerical.append(language)
            else:
                row["status"] = "complete"
            per_language[language] = row
        details = {
            "primary_language": self.primary_language,
            "configured_languages": list(self.languages),
            "languages": per_language,
            "clerical_languages": sorted(set(clerical)),
            "authorial_languages": sorted(set(authorial)),
        }
        if evidence.status != "complete":
            return _waiting_checkpoint("translations", (evidence,), details=details)
        if clerical:
            return _blocked(
                "translations",
                f"{len(set(clerical))} translation overlay(s) need deterministic staging.",
                details,
                "deterministic",
                (
                    "Stage each named overlay to reconcile structure and refresh derivable "
                    "pins without overwriting translated manuscripts."
                ),
                " && ".join(
                    f"uv run --locked mag translate {self.edition_id} {language}"
                    for language in sorted(set(clerical))
                ),
                action="stage_translations",
            )
        if authorial:
            return _blocked(
                "translations",
                f"{len(set(authorial))} translation overlay(s) still need human translation.",
                details,
                "authorial",
                (
                    "Run the translate command for each named language to print and retain "
                    "its re-translation advisories, then translate every placeholder and "
                    "resolve every listed validation error."
                ),
                " && ".join(
                    f"uv run --locked mag translate {self.edition_id} {language}"
                    for language in sorted(set(authorial))
                ),
            )
        return _complete(
            "translations",
            "Every configured language is translated and current.",
            details,
        )

    def cover_checkpoint(self, translations: Checkpoint) -> Checkpoint:
        path = cover_art_candidate_record_path(self.edition_dir)
        rounds = _cover_rounds(self.root, self.edition_dir)
        manifest_cover = (self.manifest or {}).get("cover")
        if not isinstance(manifest_cover, dict):
            manifest_cover = {}
        selected_art = str(
            manifest_cover.get("art_path") or ""
        ).strip()
        reading = _editorial_reading(self.manifest or {})
        details: dict[str, Any] = {
            "record_path": _relative(self.root, path),
            "record_present": path.is_file(),
            "rounds": rounds,
            "selection_status": None,
            "selected_art_path": selected_art or None,
            "selected_variant": None,
            "variants": {},
            "errors": [],
            "suggested_editorial_reading": reading,
        }
        if translations.status != "complete":
            return _waiting_checkpoint("cover", (translations,), details=details)
        if self._is_historical_release():
            return _complete(
                "cover",
                "Released schema-1 edition keeps its historical cover artifacts.",
                details,
            )
        if self.lifecycle == "released" and not path.is_file():
            return _complete(
                "cover",
                "Released historical edition has no cover candidate record.",
                details,
            )
        if not path.is_file():
            return _blocked(
                "cover",
                "The canonical three-branch cover candidate record is missing.",
                details,
                "deterministic",
                "Scaffold the synthetic, art-directed, and wildcard cover branches.",
                f"uv run --locked mag illustrate {self.edition_id}",
                action="scaffold_cover",
            )
        try:
            data = load_structured(path)
        except ValidationError as exc:
            details["errors"] = list(exc.errors)
            return _blocked(
                "cover",
                "The cover candidate record is unreadable.",
                details,
                "authorial",
                "Repair the cover candidate YAML errors listed here.",
            )
        details["selection_status"] = data.get("selection_status")
        details["round"] = data.get("round")
        variants = data.get("variants") if isinstance(data.get("variants"), dict) else {}
        for variant in COVER_ART_VARIANTS:
            row = variants.get(variant) if isinstance(variants.get(variant), dict) else {}
            declared = str(row.get("art_path") or "")
            candidate = (self.edition_dir / declared).resolve() if declared else None
            details["variants"][variant] = {
                "art_path": declared or None,
                "present": bool(candidate and candidate.is_file()),
                "asset_sha256": row.get("asset_sha256"),
                "generation_method": row.get("generation_method"),
            }
            if declared and declared == selected_art:
                details["selected_variant"] = variant
        current_reading = str(data.get("editorial_reading") or "")
        if current_reading.startswith("TODO: define the editorial reading for "):
            return _blocked(
                "cover",
                "The cover brief still has its collection placeholder.",
                details,
                "deterministic",
                "Hydrate the cover brief from the edition title and cover deck.",
                f"uv run --locked mag illustrate {self.edition_id}",
                action="scaffold_cover",
            )
        try:
            validate_cover_art_candidates(
                self.edition_dir,
                record_path=path,
                selected_art_path=(
                    selected_art
                    if str(data.get("selection_status") or "") == "selected"
                    else None
                ),
            )
        except ValidationError as exc:
            details["errors"] = list(exc.errors)
            return _blocked(
                "cover",
                "The three cover branches are incomplete or invalid.",
                details,
                "authorial",
                (
                    "Generate and pin one distinct typography-free PNG for each named "
                    "cover branch, then update the candidate record."
                ),
                f"uv run --locked mag illustrate {self.edition_id}",
            )
        if str(data.get("selection_status") or "") != "selected":
            return _blocked(
                "cover",
                "Three valid cover options await an editor's selection.",
                details,
                "human-review",
                (
                    "Compare the current cover round, select one variant, set "
                    "selection_status to selected, and point cover.art_path at it."
                ),
            )
        return _complete(
            "cover",
            f"Cover variant {details['selected_variant'] or selected_art} is selected and pinned.",
            details,
        )

    def illustrations_checkpoint(self, cover: Checkpoint) -> Checkpoint:
        raw_plan = (self.manifest or {}).get("art_direction_path")
        plan_path = _declared_path(self.root, self.edition_dir, raw_plan)
        details: dict[str, Any] = {
            "declared": bool(raw_plan),
            "plan_path": _relative(self.root, plan_path),
            "direction": None,
            "assets": [],
            "errors": [],
            "prompt_package": _relative(
                self.root,
                self.paths["output"] / self.edition_id / "illustration-prompts",
            ),
        }
        if cover.status != "complete":
            return _waiting_checkpoint("illustrations", (cover,), details=details)
        if self._is_historical_release():
            return _complete(
                "illustrations",
                "Released schema-1 edition keeps its historical illustration artifacts.",
                details,
            )
        if self.edition is None:
            details["errors"] = list(self.edition_errors)
            return _blocked(
                "illustrations",
                "Illustrations cannot be inspected until the edition manifest loads.",
                details,
                "authorial",
                "Repair the manifest errors listed here, then inspect the illustration plan again.",
            )
        if not raw_plan:
            if self.lifecycle == "released":
                return _complete(
                    "illustrations",
                    "Released historical edition has no authored illustration plan.",
                    details,
                )
            return _blocked(
                "illustrations",
                "The collecting edition has no internal illustration plan.",
                details,
                "authorial",
                (
                    "Author art_direction_path with a coherent direction and explicit "
                    "article-tail or closing-plate assets."
                ),
            )
        try:
            plan = load_illustration_plan(self.root, self.edition)
        except ValidationError as exc:
            details["errors"] = list(exc.errors)
            return _blocked(
                "illustrations",
                "The illustration plan is invalid.",
                details,
                "authorial",
                "Repair the illustration plan fields and inventory errors listed here.",
            )
        if plan is not None:
            details["direction"] = {
                "name": plan.direction.name,
                "visual_language": plan.direction.visual_language,
                "palette": plan.direction.palette,
            }
            details["assets"] = [
                {
                    "id": asset.id,
                    "role": asset.role,
                    "article_id": asset.article_id,
                    "plate_index": asset.plate_index,
                    "art_path": _relative(self.root, asset.art_path),
                    "present": asset.art_path.is_file(),
                }
                for asset in plan.assets
            ]
        try:
            validate_illustration_plan(self.root, self.edition)
        except ValidationError as exc:
            details["errors"] = list(exc.errors)
            return _blocked(
                "illustrations",
                "Planned internal illustrations are missing or invalid.",
                details,
                "authorial",
                (
                    "Generate or correct every planned raster, preserving the declared "
                    "direction, role, dimensions, alt text, and manifest wiring."
                ),
                f"uv run --locked mag illustrate {self.edition_id}",
            )
        return _complete(
            "illustrations",
            f"{len(details['assets'])} planned internal illustration(s) are valid.",
            details,
        )

    def _is_historical_release(self) -> bool:
        return (
            self.lifecycle == "released"
            and (self.manifest or {}).get("schema_version", 1) == 1
        )

    def build_checkpoint(self, validation: Checkpoint) -> Checkpoint:
        language_rows: dict[str, Any] = {}
        missing: list[str] = []
        stale: list[str] = []
        machine_failures: list[str] = []
        for language in self.languages:
            package = (
                self.paths["output"] / self.edition_id
                if language == self.primary_language
                else self.paths["output"] / self.edition_id / language
            )
            required = {
                "reader": package / "reader.pdf",
                "booklet": package / "home" / "booklet-a4.pdf",
                "manifest": package / "edition-manifest.json",
                "render_critic": package / "render-critic.json",
                "preflight": package / "preflight.json",
            }
            absent = [
                name for name, path in required.items() if not path.is_file()
            ]
            drift: list[str] = []
            machine_result = None
            preflight_result = None
            artifact_errors: list[str] = []
            if not absent:
                try:
                    build_manifest = load_structured(required["manifest"])
                    variant = (
                        self.edition
                        if language == self.primary_language
                        else (
                            load_translation(self.root, self.edition, language)
                            if self.edition is not None
                            else None
                        )
                    )
                    if variant is None:
                        drift.extend(self.edition_errors)
                    else:
                        expected_inputs = _current_build_input_paths(
                            self.root,
                            self.paths,
                            self.edition,
                            variant,
                            language=language,
                            primary_language=self.primary_language,
                        )
                        drift.extend(
                            _build_input_drift(
                                self.root,
                                variant.raw,
                                build_manifest,
                                expected_inputs=expected_inputs,
                                language=language,
                                primary_language=self.primary_language,
                            )
                        )
                except ValidationError as exc:
                    drift.extend(exc.errors)
                try:
                    critic = load_structured(required["render_critic"])
                    machine_result = critic.get("result")
                    if critic.get("schema_version") != 1:
                        artifact_errors.append(
                            "render critic schema_version must be 1"
                        )
                except ValidationError as exc:
                    artifact_errors.extend(exc.errors)
                try:
                    preflight = load_structured(required["preflight"])
                    preflight_result = preflight.get("result")
                    if preflight.get("schema_version") != 1:
                        artifact_errors.append("preflight schema_version must be 1")
                    if preflight_result not in _PREFLIGHT_READY_RESULTS:
                        artifact_errors.append(
                            f"unsupported preflight result: {preflight_result!r}"
                        )
                except ValidationError as exc:
                    artifact_errors.extend(exc.errors)
                if (
                    machine_result != "pass"
                    or preflight_result not in _PREFLIGHT_READY_RESULTS
                    or artifact_errors
                ):
                    machine_failures.append(language)
            if absent:
                missing.append(language)
            if drift:
                stale.append(language)
            language_rows[language] = {
                "package_path": _relative(self.root, package),
                "missing_artifacts": absent,
                "stale_inputs": drift,
                "machine_result": machine_result,
                "preflight_result": preflight_result,
                "artifact_errors": artifact_errors,
            }
        details = {
            "languages": language_rows,
            "missing_languages": missing,
            "stale_languages": stale,
            "machine_failure_languages": machine_failures,
        }
        if validation.status != "complete":
            return _waiting_checkpoint("build", (validation,), details=details)
        if machine_failures:
            return _blocked(
                "build",
                "The build exists but its machine render critic reports failures.",
                details,
                "authorial",
                (
                    "Inspect the named render-critic findings, fix the manuscripts or "
                    "layout, then rebuild every configured language."
                ),
                f"uv run --locked mag build {self.edition_id}",
            )
        if missing or stale:
            return _blocked(
                "build",
                "Build artifacts are missing or stale for configured languages.",
                details,
                "deterministic",
                "Build every configured language from the current validated inputs.",
                f"uv run --locked mag build {self.edition_id}",
                action="build",
            )
        return _complete(
            "build",
            "Current build and machine render-critic artifacts exist for every language.",
            details,
        )

    def evidence_review_checkpoint(self, build: Checkpoint) -> Checkpoint:
        details: dict[str, Any]
        if self.edition is None:
            details = {"status": "unavailable", "errors": list(self.edition_errors)}
        else:
            try:
                bindings = current_evidence_bindings(
                    self.edition,
                    self.paths["sources"],
                    require_extractions=False,
                )
                record = load_evidence_review(
                    evidence_review_path(self.paths["editions"], self.edition_id),
                    edition_id=self.edition_id,
                )
                details = evidence_review_status(
                    record,
                    edition_id=self.edition_id,
                    bindings=bindings,
                )
            except ValidationError as exc:
                details = {"status": "unavailable", "errors": list(exc.errors)}
        if build.status != "complete":
            return _waiting_checkpoint("evidence_review", (build,), details=details)
        if self.lifecycle == "released" and details.get("status") == "required_before_release":
            return _complete(
                "evidence_review",
                "No evidence review is required retroactively for this released edition.",
                details,
            )
        if details.get("status") != "approved":
            return _blocked(
                "evidence_review",
                f"Evidence review status is {details.get('status', 'unavailable')}.",
                details,
                "human-review",
                (
                    "Audit each manuscript against its fidelity ledger and committed "
                    "extractions, then record the exact reviewed article bindings."
                ),
                (
                    f"uv run --locked mag review record {self.edition_id} "
                    "--kind evidence"
                ),
            )
        return _complete(
            "evidence_review",
            "The hash-bound evidence review is approved and current.",
            details,
        )

    def render_review_checkpoint(
        self,
        build: Checkpoint,
        evidence_review: Checkpoint,
    ) -> Checkpoint:
        path = self.edition_dir / "reviews" / "render.yaml"
        try:
            record = load_render_review(path, edition_id=self.edition_id)
        except ValidationError as exc:
            record = None
            load_errors = list(exc.errors)
        else:
            load_errors = []
        languages: dict[str, Any] = {}
        for language in self.languages:
            package = (
                self.paths["output"] / self.edition_id
                if language == self.primary_language
                else self.paths["output"] / self.edition_id / language
            )
            reader = package / "reader.pdf"
            booklet = package / "home" / "booklet-a4.pdf"
            report_path = package / "render-critic.json"
            if not reader.is_file() or not booklet.is_file() or not report_path.is_file():
                languages[language] = {"status": "not_built"}
                continue
            try:
                machine = load_structured(report_path).get("result")
                visual = visual_review_status(
                    record,
                    edition_id=self.edition_id,
                    language=language,
                    reader_pdf=reader,
                    booklet_pdf=booklet,
                )
            except ValidationError as exc:
                languages[language] = {
                    "status": "unavailable",
                    "errors": list(exc.errors),
                }
                continue
            languages[language] = {
                "machine_result": machine,
                **visual,
            }
        details = {
            "record_path": _relative(self.root, path),
            "errors": load_errors,
            "languages": languages,
        }
        prerequisites = (build, evidence_review)
        if not _all_complete(prerequisites):
            return _waiting_checkpoint("render_review", prerequisites, details=details)
        incomplete = {
            language: row.get("status")
            for language, row in languages.items()
            if row.get("status") != "approved" or row.get("machine_result") != "pass"
        }
        if incomplete:
            return _blocked(
                "render_review",
                "The independent render review is missing, stale, or requests changes.",
                details,
                "human-review",
                (
                    "Inspect every reader and booklet contact sheet for every configured "
                    "language, resolve findings, then record the review against those PDFs."
                ),
                f"uv run --locked mag review record {self.edition_id}",
            )
        return _complete(
            "render_review",
            "The machine and independent render reviews pass for every language.",
            details,
        )

    def release_checkpoint(
        self,
        checkpoints: list[Checkpoint],
        *,
        release_ready: bool,
    ) -> Checkpoint:
        details = {
            "lifecycle": self.lifecycle,
            "release_ready": release_ready,
            "blocking_checkpoint_ids": [
                checkpoint.id
                for checkpoint in checkpoints
                if checkpoint.status == "blocked"
            ],
        }
        if self.lifecycle == "released":
            return _complete(
                "release",
                "Edition is already released.",
                details,
            )
        if release_ready:
            return _blocked(
                "release",
                "All release gates pass; final release remains an explicit human decision.",
                details,
                "human-review",
                (
                    "Confirm the edition looks finished, then run the single finishing "
                    "command. It owns the stable id, rebuild, freeze, and next collection."
                ),
                f"uv run --locked mag finish {self.edition_id}",
            )
        blocker = next(
            (checkpoint for checkpoint in checkpoints if checkpoint.status == "blocked"),
            None,
        )
        if blocker is None or blocker.next_action is None:
            return _blocked(
                "release",
                "Release readiness could not be established.",
                details,
                "human-review",
                "Inspect the edition state and establish its collecting assignment.",
            )
        return _blocked(
            "release",
            f"Release waits for checkpoint {blocker.id}.",
            details,
            blocker.next_action.classification,
            f"Resolve {blocker.id}: {blocker.next_action.instruction}",
            blocker.next_action.command,
        )


def _probe_checkpoint(
    checkpoint_id: str,
    probe: ProbeResult,
    *,
    failed_classification: str,
    instruction: str,
    command: str,
) -> Checkpoint:
    if probe.ok:
        return _complete(checkpoint_id, probe.summary, probe.details)
    return _blocked(
        checkpoint_id,
        probe.summary,
        probe.details,
        failed_classification,
        instruction,
        command,
    )


def _waiting_checkpoint(
    checkpoint_id: str,
    prerequisites: tuple[Checkpoint, ...] | list[Checkpoint],
    *,
    details: Mapping[str, Any] | None = None,
) -> Checkpoint:
    blocker = next(
        (checkpoint for checkpoint in prerequisites if checkpoint.status == "blocked"),
        None,
    )
    if blocker is None or blocker.next_action is None:
        return Checkpoint(
            checkpoint_id,
            "not_applicable",
            "This checkpoint has no applicable work.",
            details or {},
        )
    return _blocked(
        checkpoint_id,
        f"Waiting for checkpoint {blocker.id}.",
        details or {},
        blocker.next_action.classification,
        f"Resolve {blocker.id}: {blocker.next_action.instruction}",
        blocker.next_action.command,
    )


def _complete(
    checkpoint_id: str,
    summary: str,
    details: Mapping[str, Any],
) -> Checkpoint:
    return Checkpoint(checkpoint_id, "complete", summary, details)


def _blocked(
    checkpoint_id: str,
    summary: str,
    details: Mapping[str, Any],
    classification: str,
    instruction: str,
    command: str | None = None,
    *,
    action: str | None = None,
) -> Checkpoint:
    return Checkpoint(
        checkpoint_id,
        "blocked",
        summary,
        details,
        NextAction(classification, instruction, command, action),
    )


def _all_complete(checkpoints: tuple[Checkpoint, ...] | list[Checkpoint]) -> bool:
    return all(checkpoint.status == "complete" for checkpoint in checkpoints)


def _clean_edition_id(edition_id: str) -> str:
    clean = str(edition_id or "").strip()
    if not clean or clean in {".", ".."} or "/" in clean or "\\" in clean:
        raise ValidationError(f"Invalid edition id: {edition_id!r}")
    return clean


def _read_mapping(path: Path) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    if not path.is_file():
        return None, (f"Edition manifest not found: {path}",)
    try:
        return load_structured(path), ()
    except ValidationError as exc:
        return None, tuple(exc.errors)


def _project_config(root: Path) -> dict[str, Any]:
    path = root / "magazine.toml"
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValidationError(f"Cannot read {path}: {exc}") from exc


def _project_paths(root: Path) -> dict[str, Path]:
    config = _project_config(root)
    paths = config.get("paths") if isinstance(config.get("paths"), dict) else {}
    return {
        "sources": root / str(paths.get("sources") or "library/sources"),
        "editions": root / str(paths.get("editions") or "editions"),
        "output": root / str(paths.get("output") or "output"),
        "release_state": root
        / str(paths.get("release_state") or "library/release-state.yaml"),
    }


def _publication_name(root: Path) -> str:
    config = _project_config(root)
    publication = (
        config.get("publication")
        if isinstance(config.get("publication"), dict)
        else {}
    )
    return str(publication.get("name") or "Magazine").strip()


def _publication_languages(root: Path) -> tuple[str, tuple[str, ...]]:
    config = _project_config(root)
    publication = (
        config.get("publication")
        if isinstance(config.get("publication"), dict)
        else {}
    )
    primary = str(publication.get("language") or "en").strip()
    configured = publication.get("languages", [primary])
    if not isinstance(configured, list) or not configured:
        return primary, (primary,)
    languages = tuple(
        dict.fromkeys(str(value).strip() for value in configured if str(value).strip())
    )
    return primary, languages if primary in languages else (primary, *languages)


def _record_ids(sources_dir: Path) -> set[str]:
    if not sources_dir.is_dir():
        return set()
    return {
        path.parent.name
        for path in sources_dir.glob("*/record.y*ml")
        if path.is_file()
    }


def _article_rows(manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = (manifest or {}).get("articles")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _row_source_ids(row: dict[str, Any]) -> tuple[str, ...] | None:
    values = row.get("source_ids")
    if not isinstance(values, list):
        return None
    if any(not isinstance(value, str) or not value.strip() for value in values):
        return None
    return tuple(values)


def _string_list(data: dict[str, Any] | None, key: str) -> tuple[str, ...]:
    values = (data or {}).get(key)
    if not isinstance(values, list):
        return ()
    return tuple(str(value) for value in values)


def _declared_path(
    root: Path,
    edition_dir: Path,
    value: object,
) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidates = ((root / value).resolve(), (edition_dir / value).resolve())
    for candidate in candidates:
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.exists():
            return candidate
    candidate = candidates[0] if "/" in value else candidates[1]
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _relative(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _editorial_reading(manifest: dict[str, Any]) -> str:
    cover = manifest.get("cover") if isinstance(manifest.get("cover"), dict) else {}
    values = (
        str(manifest.get("title") or "").strip(),
        str(
            cover.get("deck")
            or manifest.get("subtitle")
            or cover.get("back_text")
            or ""
        ).strip(),
    )
    return ". ".join(value.rstrip(".") for value in values if value) + (
        "." if any(values) else ""
    )


def _cover_rounds(root: Path, edition_dir: Path) -> list[dict[str, Any]]:
    rounds: list[dict[str, Any]] = []
    for path in sorted((edition_dir / "art").glob("cover-candidates*.yaml")):
        try:
            data = load_structured(path)
        except ValidationError as exc:
            rounds.append(
                {
                    "path": _relative(root, path),
                    "round": None,
                    "selection_status": "invalid",
                    "errors": list(exc.errors),
                }
            )
            continue
        rounds.append(
            {
                "path": _relative(root, path),
                "round": data.get("round"),
                "selection_status": data.get("selection_status"),
            }
        )
    return sorted(
        rounds,
        key=lambda row: (
            row.get("round") is None,
            int(row["round"]) if str(row.get("round", "")).isdigit() else 0,
            str(row.get("path")),
        ),
    )


def _build_input_drift(
    root: Path,
    current_manifest: dict[str, Any] | None,
    build_manifest: dict[str, Any],
    *,
    expected_inputs: set[str],
    language: str,
    primary_language: str,
) -> list[str]:
    drift: list[str] = []
    if build_manifest.get("schema_version") != 1:
        drift.append("build manifest schema_version must be 1")
    publication = build_manifest.get("publication")
    if not isinstance(publication, dict):
        drift.append("build manifest publication must be a mapping")
    elif publication.get("language") != language:
        drift.append(
            f"build manifest language is {publication.get('language')!r}, expected {language!r}"
        )
    if not isinstance(build_manifest.get("edition"), dict):
        drift.append("build manifest edition must be a mapping")
    if current_manifest is not None and build_manifest.get("edition") != current_manifest:
        drift.append("edition.yaml content differs from the built edition")
    inputs = build_manifest.get("inputs")
    if not isinstance(inputs, dict):
        return [*drift, "build manifest has no inputs mapping"]

    drift.extend(
        _build_input_shape_errors(
            inputs,
            language=language,
            primary_language=primary_language,
        )
    )
    bindings, binding_errors = _hash_bindings(inputs)
    drift.extend(binding_errors)
    declared_paths: set[str] = set()
    for path_value, expected in bindings:
        if not isinstance(path_value, str) or not path_value.strip():
            drift.append(f"input binding has invalid path: {path_value!r}")
            continue
        if Path(path_value).is_absolute():
            drift.append(f"input path must be project-relative: {path_value}")
            continue
        path = (root / path_value).resolve()
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            drift.append(f"input escapes project root: {path_value}")
            continue
        declared_paths.add(relative)
        if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
            drift.append(f"input has invalid sha256: {path_value}")
            continue
        if not path.is_file():
            drift.append(f"missing input: {path_value}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            drift.append(f"changed input: {path_value}")
    drift.extend(
        f"missing input binding: {path}"
        for path in sorted(expected_inputs - declared_paths)
    )
    drift.extend(
        f"unexpected input binding: {path}"
        for path in sorted(declared_paths - expected_inputs)
    )
    return sorted(set(drift))


def _current_build_input_paths(
    root: Path,
    paths: Mapping[str, Path],
    base: Edition | None,
    variant: Edition,
    *,
    language: str,
    primary_language: str,
) -> set[str]:
    """Return every file input the compiler records for one language build."""

    if base is None:
        raise ValidationError("Base edition is unavailable for build inventory")
    inputs: set[Path] = set()

    def add(path: Path | None) -> None:
        if path is not None:
            inputs.add(path)

    plan = load_illustration_plan(root, base)
    if plan is not None:
        add(plan.path)
        add(plan.direction_path)
        inputs.update(plan.direction.reference_paths)
    add(variant.editorial.path if variant.editorial else None)
    add(variant.cover_art)
    fidelity_status = (
        paths["editions"] / base.id / "fidelity" / "source-edition-status.yaml"
    )
    add(fidelity_status if fidelity_status.is_file() else None)
    for section in variant.sections:
        add(section.path)
    for article in variant.articles:
        add(article.manuscript)
        add(article.fidelity)
        add(article.opener_art.path if article.opener_art else None)
        add(article.tail_art)
    for plate in variant.closing_plates:
        add(plate.art_path)
    source_ids = set(_string_list(base.raw, "sources")) | {
        source_id for article in base.articles for source_id in article.source_ids
    }
    for source_id in source_ids:
        add(paths["sources"] / source_id / "record.yaml")
    if language != primary_language:
        add(paths["editions"] / base.id / "translations" / language / "edition.yaml")

    relative: set[str] = set()
    for path in inputs:
        try:
            relative.add(path.resolve().relative_to(root).as_posix())
        except ValueError as exc:
            raise ValidationError(f"Build input escapes project root: {path}") from exc
    return relative


def _build_input_shape_errors(
    inputs: dict[str, Any],
    *,
    language: str,
    primary_language: str,
) -> list[str]:
    required = {
        "illustration_plan",
        "illustration_direction",
        "illustration_references",
        "cover_faces",
        "editorial",
        "cover_art",
        "translation_manifest",
        "fidelity_status",
        "sections",
        "articles",
        "closing_plates",
        "sources",
    }
    errors = [
        f"build manifest inputs missing category: {key}"
        for key in sorted(required - inputs.keys())
    ]
    for key in (
        "illustration_references",
        "sections",
        "articles",
        "closing_plates",
        "sources",
    ):
        if key in inputs and not isinstance(inputs[key], list):
            errors.append(f"build manifest inputs.{key} must be a list")
    for key in (
        "illustration_plan",
        "illustration_direction",
        "editorial",
        "cover_art",
        "translation_manifest",
        "fidelity_status",
    ):
        value = inputs.get(key)
        if value is not None and not isinstance(value, dict):
            errors.append(
                f"build manifest inputs.{key} must be a file binding or null"
            )
    translation = inputs.get("translation_manifest")
    if language == primary_language and translation is not None:
        errors.append("source-language build must not declare a translation manifest")
    if language != primary_language and not isinstance(translation, dict):
        errors.append("translated build requires a translation manifest binding")
    cover_faces = inputs.get("cover_faces")
    if not isinstance(cover_faces, dict):
        errors.append("build manifest inputs.cover_faces must be a mapping")
    else:
        for face in ("front", "back"):
            row = cover_faces.get(face)
            if not isinstance(row, dict):
                errors.append(f"build manifest cover face {face} must be a mapping")
                continue
            for key in ("input_sha256", "pdf_sha256", "png_sha256"):
                if not _SHA256.fullmatch(str(row.get(key) or "")):
                    errors.append(
                        f"build manifest cover face {face}.{key} must be a SHA-256"
                    )
    for key in ("articles", "sections", "closing_plates", "sources"):
        rows = inputs.get(key)
        if isinstance(rows, list) and any(not isinstance(row, dict) for row in rows):
            errors.append(f"build manifest inputs.{key} rows must be mappings")
    return errors


def _hash_bindings(value: Any) -> tuple[list[tuple[Any, Any]], list[str]]:
    bindings: list[tuple[Any, Any]] = []
    errors: list[str] = []

    def visit(child: Any, pointer: str) -> None:
        if isinstance(child, dict):
            has_path = "path" in child
            has_sha = "sha256" in child
            if has_path and has_sha:
                bindings.append((child.get("path"), child.get("sha256")))
                return
            if has_sha and not has_path:
                errors.append(
                    f"malformed file binding at {pointer}: path and sha256 are required"
                )
                return
            for key, nested in child.items():
                visit(nested, f"{pointer}.{key}")
        elif isinstance(child, list):
            for index, nested in enumerate(child):
                visit(nested, f"{pointer}[{index}]")

    visit(value, "inputs")
    return bindings, errors
