from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from magazine import Magazine, ValidationError
from magazine.capture import archive_snapshot
from magazine.records import SourceRecord


def make_project(root: Path, *, source_id: str = "source-one") -> None:
    source_dir = root / "library" / "sources" / source_id
    source_dir.mkdir(parents=True)
    source = {
        "schema_version": 1, "id": source_id, "title": "Source", "author": "Author",
        "canonical_url": "https://example.com/source", "submitted_url": "https://example.com/source",
        "captured_at": "2026-07-15T12:00:00Z", "publication_date": None, "kind": "article",
        "status": "extracted", "content_hash": None, "provenance": [], "rights": {}, "metadata": {}, "notes": "",
    }
    fixture = root / "raw-source.txt"
    fixture.write_text("The original article.\n", encoding="utf-8")
    archived = archive_snapshot(
        SourceRecord.from_dict(source), root / "library" / "sources", fixture, method="test_fixture"
    )
    archived.write(root / "library" / "sources")
    edition_dir = root / "editions" / "issue-001"
    (edition_dir / "articles").mkdir(parents=True)
    (edition_dir / "fidelity").mkdir()
    (edition_dir / "editorial.md").write_text("# Editorial\n\nAn argument.", encoding="utf-8")
    (edition_dir / "articles" / "article.md").write_text("The original article.", encoding="utf-8")
    ledger = {"schema_version": 1, "source_ids": [source_id], "paragraphs": [{"status": "retained", "source": "The original article.", "edited": "The original article."}]}
    (edition_dir / "fidelity" / "article.yaml").write_text(yaml.safe_dump(ledger), encoding="utf-8")
    manifest = {
        "id": "issue-001", "issue_number": "001", "title": "Issue", "publication_date": "2026-07-15",
        "editorial": "editions/issue-001/editorial.md", "cover": {"headline": "Issue"},
        "articles": [{"id": "article", "title": "Article", "author": "Author", "source_ids": [source_id],
                      "manuscript": "editions/issue-001/articles/article.md", "fidelity": "editions/issue-001/fidelity/article.yaml"}],
    }
    (edition_dir / "edition.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_validate_edition_through_public_interface(self):
        make_project(self.root)
        edition = Magazine(self.root).validate("issue-001")
        self.assertEqual(edition.title, "Issue")
        self.assertEqual(edition.articles[0].source_ids, ("source-one",))

    def test_validate_rejects_unknown_source(self):
        make_project(self.root, source_id="recorded-source")
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text())
        manifest["articles"][0]["source_ids"] = ["missing-source"]
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "unknown sources"):
            Magazine(self.root).validate("issue-001")

    def test_validate_rejects_unknown_declared_edition_source(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text())
        manifest["sources"] = ["missing-source"]
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "Edition references unknown sources"):
            Magazine(self.root).validate("issue-001")

    def test_validate_rejects_article_and_ledger_content_mode_mismatch(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text())
        manifest["articles"][0]["content_mode"] = "faithful_synthesis"
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "does not match its fidelity ledger"):
            Magazine(self.root).validate("issue-001")
