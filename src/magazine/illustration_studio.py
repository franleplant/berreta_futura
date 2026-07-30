"""Safe orchestration for edition-owned interior illustration work.

The publication compiler already owns the illustration contract in
``magazine.illustration``.  This module does not create a second contract.  It
coordinates the author-time work around that contract:

* an explicit brief selects the exact article tails and closing plates;
* scaffolding reconciles that selection with the manifest and plan;
* prompt packages compile the existing plan through ``illustration_prompt``;
* registration validates and hash-binds one supplied PNG; and
* review plans expose deterministic inputs to an injected rendering adapter.

No operation generates images or changes manuscripts.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
from tempfile import gettempdir, mkstemp
from types import SimpleNamespace
from typing import Any, Protocol

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode

from .errors import ValidationError
from .illustration import (
    IllustrationAsset,
    illustration_prompt,
    load_illustration_plan,
    _review_raster,
)
from .io import load_structured
from .release import load_release_state


_ASSET_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PENDING = "PENDING"
_PLAN_PATH = Path("art/illustrations.yaml")
_MANIFEST_PATH = Path("edition.yaml")
_RELEASE_STATE_PATH = Path("library/release-state.yaml")
_LOCK_DIRECTORY = Path(gettempdir()) / "magazine-illustration-studio-locks"
_REVIEW_FILES = (Path("reviews/render.yaml"), Path("reviews/evidence.yaml"))


class IllustrationStudioConflict(ValidationError):
    """The studio state changed after the caller inspected it."""


@dataclass(frozen=True)
class IllustrationTargetBrief:
    id: str
    role: str
    subject: str
    composition: str
    alt_text: str
    credit: str
    article_id: str | None = None
    plate_index: int | None = None
    art_path: str | None = None


@dataclass(frozen=True)
class IllustrationBrief:
    schema_version: int
    edition_id: str
    assets: tuple[IllustrationTargetBrief, ...]
    direction: Mapping[str, Any] | None = None
    direction_preset: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "IllustrationBrief":
        """Parse and validate a versioned, explicit illustration brief."""

        errors: list[str] = []
        if data.get("schema_version") != 1:
            errors.append("Illustration brief requires schema_version: 1")
        edition_id = _safe_identifier(data.get("edition_id"), "edition_id", errors)
        direction = data.get("direction")
        direction_preset = data.get("direction_preset")
        if (direction is None) == (direction_preset is None):
            errors.append(
                "Illustration brief must declare exactly one of direction or "
                "direction_preset"
            )
        if direction is not None:
            if not isinstance(direction, Mapping):
                errors.append("Illustration brief direction must be a mapping")
                direction = None
            else:
                direction = dict(direction)
                for field in ("name", "visual_language", "palette"):
                    if not str(direction.get(field) or "").strip():
                        errors.append(f"Illustration brief direction requires {field}")
                for field in ("constraints", "avoid"):
                    value = direction.get(field)
                    if (
                        not isinstance(value, list)
                        or not value
                        or any(not isinstance(item, str) or not item.strip() for item in value)
                    ):
                        errors.append(
                            f"Illustration brief direction.{field} must be a "
                            "non-empty list of strings"
                        )
        if direction_preset is not None:
            if not isinstance(direction_preset, str) or not direction_preset.strip():
                errors.append(
                    "Illustration brief direction_preset must be a non-empty path"
                )
                direction_preset = None
            else:
                direction_preset = direction_preset.strip()

        rows = data.get("assets")
        if not isinstance(rows, list) or not rows:
            errors.append("Illustration brief requires a non-empty assets list")
            rows = []
        assets: list[IllustrationTargetBrief] = []
        ids: set[str] = set()
        article_ids: set[str] = set()
        plate_indices: set[int] = set()
        paths: set[str] = set()
        for index, row in enumerate(rows, start=1):
            label = f"Illustration brief asset {index}"
            if not isinstance(row, Mapping):
                errors.append(f"{label} must be a mapping")
                continue
            asset_id = _safe_identifier(row.get("id"), f"{label} id", errors)
            if asset_id in ids:
                errors.append(f"Illustration brief asset id must be unique: {asset_id}")
            ids.add(asset_id)
            role = str(row.get("role") or "").strip()
            if role not in {"article_tail", "closing_plate"}:
                errors.append(
                    f"{label} role must be article_tail or closing_plate, not {role!r}"
                )
            values: dict[str, str] = {}
            for field in ("subject", "composition", "alt_text", "credit"):
                value = str(row.get(field) or "").strip()
                if not value:
                    errors.append(f"{label} requires {field}")
                values[field] = value
            article_id = None
            plate_index = None
            if role == "article_tail":
                article_id = _safe_identifier(
                    row.get("article_id"), f"{label} article_id", errors
                )
                if article_id in article_ids:
                    errors.append(
                        f"Illustration brief article tail must be unique: {article_id}"
                    )
                article_ids.add(article_id)
                if row.get("plate_index") is not None:
                    errors.append(f"{label} article_tail must not declare plate_index")
            elif role == "closing_plate":
                if row.get("article_id") is not None:
                    errors.append(f"{label} closing_plate must not declare article_id")
                try:
                    plate_index = int(row.get("plate_index"))
                except (TypeError, ValueError):
                    errors.append(f"{label} closing_plate requires integer plate_index")
                if plate_index not in {1, 2, 3}:
                    errors.append(f"{label} plate_index must be 1, 2, or 3")
                elif plate_index in plate_indices:
                    errors.append(
                        f"Illustration brief closing plate must be unique: {plate_index}"
                    )
                elif plate_index is not None:
                    plate_indices.add(plate_index)
            raw_art_path = row.get("art_path")
            art_path = None
            if raw_art_path is not None:
                if not isinstance(raw_art_path, str) or not raw_art_path.strip():
                    errors.append(f"{label} art_path must be a non-empty path")
                else:
                    art_path = raw_art_path.strip()
                    _safe_relative_path(art_path, f"{label} art_path", errors)
                    if art_path in paths:
                        errors.append(
                            f"Illustration brief art_path must be unique: {art_path}"
                        )
                    paths.add(art_path)
            assets.append(
                IllustrationTargetBrief(
                    id=asset_id,
                    role=role,
                    article_id=article_id,
                    plate_index=plate_index,
                    art_path=art_path,
                    subject=values["subject"],
                    composition=values["composition"],
                    alt_text=values["alt_text"],
                    credit=values["credit"],
                )
            )
        if errors:
            raise ValidationError(errors)
        return cls(
            schema_version=1,
            edition_id=edition_id,
            assets=tuple(assets),
            direction=direction,
            direction_preset=direction_preset,
        )

    @classmethod
    def load(cls, path: Path) -> "IllustrationBrief":
        return cls.from_dict(load_structured(path))


@dataclass(frozen=True)
class IllustrationAssetStatus:
    id: str
    role: str
    article_id: str | None
    plate_index: int | None
    art_path: str
    brief_status: str
    asset_status: str
    asset_sha256: str | None
    actual_sha256: str | None
    error: str | None
    next_action: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "article_id": self.article_id,
            "plate_index": self.plate_index,
            "art_path": self.art_path,
            "brief_status": self.brief_status,
            "asset_status": self.asset_status,
            "asset_sha256": self.asset_sha256,
            "actual_sha256": self.actual_sha256,
            "error": self.error,
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class IllustrationStudioStatus:
    edition_id: str
    revision: str
    state: str
    plan_path: str | None
    assets: tuple[IllustrationAssetStatus, ...]
    errors: tuple[str, ...]
    next_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "edition_id": self.edition_id,
            "revision": self.revision,
            "state": self.state,
            "plan_path": self.plan_path,
            "assets": [asset.to_dict() for asset in self.assets],
            "errors": list(self.errors),
            "next_actions": list(self.next_actions),
        }


@dataclass(frozen=True)
class IllustrationStudioAction:
    operation: str
    edition_id: str
    asset_id: str | None
    writes: tuple[Path, ...]
    changed: bool
    dry_run: bool
    revision_before: str
    revision_after: str


@dataclass
class _ConditionalInstall:
    path: Path
    expected: bytes | None
    intended: bytes
    backup: Path | None = None
    installed_identity: tuple[int, int] | None = None


@dataclass(frozen=True)
class IllustrationReviewAsset:
    id: str
    role: str
    article_id: str | None
    plate_index: int | None
    art_path: Path
    asset_sha256: str
    prompt_sha256: str


@dataclass(frozen=True)
class IllustrationReviewPlan:
    edition_id: str
    revision: str
    destination: Path
    assets: tuple[IllustrationReviewAsset, ...]


class IllustrationReviewAdapter(Protocol):
    """Render review artifacts into relative names and bytes."""

    def render(self, plan: IllustrationReviewPlan) -> Mapping[str, bytes]:
        ...


class IllustrationStudio:
    """A narrow session interface for one project's illustration workflow."""

    def __init__(
        self,
        root: Path,
        *,
        review_adapter: IllustrationReviewAdapter | None = None,
    ) -> None:
        self.root = root.resolve()
        self.review_adapter = review_adapter
        self._revisions: dict[str, str] = {}

    def inspect(self, edition_id: str) -> IllustrationStudioStatus:
        edition_id = _validated_edition_id(edition_id)
        revision = self._state_revision(edition_id)
        self._revisions[edition_id] = revision
        manifest, _ = self._load_manifest(edition_id)
        raw_plan_path = manifest.get("art_direction_path")
        if not raw_plan_path:
            return IllustrationStudioStatus(
                edition_id=edition_id,
                revision=revision,
                state="missing_brief",
                plan_path=None,
                assets=(),
                errors=(),
                next_actions=(
                    f"Scaffold an explicit illustration brief for {edition_id}.",
                ),
            )
        try:
            plan_path = self._project_path(
                raw_plan_path, label="Illustration plan", must_exist=True
            )
            edition = self._edition_inventory(edition_id, manifest)
            plan = load_illustration_plan(self.root, edition)
            if plan is None:
                raise ValidationError(
                    f"Edition {edition_id} declares no illustration plan"
                )
            inventory_errors = self._inventory_errors(edition, plan)
            if inventory_errors:
                raise ValidationError(inventory_errors)
            raw_plan = load_structured(plan_path)
            raw_assets = {
                str(row.get("id")): row
                for row in raw_plan.get("assets", [])
                if isinstance(row, dict)
            }
            statuses = tuple(
                self._asset_status(asset, raw_assets.get(asset.id, {}))
                for asset in plan.assets
            )
            statuses = _mark_duplicate_asset_bytes(statuses)
        except ValidationError as exc:
            return IllustrationStudioStatus(
                edition_id=edition_id,
                revision=revision,
                state="invalid_brief",
                plan_path=str(raw_plan_path),
                assets=(),
                errors=tuple(exc.errors),
                next_actions=("Repair the illustration plan and inspect it again.",),
            )

        state = _aggregate_status(statuses)
        actions = _next_actions(edition_id, statuses)
        return IllustrationStudioStatus(
            edition_id=edition_id,
            revision=revision,
            state=state,
            plan_path=plan_path.relative_to(self.root).as_posix(),
            assets=statuses,
            errors=tuple(
                status.error for status in statuses if status.error is not None
            ),
            next_actions=actions,
        )

    status = inspect

    def scaffold(
        self,
        brief: IllustrationBrief | Mapping[str, Any] | Path,
        *,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ) -> IllustrationStudioAction:
        """Reconcile an explicit brief into the manifest and illustration plan."""

        parsed = self._coerce_brief(brief)
        edition_id = parsed.edition_id
        with self._mutation(
            edition_id,
            expected_revision,
            dry_run=dry_run,
            require_collecting=True,
        ):
            before = self._expected_revision(edition_id, expected_revision)
            manifest, manifest_bytes = self._load_manifest(edition_id)
            edition_dir = self._edition_dir(edition_id)
            plan_path = edition_dir / _PLAN_PATH
            intended_rows, manifest_tail_paths = self._brief_rows(
                parsed, manifest, edition_dir
            )
            intended_plan = {
                "schema_version": 1,
                **(
                    {"direction": dict(parsed.direction)}
                    if parsed.direction is not None
                    else {"direction_preset": parsed.direction_preset}
                ),
                "assets": intended_rows,
            }
            manifest_path_value = plan_path.relative_to(self.root).as_posix()
            selected_manifest = self._reconcile_manifest(
                manifest_bytes,
                manifest_path_value,
                manifest_tail_paths,
                path=edition_dir / _MANIFEST_PATH,
            )
            if plan_path.exists():
                self._require_compatible_plan(plan_path, intended_plan)
                selected_plan = plan_path.read_bytes()
            else:
                selected_plan = _dump_yaml(intended_plan)

            writes: list[tuple[Path, bytes]] = []
            manifest_path = edition_dir / _MANIFEST_PATH
            if selected_manifest != manifest_bytes:
                writes.append((manifest_path, selected_manifest))
            if not plan_path.exists():
                writes.append((plan_path, selected_plan))
            if not writes:
                return IllustrationStudioAction(
                    operation="scaffold",
                    edition_id=edition_id,
                    asset_id=None,
                    writes=(manifest_path, plan_path),
                    changed=False,
                    dry_run=dry_run,
                    revision_before=before,
                    revision_after=before,
                )
            if not dry_run:
                self._require_revision(edition_id, before)
                originals = {
                    target: target.read_bytes() if target.is_file() else None
                    for target, _ in writes
                }
                _replace_files(tuple(writes), expected=originals)
                try:
                    status = self.inspect(edition_id)
                    if status.state == "invalid_brief":
                        raise ValidationError(status.errors)
                except BaseException:
                    _restore_files(originals)
                    raise
                self._refresh_revision(edition_id)
            return IllustrationStudioAction(
                operation="scaffold",
                edition_id=edition_id,
                asset_id=None,
                writes=tuple(target for target, _ in writes),
                changed=True,
                dry_run=dry_run,
                revision_before=before,
                revision_after=self._revisions.get(edition_id, before),
            )

    reconcile = scaffold

    def emit_prompt_package(
        self,
        edition_id: str,
        *,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ) -> IllustrationStudioAction:
        """Compile only interior illustration prompts and their inventory."""

        edition_id = _validated_edition_id(edition_id)
        with self._mutation(
            edition_id,
            expected_revision,
            dry_run=dry_run,
            require_collecting=False,
        ):
            before = self._expected_revision(edition_id, expected_revision)
            manifest, _ = self._load_manifest(edition_id)
            edition = self._edition_inventory(edition_id, manifest)
            plan = load_illustration_plan(self.root, edition)
            if plan is None:
                raise ValidationError(
                    f"Edition {edition_id} declares no illustration plan"
                )
            errors = self._inventory_errors(edition, plan)
            if errors:
                raise ValidationError(errors)
            destination = (
                self.root
                / "output"
                / edition_id
                / "interior-illustration-prompts"
            )
            destination = _require_contained_path(
                self.root / "output",
                destination,
                label="Illustration prompt destination",
            )
            updates: list[tuple[Path, bytes]] = []
            inventory: list[dict[str, Any]] = []
            for asset in plan.assets:
                prompt = illustration_prompt(plan, asset)
                prompt_name = f"{asset.id}.txt"
                updates.append(
                    (
                        _safe_output_artifact(destination, prompt_name),
                        (prompt + "\n").encode("utf-8"),
                    )
                )
                inventory.append(
                    {
                        "id": asset.id,
                        "role": asset.role,
                        "article_id": asset.article_id,
                        "plate_index": asset.plate_index,
                        "art_path": asset.art_path.relative_to(self.root).as_posix(),
                        "prompt": prompt_name,
                        "prompt_sha256": hashlib.sha256(
                            prompt.encode("utf-8")
                        ).hexdigest(),
                        "image_sha256": (
                            _sha256(asset.art_path)
                            if asset.art_path.is_file()
                            else None
                        ),
                        "alt_text": asset.alt_text,
                        "credit": asset.credit,
                    }
                )
            payload = {
                "schema_version": 1,
                "edition_id": edition_id,
                "plan_path": plan.path.relative_to(self.root).as_posix(),
                "plan_sha256": _sha256(plan.path),
                "direction_preset": (
                    {
                        "path": plan.direction_path.relative_to(self.root).as_posix(),
                        "sha256": _sha256(plan.direction_path),
                    }
                    if plan.direction_path is not None
                    else None
                ),
                "reference_images": [
                    {
                        "path": path.relative_to(self.root).as_posix(),
                        "sha256": _sha256(path),
                    }
                    for path in plan.direction.reference_paths
                ],
                "assets": inventory,
            }
            updates.append(
                (
                    _safe_output_artifact(destination, "illustrations.json"),
                    (
                        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
                    ).encode("utf-8"),
                )
            )
            changed = tuple(
                (path, content)
                for path, content in updates
                if not path.is_file() or path.read_bytes() != content
            )
            if not dry_run and changed:
                self._require_revision(edition_id, before)
                _replace_files(
                    changed,
                    expected={
                        path: path.read_bytes() if path.is_file() else None
                        for path, _ in changed
                    },
                )
            return IllustrationStudioAction(
                operation="emit_prompt_package",
                edition_id=edition_id,
                asset_id=None,
                writes=tuple(path for path, _ in updates),
                changed=bool(changed),
                dry_run=dry_run,
                revision_before=before,
                revision_after=before,
            )

    def register_asset(
        self,
        edition_id: str,
        asset_id: str,
        source: Path,
        *,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ) -> IllustrationStudioAction:
        """Validate, copy, and hash-bind one supplied PNG atomically."""

        edition_id = _validated_edition_id(edition_id)
        identifier_errors: list[str] = []
        _safe_identifier(asset_id, "asset_id", identifier_errors)
        if identifier_errors:
            raise ValidationError(identifier_errors)
        with self._mutation(
            edition_id,
            expected_revision,
            dry_run=dry_run,
            require_collecting=True,
        ):
            before = self._expected_revision(edition_id, expected_revision)
            manifest, _ = self._load_manifest(edition_id)
            edition = self._edition_inventory(edition_id, manifest)
            plan = load_illustration_plan(self.root, edition)
            if plan is None:
                raise ValidationError(
                    f"Edition {edition_id} declares no illustration plan"
                )
            inventory_errors = self._inventory_errors(edition, plan)
            if inventory_errors:
                raise ValidationError(inventory_errors)
            matches = [asset for asset in plan.assets if asset.id == asset_id]
            if len(matches) != 1:
                raise ValidationError(
                    f"Illustration plan has no unique asset id {asset_id!r}"
                )
            asset = matches[0]
            source_path = _require_plain_file(source, label="Illustration source")
            target = _require_contained_path(
                self._edition_dir(edition_id) / "art",
                asset.art_path,
                label=f"Illustration asset {asset_id}",
            )
            errors = _review_raster(replace(asset, art_path=source_path))
            if errors:
                raise ValidationError(errors)
            source_bytes = source_path.read_bytes()
            digest = hashlib.sha256(source_bytes).hexdigest()
            for other in plan.assets:
                if other.id == asset_id or not other.art_path.is_file():
                    continue
                if _sha256(other.art_path) == digest:
                    raise ValidationError(
                        f"Illustration asset duplicates bytes from {other.id}: {source}"
                    )
            if target.is_file() and target.read_bytes() != source_bytes:
                raise IllustrationStudioConflict(
                    f"Illustration target already exists with different bytes: {target}"
                )
            plan_path = plan.path
            plan_bytes = plan_path.read_bytes()
            updated_plan = _splice_asset_hash(
                plan_bytes, asset_id, digest, path=plan_path
            )
            writes: list[tuple[Path, bytes]] = []
            if not target.is_file():
                writes.append((target, source_bytes))
            if updated_plan != plan_bytes:
                writes.append((plan_path, updated_plan))
            if not writes:
                return IllustrationStudioAction(
                    operation="register_asset",
                    edition_id=edition_id,
                    asset_id=asset_id,
                    writes=(target, plan_path),
                    changed=False,
                    dry_run=dry_run,
                    revision_before=before,
                    revision_after=before,
                )
            if not dry_run:
                self._require_revision(edition_id, before)
                originals = {
                    path: path.read_bytes() if path.is_file() else None
                    for path, _ in writes
                }
                _replace_files(tuple(writes), expected=originals)
                try:
                    actual = _sha256(target)
                    if actual != digest:
                        raise ValidationError(
                            f"Illustration registration hash mismatch: {target}"
                        )
                    post_errors = _review_raster(asset)
                    if post_errors:
                        raise ValidationError(post_errors)
                    status = self.inspect(edition_id)
                    item = next(
                        (
                            row
                            for row in status.assets
                            if row.id == asset_id
                        ),
                        None,
                    )
                    if item is None or item.asset_status != "ready":
                        raise ValidationError(
                            item.error
                            if item is not None and item.error
                            else f"Illustration asset {asset_id} did not become ready"
                        )
                except BaseException:
                    _restore_files(originals)
                    raise
                self._refresh_revision(edition_id)
            return IllustrationStudioAction(
                operation="register_asset",
                edition_id=edition_id,
                asset_id=asset_id,
                writes=tuple(path for path, _ in writes),
                changed=True,
                dry_run=dry_run,
                revision_before=before,
                revision_after=self._revisions.get(edition_id, before),
            )

    def review_plan(self, edition_id: str) -> IllustrationReviewPlan:
        """Return the stable set of ready illustrations a reviewer must inspect."""

        status = self.inspect(edition_id)
        if status.state != "ready":
            raise ValidationError(
                f"Illustration review requires ready assets, found {status.state}"
            )
        manifest, _ = self._load_manifest(edition_id)
        edition = self._edition_inventory(edition_id, manifest)
        plan = load_illustration_plan(self.root, edition)
        assert plan is not None
        assets = tuple(
            IllustrationReviewAsset(
                id=asset.id,
                role=asset.role,
                article_id=asset.article_id,
                plate_index=asset.plate_index,
                art_path=asset.art_path,
                asset_sha256=_sha256(asset.art_path),
                prompt_sha256=hashlib.sha256(
                    illustration_prompt(plan, asset).encode("utf-8")
                ).hexdigest(),
            )
            for asset in plan.assets
        )
        return IllustrationReviewPlan(
            edition_id=edition_id,
            revision=status.revision,
            destination=self.root
            / "output"
            / edition_id
            / "illustration-review",
            assets=assets,
        )

    def create_review_sheet(
        self,
        edition_id: str,
        *,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ) -> IllustrationStudioAction:
        """Write contained review artifacts returned by the injected adapter."""

        edition_id = _validated_edition_id(edition_id)
        with self._mutation(
            edition_id,
            expected_revision,
            dry_run=dry_run,
            require_collecting=False,
        ):
            plan = self.review_plan(edition_id)
            expected = expected_revision or plan.revision
            if expected != plan.revision:
                raise IllustrationStudioConflict(
                    f"Illustration studio state is stale (expected {expected}, "
                    f"found {plan.revision})"
                )
            if dry_run:
                return IllustrationStudioAction(
                    operation="create_review_sheet",
                    edition_id=edition_id,
                    asset_id=None,
                    writes=(plan.destination,),
                    changed=True,
                    dry_run=True,
                    revision_before=expected,
                    revision_after=expected,
                )
            if self.review_adapter is None:
                raise ValidationError(
                    "Illustration review rendering requires an "
                    "IllustrationReviewAdapter"
                )
            rendered = self.review_adapter.render(plan)
            if not isinstance(rendered, Mapping) or not rendered:
                raise ValidationError(
                    "Illustration review adapter must return at least one artifact"
                )
            updates: list[tuple[Path, bytes]] = []
            if any(not isinstance(name, str) for name in rendered):
                raise ValidationError(
                    "Illustration review artifact names must be strings"
                )
            targets: set[Path] = set()
            for name in sorted(rendered):
                content = rendered[name]
                if not isinstance(content, bytes):
                    raise ValidationError(
                        f"Illustration review artifact {name!r} must contain bytes"
                    )
                path = _safe_output_artifact(plan.destination, name)
                if path in targets:
                    raise ValidationError(
                        "Illustration review artifact names resolve to the same "
                        f"destination: {name}"
                    )
                targets.add(path)
                updates.append((path, content))
            changed = tuple(
                (path, content)
                for path, content in updates
                if not path.is_file() or path.read_bytes() != content
            )
            if not dry_run and changed:
                self._require_revision(edition_id, expected)
                _replace_files(
                    changed,
                    expected={
                        path: path.read_bytes() if path.is_file() else None
                        for path, _ in changed
                    },
                )
            return IllustrationStudioAction(
                operation="create_review_sheet",
                edition_id=edition_id,
                asset_id=None,
                writes=tuple(path for path, _ in updates),
                changed=bool(changed),
                dry_run=dry_run,
                revision_before=expected,
                revision_after=expected,
            )

    def _coerce_brief(
        self, value: IllustrationBrief | Mapping[str, Any] | Path
    ) -> IllustrationBrief:
        if isinstance(value, IllustrationBrief):
            return IllustrationBrief.from_dict(_brief_dict(value))
        if isinstance(value, Path):
            return IllustrationBrief.load(value)
        if isinstance(value, Mapping):
            return IllustrationBrief.from_dict(value)
        raise ValidationError(
            "Illustration brief must be an IllustrationBrief, mapping, or path"
        )

    def _brief_rows(
        self,
        brief: IllustrationBrief,
        manifest: Mapping[str, Any],
        edition_dir: Path,
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        article_rows = manifest.get("articles")
        if not isinstance(article_rows, list):
            raise ValidationError("Edition articles must be a list")
        articles = {
            str(row.get("id")): row for row in article_rows if isinstance(row, dict)
        }
        closing_rows = manifest.get("closing_plates") or []
        if not isinstance(closing_rows, list):
            raise ValidationError("Edition closing_plates must be a list")
        selected_articles = {
            target.article_id
            for target in brief.assets
            if target.role == "article_tail"
        }
        existing_tails = {
            article_id
            for article_id, row in articles.items()
            if row.get("tail_art_path")
        }
        unselected = sorted(existing_tails - selected_articles)
        if unselected:
            raise ValidationError(
                "Illustration brief omits manifest-declared article tails: "
                + ", ".join(unselected)
            )
        selected_plates = {
            target.plate_index
            for target in brief.assets
            if target.role == "closing_plate"
        }
        expected_plates = set(range(1, len(closing_rows) + 1))
        if selected_plates != expected_plates:
            raise ValidationError(
                "Illustration brief closing plates must match the edition's "
                f"configured indices exactly (brief {sorted(selected_plates)}, "
                f"edition {sorted(expected_plates)})"
            )
        rows: list[dict[str, Any]] = []
        tail_paths: dict[str, str] = {}
        normalized_paths: set[str] = set()
        for target in brief.assets:
            if target.role == "article_tail":
                assert target.article_id is not None
                if target.article_id not in articles:
                    raise ValidationError(
                        f"Illustration brief names unknown article: {target.article_id}"
                    )
                manifest_value = articles[target.article_id].get("tail_art_path")
                art_path = target.art_path or (
                    f"editions/{brief.edition_id}/art/article-tails/"
                    f"{target.article_id}.png"
                )
                if manifest_value:
                    manifest_path = self._edition_relative_project_path(
                        edition_dir, manifest_value, label="Article tail"
                    )
                    if manifest_path != art_path:
                        raise ValidationError(
                            f"Illustration brief path for {target.article_id} does "
                            f"not match tail_art_path: {manifest_value}"
                        )
                tail_paths[target.article_id] = art_path
                row = {
                    "id": target.id,
                    "role": target.role,
                    "article_id": target.article_id,
                    "art_path": art_path,
                }
            else:
                assert target.plate_index is not None
                closing = closing_rows[target.plate_index - 1]
                if not isinstance(closing, Mapping) or not closing.get("art_path"):
                    raise ValidationError(
                        f"Closing plate {target.plate_index} requires art_path"
                    )
                existing_path = self._edition_relative_project_path(
                    edition_dir,
                    closing["art_path"],
                    label=f"Closing plate {target.plate_index}",
                )
                if target.art_path and target.art_path != existing_path:
                    raise ValidationError(
                        f"Illustration brief path for closing plate "
                        f"{target.plate_index} does not match edition.yaml: "
                        f"{closing['art_path']}"
                    )
                art_path = existing_path
                row = {
                    "id": target.id,
                    "role": target.role,
                    "plate_index": target.plate_index,
                    "art_path": art_path,
                }
            resolved = self._project_path(
                art_path, label=f"Illustration asset {target.id}", must_exist=False
            )
            _require_contained_path(
                edition_dir / "art",
                resolved,
                label=f"Illustration asset {target.id}",
            )
            if art_path in normalized_paths:
                raise ValidationError(
                    f"Illustration brief art_path must be unique: {art_path}"
                )
            normalized_paths.add(art_path)
            row.update(
                {
                    "asset_sha256": _PENDING,
                    "subject": target.subject,
                    "composition": target.composition,
                    "alt_text": target.alt_text,
                    "credit": target.credit,
                }
            )
            rows.append(row)
        return rows, tail_paths

    def _reconcile_manifest(
        self,
        content: bytes,
        plan_path: str,
        tail_paths: Mapping[str, str],
        *,
        path: Path,
    ) -> bytes:
        text = _decode_yaml(content, path)
        document = _compose_mapping(text, path)
        edits: list[tuple[int, int, str]] = []
        art_node = _optional_mapping_value(document, "art_direction_path")
        if art_node is not None:
            if not isinstance(art_node, ScalarNode) or art_node.value != plan_path:
                raise ValidationError(
                    "Edition art_direction_path already names a different plan"
                )
        else:
            insertion = _top_level_insertion(document, text)
            edits.append(
                (insertion, insertion, f"art_direction_path: {plan_path}\n")
            )
        articles_node = _mapping_value(document, "articles", path)
        if not isinstance(articles_node, SequenceNode):
            raise ValidationError("Edition articles must be a list")
        found: set[str] = set()
        for item in articles_node.value:
            if not isinstance(item, MappingNode):
                continue
            id_node = _optional_mapping_value(item, "id")
            if not isinstance(id_node, ScalarNode) or id_node.value not in tail_paths:
                continue
            article_id = id_node.value
            found.add(article_id)
            tail_node = _optional_mapping_value(item, "tail_art_path")
            if tail_node is not None:
                declared = (
                    tail_node.value if isinstance(tail_node, ScalarNode) else None
                )
                normalized = self._edition_relative_project_path(
                    path.parent, declared, label=f"Article {article_id} tail_art_path"
                )
                if normalized != tail_paths[article_id]:
                    raise ValidationError(
                        f"Article {article_id} tail_art_path already names a "
                        "different asset"
                    )
                continue
            offset = item.end_mark.index
            indent = item.start_mark.column
            edits.append(
                (
                    offset,
                    offset,
                    " " * indent
                    + f"tail_art_path: {tail_paths[article_id]}\n",
                )
            )
        missing = sorted(set(tail_paths) - found)
        if missing:
            raise ValidationError(
                "Illustration brief names unknown articles: " + ", ".join(missing)
            )
        return _apply_text_edits(text, edits).encode("utf-8")

    def _require_compatible_plan(
        self, path: Path, intended: Mapping[str, Any]
    ) -> None:
        existing = load_structured(path)
        if existing.get("schema_version") != 1:
            raise IllustrationStudioConflict(
                f"Existing illustration plan is not schema_version 1: {path}"
            )
        intended_direction = intended.get("direction")
        if intended_direction is not None and existing.get("direction") != intended_direction:
            raise IllustrationStudioConflict(
                "Existing illustration plan has authored direction that differs "
                "from the brief"
            )
        intended_preset = intended.get("direction_preset")
        if intended_preset is not None and existing.get("direction_preset") != intended_preset:
            raise IllustrationStudioConflict(
                "Existing illustration plan has an authored direction preset that "
                "differs from the brief"
            )
        existing_rows = existing.get("assets")
        intended_rows = intended.get("assets")
        if not isinstance(existing_rows, list) or not isinstance(intended_rows, list):
            raise IllustrationStudioConflict(
                f"Existing illustration plan has invalid assets: {path}"
            )
        comparable = lambda row: {
            key: value
            for key, value in row.items()
            if key != "asset_sha256"
        }
        if (
            len(existing_rows) != len(intended_rows)
            or any(not isinstance(row, dict) for row in existing_rows)
            or [comparable(row) for row in existing_rows]
            != [comparable(row) for row in intended_rows]
        ):
            raise IllustrationStudioConflict(
                "Existing illustration plan has authored assets that differ from "
                "the brief"
            )

    def _asset_status(
        self, asset: IllustrationAsset, raw: Mapping[str, Any]
    ) -> IllustrationAssetStatus:
        declared_digest = str(raw.get("asset_sha256") or "").strip()
        legacy = not declared_digest
        actual = _sha256(asset.art_path) if asset.art_path.is_file() else None
        if actual is None:
            if _SHA256.fullmatch(declared_digest):
                state = "missing_asset"
                error = f"Registered illustration asset is missing: {asset.art_path}"
                action = f"Restore or register asset {asset.id}."
            elif declared_digest not in {"", _PENDING}:
                state = "hash_mismatch"
                error = (
                    f"Illustration asset {asset.id} has invalid asset_sha256 "
                    f"{declared_digest!r}"
                )
                action = f"Register asset {asset.id} to compute its hash."
            else:
                state = "prompt_ready"
                error = None
                action = (
                    f"Emit prompts, create the PNG, then register asset {asset.id}."
                )
        elif _SHA256.fullmatch(declared_digest) and declared_digest != actual:
            state = "hash_mismatch"
            error = (
                f"Illustration asset hash mismatch: expected {declared_digest}, "
                f"found {actual}"
            )
            action = f"Restore the registered bytes for {asset.id}."
        else:
            raster_errors = _review_raster(asset)
            if raster_errors:
                state = "invalid_raster"
                error = "; ".join(raster_errors)
                action = f"Replace and register a valid PNG for {asset.id}."
            elif declared_digest == _PENDING:
                state = "prompt_ready"
                error = None
                action = f"Register the existing PNG for {asset.id}."
            elif declared_digest and not _SHA256.fullmatch(declared_digest):
                state = "hash_mismatch"
                error = (
                    f"Illustration asset {asset.id} has invalid asset_sha256 "
                    f"{declared_digest!r}"
                )
                action = f"Register asset {asset.id} to compute its hash."
            else:
                state = "ready"
                error = None
                action = None
        return IllustrationAssetStatus(
            id=asset.id,
            role=asset.role,
            article_id=asset.article_id,
            plate_index=asset.plate_index,
            art_path=asset.art_path.relative_to(self.root).as_posix(),
            brief_status="prompt_ready",
            asset_status=state,
            asset_sha256=None if legacy else declared_digest,
            actual_sha256=actual,
            error=error,
            next_action=action,
        )

    def _inventory_errors(self, edition: Any, plan: Any) -> list[str]:
        planned_tails = {
            asset.article_id: asset.art_path
            for asset in plan.assets
            if asset.role == "article_tail"
        }
        declared_tails = {
            article.id: article.tail_art
            for article in edition.articles
            if article.tail_art is not None
        }
        errors: list[str] = []
        if set(planned_tails) != set(declared_tails):
            errors.append(
                "Illustration plan article tails do not match edition.yaml "
                f"(plan {sorted(planned_tails)}, edition {sorted(declared_tails)})"
            )
        for article_id in set(planned_tails) & set(declared_tails):
            if planned_tails[article_id] != declared_tails[article_id]:
                errors.append(
                    f"Illustration plan path for {article_id} does not match "
                    "tail_art_path"
                )
        planned_plates = {
            asset.plate_index: asset.art_path
            for asset in plan.assets
            if asset.role == "closing_plate"
        }
        declared_plates = {
            index: plate.art_path
            for index, plate in enumerate(edition.closing_plates, start=1)
        }
        if set(planned_plates) != set(declared_plates):
            errors.append(
                "Illustration plan closing plates do not match edition.yaml "
                f"(plan {sorted(planned_plates)}, edition {sorted(declared_plates)})"
            )
        for index in set(planned_plates) & set(declared_plates):
            if planned_plates[index] != declared_plates[index]:
                errors.append(
                    f"Illustration plan path for closing plate {index} does not "
                    "match edition.yaml"
                )
        return errors

    def _edition_inventory(
        self, edition_id: str, manifest: Mapping[str, Any]
    ) -> Any:
        edition_dir = self._edition_dir(edition_id)
        articles: list[Any] = []
        article_rows = manifest.get("articles")
        if not isinstance(article_rows, list):
            raise ValidationError("Edition articles must be a list")
        ids: set[str] = set()
        for row in article_rows:
            if not isinstance(row, Mapping):
                raise ValidationError("Every edition article must be a mapping")
            article_id = str(row.get("id") or "").strip()
            if not article_id or article_id in ids:
                raise ValidationError("Edition article ids must be non-empty and unique")
            ids.add(article_id)
            tail = (
                self._manifest_asset_path(
                    edition_dir,
                    row["tail_art_path"],
                    label=f"Article {article_id} tail_art_path",
                )
                if row.get("tail_art_path")
                else None
            )
            articles.append(SimpleNamespace(id=article_id, tail_art=tail))
        closing_rows = manifest.get("closing_plates") or []
        if not isinstance(closing_rows, list):
            raise ValidationError("Edition closing_plates must be a list")
        plates: list[Any] = []
        for index, row in enumerate(closing_rows, start=1):
            if not isinstance(row, Mapping) or not row.get("art_path"):
                raise ValidationError(
                    f"Closing plate {index} requires title and art_path"
                )
            plates.append(
                SimpleNamespace(
                    title=str(row.get("title") or ""),
                    art_path=self._manifest_asset_path(
                        edition_dir,
                        row["art_path"],
                        label=f"Closing plate {index}",
                    ),
                )
            )
        return SimpleNamespace(
            id=edition_id,
            raw=dict(manifest),
            articles=tuple(articles),
            closing_plates=tuple(plates),
        )

    def _manifest_asset_path(
        self, edition_dir: Path, value: object, *, label: str
    ) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"{label} requires a non-empty path")
        path = Path(value)
        candidate = self.root / path if path.parts[:1] == ("editions",) else edition_dir / path
        return _require_contained_path(
            edition_dir / "art", candidate, label=label
        )

    def _edition_relative_project_path(
        self, edition_dir: Path, value: object, *, label: str
    ) -> str:
        path = self._manifest_asset_path(edition_dir, value, label=label)
        return path.relative_to(self.root).as_posix()

    def _project_path(
        self, value: object, *, label: str, must_exist: bool
    ) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"{label} requires a non-empty path")
        candidate = self.root / value
        path = _require_contained_path(self.root, candidate, label=label)
        if must_exist and not path.is_file():
            raise ValidationError(f"{label} not found: {path}")
        return path

    def _edition_dir(self, edition_id: str) -> Path:
        path = self.root / "editions" / edition_id
        return _require_contained_path(
            self.root / "editions", path, label="Edition directory"
        )

    def _load_manifest(
        self, edition_id: str
    ) -> tuple[dict[str, Any], bytes]:
        path = self._edition_dir(edition_id) / _MANIFEST_PATH
        if not path.is_file():
            raise ValidationError(f"Edition manifest not found: {path}")
        content = path.read_bytes()
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise ValidationError(f"Cannot parse edition manifest {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValidationError(f"Edition manifest must be a mapping: {path}")
        if data.get("id") != edition_id:
            raise ValidationError(
                f"Edition id {data.get('id')!r} does not match directory "
                f"{edition_id!r}"
            )
        return data, content

    def _require_mutable(self, edition_id: str) -> None:
        state_path = self.root / _RELEASE_STATE_PATH
        if not state_path.is_file():
            raise ValidationError(f"Release state not found: {state_path}")
        state = load_release_state(state_path)
        if edition_id not in state.collecting_edition_ids:
            raise ValidationError(
                f"Illustration assets can change only in a collecting edition: "
                f"{edition_id}"
            )
        edition_dir = self._edition_dir(edition_id)
        reviews = [path for path in _REVIEW_FILES if (edition_dir / path).is_file()]
        if reviews:
            raise ValidationError(
                "Illustration assets cannot change after edition review records "
                "exist: " + ", ".join(path.as_posix() for path in reviews)
            )

    @contextmanager
    def _mutation(
        self,
        edition_id: str,
        expected_revision: str | None,
        *,
        dry_run: bool,
        require_collecting: bool,
    ):
        expected = self._expected_revision(edition_id, expected_revision)
        if dry_run:
            self._require_revision(edition_id, expected)
            if require_collecting:
                self._require_mutable(edition_id)
            yield
            return
        lock_path = _LOCK_DIRECTORY / (
            hashlib.sha256(
                f"{self.root}:{edition_id}".encode("utf-8")
            ).hexdigest()
            + ".lock"
        )
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise IllustrationStudioConflict(
                    f"Another illustration studio operation is active: {lock_path}"
                ) from exc
            self._require_revision(edition_id, expected)
            if require_collecting:
                self._require_mutable(edition_id)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _expected_revision(
        self, edition_id: str, explicit: str | None
    ) -> str:
        current = self._state_revision(edition_id)
        remembered = self._revisions.get(edition_id)
        expected = explicit or remembered or current
        if remembered is not None and remembered != expected:
            raise IllustrationStudioConflict(
                f"Illustration studio state is stale (expected {expected}, "
                f"session has {remembered})"
            )
        return expected

    def _require_revision(self, edition_id: str, expected: str) -> None:
        current = self._state_revision(edition_id)
        if current != expected:
            raise IllustrationStudioConflict(
                f"Illustration studio state is stale (expected {expected}, "
                f"found {current})"
            )

    def _refresh_revision(self, edition_id: str) -> None:
        self._revisions[edition_id] = self._state_revision(edition_id)

    def _state_revision(self, edition_id: str) -> str:
        digest = hashlib.sha256()
        edition_dir = self._edition_dir(edition_id)
        candidates = [
            edition_dir / _MANIFEST_PATH,
            edition_dir / _PLAN_PATH,
            self.root / _RELEASE_STATE_PATH,
            *(edition_dir / path for path in _REVIEW_FILES),
        ]
        plan_paths: set[Path] = {edition_dir / _PLAN_PATH}
        manifest_path = edition_dir / _MANIFEST_PATH
        if manifest_path.is_file():
            try:
                manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
                raw_plan = (
                    manifest.get("art_direction_path")
                    if isinstance(manifest, dict)
                    else None
                )
                if raw_plan:
                    declared_plan = self._project_path(
                        raw_plan, label="Illustration plan", must_exist=False
                    )
                    candidates.append(declared_plan)
                    plan_paths.add(declared_plan)
            except (ValidationError, yaml.YAMLError):
                pass
        for plan_path in sorted(plan_paths):
            if not plan_path.is_file():
                continue
            try:
                data = load_structured(plan_path)
                rows = data.get("assets")
                for row in rows if isinstance(rows, list) else []:
                    if isinstance(row, dict) and row.get("art_path"):
                        candidates.append(
                            self._project_path(
                                row["art_path"],
                                label="Illustration asset",
                                must_exist=False,
                            )
                        )
                direction = data.get("direction")
                preset_value = data.get("direction_preset")
                if preset_value:
                    preset_path = self._project_path(
                        preset_value,
                        label="Illustration direction preset",
                        must_exist=False,
                    )
                    candidates.append(preset_path)
                    if preset_path.is_file():
                        preset = load_structured(preset_path)
                        direction = preset.get("direction")
                if isinstance(direction, dict):
                    references = direction.get("reference_images")
                    for reference in (
                        references if isinstance(references, list) else []
                    ):
                        candidates.append(
                            self._project_path(
                                reference,
                                label="Illustration direction reference",
                                must_exist=False,
                            )
                        )
            except ValidationError:
                pass
        for path in sorted(set(candidates)):
            try:
                label = path.relative_to(self.root).as_posix()
            except ValueError:
                continue
            digest.update(label.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes() if path.is_file() else b"<missing>")
            digest.update(b"\0")
        return digest.hexdigest()


def _validated_edition_id(value: object) -> str:
    errors: list[str] = []
    result = _safe_identifier(value, "edition_id", errors)
    if errors:
        raise ValidationError(errors)
    return result


def _brief_dict(brief: IllustrationBrief) -> dict[str, Any]:
    return {
        "schema_version": brief.schema_version,
        "edition_id": brief.edition_id,
        **(
            {"direction": dict(brief.direction)}
            if brief.direction is not None
            else {"direction_preset": brief.direction_preset}
        ),
        "assets": [
            {
                "id": asset.id,
                "role": asset.role,
                **(
                    {"article_id": asset.article_id}
                    if asset.role == "article_tail"
                    else {"plate_index": asset.plate_index}
                ),
                **({"art_path": asset.art_path} if asset.art_path else {}),
                "subject": asset.subject,
                "composition": asset.composition,
                "alt_text": asset.alt_text,
                "credit": asset.credit,
            }
            for asset in brief.assets
        ],
    }


def _safe_identifier(value: object, label: str, errors: list[str]) -> str:
    result = str(value or "").strip()
    if not _ASSET_ID.fullmatch(result):
        errors.append(
            f"Illustration brief {label} must contain lowercase letters, "
            "numbers, and single hyphens"
        )
    return result


def _safe_relative_path(value: str, label: str, errors: list[str]) -> None:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        errors.append(f"{label} must be a safe project-relative path")


def _aggregate_status(assets: tuple[IllustrationAssetStatus, ...]) -> str:
    states = {asset.asset_status for asset in assets}
    for state in (
        "duplicate_asset",
        "invalid_raster",
        "hash_mismatch",
        "missing_asset",
        "prompt_ready",
    ):
        if state in states:
            return state
    return "ready"


def _mark_duplicate_asset_bytes(
    assets: tuple[IllustrationAssetStatus, ...],
) -> tuple[IllustrationAssetStatus, ...]:
    by_digest: dict[str, list[str]] = {}
    for asset in assets:
        if asset.actual_sha256 is not None:
            by_digest.setdefault(asset.actual_sha256, []).append(asset.id)
    duplicate_ids = {
        asset_id
        for ids in by_digest.values()
        if len(ids) > 1
        for asset_id in ids
    }
    if not duplicate_ids:
        return assets
    duplicates_by_id = {
        asset_id: tuple(sorted(ids))
        for ids in by_digest.values()
        if len(ids) > 1
        for asset_id in ids
    }
    return tuple(
        replace(
            asset,
            asset_status="duplicate_asset",
            error=(
                "Illustration asset duplicates committed bytes shared by: "
                + ", ".join(duplicates_by_id[asset.id])
            ),
            next_action=(
                f"Replace and register distinct artwork for {asset.id}."
            ),
        )
        if asset.id in duplicate_ids
        else asset
        for asset in assets
    )


def _next_actions(
    edition_id: str, assets: tuple[IllustrationAssetStatus, ...]
) -> tuple[str, ...]:
    actions: list[str] = []
    if any(asset.asset_status == "prompt_ready" for asset in assets):
        actions.append(f"Emit the interior illustration prompts for {edition_id}.")
    actions.extend(
        asset.next_action
        for asset in assets
        if asset.next_action is not None and asset.next_action not in actions
    )
    if not actions:
        actions.append(f"Create the illustration review sheet for {edition_id}.")
    return tuple(actions)


def _require_plain_file(path: Path, *, label: str) -> Path:
    lexical = Path(os.path.abspath(path))
    resolved = path.resolve()
    if lexical != resolved:
        raise ValidationError(f"{label} uses a symlink or redirected path: {path}")
    if not lexical.is_file():
        raise ValidationError(f"{label} does not exist: {path}")
    return lexical


def _require_contained_path(root: Path, path: Path, *, label: str) -> Path:
    resolved_root = root.resolve()
    lexical = Path(os.path.abspath(path))
    resolved = path.resolve()
    try:
        lexical.relative_to(resolved_root)
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValidationError(f"{label} escapes {resolved_root}: {path}") from exc
    if lexical != resolved:
        raise ValidationError(
            f"{label} uses a symlink or redirected path component: {path}"
        )
    return lexical


def _safe_output_artifact(destination: Path, value: object) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(
            "Illustration review artifact name must be a non-empty relative path"
        )
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or "." in relative.parts:
        raise ValidationError(
            f"Illustration review artifact name must be relative: {value}"
        )
    target = destination / relative
    return _require_contained_path(
        destination, target, label="Illustration review artifact"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dump_yaml(data: Mapping[str, Any]) -> bytes:
    return yaml.safe_dump(
        dict(data), sort_keys=False, allow_unicode=True, width=100
    ).encode("utf-8")


def _decode_yaml(content: bytes, path: Path) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"YAML file must be UTF-8: {path}") from exc


def _compose_mapping(text: str, path: Path) -> MappingNode:
    try:
        document = yaml.compose(text)
    except yaml.YAMLError as exc:
        raise ValidationError(f"Cannot parse YAML file {path}: {exc}") from exc
    if not isinstance(document, MappingNode):
        raise ValidationError(f"YAML file must contain a mapping: {path}")
    return document


def _optional_mapping_value(
    node: MappingNode, key: str
) -> Any | None:
    matches = [
        value_node
        for key_node, value_node in node.value
        if isinstance(key_node, ScalarNode) and key_node.value == key
    ]
    if len(matches) > 1:
        raise ValidationError(f"YAML mapping has duplicate {key} fields")
    return matches[0] if matches else None


def _mapping_value(node: MappingNode, key: str, path: Path) -> Any:
    value = _optional_mapping_value(node, key)
    if value is None:
        raise ValidationError(f"YAML file requires {key}: {path}")
    return value


def _top_level_insertion(document: MappingNode, text: str) -> int:
    schema_node = _optional_mapping_value(document, "schema_version")
    if schema_node is None:
        return 0
    newline = text.find("\n", schema_node.end_mark.index)
    return len(text) if newline < 0 else newline + 1


def _apply_text_edits(
    text: str, edits: list[tuple[int, int, str]]
) -> str:
    result = text
    for start, end, replacement in sorted(edits, reverse=True):
        result = result[:start] + replacement + result[end:]
    return result


def _splice_asset_hash(
    content: bytes, asset_id: str, digest: str, *, path: Path
) -> bytes:
    text = _decode_yaml(content, path)
    document = _compose_mapping(text, path)
    assets_node = _mapping_value(document, "assets", path)
    if not isinstance(assets_node, SequenceNode):
        raise ValidationError(f"Illustration plan assets must be a list: {path}")
    matches: list[MappingNode] = []
    for item in assets_node.value:
        if not isinstance(item, MappingNode):
            continue
        id_node = _optional_mapping_value(item, "id")
        if isinstance(id_node, ScalarNode) and id_node.value == asset_id:
            matches.append(item)
    if len(matches) != 1:
        raise ValidationError(
            f"Illustration plan requires exactly one asset {asset_id!r}: {path}"
        )
    row = matches[0]
    digest_node = _optional_mapping_value(row, "asset_sha256")
    if digest_node is not None:
        if not isinstance(digest_node, ScalarNode):
            raise ValidationError(
                f"Illustration asset {asset_id} asset_sha256 must be a scalar"
            )
        updated = (
            text[: digest_node.start_mark.index]
            + digest
            + text[digest_node.end_mark.index :]
        )
    else:
        offset = row.end_mark.index
        indent = row.start_mark.column
        updated = (
            text[:offset]
            + " " * indent
            + f"asset_sha256: {digest}\n"
            + text[offset:]
        )
    return updated.encode("utf-8")


def _replace_files(
    updates: tuple[tuple[Path, bytes], ...],
    *,
    expected: Mapping[Path, bytes | None],
) -> None:
    update_contents = dict(updates)
    if len(update_contents) != len(updates):
        raise ValidationError(
            "Illustration studio update targets must be unique"
        )
    staged: dict[Path, Path] = {}
    installs: list[_ConditionalInstall] = []
    try:
        for target, content in updates:
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, raw = mkstemp(prefix=f".{target.name}.", dir=target.parent)
            temporary = Path(raw)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
            staged[target] = temporary
        _assert_expected_files(expected, committed={})
        for target, content in updates:
            committed = {
                install.path: install.intended
                for install in installs
                if install.installed_identity is not None
            }
            _assert_expected_files(expected, committed=committed)
            install = _prepare_conditional_install(
                target,
                expected.get(target),
                content,
            )
            installs.append(install)
            _install_exclusive(staged[target], target)
            stat = target.stat()
            install.installed_identity = (stat.st_dev, stat.st_ino)
        _assert_expected_files(expected, committed=update_contents)
    except BaseException:
        for install in reversed(installs):
            _restore_conditional_install(install)
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
        raise
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


def _assert_expected_files(
    expected: Mapping[Path, bytes | None],
    *,
    committed: Mapping[Path, bytes],
) -> None:
    conflicts: list[Path] = []
    for path, original in expected.items():
        wanted = committed.get(path, original)
        current = (
            path.read_bytes()
            if path.is_file() and not path.is_symlink()
            else None
        )
        if current != wanted:
            conflicts.append(path)
    if conflicts:
        raise IllustrationStudioConflict(
            "Illustration studio state changed during commit and was preserved: "
            + ", ".join(str(path) for path in conflicts)
        )


def _prepare_conditional_install(
    path: Path,
    expected: bytes | None,
    intended: bytes,
) -> _ConditionalInstall:
    install = _ConditionalInstall(path, expected, intended)
    if expected is None:
        if path.exists() or path.is_symlink():
            raise IllustrationStudioConflict(
                f"Destination appeared during commit and was preserved: {path}"
            )
        return install
    backup = _reserve_backup(path)
    install.backup = backup
    try:
        os.replace(path, backup)
    except BaseException:
        backup.unlink(missing_ok=True)
        install.backup = None
        raise
    if backup.read_bytes() != expected:
        _restore_conditional_install(install)
        raise IllustrationStudioConflict(
            f"Destination changed during commit and was preserved: {path}"
        )
    return install


def _install_exclusive(staged: Path, destination: Path) -> None:
    try:
        os.link(staged, destination, follow_symlinks=False)
    except FileExistsError as exc:
        raise IllustrationStudioConflict(
            f"Destination appeared during commit and was preserved: {destination}"
        ) from exc


def _restore_conditional_install(install: _ConditionalInstall) -> None:
    path = install.path
    if install.installed_identity is not None and path.exists():
        stat = path.stat()
        if (
            (stat.st_dev, stat.st_ino) == install.installed_identity
            and path.read_bytes() == install.intended
        ):
            path.unlink()
    if install.backup is not None:
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


def _restore_files(originals: Mapping[Path, bytes | None]) -> None:
    for target, content in reversed(tuple(originals.items())):
        if content is None:
            target.unlink(missing_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, raw = mkstemp(prefix=f".{target.name}.restore.", dir=target.parent)
        temporary = Path(raw)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
