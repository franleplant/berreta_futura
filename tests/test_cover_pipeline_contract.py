from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image
import pytest
import yaml

from magazine import Magazine, ValidationError
from magazine.cover_art_candidates import COVER_ART_VARIANTS
from test_manifest import (
    add_extraction,
    make_project,
    pin_ledger_source_hash,
    set_open_edition,
)


def _write_cover_candidates(root: Path) -> Path:
    edition_dir = root / "editions" / "issue-001"
    variants: dict[str, dict[str, str]] = {}
    for index, variant in enumerate(COVER_ART_VARIANTS, start=1):
        art_path = edition_dir / "art" / f"cover-candidate-{variant}.png"
        Image.new("RGB", (1000, 1000), (index * 50, 20, 90)).save(art_path)
        variants[variant] = {
            "art_path": art_path.relative_to(edition_dir).as_posix(),
            "asset_sha256": hashlib.sha256(art_path.read_bytes()).hexdigest(),
            "generation_method": "imagegen",
            "direction": f"Distinct {variant} direction.",
        }
    record_path = edition_dir / "art" / "cover-candidates.yaml"
    record_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "selection_status": "pending_editor_choice",
                "editorial_reading": "A test of the systems around a model.",
                "variants": variants,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return record_path


def _make_collecting_project(root: Path) -> None:
    make_project(root)
    (
        root
        / "editions"
        / "issue-001"
        / "art"
        / "cover-candidates.yaml"
    ).unlink()
    set_open_edition(root, "issue-001", issue_number=1)
    pin_ledger_source_hash(root, add_extraction(root))


def _add_illustration_plan(root: Path) -> None:
    edition_path = root / "editions" / "issue-001" / "edition.yaml"
    edition = yaml.safe_load(edition_path.read_text(encoding="utf-8"))
    plan_path = root / "editions" / "issue-001" / "art" / "illustrations.yaml"
    plan = {
        "schema_version": 1,
        "direction": {
            "name": "Test direction",
            "visual_language": "Simple geometric scenes.",
            "palette": "Three spot colors.",
            "constraints": ["Wordless"],
            "avoid": ["Logos"],
        },
        "assets": [
            {
                "id": f"plate-{index}",
                "role": "closing_plate",
                "plate_index": index,
                "art_path": plate["art_path"],
                "subject": f"Closing scene {index}.",
                "composition": "A centered portrait scene.",
                "alt_text": f"Closing scene {index}.",
                "credit": "Illustration by the editors.",
            }
            for index, plate in enumerate(edition["closing_plates"], start=1)
        ],
    }
    plan_path.write_text(
        yaml.safe_dump(plan, sort_keys=False),
        encoding="utf-8",
    )
    edition["art_direction_path"] = plan_path.relative_to(root).as_posix()
    edition_path.write_text(
        yaml.safe_dump(edition, sort_keys=False),
        encoding="utf-8",
    )


def test_collecting_edition_cannot_validate_without_canonical_record(
    tmp_path: Path,
) -> None:
    _make_collecting_project(tmp_path)

    with pytest.raises(
        ValidationError,
        match="requires the canonical three-branch cover-art record",
    ):
        Magazine(tmp_path).validate("issue-001")


def test_collecting_edition_cannot_build_without_canonical_record(
    tmp_path: Path,
) -> None:
    _make_collecting_project(tmp_path)

    with pytest.raises(
        ValidationError,
        match="requires the canonical three-branch cover-art record",
    ):
        Magazine(tmp_path).build("issue-001")


def test_collecting_edition_discovers_canonical_record_without_manifest_opt_in(
    tmp_path: Path,
) -> None:
    _make_collecting_project(tmp_path)
    _write_cover_candidates(tmp_path)
    manifest_path = tmp_path / "editions" / "issue-001" / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    assert "cover_candidates_path" not in manifest
    assert Magazine(tmp_path).validate("issue-001").id == "issue-001"


def test_illustrate_emits_three_cover_prompts_by_canonical_discovery(
    tmp_path: Path,
) -> None:
    make_project(tmp_path)
    set_open_edition(tmp_path, "issue-001", issue_number=1)
    _write_cover_candidates(tmp_path)
    _add_illustration_plan(tmp_path)
    manifest = yaml.safe_load(
        (tmp_path / "editions" / "issue-001" / "edition.yaml").read_text(
            encoding="utf-8"
        )
    )

    destination = Magazine(tmp_path).illustration_package("issue-001")
    inventory = json.loads(
        (destination / "cover-candidates.json").read_text(encoding="utf-8")
    )

    assert "cover_candidates_path" not in manifest
    assert [row["variant"] for row in inventory["variants"]] == list(
        COVER_ART_VARIANTS
    )
    assert {
        path.name for path in destination.glob("cover-*.txt")
    } == {
        "cover-synthetic.txt",
        "cover-art_directed.txt",
        "cover-wildcard.txt",
    }


def test_illustrate_emits_cover_prompts_without_an_interior_art_plan(
    tmp_path: Path,
) -> None:
    make_project(tmp_path)
    set_open_edition(tmp_path, "issue-001", issue_number=1)
    _write_cover_candidates(tmp_path)
    manifest_path = tmp_path / "editions" / "issue-001" / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("art_direction_path", None)
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False),
        encoding="utf-8",
    )

    destination = Magazine(tmp_path).illustration_package("issue-001")

    assert (destination / "cover-candidates.json").is_file()
    assert not (destination / "illustrations.json").exists()


def test_collecting_illustrate_scaffolds_and_hydrates_three_cover_branches(
    tmp_path: Path,
) -> None:
    _make_collecting_project(tmp_path)

    destination = Magazine(tmp_path).illustration_package("issue-001")
    record_path = (
        tmp_path
        / "editions"
        / "issue-001"
        / "art"
        / "cover-candidates.yaml"
    )
    record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
    inventory = json.loads(
        (destination / "cover-candidates.json").read_text(encoding="utf-8")
    )

    assert tuple(record["variants"]) == COVER_ART_VARIANTS
    assert not record["editorial_reading"].startswith("TODO:")
    assert [row["variant"] for row in inventory["variants"]] == list(
        COVER_ART_VARIANTS
    )
    assert not (destination / "illustrations.json").exists()


def test_released_edition_without_cover_candidate_record_still_validates(
    tmp_path: Path,
) -> None:
    make_project(tmp_path)
    candidate_path = (
        tmp_path
        / "editions"
        / "issue-001"
        / "art"
        / "cover-candidates.yaml"
    )
    candidate_path.unlink()
    state_path = tmp_path / "library" / "release-state.yaml"
    state_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "intake_edition_id": "999-unreleased",
                "collecting_editions": [
                    {
                        "id": "999-unreleased",
                        "issue_number": 999,
                        "status": "collecting",
                        "source_ids": [],
                    }
                ],
                "released_editions": [
                    {
                        "id": "issue-001",
                        "issue_number": 1,
                        "source_ids": ["source-one"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    assert not candidate_path.exists()
    assert Magazine(tmp_path).validate("issue-001").id == "issue-001"


def test_released_edition_ignores_an_incomplete_legacy_candidate_record(
    tmp_path: Path,
) -> None:
    make_project(tmp_path)
    record_path = (
        tmp_path
        / "editions"
        / "issue-001"
        / "art"
        / "cover-candidates.yaml"
    )
    record_path.write_text(
        "legacy_authoring_note: optional and incomplete\n",
        encoding="utf-8",
    )
    state_path = tmp_path / "library" / "release-state.yaml"
    state_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "intake_edition_id": "999-unreleased",
                "collecting_editions": [
                    {
                        "id": "999-unreleased",
                        "issue_number": 999,
                        "status": "collecting",
                        "source_ids": [],
                    }
                ],
                "released_editions": [
                    {
                        "id": "issue-001",
                        "issue_number": 1,
                        "source_ids": ["source-one"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    assert Magazine(tmp_path).validate("issue-001").id == "issue-001"

    destination = Magazine(tmp_path).illustration_package("issue-001")
    assert not (destination / "cover-candidates.json").exists()


def test_cover_only_illustrate_removes_stale_interior_prompt_outputs(
    tmp_path: Path,
) -> None:
    make_project(tmp_path)
    set_open_edition(tmp_path, "issue-001", issue_number=1)
    _write_cover_candidates(tmp_path)
    destination = tmp_path / "output" / "issue-001" / "illustration-prompts"
    destination.mkdir(parents=True)
    (destination / "old-tail.txt").write_text("stale\n", encoding="utf-8")
    (destination / "illustrations.json").write_text("{}\n", encoding="utf-8")

    Magazine(tmp_path).illustration_package("issue-001")

    assert not (destination / "old-tail.txt").exists()
    assert not (destination / "illustrations.json").exists()
    assert (destination / "cover-candidates.json").is_file()
