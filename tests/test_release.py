import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import yaml

from magazine import Magazine, ValidationError
from magazine.release import (
    _released_package_updates,
    finalize_release,
    finished_edition_id,
    load_release_state,
    open_collection,
    plan_release,
    sync_release_state,
)
from magazine.render_review import create_render_review, load_render_review, write_render_review
from test_manifest import add_extraction, make_project, pin_article_source_hash


class ReleaseStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_capture_queues_new_source_in_open_edition(self):
        magazine = Magazine(self.root)
        snapshot = self.root / "article.html"
        snapshot.write_text("article", encoding="utf-8")
        record = magazine.capture("https://example.com/article", snapshot=snapshot, title="Article")

        state = load_release_state(self.root / "library" / "release-state.yaml")

        self.assertEqual(state.open_edition_id, "001-the-work-left-to-us")
        self.assertEqual(state.queued_source_ids, (record.id,))

    def test_sync_adds_unassigned_sources_but_never_requeues_released_sources(self):
        path = self.root / "library" / "release-state.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(yaml.safe_dump({
            "schema_version": 1,
            "open_edition": {"id": "002-open", "issue_number": 2, "status": "collecting", "source_ids": []},
            "released_editions": [{"id": "001-released", "issue_number": 1, "source_ids": ["old"]}],
        }, sort_keys=False), encoding="utf-8")

        state = sync_release_state(path, {"old", "new"})

        self.assertEqual(state.queued_source_ids, ("new",))
        self.assertEqual(state.assignments()["old"], "released:001-released")

    def test_sources_catalog_exposes_open_edition_assignment(self):
        magazine = Magazine(self.root)
        snapshot = self.root / "article.html"
        snapshot.write_text("article", encoding="utf-8")
        record = magazine.capture("https://example.com/article", snapshot=snapshot, title="Article")

        catalog = magazine.write_sources().read_text(encoding="utf-8")

        self.assertIn("Open edition: `001-the-work-left-to-us`", catalog)
        self.assertIn(f"Release: queued for `001-the-work-left-to-us`", catalog)
        self.assertIn(record.id, catalog)

    def test_a_future_edition_can_receive_intake_while_the_current_one_stays_collecting(self):
        path = self.root / "library" / "release-state.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(yaml.safe_dump({
            "schema_version": 1,
            "open_edition": {
                "id": "003-unreleased",
                "issue_number": 3,
                "status": "collecting",
                "source_ids": ["edition-three-source"],
            },
            "released_editions": [],
        }, sort_keys=False), encoding="utf-8")

        opened = open_collection(
            path,
            edition_id="004-unreleased",
            issue_number=4,
        )
        synced = sync_release_state(
            path,
            {"edition-three-source", "edition-four-source"},
        )

        self.assertEqual(opened.intake_edition_id, "004-unreleased")
        self.assertEqual(
            synced.queued_source_ids_for("003-unreleased"),
            ("edition-three-source",),
        )
        self.assertEqual(
            synced.queued_source_ids_for("004-unreleased"),
            ("edition-four-source",),
        )
        self.assertEqual(
            synced.assignments()["edition-four-source"],
            "queued:004-unreleased",
        )

    def test_capture_can_target_one_of_several_collecting_editions(self):
        magazine = Magazine(self.root)
        magazine.open_collection("002-unreleased", issue_number=2)
        snapshot = self.root / "article.html"
        snapshot.write_text("article", encoding="utf-8")

        record = magazine.capture(
            "https://example.com/article",
            snapshot=snapshot,
            title="Article",
            edition_id="001-the-work-left-to-us",
        )

        state = load_release_state(self.root / "library" / "release-state.yaml")
        self.assertEqual(state.intake_edition_id, "002-unreleased")
        self.assertEqual(
            state.queued_source_ids_for("001-the-work-left-to-us"),
            (record.id,),
        )
        self.assertEqual(state.queued_source_ids_for("002-unreleased"), ())

    def test_open_collection_scaffolds_generic_cover_candidate_brief(self):
        magazine = Magazine(self.root)

        magazine.open_collection("004-unreleased", issue_number=4)

        record_path = (
            self.root
            / "editions"
            / "004-unreleased"
            / "art"
            / "cover-candidates.yaml"
        )
        record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
        self.assertEqual(
            tuple(record["variants"]),
            ("synthetic", "art_directed", "wildcard"),
        )
        self.assertEqual(
            record["selection_status"],
            "pending_editor_choice",
        )

    def test_releasing_an_older_collection_preserves_the_newer_intake_queue(self):
        path = self.root / "library" / "release-state.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(yaml.safe_dump({
            "schema_version": 2,
            "intake_edition_id": "004-unreleased",
            "collecting_editions": [
                {
                    "id": "003-unreleased",
                    "issue_number": 3,
                    "status": "collecting",
                    "source_ids": ["three"],
                },
                {
                    "id": "004-unreleased",
                    "issue_number": 4,
                    "status": "collecting",
                    "source_ids": ["four"],
                },
            ],
            "released_editions": [],
        }, sort_keys=False), encoding="utf-8")

        transition = plan_release(
            load_release_state(path),
            edition_id="003-unreleased",
            issue_number=3,
            source_ids={"three"},
            publication_date="2026-07-28",
        )

        self.assertEqual(transition.next_edition_id, "004-unreleased")
        self.assertEqual(
            transition.state.collecting_edition_ids,
            ("004-unreleased",),
        )
        self.assertEqual(
            transition.state.queued_source_ids_for("004-unreleased"),
            ("four",),
        )

    def test_finished_edition_id_comes_from_issue_number_and_title(self):
        self.assertEqual(
            finished_edition_id(4, "The Systems Around the Model"),
            "004-the-systems-around-the-model",
        )
        self.assertEqual(
            finished_edition_id("12", "Diseño, revisión y señal"),
            "012-diseno-revision-y-senal",
        )

    def prepare_releasable_project(self) -> tuple[Magazine, Path, Path]:
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest.update({
            "status": "assembling",
            "distribution": "private",
            "rights": {
                "faithful_source_reprint": "private_only_while_rights_unknown",
                "public_release": "blocked_pending_permission",
            },
        })
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        state_path = self.root / "library" / "release-state.yaml"
        state_path.write_text(yaml.safe_dump({
            "schema_version": 1,
            "open_edition": {
                "id": "issue-001", "issue_number": 1, "status": "assembling",
                "source_ids": ["source-one"],
            },
            "released_editions": [],
        }, sort_keys=False), encoding="utf-8")
        # issue-001 is now the open edition, so validation requires committed
        # extractions with matching article source pins, and release requires a
        # fresh approved evidence review bound to them.
        pin_article_source_hash(self.root, add_extraction(self.root))
        magazine = Magazine(self.root)
        magazine.record_evidence_review(
            "issue-001", reviewer="Evidence auditor", result="approved"
        )
        return magazine, manifest_path, state_path

    def add_source_record(self, source_id: str) -> None:
        source = yaml.safe_load(
            (self.root / "library" / "sources" / "source-one" / "record.yaml").read_text(
                encoding="utf-8"
            )
        )
        source.update({
            "id": source_id,
            "title": source_id.replace("-", " ").title(),
            "canonical_url": f"https://example.com/{source_id}",
            "submitted_url": f"https://example.com/{source_id}",
        })
        source_dir = self.root / "library" / "sources" / source_id
        source_dir.mkdir()
        source.pop("raw_captures", None)
        source.pop("media_reviews", None)
        (source_dir / "record.yaml").write_text(
            yaml.safe_dump(source, sort_keys=False), encoding="utf-8"
        )
        fixture = self.root / f"{source_id}.txt"
        fixture.write_text(source_id, encoding="utf-8")
        from magazine.capture import archive_snapshot
        from magazine.records import SourceRecord
        archived = archive_snapshot(
            SourceRecord.from_dict(source), self.root / "library" / "sources", fixture,
            method="test_fixture",
        )
        archived.write(self.root / "library" / "sources")

    def test_release_builds_before_freezing_and_opens_empty_next_edition(self):
        magazine, manifest_path, state_path = self.prepare_releasable_project()
        package_dir = self.root / "output" / "issue-001"
        package_dir.mkdir(parents=True)
        package_manifest = package_dir / "edition-manifest.json"
        package_manifest.write_text(json.dumps({
            "edition": {
                "id": "issue-001", "status": "assembling", "distribution": "private",
                "rights": {"public_release": "blocked_pending_permission"},
            },
        }), encoding="utf-8")
        (package_dir / "SHA256SUMS").write_text("stale\n", encoding="utf-8")
        (package_dir / "render-critic.json").write_text(
            json.dumps({"visual_review": {"status": "approved"}}), encoding="utf-8"
        )
        build_result = SimpleNamespace(
            output_dir=package_dir,
            languages=(SimpleNamespace(language="en", output_dir=package_dir),),
        )

        with patch.object(magazine, "build", return_value=build_result) as build:
            result, transition = magazine.release("issue-001")

        build.assert_called_once_with("issue-001")
        self.assertIs(result, build_result)
        self.assertEqual(transition.next_edition_id, "002-unreleased")
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "released")
        self.assertEqual(manifest["distribution"], "private")
        self.assertEqual(manifest["rights"]["public_release"], "blocked_pending_permission")
        packaged = json.loads(package_manifest.read_text(encoding="utf-8"))
        self.assertEqual(packaged["edition"]["status"], "released")
        self.assertEqual(packaged["edition"]["distribution"], "private")
        checksums = {
            relative: checksum
            for checksum, relative in (
                line.split("  ", 1)
                for line in (package_dir / "SHA256SUMS").read_text().splitlines()
            )
        }
        self.assertEqual(
            checksums["edition-manifest.json"],
            hashlib.sha256(package_manifest.read_bytes()).hexdigest(),
        )
        state = load_release_state(state_path)
        self.assertEqual(state.open_edition, {
            "id": "002-unreleased", "issue_number": 2, "status": "collecting", "source_ids": [],
        })
        self.assertEqual(state.assignments()["source-one"], "released:issue-001")
        catalog = (self.root / "sources.md").read_text(encoding="utf-8")
        self.assertIn("Release: released for `issue-001`", catalog)
        self.assertIn("Intake edition: `002-unreleased`", catalog)
        next_cover_record = (
            self.root
            / "editions"
            / "002-unreleased"
            / "art"
            / "cover-candidates.yaml"
        )
        self.assertTrue(next_cover_record.is_file())
        self.assertEqual(
            tuple(
                yaml.safe_load(
                    next_cover_record.read_text(encoding="utf-8")
                )["variants"]
            ),
            ("synthetic", "art_directed", "wildcard"),
        )

    def test_finish_renames_the_collection_and_delegates_one_release(self):
        magazine, _, state_path = self.prepare_releasable_project()
        note = self.root / "editions" / "issue-001" / "prototypes" / "note.md"
        note.parent.mkdir()
        note.write_text(
            "The working label issue-001 appears here as quoted prose.\n",
            encoding="utf-8",
        )
        build_result = SimpleNamespace(output_dir=self.root / "output" / "001-issue")
        transition = SimpleNamespace(
            released_edition_id="001-issue",
            next_edition_id="002-unreleased",
        )

        with patch.object(
            magazine,
            "release",
            return_value=(build_result, transition),
        ) as release, patch.object(magazine, "web") as web, patch.object(
            magazine,
            "render_review_status",
            return_value={
                "languages": {"en": {"status": "approved", "machine_result": "pass"}}
            },
        ):
            result, finished = magazine.finish("issue-001")

        web.assert_called_once_with("001-issue")
        release.assert_called_once_with(
            "001-issue",
            next_edition_id=None,
            review_baseline=("issue-001", magazine.output_dir / "issue-001"),
        )
        self.assertIs(result, build_result)
        self.assertIs(finished, transition)
        self.assertFalse((self.root / "editions" / "issue-001").exists())
        renamed = self.root / "editions" / "001-issue"
        self.assertTrue(renamed.is_dir())
        manifest = yaml.safe_load(
            (renamed / "edition.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["id"], "001-issue")
        self.assertIn(
            "editions/001-issue/articles/article.md",
            manifest["articles"][0]["manuscript"],
        )
        self.assertIn(
            "working label issue-001",
            (renamed / "prototypes" / "note.md").read_text(encoding="utf-8"),
        )
        evidence = yaml.safe_load(
            (renamed / "reviews" / "evidence.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(evidence["edition_id"], "001-issue")
        state = load_release_state(state_path)
        self.assertEqual(state.intake_edition_id, "001-issue")
        self.assertEqual(state.collecting_edition_ids, ("001-issue",))

    def test_finish_rolls_the_identity_back_when_release_fails(self):
        magazine, _, state_path = self.prepare_releasable_project()

        def write_web(_edition_id):
            index = self.root / "output" / "001-issue" / "web" / "en" / "index.html"
            index.parent.mkdir(parents=True)
            index.write_text("generated", encoding="utf-8")

        with patch.object(
            magazine,
            "release",
            side_effect=ValidationError("render failed"),
        ), patch.object(magazine, "web", side_effect=write_web):
            with patch.object(
                magazine,
                "render_review_status",
                return_value={
                    "languages": {
                        "en": {"status": "approved", "machine_result": "pass"}
                    }
                },
            ):
                with self.assertRaisesRegex(ValidationError, "render failed"):
                    magazine.finish("issue-001")

        original = self.root / "editions" / "issue-001"
        self.assertTrue(original.is_dir())
        self.assertFalse((self.root / "editions" / "001-issue").exists())
        manifest = yaml.safe_load(
            (original / "edition.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["id"], "issue-001")
        evidence = yaml.safe_load(
            (original / "reviews" / "evidence.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(evidence["edition_id"], "issue-001")
        self.assertEqual(load_release_state(state_path).intake_edition_id, "issue-001")
        self.assertFalse((self.root / "output" / "001-issue").exists())

    def test_finish_reports_when_generated_output_cannot_be_removed(self):
        magazine, _, state_path = self.prepare_releasable_project()

        def write_web(_edition_id):
            index = self.root / "output" / "001-issue" / "web" / "en" / "index.html"
            index.parent.mkdir(parents=True)
            index.write_text("generated", encoding="utf-8")

        with patch.object(
            magazine,
            "release",
            side_effect=ValidationError("render failed"),
        ), patch.object(
            magazine,
            "web",
            side_effect=write_web,
        ), patch(
            "magazine.compiler.shutil.rmtree",
            side_effect=OSError("permission denied"),
        ), patch.object(
            magazine,
            "render_review_status",
            return_value={
                "languages": {"en": {"status": "approved", "machine_result": "pass"}}
            },
        ):
            with self.assertRaisesRegex(
                ValidationError,
                "could not remove generated output",
            ):
                magazine.finish("issue-001")

        self.assertTrue((self.root / "editions" / "issue-001").is_dir())
        self.assertEqual(load_release_state(state_path).intake_edition_id, "issue-001")

    def test_release_does_not_commit_if_next_collection_scaffolding_fails(self):
        magazine, _, state_path = self.prepare_releasable_project()

        with patch.object(
            magazine,
            "_scaffold_collecting_cover_records",
            side_effect=OSError("disk full"),
        ), patch.object(magazine, "build") as build:
            with self.assertRaisesRegex(OSError, "disk full"):
                magazine.release("issue-001")

        build.assert_not_called()
        state = load_release_state(state_path)
        self.assertEqual(state.collecting_edition_ids, ("issue-001",))
        manifest = yaml.safe_load(
            (self.root / "editions" / "issue-001" / "edition.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotEqual(manifest["status"], "released")

    def test_release_rebinds_an_identity_only_visual_match_before_freezing(self):
        magazine, _, state_path = self.prepare_releasable_project()

        def reviewable_package(path: Path, *, pdf_marker: bytes) -> Path:
            (path / "home").mkdir(parents=True)
            (path / "reader.pdf").write_bytes(pdf_marker + b" reader")
            (path / "home" / "booklet-a4.pdf").write_bytes(
                pdf_marker + b" booklet"
            )
            (path / "edition-manifest.json").write_text(
                json.dumps(
                    {
                        "edition": {"id": "issue-001", "status": "assembling"},
                        "layout": {
                            "design_direction": "WeasyPrint / A5 fold proof"
                        },
                    }
                ),
                encoding="utf-8",
            )
            (path / "render-critic.json").write_text(
                json.dumps(
                    {
                        "result": "pass",
                        "page_count": 1,
                        "visual_review": {"status": "stale"},
                    }
                ),
                encoding="utf-8",
            )
            for directory in (
                "reader-pages",
                "booklet-sides",
                "cover-booklet-sides",
            ):
                raster = path / "render-review" / directory / "page-001.png"
                raster.parent.mkdir(parents=True)
                raster.write_bytes(b"identical printed pixels " + directory.encode())
            files = sorted(
                item
                for item in path.rglob("*")
                if item.is_file() and item.name != "SHA256SUMS"
            )
            (path / "SHA256SUMS").write_text(
                "".join(
                    f"{hashlib.sha256(item.read_bytes()).hexdigest()}  "
                    f"{item.relative_to(path).as_posix()}\n"
                    for item in files
                ),
                encoding="utf-8",
            )
            return path

        baseline = reviewable_package(
            self.root / "reviewed-output",
            pdf_marker=b"working-id",
        )
        candidate = reviewable_package(
            magazine.output_dir / "issue-001",
            pdf_marker=b"stable-id",
        )
        record = create_render_review(
            edition_id="issue-001",
            reviewer="Independent critic",
            result="approved",
            language_packages={"en": baseline},
            engine="weasyprint",
            design_direction="WeasyPrint / A5 fold proof",
            reviewed_at="2026-07-21T18:00:00+00:00",
        )
        review_path = (
            self.root / "editions" / "issue-001" / "reviews" / "render.yaml"
        )
        write_render_review(review_path, record)
        built = SimpleNamespace(
            output_dir=candidate,
            languages=(
                SimpleNamespace(language="en", output_dir=candidate),
            ),
        )

        with patch.object(magazine, "build", return_value=built):
            _, transition = magazine.release(
                "issue-001",
                review_baseline=("working-id", baseline),
            )

        rebound = load_render_review(review_path, edition_id="issue-001")
        self.assertEqual(transition.released_edition_id, "issue-001")
        self.assertEqual(
            rebound["identity_rebind"]["method"],
            "exact_reader_and_booklet_raster_match",
        )
        self.assertEqual(
            rebound["languages"]["en"]["reader_sha256"],
            hashlib.sha256((candidate / "reader.pdf").read_bytes()).hexdigest(),
        )
        report = json.loads(
            (candidate / "render-critic.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["visual_review"]["status"], "approved")
        self.assertNotIn("issue-001", load_release_state(state_path).collecting_edition_ids)

    def test_release_without_an_evidence_record_refuses_before_building(self):
        """The evidence gate is wired ahead of the expensive render: no record
        means a refusal naming the requirement and no output package at all."""
        magazine, _, _ = self.prepare_releasable_project()
        (self.root / "editions" / "issue-001" / "reviews" / "evidence.yaml").unlink()

        with patch.object(magazine, "build") as build:
            with self.assertRaisesRegex(
                ValidationError,
                # "audit" rather than "review": the shared per-piece spine
                # names the act each lens performs, and evidence's is an audit.
                r"(?s)Release requires a current approved evidence audit.*"
                r"required_before_release",
            ):
                magazine.release("issue-001")

        build.assert_not_called()
        self.assertFalse((self.root / "output").exists())

    def test_release_refuses_missing_visual_approval_after_build(self):
        magazine, manifest_path, state_path = self.prepare_releasable_project()
        package_dir = self.root / "output" / "issue-001"
        package_dir.mkdir(parents=True)
        (package_dir / "render-critic.json").write_text(
            json.dumps({"visual_review": {"status": "required_before_release"}}),
            encoding="utf-8",
        )
        build_result = SimpleNamespace(
            output_dir=package_dir,
            languages=(SimpleNamespace(language="en", output_dir=package_dir),),
        )
        manifest_before = manifest_path.read_bytes()
        state_before = state_path.read_bytes()

        with patch.object(magazine, "build", return_value=build_result):
            with self.assertRaisesRegex(ValidationError, "current approved render review"):
                magazine.release("issue-001")

        self.assertEqual(manifest_path.read_bytes(), manifest_before)
        self.assertEqual(state_path.read_bytes(), state_before)

    def test_release_refuses_to_postpone_any_open_source_without_building(self):
        magazine, manifest_path, state_path = self.prepare_releasable_project()
        self.add_source_record("postponed-source")
        state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        state["open_edition"]["source_ids"].append("postponed-source")
        state_path.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")
        manifest_before = manifest_path.read_bytes()
        state_before = state_path.read_bytes()

        with patch.object(magazine, "build") as build:
            with self.assertRaisesRegex(ValidationError, "postpones sources"):
                magazine.release("issue-001")

        build.assert_not_called()
        self.assertEqual(manifest_path.read_bytes(), manifest_before)
        self.assertEqual(state_path.read_bytes(), state_before)

    def test_release_syncs_stale_source_records_before_planning(self):
        magazine, _, state_path = self.prepare_releasable_project()
        self.add_source_record("late-source")

        with patch.object(magazine, "build") as build:
            with self.assertRaisesRegex(ValidationError, "late-source"):
                magazine.release("issue-001")

        build.assert_not_called()
        self.assertEqual(
            load_release_state(state_path).queued_source_ids,
            ("late-source", "source-one"),
        )

    def test_bare_manifest_source_declaration_does_not_satisfy_release(self):
        magazine, manifest_path, state_path = self.prepare_releasable_project()
        self.add_source_record("declared-only")
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["sources"] = ["source-one", "declared-only"]
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
        state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        state["open_edition"]["source_ids"].append("declared-only")
        state_path.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")

        with patch.object(magazine, "build") as build:
            with self.assertRaisesRegex(ValidationError, "declared-only"):
                magazine.release("issue-001")

        build.assert_not_called()

    def test_build_failure_leaves_manifest_and_release_state_untouched(self):
        magazine, manifest_path, state_path = self.prepare_releasable_project()
        manifest_before = manifest_path.read_bytes()
        state_before = state_path.read_bytes()

        with patch.object(magazine, "build", side_effect=RuntimeError("render failed")):
            with self.assertRaisesRegex(RuntimeError, "render failed"):
                magazine.release("issue-001")

        self.assertEqual(manifest_path.read_bytes(), manifest_before)
        self.assertEqual(state_path.read_bytes(), state_before)

    def test_commit_failure_rolls_back_manifest_and_release_state(self):
        _, manifest_path, state_path = self.prepare_releasable_project()
        manifest_before = manifest_path.read_bytes()
        state_before = state_path.read_bytes()
        real_replace = os.replace
        calls = 0

        def fail_ledger_replace(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated ledger failure")
            return real_replace(source, destination)

        with patch("magazine.release.os.replace", side_effect=fail_ledger_replace):
            with self.assertRaisesRegex(ValidationError, "Cannot commit release state"):
                finalize_release(
                    state_path,
                    manifest_path,
                    edition_id="issue-001",
                    issue_number=1,
                    source_ids={"source-one"},
                    publication_date="2026-07-15",
                )

        self.assertEqual(manifest_path.read_bytes(), manifest_before)
        self.assertEqual(state_path.read_bytes(), state_before)

    def test_released_sources_are_not_requeued_after_transition(self):
        _, manifest_path, state_path = self.prepare_releasable_project()
        finalize_release(
            state_path,
            manifest_path,
            edition_id="issue-001",
            issue_number=1,
            source_ids={"source-one"},
            publication_date="2026-07-15",
        )

        state = sync_release_state(state_path, {"source-one", "source-two"})

        self.assertEqual(state.queued_source_ids, ("source-two",))
        self.assertEqual(state.assignments()["source-one"], "released:issue-001")

    def test_release_updates_each_language_manifest_and_keeps_checksums_separate(self):
        package = self.root / "output" / "issue-001"
        spanish = package / "es"
        for language_root, language in ((package, "en"), (spanish, "es")):
            language_root.mkdir(parents=True, exist_ok=True)
            (language_root / "edition-manifest.json").write_text(
                json.dumps({
                    "publication": {"language": language},
                    "edition": {"id": "issue-001", "status": "assembling"},
                }),
                encoding="utf-8",
            )
            (language_root / "reader.pdf").write_bytes(language.encode("ascii"))
            (language_root / "SHA256SUMS").write_text("stale\n", encoding="utf-8")
        web_index = package / "web" / "en" / "index.html"
        web_index.parent.mkdir(parents=True)
        web_index.write_text("private web output", encoding="utf-8")

        updates = dict(_released_package_updates(package))

        english_manifest = json.loads(updates[package / "edition-manifest.json"])
        spanish_manifest = json.loads(updates[spanish / "edition-manifest.json"])
        self.assertEqual(english_manifest["edition"]["status"], "released")
        self.assertEqual(spanish_manifest["edition"]["status"], "released")
        self.assertNotIn("es/", updates[package / "SHA256SUMS"].decode("utf-8"))
        self.assertNotIn("web/", updates[package / "SHA256SUMS"].decode("utf-8"))
        self.assertIn("reader.pdf", updates[spanish / "SHA256SUMS"].decode("utf-8"))
