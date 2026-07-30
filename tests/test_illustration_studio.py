from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image
import pytest
import yaml

from magazine.errors import ValidationError
from magazine.illustration import validate_illustration_plan
import magazine.illustration_studio as illustration_studio_module
from magazine.illustration_studio import (
    IllustrationBrief,
    IllustrationStudio,
    IllustrationStudioConflict,
)


EDITION_ID = "issue-one"


def _write_png(
    path: Path,
    size: tuple[int, int],
    color: tuple[int, int, int] | str = "white",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)


def _project(tmp_path: Path, *, articles: tuple[str, ...] = ("one", "two")) -> Path:
    edition_dir = tmp_path / "editions" / EDITION_ID
    edition_dir.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "id": EDITION_ID,
        "issue_number": "1",
        "title": "A test issue",
        "publication_date": "2026-07-29",
        "articles": [{"id": article_id} for article_id in articles],
        "closing_plates": [
            {
                "title": f"Plate {index}",
                "art_path": (
                    f"editions/{EDITION_ID}/art/closing-plate-{index}.png"
                ),
            }
            for index in range(1, 4)
        ],
    }
    (edition_dir / "edition.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    state = {
        "schema_version": 2,
        "intake_edition_id": EDITION_ID,
        "collecting_editions": [
            {
                "id": EDITION_ID,
                "issue_number": 1,
                "status": "collecting",
                "source_ids": [],
            }
        ],
        "released_editions": [],
    }
    state_path = tmp_path / "library" / "release-state.yaml"
    state_path.parent.mkdir()
    state_path.write_text(
        yaml.safe_dump(state, sort_keys=False), encoding="utf-8"
    )
    return edition_dir


def _brief(
    *,
    articles: tuple[str, ...] = ("one",),
    plates: tuple[int, ...] = (1, 2, 3),
) -> dict:
    return {
        "schema_version": 1,
        "edition_id": EDITION_ID,
        "direction": {
            "name": "Friendly systems",
            "visual_language": "Chunky black ink and flat spot color.",
            "palette": "Warm paper, violet, orange, and blue.",
            "constraints": ["Wordless", "Strong silhouette"],
            "avoid": ["Logos", "Franchise characters"],
        },
        "assets": [
            *[
                {
                    "id": f"tail-{article_id}",
                    "role": "article_tail",
                    "article_id": article_id,
                    "subject": f"A useful scene for {article_id}.",
                    "composition": "Keep the action in the central horizontal third.",
                    "alt_text": f"A useful scene for {article_id}.",
                    "credit": "Original illustration by the editors.",
                }
                for article_id in articles
            ],
            *[
                {
                    "id": f"closing-{index}",
                    "role": "closing_plate",
                    "plate_index": index,
                    "subject": f"Closing scene {index}.",
                    "composition": "A clear portrait composition.",
                    "alt_text": f"Closing scene {index}.",
                    "credit": "Original illustration by the editors.",
                }
                for index in plates
            ],
        ],
    }


def _scaffold(tmp_path: Path) -> tuple[IllustrationStudio, Path]:
    edition_dir = _project(tmp_path)
    studio = IllustrationStudio(tmp_path)
    studio.scaffold(_brief())
    return studio, edition_dir


def _register_all(studio: IllustrationStudio, tmp_path: Path) -> None:
    for index, asset in enumerate(studio.status(EDITION_ID).assets, start=1):
        source = tmp_path / "supplied" / f"{asset.id}.png"
        size = (1536, 1024) if asset.role == "article_tail" else (1024, 1400)
        _write_png(source, size, (index, index * 2, index * 3))
        studio.register_asset(EDITION_ID, asset.id, source)


def test_scaffold_explicit_subset_preserves_unselected_articles(tmp_path: Path):
    edition_dir = _project(tmp_path)
    before = (edition_dir / "edition.yaml").read_text(encoding="utf-8")
    studio = IllustrationStudio(tmp_path)

    action = studio.scaffold(_brief(articles=("one",)))

    assert action.changed
    manifest_text = (edition_dir / "edition.yaml").read_text(encoding="utf-8")
    manifest = yaml.safe_load(manifest_text)
    assert manifest["articles"][0]["tail_art_path"].endswith("/one.png")
    assert "tail_art_path" not in manifest["articles"][1]
    assert manifest_text.count("#") == before.count("#")
    plan = yaml.safe_load(
        (edition_dir / "art" / "illustrations.yaml").read_text(encoding="utf-8")
    )
    assert [row["id"] for row in plan["assets"]] == [
        "tail-one",
        "closing-1",
        "closing-2",
        "closing-3",
    ]
    assert all(row["asset_sha256"] == "PENDING" for row in plan["assets"])


def test_status_separates_missing_brief_prompt_ready_and_ready(tmp_path: Path):
    edition_dir = _project(tmp_path)
    studio = IllustrationStudio(tmp_path)

    missing = studio.status(EDITION_ID)
    assert missing.state == "missing_brief"
    assert missing.to_dict()["assets"] == []

    studio.scaffold(_brief(), expected_revision=missing.revision)
    prompt_ready = studio.status(EDITION_ID)
    assert prompt_ready.state == "prompt_ready"
    assert {asset.asset_status for asset in prompt_ready.assets} == {
        "prompt_ready"
    }

    _register_all(studio, tmp_path)
    ready = studio.status(EDITION_ID)
    assert ready.state == "ready"
    assert all(asset.asset_status == "ready" for asset in ready.assets)
    assert ready.to_dict() == studio.status(EDITION_ID).to_dict()
    assert (edition_dir / "art" / "article-tails" / "one.png").is_file()


def test_scaffold_dry_run_and_idempotency_do_not_overwrite_plan(tmp_path: Path):
    edition_dir = _project(tmp_path)
    studio = IllustrationStudio(tmp_path)

    dry = studio.scaffold(_brief(), dry_run=True)
    assert dry.changed
    assert not (edition_dir / "art" / "illustrations.yaml").exists()

    first = studio.scaffold(_brief())
    plan_path = edition_dir / "art" / "illustrations.yaml"
    plan_path.write_text(
        plan_path.read_text(encoding="utf-8") + "# Human note\n",
        encoding="utf-8",
    )
    fresh = IllustrationStudio(tmp_path)
    second = fresh.scaffold(_brief())

    assert first.changed
    assert not second.changed
    assert plan_path.read_text(encoding="utf-8").endswith("# Human note\n")


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda row: row.update({"schema_version": 2}), "schema_version"),
        (
            lambda row: row["assets"].append(dict(row["assets"][0])),
            "must be unique",
        ),
        (
            lambda row: row["assets"][0].update({"article_id": "../one"}),
            "lowercase letters",
        ),
        (
            lambda row: row["assets"][0].update({"art_path": "../../escape.png"}),
            "safe project-relative",
        ),
    ],
)
def test_malformed_briefs_are_rejected(tmp_path: Path, mutation, match: str):
    _project(tmp_path)
    data = _brief()
    mutation(data)

    with pytest.raises(ValidationError, match=match):
        IllustrationBrief.from_dict(data)


def test_unknown_and_incomplete_inventory_is_rejected(tmp_path: Path):
    _project(tmp_path)
    studio = IllustrationStudio(tmp_path)
    unknown = _brief(articles=("missing",))
    incomplete = _brief(plates=(1, 2))

    with pytest.raises(ValidationError, match="unknown article"):
        studio.scaffold(unknown)
    with pytest.raises(ValidationError, match="configured indices exactly"):
        IllustrationStudio(tmp_path).scaffold(incomplete)


def test_existing_authored_plan_is_never_replaced(tmp_path: Path):
    studio, edition_dir = _scaffold(tmp_path)
    plan_path = edition_dir / "art" / "illustrations.yaml"
    original = plan_path.read_bytes()
    changed = _brief()
    changed["assets"][0]["subject"] = "A different authored decision."

    with pytest.raises(IllustrationStudioConflict, match="differ"):
        IllustrationStudio(tmp_path).scaffold(changed)

    assert plan_path.read_bytes() == original
    assert studio.status(EDITION_ID).state == "prompt_ready"


def test_prompt_package_is_deterministic_and_contains_no_cover_prompts(tmp_path: Path):
    studio, _ = _scaffold(tmp_path)

    first = studio.emit_prompt_package(EDITION_ID)
    inventory_path = (
        tmp_path
        / "output"
        / EDITION_ID
        / "interior-illustration-prompts"
        / "illustrations.json"
    )
    before = inventory_path.read_bytes()
    second = studio.emit_prompt_package(EDITION_ID)
    payload = json.loads(before)

    assert first.changed
    assert not second.changed
    assert inventory_path.read_bytes() == before
    assert "cover" not in {path.name for path in first.writes}
    assert [row["id"] for row in payload["assets"]] == [
        "tail-one",
        "closing-1",
        "closing-2",
        "closing-3",
    ]
    prompt = inventory_path.parent / payload["assets"][0]["prompt"]
    assert "Friendly systems" in prompt.read_text(encoding="utf-8")


@pytest.mark.parametrize("unsafe_id", ("../escape", "nested/escape", "/absolute"))
def test_authored_plan_rejects_unsafe_asset_ids_before_prompt_paths(
    tmp_path: Path, unsafe_id: str
):
    studio, edition_dir = _scaffold(tmp_path)
    plan_path = edition_dir / "art" / "illustrations.yaml"
    record = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    record["assets"][0]["id"] = unsafe_id
    plan_path.write_text(
        yaml.safe_dump(record, sort_keys=False), encoding="utf-8"
    )
    studio = IllustrationStudio(tmp_path)

    status = studio.status(EDITION_ID)

    assert status.state == "invalid_brief"
    assert any("id must use lowercase" in error for error in status.errors)
    with pytest.raises(ValidationError, match="id must use lowercase"):
        studio.emit_prompt_package(EDITION_ID)
    assert not (tmp_path / "output").exists()


def test_register_validates_png_computes_hash_and_preserves_comments(tmp_path: Path):
    studio, edition_dir = _scaffold(tmp_path)
    plan_path = edition_dir / "art" / "illustrations.yaml"
    text = plan_path.read_text(encoding="utf-8")
    plan_path.write_text(
        text.replace("- id: tail-one", "# Keep this note\n- id: tail-one"),
        encoding="utf-8",
    )
    studio = IllustrationStudio(tmp_path)
    source = tmp_path / "source.png"
    _write_png(source, (1536, 1024))

    action = studio.register_asset(EDITION_ID, "tail-one", source)

    target = edition_dir / "art" / "article-tails" / "one.png"
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    record = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    assert action.changed
    assert target.read_bytes() == source.read_bytes()
    assert record["assets"][0]["asset_sha256"] == expected
    assert "# Keep this note" in plan_path.read_text(encoding="utf-8")
    assert studio.status(EDITION_ID).assets[0].actual_sha256 == expected


def test_register_dry_run_writes_nothing(tmp_path: Path):
    studio, edition_dir = _scaffold(tmp_path)
    source = tmp_path / "source.png"
    _write_png(source, (1536, 1024))
    plan_path = edition_dir / "art" / "illustrations.yaml"
    before = plan_path.read_bytes()

    action = studio.register_asset(
        EDITION_ID, "tail-one", source, dry_run=True
    )

    assert action.changed
    assert plan_path.read_bytes() == before
    assert not (edition_dir / "art" / "article-tails" / "one.png").exists()


@pytest.mark.parametrize(
    ("size", "match"),
    [
        ((1024, 1024), "requires at least"),
        ((1024, 1536), "landscape"),
    ],
)
def test_register_rejects_invalid_article_rasters(
    tmp_path: Path, size: tuple[int, int], match: str
):
    studio, edition_dir = _scaffold(tmp_path)
    source = tmp_path / "source.png"
    _write_png(source, size)
    plan_before = (edition_dir / "art" / "illustrations.yaml").read_bytes()

    with pytest.raises(ValidationError, match=match):
        studio.register_asset(EDITION_ID, "tail-one", source)

    assert not (edition_dir / "art" / "article-tails" / "one.png").exists()
    assert (edition_dir / "art" / "illustrations.yaml").read_bytes() == plan_before


def test_concurrent_plan_edit_in_final_commit_window_is_preserved(
    tmp_path: Path, monkeypatch
):
    studio, edition_dir = _scaffold(tmp_path)
    source = tmp_path / "source.png"
    _write_png(source, (1536, 1024))
    plan_path = edition_dir / "art" / "illustrations.yaml"
    target = edition_dir / "art" / "article-tails" / "one.png"
    real_replace = illustration_studio_module.os.replace
    injected = False

    def concurrent_edit(source_path, destination_path):
        nonlocal injected
        if Path(source_path) == plan_path and not injected:
            injected = True
            with plan_path.open("a", encoding="utf-8") as handle:
                handle.write("# concurrent art director note\n")
        return real_replace(source_path, destination_path)

    monkeypatch.setattr(
        illustration_studio_module.os, "replace", concurrent_edit
    )

    with pytest.raises(IllustrationStudioConflict, match="preserved"):
        studio.register_asset(EDITION_ID, "tail-one", source)

    assert plan_path.read_text(encoding="utf-8").endswith(
        "# concurrent art director note\n"
    )
    assert not target.exists()


def test_register_rejects_a_non_png_raster(tmp_path: Path):
    studio, _ = _scaffold(tmp_path)
    source = tmp_path / "source.jpg"
    Image.new("RGB", (1536, 1024), "white").save(source, format="JPEG")

    with pytest.raises(ValidationError, match="must be PNG"):
        studio.register_asset(EDITION_ID, "tail-one", source)


def test_truncated_png_fails_registration_and_status(tmp_path: Path):
    studio, edition_dir = _scaffold(tmp_path)
    source = tmp_path / "truncated.png"
    _write_png(source, (1536, 1024), (12, 34, 56))
    source.write_bytes(source.read_bytes()[:-100])

    with pytest.raises(ValidationError, match="cannot be decoded"):
        studio.register_asset(EDITION_ID, "tail-one", source)

    target = edition_dir / "art" / "article-tails" / "one.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    plan_path = edition_dir / "art" / "illustrations.yaml"
    record = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    record["assets"][0]["asset_sha256"] = hashlib.sha256(
        target.read_bytes()
    ).hexdigest()
    plan_path.write_text(
        yaml.safe_dump(record, sort_keys=False), encoding="utf-8"
    )

    status = IllustrationStudio(tmp_path).status(EDITION_ID)

    assert status.assets[0].asset_status == "invalid_raster"
    assert "cannot be decoded" in status.assets[0].error


def test_register_rejects_symlink_duplicate_and_existing_target(tmp_path: Path):
    studio, edition_dir = _scaffold(tmp_path)
    source = tmp_path / "source.png"
    _write_png(source, (1024, 1400))
    link = tmp_path / "linked.png"
    link.symlink_to(source)

    with pytest.raises(ValidationError, match="symlink"):
        studio.register_asset(EDITION_ID, "closing-1", link)

    studio.register_asset(EDITION_ID, "closing-1", source)
    duplicate = tmp_path / "duplicate.png"
    duplicate.write_bytes(source.read_bytes())
    with pytest.raises(ValidationError, match="duplicates bytes"):
        studio.register_asset(EDITION_ID, "closing-2", duplicate)

    target = edition_dir / "art" / "closing-plate-2.png"
    _write_png(target, (1024, 1400))
    Image.new("RGB", (1024, 1400), "black").save(duplicate)
    with pytest.raises(IllustrationStudioConflict, match="different bytes"):
        IllustrationStudio(tmp_path).register_asset(
            EDITION_ID, "closing-2", duplicate
        )


def test_registration_rolls_back_if_the_second_atomic_replace_fails(
    tmp_path: Path, monkeypatch
):
    studio, edition_dir = _scaffold(tmp_path)
    source = tmp_path / "source.png"
    _write_png(source, (1536, 1024))
    plan_path = edition_dir / "art" / "illustrations.yaml"
    plan_before = plan_path.read_bytes()
    target = edition_dir / "art" / "article-tails" / "one.png"
    real_link = illustration_studio_module.os.link
    calls = 0

    def fail_once(source_path, target_path, *, follow_symlinks=False):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected replacement failure")
        return real_link(
            source_path,
            target_path,
            follow_symlinks=follow_symlinks,
        )

    monkeypatch.setattr(illustration_studio_module.os, "link", fail_once)

    with pytest.raises(OSError, match="injected"):
        studio.register_asset(EDITION_ID, "tail-one", source)

    assert not target.exists()
    assert plan_path.read_bytes() == plan_before


@pytest.mark.parametrize(
    ("row_index", "replacement", "match"),
    [
        (
            0,
            {
                "id": "another-tail",
                "art_path": (
                    f"editions/{EDITION_ID}/art/article-tails/another.png"
                ),
            },
            "article_id must be unique",
        ),
        (
            1,
            {
                "id": "another-closing",
                "art_path": (
                    f"editions/{EDITION_ID}/art/another-closing.png"
                ),
            },
            "plate_index must be unique",
        ),
    ],
)
def test_loaded_plan_rejects_duplicate_slot_targets(
    tmp_path: Path,
    row_index: int,
    replacement: dict[str, str],
    match: str,
):
    _, edition_dir = _scaffold(tmp_path)
    plan_path = edition_dir / "art" / "illustrations.yaml"
    record = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    duplicate = dict(record["assets"][row_index])
    duplicate.update(replacement)
    record["assets"].append(duplicate)
    plan_path.write_text(
        yaml.safe_dump(record, sort_keys=False), encoding="utf-8"
    )

    status = IllustrationStudio(tmp_path).status(EDITION_ID)

    assert status.state == "invalid_brief"
    assert any(match in error for error in status.errors)


def test_hash_mismatch_missing_asset_and_invalid_raster_have_distinct_status(
    tmp_path: Path,
):
    studio, edition_dir = _scaffold(tmp_path)
    source = tmp_path / "source.png"
    _write_png(source, (1536, 1024))
    studio.register_asset(EDITION_ID, "tail-one", source)
    target = edition_dir / "art" / "article-tails" / "one.png"

    target.unlink()
    status = studio.status(EDITION_ID)
    assert status.assets[0].asset_status == "missing_asset"

    _write_png(target, (1536, 1024))
    Image.new("RGB", (1536, 1024), "black").save(target)
    status = studio.status(EDITION_ID)
    assert status.assets[0].asset_status == "hash_mismatch"

    record_path = edition_dir / "art" / "illustrations.yaml"
    record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
    record["assets"][0]["asset_sha256"] = hashlib.sha256(
        target.read_bytes()
    ).hexdigest()
    record_path.write_text(
        yaml.safe_dump(record, sort_keys=False), encoding="utf-8"
    )
    Image.new("RGB", (1024, 1024), "black").save(target)
    record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
    record["assets"][0]["asset_sha256"] = hashlib.sha256(
        target.read_bytes()
    ).hexdigest()
    record_path.write_text(
        yaml.safe_dump(record, sort_keys=False), encoding="utf-8"
    )
    status = IllustrationStudio(tmp_path).status(EDITION_ID)
    assert status.assets[0].asset_status == "invalid_raster"


def test_status_rejects_duplicate_bytes_already_committed_to_two_assets(
    tmp_path: Path,
):
    _, edition_dir = _scaffold(tmp_path)
    shared = tmp_path / "shared.png"
    _write_png(shared, (1024, 1400), (21, 42, 63))
    for index in (1, 2):
        target = edition_dir / "art" / f"closing-plate-{index}.png"
        target.write_bytes(shared.read_bytes())

    status = IllustrationStudio(tmp_path).status(EDITION_ID)
    duplicates = [
        asset
        for asset in status.assets
        if asset.id in {"closing-1", "closing-2"}
    ]

    assert status.state == "duplicate_asset"
    assert {asset.asset_status for asset in duplicates} == {
        "duplicate_asset"
    }
    assert all("duplicates committed bytes" in asset.error for asset in duplicates)


def test_stale_session_and_reviewed_or_released_mutations_are_rejected(
    tmp_path: Path,
):
    edition_dir = _project(tmp_path)
    stale = IllustrationStudio(tmp_path)
    stale.status(EDITION_ID)
    (edition_dir / "edition.yaml").write_text(
        (edition_dir / "edition.yaml").read_text(encoding="utf-8") + "# changed\n",
        encoding="utf-8",
    )
    with pytest.raises(IllustrationStudioConflict, match="stale"):
        stale.scaffold(_brief())

    current = IllustrationStudio(tmp_path)
    review = edition_dir / "reviews" / "render.yaml"
    review.parent.mkdir()
    review.write_text("schema_version: 1\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="review records"):
        current.scaffold(_brief())
    review.unlink()

    state_path = tmp_path / "library" / "release-state.yaml"
    state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    state["collecting_editions"] = [
        {
            "id": "other",
            "issue_number": 2,
            "status": "collecting",
            "source_ids": [],
        }
    ]
    state["intake_edition_id"] = "other"
    state["released_editions"] = [
        {
            "id": EDITION_ID,
            "issue_number": 1,
            "status": "released",
            "source_ids": [],
        }
    ]
    state_path.write_text(
        yaml.safe_dump(state, sort_keys=False), encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="collecting edition"):
        IllustrationStudio(tmp_path).scaffold(_brief())


class _ReviewAdapter:
    def __init__(self, output: dict[str, bytes] | None = None) -> None:
        self.output = output or {"contact-sheet.png": b"review"}
        self.seen = None
        self.calls = 0

    def render(self, plan):
        self.calls += 1
        self.seen = plan
        return self.output


def test_review_plan_and_adapter_output_are_deterministic_and_contained(
    tmp_path: Path,
):
    _project(tmp_path)
    adapter = _ReviewAdapter()
    studio = IllustrationStudio(tmp_path, review_adapter=adapter)
    studio.scaffold(_brief())
    _register_all(studio, tmp_path)

    plan = studio.review_plan(EDITION_ID)
    action = studio.create_review_sheet(
        EDITION_ID, expected_revision=plan.revision
    )
    again = studio.create_review_sheet(EDITION_ID)

    assert [asset.id for asset in plan.assets] == [
        "tail-one",
        "closing-1",
        "closing-2",
        "closing-3",
    ]
    assert all(len(asset.asset_sha256) == 64 for asset in plan.assets)
    assert action.changed
    assert not again.changed
    assert action.writes[0].read_bytes() == b"review"

    escaping = IllustrationStudio(
        tmp_path, review_adapter=_ReviewAdapter({"../escape.png": b"bad"})
    )
    with pytest.raises(ValidationError, match="must be relative"):
        escaping.create_review_sheet(EDITION_ID)


def test_review_adapter_artifact_aliases_are_rejected_after_normalization(
    tmp_path: Path,
):
    _project(tmp_path)
    adapter = _ReviewAdapter(
        {"sheet.png": b"one", "./sheet.png": b"two"}
    )
    studio = IllustrationStudio(tmp_path, review_adapter=adapter)
    studio.scaffold(_brief())
    _register_all(studio, tmp_path)

    with pytest.raises(ValidationError, match="same destination"):
        studio.create_review_sheet(EDITION_ID)

    assert not (
        tmp_path
        / "output"
        / EDITION_ID
        / "illustration-review"
        / "sheet.png"
    ).exists()


def test_review_sheet_dry_run_never_invokes_adapter(tmp_path: Path):
    _project(tmp_path)
    adapter = _ReviewAdapter()
    studio = IllustrationStudio(tmp_path, review_adapter=adapter)
    studio.scaffold(_brief())
    _register_all(studio, tmp_path)

    action = studio.create_review_sheet(EDITION_ID, dry_run=True)

    assert action.dry_run
    assert action.changed
    assert adapter.calls == 0
    assert action.writes == (
        tmp_path / "output" / EDITION_ID / "illustration-review",
    )


def test_revision_binds_direction_preset_and_reference_bytes(tmp_path: Path):
    _, edition_dir = _scaffold(tmp_path)
    preset_path = tmp_path / "art-directions" / "direction.yaml"
    reference_path = tmp_path / "art-directions" / "reference.png"
    _write_png(reference_path, (256, 256), (2, 4, 8))
    preset_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "direction": {
                    "name": "Preset direction",
                    "visual_language": "Friendly ink.",
                    "palette": "Warm paper.",
                    "reference_images": [
                        reference_path.relative_to(tmp_path).as_posix()
                    ],
                    "constraints": ["Wordless"],
                    "avoid": ["Logos"],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    plan_path = edition_dir / "art" / "illustrations.yaml"
    record = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    record.pop("direction")
    record["direction_preset"] = preset_path.relative_to(tmp_path).as_posix()
    plan_path.write_text(
        yaml.safe_dump(record, sort_keys=False), encoding="utf-8"
    )
    studio = IllustrationStudio(tmp_path)
    initial = studio.status(EDITION_ID)

    _write_png(reference_path, (256, 256), (3, 6, 9))
    reference_changed = IllustrationStudio(tmp_path).status(EDITION_ID)

    assert reference_changed.revision != initial.revision
    preset = yaml.safe_load(preset_path.read_text(encoding="utf-8"))
    preset["direction"]["palette"] = "Cool paper."
    preset_path.write_text(
        yaml.safe_dump(preset, sort_keys=False), encoding="utf-8"
    )
    preset_changed = IllustrationStudio(tmp_path).status(EDITION_ID)
    assert preset_changed.revision != reference_changed.revision

    source = tmp_path / "source.png"
    _write_png(source, (1536, 1024))
    with pytest.raises(IllustrationStudioConflict, match="stale"):
        studio.register_asset(
            EDITION_ID,
            "tail-one",
            source,
            expected_revision=initial.revision,
        )


def test_prompt_destination_cannot_follow_a_symlink_outside_output(tmp_path: Path):
    studio, _ = _scaffold(tmp_path)
    output = tmp_path / "output"
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    output.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValidationError, match="escapes|symlink"):
        studio.emit_prompt_package(EDITION_ID)


def test_legacy_plan_without_hashes_remains_ready(tmp_path: Path):
    studio, edition_dir = _scaffold(tmp_path)
    _register_all(studio, tmp_path)
    plan_path = edition_dir / "art" / "illustrations.yaml"
    record = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    for row in record["assets"]:
        row.pop("asset_sha256")
    plan_path.write_text(
        yaml.safe_dump(record, sort_keys=False), encoding="utf-8"
    )

    status = IllustrationStudio(tmp_path).status(EDITION_ID)

    assert status.state == "ready"
    assert all(asset.asset_sha256 is None for asset in status.assets)
    edition = IllustrationStudio(tmp_path)._edition_inventory(
        EDITION_ID,
        yaml.safe_load((edition_dir / "edition.yaml").read_text(encoding="utf-8")),
    )
    assert validate_illustration_plan(tmp_path, edition) is not None
