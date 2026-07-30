from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import pytest
import yaml

from magazine.cover_art_candidates import (
    COVER_ART_VARIANTS,
    validate_cover_art_candidates,
)
from magazine.cover_studio import (
    CoverProofRequest,
    CoverStudio,
    CoverStudioConflict,
)
from magazine.errors import ValidationError


def _write_edition(path: Path) -> None:
    path.mkdir()
    (path / "edition.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "id": path.name,
                "cover": {
                    "headline": "A systems issue",
                    "art_path": "art/not-selected.png",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _generated_images(path: Path, *, seed: int = 0) -> dict[str, Path]:
    path.mkdir(parents=True)
    images: dict[str, Path] = {}
    for index, variant in enumerate(COVER_ART_VARIANTS):
        image = path / f"{variant}.png"
        Image.new(
            "RGB",
            (1000, 1000),
            ((seed + index * 50) % 256, 20 + index, 40 + seed),
        ).save(image)
        images[variant] = image
    return images


def _registered_round(
    studio: CoverStudio,
    generated_root: Path,
    *,
    seed: int,
) -> int:
    action = studio.scaffold_next_round(
        editorial_reading="Systems make capable models useful."
    )
    assert action.round_number is not None
    studio.register_round(
        action.round_number,
        _generated_images(generated_root, seed=seed),
    )
    return action.round_number


def test_next_round_numbering_discovers_all_rounds_and_preserves_history(
    tmp_path: Path,
) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    studio = CoverStudio(edition)

    first = studio.scaffold_next_round(
        editorial_reading="Systems make capable models useful."
    )
    first_bytes = first.writes[0].read_bytes()
    second = studio.scaffold_next_round()

    status = studio.inspect()
    assert first.round_number == 1
    assert second.round_number == 2
    assert [item.number for item in status.rounds] == [1, 2]
    assert status.next_round == 3
    assert first.writes[0].read_bytes() == first_bytes
    assert all(not item.registered and not item.valid for item in status.rounds)
    assert tuple(item.name for item in status.rounds[0].variants) == COVER_ART_VARIANTS


def test_registration_copies_round_owned_pngs_and_computes_hashes_idempotently(
    tmp_path: Path,
) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    studio = CoverStudio(edition)
    round_number = studio.scaffold_next_round(
        editorial_reading="Systems make capable models useful."
    ).round_number
    assert round_number == 1
    generated = _generated_images(tmp_path / "generated", seed=10)

    first = studio.register_round(round_number, generated)
    record_path = edition / "art" / "cover-candidates-round-1.yaml"
    record = yaml.safe_load(record_path.read_text(encoding="utf-8"))

    assert first.changed is True
    for variant in COVER_ART_VARIANTS:
        destination = edition / record["variants"][variant]["art_path"]
        assert destination.read_bytes() == generated[variant].read_bytes()
        assert record["variants"][variant]["asset_sha256"] == hashlib.sha256(
            destination.read_bytes()
        ).hexdigest()
    validate_cover_art_candidates(edition, record_path=record_path)

    record_bytes = record_path.read_bytes()
    second = studio.register_round(round_number, generated)
    assert second.changed is False
    assert record_path.read_bytes() == record_bytes


def test_invalid_registration_rolls_back_without_images_or_hashes(
    tmp_path: Path,
) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    studio = CoverStudio(edition)
    studio.scaffold_next_round(
        editorial_reading="Systems make capable models useful."
    )
    record_path = edition / "art" / "cover-candidates-round-1.yaml"
    before = record_path.read_bytes()
    generated = _generated_images(tmp_path / "generated")
    Image.new("RGB", (900, 900), "white").save(generated["wildcard"])

    with pytest.raises(ValidationError, match="at least 1000px"):
        studio.register_round(1, generated)

    assert record_path.read_bytes() == before
    assert not (edition / "art" / "cover-rounds" / "round-1").exists()


def test_prompt_package_is_deterministic_and_never_overwrites_changed_evidence(
    tmp_path: Path,
) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    studio = CoverStudio(edition)
    studio.scaffold_next_round(
        editorial_reading="Systems make capable models useful."
    )

    first = studio.emit_prompt_package(1)
    contents = {path: path.read_bytes() for path in first.writes}
    second = studio.emit_prompt_package(1)

    assert second.changed is False
    assert {path: path.read_bytes() for path in second.writes} == contents
    inventory = yaml.safe_load(
        next(path for path in first.writes if path.name.endswith(".json")).read_text(
            encoding="utf-8"
        )
    )
    assert [item["variant"] for item in inventory["variants"]] == list(
        COVER_ART_VARIANTS
    )

    prompt = next(path for path in first.writes if path.name == "cover-synthetic.txt")
    prompt.write_text("human work\n", encoding="utf-8")
    with pytest.raises(CoverStudioConflict, match="different bytes"):
        CoverStudio(edition).emit_prompt_package(1)


def test_selection_updates_canonical_and_manifest_without_mutating_rounds(
    tmp_path: Path,
) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    studio = CoverStudio(edition)
    first_round = _registered_round(studio, tmp_path / "generated-1", seed=10)
    second_round = _registered_round(studio, tmp_path / "generated-2", seed=100)
    round_paths = [
        edition / "art" / f"cover-candidates-round-{number}.yaml"
        for number in (first_round, second_round)
    ]
    preserved = {path: path.read_bytes() for path in round_paths}

    action = studio.select(first_round, "art_directed")
    canonical_path = edition / "art" / "cover-candidates.yaml"
    canonical = yaml.safe_load(canonical_path.read_text(encoding="utf-8"))
    manifest = yaml.safe_load((edition / "edition.yaml").read_text(encoding="utf-8"))

    assert action.changed is True
    assert canonical["round"] == 1
    assert canonical["selection_status"] == "selected"
    assert canonical["selected_variant"] == "art_directed"
    assert manifest["cover"]["art_path"] == canonical["variants"]["art_directed"]["art_path"]
    assert {path: path.read_bytes() for path in round_paths} == preserved
    validate_cover_art_candidates(
        edition,
        selected_art_path=manifest["cover"]["art_path"],
    )

    canonical_bytes = canonical_path.read_bytes()
    manifest_bytes = (edition / "edition.yaml").read_bytes()
    assert studio.select(first_round, "art_directed").changed is False
    assert canonical_path.read_bytes() == canonical_bytes
    assert (edition / "edition.yaml").read_bytes() == manifest_bytes


def test_selection_rolls_back_if_two_file_commit_fails(tmp_path: Path) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    studio = CoverStudio(edition)
    _registered_round(studio, tmp_path / "generated", seed=10)
    manifest_path = edition / "edition.yaml"
    before = manifest_path.read_bytes()
    real_replace = __import__("os").replace
    calls = 0

    def fail_second(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated manifest failure")
        real_replace(source, destination)

    with patch("magazine.cover_studio.os.replace", side_effect=fail_second):
        with pytest.raises(ValidationError, match="Cannot commit cover studio state"):
            studio.select(1, "synthetic")

    assert not (edition / "art" / "cover-candidates.yaml").exists()
    assert manifest_path.read_bytes() == before


def test_selection_rolls_back_both_files_if_post_write_validation_fails(
    tmp_path: Path,
) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    studio = CoverStudio(edition)
    _registered_round(studio, tmp_path / "generated", seed=10)
    studio.select(1, "synthetic")
    canonical_path = edition / "art" / "cover-candidates.yaml"
    manifest_path = edition / "edition.yaml"
    canonical_before = canonical_path.read_bytes()
    manifest_before = manifest_path.read_bytes()
    real_validate = validate_cover_art_candidates

    def reject_canonical(
        edition_dir: Path,
        *,
        record_path: Path | None = None,
        selected_art_path: str | None = None,
    ) -> dict[str, object]:
        if record_path == canonical_path:
            raise ValidationError("simulated post-write validation failure")
        return real_validate(
            edition_dir,
            record_path=record_path,
            selected_art_path=selected_art_path,
        )

    with patch(
        "magazine.cover_studio.validate_cover_art_candidates",
        side_effect=reject_canonical,
    ):
        with pytest.raises(
            ValidationError,
            match="simulated post-write validation failure",
        ):
            studio.select(1, "art_directed")

    assert canonical_path.read_bytes() == canonical_before
    assert manifest_path.read_bytes() == manifest_before


def test_selection_preserves_manifest_comments_quotes_and_wrapping(
    tmp_path: Path,
) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    manifest_path = edition / "edition.yaml"
    manifest_path.write_text(
        "schema_version: 1 # schema comment\n"
        "id: issue\n"
        "cover:\n"
        '  headline: "A systems issue" # headline comment\n'
        "  art_path: 'art/not-selected.png' # selected asset\n"
        "notes: >-\n"
        "  This wrapping and every comment must remain untouched.\n",
        encoding="utf-8",
    )
    studio = CoverStudio(edition)
    _registered_round(studio, tmp_path / "generated", seed=10)
    round_record = yaml.safe_load(
        (edition / "art" / "cover-candidates-round-1.yaml").read_text(
            encoding="utf-8"
        )
    )
    selected_path = round_record["variants"]["wildcard"]["art_path"]
    before = manifest_path.read_bytes()
    expected = before.replace(
        b"'art/not-selected.png'",
        f"'{selected_path}'".encode("utf-8"),
    )

    studio.select(1, "wildcard")

    assert manifest_path.read_bytes() == expected


def test_canonical_requires_selected_variant_to_match_manifest(
    tmp_path: Path,
) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    studio = CoverStudio(edition)
    _registered_round(studio, tmp_path / "generated", seed=10)
    studio.select(1, "synthetic")
    canonical_path = edition / "art" / "cover-candidates.yaml"
    canonical = yaml.safe_load(canonical_path.read_text(encoding="utf-8"))
    canonical["selected_variant"] = "wildcard"
    canonical_path.write_text(
        yaml.safe_dump(canonical, sort_keys=False),
        encoding="utf-8",
    )

    selection = CoverStudio(edition).inspect().canonical

    assert selection is not None
    assert selection.valid is False
    assert "but edition cover.art_path is" in (selection.error or "")


def test_canonical_requires_exact_immutable_round_content(tmp_path: Path) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    studio = CoverStudio(edition)
    _registered_round(studio, tmp_path / "generated", seed=10)
    studio.select(1, "synthetic")
    canonical_path = edition / "art" / "cover-candidates.yaml"
    canonical = yaml.safe_load(canonical_path.read_text(encoding="utf-8"))
    canonical["variants"]["wildcard"]["direction"] = "Tampered direction"
    canonical_path.write_text(
        yaml.safe_dump(canonical, sort_keys=False),
        encoding="utf-8",
    )

    selection = CoverStudio(edition).inspect().canonical

    assert selection is not None
    assert selection.valid is False
    assert "does not match immutable round 1" in (selection.error or "")


def test_schema_two_canonical_cannot_drop_round_to_bypass_provenance(
    tmp_path: Path,
) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    studio = CoverStudio(edition)
    _registered_round(studio, tmp_path / "generated", seed=10)
    studio.select(1, "synthetic")
    canonical_path = edition / "art" / "cover-candidates.yaml"
    canonical = yaml.safe_load(canonical_path.read_text(encoding="utf-8"))
    canonical.pop("round")
    canonical["variants"]["wildcard"]["direction"] = "Tampered direction"
    canonical_path.write_text(
        yaml.safe_dump(canonical, sort_keys=False),
        encoding="utf-8",
    )

    selection = CoverStudio(edition).inspect().canonical

    assert selection is not None
    assert selection.valid is False
    assert "requires a positive round" in (selection.error or "")


def test_schema_two_canonical_infers_unique_variant_with_round_provenance(
    tmp_path: Path,
) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    studio = CoverStudio(edition)
    _registered_round(studio, tmp_path / "generated", seed=10)
    studio.select(1, "art_directed")
    canonical_path = edition / "art" / "cover-candidates.yaml"
    canonical = yaml.safe_load(canonical_path.read_text(encoding="utf-8"))
    assert canonical["schema_version"] == 2
    assert canonical["round"] == 1
    assert canonical["selection_status"] == "selected"
    canonical.pop("selected_variant")
    canonical_path.write_text(
        yaml.safe_dump(canonical, sort_keys=False),
        encoding="utf-8",
    )

    selection = CoverStudio(edition).inspect().canonical

    assert selection is not None
    assert selection.valid is True
    assert selection.round_number == 1
    assert selection.variant == "art_directed"


def test_schema_one_canonical_without_round_infers_selected_variant(
    tmp_path: Path,
) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    studio = CoverStudio(edition)
    _registered_round(studio, tmp_path / "generated", seed=10)
    round_path = edition / "art" / "cover-candidates-round-1.yaml"
    legacy = yaml.safe_load(round_path.read_text(encoding="utf-8"))
    legacy["schema_version"] = 1
    legacy.pop("round")
    legacy.pop("selected_variant", None)
    canonical_path = edition / "art" / "cover-candidates.yaml"
    canonical_path.write_text(
        yaml.safe_dump(legacy, sort_keys=False),
        encoding="utf-8",
    )
    manifest_path = edition / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["cover"]["art_path"] = legacy["variants"]["art_directed"]["art_path"]
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False),
        encoding="utf-8",
    )

    selection = CoverStudio(edition).inspect().canonical

    assert selection is not None
    assert selection.valid is True
    assert selection.round_number is None
    assert selection.variant == "art_directed"


def test_stale_session_refuses_concurrent_round_creation(tmp_path: Path) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    first = CoverStudio(edition)
    stale = CoverStudio(edition)

    first.scaffold_next_round(
        editorial_reading="Systems make capable models useful."
    )

    with pytest.raises(CoverStudioConflict, match="state is stale"):
        stale.scaffold_next_round(
            editorial_reading="This must not overwrite current state."
        )
    assert [item.number for item in CoverStudio(edition).inspect().rounds] == [1]


class _ProofAdapter:
    def __init__(self) -> None:
        self.requests: list[CoverProofRequest] = []

    def render(self, request: CoverProofRequest) -> dict[str, bytes]:
        self.requests.append(request)
        return {
            "cover.png": (
                f"{request.round_number}:{request.language}:{request.variant}"
            ).encode("utf-8")
        }


def test_proof_render_rejects_symlinked_destination_before_adapter_call(
    tmp_path: Path,
) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    adapter = _ProofAdapter()
    studio = CoverStudio(edition, proof_adapter=adapter)
    _registered_round(studio, tmp_path / "generated", seed=10)
    outside = tmp_path / "outside"
    outside.mkdir()
    proofs = edition / "art" / "cover-rounds" / "round-1" / "proofs"
    proofs.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValidationError, match="destination escapes"):
        studio.render_proofs(("en",))

    assert adapter.requests == []
    assert list(outside.iterdir()) == []


def test_proof_render_rejects_same_edition_destination_redirect_before_adapter(
    tmp_path: Path,
) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    adapter = _ProofAdapter()
    studio = CoverStudio(edition, proof_adapter=adapter)
    _registered_round(studio, tmp_path / "generated", seed=10)
    manifest_path = edition / "edition.yaml"
    manifest_before = manifest_path.read_bytes()
    destination = (
        edition
        / "art"
        / "cover-rounds"
        / "round-1"
        / "proofs"
        / "en"
        / "synthetic"
    )
    destination.parent.mkdir(parents=True)
    destination.symlink_to(edition, target_is_directory=True)

    with pytest.raises(ValidationError, match="redirected path component"):
        studio.render_proofs(("en",))

    assert adapter.requests == []
    assert manifest_path.read_bytes() == manifest_before


class _ArtifactSymlinkAdapter:
    def __init__(self, outside: Path) -> None:
        self.outside = outside

    def render(self, request: CoverProofRequest) -> dict[str, bytes]:
        request.destination.mkdir(parents=True, exist_ok=True)
        (request.destination / "redirect").symlink_to(
            self.outside,
            target_is_directory=True,
        )
        return {"redirect/cover.png": b"must stay inside the edition"}


def test_proof_render_rejects_adapter_artifact_through_symlink(
    tmp_path: Path,
) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    outside = tmp_path / "outside"
    outside.mkdir()
    studio = CoverStudio(
        edition,
        proof_adapter=_ArtifactSymlinkAdapter(outside),
    )
    _registered_round(studio, tmp_path / "generated", seed=10)

    with pytest.raises(ValidationError, match="escapes its destination"):
        studio.render_proofs(("en",))

    assert not (outside / "cover.png").exists()


def test_proof_adapter_receives_every_round_variant_and_language(
    tmp_path: Path,
) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    adapter = _ProofAdapter()
    studio = CoverStudio(edition, proof_adapter=adapter)
    _registered_round(studio, tmp_path / "generated-1", seed=10)
    _registered_round(studio, tmp_path / "generated-2", seed=100)

    plan = studio.proof_plan(("en", "es"))
    action = studio.render_proofs(("en", "es"))

    assert len(plan) == 12
    assert [
        (item.round_number, item.language, item.variant)
        for item in adapter.requests
    ] == [
        (item.round_number, item.language, item.variant)
        for item in plan
    ]
    assert len(action.writes) == 12
    assert all(path.is_file() for path in action.writes)
    assert studio.render_proofs(("en", "es")).changed is False


def test_dry_run_plans_without_writing_and_contact_sheet_is_round_ordered(
    tmp_path: Path,
) -> None:
    edition = tmp_path / "issue"
    _write_edition(edition)
    studio = CoverStudio(edition)
    planned = studio.scaffold_next_round(
        editorial_reading="Systems make capable models useful.",
        dry_run=True,
    )
    assert planned.dry_run is True
    assert not planned.writes[0].exists()
    assert not (edition / "art").exists()

    _registered_round(studio, tmp_path / "generated-1", seed=10)
    _registered_round(studio, tmp_path / "generated-2", seed=100)
    action = studio.create_comparison_sheet()

    with Image.open(action.writes[0]) as comparison:
        assert comparison.size == (1200, 868)
        assert comparison.getpixel((10, 10)) == (10, 20, 50)
        assert comparison.getpixel((10, 444)) == (100, 20, 140)
