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
    load_release_state,
    sync_release_state,
)
from test_manifest import make_project


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
        return Magazine(self.root), manifest_path, state_path

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
        build_result = SimpleNamespace(output_dir=package_dir)

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
        checksum, relative = (package_dir / "SHA256SUMS").read_text().strip().split("  ")
        self.assertEqual(relative, "edition-manifest.json")
        self.assertEqual(checksum, hashlib.sha256(package_manifest.read_bytes()).hexdigest())
        state = load_release_state(state_path)
        self.assertEqual(state.open_edition, {
            "id": "002-unreleased", "issue_number": 2, "status": "collecting", "source_ids": [],
        })
        self.assertEqual(state.assignments()["source-one"], "released:issue-001")

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

        updates = dict(_released_package_updates(package))

        english_manifest = json.loads(updates[package / "edition-manifest.json"])
        spanish_manifest = json.loads(updates[spanish / "edition-manifest.json"])
        self.assertEqual(english_manifest["edition"]["status"], "released")
        self.assertEqual(spanish_manifest["edition"]["status"], "released")
        self.assertNotIn("es/", updates[package / "SHA256SUMS"].decode("utf-8"))
        self.assertIn("reader.pdf", updates[spanish / "SHA256SUMS"].decode("utf-8"))
