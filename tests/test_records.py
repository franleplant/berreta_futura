from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from datetime import datetime, timezone

import yaml

from magazine import Magazine
from magazine.catalog import render_sources
from magazine.capture import verify_snapshots
from magazine.errors import ValidationError
from magazine.records import SourceRecord, canonicalize_url, load_records


class RecordTests(unittest.TestCase):
    def test_canonicalize_removes_tracking_fragment_and_normalizes(self):
        self.assertEqual(canonicalize_url("HTTPS://Example.COM/a//b/?utm_source=x&z=2&a=1#part"), "https://example.com/a/b?a=1&z=2")

    def test_loader_accepts_durable_source_vocabulary(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        tmp_path = Path(temporary.name)
        directory = tmp_path / "sources" / "the-source"
        directory.mkdir(parents=True)
        record = {
        "schema_version": 1,
        "id": "the-source",
        "title": "The Source",
        "author": "A. Writer",
        "canonical_url": "https://example.com/work",
        "submitted_url": "https://example.com/work?utm_source=x",
        "captured_at": "2026-07-15T12:00:00Z",
        "publication_date": "2026-07-01",
        "kind": "article",
        "status": "extracted",
        "content_hash": "sha256:abc",
        "provenance": [{"relation": "primary_material", "url": "https://example.com/slides"}],
        "rights": {"status": "unknown"},
        "metadata": {"tags": ["AI"], "synopsis": "Worth preserving."},
        "notes": "Private use.",
        }
        (directory / "record.yaml").write_text(yaml.safe_dump(record), encoding="utf-8")
        loaded = load_records(tmp_path / "sources")[0]
        self.assertTrue(loaded.url.endswith("utm_source=x"))
        self.assertEqual(loaded.published_at, "2026-07-01")
        self.assertEqual(loaded.primary_material, ["https://example.com/slides"])
        catalog = render_sources([loaded])
        self.assertIn("Worth preserving.", catalog)
        self.assertIn("- ID: `the-source`", catalog)
        self.assertIn("- Kind / status: article / extracted", catalog)
        self.assertIn("- Content hash: `sha256:abc`", catalog)
        self.assertIn("- Rights status: unknown", catalog)
        self.assertIn("primary_material -> https://example.com/slides", catalog)

    def test_loader_normalizes_yaml_timestamps_for_json_manifests(self):
        record = SourceRecord.from_dict({
            "id": "source", "title": "Source", "canonical_url": "https://example.com/",
            "submitted_url": "https://example.com/",
            "captured_at": datetime(2026, 7, 15, 12, tzinfo=timezone.utc),
            "raw_captures": [{
                "id": "abc", "path": "raw/abc/manifest.json",
                "captured_at": datetime(2026, 7, 15, 13, tzinfo=timezone.utc),
            }],
        })
        self.assertEqual(record.captured_at, "2026-07-15T12:00:00+00:00")
        self.assertEqual(record.raw_captures[0]["captured_at"], "2026-07-15T13:00:00+00:00")

    def test_loader_preserves_legacy_records_without_media_triage(self):
        record = SourceRecord.from_dict({
            "id": "source", "title": "Source", "canonical_url": "https://example.com/",
            "submitted_url": "https://example.com/", "captured_at": "2026-07-15T12:00:00Z",
            "raw_captures": [{"id": "a" * 64, "path": f"raw/{'a' * 64}/manifest.json"}],
        })

        self.assertEqual(record.media_reviews, ())

    def test_loader_validates_and_round_trips_capture_media_triage(self):
        capture_id = "a" * 64
        asset_sha = "b" * 64
        record = SourceRecord.from_dict({
            "id": "source", "title": "Source", "canonical_url": "https://example.com/",
            "submitted_url": "https://example.com/", "captured_at": "2026-07-15T12:00:00Z",
            "raw_captures": [{"id": capture_id, "path": f"raw/{capture_id}/manifest.json"}],
            "media_reviews": [{
                "capture_id": capture_id,
                "status": "media_curated",
                "assets": [{
                    "id": "diagram",
                    "artifact_path": "media/diagram.png",
                    "artifact_sha256": asset_sha,
                    "mime_type": "image/png",
                    "creator": "A. Writer",
                    "credit": "Diagram by A. Writer",
                    "rights": {
                        "status": "unknown",
                        "intended_use": "private_reference",
                        "attribution_required": True,
                        "public_reprint_allowed": False,
                    },
                }],
            }],
        })

        serialized = record.to_dict()
        self.assertEqual(record.media_reviews[0].assets[0].id, "diagram")
        self.assertEqual(serialized["media_reviews"][0]["status"], "media_curated")
        self.assertEqual(serialized["media_reviews"][0]["assets"][0]["artifact_sha256"], asset_sha)

    def test_media_rejected_requires_a_human_note_and_no_selected_assets(self):
        capture_id = "a" * 64
        with self.assertRaisesRegex(ValidationError, "media_rejected requires a note"):
            SourceRecord.from_dict({
                "id": "source", "title": "Source", "canonical_url": "https://example.com/",
                "submitted_url": "https://example.com/", "captured_at": "2026-07-15T12:00:00Z",
                "raw_captures": [{"id": capture_id, "path": f"raw/{capture_id}/manifest.json"}],
                "media_reviews": [{
                    "capture_id": capture_id,
                    "status": "media_rejected",
                    "assets": [],
                }],
            })

    def test_capture_is_idempotent_and_generates_catalog(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        tmp_path = Path(temporary.name)
        magazine = Magazine(tmp_path)
        snapshot = tmp_path / "post.html"
        snapshot.write_text("<main>Original post</main>", encoding="utf-8")
        first = magazine.capture(
            "https://example.com/post?utm_campaign=one", snapshot=snapshot,
            title="Post", captured_at="2026-07-15T12:00:00Z", tags=["AI", "ai"]
        )
        second = magazine.capture(
            "https://example.com/post#later", snapshot=snapshot, title="Different title"
        )
        self.assertEqual(first.id, second.id)
        self.assertEqual(len(second.raw_captures), 1)
        self.assertEqual(len(load_records(tmp_path / "library" / "sources")), 1)
        catalog = magazine.write_sources()
        self.assertIn("## Post", catalog.read_text(encoding="utf-8"))
        self.assertIn("Raw captures: 1 committed bundle", catalog.read_text(encoding="utf-8"))

    def test_capture_requires_a_snapshot(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        with self.assertRaises(TypeError):
            Magazine(Path(temporary.name)).capture("https://example.com/post", title="Post")

    def test_raw_capture_detects_later_mutation(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        snapshot = root / "page.html"
        snapshot.write_text("original", encoding="utf-8")
        magazine = Magazine(root)
        record = magazine.capture("https://example.com/post", snapshot=snapshot, title="Post")
        manifest = root / "library" / "sources" / record.id / record.raw_captures[0]["path"]
        artifact = manifest.parent / "artifacts" / "page.html"
        artifact.write_text("changed", encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "changed after capture"):
            verify_snapshots(record, magazine.sources_dir)

    def test_raw_directory_capture_preserves_nested_artifacts(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        snapshot = root / "browser-export"
        (snapshot / "media").mkdir(parents=True)
        (snapshot / "page.html").write_text("<main>Page</main>", encoding="utf-8")
        (snapshot / "media" / "image.bin").write_bytes(b"image")

        magazine = Magazine(root)
        record = magazine.capture(
            "https://example.com/post", snapshot=snapshot,
            capture_method="authenticated_browser", title="Post"
        )

        manifest = root / "library" / "sources" / record.id / record.raw_captures[0]["path"]
        self.assertTrue((manifest.parent / "artifacts" / "page.html").is_file())
        self.assertTrue((manifest.parent / "artifacts" / "media" / "image.bin").is_file())
        verify_snapshots(record, magazine.sources_dir)
