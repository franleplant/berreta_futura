from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
import warnings

import yaml
from PIL import Image, UnidentifiedImageError

from magazine.errors import ValidationError


COVER_ART_VARIANTS = ("synthetic", "art_directed", "wildcard")
COVER_ART_CANDIDATE_RECORD = Path("art/cover-candidates.yaml")
SUPPORTED_SCHEMA_VERSIONS = (1, 2)
MIN_CANDIDATE_PIXELS = 1000
MAX_CANDIDATE_PIXELS = 10000
SELECTION_STATES = {"pending_editor_choice", "selected"}

DEFAULT_COVER_ART_DIRECTIONS = {
    "synthetic": (
        "Synthetic/geometric. Build a precise, image-generated composition from "
        "clean systems geometry, controlled perspective, and a restrained palette."
    ),
    "art_directed": (
        "Art-directed/material. Interpret the editorial idea through a tactile "
        "physical medium such as collage, printmaking, painted paper, or constructed objects."
    ),
    "wildcard": (
        "Wildcard. Take a surprising visual approach that is clearly distinct from "
        "the synthetic and art-directed branches while preserving the editorial idea."
    ),
}


def cover_art_candidate_record_path(edition_dir: Path) -> Path:
    """Return the canonical, manifest-independent candidate record path."""

    return edition_dir / COVER_ART_CANDIDATE_RECORD


def scaffold_cover_art_candidates(edition_dir: Path) -> Path:
    """Create the standard three-branch cover brief without overwriting work.

    Collection does not yet know an edition's editorial reading, so the
    scaffold is deliberately incomplete. Authoring replaces the TODO reading
    and pending hashes after generating the three named assets. Validation
    then treats this canonical record exactly like a hand-authored record.
    """

    path = cover_art_candidate_record_path(edition_dir)
    if path.exists():
        return path
    data = {
        "schema_version": 2,
        "selection_status": "pending_editor_choice",
        "editorial_reading": (
            f"TODO: define the editorial reading for {edition_dir.name}"
        ),
        "variants": {
            variant: {
                "art_path": f"art/cover-candidate-{variant.replace('_', '-')}.png",
                "asset_sha256": "PENDING",
                "generation_method": "imagegen",
                "direction": DEFAULT_COVER_ART_DIRECTIONS[variant],
            }
            for variant in COVER_ART_VARIANTS
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def hydrate_cover_art_candidates(
    edition_dir: Path,
    *,
    editorial_reading: str,
) -> Path:
    """Replace only the untouched collection placeholder with edition context."""

    path = scaffold_cover_art_candidates(edition_dir)
    data = _load_mapping(path)
    current = str(data.get("editorial_reading") or "").strip()
    if current.startswith("TODO: define the editorial reading for "):
        reading = editorial_reading.strip()
        if not reading:
            raise ValidationError(
                f"Cannot hydrate cover-art candidates without an editorial reading: {path}"
            )
        data["editorial_reading"] = reading
        path.write_text(
            yaml.safe_dump(data, sort_keys=False),
            encoding="utf-8",
        )
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValidationError(f"Cannot read cover-art candidate record {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationError(f"Cover-art candidate record must be a mapping: {path}")
    return data


def _candidate_path(edition_dir: Path, value: object, *, variant: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"Cover-art variant {variant} requires a non-empty art_path")
    edition_root = edition_dir.resolve()
    path = (edition_dir / value).resolve()
    try:
        path.relative_to(edition_root)
    except ValueError as exc:
        raise ValidationError(
            f"Cover-art variant {variant} escapes the edition directory: {value}"
        ) from exc
    return path


def validate_cover_art_candidates(
    edition_dir: Path,
    *,
    record_path: Path | None = None,
    selected_art_path: str | None = None,
) -> dict[str, Any]:
    """Validate the three author-time cover candidates for one edition.

    Candidate generation stays outside the deterministic build. This record
    pins the resulting assets while ``edition.yaml`` continues to select the
    sole production image through ``cover.art_path``.
    """

    path = record_path or cover_art_candidate_record_path(edition_dir)
    data = _load_mapping(path)
    schema_version = data.get("schema_version")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValidationError(
            "Cover-art candidate schema_version must be one of "
            f"{list(SUPPORTED_SCHEMA_VERSIONS)}"
        )
    editorial_reading = data.get("editorial_reading")
    if not isinstance(editorial_reading, str) or not editorial_reading.strip():
        raise ValidationError("Cover-art candidate record requires an editorial_reading")
    if editorial_reading.strip().startswith(
        "TODO: define the editorial reading for "
    ):
        raise ValidationError(
            "Cover-art candidate editorial_reading is still the collection placeholder"
        )
    selection_status = str(data.get("selection_status") or "").strip()
    if schema_version >= 2 and selection_status not in SELECTION_STATES:
        raise ValidationError(
            "Cover-art candidate record requires selection_status to be "
            "pending_editor_choice or selected"
        )

    variants = data.get("variants")
    if not isinstance(variants, dict):
        raise ValidationError("Cover-art candidate record requires a variants mapping")
    actual = set(variants)
    expected = set(COVER_ART_VARIANTS)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValidationError(
            f"Cover-art variants must be exactly {list(COVER_ART_VARIANTS)}; "
            f"missing={missing}, extra={extra}"
        )

    resolved: dict[str, Path] = {}
    resolved_paths: set[Path] = set()
    asset_hashes: set[str] = set()
    declared_paths: set[str] = set()
    for variant in COVER_ART_VARIANTS:
        row = variants[variant]
        if not isinstance(row, dict):
            raise ValidationError(f"Cover-art variant {variant} must be a mapping")
        direction = row.get("direction")
        if not isinstance(direction, str) or not direction.strip():
            raise ValidationError(f"Cover-art variant {variant} requires a direction")
        if schema_version >= 2:
            generation_method = row.get("generation_method")
            if not isinstance(generation_method, str) or not generation_method.strip():
                raise ValidationError(
                    f"Cover-art variant {variant} requires a generation_method"
                )
            if variant == "synthetic" and generation_method != "imagegen":
                raise ValidationError(
                    "Cover-art variant synthetic must use generation_method imagegen"
                )

        declared = row.get("art_path")
        candidate = _candidate_path(edition_dir, declared, variant=variant)
        if candidate in resolved_paths:
            raise ValidationError(
                f"Cover-art variants must resolve to unique files: {declared}"
            )
        resolved_paths.add(candidate)
        declared_paths.add(str(declared))
        if candidate.suffix.lower() != ".png":
            raise ValidationError(f"Cover-art variant {variant} must be a PNG: {declared}")
        if not candidate.is_file():
            raise ValidationError(f"Cover-art variant {variant} is missing: {declared}")

        expected_sha = row.get("asset_sha256")
        if expected_sha == "PENDING":
            raise ValidationError(
                f"Cover-art variant {variant} still has a pending asset hash"
            )
        actual_sha = _sha256(candidate)
        if expected_sha != actual_sha:
            raise ValidationError(
                f"Cover-art variant {variant} hash mismatch: expected {expected_sha}, "
                f"found {actual_sha}"
            )
        if actual_sha in asset_hashes:
            raise ValidationError(
                f"Cover-art variants must contain distinct image bytes: {variant}"
            )
        asset_hashes.add(actual_sha)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(candidate) as image:
                    if image.format != "PNG":
                        raise ValidationError(
                            f"Cover-art variant {variant} must contain PNG image data"
                        )
                    width, height = image.size
                    image.verify()
        except (
            OSError,
            UnidentifiedImageError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as exc:
            raise ValidationError(f"Cover-art variant {variant} is not a readable PNG") from exc
        if width != height:
            raise ValidationError(
                f"Cover-art variant {variant} must be square, found {width}x{height}"
            )
        if width < MIN_CANDIDATE_PIXELS:
            raise ValidationError(
                f"Cover-art variant {variant} must be at least "
                f"{MIN_CANDIDATE_PIXELS}px square, found {width}x{height}"
            )
        if width > MAX_CANDIDATE_PIXELS:
            raise ValidationError(
                f"Cover-art variant {variant} must be at most "
                f"{MAX_CANDIDATE_PIXELS}px square, found {width}x{height}"
            )
        resolved[variant] = candidate

    if (
        (schema_version == 1 or selection_status == "selected")
        and selected_art_path is not None
        and selected_art_path not in declared_paths
    ):
        raise ValidationError(
            f"Selected cover art {selected_art_path} is not one of the three recorded candidates"
        )
    if selection_status == "selected" and selected_art_path is None:
        raise ValidationError(
            "Cover-art candidate record marked selected requires selected_art_path"
        )
    return {
        "record_path": path,
        "variants": resolved,
        "selection_status": selection_status,
        "selected_art_path": selected_art_path,
    }


def cover_art_candidate_prompt(
    editorial_reading: str,
    *,
    variant: str,
    direction: str,
) -> str:
    """Compile one typography-free square cover prompt from the candidate record."""

    return (
        "Use case: magazine cover art candidate\n"
        f"Variant: {variant}\n"
        "Output: exactly one square RGB PNG, at least 1000x1000 pixels\n"
        f"Editorial reading: {editorial_reading.strip()}\n"
        f"Art direction: {direction.strip()}\n"
        "The image must materially differ in medium and visual language from the "
        "other two variants while expressing the same editorial reading.\n"
        "Reserve calm negative space near the upper and lower edges for layout-owned "
        "typography.\n"
        "Do not add words, letters, numbers, logos, mastheads, cover lines, QR codes, "
        "watermarks, or decorative borders."
    )


def write_cover_art_prompt_package(
    edition_dir: Path,
    destination: Path,
    *,
    record_path: Path | None = None,
) -> Path:
    """Write the exact three cover prompts before or after image generation."""

    path = record_path or cover_art_candidate_record_path(edition_dir)
    data = _load_mapping(path)
    editorial_reading = str(data.get("editorial_reading") or "").strip()
    if not editorial_reading:
        raise ValidationError("Cover-art candidate record requires an editorial_reading")
    variants = data.get("variants")
    if not isinstance(variants, dict) or set(variants) != set(COVER_ART_VARIANTS):
        raise ValidationError(
            f"Cover-art variants must be exactly {list(COVER_ART_VARIANTS)}"
        )
    destination.mkdir(parents=True, exist_ok=True)
    inventory: list[dict[str, str]] = []
    for variant in COVER_ART_VARIANTS:
        row = variants[variant]
        if not isinstance(row, dict):
            raise ValidationError(f"Cover-art variant {variant} must be a mapping")
        direction = str(row.get("direction") or "").strip()
        if not direction:
            raise ValidationError(f"Cover-art variant {variant} requires a direction")
        prompt = cover_art_candidate_prompt(
            editorial_reading,
            variant=variant,
            direction=direction,
        )
        prompt_path = destination / f"cover-{variant}.txt"
        prompt_path.write_text(prompt + "\n", encoding="utf-8")
        inventory.append(
            {
                "variant": variant,
                "prompt": prompt_path.name,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "art_path": str(row.get("art_path") or ""),
            }
        )
    (destination / "cover-candidates.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "record_path": path.relative_to(edition_dir).as_posix(),
                "editorial_reading": editorial_reading,
                "variants": inventory,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination
