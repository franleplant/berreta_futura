from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import unittest

import yaml

from magazine import Magazine, ValidationError
from magazine.capture import archive_snapshot
from magazine.manifest import _edition_copy_sha256
from magazine.records import SourceRecord


def make_project(root: Path, *, source_id: str = "source-one") -> None:
    (root / "magazine.toml").write_text(
        '[publication]\nname = "Test Review"\n', encoding="utf-8"
    )
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
    (edition_dir / "editorial.md").write_text(
        "---\ntitle: A Test Editorial\nbyline: The editors\nlabel: ORIGINAL EDITORIAL\n---\n\nAn argument.",
        encoding="utf-8",
    )
    (edition_dir / "articles" / "article.md").write_text("The original article.", encoding="utf-8")
    ledger = {"schema_version": 1, "source_ids": [source_id], "paragraphs": [{"status": "retained", "source": "The original article.", "edited": "The original article."}]}
    (edition_dir / "fidelity" / "article.yaml").write_text(yaml.safe_dump(ledger), encoding="utf-8")
    manifest = {
        "id": "issue-001", "issue_number": "001", "title": "Issue", "publication_date": "2026-07-15",
        "editorial": "editions/issue-001/editorial.md", "cover": {"headline": "Issue"},
        "articles": [{"id": "article", "title": "Article", "short_title": "Article",
                      "opener_variant": "edge_medallion", "author": "Author",
                      "author_note": "Author writes about this subject for Example.", "source_ids": [source_id],
                      "manuscript": "editions/issue-001/articles/article.md", "fidelity": "editions/issue-001/fidelity/article.yaml"}],
    }
    (edition_dir / "edition.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def add_spanish_translation(root: Path) -> None:
    base = Magazine(root).validate("issue-001")
    (root / "magazine.toml").write_text(
        '[publication]\nname = "Test Review"\nlanguage = "en"\nlanguages = ["en", "es"]\n',
        encoding="utf-8",
    )
    translation_dir = root / "editions" / "issue-001" / "translations" / "es"
    (translation_dir / "articles").mkdir(parents=True)
    source_editorial = root / "editions" / "issue-001" / "editorial.md"
    source_article = root / "editions" / "issue-001" / "articles" / "article.md"
    translated_editorial = translation_dir / "editorial.md"
    translated_article = translation_dir / "articles" / "article.md"
    translated_editorial.write_text(
        "---\ntitle: Un editorial de prueba\nbyline: La redacción\nlabel: EDITORIAL ORIGINAL\n---\n\nUn argumento.",
        encoding="utf-8",
    )
    translated_article.write_text("El artículo original.", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "language": "es",
        "source_language": "en",
        "locale": "es-AR",
        "fallback_locale": "es-ES",
        "base_copy_sha256": _edition_copy_sha256(base),
        "title": "Número",
        "cover": {"headline": "Número"},
        "editorial": {
            "path": "editorial.md",
            "source_sha256": hashlib.sha256(source_editorial.read_bytes()).hexdigest(),
        },
        "articles": [{
            "id": "article",
            "title": "Artículo",
            "short_title": "Artículo",
            "author_note": "Author escribe sobre este tema para Example.",
            "manuscript": "articles/article.md",
            "source_sha256": hashlib.sha256(source_article.read_bytes()).hexdigest(),
        }],
        "sections": [],
    }
    (translation_dir / "edition.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_validate_edition_through_public_interface(self):
        make_project(self.root)
        edition = Magazine(self.root).validate("issue-001")
        self.assertEqual(edition.publication_name, "Test Review")
        self.assertEqual(edition.title, "Issue")
        self.assertEqual(
            edition.articles[0].author_note,
            "Author writes about this subject for Example.",
        )
        self.assertEqual(edition.articles[0].source_ids, ("source-one",))

    def test_validate_rejects_unknown_source(self):
        make_project(self.root, source_id="recorded-source")
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text())
        manifest["articles"][0]["source_ids"] = ["missing-source"]
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "unknown sources"):
            Magazine(self.root).validate("issue-001")

    def test_validate_requires_a_concise_article_author_note(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text())
        manifest["articles"][0].pop("author_note")
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "missing: author_note"):
            Magazine(self.root).validate("issue-001")

    def test_validate_rejects_display_emphasis_outside_the_article_title(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text())
        manifest["articles"][0]["display_emphasis"] = "Missing"
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "display_emphasis must occur"):
            Magazine(self.root).validate("issue-001")

    def test_validate_rejects_non_source_faithful_short_title(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text())
        manifest["articles"][0]["short_title"] = "Invented navigation"
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "short_title must occur"):
            Magazine(self.root).validate("issue-001")

    def test_validate_rejects_unknown_opener_variant(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text())
        manifest["articles"][0]["opener_variant"] = "surprise_me"
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "invalid opener_variant"):
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

    def test_validate_requires_editorial_title_metadata(self):
        make_project(self.root)
        editorial = self.root / "editions" / "issue-001" / "editorial.md"
        editorial.write_text("---\nbyline: The editors\n---\n\nAn argument.", encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "requires a non-empty title"):
            Magazine(self.root).validate("issue-001")

    def test_validate_requires_every_configured_language(self):
        make_project(self.root)
        (self.root / "magazine.toml").write_text(
            '[publication]\nname = "Test Review"\nlanguage = "en"\nlanguages = ["en", "es"]\n',
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValidationError, "translation manifest not found"):
            Magazine(self.root).validate("issue-001")

    def test_validate_accepts_hash_pinned_structure_preserving_translation(self):
        make_project(self.root)
        add_spanish_translation(self.root)

        edition = Magazine(self.root).validate("issue-001")

        self.assertEqual(edition.language, "en")

    def test_validate_rejects_translation_after_english_source_changes(self):
        make_project(self.root)
        add_spanish_translation(self.root)
        editorial = self.root / "editions" / "issue-001" / "editorial.md"
        editorial.write_text(
            "---\ntitle: A Test Editorial\nbyline: The editors\nlabel: ORIGINAL EDITORIAL\n---\n\nA revised argument.",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValidationError, "is stale"):
            Magazine(self.root).validate("issue-001")
