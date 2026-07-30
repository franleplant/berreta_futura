from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from tempfile import mkstemp
from typing import Any

from .errors import ValidationError
from .io import dump_yaml, load_structured


_EDITION_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_EDITION_TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".json",
    ".md",
    ".svg",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
_EDITION_IDENTITY_FILES = {
    Path("edition.yaml"),
    Path("reviews/evidence.yaml"),
    Path("reviews/render.yaml"),
}


@dataclass(frozen=True)
class ReleaseState:
    collecting_editions: tuple[dict[str, Any], ...]
    intake_edition_id: str
    released_editions: tuple[dict[str, Any], ...]
    schema_version: int = 2

    @property
    def open_edition(self) -> dict[str, Any]:
        """Compatibility view of the edition currently receiving intake."""

        return self.collecting_edition(self.intake_edition_id)

    @property
    def open_edition_id(self) -> str:
        """Compatibility name for the edition currently receiving intake."""

        return self.intake_edition_id

    @property
    def queued_source_ids(self) -> tuple[str, ...]:
        """Compatibility view of the intake edition's source queue."""

        return self.queued_source_ids_for(self.intake_edition_id)

    @property
    def collecting_edition_ids(self) -> tuple[str, ...]:
        return tuple(str(edition["id"]) for edition in self.collecting_editions)

    def collecting_edition(self, edition_id: str) -> dict[str, Any]:
        for edition in self.collecting_editions:
            if str(edition.get("id")) == edition_id:
                return dict(edition)
        raise ValidationError(f"Edition is not collecting: {edition_id}")

    def queued_source_ids_for(self, edition_id: str) -> tuple[str, ...]:
        edition = self.collecting_edition(edition_id)
        return tuple(str(value) for value in edition.get("source_ids", []))

    def assignments(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for edition in self.collecting_editions:
            edition_id = str(edition["id"])
            for source_id in edition.get("source_ids", []):
                result[str(source_id)] = f"queued:{edition_id}"
        for edition in self.released_editions:
            edition_id = str(edition["id"])
            for source_id in edition.get("source_ids", []):
                result[str(source_id)] = f"released:{edition_id}"
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "intake_edition_id": self.intake_edition_id,
            "collecting_editions": [
                dict(edition) for edition in self.collecting_editions
            ],
            "released_editions": [dict(edition) for edition in self.released_editions],
        }


@dataclass(frozen=True)
class ReleaseTransition:
    """The canonical state produced by a successful edition release."""

    released_edition_id: str
    next_edition_id: str
    source_ids: tuple[str, ...]
    state: ReleaseState


def finished_edition_id(issue_number: str | int, title: str) -> str:
    """Derive the stable released id a human expects from issue copy."""

    try:
        number = int(issue_number)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Edition issue_number must be an integer") from exc
    if number < 1:
        raise ValidationError("Edition issue_number must be positive")
    ascii_title = (
        unicodedata.normalize("NFKD", str(title))
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title).strip("-")
    if not slug:
        raise ValidationError("Edition title cannot produce a finished id")
    return f"{number:03d}-{slug}"


def rename_collecting_edition(
    state_path: Path,
    editions_dir: Path,
    *,
    old_id: str,
    new_id: str,
) -> None:
    """Atomically migrate one collecting edition's identity and local paths."""

    old_id = str(old_id or "").strip()
    new_id = str(new_id or "").strip()
    for label, value in (("Current", old_id), ("Finished", new_id)):
        if not _EDITION_ID.fullmatch(value):
            raise ValidationError(
                f"{label} edition id must use lowercase letters, numbers, and hyphens: "
                f"{value!r}"
            )
    if old_id == new_id:
        return

    state = load_release_state(state_path)
    if old_id not in state.collecting_edition_ids:
        raise ValidationError(f"Edition is not collecting: {old_id}")
    used_ids = set(state.collecting_edition_ids) | {
        str(row.get("id")) for row in state.released_editions
    }
    if new_id in used_ids:
        raise ValidationError(f"Edition id is already in use: {new_id}")

    editions_root = editions_dir.resolve()
    old_dir = (editions_dir / old_id).resolve()
    new_dir = (editions_dir / new_id).resolve()
    if not old_dir.is_relative_to(editions_root) or not new_dir.is_relative_to(
        editions_root
    ):
        raise ValidationError("Edition rename escapes the editions directory")
    if not old_dir.is_dir():
        raise ValidationError(f"Edition directory not found: {old_dir}")
    if new_dir.exists():
        raise ValidationError(f"Finished edition directory already exists: {new_dir}")

    manifest = load_structured(old_dir / "edition.yaml")
    if manifest.get("id") != old_id:
        raise ValidationError(
            f"Edition manifest id {manifest.get('id')!r} does not match {old_id!r}"
        )

    edition_updates: list[tuple[Path, bytes]] = []
    for path in sorted(old_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _EDITION_TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(old_dir)
        replaced = text.replace(
            f"editions/{old_id}/",
            f"editions/{new_id}/",
        ).replace(
            f"output/{old_id}/",
            f"output/{new_id}/",
        )
        if relative in _EDITION_IDENTITY_FILES:
            replaced = re.sub(
                rf"^(\s*(?:id|edition_id):\s*){re.escape(old_id)}(\s*(?:#.*)?)$",
                rf"\g<1>{new_id}\g<2>",
                replaced,
                flags=re.MULTILINE,
            )
        if replaced != text:
            edition_updates.append(
                (relative, replaced.encode("utf-8"))
            )

    collecting = []
    for row in state.collecting_editions:
        renamed = dict(row)
        if str(renamed.get("id")) == old_id:
            renamed["id"] = new_id
        collecting.append(renamed)
    renamed_state = ReleaseState(
        tuple(collecting),
        new_id if state.intake_edition_id == old_id else state.intake_edition_id,
        state.released_editions,
    )

    try:
        old_dir.rename(new_dir)
    except OSError as exc:
        raise ValidationError(
            f"Cannot rename collecting edition {old_id} to {new_id}: {exc}"
        ) from exc
    try:
        _replace_files_atomically(
            tuple(
                (new_dir / relative, content)
                for relative, content in edition_updates
            )
            + (
                (
                    state_path,
                    dump_yaml(renamed_state.to_dict()).encode("utf-8"),
                ),
            )
        )
    except BaseException:
        try:
            new_dir.rename(old_dir)
        except OSError as rollback_exc:
            raise ValidationError(
                f"Edition rename failed and directory rollback also failed: "
                f"{rollback_exc}"
            ) from rollback_exc
        raise


def load_release_state(path: Path, *, default_open_id: str = "001-unreleased") -> ReleaseState:
    if not path.is_file():
        return ReleaseState(
            collecting_editions=(_collecting_edition(default_open_id, 1),),
            intake_edition_id=default_open_id,
            released_editions=(),
        )
    data = load_structured(path)
    schema_version = int(data.get("schema_version", 1))
    if schema_version == 1:
        legacy_open = data.get("open_edition")
        if isinstance(legacy_open, dict):
            normalized_open = dict(legacy_open)
            normalized_open["status"] = "collecting"
            collecting = [normalized_open]
        else:
            collecting = []
        intake_edition_id = str(
            legacy_open.get("id") if isinstance(legacy_open, dict) else ""
        )
    elif schema_version == 2:
        collecting = data.get("collecting_editions", [])
        intake_edition_id = str(data.get("intake_edition_id") or "")
    else:
        raise ValidationError(f"Unsupported release state schema_version: {schema_version}")
    released = data.get("released_editions", [])
    errors: list[str] = []
    if not isinstance(collecting, list) or not collecting:
        errors.append("Release state requires at least one collecting edition")
        collecting = []
    elif any(not isinstance(item, dict) for item in collecting):
        errors.append("collecting_editions must be a list of mappings")
        collecting = []
    for edition in collecting:
        label = str(edition.get("id") or "<unknown>")
        for key in ("id", "issue_number", "status", "source_ids"):
            if edition.get(key) in (None, ""):
                errors.append(f"Collecting edition {label} missing: {key}")
        if edition.get("status") != "collecting":
            errors.append(f"Collecting edition {label} status must be collecting")
        if not isinstance(edition.get("source_ids"), list):
            errors.append(f"Collecting edition {label} source_ids must be a list")
    collecting_ids = [str(item.get("id")) for item in collecting]
    if len(set(collecting_ids)) != len(collecting_ids):
        errors.append("Collecting edition ids must be unique")
    if intake_edition_id not in collecting_ids:
        errors.append("intake_edition_id must name a collecting edition")
    if not isinstance(released, list) or any(not isinstance(item, dict) for item in released):
        errors.append("released_editions must be a list of mappings")
        released = []
    if errors:
        raise ValidationError(errors)
    state = ReleaseState(
        tuple(dict(item) for item in collecting),
        intake_edition_id,
        tuple(dict(item) for item in released),
    )
    assignments = state.assignments()
    expected = sum(
        len(item.get("source_ids", [])) for item in state.collecting_editions
    ) + sum(len(item.get("source_ids", [])) for item in state.released_editions)
    if len(assignments) != expected:
        raise ValidationError(
            "A source may appear in only one collecting or released edition"
        )
    return state


def sync_release_state(
    path: Path,
    source_ids: set[str],
    *,
    default_open_id: str = "001-unreleased",
    target_edition_id: str | None = None,
) -> ReleaseState:
    state = load_release_state(path, default_open_id=default_open_id)
    assignments = state.assignments()
    unassigned = sorted(source_ids - assignments.keys())
    unknown = sorted(assignments.keys() - source_ids)
    if unknown:
        raise ValidationError(f"Release state references unknown sources: {', '.join(unknown)}")
    if not unassigned and path.is_file():
        return state
    destination_id = target_edition_id or state.intake_edition_id
    state.collecting_edition(destination_id)
    collecting: list[dict[str, Any]] = []
    for edition in state.collecting_editions:
        row = dict(edition)
        if str(row["id"]) == destination_id:
            row["source_ids"] = sorted(
                set(str(value) for value in row.get("source_ids", []))
                | set(unassigned)
            )
        collecting.append(row)
    updated = ReleaseState(
        tuple(collecting),
        state.intake_edition_id,
        state.released_editions,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml(updated.to_dict()), encoding="utf-8")
    return updated


def open_collection(
    path: Path,
    *,
    edition_id: str,
    issue_number: str | int,
    select_for_intake: bool = True,
    default_open_id: str = "001-unreleased",
) -> ReleaseState:
    """Create a collecting edition and optionally make it the intake target."""

    clean_id = str(edition_id or "").strip()
    if not clean_id:
        raise ValidationError("Collecting edition id cannot be empty")
    try:
        number = int(issue_number)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Collecting edition issue_number must be an integer") from exc
    if number < 1:
        raise ValidationError("Collecting edition issue_number must be positive")
    state = load_release_state(path, default_open_id=default_open_id)
    all_ids = set(state.collecting_edition_ids) | {
        str(item.get("id")) for item in state.released_editions
    }
    if clean_id in all_ids:
        if clean_id in state.collecting_edition_ids and select_for_intake:
            updated = ReleaseState(
                state.collecting_editions,
                clean_id,
                state.released_editions,
            )
            path.write_text(dump_yaml(updated.to_dict()), encoding="utf-8")
            return updated
        raise ValidationError(f"Edition id is already in use: {clean_id}")
    used_numbers = {
        int(item["issue_number"])
        for item in (*state.collecting_editions, *state.released_editions)
        if str(item.get("issue_number", "")).isdigit()
    }
    if number in used_numbers:
        raise ValidationError(f"Edition issue_number is already in use: {number}")
    collecting = (*state.collecting_editions, _collecting_edition(clean_id, number))
    updated = ReleaseState(
        collecting,
        clean_id if select_for_intake else state.intake_edition_id,
        state.released_editions,
    )
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
    if edition_id not in state.collecting_edition_ids:
        errors.append(f"Cannot release {edition_id}: the edition is not collecting")
        queued: set[str] = set()
        collecting_edition: dict[str, Any] = {}
    else:
        collecting_edition = state.collecting_edition(edition_id)
        queued = set(state.queued_source_ids_for(edition_id))
    if not queued:
        errors.append("Cannot release an edition with no queued sources")

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
        open_number = int(collecting_edition["issue_number"])
    except (KeyError, TypeError, ValueError):
        open_number = 0
        errors.append("Collecting edition issue_number must be an integer")
    if number and open_number and number != open_number:
        errors.append(
            f"Edition issue_number {number} does not match collecting edition issue_number {open_number}"
        )

    released_ids = {str(item.get("id")) for item in state.released_editions}
    if edition_id in released_ids:
        errors.append(f"Edition is already released: {edition_id}")
    remaining = tuple(
        dict(item)
        for item in state.collecting_editions
        if str(item.get("id")) != edition_id
    )
    if remaining:
        if next_edition_id is not None:
            errors.append(
                "Cannot override the next edition while another collecting edition exists"
            )
        selected_next_id = (
            state.intake_edition_id
            if state.intake_edition_id != edition_id
            else str(remaining[-1]["id"])
        )
        next_collecting = remaining
    else:
        next_number = number + 1 if number else open_number + 1
        selected_next_id = next_edition_id or f"{next_number:03d}-unreleased"
        if not selected_next_id.strip():
            errors.append("Next edition id cannot be empty")
        if selected_next_id == edition_id or selected_next_id in released_ids:
            errors.append(f"Next edition id is already in use: {selected_next_id}")
        next_collecting = (_collecting_edition(selected_next_id, next_number),)
    if errors:
        raise ValidationError(errors)

    released = {
        "id": edition_id,
        "issue_number": number,
        "status": "released",
        "publication_date": publication_date,
        "source_ids": sorted(source_ids),
    }
    updated = ReleaseState(
        next_collecting,
        selected_next_id,
        (*state.released_editions, released),
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


def _collecting_edition(edition_id: str, issue_number: int) -> dict[str, Any]:
    return {
        "id": edition_id,
        "issue_number": issue_number,
        "status": "collecting",
        "source_ids": [],
    }


def _released_package_updates(package_dir: Path) -> tuple[tuple[Path, bytes], ...]:
    package_roots = [package_dir]
    package_roots.extend(
        sorted(
            (path.parent for path in package_dir.glob("*/edition-manifest.json")),
            key=lambda path: path.name,
        )
    )
    updates: list[tuple[Path, bytes]] = []
    for package_root in package_roots:
        updates.extend(_released_single_package_updates(package_root))
    return tuple(updates)


def _released_single_package_updates(package_dir: Path) -> tuple[tuple[Path, bytes], ...]:
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

    nested_package_roots = {
        path.parent for path in package_dir.glob("*/edition-manifest.json")
    }
    web_root = package_dir / "web"
    files = sorted(
        path
        for path in package_dir.rglob("*")
        if path.is_file()
        and path.name != "SHA256SUMS"
        and not path.is_relative_to(web_root)
        and not any(path.is_relative_to(nested) for nested in nested_package_roots)
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
