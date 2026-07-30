from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest
import yaml

from magazine.cli import parser
from magazine.errors import ValidationError
from magazine.illustration import (
    illustration_prompt,
    load_illustration_plan,
    validate_illustration_plan,
    write_illustration_package,
)


def _fixture(tmp_path: Path):
    art = tmp_path / "editions" / "issue" / "art"
    tails = art / "article-tails"
    tails.mkdir(parents=True)
    tail = tails / "article.png"
    Image.new("RGB", (1536, 1024), "white").save(tail)
    plates = []
    for index in range(1, 4):
        path = art / f"plate-{index}.png"
        Image.new("RGB", (1024, 1400), "white").save(path)
        plates.append(SimpleNamespace(title=f"Plate {index}", art_path=path))
    plan_path = art / "illustrations.yaml"
    plan_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "direction": {
                    "name": "Old futures",
                    "visual_language": "Chunky ink and economical screentone.",
                    "palette": "Open vintage spot colors over warm paper.",
                    "constraints": ["Wordless", "Strong silhouettes"],
                    "avoid": ["Franchise characters", "Glossy anime rendering"],
                },
                "assets": [
                    {
                        "id": "tail-article",
                        "role": "article_tail",
                        "article_id": "article",
                        "art_path": tail.relative_to(tmp_path).as_posix(),
                        "subject": "A mechanic helps a machine recover.",
                        "composition": "Action stays in the central horizontal third.",
                        "alt_text": "A mechanic helping a tangled machine.",
                        "credit": "Illustration by the editors with Codex image generation.",
                    },
                    *[
                        {
                            "id": f"plate-{index}",
                            "role": "closing_plate",
                            "plate_index": index,
                            "art_path": path.relative_to(tmp_path).as_posix(),
                            "subject": f"Closing scene {index}.",
                            "composition": "A portrait scene that also works alone.",
                            "alt_text": f"Closing scene {index}.",
                            "credit": "Illustration by the editors with Codex image generation.",
                        }
                        for index, path in enumerate(
                            [plate.art_path for plate in plates], start=1
                        )
                    ],
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    article = SimpleNamespace(id="article", tail_art=tail)
    edition = SimpleNamespace(
        id="issue",
        raw={"art_direction_path": plan_path.relative_to(tmp_path).as_posix()},
        articles=(article,),
        closing_plates=tuple(plates),
    )
    return edition, plan_path


def test_plan_is_the_exact_inventory_the_renderer_consumes(tmp_path: Path):
    edition, plan_path = _fixture(tmp_path)

    plan = validate_illustration_plan(tmp_path, edition)

    assert plan is not None
    assert plan.path == plan_path
    assert [asset.id for asset in plan.assets] == [
        "tail-article",
        "plate-1",
        "plate-2",
        "plate-3",
    ]


def test_prompt_package_binds_prompts_and_selected_pixels(tmp_path: Path):
    edition, _ = _fixture(tmp_path)
    destination = write_illustration_package(
        tmp_path, tmp_path / "output", edition
    )

    payload = json.loads(
        (destination / "illustrations.json").read_text(encoding="utf-8")
    )
    assert payload["edition_id"] == "issue"
    assert len(payload["assets"]) == 4
    assert len(payload["assets"][0]["prompt_sha256"]) == 64
    assert len(payload["assets"][0]["image_sha256"]) == 64
    prompt = (destination / "tail-article.txt").read_text(encoding="utf-8")
    assert "Open vintage spot colors" in prompt
    assert "central horizontal third" in prompt
    assert "Franchise characters" in prompt


def test_plan_can_reuse_a_hash_bound_direction_preset(tmp_path: Path):
    edition, plan_path = _fixture(tmp_path)
    preset_path = tmp_path / "art-directions" / "playful-science-vignettes.yaml"
    preset_path.parent.mkdir()
    reference_path = preset_path.parent / "reference-square.png"
    Image.new("RGB", (1024, 1024), "white").save(reference_path)
    preset_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "direction": {
                    "name": "Playful Science Vignettes",
                    "visual_language": "One friendly manga vignette with simple ink.",
                    "palette": "Relaxed spot colors over warm cream paper.",
                    "reference_images": [
                        reference_path.relative_to(tmp_path).as_posix()
                    ],
                    "constraints": ["One self-contained scene", "Original characters"],
                    "avoid": ["Franchise characters", "Multi-panel pages"],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    plan_data = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    plan_data.pop("direction")
    plan_data["direction_preset"] = preset_path.relative_to(tmp_path).as_posix()
    plan_path.write_text(
        yaml.safe_dump(plan_data, sort_keys=False),
        encoding="utf-8",
    )

    plan = load_illustration_plan(tmp_path, edition)
    destination = write_illustration_package(
        tmp_path, tmp_path / "output", edition
    )
    payload = json.loads(
        (destination / "illustrations.json").read_text(encoding="utf-8")
    )

    assert plan is not None
    assert plan.direction.name == "Playful Science Vignettes"
    assert plan.direction_path == preset_path
    assert plan.direction.reference_paths == (reference_path,)
    assert payload["direction_preset"]["path"] == (
        "art-directions/playful-science-vignettes.yaml"
    )
    assert len(payload["direction_preset"]["sha256"]) == 64
    assert payload["reference_images"][0]["path"] == (
        "art-directions/reference-square.png"
    )
    assert len(payload["reference_images"][0]["sha256"]) == 64
    assert "One friendly manga vignette" in (
        destination / "tail-article.txt"
    ).read_text(encoding="utf-8")
    assert "art-directions/reference-square.png" in (
        destination / "tail-article.txt"
    ).read_text(encoding="utf-8")


def test_plan_cannot_mix_inline_direction_and_preset(tmp_path: Path):
    edition, plan_path = _fixture(tmp_path)
    plan_data = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    plan_data["direction_preset"] = "art-directions/default.yaml"
    plan_path.write_text(
        yaml.safe_dump(plan_data, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="not both"):
        load_illustration_plan(tmp_path, edition)


def test_a_plan_cannot_point_somewhere_other_than_the_manifest(tmp_path: Path):
    edition, _ = _fixture(tmp_path)
    wrong = tmp_path / "editions" / "issue" / "art" / "wrong.png"
    Image.new("RGB", (1536, 1024), "white").save(wrong)
    edition.articles[0].tail_art = wrong

    with pytest.raises(ValidationError, match="does not match tail_art_path"):
        validate_illustration_plan(tmp_path, edition)


def test_raster_shape_and_resolution_are_part_of_the_plan_contract(tmp_path: Path):
    edition, _ = _fixture(tmp_path)
    tail = edition.articles[0].tail_art
    Image.new("RGB", (1024, 1024), "white").save(tail)

    with pytest.raises(ValidationError, match="requires at least 1536x1024"):
        validate_illustration_plan(tmp_path, edition)


def test_article_opener_is_a_distinct_landscape_role_bound_to_manifest_copy(
    tmp_path: Path,
):
    edition, plan_path = _fixture(tmp_path)
    opener_path = (
        tmp_path
        / "editions"
        / "issue"
        / "art"
        / "article-openers"
        / "article.png"
    )
    opener_path.parent.mkdir()
    Image.new("RGB", (1536, 1024), "white").save(opener_path)
    edition.articles[0].opener_art = SimpleNamespace(
        path=opener_path,
        alt_text="A boy and robot inspect a useful system.",
        credit="Original illustration by the editors.",
    )
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    plan["assets"].insert(
        0,
        {
            "id": "opener-article",
            "role": "article_opener",
            "article_id": "article",
            "art_path": opener_path.relative_to(tmp_path).as_posix(),
            "subject": "A boy and robot inspect a useful system.",
            "composition": "A wide central scene for the article opener.",
            "alt_text": "A boy and robot inspect a useful system.",
            "credit": "Original illustration by the editors.",
        },
    )
    plan_path.write_text(yaml.safe_dump(plan, sort_keys=False), encoding="utf-8")

    loaded = validate_illustration_plan(tmp_path, edition)

    assert loaded is not None
    assert loaded.assets[0].role == "article_opener"
    assert "348pt by 203pt panel" in illustration_prompt(
        loaded, loaded.assets[0]
    )

    loaded.assets[0].art_path.unlink()
    Image.new("RGB", (1024, 1536), "white").save(opener_path)
    with pytest.raises(ValidationError, match="requires at least 1536x1024"):
        validate_illustration_plan(tmp_path, edition)


def test_absent_plan_is_ordinary_for_historical_editions(tmp_path: Path):
    edition = SimpleNamespace(raw={}, articles=(), closing_plates=())
    assert load_illustration_plan(tmp_path, edition) is None


def test_cli_exposes_the_author_time_illustration_command():
    args = parser().parse_args(["illustrate", "003-unreleased"])
    assert args.command == "illustrate"
    assert args.edition_id == "003-unreleased"
