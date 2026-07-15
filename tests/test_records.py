from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from magazine import Magazine
from magazine.catalog import render_sources
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

    def test_capture_is_idempotent_and_generates_catalog(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        tmp_path = Path(temporary.name)
        magazine = Magazine(tmp_path)
        first = magazine.capture("https://example.com/post?utm_campaign=one", title="Post", captured_at="2026-07-15T12:00:00Z", tags=["AI", "ai"])
        second = magazine.capture("https://example.com/post#later", title="Different title")
        self.assertEqual(first.id, second.id)
        self.assertEqual(len(load_records(tmp_path / "library" / "sources")), 1)
        catalog = magazine.write_sources()
        self.assertIn("## Post", catalog.read_text(encoding="utf-8"))
