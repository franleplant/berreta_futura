from __future__ import annotations

from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
from tempfile import gettempdir, mkstemp
from typing import Any, Protocol
import warnings

from PIL import Image, ImageDraw, UnidentifiedImageError
import yaml
from yaml.nodes import MappingNode, ScalarNode

from .cover_art_candidates import (
    COVER_ART_VARIANTS,
    DEFAULT_COVER_ART_DIRECTIONS,
    MAX_CANDIDATE_PIXELS,
    MIN_CANDIDATE_PIXELS,
    cover_art_candidate_prompt,
    validate_cover_art_candidates,
)
from .errors import ValidationError


_ROUND_RECORD_PATTERN = re.compile(r"^cover-candidates-round-([1-9][0-9]*)\.yaml$")
_CANONICAL_RECORD = Path("art/cover-candidates.yaml")
_EDITION_MANIFEST = Path("edition.yaml")
_LOCK_DIRECTORY = Path(gettempdir()) / "magazine-cover-studio-locks"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_COMPARISON_CELL = 400
_COMPARISON_LABEL_HEIGHT = 34


class CoverStudioConflict(ValidationError):
    """Raised when an operation was planned against stale studio state."""


@dataclass(frozen=True)
class CoverVariantStatus:
    name: str
    art_path: str | None
    asset_sha256: str | None
    registered: bool
    valid: bool
    error: str | None = None


@dataclass(frozen=True)
class CoverRoundStatus:
    number: int
    record_path: Path
    selection_status: str
    selected_variant: str | None
    registered: bool
    valid: bool
    variants: tuple[CoverVariantStatus, ...]
    error: str | None = None


@dataclass(frozen=True)
class CanonicalCoverSelection:
    record_path: Path
    round_number: int | None
    variant: str | None
    art_path: str | None
    valid: bool
    error: str | None = None


@dataclass(frozen=True)
class CoverStudioStatus:
    revision: str
    rounds: tuple[CoverRoundStatus, ...]
    canonical: CanonicalCoverSelection | None

    @property
    def next_round(self) -> int:
        numbers = [item.number for item in self.rounds]
        if self.canonical and self.canonical.round_number is not None:
            numbers.append(self.canonical.round_number)
        return max(numbers, default=0) + 1


@dataclass(frozen=True)
class CoverStudioAction:
    operation: str
    round_number: int | None
    variant: str | None
    writes: tuple[Path, ...]
    changed: bool
    dry_run: bool
    revision_before: str
    revision_after: str


@dataclass(frozen=True)
class CoverProofRequest:
    edition_dir: Path
    round_number: int
    variant: str
    language: str
    art_path: Path
    destination: Path
    cover_override: Mapping[str, str]


class CoverProofAdapter(Protocol):
    """Render one request into a set of relative artifact names and bytes."""

    def render(self, request: CoverProofRequest) -> Mapping[str, bytes]:
        ...


class CoverStudio:
    """Own the append-only cover round workflow behind one interface.

    A studio instance is an optimistic session. It remembers the edition state
    seen at construction and refreshes that revision after its own writes. If
    another process changes a round, candidate image, canonical selection, or
    edition manifest, the next mutation refuses instead of overwriting it.
    """

    def __init__(
        self,
        edition_dir: Path,
        *,
        proof_adapter: CoverProofAdapter | None = None,
    ) -> None:
        self.edition_dir = edition_dir.resolve()
        self.proof_adapter = proof_adapter
        self._revision = self._state_revision()

    @property
    def revision(self) -> str:
        return self._revision

    def inspect(self) -> CoverStudioStatus:
        """Discover every immutable round and the canonical selection."""

        rounds = tuple(self._inspect_round(number, path) for number, path in self._round_paths())
        canonical = self._inspect_canonical()
        return CoverStudioStatus(
            revision=self._state_revision(),
            rounds=rounds,
            canonical=canonical,
        )

    status = inspect

    def scaffold_next_round(
        self,
        *,
        editorial_reading: str | None = None,
        directions: Mapping[str, str] | None = None,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ) -> CoverStudioAction:
        """Create the next immutable round record with three named branches."""

        with self._mutation(expected_revision, dry_run=dry_run):
            before = self._revision
            status = self.inspect()
            number = status.next_round
            record_path = self._round_record_path(number)
            reading = (editorial_reading or self._latest_editorial_reading()).strip()
            if not reading:
                raise ValidationError(
                    "A cover round requires editorial_reading when no earlier record provides it"
                )
            if reading.startswith("TODO: define the editorial reading for "):
                raise ValidationError(
                    "A cover round cannot use the collection editorial_reading placeholder"
                )
            branch_directions = dict(DEFAULT_COVER_ART_DIRECTIONS)
            if directions is not None:
                if set(directions) != set(COVER_ART_VARIANTS):
                    raise ValidationError(
                        f"Cover directions must be exactly {list(COVER_ART_VARIANTS)}"
                    )
                branch_directions = {
                    variant: str(directions[variant]).strip()
                    for variant in COVER_ART_VARIANTS
                }
            if any(not branch_directions[variant] for variant in COVER_ART_VARIANTS):
                raise ValidationError("Every cover direction must be non-empty")
            record = {
                "schema_version": 2,
                "round": number,
                "selection_status": "pending_editor_choice",
                "editorial_reading": reading,
                "variants": {
                    variant: {
                        "art_path": self._round_art_path(number, variant),
                        "asset_sha256": "PENDING",
                        "generation_method": "imagegen",
                        "direction": branch_directions[variant],
                    }
                    for variant in COVER_ART_VARIANTS
                },
            }
            content = _dump_yaml(record)
            if record_path.exists():
                raise CoverStudioConflict(
                    f"Cover round {number} appeared concurrently: {record_path}"
                )
            if not dry_run:
                self._require_revision(before)
                _create_file(record_path, content)
                self._refresh_revision()
            return CoverStudioAction(
                operation="scaffold",
                round_number=number,
                variant=None,
                writes=(record_path,),
                changed=True,
                dry_run=dry_run,
                revision_before=before,
                revision_after=self._revision,
            )

    def emit_prompt_package(
        self,
        round_number: int,
        *,
        destination: Path | None = None,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ) -> CoverStudioAction:
        """Write a deterministic three-prompt package for one round."""

        with self._mutation(expected_revision, dry_run=dry_run):
            before = self._revision
            path, record = self._load_round(round_number)
            package = (
                destination.resolve()
                if destination is not None
                else self.edition_dir
                / "art"
                / "cover-rounds"
                / f"round-{round_number}"
                / "prompts"
            )
            updates = self._prompt_package(path, record, package)
            changed_updates = tuple(
                (target, content)
                for target, content in updates
                if not target.is_file() or target.read_bytes() != content
            )
            if any(target.exists() for target, _ in changed_updates):
                changed = next(target for target, _ in changed_updates if target.exists())
                raise CoverStudioConflict(
                    f"Prompt evidence already exists with different bytes: {changed}"
                )
            if changed_updates and not dry_run:
                self._require_revision(before)
                _replace_files(
                    changed_updates,
                    expected={target: None for target, _ in changed_updates},
                )
                self._refresh_revision()
            return CoverStudioAction(
                operation="prompts",
                round_number=round_number,
                variant=None,
                writes=tuple(target for target, _ in updates),
                changed=bool(changed_updates),
                dry_run=dry_run,
                revision_before=before,
                revision_after=self._revision,
            )

    def register_round(
        self,
        round_number: int,
        images: Mapping[str, Path],
        *,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ) -> CoverStudioAction:
        """Validate and copy three PNGs, then pin their computed hashes."""

        with self._mutation(expected_revision, dry_run=dry_run):
            before = self._revision
            record_path, record = self._load_round(round_number)
            if set(images) != set(COVER_ART_VARIANTS):
                raise ValidationError(
                    f"Generated cover images must be exactly {list(COVER_ART_VARIANTS)}"
                )
            payloads = {
                variant: _read_candidate_png(Path(images[variant]), variant=variant)
                for variant in COVER_ART_VARIANTS
            }
            hashes = {
                variant: hashlib.sha256(payloads[variant]).hexdigest()
                for variant in COVER_ART_VARIANTS
            }
            if len(set(hashes.values())) != len(COVER_ART_VARIANTS):
                raise ValidationError("Generated cover images must contain distinct bytes")

            variants = _require_variants(record)
            destinations: dict[str, Path] = {}
            record_bytes = record_path.read_bytes()
            finalized = deepcopy(record)
            finalized_variants = _require_variants(finalized)
            for variant in COVER_ART_VARIANTS:
                declared = variants[variant].get("art_path")
                destination_path = _safe_edition_path(
                    self.edition_dir,
                    declared,
                    label=f"Cover-art variant {variant}",
                )
                if destination_path.suffix.lower() != ".png":
                    raise ValidationError(
                        f"Cover-art variant {variant} must be registered as a PNG"
                    )
                destinations[variant] = destination_path
                finalized_variants[variant]["asset_sha256"] = hashes[variant]

            current_hashes = {
                variant: str(variants[variant].get("asset_sha256") or "")
                for variant in COVER_ART_VARIANTS
            }
            already_registered = all(
                _SHA256_PATTERN.fullmatch(current_hashes[variant])
                for variant in COVER_ART_VARIANTS
            )
            if already_registered:
                exact = all(
                    current_hashes[variant] == hashes[variant]
                    and destinations[variant].is_file()
                    and destinations[variant].read_bytes() == payloads[variant]
                    for variant in COVER_ART_VARIANTS
                )
                if not exact:
                    raise CoverStudioConflict(
                        f"Cover round {round_number} is already registered with different assets"
                    )
                self.validate_round(round_number)
                return CoverStudioAction(
                    operation="register",
                    round_number=round_number,
                    variant=None,
                    writes=tuple(destinations.values()) + (record_path,),
                    changed=False,
                    dry_run=dry_run,
                    revision_before=before,
                    revision_after=self._revision,
                )
            if any(value != "PENDING" for value in current_hashes.values()):
                raise ValidationError(
                    f"Cover round {round_number} mixes pending and pinned hashes"
                )

            for variant, destination_path in destinations.items():
                if (
                    destination_path.exists()
                    and destination_path.read_bytes() != payloads[variant]
                ):
                    raise CoverStudioConflict(
                        f"Registration refuses to overwrite existing cover art: {destination_path}"
                    )

            updates = tuple(
                (destinations[variant], payloads[variant])
                for variant in COVER_ART_VARIANTS
                if not destinations[variant].is_file()
            ) + ((record_path, _dump_yaml(finalized)),)
            if not dry_run:
                self._require_revision(before)
                expected_files = {
                    target: None
                    for target, _ in updates
                    if target != record_path
                }
                expected_files[record_path] = record_bytes
                _replace_files(updates, expected=expected_files)
                try:
                    self.validate_round(round_number)
                except BaseException:
                    created = {
                        target
                        for target, _ in updates
                        if target != record_path
                    }
                    _restore_files(
                        ((record_path, record_bytes),),
                        absent=created,
                    )
                    raise
                self._refresh_revision()
            return CoverStudioAction(
                operation="register",
                round_number=round_number,
                variant=None,
                writes=tuple(destinations.values()) + (record_path,),
                changed=True,
                dry_run=dry_run,
                revision_before=before,
                revision_after=self._revision,
            )

    def validate_round(self, round_number: int) -> dict[str, Any]:
        """Validate one finalized immutable record through the canonical validator."""

        path, record = self._load_round(round_number)
        selected_path = _selected_art_path(record)
        return validate_cover_art_candidates(
            self.edition_dir,
            record_path=path,
            selected_art_path=selected_path,
        )

    def proof_plan(
        self,
        languages: Iterable[str],
        *,
        rounds: Iterable[int] | None = None,
    ) -> tuple[CoverProofRequest, ...]:
        """Plan every round, variant, and language proof in stable order."""

        requested_languages = tuple(dict.fromkeys(str(item).strip() for item in languages))
        if not requested_languages or any(not language for language in requested_languages):
            raise ValidationError("Cover proof planning requires at least one language")
        available = {number: path for number, path in self._round_paths()}
        requested_rounds = (
            tuple(sorted(available))
            if rounds is None
            else tuple(dict.fromkeys(int(item) for item in rounds))
        )
        if not requested_rounds:
            raise ValidationError("Cover proof planning requires at least one cover round")
        missing = sorted(set(requested_rounds) - set(available))
        if missing:
            raise ValidationError(f"Cover rounds do not exist: {missing}")

        requests: list[CoverProofRequest] = []
        for number in requested_rounds:
            validated = self.validate_round(number)
            record = _load_mapping(available[number])
            variants = _require_variants(record)
            for language in requested_languages:
                for variant in COVER_ART_VARIANTS:
                    destination = (
                        self.edition_dir
                        / "art"
                        / "cover-rounds"
                        / f"round-{number}"
                        / "proofs"
                        / language
                        / variant
                    )
                    art_path = validated["variants"][variant]
                    requests.append(
                        CoverProofRequest(
                            edition_dir=self.edition_dir,
                            round_number=number,
                            variant=variant,
                            language=language,
                            art_path=art_path,
                            destination=destination,
                            cover_override={
                                "art_path": str(variants[variant]["art_path"])
                            },
                        )
                    )
        return tuple(requests)

    def render_proofs(
        self,
        languages: Iterable[str],
        *,
        rounds: Iterable[int] | None = None,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ) -> CoverStudioAction:
        """Render planned proofs through the injected adapter and own the outputs."""

        with self._mutation(expected_revision, dry_run=dry_run):
            before = self._revision
            requests = self.proof_plan(languages, rounds=rounds)
            planned_writes = tuple(request.destination for request in requests)
            for request in requests:
                _require_contained_path(
                    self.edition_dir,
                    request.destination,
                    label="Cover proof destination",
                )
            if dry_run:
                return CoverStudioAction(
                    operation="proofs",
                    round_number=None,
                    variant=None,
                    writes=planned_writes,
                    changed=True,
                    dry_run=True,
                    revision_before=before,
                    revision_after=self._revision,
                )
            if self.proof_adapter is None:
                raise ValidationError(
                    "Cover proof rendering requires an injected CoverProofAdapter"
                )
            updates: list[tuple[Path, bytes]] = []
            for request in requests:
                rendered = self.proof_adapter.render(request)
                if not rendered:
                    raise ValidationError(
                        f"Cover proof adapter returned no artifacts for "
                        f"round {request.round_number} {request.language} {request.variant}"
                    )
                for name, content in sorted(rendered.items()):
                    target = _safe_relative_output(
                        self.edition_dir,
                        request.destination,
                        name,
                    )
                    if not isinstance(content, bytes):
                        raise ValidationError(
                            f"Cover proof artifact {name!r} must contain bytes"
                        )
                    updates.append((target, content))
            if self._state_revision() != before:
                raise CoverStudioConflict(
                    "Cover studio state changed while proofs were rendering"
                )
            changed_updates = tuple(
                (target, content)
                for target, content in updates
                if not target.is_file() or target.read_bytes() != content
            )
            if changed_updates:
                _replace_files(changed_updates, root=self.edition_dir)
            self._refresh_revision()
            return CoverStudioAction(
                operation="proofs",
                round_number=None,
                variant=None,
                writes=tuple(target for target, _ in updates),
                changed=bool(changed_updates),
                dry_run=False,
                revision_before=before,
                revision_after=self._revision,
            )

    def create_comparison_sheet(
        self,
        *,
        destination: Path | None = None,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ) -> CoverStudioAction:
        """Create one ordered contact sheet across all rounds and branches."""

        with self._mutation(expected_revision, dry_run=dry_run):
            before = self._revision
            statuses = self.inspect().rounds
            if not statuses:
                raise ValidationError("A comparison sheet requires at least one cover round")
            for status in statuses:
                if not status.valid:
                    raise ValidationError(
                        f"Cover round {status.number} is not ready for comparison: "
                        f"{status.error or 'incomplete candidates'}"
                    )
            target = (
                destination.resolve()
                if destination is not None
                else self.edition_dir / "art" / "cover-rounds" / "comparison.png"
            )
            content = self._comparison_png(statuses)
            changed = not target.is_file() or target.read_bytes() != content
            if changed and not dry_run:
                self._require_revision(before)
                _replace_files(((target, content),))
                self._refresh_revision()
            return CoverStudioAction(
                operation="comparison",
                round_number=None,
                variant=None,
                writes=(target,),
                changed=changed,
                dry_run=dry_run,
                revision_before=before,
                revision_after=self._revision,
            )

    def select(
        self,
        round_number: int,
        variant: str,
        *,
        dry_run: bool = False,
        expected_revision: str | None = None,
    ) -> CoverStudioAction:
        """Select any historical candidate without changing its round record."""

        with self._mutation(expected_revision, dry_run=dry_run):
            before = self._revision
            if variant not in COVER_ART_VARIANTS:
                raise ValidationError(
                    f"Cover variant must be one of {list(COVER_ART_VARIANTS)}"
                )
            record_path, round_record = self._load_round(round_number)
            self.validate_round(round_number)
            manifest_path = self.edition_dir / _EDITION_MANIFEST
            manifest_bytes = manifest_path.read_bytes()
            manifest = _load_mapping(manifest_path)
            cover = manifest.get("cover")
            if not isinstance(cover, dict):
                raise ValidationError(f"Edition manifest requires a cover mapping: {manifest_path}")
            variants = _require_variants(round_record)
            art_path = str(variants[variant]["art_path"])
            canonical_record = deepcopy(round_record)
            canonical_record["selection_status"] = "selected"
            canonical_record["selected_variant"] = variant
            selected_manifest_bytes = _splice_manifest_cover_art_path(
                manifest_bytes,
                art_path,
                path=manifest_path,
            )
            canonical_path = self.edition_dir / _CANONICAL_RECORD
            canonical_bytes = (
                canonical_path.read_bytes()
                if canonical_path.is_file()
                else None
            )

            current = self._inspect_canonical()
            if (
                current is not None
                and current.valid
                and current.round_number == round_number
                and current.variant == variant
                and cover.get("art_path") == art_path
            ):
                return CoverStudioAction(
                    operation="select",
                    round_number=round_number,
                    variant=variant,
                    writes=(canonical_path, manifest_path),
                    changed=False,
                    dry_run=dry_run,
                    revision_before=before,
                    revision_after=self._revision,
                )

            validate_cover_art_candidates(
                self.edition_dir,
                record_path=record_path,
                selected_art_path=art_path,
            )
            updates = (
                (canonical_path, _dump_yaml(canonical_record)),
                (manifest_path, selected_manifest_bytes),
            )
            if not dry_run:
                self._require_revision(before)
                _replace_files(
                    updates,
                    expected={
                        canonical_path: canonical_bytes,
                        manifest_path: manifest_bytes,
                    },
                )
                try:
                    validate_cover_art_candidates(
                        self.edition_dir,
                        record_path=canonical_path,
                        selected_art_path=art_path,
                    )
                    selected = self._inspect_canonical()
                    if (
                        selected is None
                        or not selected.valid
                        or selected.round_number != round_number
                        or selected.variant != variant
                        or selected.art_path != art_path
                    ):
                        detail = selected.error if selected is not None else "selection is missing"
                        raise ValidationError(
                            f"Cover selection failed post-write validation: {detail}"
                        )
                except BaseException:
                    originals = tuple(
                        (target, content)
                        for target, content in (
                            (canonical_path, canonical_bytes),
                            (manifest_path, manifest_bytes),
                        )
                        if content is not None
                    )
                    absent = {
                        target
                        for target, content in (
                            (canonical_path, canonical_bytes),
                            (manifest_path, manifest_bytes),
                        )
                        if content is None
                    }
                    _restore_files(originals, absent=absent)
                    raise
                self._refresh_revision()
            return CoverStudioAction(
                operation="select",
                round_number=round_number,
                variant=variant,
                writes=(canonical_path, manifest_path),
                changed=True,
                dry_run=dry_run,
                revision_before=before,
                revision_after=self._revision,
            )

    def _inspect_round(self, number: int, path: Path) -> CoverRoundStatus:
        try:
            record = _load_mapping(path)
            declared_round = record.get("round")
            if declared_round is not None and declared_round != number:
                raise ValidationError(
                    f"Cover round filename says {number}, record says {declared_round!r}"
                )
            variants = _require_variants(record)
            variant_statuses = tuple(
                self._inspect_variant(variant, variants[variant])
                for variant in COVER_ART_VARIANTS
            )
            registered = all(item.registered for item in variant_statuses)
            error = None
            valid = False
            if registered:
                try:
                    self.validate_round(number)
                    valid = True
                except ValidationError as exc:
                    error = str(exc)
            return CoverRoundStatus(
                number=number,
                record_path=path,
                selection_status=str(record.get("selection_status") or ""),
                selected_variant=_selected_variant(record),
                registered=registered,
                valid=valid,
                variants=variant_statuses,
                error=error,
            )
        except ValidationError as exc:
            return CoverRoundStatus(
                number=number,
                record_path=path,
                selection_status="invalid",
                selected_variant=None,
                registered=False,
                valid=False,
                variants=(),
                error=str(exc),
            )

    def _inspect_variant(
        self,
        variant: str,
        row: Mapping[str, Any],
    ) -> CoverVariantStatus:
        declared = row.get("art_path")
        digest = str(row.get("asset_sha256") or "")
        registered = bool(_SHA256_PATTERN.fullmatch(digest))
        try:
            path = _safe_edition_path(
                self.edition_dir,
                declared,
                label=f"Cover-art variant {variant}",
            )
            if not registered:
                return CoverVariantStatus(
                    name=variant,
                    art_path=str(declared) if declared is not None else None,
                    asset_sha256=digest or None,
                    registered=False,
                    valid=False,
                    error="asset hash is pending",
                )
            if not path.is_file():
                raise ValidationError(f"Candidate is missing: {path}")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != digest:
                raise ValidationError(
                    f"Candidate hash mismatch: expected {digest}, found {actual}"
                )
            _read_candidate_png(path, variant=variant)
            return CoverVariantStatus(
                name=variant,
                art_path=str(declared),
                asset_sha256=digest,
                registered=True,
                valid=True,
            )
        except ValidationError as exc:
            return CoverVariantStatus(
                name=variant,
                art_path=str(declared) if declared is not None else None,
                asset_sha256=digest or None,
                registered=registered,
                valid=False,
                error=str(exc),
            )

    def _inspect_canonical(self) -> CanonicalCoverSelection | None:
        path = self.edition_dir / _CANONICAL_RECORD
        if not path.is_file():
            return None
        try:
            record = _load_mapping(path)
            manifest_path = self.edition_dir / _EDITION_MANIFEST
            manifest = _load_mapping(manifest_path)
            cover = manifest.get("cover")
            if not isinstance(cover, dict):
                raise ValidationError("Edition manifest requires a cover mapping")
            art_path = cover.get("art_path")
            if not isinstance(art_path, str) or not art_path.strip():
                raise ValidationError("Edition cover requires art_path")
            schema_version = record.get("schema_version")
            declared_round = record.get("round")
            round_number = _round_number(record)
            if declared_round is not None and round_number is None:
                raise ValidationError(
                    f"Canonical cover declares an invalid round: {declared_round!r}"
                )
            if schema_version == 2 and round_number is None:
                raise ValidationError(
                    "Schema-version 2 canonical cover requires a positive round"
                )
            declared_variant = record.get("selected_variant")
            if declared_variant is None:
                variant = _selected_variant(record, selected_art_path=art_path)
            else:
                if declared_variant not in COVER_ART_VARIANTS:
                    raise ValidationError(
                        f"Canonical cover declares an invalid selected_variant: "
                        f"{declared_variant!r}"
                    )
                variant = str(declared_variant)
            if variant is None:
                raise ValidationError(
                    "Canonical cover does not identify the manifest-selected variant"
                )
            variants = _require_variants(record)
            variant_art_path = variants[variant].get("art_path")
            if variant_art_path != art_path:
                raise ValidationError(
                    f"Canonical selected_variant {variant} points to "
                    f"{variant_art_path!r}, but edition cover.art_path is {art_path!r}"
                )
            if round_number is not None:
                _, immutable_round = self._load_round(round_number)
                if _candidate_record_content(record) != _candidate_record_content(
                    immutable_round
                ):
                    raise ValidationError(
                        f"Canonical cover does not match immutable round {round_number}"
                    )
            validate_cover_art_candidates(
                self.edition_dir,
                record_path=path,
                selected_art_path=art_path,
            )
            return CanonicalCoverSelection(
                record_path=path,
                round_number=round_number,
                variant=variant,
                art_path=art_path,
                valid=True,
            )
        except ValidationError as exc:
            return CanonicalCoverSelection(
                record_path=path,
                round_number=None,
                variant=None,
                art_path=None,
                valid=False,
                error=str(exc),
            )

    def _load_round(self, round_number: int) -> tuple[Path, dict[str, Any]]:
        if round_number < 1:
            raise ValidationError("Cover round number must be positive")
        path = self._round_record_path(round_number)
        if not path.is_file():
            raise ValidationError(f"Cover round {round_number} does not exist: {path}")
        record = _load_mapping(path)
        declared = record.get("round")
        if declared is not None and declared != round_number:
            raise ValidationError(
                f"Cover round filename says {round_number}, record says {declared!r}"
            )
        _require_variants(record)
        return path, record

    def _round_paths(self) -> tuple[tuple[int, Path], ...]:
        art_dir = self.edition_dir / "art"
        if not art_dir.is_dir():
            return ()
        found: list[tuple[int, Path]] = []
        for path in art_dir.glob("cover-candidates-round-*.yaml"):
            match = _ROUND_RECORD_PATTERN.fullmatch(path.name)
            if match:
                found.append((int(match.group(1)), path))
        return tuple(sorted(found))

    def _round_record_path(self, number: int) -> Path:
        return self.edition_dir / "art" / f"cover-candidates-round-{number}.yaml"

    @staticmethod
    def _round_art_path(number: int, variant: str) -> str:
        slug = variant.replace("_", "-")
        return f"art/cover-rounds/round-{number}/cover-{slug}.png"

    def _latest_editorial_reading(self) -> str:
        records = list(self._round_paths())
        canonical = self.edition_dir / _CANONICAL_RECORD
        paths = [path for _, path in reversed(records)]
        if canonical.is_file():
            paths.append(canonical)
        for path in paths:
            record = _load_mapping(path)
            reading = str(record.get("editorial_reading") or "").strip()
            if reading:
                return reading
        return ""

    def _prompt_package(
        self,
        record_path: Path,
        record: Mapping[str, Any],
        destination: Path,
    ) -> tuple[tuple[Path, bytes], ...]:
        reading = str(record.get("editorial_reading") or "").strip()
        if not reading:
            raise ValidationError("Cover-art candidate record requires editorial_reading")
        variants = _require_variants(record)
        updates: list[tuple[Path, bytes]] = []
        inventory: list[dict[str, str]] = []
        for variant in COVER_ART_VARIANTS:
            direction = str(variants[variant].get("direction") or "").strip()
            if not direction:
                raise ValidationError(f"Cover-art variant {variant} requires a direction")
            prompt = cover_art_candidate_prompt(
                reading,
                variant=variant,
                direction=direction,
            )
            name = f"cover-{variant}.txt"
            updates.append((destination / name, (prompt + "\n").encode("utf-8")))
            inventory.append(
                {
                    "variant": variant,
                    "prompt": name,
                    "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    "art_path": str(variants[variant].get("art_path") or ""),
                }
            )
        relative_record = record_path.relative_to(self.edition_dir).as_posix()
        inventory_bytes = (
            json.dumps(
                {
                    "schema_version": 1,
                    "record_path": relative_record,
                    "round": _round_number(record),
                    "editorial_reading": reading,
                    "variants": inventory,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        updates.append((destination / "cover-candidates.json", inventory_bytes))
        return tuple(updates)

    def _comparison_png(self, rounds: tuple[CoverRoundStatus, ...]) -> bytes:
        width = len(COVER_ART_VARIANTS) * _COMPARISON_CELL
        row_height = _COMPARISON_CELL + _COMPARISON_LABEL_HEIGHT
        sheet = Image.new("RGB", (width, len(rounds) * row_height), "white")
        draw = ImageDraw.Draw(sheet)
        for row_index, round_status in enumerate(rounds):
            for column, variant_status in enumerate(round_status.variants):
                assert variant_status.art_path is not None
                art_path = _safe_edition_path(
                    self.edition_dir,
                    variant_status.art_path,
                    label=f"Cover-art variant {variant_status.name}",
                )
                with Image.open(art_path) as opened:
                    image = opened.convert("RGB")
                    image.thumbnail((_COMPARISON_CELL, _COMPARISON_CELL))
                    x = column * _COMPARISON_CELL + (_COMPARISON_CELL - image.width) // 2
                    y = row_index * row_height
                    sheet.paste(image, (x, y))
                label = f"Round {round_status.number} | {variant_status.name}"
                draw.text(
                    (column * _COMPARISON_CELL + 10, y + _COMPARISON_CELL + 9),
                    label,
                    fill="black",
                )
        output = io.BytesIO()
        sheet.save(output, format="PNG", optimize=False)
        return output.getvalue()

    @contextmanager
    def _mutation(
        self,
        expected_revision: str | None,
        *,
        dry_run: bool,
    ):
        if dry_run:
            current = self._state_revision()
            expected = expected_revision or self._revision
            if current != expected or self._revision != expected:
                raise CoverStudioConflict(
                    "Cover studio state is stale; inspect again with a new CoverStudio "
                    f"instance (expected {expected}, found {current})"
                )
            yield
            return
        lock_name = hashlib.sha256(
            str(self.edition_dir).encode("utf-8")
        ).hexdigest()
        lock_path = _LOCK_DIRECTORY / f"{lock_name}.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise CoverStudioConflict(
                    f"Another cover studio operation is active: {lock_path}"
                ) from exc
            current = self._state_revision()
            expected = expected_revision or self._revision
            if current != expected or self._revision != expected:
                raise CoverStudioConflict(
                    "Cover studio state is stale; inspect again with a new CoverStudio "
                    f"instance (expected {expected}, found {current})"
                )
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _state_revision(self) -> str:
        digest = hashlib.sha256()
        paths = [self.edition_dir / _EDITION_MANIFEST]
        canonical = self.edition_dir / _CANONICAL_RECORD
        paths.append(canonical)
        paths.extend(path for _, path in self._round_paths())
        candidate_paths: set[Path] = set()
        for path in paths[1:]:
            if not path.is_file():
                continue
            try:
                record = _load_mapping(path)
                variants = record.get("variants")
                if isinstance(variants, dict):
                    for row in variants.values():
                        if not isinstance(row, dict):
                            continue
                        try:
                            candidate_paths.add(
                                _safe_edition_path(
                                    self.edition_dir,
                                    row.get("art_path"),
                                    label="Cover-art variant",
                                )
                            )
                        except ValidationError:
                            continue
            except ValidationError:
                continue
        paths.extend(sorted(candidate_paths))
        for path in sorted(set(paths)):
            try:
                label = path.relative_to(self.edition_dir).as_posix()
            except ValueError:
                continue
            digest.update(label.encode("utf-8"))
            digest.update(b"\0")
            if path.is_file():
                digest.update(path.read_bytes())
            else:
                digest.update(b"<missing>")
            digest.update(b"\0")
        return digest.hexdigest()

    def _refresh_revision(self) -> None:
        self._revision = self._state_revision()

    def _require_revision(self, expected: str) -> None:
        current = self._state_revision()
        if current != expected:
            raise CoverStudioConflict(
                "Cover studio state changed during the operation "
                f"(expected {expected}, found {current})"
            )


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValidationError(f"Cannot read structured cover studio file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationError(f"Structured cover studio file must be a mapping: {path}")
    return data


def _dump_yaml(data: Mapping[str, Any]) -> bytes:
    return yaml.safe_dump(
        dict(data),
        sort_keys=False,
        allow_unicode=True,
    ).encode("utf-8")


def _require_variants(record: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    variants = record.get("variants")
    if not isinstance(variants, dict) or set(variants) != set(COVER_ART_VARIANTS):
        raise ValidationError(
            f"Cover-art variants must be exactly {list(COVER_ART_VARIANTS)}"
        )
    if any(not isinstance(variants[variant], dict) for variant in COVER_ART_VARIANTS):
        raise ValidationError("Every cover-art variant must be a mapping")
    return variants


def _safe_edition_path(edition_dir: Path, value: object, *, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} requires a non-empty path")
    root = edition_dir.resolve()
    path = (edition_dir / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValidationError(f"{label} escapes the edition directory: {value}") from exc
    return path


def _require_contained_path(root: Path, path: Path, *, label: str) -> Path:
    resolved_root = root.resolve()
    lexical_path = Path(os.path.abspath(path))
    resolved_path = path.resolve()
    try:
        lexical_path.relative_to(resolved_root)
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValidationError(
            f"{label} escapes the edition directory: {path}"
        ) from exc
    if resolved_path != lexical_path:
        raise ValidationError(
            f"{label} uses a symlink or redirected path component: {path}"
        )
    return lexical_path


def _safe_relative_output(
    edition_dir: Path,
    destination: Path,
    value: object,
) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Cover proof artifact name must be a non-empty relative path")
    relative = Path(value)
    if relative.is_absolute():
        raise ValidationError(f"Cover proof artifact name must be relative: {value}")
    resolved_destination = _require_contained_path(
        edition_dir,
        destination,
        label="Cover proof destination",
    )
    target = Path(os.path.abspath(resolved_destination / relative))
    try:
        target.relative_to(resolved_destination)
        target.resolve().relative_to(resolved_destination)
    except ValueError as exc:
        raise ValidationError(f"Cover proof artifact escapes its destination: {value}") from exc
    _require_contained_path(
        edition_dir,
        target,
        label="Cover proof artifact",
    )
    return target


def _candidate_record_content(record: Mapping[str, Any]) -> dict[str, Any]:
    content = deepcopy(dict(record))
    content.pop("selection_status", None)
    content.pop("selected_variant", None)
    return content


def _mapping_value(node: MappingNode, key: str) -> object:
    matches = [
        value_node
        for key_node, value_node in node.value
        if isinstance(key_node, ScalarNode) and key_node.value == key
    ]
    if len(matches) != 1:
        raise ValidationError(f"Edition manifest requires exactly one {key} field")
    return matches[0]


def _yaml_scalar_with_style(value: str, style: str | None) -> str:
    if style == "'":
        return "'" + value.replace("'", "''") + "'"
    if style == '"':
        return json.dumps(value, ensure_ascii=False)
    if style in {"|", ">"}:
        raise ValidationError(
            "Edition cover.art_path must use a plain or quoted YAML scalar"
        )
    try:
        parsed = yaml.safe_load(value)
    except yaml.YAMLError:
        parsed = None
    if parsed != value:
        return "'" + value.replace("'", "''") + "'"
    return value


def _splice_manifest_cover_art_path(
    content: bytes,
    art_path: str,
    *,
    path: Path,
) -> bytes:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"Edition manifest must be UTF-8: {path}") from exc
    try:
        document = yaml.compose(text)
    except yaml.YAMLError as exc:
        raise ValidationError(f"Cannot parse edition manifest {path}: {exc}") from exc
    if not isinstance(document, MappingNode):
        raise ValidationError(f"Edition manifest must be a mapping: {path}")
    cover_node = _mapping_value(document, "cover")
    if not isinstance(cover_node, MappingNode):
        raise ValidationError(f"Edition manifest requires a cover mapping: {path}")
    art_path_node = _mapping_value(cover_node, "art_path")
    if not isinstance(art_path_node, ScalarNode):
        raise ValidationError(
            f"Edition cover.art_path must be a scalar: {path}"
        )
    replacement = _yaml_scalar_with_style(art_path, art_path_node.style)
    updated_text = (
        text[: art_path_node.start_mark.index]
        + replacement
        + text[art_path_node.end_mark.index :]
    )
    try:
        updated = yaml.safe_load(updated_text)
    except yaml.YAMLError as exc:
        raise ValidationError(
            f"Cover selection produced an invalid edition manifest {path}: {exc}"
        ) from exc
    if not isinstance(updated, dict):
        raise ValidationError(f"Edition manifest must remain a mapping: {path}")
    cover = updated.get("cover")
    if not isinstance(cover, dict) or cover.get("art_path") != art_path:
        raise ValidationError(
            f"Cover selection did not update edition cover.art_path: {path}"
        )
    return updated_text.encode("utf-8")


def _read_candidate_png(path: Path, *, variant: str) -> bytes:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ValidationError(
            f"Cannot read generated cover image for {variant}: {path}: {exc}"
        ) from exc
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if image.format != "PNG":
                    raise ValidationError(
                        f"Generated cover image for {variant} must contain PNG data"
                    )
                width, height = image.size
                image.verify()
    except (
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValidationError(
            f"Generated cover image for {variant} is not a readable PNG"
        ) from exc
    if width != height:
        raise ValidationError(
            f"Generated cover image for {variant} must be square, found {width}x{height}"
        )
    if width < MIN_CANDIDATE_PIXELS:
        raise ValidationError(
            f"Generated cover image for {variant} must be at least "
            f"{MIN_CANDIDATE_PIXELS}px square, found {width}x{height}"
        )
    if width > MAX_CANDIDATE_PIXELS:
        raise ValidationError(
            f"Generated cover image for {variant} must be at most "
            f"{MAX_CANDIDATE_PIXELS}px square, found {width}x{height}"
        )
    return content


def _round_number(record: Mapping[str, Any]) -> int | None:
    value = record.get("round")
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
        else None
    )


def _selected_variant(
    record: Mapping[str, Any],
    *,
    selected_art_path: str | None = None,
) -> str | None:
    declared = record.get("selected_variant")
    if declared in COVER_ART_VARIANTS:
        return str(declared)
    if selected_art_path is not None:
        variants = _require_variants(record)
        matches = [
            variant
            for variant in COVER_ART_VARIANTS
            if variants[variant].get("art_path") == selected_art_path
        ]
        if len(matches) == 1:
            return matches[0]
    return None


def _selected_art_path(record: Mapping[str, Any]) -> str | None:
    if str(record.get("selection_status") or "") != "selected":
        return None
    variant = _selected_variant(record)
    if variant is None:
        return None
    return str(_require_variants(record)[variant].get("art_path") or "") or None


def _create_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _stage_bytes(path, content)
    try:
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise CoverStudioConflict(f"Refusing to overwrite existing cover work: {path}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def _replace_files(
    updates: tuple[tuple[Path, bytes], ...],
    *,
    expected: Mapping[Path, bytes | None] | None = None,
    root: Path | None = None,
) -> None:
    """Replace a small file set and restore every completed write on failure."""

    if len({path for path, _ in updates}) != len(updates):
        raise ValidationError("Cover studio transaction contains duplicate paths")
    if root is not None:
        for path, _ in updates:
            _require_contained_path(
                root,
                path,
                label="Cover studio transaction target",
            )
    originals = {
        path: path.read_bytes() if path.is_file() else None
        for path, _ in updates
    }
    if expected is not None:
        for path, anticipated in expected.items():
            current = path.read_bytes() if path.is_file() else None
            if current != anticipated:
                raise CoverStudioConflict(
                    f"Cover studio file changed concurrently: {path}"
                )
    staged: dict[Path, Path] = {}
    changed: list[Path] = []
    try:
        for path, content in updates:
            path.parent.mkdir(parents=True, exist_ok=True)
            if root is not None:
                _require_contained_path(
                    root,
                    path,
                    label="Cover studio transaction target",
                )
            staged[path] = _stage_bytes(path, content)
        for path, _ in updates:
            if root is not None:
                _require_contained_path(
                    root,
                    path,
                    label="Cover studio transaction target",
                )
            if expected is not None and path in expected:
                current = path.read_bytes() if path.is_file() else None
                if current != expected[path]:
                    raise CoverStudioConflict(
                        f"Cover studio file changed concurrently: {path}"
                    )
            os.replace(staged[path], path)
            changed.append(path)
    except (OSError, CoverStudioConflict, ValidationError) as exc:
        rollback_errors: list[str] = []
        for path in reversed(changed):
            try:
                original = originals[path]
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    _replace_with_bytes(path, original)
            except OSError as rollback_exc:
                rollback_errors.append(f"{path}: {rollback_exc}")
        detail = f"Cannot commit cover studio state: {exc}"
        if rollback_errors:
            detail += "; rollback failed: " + "; ".join(rollback_errors)
        if isinstance(exc, CoverStudioConflict) and not rollback_errors:
            raise CoverStudioConflict(detail) from exc
        raise ValidationError(detail) from exc
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def _restore_files(
    updates: tuple[tuple[Path, bytes], ...],
    *,
    absent: set[Path],
) -> None:
    errors: list[str] = []
    for path, content in updates:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            _replace_with_bytes(path, content)
        except OSError as exc:
            errors.append(f"{path}: {exc}")
    for path in absent:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            errors.append(f"{path}: {exc}")
    if errors:
        raise ValidationError(
            "Cannot roll back cover studio state: " + "; ".join(errors)
        )


def _replace_with_bytes(destination: Path, content: bytes) -> None:
    temporary = _stage_bytes(destination, content)
    try:
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


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
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)
