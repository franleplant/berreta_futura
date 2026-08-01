from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from PIL import Image

from magazine.cli import main as cli_main
from magazine.cli import parser
from magazine.compiler import Magazine, _copy_preflight_project
from magazine.cover import CoverArtifact
from magazine.errors import ValidationError


EDITION_ID = "issue-one"
SOURCE_ID = "source-one"


def _write_yaml(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def _project(
    root: Path,
    *,
    languages: tuple[str, ...] = ("en", "es"),
) -> Path:
    configured_languages = ", ".join(f'"{language}"' for language in languages)
    (root / "magazine.toml").write_text(
        "[publication]\n"
        'name = "Integration Magazine"\n'
        'language = "en"\n'
        f"languages = [{configured_languages}]\n"
        "\n"
        "[paths]\n"
        'sources = "library/sources"\n'
        'editions = "editions"\n'
        'release_state = "library/release-state.yaml"\n',
        encoding="utf-8",
    )
    capture_id = hashlib.sha256(SOURCE_ID.encode("utf-8")).hexdigest()
    source_dir = root / "library" / "sources" / SOURCE_ID
    bundle_dir = source_dir / "raw" / capture_id
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
    _write_yaml(
        source_dir / "record.yaml",
        {
            "schema_version": 2,
            "id": SOURCE_ID,
            "title": "Source One",
            "author": "Example Author",
            "author_profile": {
                "note": "Example Author is an engineer at Example Company.",
                "evidence": [
                    {
                        "url": "https://example.com/author",
                        "capture_id": capture_id,
                    }
                ],
            },
            "canonical_url": "https://example.com/source",
            "submitted_url": "https://example.com/source",
            "captured_at": "2026-07-29T12:00:00Z",
            "publication_date": "2026-07-28",
            "kind": "article",
            "status": "captured",
            "raw_captures": [
                {
                    "id": capture_id,
                    "path": f"raw/{capture_id}/manifest.json",
                    "method": "test fixture",
                    "captured_at": "2026-07-29T12:00:00Z",
                    "artifact_count": 1,
                    "byte_count": 2,
                }
            ],
            "provenance": [],
            "rights": {},
            "metadata": {},
            "notes": "",
        },
    )
    (source_dir / "extracted.md").write_text(
        "---\n"
        "schema_version: 1\n"
        f"source_id: {SOURCE_ID}\n"
        f"raw_bundle: {capture_id}\n"
        "extraction_method: test fixture transcription\n"
        "---\n"
        "Substantive source body.\n",
        encoding="utf-8",
    )
    _write_yaml(
        root / "library" / "release-state.yaml",
        {
            "schema_version": 2,
            "intake_edition_id": EDITION_ID,
            "collecting_editions": [
                {
                    "id": EDITION_ID,
                    "issue_number": 1,
                    "status": "collecting",
                    "source_ids": [SOURCE_ID],
                }
            ],
            "released_editions": [],
        },
    )
    edition_dir = root / "editions" / EDITION_ID
    edition_dir.mkdir(parents=True)
    (edition_dir / "editorial.md").write_text(
        "---\n"
        "title: Opening Note\n"
        "byline: The editors\n"
        "label: ORIGINAL EDITORIAL\n"
        "---\n\n"
        "A short note.\n",
        encoding="utf-8",
    )
    _write_yaml(
        edition_dir / "edition.yaml",
        {
            "schema_version": 1,
            "id": EDITION_ID,
            "issue_number": 1,
            "title": "Issue One",
            "publication_date": "2026-07-29",
            "language": "en",
            "sources": [],
            "editorial": f"editions/{EDITION_ID}/editorial.md",
            "cover": {
                "headline": "Issue One",
                "deck": "One source through a controlled workflow",
            },
            "articles": [],
        },
    )
    brief = root / "article-brief.yaml"
    _write_yaml(
        brief,
        {
            "schema_version": 1,
            "edition_id": EDITION_ID,
            "id": "source-one-article",
            "title": "Source One",
            "short_title": "Source One",
            "display_emphasis": "One",
            "opener_variant": "edge_medallion",
            "content_mode": "faithful_edit",
            "source_ids": [SOURCE_ID],
        },
    )
    return brief


def _seed_empty_overlays(root: Path, *languages: str) -> None:
    magazine = Magazine(root)
    brief = root / "article-brief.yaml"
    manifest_path = root / "editions" / EDITION_ID / "edition.yaml"
    original_manifest = manifest_path.read_bytes()
    magazine.stage_article(brief)
    manifest_path.write_bytes(original_manifest)
    article = (
        root
        / "editions"
        / EDITION_ID
        / "articles"
        / "source-one-article.md"
    )
    article.unlink()
    for language in languages:
        overlay_dir = (
            root / "editions" / EDITION_ID / "translations" / language
        )
        overlay_path = overlay_dir / "edition.yaml"
        data = yaml.safe_load(overlay_path.read_text(encoding="utf-8"))
        data["articles"] = []
        overlay_path.write_text(
            yaml.safe_dump(data, sort_keys=False),
            encoding="utf-8",
        )
        translated = overlay_dir / "articles" / "source-one-article.md"
        translated.unlink()
        translated.parent.rmdir()
    article.parent.rmdir()


def _add_second_source(root: Path) -> None:
    first = root / "library" / "sources" / SOURCE_ID
    second = root / "library" / "sources" / "source-two"
    second.mkdir(parents=True)
    record = yaml.safe_load(
        (first / "record.yaml").read_text(encoding="utf-8")
    )
    capture_id = hashlib.sha256(b"source-two").hexdigest()
    record.update(
        {
            "id": "source-two",
            "title": "Source Two",
            "canonical_url": "https://example.com/source-two",
            "submitted_url": "https://example.com/source-two",
        }
    )
    record["raw_captures"][0]["id"] = capture_id
    record["raw_captures"][0]["path"] = f"raw/{capture_id}/manifest.json"
    record["author_profile"]["evidence"][0]["capture_id"] = capture_id
    _write_yaml(second / "record.yaml", record)
    raw_bundle = second / "raw" / capture_id / "manifest.json"
    raw_bundle.parent.mkdir(parents=True)
    raw_bundle.write_text("{}\n", encoding="utf-8")
    (second / "extracted.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "source_id: source-two\n"
        f"raw_bundle: {capture_id}\n"
        "extraction_method: test fixture transcription\n"
        "---\n"
        "A second substantive source body.\n",
        encoding="utf-8",
    )
    state_path = root / "library" / "release-state.yaml"
    state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    state["collecting_editions"][0]["source_ids"].append("source-two")
    _write_yaml(state_path, state)


def test_article_stage_is_one_translation_aware_transaction(tmp_path: Path) -> None:
    brief = _project(tmp_path)
    magazine = Magazine(tmp_path)

    report = magazine.stage_article(brief)

    assert report.changed
    assert report.translations[0]["language"] == "es"
    assert report.translations[0]["changed"]
    overlay = (
        tmp_path
        / "editions"
        / EDITION_ID
        / "translations"
        / "es"
        / "edition.yaml"
    )
    assert overlay.is_file()
    payload = report.to_dict(tmp_path)
    assert payload["created"]
    assert payload["translations"][0]["created"]
    assert any(
        item["pointer"] == "articles[source-one-article].manuscript"
        for item in payload["translations"][0]["placeholders"]
    )


def test_article_stage_restores_the_edition_if_translation_staging_fails(
    tmp_path: Path,
) -> None:
    brief = _project(tmp_path)
    edition_dir = tmp_path / "editions" / EDITION_ID
    before = {
        path.relative_to(edition_dir): path.read_bytes()
        for path in edition_dir.rglob("*")
        if path.is_file()
    }
    before_directories = {
        path.relative_to(edition_dir)
        for path in edition_dir.rglob("*")
        if path.is_dir()
    }

    with patch.object(
        Magazine,
        "stage_translation",
        side_effect=ValidationError("injected translation refusal"),
    ):
        with pytest.raises(ValidationError, match="injected translation refusal"):
            Magazine(tmp_path).stage_article(brief)

    after = {
        path.relative_to(edition_dir): path.read_bytes()
        for path in edition_dir.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert {
        path.relative_to(edition_dir)
        for path in edition_dir.rglob("*")
        if path.is_dir()
    } == before_directories


def test_status_and_run_stop_at_the_first_authorial_checkpoint(
    tmp_path: Path,
) -> None:
    brief = _project(tmp_path)
    magazine = Magazine(tmp_path)
    magazine.stage_article(brief)

    status = magazine.workflow_status(EDITION_ID)
    result = magazine.workflow_run(EDITION_ID)

    assert status.next_checkpoint is not None
    assert status.next_checkpoint.next_action is not None
    assert status.next_checkpoint.next_action.classification in {
        "deterministic",
        "authorial",
    }
    assert result.report.next_checkpoint is not None
    assert result.report.next_checkpoint.next_action is not None
    assert result.report.next_checkpoint.next_action.classification in {
        "authorial",
        "human-review",
    }
    assert all("review" not in action.lower() for action in result.actions)


def test_cli_json_fast_path_and_legacy_commands_remain_available(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    brief = _project(tmp_path)
    assert (
        cli_main(
            [
                "--root",
                str(tmp_path),
                "article",
                "stage",
                str(brief),
            ]
        )
        == 0
    )
    staged = json.loads(capsys.readouterr().out)
    assert staged["article_id"] == "source-one-article"
    assert staged["translations"][0]["language"] == "es"

    assert (
        cli_main(
            [
                "--root",
                str(tmp_path),
                "status",
                EDITION_ID,
                "--json",
            ]
        )
        == 0
    )
    status = json.loads(capsys.readouterr().out)
    assert status["schema_version"] == 1
    assert status["next_checkpoint"]

    assert parser().parse_args(["illustrate", EDITION_ID]).command == "illustrate"
    assert parser().parse_args(["cover-proof", EDITION_ID]).command == "cover-proof"
    assert parser().parse_args(["validate", EDITION_ID]).command == "validate"


def test_cover_and_interior_status_are_public_and_json_serializable(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _project(tmp_path)
    assert (
        cli_main(
            ["--root", str(tmp_path), "cover-art", "status", EDITION_ID]
        )
        == 0
    )
    cover = json.loads(capsys.readouterr().out)
    assert "revision" in cover
    assert cover["rounds"] == []

    assert (
        cli_main(
            ["--root", str(tmp_path), "interior-art", "status", EDITION_ID]
        )
        == 0
    )
    interior = json.loads(capsys.readouterr().out)
    assert interior["state"] == "missing_brief"


def test_dry_run_article_stage_does_not_write_translation_placeholders(
    tmp_path: Path,
) -> None:
    brief = _project(tmp_path)
    report = Magazine(tmp_path).stage_article(brief, dry_run=True)

    assert report.dry_run
    assert report.changed
    assert report.translations[0]["language"] == "es"
    assert report.translations[0]["dry_run"] is True
    assert report.translations[0]["changed"] is True
    assert report.translations[0]["created"]
    assert report.translations[0]["placeholders"]
    assert not (
        tmp_path / "editions" / EDITION_ID / "translations"
    ).exists()
    assert not (
        tmp_path
        / "editions"
        / EDITION_ID
        / "articles"
        / "source-one-article.md"
    ).exists()


def test_rollback_ignores_and_preserves_unrelated_concurrent_overlay_files(
    tmp_path: Path,
) -> None:
    brief = _project(tmp_path, languages=("en", "es", "fr"))
    _seed_empty_overlays(tmp_path, "es", "fr")
    edition_dir = tmp_path / "editions" / EDITION_ID
    manifest = edition_dir / "edition.yaml"
    spanish_manifest = edition_dir / "translations" / "es" / "edition.yaml"
    french_manifest = edition_dir / "translations" / "fr" / "edition.yaml"
    before = {
        manifest: manifest.read_bytes(),
        spanish_manifest: spanish_manifest.read_bytes(),
        french_manifest: french_manifest.read_bytes(),
    }
    original = Magazine.stage_translation
    concurrent = edition_dir / "translations" / "es" / "concurrent.txt"

    def fail_after_spanish(self, edition_id: str, language: str):
        if language == "es":
            return original(self, edition_id, language)
        concurrent.write_text("unrelated concurrent work\n", encoding="utf-8")
        raise ValidationError("injected French staging refusal")

    with patch.object(Magazine, "stage_translation", fail_after_spanish):
        with pytest.raises(
            ValidationError,
            match="injected French staging refusal",
        ):
            Magazine(tmp_path).stage_article(brief)

    assert concurrent.read_text(encoding="utf-8") == "unrelated concurrent work\n"
    assert manifest.read_bytes() == before[manifest]
    assert spanish_manifest.read_bytes() == before[spanish_manifest]
    assert french_manifest.read_bytes() == before[french_manifest]
    assert not (edition_dir / "articles" / "source-one-article.md").exists()
    assert not (
        edition_dir
        / "translations"
        / "es"
        / "articles"
        / "source-one-article.md"
    ).exists()


def test_rollback_preserves_a_concurrently_edited_touched_file_and_reports_it(
    tmp_path: Path,
) -> None:
    brief = _project(tmp_path, languages=("en", "es", "fr"))
    _seed_empty_overlays(tmp_path, "es", "fr")
    edition_dir = tmp_path / "editions" / EDITION_ID
    manifest = edition_dir / "edition.yaml"
    manifest_before = manifest.read_bytes()
    spanish_manifest = edition_dir / "translations" / "es" / "edition.yaml"
    original = Magazine.stage_translation

    def conflict_after_spanish(self, edition_id: str, language: str):
        if language == "es":
            return original(self, edition_id, language)
        spanish_manifest.write_text(
            spanish_manifest.read_text(encoding="utf-8")
            + "# concurrent translator note\n",
            encoding="utf-8",
        )
        raise ValidationError("injected French staging refusal")

    with patch.object(Magazine, "stage_translation", conflict_after_spanish):
        with pytest.raises(ValidationError) as caught:
            Magazine(tmp_path).stage_article(brief)

    message = str(caught.value)
    assert "injected French staging refusal" in message
    assert "translations/es/edition.yaml" in message
    assert spanish_manifest.read_text(encoding="utf-8").endswith(
        "# concurrent translator note\n"
    )
    assert manifest.read_bytes() == manifest_before
    assert not (edition_dir / "articles" / "source-one-article.md").exists()
    assert not (
        edition_dir
        / "translations"
        / "es"
        / "articles"
        / "source-one-article.md"
    ).exists()


def test_malformed_configured_overlay_fails_real_dry_run_and_cli_without_writes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    brief = _project(tmp_path, languages=("en", "es", "fr"))
    _seed_empty_overlays(tmp_path, "es", "fr")
    french = (
        tmp_path
        / "editions"
        / EDITION_ID
        / "translations"
        / "fr"
        / "edition.yaml"
    )
    french_before = french.read_bytes()
    french.write_text("title: [unterminated\n", encoding="utf-8")
    manifest = tmp_path / "editions" / EDITION_ID / "edition.yaml"
    before = manifest.read_bytes()

    with pytest.raises(ValidationError, match="Cannot parse translation overlay"):
        Magazine(tmp_path).stage_article(brief, dry_run=True)
    with pytest.raises(ValidationError, match="Cannot parse translation overlay"):
        Magazine(tmp_path).stage_article(brief)

    assert manifest.read_bytes() == before
    assert not (
        tmp_path
        / "editions"
        / EDITION_ID
        / "articles"
        / "source-one-article.md"
    ).exists()

    code = cli_main(
        [
            "--root",
            str(tmp_path),
            "article",
            "stage",
            str(brief),
            "--dry-run",
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "Cannot parse translation overlay" in captured.err
    assert "Traceback" not in captured.err

    french.write_bytes(french_before)
    Magazine(tmp_path).stage_article(brief)
    french.write_text("title: [unterminated\n", encoding="utf-8")
    code = cli_main(
        ["--root", str(tmp_path), "translate", EDITION_ID, "fr"]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "Cannot parse translation overlay" in captured.err
    assert "Traceback" not in captured.err


def test_cover_proofs_use_public_localized_loading_and_write_one_comparison(
    tmp_path: Path,
) -> None:
    brief = _project(tmp_path)
    magazine = Magazine(tmp_path)
    magazine.stage_article(brief)
    base_manuscript = (
        tmp_path
        / "editions"
        / EDITION_ID
        / "articles"
        / "source-one-article.md"
    )
    translated_manuscript = (
        tmp_path
        / "editions"
        / EDITION_ID
        / "translations"
        / "es"
        / "articles"
        / "source-one-article.md"
    )
    base_manuscript.write_text("Substantive source body.\n", encoding="utf-8")
    translated_manuscript.write_text(
        "Cuerpo sustantivo de la fuente.\n",
        encoding="utf-8",
    )
    magazine.stage_translation(EDITION_ID, "es")
    round_number = magazine.cover_studio_scaffold(
        EDITION_ID,
        editorial_reading="One source becomes one controlled edition.",
    ).round_number
    assert round_number == 1
    supplied: dict[str, Path] = {}
    for index, variant in enumerate(
        ("synthetic", "art_directed", "wildcard"),
        start=1,
    ):
        path = tmp_path / "supplied" / f"{variant}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1000, 1000), (index * 40, 20, 30)).save(path)
        supplied[variant] = path
    magazine.cover_studio_register(EDITION_ID, 1, supplied)

    class FakeCoverCompiler:
        def __init__(self, root: Path):
            self.root = root

        def compile(self, edition, destination: Path) -> CoverArtifact:
            destination.mkdir(parents=True, exist_ok=True)
            svg = destination / "cover.svg"
            pdf = destination / "cover.pdf"
            png = destination / "cover.png"
            proof = destination / "proof.json"
            svg.write_text(f"<svg>{edition.language}</svg>\n", encoding="utf-8")
            pdf.write_bytes(b"%PDF fixture\n")
            with Image.open(edition.cover_art) as art:
                cover = art.convert("RGB")
                cover.thumbnail((300, 426))
                cover.save(png)
            proof.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "language": edition.language,
                        "art_path": edition.cover["art_path"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            return CoverArtifact(
                edition.language,
                svg,
                pdf,
                png,
                proof,
                "a" * 64,
                "b" * 64,
                "c" * 64,
                "not_compared",
            )

    with patch("magazine.compiler.CoverCompiler", FakeCoverCompiler):
        action, comparison = magazine.cover_studio_render_proofs(
            EDITION_ID,
            languages=("en", "es"),
        )

    assert action.changed
    assert len(action.writes) == 24
    assert comparison.is_file()
    assert comparison.name == "full-cover-comparison.png"
    for language in ("en", "es"):
        for variant in ("synthetic", "art_directed", "wildcard"):
            proof = (
                tmp_path
                / "editions"
                / EDITION_ID
                / "art"
                / "cover-rounds"
                / "round-1"
                / "proofs"
                / language
                / variant
                / "proof.json"
            )
            assert json.loads(proof.read_text(encoding="utf-8"))["language"] == language


def test_preflight_copies_only_records_and_requested_extractions_not_raw_bundles(
    tmp_path: Path,
) -> None:
    brief_path = _project(tmp_path)
    _add_second_source(tmp_path)
    sources = tmp_path / "library" / "sources"
    sentinel = (
        sources
        / SOURCE_ID
        / "raw"
        / ("f" * 64)
        / "large-browser-export.bin"
    )
    sentinel.parent.mkdir(parents=True)
    sentinel.write_bytes(b"x" * (1024 * 1024))

    sandbox = tmp_path / "bounded-preflight"
    sandbox.mkdir()
    magazine = Magazine(tmp_path)
    _copy_preflight_project(
        magazine,
        sandbox,
        edition_id=EDITION_ID,
        source_ids=(SOURCE_ID, "source-two"),
    )

    copied_sources = sandbox / "library" / "sources"
    copied = sorted(
        path.relative_to(copied_sources).as_posix()
        for path in copied_sources.rglob("*")
        if path.is_file()
    )
    assert copied == [
        "source-one/extracted.md",
        "source-one/record.yaml",
        "source-two/extracted.md",
        "source-two/record.yaml",
    ]
    assert not any(path.name == "raw" for path in copied_sources.rglob("*"))
    assert len(copied) == 4

    single = magazine.stage_article(brief_path, dry_run=True)
    assert single.changed
    brief = yaml.safe_load(brief_path.read_text(encoding="utf-8"))
    brief["source_ids"] = [SOURCE_ID, "source-two"]
    _write_yaml(brief_path, brief)
    multiple = magazine.stage_article(brief_path, dry_run=True)
    assert multiple.changed
