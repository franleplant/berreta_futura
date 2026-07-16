from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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
