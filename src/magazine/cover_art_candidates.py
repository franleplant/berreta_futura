from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
import warnings

import yaml
from PIL import Image, UnidentifiedImageError

from magazine.errors import ValidationError


COVER_ART_VARIANTS = ("synthetic", "art_directed", "wildcard")
SUPPORTED_SCHEMA_VERSIONS = (1, 2)
MIN_CANDIDATE_PIXELS = 1000
MAX_CANDIDATE_PIXELS = 10000


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

    path = record_path or edition_dir / "art" / "cover-candidates.yaml"
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

    if selected_art_path is not None and selected_art_path not in declared_paths:
        raise ValidationError(
            f"Selected cover art {selected_art_path} is not one of the three recorded candidates"
        )
    return {
        "record_path": path,
        "variants": resolved,
        "selected_art_path": selected_art_path,
    }
