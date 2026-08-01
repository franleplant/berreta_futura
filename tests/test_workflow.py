from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import yaml

from magazine.workflow import (
    AdvanceResult,
    _build_input_drift,
    Checkpoint,
    DefaultWorkflowAdapter,
    _hash_path_bytes,
    _probe_cache_key,
    ProbeResult,
    Workflow,
    _WORKFLOW_CACHE_SCHEMA,
)
from magazine.translate_stage import stage_translation


EDITION_ID = "issue-001"
SOURCE_ID = "source-one"


class GuardAdapter:
    """A probe adapter that proves blocked early checkpoints stay cheap."""

    def fit(self, root: Path, edition_id: str) -> ProbeResult:
        raise AssertionError("fit must not run before author-time checkpoints pass")

    def validate(self, root: Path, edition_id: str) -> ProbeResult:
        raise AssertionError("validation must not run before author-time checkpoints pass")

    def advance(
        self, root: Path, edition_id: str, checkpoint: Checkpoint
    ) -> tuple[str, ...]:
        raise AssertionError("this adapter does not advance")


class BuildAdapter:
    def __init__(self):
        self.advanced: list[str] = []

    def fit(self, root: Path, edition_id: str) -> ProbeResult:
        return ProbeResult(
            True,
            "Fits.",
            {
                "ok": True,
                "languages": {
                    "en": {
                        "articles": [{"id": "article", "pages": 1, "cap": 7}],
                        "editorial": {"pages": 1, "cap": 1},
                    }
                },
            },
        )

    def validate(self, root: Path, edition_id: str) -> ProbeResult:
        return ProbeResult(True, "Valid.", {"errors": []})

    def advance(
        self, root: Path, edition_id: str, checkpoint: Checkpoint
    ) -> tuple[str, ...]:
        assert checkpoint.id == "build"
        self.advanced.append(checkpoint.id)
        _write_build(root)
        return ("Built the fixture.",)


class ReleasedSpyAdapter(BuildAdapter):
    def advance(
        self, root: Path, edition_id: str, checkpoint: Checkpoint
    ) -> tuple[str, ...]:
        self.advanced.append(checkpoint.id)
        return ("This must never run for a released edition.",)


class CountingBuildAdapter(BuildAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.fit_calls = 0
        self.validate_calls = 0

    def fit(self, root: Path, edition_id: str) -> ProbeResult:
        self.fit_calls += 1
        return super().fit(root, edition_id)

    def validate(self, root: Path, edition_id: str) -> ProbeResult:
        self.validate_calls += 1
        return super().validate(root, edition_id)


def _cache_path(root: Path) -> Path:
    return root / "output" / ".build" / "workflow-cache" / f"{EDITION_ID}.json"


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _file_entry(root: Path, path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _add_source_record(root: Path, source_id: str) -> None:
    _write_yaml(
        root / "library" / "sources" / source_id / "record.yaml",
        {
            "schema_version": 1,
            "id": source_id,
            "title": source_id,
            "author": "Author",
            "canonical_url": f"https://example.com/{source_id}",
            "submitted_url": f"https://example.com/{source_id}",
            "captured_at": "2026-07-29T12:00:00Z",
            "publication_date": None,
            "kind": "article",
            "status": "captured",
            "content_hash": None,
            "raw_captures": [],
            "provenance": [],
            "rights": {},
            "metadata": {},
            "notes": "",
        },
    )


def _make_project(
    root: Path,
    *,
    extraction: bool,
    complete_art: bool = False,
) -> None:
    (root / "magazine.toml").write_text(
        '[publication]\nname = "Workflow Test"\nlanguage = "en"\nlanguages = ["en"]\n',
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
    source_dir = root / "library" / "sources" / SOURCE_ID
    _write_yaml(
        source_dir / "record.yaml",
        {
            "schema_version": 1,
            "id": SOURCE_ID,
            "title": "Source",
            "author": "Author",
            "canonical_url": "https://example.com/source",
            "submitted_url": "https://example.com/source",
            "captured_at": "2026-07-29T12:00:00Z",
            "publication_date": None,
            "kind": "article",
            "status": "captured",
            "content_hash": None,
            "raw_captures": [],
            "provenance": [],
            "rights": {},
            "metadata": {},
            "notes": "",
        },
    )
    body = "Source evidence.\n"
    body_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if extraction:
        raw_bundle = "a" * 64
        _write_yaml(source_dir / "raw" / raw_bundle / "manifest.json", {})
        (source_dir / "extracted.md").write_text(
            "---\n"
            "schema_version: 1\n"
            f"source_id: {SOURCE_ID}\n"
            f"raw_bundle: {raw_bundle}\n"
            "extraction_method: test transcription\n"
            "---\n"
            + body,
            encoding="utf-8",
        )

    edition_dir = root / "editions" / EDITION_ID
    (edition_dir / "articles").mkdir(parents=True)
    (edition_dir / "articles" / "article.md").write_text(
        "Source evidence.",
        encoding="utf-8",
    )
    (edition_dir / "editorial.md").write_text(
        "---\n"
        "title: Opening Note\n"
        "byline: The editors\n"
        "label: ORIGINAL EDITORIAL\n"
        "---\n\n"
        "A short editorial.",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "id": EDITION_ID,
        "issue_number": 1,
        "title": "A Workflow Issue",
        "publication_date": "2026-07-29",
        "language": "en",
        "sources": [SOURCE_ID],
        "editorial": f"editions/{EDITION_ID}/editorial.md",
        "cover": {
            "headline": "A Workflow Issue",
            "deck": "One source through one controlled workflow",
        },
        "articles": [
            {
                "id": "article",
                "title": "Source Evidence",
                "short_title": "Source Evidence",
                "opener_variant": "edge_medallion",
                "author": "Author",
                "source_ids": [SOURCE_ID],
                # The article row is the only place a source pin lives now;
                # the extraction it pins is written above only when the
                # fixture asks for one, so an unextracted source still leaves
                # the evidence checkpoint with a pin to complain about.
                "source_body_sha256": body_sha,
                "manuscript": f"editions/{EDITION_ID}/articles/article.md",
            }
        ],
    }
    if complete_art:
        _add_complete_art(root, manifest)
    _write_yaml(edition_dir / "edition.yaml", manifest)


def _add_complete_art(root: Path, manifest: dict) -> None:
    edition_dir = root / "editions" / EDITION_ID
    variants = {}
    selected_path = None
    for index, variant in enumerate(
        ("synthetic", "art_directed", "wildcard"),
        start=1,
    ):
        relative = f"art/cover-candidate-{variant}.png"
        path = edition_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1000, 1000), (index * 60, 20, 30)).save(path)
        variants[variant] = {
            "art_path": relative,
            "asset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "generation_method": "imagegen",
            "direction": f"Distinct {variant} direction.",
        }
        if variant == "wildcard":
            selected_path = relative
    _write_yaml(
        edition_dir / "art" / "cover-candidates.yaml",
        {
            "schema_version": 2,
            "round": 3,
            "selection_status": "selected",
            "editorial_reading": "One controlled source becomes a finished edition.",
            "variants": variants,
        },
    )
    manifest["cover"]["art_path"] = selected_path

    tail = edition_dir / "art" / "article-tail.png"
    Image.new("RGB", (1536, 1024), (30, 40, 50)).save(tail)
    manifest["articles"][0]["tail_art_path"] = (
        f"editions/{EDITION_ID}/art/article-tail.png"
    )
    manifest["art_direction_path"] = (
        f"editions/{EDITION_ID}/art/illustrations.yaml"
    )
    _write_yaml(
        edition_dir / "art" / "illustrations.yaml",
        {
            "schema_version": 1,
            "direction": {
                "name": "Measured diagrams",
                "visual_language": "Simple editorial shapes.",
                "palette": "Black, cream, and orange.",
                "constraints": ["No text"],
                "avoid": ["Decoration"],
            },
            "assets": [
                {
                    "id": "article-tail",
                    "role": "article_tail",
                    "article_id": "article",
                    "art_path": f"editions/{EDITION_ID}/art/article-tail.png",
                    "subject": "Evidence moving through gates.",
                    "composition": "A wide centered sequence.",
                    "alt_text": "Evidence moves through three gates.",
                    "credit": "Original illustration by the editors.",
                }
            ],
        },
    )


def _add_article_opener(root: Path) -> None:
    edition_dir = root / "editions" / EDITION_ID
    opener = edition_dir / "art" / "article-opener.png"
    Image.new("RGB", (1600, 900), (70, 110, 150)).save(opener)

    manifest_path = edition_dir / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["format"] = {
        "article_opener": "illustrated_paper_spots_v1",
    }
    manifest["articles"][0]["author_note"] = "Author writes about evidence."
    manifest["articles"][0]["opener_art"] = {
        "path": f"editions/{EDITION_ID}/art/article-opener.png",
        "alt_text": "A boy and robot inspect the evidence.",
        "credit": "Original illustration by the editors.",
    }
    _write_yaml(manifest_path, manifest)

    plan_path = edition_dir / "art" / "illustrations.yaml"
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    plan["assets"].append(
        {
            "id": "article-opener",
            "role": "article_opener",
            "article_id": "article",
            "art_path": f"editions/{EDITION_ID}/art/article-opener.png",
            "subject": "A boy and robot inspect the evidence.",
            "composition": "A wide workshop scene.",
            "alt_text": "A boy and robot inspect the evidence.",
            "credit": "Original illustration by the editors.",
        }
    )
    _write_yaml(plan_path, plan)


def _write_build(root: Path) -> None:
    package = root / "output" / EDITION_ID
    (package / "home").mkdir(parents=True, exist_ok=True)
    (package / "reader.pdf").write_bytes(b"reader")
    (package / "home" / "booklet-a4.pdf").write_bytes(b"booklet")
    manifest = yaml.safe_load(
        (root / "editions" / EDITION_ID / "edition.yaml").read_text(encoding="utf-8")
    )
    manuscript = root / "editions" / EDITION_ID / "articles" / "article.md"
    editorial = root / "editions" / EDITION_ID / "editorial.md"
    illustration_plan = (
        root / "editions" / EDITION_ID / "art" / "illustrations.yaml"
    )
    cover_art = (
        root / "editions" / EDITION_ID / manifest["cover"]["art_path"]
    )
    tail_art = root / manifest["articles"][0]["tail_art_path"]
    opener_art_value = manifest["articles"][0].get("opener_art")
    opener_art = (
        root / opener_art_value["path"]
        if isinstance(opener_art_value, dict)
        else None
    )
    source_record = (
        root / "library" / "sources" / SOURCE_ID / "record.yaml"
    )
    (package / "edition-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "publication": {
                    "language": "en",
                },
                "edition": manifest,
                "inputs": {
                    "illustration_plan": _file_entry(root, illustration_plan),
                    "illustration_direction": None,
                    "illustration_references": [],
                    "cover_faces": {
                        "front": {
                            "input_sha256": "a" * 64,
                            "pdf_sha256": "b" * 64,
                            "png_sha256": "c" * 64,
                        },
                        "back": {
                            "input_sha256": "d" * 64,
                            "pdf_sha256": "e" * 64,
                            "png_sha256": "f" * 64,
                        },
                    },
                    "editorial": _file_entry(root, editorial),
                    "cover_art": _file_entry(root, cover_art),
                    "translation_manifest": None,
                    "sections": [],
                    "articles": [
                        {
                            "id": "article",
                            "manuscript": _file_entry(root, manuscript),
                            "opener_art": (
                                _file_entry(root, opener_art)
                                if opener_art is not None
                                else None
                            ),
                            "tail_art": _file_entry(root, tail_art),
                        }
                    ],
                    "closing_plates": [],
                    "sources": [
                        {
                            "id": SOURCE_ID,
                            "record": _file_entry(root, source_record),
                        }
                    ],
                },
                "layout": {
                    "article_pages": {"article": 1},
                    "maximum_article_pages": 7,
                    "editorial_pages": 1,
                    "maximum_editorial_pages": 1,
                },
            }
        ),
        encoding="utf-8",
    )
    (package / "render-critic.json").write_text(
        json.dumps({"schema_version": 1, "result": "pass"}),
        encoding="utf-8",
    )
    (package / "preflight.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "result": "home_ready_studio_blocked",
            }
        ),
        encoding="utf-8",
    )


def _write_reviews(root: Path) -> None:
    edition_dir = root / "editions" / EDITION_ID
    source_dir = root / "library" / "sources" / SOURCE_ID
    manuscript = edition_dir / "articles" / "article.md"
    extraction = source_dir / "extracted.md"
    extraction_text = extraction.read_text(encoding="utf-8")
    body = extraction_text.partition("\n---\n")[2]
    _write_yaml(
        edition_dir / "reviews" / "evidence.yaml",
        {
            "schema_version": 2,
            "edition_id": EDITION_ID,
            "reviewer": "Evidence reviewer",
            "reviewed_at": "2026-07-29T12:00:00+00:00",
            "result": "approved",
            "findings": [],
            "articles": {
                "article": {
                    "reviewed_at": "2026-07-29T12:00:00+00:00",
                    "manuscript_sha256": hashlib.sha256(
                        manuscript.read_bytes()
                    ).hexdigest(),
                    "source_extractions": {
                        SOURCE_ID: {
                            "body_sha256": hashlib.sha256(
                                body.encode("utf-8")
                            ).hexdigest(),
                            "file_sha256": hashlib.sha256(
                                extraction.read_bytes()
                            ).hexdigest(),
                        }
                    },
                }
            },
        },
    )
    package = root / "output" / EDITION_ID
    _write_yaml(
        edition_dir / "reviews" / "render.yaml",
        {
            "schema_version": 1,
            "edition_id": EDITION_ID,
            "reviewer": "Render reviewer",
            "reviewed_at": "2026-07-29T13:00:00+00:00",
            "result": "approved",
            "findings": [],
            "languages": {
                "en": {
                    "reader_sha256": hashlib.sha256(
                        (package / "reader.pdf").read_bytes()
                    ).hexdigest(),
                    "booklet_sha256": hashlib.sha256(
                        (package / "home" / "booklet-a4.pdf").read_bytes()
                    ).hexdigest(),
                }
            },
        },
    )


def test_status_reports_the_whole_ordered_workflow_and_precise_blockers(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=False)

    report = Workflow(tmp_path, adapter=GuardAdapter()).status(EDITION_ID)

    assert report.lifecycle == "collecting"
    assert [checkpoint.id for checkpoint in report.checkpoints] == [
        "assignment",
        "coverage",
        "evidence",
        # Drafting, before everything that reads a manuscript.
        "production",
        "translations",
        "cover",
        "illustrations",
        "fit",
        "validation",
        "build",
        # The editorial bench sits together after the build: the evidence
        # audit, then the three prose judges, then the visual decision.
        "evidence_review",
        "line_review",
        "edition_review",
        "learning_review",
        "render_review",
        "release",
    ]
    assert report.next_checkpoint.id == "evidence"
    evidence = report.checkpoint("evidence")
    assert evidence.next_action.classification == "authorial"
    assert evidence.details["missing_or_invalid_extractions"] == [SOURCE_ID]
    assert evidence.details["unpinned_or_invalid_articles"] == ["article"]
    assert all(
        checkpoint.next_action is not None
        and checkpoint.next_action.classification
        in {"deterministic", "authorial", "human-review"}
        for checkpoint in report.checkpoints
        if checkpoint.status == "blocked"
    )
    payload = report.to_dict()
    assert payload["schema_version"] == 1
    assert payload["next_checkpoint"] == "evidence"
    assert json.loads(report.to_json()) == payload


def test_evidence_reads_raw_article_rows_so_an_unloadable_manifest_still_reports(
    tmp_path: Path,
):
    """Per-article pin status must survive a manifest that will not load.

    The pins live in edition.yaml itself, so it is tempting to read them off
    the loaded Edition. The checkpoint reads the raw rows instead: an author
    whose manifest is broken for an unrelated reason still needs to see which
    articles are pinned and which are not, rather than one opaque load error
    standing in for every article at once.
    """

    _make_project(tmp_path, extraction=True)
    manifest_path = tmp_path / "editions" / EDITION_ID / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["articles"][0]["manuscript"] = (
        f"editions/{EDITION_ID}/articles/does-not-exist.md"
    )
    _write_yaml(manifest_path, manifest)

    report = Workflow(tmp_path, adapter=GuardAdapter()).status(EDITION_ID)

    evidence = report.checkpoint("evidence")
    assert evidence.status == "complete"
    assert evidence.summary == "Source extractions and article source pins are complete."
    assert evidence.details["unpinned_or_invalid_articles"] == []
    assert evidence.details["source_pins"] == {
        "article": {
            "path": f"editions/{EDITION_ID}/edition.yaml",
            "status": "complete",
            "source_ids": [SOURCE_ID],
        }
    }


def test_evidence_reports_the_offending_article_for_a_pin_that_does_not_match(
    tmp_path: Path,
):
    """A pin that no longer matches its extraction is that article's problem.

    The whole point of moving the pin into the article row is that it names
    the source it verifies, so a stale pin must be reported against the
    article and the source id, not as an edition-wide failure.
    """

    _make_project(tmp_path, extraction=True)
    manifest_path = tmp_path / "editions" / EDITION_ID / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["articles"][0]["source_body_sha256"] = "0" * 64
    _write_yaml(manifest_path, manifest)

    report = Workflow(tmp_path, adapter=GuardAdapter()).status(EDITION_ID)

    evidence = report.checkpoint("evidence")
    assert evidence.status == "blocked"
    assert evidence.summary == "0 extraction(s) and 1 article source pin(s) need work."
    assert evidence.next_action.classification == "authorial"
    assert evidence.details["unpinned_or_invalid_articles"] == ["article"]
    row = evidence.details["source_pins"]["article"]
    assert row["status"] == "invalid"
    assert len(row["errors"]) == 1
    assert row["errors"][0].startswith(
        f"editions/{EDITION_ID}/edition.yaml: article article: "
        f"source_body_sha256 for {SOURCE_ID} is {'0' * 64}"
    )
    assert evidence.details["errors"] == row["errors"]


def test_assignment_advances_only_target_manifest_sources_and_preserves_other_queues(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True)
    _add_source_record(tmp_path, "source-other")
    _add_source_record(tmp_path, "source-orphan")
    _write_yaml(
        tmp_path / "library" / "release-state.yaml",
        {
            "schema_version": 2,
            "intake_edition_id": EDITION_ID,
            "collecting_editions": [
                {
                    "id": EDITION_ID,
                    "issue_number": 1,
                    "status": "collecting",
                    "source_ids": [],
                },
                {
                    "id": "issue-other",
                    "issue_number": 2,
                    "status": "collecting",
                    "source_ids": ["source-other"],
                },
            ],
            "released_editions": [],
        },
    )
    checkpoint = Workflow(tmp_path, adapter=GuardAdapter()).status(
        EDITION_ID
    ).next_checkpoint

    with patch("magazine.workflow.verify_snapshots"):
        DefaultWorkflowAdapter().advance(tmp_path, EDITION_ID, checkpoint)

    state = yaml.safe_load(
        (tmp_path / "library" / "release-state.yaml").read_text(encoding="utf-8")
    )
    queues = {
        row["id"]: row["source_ids"] for row in state["collecting_editions"]
    }
    assert queues == {
        EDITION_ID: [SOURCE_ID],
        "issue-other": ["source-other"],
    }
    assert "source-orphan" not in {
        source_id for source_ids in queues.values() for source_id in source_ids
    }


def test_malformed_release_ledger_is_authorial_and_run_does_not_claim_a_repair(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True)
    _write_yaml(
        tmp_path / "library" / "release-state.yaml",
        {
            "schema_version": 2,
            "intake_edition_id": EDITION_ID,
            "collecting_editions": [],
            "released_editions": [],
        },
    )

    report = Workflow(tmp_path).status(EDITION_ID)
    assignment = report.checkpoint("assignment")
    result = Workflow(tmp_path).run(EDITION_ID)

    assert assignment.status == "blocked"
    assert assignment.next_action.classification == "authorial"
    assert assignment.next_action.action is None
    assert not result.changed
    assert result.report.to_dict() == report.to_dict()


def test_status_never_iterates_a_scalar_article_source_ids_value(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True)
    manifest_path = tmp_path / "editions" / EDITION_ID / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["articles"][0]["source_ids"] = 7
    _write_yaml(manifest_path, manifest)

    report = Workflow(tmp_path, adapter=GuardAdapter()).status(EDITION_ID)

    coverage = report.checkpoint("coverage")
    assert coverage.status == "blocked"
    assert coverage.details["article_source_ids"] == {}
    assert coverage.details["uncovered_source_ids"] == [SOURCE_ID]


def test_released_schema_one_skips_modern_cover_and_illustration_requirements(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True, complete_art=True)
    manifest_path = tmp_path / "editions" / EDITION_ID / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 1
    manifest["art_direction_path"] = "editions/issue-001/art/missing-plan.yaml"
    _write_yaml(manifest_path, manifest)
    _write_yaml(
        tmp_path / "editions" / EDITION_ID / "art" / "cover-candidates.yaml",
        {"schema_version": 999, "variants": "malformed"},
    )
    _write_yaml(
        tmp_path / "library" / "release-state.yaml",
        {
            "schema_version": 2,
            "intake_edition_id": "issue-next",
            "collecting_editions": [
                {
                    "id": "issue-next",
                    "issue_number": 2,
                    "status": "collecting",
                    "source_ids": [],
                }
            ],
            "released_editions": [
                {
                    "id": EDITION_ID,
                    "issue_number": 1,
                    "source_ids": [SOURCE_ID],
                }
            ],
        },
    )

    report = Workflow(tmp_path, adapter=BuildAdapter()).status(EDITION_ID)

    assert report.lifecycle == "released"
    assert report.checkpoint("cover").status == "complete"
    assert report.checkpoint("illustrations").status == "complete"
    assert report.checkpoint("build").status == "blocked"


def test_run_is_strictly_read_only_for_a_released_schema_one_edition(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True)
    manifest_path = tmp_path / "editions" / EDITION_ID / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 1
    _write_yaml(manifest_path, manifest)
    _write_yaml(
        tmp_path / "library" / "release-state.yaml",
        {
            "schema_version": 2,
            "intake_edition_id": "issue-next",
            "collecting_editions": [
                {
                    "id": "issue-next",
                    "issue_number": 2,
                    "status": "collecting",
                    "source_ids": [],
                }
            ],
            "released_editions": [
                {
                    "id": EDITION_ID,
                    "issue_number": 1,
                    "source_ids": [SOURCE_ID],
                }
            ],
        },
    )
    adapter = ReleasedSpyAdapter()

    result = Workflow(tmp_path, adapter=adapter).run(EDITION_ID)

    assert result.report.lifecycle == "released"
    assert result.report.next_checkpoint.id == "build"
    assert result.report.next_checkpoint.next_action.action == "build"
    assert not result.changed
    assert result.actions == ()
    assert adapter.advanced == []


def test_run_scaffolds_and_hydrates_cover_then_stops_before_art_work(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True)
    workflow = Workflow(tmp_path, adapter=GuardAdapter())

    initial = workflow.status(EDITION_ID)
    assert initial.next_checkpoint.id == "cover"
    assert initial.next_checkpoint.next_action.classification == "deterministic"

    result = Workflow(tmp_path).run(EDITION_ID)

    assert isinstance(result, AdvanceResult)
    assert result.changed
    assert result.report.next_checkpoint.id == "cover"
    assert result.report.next_checkpoint.next_action.classification == "authorial"
    record_path = (
        tmp_path / "editions" / EDITION_ID / "art" / "cover-candidates.yaml"
    )
    record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
    assert not record["editorial_reading"].startswith("TODO:")
    assert set(record["variants"]) == {"synthetic", "art_directed", "wildcard"}

    repeated = Workflow(tmp_path).run(EDITION_ID)
    assert not repeated.changed
    assert repeated.report.to_dict() == result.report.to_dict()


def test_run_does_not_refresh_stale_translation_pins_before_retranslation(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True)
    (tmp_path / "magazine.toml").write_text(
        '[publication]\n'
        'name = "Workflow Test"\n'
        'language = "en"\n'
        'languages = ["en", "es"]\n',
        encoding="utf-8",
    )
    overlay_dir = (
        tmp_path / "editions" / EDITION_ID / "translations" / "es"
    )
    (overlay_dir / "articles").mkdir(parents=True)
    (overlay_dir / "articles" / "article.md").write_text(
        "Pruebas de la fuente.",
        encoding="utf-8",
    )
    (overlay_dir / "editorial.md").write_text(
        "---\n"
        "title: Nota inicial\n"
        "byline: La redacción\n"
        "label: EDITORIAL ORIGINAL\n"
        "---\n\n"
        "Un editorial breve.",
        encoding="utf-8",
    )
    _write_yaml(
        overlay_dir / "edition.yaml",
        {
            "schema_version": 1,
            "language": "es",
            "source_language": "en",
            "base_copy_sha256": "0" * 64,
            "title": "Un número de flujo",
            "cover": {
                "headline": "Un número de flujo",
                "deck": "Una fuente pasa por un flujo controlado",
            },
            "editorial": {
                "path": "editorial.md",
                "source_sha256": "0" * 64,
            },
            "articles": [
                {
                    "id": "article",
                    "title": "Pruebas de la fuente",
                    "short_title": "Pruebas de la fuente",
                    "manuscript": "articles/article.md",
                    "source_sha256": "0" * 64,
                }
            ],
            "sections": [],
        },
    )
    before = (overlay_dir / "edition.yaml").read_bytes()

    report = Workflow(tmp_path, adapter=GuardAdapter()).status(EDITION_ID)

    translations = report.checkpoint("translations")
    assert translations.status == "blocked"
    assert translations.next_action.classification == "authorial"
    assert translations.details["languages"]["es"]["status"] == "needs_retranslation"
    result = Workflow(tmp_path).run(EDITION_ID)
    assert not result.changed
    assert (overlay_dir / "edition.yaml").read_bytes() == before


def test_staged_translation_placeholders_stop_run_for_authorial_work(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True)
    (tmp_path / "magazine.toml").write_text(
        '[publication]\n'
        'name = "Workflow Test"\n'
        'language = "en"\n'
        'languages = ["en", "es"]\n',
        encoding="utf-8",
    )
    staged = stage_translation(tmp_path, EDITION_ID, "es")
    assert staged.placeholders
    assert not staged.validation_errors
    overlay_path = (
        tmp_path
        / "editions"
        / EDITION_ID
        / "translations"
        / "es"
        / "edition.yaml"
    )
    overlay = yaml.safe_load(overlay_path.read_text(encoding="utf-8"))
    overlay["articles"][0]["title"] = "Pruebas de la fuente"
    _write_yaml(overlay_path, overlay)

    workflow = Workflow(tmp_path, adapter=GuardAdapter())
    translations = workflow.status(EDITION_ID).checkpoint("translations")

    assert translations.status == "blocked"
    assert translations.next_action.classification == "authorial"
    assert translations.next_action.action is None
    assert translations.details["clerical_languages"] == []
    assert translations.details["authorial_languages"] == ["es"]
    spanish = translations.details["languages"]["es"]
    assert spanish["status"] == "needs_translation"
    assert {
        placeholder["pointer"] for placeholder in spanish["placeholders"]
    } >= {
        "title",
        "cover.headline",
        "cover.deck",
        "articles[article].short_title",
        "articles[article].manuscript",
    }

    result = workflow.run(EDITION_ID)

    assert not result.changed
    assert result.report.checkpoint("translations").to_dict() == translations.to_dict()


def test_injected_adapter_builds_once_then_status_detects_input_drift(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True, complete_art=True)
    adapter = BuildAdapter()
    workflow = Workflow(tmp_path, adapter=adapter)

    result = workflow.run(EDITION_ID)

    assert result.actions == ("Built the fixture.",)
    assert adapter.advanced == ["build"]
    assert result.report.checkpoint("fit").status == "complete"
    assert result.report.checkpoint("validation").status == "complete"
    assert result.report.checkpoint("build").status == "complete"
    assert result.report.next_checkpoint.id == "evidence_review"
    assert (
        result.report.next_checkpoint.next_action.classification == "human-review"
    )

    manuscript = tmp_path / "editions" / EDITION_ID / "articles" / "article.md"
    manuscript.write_text("Source evidence, revised.", encoding="utf-8")
    drifted = workflow.status(EDITION_ID)

    build = drifted.checkpoint("build")
    assert build.status == "blocked"
    assert build.next_action.classification == "deterministic"
    assert build.details["stale_languages"] == ["en"]
    assert build.details["languages"]["en"]["stale_inputs"] == [
        f"changed input: editions/{EDITION_ID}/articles/article.md"
    ]


def test_run_reuses_probe_checkpoints_after_build_and_second_status_runs_no_probes(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True, complete_art=True)
    adapter = CountingBuildAdapter()
    keyed: list[str] = []

    def counting_key(kind: str, *args, **kwargs) -> str:
        keyed.append(kind)
        return _probe_cache_key(kind, *args, **kwargs)

    with patch("magazine.workflow._probe_cache_key", counting_key):
        result = Workflow(tmp_path, adapter=adapter).run(EDITION_ID)

    assert adapter.advanced == ["build"]
    assert result.report.checkpoint("fit").status == "complete"
    assert result.report.checkpoint("validation").status == "complete"
    assert result.report.checkpoint("build").status == "complete"
    assert adapter.fit_calls == 1
    assert adapter.validate_calls == 1
    # The post-build iteration reused checkpoints 0-7 (L1), so it computed no
    # probe keys at all; only the first status keyed fit and validate.
    assert keyed == ["fit", "validate"]

    fresh = Workflow(tmp_path, adapter=adapter).status(EDITION_ID)

    assert adapter.fit_calls == 1
    assert adapter.validate_calls == 1
    assert fresh.to_dict() == result.report.to_dict()
    assert fresh.to_json() == result.report.to_json()
    # Details keep the adapter's raw insertion order on both the miss report
    # and the persisted-hit report, including nested dicts.
    for report in (result.report, fresh):
        details = report.checkpoint("fit").details
        assert list(details) == ["ok", "languages"]
        assert list(details["languages"]["en"]["articles"][0]) == [
            "id",
            "pages",
            "cap",
        ]


def test_second_status_hashes_nothing_and_one_manuscript_edit_invalidates_exactly_one_entry(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True, complete_art=True)
    adapter = CountingBuildAdapter()
    Workflow(tmp_path, adapter=adapter).run(EDITION_ID)
    before = json.loads(_cache_path(tmp_path).read_text(encoding="utf-8"))
    fit_calls = adapter.fit_calls
    validate_calls = adapter.validate_calls
    project_root = tmp_path.resolve()
    hashed: list[str] = []

    def counting_hash(path: Path) -> str:
        hashed.append(path.resolve().relative_to(project_root).as_posix())
        return _hash_path_bytes(path)

    with patch("magazine.workflow._hash_path_bytes", counting_hash):
        Workflow(tmp_path, adapter=adapter).status(EDITION_ID)

        assert hashed == []
        assert adapter.fit_calls == fit_calls
        assert adapter.validate_calls == validate_calls

        manuscript = (
            tmp_path / "editions" / EDITION_ID / "articles" / "article.md"
        )
        manuscript.write_text("Source evidence, revised.", encoding="utf-8")
        stat = manuscript.stat()
        os.utime(
            manuscript,
            ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000),
        )

        drifted = Workflow(tmp_path, adapter=adapter).status(EDITION_ID)

    manuscript_relative = f"editions/{EDITION_ID}/articles/article.md"
    assert hashed == [manuscript_relative]
    assert adapter.fit_calls == fit_calls + 1
    assert adapter.validate_calls == validate_calls + 1
    build = drifted.checkpoint("build")
    assert build.status == "blocked"
    assert build.details["languages"]["en"]["stale_inputs"] == [
        f"changed input: {manuscript_relative}"
    ]
    after = json.loads(_cache_path(tmp_path).read_text(encoding="utf-8"))
    assert (
        after["hashes"][manuscript_relative]["sha256"]
        != before["hashes"][manuscript_relative]["sha256"]
    )
    assert {
        key: value
        for key, value in after["hashes"].items()
        if key != manuscript_relative
    } == {
        key: value
        for key, value in before["hashes"].items()
        if key != manuscript_relative
    }


def test_report_is_identical_with_and_without_the_workflow_cache_file(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True, complete_art=True)
    adapter = CountingBuildAdapter()
    _write_build(tmp_path)
    package_dir = tmp_path / "output" / EDITION_ID

    def package_files() -> list[str]:
        return sorted(
            path.relative_to(package_dir).as_posix()
            for path in package_dir.rglob("*")
            if path.is_file()
        )

    # Baseline before any workflow call, so a cache file wrongly placed under
    # the package dir cannot hide inside it.
    baseline_files = package_files()
    Workflow(tmp_path, adapter=adapter).run(EDITION_ID)

    assert package_files() == baseline_files

    cached = Workflow(tmp_path, adapter=adapter).status(EDITION_ID).to_json()
    fit_calls = adapter.fit_calls
    validate_calls = adapter.validate_calls
    _cache_path(tmp_path).unlink()

    fresh = Workflow(tmp_path, adapter=adapter).status(EDITION_ID).to_json()

    assert fresh == cached
    assert adapter.fit_calls == fit_calls + 1
    assert adapter.validate_calls == validate_calls + 1
    assert package_files() == baseline_files


def test_corrupt_cache_file_degrades_to_full_recompute(tmp_path: Path):
    _make_project(tmp_path, extraction=True, complete_art=True)
    adapter = CountingBuildAdapter()
    Workflow(tmp_path, adapter=adapter).run(EDITION_ID)
    baseline = Workflow(tmp_path, adapter=adapter).status(EDITION_ID).to_json()
    _cache_path(tmp_path).write_bytes(b"{not json")
    fit_calls = adapter.fit_calls
    validate_calls = adapter.validate_calls

    report = Workflow(tmp_path, adapter=adapter).status(EDITION_ID)

    assert report.to_json() == baseline
    assert adapter.fit_calls == fit_calls + 1
    assert adapter.validate_calls == validate_calls + 1
    restored = json.loads(_cache_path(tmp_path).read_text(encoding="utf-8"))
    assert restored["schema_version"] == _WORKFLOW_CACHE_SCHEMA
    assert restored["edition_id"] == EDITION_ID
    assert set(restored["probes"]) == {"fit", "validate"}


def test_cache_written_under_a_superseded_schema_is_discarded_not_trusted(
    tmp_path: Path,
):
    """A schema bump must invalidate every persisted probe verdict.

    The schema exists because the probe closure itself can change shape --
    version 2 dropped the per-article fidelity ledgers from the declared build
    inputs -- so a cache written under an older schema keyed its probe entries
    over a different inventory. Reusing it would serve a verdict computed from
    files the current closure no longer reads. The stale file must be ignored
    wholesale, hashes as well as probes, and rewritten at the current schema.
    """

    _make_project(tmp_path, extraction=True, complete_art=True)
    adapter = CountingBuildAdapter()
    Workflow(tmp_path, adapter=adapter).run(EDITION_ID)
    baseline = Workflow(tmp_path, adapter=adapter).status(EDITION_ID).to_json()
    cached = json.loads(_cache_path(tmp_path).read_text(encoding="utf-8"))
    assert cached["schema_version"] == _WORKFLOW_CACHE_SCHEMA
    cached["schema_version"] = _WORKFLOW_CACHE_SCHEMA - 1
    _cache_path(tmp_path).write_text(json.dumps(cached), encoding="utf-8")
    fit_calls = adapter.fit_calls
    validate_calls = adapter.validate_calls
    hashed: list[str] = []

    def counting_hash(path: Path) -> str:
        hashed.append(path.name)
        return _hash_path_bytes(path)

    with patch("magazine.workflow._hash_path_bytes", counting_hash):
        report = Workflow(tmp_path, adapter=adapter).status(EDITION_ID)

    assert report.to_json() == baseline
    assert adapter.fit_calls == fit_calls + 1
    assert adapter.validate_calls == validate_calls + 1
    # Not one memoized hash survived the bump either.
    assert hashed
    rewritten = json.loads(_cache_path(tmp_path).read_text(encoding="utf-8"))
    assert rewritten["schema_version"] == _WORKFLOW_CACHE_SCHEMA


def test_probe_cache_tracks_declared_inputs_outside_the_edition_directory(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True, complete_art=True)
    adapter = CountingBuildAdapter()
    Workflow(tmp_path, adapter=adapter).run(EDITION_ID)

    # Re-point the manuscript at a shared file outside editions/<id>/ and
    # sources/, with identical bytes so the authoring checkpoints stay
    # complete and the probes keep running.
    manuscript = tmp_path / "editions" / EDITION_ID / "articles" / "article.md"
    shared = tmp_path / "shared" / "article.md"
    shared.parent.mkdir()
    shared.write_bytes(manuscript.read_bytes())
    manifest_path = tmp_path / "editions" / EDITION_ID / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["articles"][0]["manuscript"] = "../../shared/article.md"
    _write_yaml(manifest_path, manifest)
    Workflow(tmp_path, adapter=adapter).status(EDITION_ID)
    fit_calls = adapter.fit_calls
    validate_calls = adapter.validate_calls

    steady = Workflow(tmp_path, adapter=adapter).status(EDITION_ID)

    assert steady.checkpoint("fit").status == "complete"
    assert adapter.fit_calls == fit_calls
    assert adapter.validate_calls == validate_calls

    shared.write_text("Source evidence, revised elsewhere.", encoding="utf-8")
    stat = shared.stat()
    os.utime(shared, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

    Workflow(tmp_path, adapter=adapter).status(EDITION_ID)

    assert adapter.fit_calls == fit_calls + 1
    assert adapter.validate_calls == validate_calls + 1


def test_build_manifest_requires_the_complete_current_input_inventory(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True, complete_art=True)
    _write_build(tmp_path)
    path = tmp_path / "output" / EDITION_ID / "edition-manifest.json"
    built = json.loads(path.read_text(encoding="utf-8"))
    del built["inputs"]["articles"][0]["tail_art"]
    path.write_text(json.dumps(built), encoding="utf-8")

    build = Workflow(tmp_path, adapter=BuildAdapter()).status(
        EDITION_ID
    ).checkpoint("build")

    assert build.status == "blocked"
    assert build.details["languages"]["en"]["stale_inputs"] == [
        f"missing input binding: editions/{EDITION_ID}/art/article-tail.png"
    ]


def test_build_inventory_accepts_article_opener_art_binding(tmp_path: Path):
    _make_project(tmp_path, extraction=True, complete_art=True)
    _add_article_opener(tmp_path)
    _write_build(tmp_path)

    build = Workflow(tmp_path, adapter=BuildAdapter()).status(
        EDITION_ID
    ).checkpoint("build")

    assert build.details["languages"]["en"]["stale_inputs"] == []
    assert build.details["stale_languages"] == []


def test_build_manifest_rejects_malformed_hashes_and_escaping_paths(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True, complete_art=True)
    _write_build(tmp_path)
    path = tmp_path / "output" / EDITION_ID / "edition-manifest.json"
    built = json.loads(path.read_text(encoding="utf-8"))
    built["inputs"]["articles"][0]["manuscript"]["sha256"] = "not-a-sha"
    built["inputs"]["articles"][0]["tail_art"] = {
        "path": "../outside.png",
        "sha256": "0" * 64,
    }
    path.write_text(json.dumps(built), encoding="utf-8")

    build = Workflow(tmp_path, adapter=BuildAdapter()).status(
        EDITION_ID
    ).checkpoint("build")
    stale = build.details["languages"]["en"]["stale_inputs"]

    assert build.status == "blocked"
    assert (
        f"input has invalid sha256: editions/{EDITION_ID}/articles/article.md"
        in stale
    )
    assert "input escapes project root: ../outside.png" in stale
    assert (
        f"missing input binding: editions/{EDITION_ID}/art/article-tail.png"
        in stale
    )


def test_build_requires_a_supported_schema_one_preflight_result(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True, complete_art=True)
    _write_build(tmp_path)
    preflight_path = tmp_path / "output" / EDITION_ID / "preflight.json"
    preflight_path.write_text(
        json.dumps({"schema_version": 7, "result": "optimistic"}),
        encoding="utf-8",
    )

    build = Workflow(tmp_path, adapter=BuildAdapter()).status(
        EDITION_ID
    ).checkpoint("build")
    language = build.details["languages"]["en"]

    assert build.status == "blocked"
    assert build.details["machine_failure_languages"] == ["en"]
    assert language["preflight_result"] == "optimistic"
    assert language["artifact_errors"] == [
        "preflight schema_version must be 1",
        "unsupported preflight result: 'optimistic'",
    ]


def test_translated_build_requires_its_current_translation_manifest_binding(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True, complete_art=True)
    _write_build(tmp_path)
    path = tmp_path / "output" / EDITION_ID / "edition-manifest.json"
    built = json.loads(path.read_text(encoding="utf-8"))
    built["publication"]["language"] = "es"
    expected_inputs = {
        f"editions/{EDITION_ID}/art/illustrations.yaml",
        f"editions/{EDITION_ID}/art/cover-candidate-wildcard.png",
        f"editions/{EDITION_ID}/articles/article.md",
        f"editions/{EDITION_ID}/editorial.md",
        f"editions/{EDITION_ID}/art/article-tail.png",
        f"library/sources/{SOURCE_ID}/record.yaml",
        f"editions/{EDITION_ID}/translations/es/edition.yaml",
    }

    drift = _build_input_drift(
        tmp_path,
        built["edition"],
        built,
        expected_inputs=expected_inputs,
        language="es",
        primary_language="en",
    )

    assert "translated build requires a translation manifest binding" in drift
    assert (
        f"missing input binding: editions/{EDITION_ID}/translations/es/edition.yaml"
        in drift
    )


def test_the_prose_bench_reports_without_blocking_during_the_advisory_rollout(
    tmp_path: Path,
):
    """The three new judges are collected and calibrated before they refuse.

    An edition with no line, edition or learning record must still reach
    ``release_ready``: their thresholds are being calibrated against edition
    004, and a gate switched on before its threshold is known teaches the
    operator to route around it.  So each checkpoint reports what it found --
    including the exact recording command in its details -- without ever
    reaching ``blocked`` and without ever becoming the report's next
    checkpoint.  Emptying ``_ADVISORY_REVIEW_CHECKPOINTS`` is the flip.
    """

    _make_project(tmp_path, extraction=True, complete_art=True)
    _write_build(tmp_path)
    _write_reviews(tmp_path)

    report = Workflow(tmp_path, adapter=BuildAdapter()).status(EDITION_ID)

    for checkpoint_id, kind in (
        ("line_review", "line"),
        ("edition_review", "edition"),
        ("learning_review", "learning"),
    ):
        checkpoint = report.checkpoint(checkpoint_id)
        assert checkpoint.status == "not_applicable", checkpoint_id
        assert checkpoint.next_action is None
        assert checkpoint.details["advisory"] is True
        assert checkpoint.details["status"] == "required_before_release"
        assert checkpoint.details["command"] == (
            f"uv run --locked mag review record {EDITION_ID} --kind {kind}"
        )
    assert report.release_ready
    assert report.next_checkpoint.id == "release"


def test_an_approved_line_review_completes_its_checkpoint(tmp_path: Path):
    _make_project(tmp_path, extraction=True, complete_art=True)
    _write_build(tmp_path)
    _write_reviews(tmp_path)
    edition_dir = tmp_path / "editions" / EDITION_ID
    _write_yaml(
        edition_dir / "reviews" / "line.yaml",
        {
            "schema_version": 1,
            "edition_id": EDITION_ID,
            "reviewer": "Line editor",
            "reviewed_at": "2026-07-29T14:00:00+00:00",
            "result": "approved",
            "findings": [],
            "articles": {
                article_id: {
                    "reviewed_at": "2026-07-29T14:00:00+00:00",
                    "manuscript_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
                for article_id, path in (
                    ("article", edition_dir / "articles" / "article.md"),
                    ("editorial", edition_dir / "editorial.md"),
                )
            },
        },
    )

    report = Workflow(tmp_path, adapter=BuildAdapter()).status(EDITION_ID)

    checkpoint = report.checkpoint("line_review")
    assert checkpoint.status == "complete"
    assert checkpoint.details["articles"]["editorial"]["status"] == "current"
    assert report.release_ready


def test_release_readiness_requires_current_evidence_and_render_decisions(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True, complete_art=True)
    _write_build(tmp_path)
    _write_reviews(tmp_path)

    report = Workflow(tmp_path, adapter=BuildAdapter()).status(EDITION_ID)

    assert report.checkpoint("evidence_review").status == "complete"
    assert report.checkpoint("render_review").status == "complete"
    assert report.release_ready
    assert report.next_checkpoint.id == "release"
    assert report.next_checkpoint.next_action.classification == "human-review"
    assert report.next_checkpoint.next_action.command == (
        f"uv run --locked mag finish {EDITION_ID}"
    )


def test_production_is_complete_for_prose_authored_before_the_pipeline(
    tmp_path: Path,
):
    """The checkpoint asks whether the prose is there, not who wrote it.

    Editions 001 to 004 were drafted before ``mag produce`` existed and carry no
    production records at all. Reporting them blocked would make the report
    useless on every edition the magazine has actually shipped.
    """

    _make_project(tmp_path, extraction=True, complete_art=True)

    report = Workflow(tmp_path, adapter=BuildAdapter()).status(EDITION_ID)

    production = report.checkpoint("production")
    assert production.status == "complete"
    assert production.details["undrafted_pieces"] == []
    assert production.details["pieces"]["article"]["production_status"] == "none"


def test_production_blocks_on_a_staging_marker_and_names_produce(tmp_path: Path):
    _make_project(tmp_path, extraction=True, complete_art=True)
    manuscript = tmp_path / "editions" / EDITION_ID / "articles" / "article.md"
    manuscript.write_text(
        "---\nstage_status: todo\nlabel: EDITORIAL WORK REQUIRED\n---\n\n"
        "<!-- TODO(editor): Replace this staging marker. -->\n",
        encoding="utf-8",
    )

    report = Workflow(tmp_path, adapter=GuardAdapter()).status(EDITION_ID)

    assert report.next_checkpoint.id == "production"
    assert report.next_checkpoint.next_action.classification == "authorial"
    assert report.next_checkpoint.next_action.command == (
        f"uv run --locked mag produce {EDITION_ID}"
    )
    assert "--backend agent" in report.next_checkpoint.next_action.instruction
    assert report.checkpoint("production").details["undrafted_pieces"] == ["article"]
    # Everything downstream reads a manuscript, so nothing downstream runs.
    assert report.checkpoint("translations").status == "blocked"
    assert not report.release_ready


def test_production_blocks_on_the_editorial_marker_that_reached_the_page(
    tmp_path: Path,
):
    """The shape that got through: a marker whose body is a real paragraph.

    ``rerun-004``'s editorial carried a title, a byline and a paragraph, so it
    typeset like any short opening note.  Status has to name it as undrafted
    for the same reason ``validate`` now refuses it -- the frontmatter says so.
    """

    _make_project(tmp_path, extraction=True, complete_art=True)
    (tmp_path / "editions" / EDITION_ID / "editorial.md").write_text(
        "---\n"
        "label: EDITORIAL WORK REQUIRED\n"
        "title: Untitled editorial\n"
        "byline: The Editors\n"
        "stage_status: todo\n"
        "---\n\n"
        "TODO(editor): Replace this staging marker with a source-faithful "
        "manuscript. No source prose was generated.\n",
        encoding="utf-8",
    )

    report = Workflow(tmp_path, adapter=GuardAdapter()).status(EDITION_ID)

    production = report.checkpoint("production")
    assert report.next_checkpoint.id == "production"
    assert production.details["undrafted_pieces"] == ["editorial"]
    assert production.details["pieces"]["editorial"]["staging_marker"]
    assert not production.details["pieces"]["article"]["staging_marker"]
    assert production.next_action.classification == "authorial"
    assert production.next_action.command == (
        f"uv run --locked mag produce {EDITION_ID}"
    )
    assert not report.release_ready


def test_production_blocks_on_an_outstanding_agent_ready_set(tmp_path: Path):
    """The front door names the loop, so a driver never has to invent one."""

    _make_project(tmp_path, extraction=True, complete_art=True)
    _write_yaml(
        tmp_path
        / "editions"
        / EDITION_ID
        / "production"
        / "agent"
        / "ready.yaml",
        {
            "schema_version": 1,
            "edition_id": EDITION_ID,
            "backend": "agent",
            "state": "awaiting_work",
            "ready": [{"item": "article/r1-writer"}, {"item": "editorial/r1-writer"}],
        },
    )

    report = Workflow(tmp_path, adapter=GuardAdapter()).status(EDITION_ID)

    production = report.checkpoint("production")
    assert report.next_checkpoint.id == "production"
    assert production.details["agent_ready"] == [
        "article/r1-writer",
        "editorial/r1-writer",
    ]
    assert production.next_action.command == (
        f"uv run --locked mag produce {EDITION_ID} --backend agent"
    )
    assert "hand-orchestrate" in production.next_action.instruction


def test_production_blocks_on_an_escalated_piece_and_asks_for_a_human(
    tmp_path: Path,
):
    _make_project(tmp_path, extraction=True, complete_art=True)
    _write_yaml(
        tmp_path
        / "editions"
        / EDITION_ID
        / "production"
        / "articles"
        / "article.yaml",
        {
            "schema_version": 1,
            "edition_id": EDITION_ID,
            "piece_id": "article",
            "content_mode": "faithful_edit",
            "status": "escalated",
            "inputs_sha256": "0" * 64,
            "manuscript_sha256": "0" * 64,
            "rounds": [],
        },
    )

    report = Workflow(tmp_path, adapter=GuardAdapter()).status(EDITION_ID)

    production = report.checkpoint("production")
    assert production.status == "blocked"
    assert production.next_action.classification == "human-review"
    assert production.details["escalated_pieces"] == ["article"]
