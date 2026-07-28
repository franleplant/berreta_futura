from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml
from PIL import Image

from magazine.cover_art_candidates import (
    COVER_ART_VARIANTS,
    validate_cover_art_candidates,
)
from magazine.errors import ValidationError


def _write_candidate_record(tmp_path: Path) -> tuple[Path, dict]:
    art = tmp_path / "art"
    art.mkdir()
    variants = {}
    for index, variant in enumerate(COVER_ART_VARIANTS):
        image_path = art / f"{variant}.png"
        Image.new("RGB", (1000, 1000), (index * 40, 20, 40)).save(image_path)
        variants[variant] = {
            "art_path": f"art/{variant}.png",
            "asset_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "direction": f"{variant} direction",
        }
    record = {
        "schema_version": 1,
        "editorial_reading": "The edition is about constrained agency.",
        "variants": variants,
    }
    path = art / "cover-candidates.yaml"
    path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
    return path, record


def test_validates_exact_three_candidates_and_selected_path(tmp_path: Path) -> None:
    _write_candidate_record(tmp_path)
    result = validate_cover_art_candidates(
        tmp_path,
        selected_art_path="art/art_directed.png",
    )
    assert tuple(result["variants"]) == COVER_ART_VARIANTS


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_requires_exact_variant_set(tmp_path: Path, mutation: str) -> None:
    path, record = _write_candidate_record(tmp_path)
    if mutation == "missing":
        record["variants"].pop("wildcard")
    else:
        record["variants"]["other"] = record["variants"]["synthetic"]
    path.write_text(yaml.safe_dump(record), encoding="utf-8")
    with pytest.raises(ValidationError, match="must be exactly"):
        validate_cover_art_candidates(tmp_path)


def test_rejects_hash_mismatch(tmp_path: Path) -> None:
    path, record = _write_candidate_record(tmp_path)
    record["variants"]["wildcard"]["asset_sha256"] = "0" * 64
    path.write_text(yaml.safe_dump(record), encoding="utf-8")
    with pytest.raises(ValidationError, match="hash mismatch"):
        validate_cover_art_candidates(tmp_path)


def test_requires_editorial_reading(tmp_path: Path) -> None:
    path, record = _write_candidate_record(tmp_path)
    record.pop("editorial_reading")
    path.write_text(yaml.safe_dump(record), encoding="utf-8")
    with pytest.raises(ValidationError, match="editorial_reading"):
        validate_cover_art_candidates(tmp_path)


def test_schema_two_requires_image_generated_synthetic_branch(tmp_path: Path) -> None:
    path, record = _write_candidate_record(tmp_path)
    record["schema_version"] = 2
    for row in record["variants"].values():
        row["generation_method"] = "imagegen"
    record["variants"]["synthetic"]["generation_method"] = "deterministic"
    path.write_text(yaml.safe_dump(record), encoding="utf-8")

    with pytest.raises(
        ValidationError,
        match="synthetic must use generation_method imagegen",
    ):
        validate_cover_art_candidates(tmp_path)


def test_schema_two_accepts_declared_generation_methods(tmp_path: Path) -> None:
    path, record = _write_candidate_record(tmp_path)
    record["schema_version"] = 2
    for row in record["variants"].values():
        row["generation_method"] = "imagegen"
    path.write_text(yaml.safe_dump(record), encoding="utf-8")

    validate_cover_art_candidates(tmp_path)


def test_rejects_non_square_candidate(tmp_path: Path) -> None:
    path, record = _write_candidate_record(tmp_path)
    candidate = tmp_path / "art" / "wildcard.png"
    Image.new("RGB", (900, 1000), "white").save(candidate)
    record["variants"]["wildcard"]["asset_sha256"] = hashlib.sha256(
        candidate.read_bytes()
    ).hexdigest()
    path.write_text(yaml.safe_dump(record), encoding="utf-8")
    with pytest.raises(ValidationError, match="must be square"):
        validate_cover_art_candidates(tmp_path)


def test_rejects_undersized_candidate(tmp_path: Path) -> None:
    path, record = _write_candidate_record(tmp_path)
    candidate = tmp_path / "art" / "wildcard.png"
    Image.new("RGB", (900, 900), "white").save(candidate)
    record["variants"]["wildcard"]["asset_sha256"] = hashlib.sha256(
        candidate.read_bytes()
    ).hexdigest()
    path.write_text(yaml.safe_dump(record), encoding="utf-8")
    with pytest.raises(ValidationError, match="at least 1000px"):
        validate_cover_art_candidates(tmp_path)


def test_rejects_jpeg_renamed_as_png(tmp_path: Path) -> None:
    path, record = _write_candidate_record(tmp_path)
    candidate = tmp_path / "art" / "wildcard.png"
    Image.new("RGB", (1000, 1000), "white").save(candidate, format="JPEG")
    record["variants"]["wildcard"]["asset_sha256"] = hashlib.sha256(
        candidate.read_bytes()
    ).hexdigest()
    path.write_text(yaml.safe_dump(record), encoding="utf-8")
    with pytest.raises(ValidationError, match="must contain PNG"):
        validate_cover_art_candidates(tmp_path)


def test_rejects_two_paths_resolving_to_same_file(tmp_path: Path) -> None:
    path, record = _write_candidate_record(tmp_path)
    record["variants"]["wildcard"] = {
        **record["variants"]["synthetic"],
        "art_path": "art/../art/synthetic.png",
        "direction": "Aliased path",
    }
    path.write_text(yaml.safe_dump(record), encoding="utf-8")
    with pytest.raises(ValidationError, match="resolve to unique"):
        validate_cover_art_candidates(tmp_path)


def test_rejects_duplicate_image_bytes(tmp_path: Path) -> None:
    path, record = _write_candidate_record(tmp_path)
    synthetic = tmp_path / "art" / "synthetic.png"
    wildcard = tmp_path / "art" / "wildcard.png"
    wildcard.write_bytes(synthetic.read_bytes())
    record["variants"]["wildcard"]["asset_sha256"] = hashlib.sha256(
        wildcard.read_bytes()
    ).hexdigest()
    path.write_text(yaml.safe_dump(record), encoding="utf-8")
    with pytest.raises(ValidationError, match="distinct image bytes"):
        validate_cover_art_candidates(tmp_path)


def test_rejects_unrecorded_production_selection(tmp_path: Path) -> None:
    _write_candidate_record(tmp_path)
    with pytest.raises(ValidationError, match="not one of the three"):
        validate_cover_art_candidates(
            tmp_path,
            selected_art_path="art/unrecorded.png",
        )


def test_rejects_path_escape(tmp_path: Path) -> None:
    path, record = _write_candidate_record(tmp_path)
    record["variants"]["wildcard"]["art_path"] = "../outside.png"
    path.write_text(yaml.safe_dump(record), encoding="utf-8")
    with pytest.raises(ValidationError, match="escapes"):
        validate_cover_art_candidates(tmp_path)
