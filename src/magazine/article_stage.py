"""Transactional staging from captured sources to an authored article slot.

This module owns the clerical seam between durable source capture and human
editorial work. It validates a versioned brief, derives provenance and author
metadata from source records, and prepares three artifacts together:

* a manuscript containing only an explicit, non-reader TODO;
* a fidelity ledger with exact extraction-body pins and no invented prose;
* the matching article row and source declarations in ``edition.yaml``.

Planning is read-only. Staging commits the complete plan as one batch and
rolls completed replacements back if a later replacement fails. Existing
article work is never overwritten. A second run for an already staged,
compatible article is a no-op even after an editor has begun filling in the
manuscript and ledger.
"""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import gettempdir, mkstemp
from typing import Any, Mapping

import yaml
from yaml.nodes import MappingNode, SequenceNode

from .errors import ValidationError
from .extraction import Extraction, load_extraction
from .io import dump_yaml, load_structured
from .records import SourceRecord, load_records
from .release import load_release_state

ARTICLE_BRIEF_SCHEMA_VERSION = 1
CONTENT_MODES = {
    "faithful_edit",
    "faithful_synthesis",
    "selected_extracts",
    "original_synthesis",
}
OPENER_VARIANTS = {"edge_medallion", "split_axis", "stepped_title"}
_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_LOCK_DIRECTORY = Path(gettempdir()) / "magazine-article-stage-locks"


@dataclass(frozen=True)
class _FileFingerprint:
    path: Path
    content_sha256: str | None


@dataclass
class _ConditionalInstall:
    path: Path
    original: bytes | None
    intended: bytes
    backup: Path | None = None
    installed_identity: tuple[int, int] | None = None


class _ConcurrentWrite(ValidationError):
    """A destination changed after planning and was deliberately preserved."""


@dataclass(frozen=True)
class ArticleBrief:
    """Versioned human decision record for one source-backed article slot."""

    edition_id: str
    id: str
    title: str
    source_ids: tuple[str, ...]
    short_title: str
    content_mode: str = "faithful_edit"
    opener_variant: str = "edge_medallion"
    display_emphasis: str = ""
    minimum_reader_pages: int = 1
    schema_version: int = ARTICLE_BRIEF_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ArticleBrief":
        """Parse the stable mapping interface intended for later CLI use."""

        if not isinstance(data, Mapping):
            raise ValidationError("Article brief must be a mapping")
        source_ids = data.get("source_ids")
        if not isinstance(source_ids, (list, tuple)):
            source_ids = ()
        title = str(data.get("title") or "").strip()
        return cls(
            schema_version=_as_int(data.get("schema_version"), default=0),
            edition_id=str(data.get("edition_id") or "").strip(),
            id=str(data.get("id") or "").strip(),
            title=title,
            short_title=str(data.get("short_title") or title).strip(),
            source_ids=tuple(str(item).strip() for item in source_ids),
            content_mode=str(data.get("content_mode") or "faithful_edit").strip(),
            opener_variant=str(data.get("opener_variant") or "edge_medallion").strip(),
            display_emphasis=str(data.get("display_emphasis") or "").strip(),
            minimum_reader_pages=_as_int(
                data.get("minimum_reader_pages"), default=1
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "edition_id": self.edition_id,
            "id": self.id,
            "title": self.title,
            "short_title": self.short_title,
            "display_emphasis": self.display_emphasis,
            "opener_variant": self.opener_variant,
            "content_mode": self.content_mode,
            "minimum_reader_pages": self.minimum_reader_pages,
            "source_ids": list(self.source_ids),
        }


@dataclass(frozen=True)
class ArticleStageChange:
    """One filesystem action in a read-only stage plan."""

    path: Path
    action: str
    purpose: str


@dataclass(frozen=True)
class ArticleStagePlan:
    """Complete read-only staging decision, including prepared file bytes."""

    edition_id: str
    article_id: str
    article_row: Mapping[str, Any]
    changes: tuple[ArticleStageChange, ...]
    _updates: tuple[tuple[Path, bytes], ...] = field(repr=False)
    _dependencies: tuple[_FileFingerprint, ...] = field(
        repr=False, default=()
    )

    @property
    def changed(self) -> bool:
        return bool(self._updates)

    @property
    def created(self) -> tuple[Path, ...]:
        return tuple(change.path for change in self.changes if change.action == "create")

    @property
    def updated(self) -> tuple[Path, ...]:
        return tuple(change.path for change in self.changes if change.action == "update")

    @property
    def kept(self) -> tuple[Path, ...]:
        return tuple(change.path for change in self.changes if change.action == "keep")


@dataclass(frozen=True)
class ArticleStageReport:
    """Applied or dry-run result suitable for a future CLI renderer."""

    edition_id: str
    article_id: str
    created: tuple[Path, ...]
    updated: tuple[Path, ...]
    kept: tuple[Path, ...]
    dry_run: bool = False

    @property
    def changed(self) -> bool:
        return bool(self.created or self.updated)


def plan_article_stage(root: Path, brief: ArticleBrief | Mapping[str, Any]) -> ArticleStagePlan:
    """Validate and prepare one article stage without writing anything."""

    root = root.resolve()
    brief = brief if isinstance(brief, ArticleBrief) else ArticleBrief.from_dict(brief)
    _validate_brief(brief)
    config = _load_config(root)
    editions_dir = _safe_repo_path(
        root, root / config["editions"], label="Configured editions directory"
    )
    sources_dir = _safe_repo_path(
        root, root / config["sources"], label="Configured sources directory"
    )
    release_state_path = _safe_repo_path(
        root,
        root / config["release_state"],
        label="Configured release state",
    )
    release_state = load_release_state(release_state_path)
    if brief.edition_id not in release_state.collecting_edition_ids:
        raise ValidationError(
            f"Edition is not collecting: {brief.edition_id}"
        )
    assigned = release_state.queued_source_ids_for(brief.edition_id)
    assignments = release_state.assignments()
    errors: list[str] = []
    for source_id in brief.source_ids:
        assignment = assignments.get(source_id)
        expected = f"queued:{brief.edition_id}"
        if assignment != expected:
            if assignment is None:
                errors.append(
                    f"Source {source_id} is not assigned to collecting edition "
                    f"{brief.edition_id}"
                )
            else:
                errors.append(
                    f"Source {source_id} is assigned to {assignment}, not "
                    f"queued:{brief.edition_id}"
                )
    unknown_queue = sorted(set(brief.source_ids) - set(assigned))
    if unknown_queue and not errors:
        errors.append(
            f"Sources are not queued for {brief.edition_id}: {', '.join(unknown_queue)}"
        )
    if errors:
        raise ValidationError(errors)

    records = {record.id: record for record in load_records(sources_dir)}
    selected_records: list[SourceRecord] = []
    extractions: list[Extraction] = []
    for source_id in brief.source_ids:
        record = records.get(source_id)
        if record is None:
            errors.append(f"Source record not found: {source_id}")
            continue
        selected_records.append(record)
        extraction = load_extraction(sources_dir, source_id)
        if extraction is None:
            errors.append(
                f"Source {source_id} has no committed extraction at "
                f"library/sources/{source_id}/extracted.md"
            )
        else:
            extractions.append(extraction)
    if errors:
        raise ValidationError(errors)
    author, author_note = _consistent_author_profile(selected_records)

    edition_dir = _safe_repo_path(
        root,
        editions_dir / brief.edition_id,
        label=f"Edition {brief.edition_id}",
    )
    manifest_path = _safe_repo_path(
        root,
        edition_dir / "edition.yaml",
        label="Edition manifest",
    )
    if not manifest_path.is_file():
        raise ValidationError(f"Edition manifest not found: {manifest_path}")
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest = load_structured(manifest_path)
    if manifest.get("id") != brief.edition_id:
        raise ValidationError(
            f"Edition id {manifest.get('id')!r} does not match "
            f"{brief.edition_id!r}"
        )
    articles = manifest.get("articles", [])
    if articles is None:
        articles = []
    if not isinstance(articles, list) or any(
        not isinstance(item, dict) for item in articles
    ):
        raise ValidationError(f"{manifest_path}: articles must be a list of mappings")
    declared_sources = manifest.get("sources", [])
    if declared_sources is None:
        declared_sources = []
    if not isinstance(declared_sources, list):
        raise ValidationError(f"{manifest_path}: sources must be a list")

    manuscript_path = _safe_repo_path(
        root,
        edition_dir / "articles" / f"{brief.id}.md",
        label="Article manuscript destination",
    )
    ledger_path = _safe_repo_path(
        root,
        edition_dir / "fidelity" / f"{brief.id}.yaml",
        label="Fidelity ledger destination",
    )
    _assert_safe_destination(root, manuscript_path, "Article manuscript destination")
    _assert_safe_destination(root, ledger_path, "Fidelity ledger destination")
    article_row = _article_row(
        root,
        brief,
        manuscript_path,
        ledger_path,
        author,
        author_note,
    )
    existing_row = next(
        (row for row in articles if str(row.get("id")) == brief.id),
        None,
    )
    duplicate_rows = [
        row for row in articles if str(row.get("id")) == brief.id
    ]
    if len(duplicate_rows) > 1:
        raise ValidationError(
            f"{manifest_path}: duplicate article id {brief.id}"
        )
    overlapping_articles: list[str] = []
    requested_sources = set(brief.source_ids)
    for row in articles:
        row_id = str(row.get("id") or "")
        if row_id == brief.id:
            continue
        row_sources = row.get("source_ids")
        if not isinstance(row_sources, list):
            continue
        overlap = requested_sources.intersection(
            str(source_id) for source_id in row_sources
        )
        if overlap:
            overlapping_articles.append(
                f"{row_id or '<missing id>'} ({', '.join(sorted(overlap))})"
            )
    if overlapping_articles:
        raise ValidationError(
            f"{manifest_path}: sources already belong to another article: "
            + ", ".join(overlapping_articles)
        )

    manuscript_bytes = _manuscript_skeleton(brief).encode("utf-8")
    ledger_bytes = _ledger_skeleton(brief, extractions, author).encode("utf-8")
    if existing_row is not None:
        _validate_existing_stage(
            manifest_path,
            existing_row,
            article_row,
            manuscript_path,
            ledger_path,
        )
        return ArticleStagePlan(
            brief.edition_id,
            brief.id,
            article_row,
            (
                ArticleStageChange(manuscript_path, "keep", "manuscript"),
                ArticleStageChange(ledger_path, "keep", "fidelity ledger"),
                ArticleStageChange(manifest_path, "keep", "edition manifest"),
            ),
            (),
            (),
        )

    collisions = [
        path for path in (manuscript_path, ledger_path) if path.exists()
    ]
    if collisions:
        raise ValidationError(
            [
                f"Refusing to overwrite existing article work: {path}"
                for path in collisions
            ]
        )

    missing_sources = [
        source_id
        for source_id in brief.source_ids
        if source_id not in declared_sources
    ]
    manifest_bytes = _append_manifest_article(
        manifest_path,
        manifest_text,
        missing_sources,
        article_row,
    )
    updates = (
        (manuscript_path, manuscript_bytes),
        (ledger_path, ledger_bytes),
        (manifest_path, manifest_bytes),
    )
    dependency_paths = [
        release_state_path,
        manifest_path,
        *(_source_record_path(sources_dir, source_id) for source_id in brief.source_ids),
        *(extraction.path for extraction in extractions),
        manuscript_path,
        ledger_path,
    ]
    return ArticleStagePlan(
        brief.edition_id,
        brief.id,
        article_row,
        (
            ArticleStageChange(manuscript_path, "create", "manuscript"),
            ArticleStageChange(ledger_path, "create", "fidelity ledger"),
            ArticleStageChange(manifest_path, "update", "edition manifest"),
        ),
        updates,
        tuple(_fingerprint(path) for path in dependency_paths),
    )


def stage_article(
    root: Path,
    brief: ArticleBrief | Mapping[str, Any],
    *,
    dry_run: bool = False,
) -> ArticleStageReport:
    """Plan and atomically stage one source-backed article.

    With ``dry_run=True`` the report names the changes that would be made but
    the filesystem is untouched.
    """

    normalized_brief = (
        brief if isinstance(brief, ArticleBrief) else ArticleBrief.from_dict(brief)
    )
    if dry_run:
        plan = plan_article_stage(root, normalized_brief)
    else:
        with _edition_lock(Path(root).resolve(), normalized_brief.edition_id):
            plan = plan_article_stage(root, normalized_brief)
            if plan.changed:
                _replace_files_atomically(
                    Path(root).resolve(),
                    plan._updates,
                    expected=plan._dependencies,
                )
    return ArticleStageReport(
        plan.edition_id,
        plan.article_id,
        plan.created,
        plan.updated,
        plan.kept,
        dry_run=dry_run,
    )


def _validate_brief(brief: ArticleBrief) -> None:
    errors: list[str] = []
    if brief.schema_version != ARTICLE_BRIEF_SCHEMA_VERSION:
        errors.append(
            f"Article brief schema_version must be "
            f"{ARTICLE_BRIEF_SCHEMA_VERSION}"
        )
    for label, value in (("edition_id", brief.edition_id), ("id", brief.id)):
        if not _SAFE_ID.fullmatch(value):
            errors.append(
                f"Article brief {label} must use lowercase letters, digits, and hyphens"
            )
    if not brief.title:
        errors.append("Article brief title cannot be empty")
    if not brief.source_ids:
        errors.append("Article brief source_ids must be a non-empty list")
    elif any(not source_id for source_id in brief.source_ids):
        errors.append("Article brief source_ids cannot contain empty values")
    elif len(set(brief.source_ids)) != len(brief.source_ids):
        errors.append("Article brief source_ids must be unique")
    elif any(not _SAFE_ID.fullmatch(source_id) for source_id in brief.source_ids):
        errors.append(
            "Article brief source_ids must use lowercase letters, digits, and hyphens"
        )
    if (
        not brief.short_title
        or "\n" in brief.short_title
        or len(brief.short_title) > 40
    ):
        errors.append("Article brief short_title must be one line of at most 40 characters")
    elif brief.short_title.casefold() not in brief.title.casefold():
        errors.append("Article brief short_title must occur in title")
    if (
        brief.display_emphasis
        and brief.display_emphasis.casefold() not in brief.title.casefold()
    ):
        errors.append("Article brief display_emphasis must occur in title")
    if brief.content_mode not in CONTENT_MODES:
        errors.append(f"Article brief has invalid content_mode: {brief.content_mode}")
    elif brief.content_mode == "original_synthesis":
        errors.append(
            "Article staging cannot infer an editor byline for original_synthesis; "
            "use an explicit editor-authoring workflow"
        )
    if brief.opener_variant not in OPENER_VARIANTS:
        errors.append(f"Article brief has invalid opener_variant: {brief.opener_variant}")
    if not 1 <= brief.minimum_reader_pages <= 7:
        errors.append("Article brief minimum_reader_pages must be from 1 to 7")
    if errors:
        raise ValidationError(errors)


def _consistent_author_profile(records: list[SourceRecord]) -> tuple[str, str]:
    errors: list[str] = []
    identities: list[tuple[str, str]] = []
    for record in records:
        author = str(record.author or "").strip()
        profile = record.author_profile
        if not author or profile is None:
            errors.append(
                f"Source {record.id} has no captured author identity and profile"
            )
            continue
        identities.append((author, profile.note))
    if errors:
        raise ValidationError(errors)
    expected = identities[0]
    mismatches = [
        record.id
        for record, identity in zip(records, identities)
        if identity != expected
    ]
    if mismatches:
        raise ValidationError(
            "Article sources have inconsistent author profiles: "
            + ", ".join(mismatches)
        )
    return expected


def _article_row(
    root: Path,
    brief: ArticleBrief,
    manuscript: Path,
    ledger: Path,
    author: str,
    author_note: str,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": brief.id,
        "title": brief.title,
        "short_title": brief.short_title,
    }
    if brief.display_emphasis:
        row["display_emphasis"] = brief.display_emphasis
    row.update(
        {
            "opener_variant": brief.opener_variant,
            "author": author,
        }
    )
    if author_note:
        row["author_note"] = author_note
    row.update(
        {
            "content_mode": brief.content_mode,
            "source_ids": list(brief.source_ids),
            "manuscript": manuscript.relative_to(root).as_posix(),
            "fidelity": ledger.relative_to(root).as_posix(),
        }
    )
    if brief.minimum_reader_pages != 1:
        row["minimum_reader_pages"] = brief.minimum_reader_pages
    return row


def _manuscript_skeleton(brief: ArticleBrief) -> str:
    metadata = {
        "source_ids": list(brief.source_ids),
        "content_mode": brief.content_mode,
        "label": "EDITORIAL WORK REQUIRED",
        "stage_status": "todo",
    }
    return (
        "---\n"
        + dump_yaml(metadata)
        + "---\n\n"
        + "<!-- TODO(editor): Replace this staging marker with a "
        + "source-faithful manuscript. No source prose was generated. -->\n"
    )


def _ledger_skeleton(
    brief: ArticleBrief,
    extractions: list[Extraction],
    author: str,
) -> str:
    hashes = {
        extraction.source_id: extraction.body_sha256
        for extraction in extractions
    }
    source_body_sha256: str | dict[str, str]
    if len(brief.source_ids) == 1:
        source_body_sha256 = hashes[brief.source_ids[0]]
    else:
        source_body_sha256 = {
            source_id: hashes[source_id] for source_id in brief.source_ids
        }
    data = {
        "schema_version": 1,
        "source_ids": list(brief.source_ids),
        "source_body_sha256": source_body_sha256,
        "source_author": author,
        "content_mode": brief.content_mode,
        "stage_status": "todo_editorial_mapping_required",
        "paragraphs": [
            {
                "id": "TODO",
                "status": "todo_editorial_mapping_required",
                "note": (
                    "Replace this non-source marker with audited source-to-edited "
                    "mappings before validation."
                ),
            }
        ],
    }
    return dump_yaml(data)


def _validate_existing_stage(
    manifest_path: Path,
    existing: Mapping[str, Any],
    expected: Mapping[str, Any],
    manuscript_path: Path,
    ledger_path: Path,
) -> None:
    errors: list[str] = []
    for key, value in expected.items():
        if existing.get(key) != value:
            errors.append(
                f"{manifest_path}: existing article {expected['id']} has "
                f"incompatible {key}"
            )
    for path, purpose in (
        (manuscript_path, "manuscript"),
        (ledger_path, "fidelity ledger"),
    ):
        if not path.is_file():
            errors.append(
                f"{manifest_path}: existing article {expected['id']} is missing "
                f"its {purpose}: {path}"
            )
    if errors:
        raise ValidationError(errors)


def _append_manifest_article(
    path: Path,
    text: str,
    source_ids: list[str],
    article_row: Mapping[str, Any],
) -> bytes:
    """Append only the two derived manifest fragments, preserving prior text."""

    updated = text
    if source_ids:
        updated = _append_root_sequence(path, updated, "sources", source_ids)
    updated = _append_root_sequence(path, updated, "articles", [dict(article_row)])
    try:
        reparsed = yaml.safe_load(updated)
    except yaml.YAMLError as exc:
        raise ValidationError(
            f"{path}: staged manifest no longer parses: {exc}"
        ) from exc
    if not isinstance(reparsed, dict):
        raise ValidationError(f"{path}: staged manifest must remain a mapping")
    sources = reparsed.get("sources")
    articles = reparsed.get("articles")
    if not isinstance(sources, list) or any(
        source_id not in sources for source_id in source_ids
    ):
        raise ValidationError(f"{path}: failed to append staged source declarations")
    if (
        not isinstance(articles, list)
        or not articles
        or articles[-1] != dict(article_row)
    ):
        raise ValidationError(f"{path}: failed to append staged article row")
    return updated.encode("utf-8")


def _append_root_sequence(
    path: Path,
    text: str,
    key: str,
    items: list[object],
) -> str:
    """Append sequence items using YAML parser marks instead of re-dumping."""

    if not items:
        return text
    try:
        root_node = yaml.compose(text)
    except yaml.YAMLError as exc:
        raise ValidationError(f"{path}: cannot locate root {key}: {exc}") from exc
    if not isinstance(root_node, MappingNode):
        raise ValidationError(f"{path}: edition manifest must be a mapping")
    matches = [
        value_node
        for key_node, value_node in root_node.value
        if getattr(key_node, "value", None) == key
    ]
    if len(matches) != 1:
        detail = "is missing" if not matches else "appears more than once"
        raise ValidationError(f"{path}: root {key} {detail}")
    sequence = matches[0]
    if not isinstance(sequence, SequenceNode):
        raise ValidationError(f"{path}: root {key} must be a list")

    if sequence.flow_style:
        insertion = sequence.end_mark.index - 1
        serialized = []
        for item in items:
            wrapped = yaml.safe_dump(
                [item],
                default_flow_style=True,
                sort_keys=False,
                allow_unicode=True,
                width=1_000_000,
            ).strip()
            serialized.append(wrapped[1:-1])
        prefix = ", " if sequence.value else ""
        return text[:insertion] + prefix + ", ".join(serialized) + text[insertion:]

    if not sequence.value:
        raise ValidationError(
            f"{path}: root {key} uses an unsupported empty block sequence"
        )
    last_item = sequence.value[-1]
    line_end = text.find("\n", last_item.end_mark.index)
    insertion = len(text) if line_end < 0 else line_end + 1
    column = sequence.start_mark.column
    fragment = yaml.safe_dump(
        items,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
    if column:
        indent = " " * column
        fragment = "".join(
            indent + line if line.strip() else line
            for line in fragment.splitlines(keepends=True)
        )
    if insertion == len(text) and text and not text.endswith("\n"):
        fragment = "\n" + fragment
    return text[:insertion] + fragment + text[insertion:]


def _source_record_path(sources_dir: Path, source_id: str) -> Path:
    paths = sorted((sources_dir / source_id).glob("record.y*ml"))
    if len(paths) != 1:
        raise ValidationError(
            f"Source {source_id} must have exactly one record.yaml or record.yml"
        )
    return paths[0]


def _fingerprint(path: Path) -> _FileFingerprint:
    if path.is_symlink():
        raise ValidationError(f"Refusing symlink dependency: {path}")
    if not path.exists():
        return _FileFingerprint(path, None)
    if not path.is_file():
        raise ValidationError(f"Expected a regular file dependency: {path}")
    return _FileFingerprint(path, hashlib.sha256(path.read_bytes()).hexdigest())


def _assert_fingerprints(
    expected: tuple[_FileFingerprint, ...],
    *,
    committed: Mapping[Path, bytes] | None = None,
) -> None:
    conflicts: list[str] = []
    committed = committed or {}
    for fingerprint in expected:
        try:
            current = _fingerprint(fingerprint.path).content_sha256
        except ValidationError as exc:
            conflicts.append(str(exc))
            continue
        intended = committed.get(fingerprint.path)
        expected_digest = (
            hashlib.sha256(intended).hexdigest()
            if intended is not None
            else fingerprint.content_sha256
        )
        if current != expected_digest:
            conflicts.append(f"changed while staging: {fingerprint.path}")
    if conflicts:
        raise ValidationError(
            ["Article stage is stale; no files were written", *conflicts]
        )


def _safe_repo_path(root: Path, path: Path, *, label: str) -> Path:
    """Resolve a configured path and reject symlinks or escapes from the repo."""

    root = root.resolve()
    candidate = path if path.is_absolute() else root / path
    try:
        lexical = candidate.relative_to(root)
    except ValueError as exc:
        raise ValidationError(f"{label} escapes repository root: {candidate}") from exc
    if ".." in lexical.parts:
        raise ValidationError(f"{label} escapes repository root: {candidate}")
    current = root
    for part in lexical.parts:
        current = current / part
        if current.is_symlink():
            raise ValidationError(f"{label} cannot use symlink path component: {current}")
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ValidationError(f"{label} escapes repository root: {candidate}")
    return resolved


def _assert_safe_destination(root: Path, path: Path, label: str) -> None:
    _safe_repo_path(root, path, label=label)
    current = root.resolve()
    for part in path.relative_to(root.resolve()).parts[:-1]:
        current = current / part
        if current.exists() and not current.is_dir():
            raise ValidationError(
                f"{label} parent must be a directory: {current}"
            )


@contextmanager
def _edition_lock(root: Path, edition_id: str):
    lock_name = hashlib.sha256(
        f"{root}:{edition_id}".encode("utf-8")
    ).hexdigest()
    lock_path = _LOCK_DIRECTORY / f"{lock_name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _replace_files_atomically(
    root: Path,
    updates: tuple[tuple[Path, bytes], ...],
    *,
    expected: tuple[_FileFingerprint, ...],
) -> None:
    """Conditionally install a batch without overwriting concurrent writes."""

    originals = {
        path: path.read_bytes() if path.exists() else None
        for path, _ in updates
    }
    update_contents = dict(updates)
    staged: dict[Path, Path] = {}
    installs: list[_ConditionalInstall] = []
    try:
        for path, content in updates:
            _assert_safe_destination(root, path, "Article stage destination")
            path.parent.mkdir(parents=True, exist_ok=True)
            _assert_safe_destination(root, path, "Article stage destination")
            staged[path] = _stage_bytes(path, content)
        _assert_fingerprints(expected)
        for path, _ in updates:
            _assert_fingerprints(
                expected,
                committed={
                    install.path: install.intended
                    for install in installs
                    if install.installed_identity is not None
                },
            )
            _assert_safe_destination(root, path, "Article stage destination")
            install = _prepare_conditional_install(
                path,
                originals[path],
                update_contents[path],
            )
            installs.append(install)
            _install_exclusive(staged[path], path)
            stat = path.stat()
            install.installed_identity = (stat.st_dev, stat.st_ino)
        _assert_fingerprints(
            expected,
            committed={path: content for path, content in updates},
        )
    except (OSError, ValidationError) as exc:
        rollback_errors: list[str] = []
        for install in reversed(installs):
            try:
                _restore_conditional_install(install)
            except OSError as rollback_exc:
                rollback_errors.append(f"{install.path}: {rollback_exc}")
        detail = f"Cannot stage article atomically: {exc}"
        if rollback_errors:
            detail += "; rollback failed: " + "; ".join(rollback_errors)
        raise ValidationError(detail) from exc
    else:
        for install in installs:
            if install.backup is not None:
                install.backup.unlink(missing_ok=True)
    finally:
        for install in installs:
            if install.backup is not None:
                install.backup.unlink(missing_ok=True)
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def _prepare_conditional_install(
    path: Path,
    expected: bytes | None,
    intended: bytes,
) -> _ConditionalInstall:
    install = _ConditionalInstall(path, expected, intended)
    if expected is None:
        if path.exists() or path.is_symlink():
            raise _ConcurrentWrite(
                f"Destination appeared while staging and was preserved: {path}"
            )
        return install

    backup = _reserve_backup(path)
    install.backup = backup
    try:
        os.replace(path, backup)
    except OSError:
        backup.unlink(missing_ok=True)
        install.backup = None
        raise
    found = backup.read_bytes()
    if found != expected:
        _restore_conditional_install(install)
        raise _ConcurrentWrite(
            f"Destination changed while staging and was preserved: {path}"
        )
    return install


def _install_exclusive(staged: Path, destination: Path) -> None:
    try:
        os.link(staged, destination, follow_symlinks=False)
    except FileExistsError as exc:
        raise _ConcurrentWrite(
            f"Destination appeared while staging and was preserved: {destination}"
        ) from exc


def _restore_conditional_install(install: _ConditionalInstall) -> None:
    path = install.path
    if install.installed_identity is not None and path.exists():
        stat = path.stat()
        identity = (stat.st_dev, stat.st_ino)
        if (
            identity == install.installed_identity
            and path.read_bytes() == install.intended
        ):
            path.unlink()
    if install.backup is None:
        return
    if not path.exists() and not path.is_symlink():
        try:
            os.link(install.backup, path, follow_symlinks=False)
        except FileExistsError:
            pass
    install.backup.unlink(missing_ok=True)
    install.backup = None


def _reserve_backup(destination: Path) -> Path:
    descriptor, name = mkstemp(
        prefix=f".{destination.name}.",
        suffix=".rollback",
        dir=destination.parent,
    )
    os.close(descriptor)
    return Path(name)


def _stage_bytes(destination: Path, content: bytes) -> Path:
    descriptor, name = mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if destination.is_file() and not destination.is_symlink():
            os.chmod(name, destination.stat().st_mode)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)


def _load_config(root: Path) -> dict[str, str]:
    config_path = root / "magazine.toml"
    data = (
        tomllib.loads(config_path.read_text(encoding="utf-8"))
        if config_path.is_file()
        else {}
    )
    paths = data.get("paths", {})
    return {
        "sources": str(paths.get("sources", "library/sources")),
        "editions": str(paths.get("editions", "editions")),
        "release_state": str(
            paths.get("release_state", "library/release-state.yaml")
        ),
    }


def _as_int(value: object, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
