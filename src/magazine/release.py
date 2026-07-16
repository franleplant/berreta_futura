from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import mkstemp
from typing import Any

from .errors import ValidationError
from .io import dump_yaml, load_structured


@dataclass(frozen=True)
class ReleaseState:
    open_edition: dict[str, Any]
    released_editions: tuple[dict[str, Any], ...]
    schema_version: int = 1

    @property
    def open_edition_id(self) -> str:
        return str(self.open_edition["id"])

    @property
    def queued_source_ids(self) -> tuple[str, ...]:
        return tuple(str(value) for value in self.open_edition.get("source_ids", []))

    def assignments(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for source_id in self.queued_source_ids:
            result[source_id] = f"queued:{self.open_edition_id}"
        for edition in self.released_editions:
            edition_id = str(edition["id"])
            for source_id in edition.get("source_ids", []):
                result[str(source_id)] = f"released:{edition_id}"
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "open_edition": dict(self.open_edition),
            "released_editions": [dict(edition) for edition in self.released_editions],
        }


@dataclass(frozen=True)
class ReleaseTransition:
    """The canonical state produced by a successful edition release."""

    released_edition_id: str
    next_edition_id: str
    source_ids: tuple[str, ...]
    state: ReleaseState


def load_release_state(path: Path, *, default_open_id: str = "001-unreleased") -> ReleaseState:
    if not path.is_file():
        return ReleaseState(
            open_edition={
                "id": default_open_id,
                "issue_number": 1,
                "status": "collecting",
                "source_ids": [],
            },
            released_editions=(),
        )
    data = load_structured(path)
    open_edition = data.get("open_edition")
    released = data.get("released_editions", [])
    errors: list[str] = []
    if not isinstance(open_edition, dict):
        errors.append("Release state requires an open_edition mapping")
        open_edition = {}
    for key in ("id", "issue_number", "status", "source_ids"):
        if open_edition.get(key) in (None, ""):
            errors.append(f"Open edition missing: {key}")
    if not isinstance(open_edition.get("source_ids"), list):
        errors.append("Open edition source_ids must be a list")
    if not isinstance(released, list) or any(not isinstance(item, dict) for item in released):
        errors.append("released_editions must be a list of mappings")
        released = []
    if errors:
        raise ValidationError(errors)
    state = ReleaseState(dict(open_edition), tuple(dict(item) for item in released), int(data.get("schema_version", 1)))
    assignments = state.assignments()
    expected = len(state.queued_source_ids) + sum(len(item.get("source_ids", [])) for item in state.released_editions)
    if len(assignments) != expected:
        raise ValidationError("A source may appear in only one open or released edition")
    return state


def sync_release_state(path: Path, source_ids: set[str], *, default_open_id: str = "001-unreleased") -> ReleaseState:
    state = load_release_state(path, default_open_id=default_open_id)
    assignments = state.assignments()
    unassigned = sorted(source_ids - assignments.keys())
    unknown = sorted(assignments.keys() - source_ids)
    if unknown:
        raise ValidationError(f"Release state references unknown sources: {', '.join(unknown)}")
    if not unassigned and path.is_file():
        return state
    open_edition = dict(state.open_edition)
    open_edition["source_ids"] = sorted(set(state.queued_source_ids) | set(unassigned))
    updated = ReleaseState(open_edition, state.released_editions, state.schema_version)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml(updated.to_dict()), encoding="utf-8")
    return updated


def plan_release(
    state: ReleaseState,
    *,
    edition_id: str,
    issue_number: str | int,
    source_ids: set[str],
    publication_date: str,
    next_edition_id: str | None = None,
) -> ReleaseTransition:
    """Validate and construct a release transition without writing anything."""

    errors: list[str] = []
    if state.open_edition_id != edition_id:
        errors.append(
            f"Cannot release {edition_id}: the open edition is {state.open_edition_id}"
        )
    if not state.queued_source_ids:
        errors.append("Cannot release an edition with no queued sources")

    queued = set(state.queued_source_ids)
    missing = sorted(queued - source_ids)
    unexpected = sorted(source_ids - queued)
    if missing:
        errors.append(
            "Edition postpones sources from the open queue: " + ", ".join(missing)
        )
    if unexpected:
        errors.append(
            "Edition contains sources not assigned to its open queue: " + ", ".join(unexpected)
        )

    try:
        number = int(issue_number)
    except (TypeError, ValueError):
        number = 0
        errors.append(f"Edition issue_number must be an integer: {issue_number!r}")
    try:
        open_number = int(state.open_edition["issue_number"])
    except (KeyError, TypeError, ValueError):
        open_number = 0
        errors.append("Open edition issue_number must be an integer")
    if number and open_number and number != open_number:
        errors.append(
            f"Edition issue_number {number} does not match open edition issue_number {open_number}"
        )

    released_ids = {str(item.get("id")) for item in state.released_editions}
    if edition_id in released_ids:
        errors.append(f"Edition is already released: {edition_id}")
    next_number = number + 1 if number else open_number + 1
    selected_next_id = next_edition_id or f"{next_number:03d}-unreleased"
    if not selected_next_id.strip():
        errors.append("Next edition id cannot be empty")
    if selected_next_id == edition_id or selected_next_id in released_ids:
        errors.append(f"Next edition id is already in use: {selected_next_id}")
    if errors:
        raise ValidationError(errors)

    released = {
        "id": edition_id,
        "issue_number": number,
        "status": "released",
        "publication_date": publication_date,
        "source_ids": sorted(source_ids),
    }
    open_edition = {
        "id": selected_next_id,
        "issue_number": next_number,
        "status": "collecting",
        "source_ids": [],
    }
    updated = ReleaseState(
        open_edition,
        (*state.released_editions, released),
        state.schema_version,
    )
    return ReleaseTransition(edition_id, selected_next_id, tuple(sorted(source_ids)), updated)


def finalize_release(
    state_path: Path,
    manifest_path: Path,
    *,
    edition_id: str,
    issue_number: str | int,
    source_ids: set[str],
    publication_date: str,
    next_edition_id: str | None = None,
    package_dir: Path | None = None,
) -> ReleaseTransition:
    """Atomically commit manifest and ledger state after a successful build.

    The manifest is written first and the authoritative release ledger last. If
    either replacement fails, every changed file is restored to its original
    bytes before the error is returned.
    """

    state = load_release_state(state_path)
    manifest = load_structured(manifest_path)
    if manifest.get("id") != edition_id:
        raise ValidationError(
            f"Edition id {manifest.get('id')!r} does not match release target {edition_id!r}"
        )
    if manifest.get("status") == "released":
        raise ValidationError(f"Edition manifest is already released: {edition_id}")
    transition = plan_release(
        state,
        edition_id=edition_id,
        issue_number=issue_number,
        source_ids=source_ids,
        publication_date=publication_date,
        next_edition_id=next_edition_id,
    )
    released_manifest = dict(manifest)
    released_manifest["status"] = "released"
    package_updates = _released_package_updates(package_dir) if package_dir else ()
    _replace_files_atomically(
        package_updates + (
            (manifest_path, dump_yaml(released_manifest).encode("utf-8")),
            (state_path, dump_yaml(transition.state.to_dict()).encode("utf-8")),
        )
    )
    return transition


def _released_package_updates(package_dir: Path) -> tuple[tuple[Path, bytes], ...]:
    manifest_path = package_dir / "edition-manifest.json"
    checksums_path = package_dir / "SHA256SUMS"
    manifest = load_structured(manifest_path)
    edition = manifest.get("edition")
    if not isinstance(edition, dict):
        raise ValidationError(f"{manifest_path} requires an edition mapping")
    released_edition = dict(edition)
    released_edition["status"] = "released"
    released_manifest = dict(manifest)
    released_manifest["edition"] = released_edition
    manifest_bytes = (
        json.dumps(released_manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n"
    ).encode("utf-8")

    files = sorted(
        path for path in package_dir.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    if manifest_path not in files:
        raise ValidationError(f"Release package manifest not found: {manifest_path}")
    checksum_lines = []
    for path in files:
        content = manifest_bytes if path == manifest_path else path.read_bytes()
        checksum_lines.append(
            f"{hashlib.sha256(content).hexdigest()}  {path.relative_to(package_dir).as_posix()}\n"
        )
    return (
        (manifest_path, manifest_bytes),
        (checksums_path, "".join(checksum_lines).encode("utf-8")),
    )


def _replace_files_atomically(updates: tuple[tuple[Path, bytes], ...]) -> None:
    """Replace a small set of files and roll back completed replacements."""

    originals = {path: path.read_bytes() if path.exists() else None for path, _ in updates}
    staged: dict[Path, Path] = {}
    changed: list[Path] = []
    try:
        for path, content in updates:
            path.parent.mkdir(parents=True, exist_ok=True)
            staged[path] = _stage_bytes(path, content)
        for path, _ in updates:
            os.replace(staged[path], path)
            changed.append(path)
    except OSError as exc:
        rollback_errors: list[str] = []
        for path in reversed(changed):
            try:
                original = originals[path]
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    os.replace(_stage_bytes(path, original), path)
            except OSError as rollback_exc:
                rollback_errors.append(f"{path}: {rollback_exc}")
        detail = f"Cannot commit release state: {exc}"
        if rollback_errors:
            detail += "; rollback failed: " + "; ".join(rollback_errors)
        raise ValidationError(detail) from exc
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def _stage_bytes(destination: Path, content: bytes) -> Path:
    descriptor, name = mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)
