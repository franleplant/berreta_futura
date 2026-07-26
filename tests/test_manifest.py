from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import unittest

import yaml
from PIL import Image

from magazine import Magazine, ValidationError
from magazine.capture import archive_snapshot
from magazine.manifest import _edition_copy_sha256, load_edition, load_translation
from magazine.media_schema import caption_sha256, credit_sha256
from magazine.records import SourceRecord, load_records


def render_engine_table(engine: str | None) -> str:
    """The ``[render]`` table pinning ``engine``.

    ``None`` writes no table at all, which is what a real project looks like and
    what selects the publication default (``render_engine.DEFAULT_ENGINE``).  A
    fixture only names an engine when the test is about that engine -- pinning
    by default is how the build suite ended up exercising the rollback.
    """
    return "" if engine is None else f'\n[render]\nengine = "{engine}"\n'


def make_project(
    root: Path, *, source_id: str = "source-one", engine: str | None = None
) -> None:
    (root / "magazine.toml").write_text(
        '[publication]\nname = "Test Review"\n' + render_engine_table(engine),
        encoding="utf-8",
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
    (edition_dir / "art").mkdir()
    closing_plates = []
    for index, color in enumerate(("#2d145e", "#ff5a00", "#111111"), start=1):
        art_path = edition_dir / "art" / f"coda-{index}.png"
        Image.new("RGB", (900, 1125), color).save(art_path)
        closing_plates.append({
            "title": f"Coda {index}",
            "art_path": art_path.relative_to(root).as_posix(),
        })
    ledger = {"schema_version": 1, "source_ids": [source_id], "paragraphs": [{"status": "retained", "source": "The original article.", "edited": "The original article."}]}
    (edition_dir / "fidelity" / "article.yaml").write_text(yaml.safe_dump(ledger), encoding="utf-8")
    manifest = {
        "id": "issue-001", "issue_number": "001", "title": "Issue", "publication_date": "2026-07-15",
        "editorial": "editions/issue-001/editorial.md", "cover": {"headline": "Issue"},
        "closing_plates": closing_plates,
        "articles": [{"id": "article", "title": "Article", "short_title": "Article",
                      "opener_variant": "edge_medallion", "author": "Author",
                      "author_note": "Author writes about this subject for Example.", "source_ids": [source_id],
                      "manuscript": "editions/issue-001/articles/article.md", "fidelity": "editions/issue-001/fidelity/article.yaml"}],
    }
    (edition_dir / "edition.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def add_spanish_translation(root: Path, *, engine: str | None = None) -> None:
    edition_data = yaml.safe_load(
        (root / "editions" / "issue-001" / "edition.yaml").read_text(encoding="utf-8")
    )
    has_figures = any(article.get("figures") for article in edition_data.get("articles", []))
    base = load_edition_with_records(root) if has_figures else Magazine(root).validate("issue-001")
    # This rewrites magazine.toml wholesale, so it has to restate the engine the
    # project was made with rather than silently dropping the caller's choice.
    (root / "magazine.toml").write_text(
        '[publication]\nname = "Test Review"\nlanguage = "en"\nlanguages = ["en", "es"]\n'
        + render_engine_table(engine),
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
        "closing_plate_titles": ["Coda uno", "Coda dos", "Coda tres"],
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


def add_curated_figure(root: Path, *, source_id: str = "source-one") -> None:
    record_path = root / "library" / "sources" / source_id / "record.yaml"
    record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
    capture_id = record["raw_captures"][0]["id"]
    manifest_path = root / "library" / "sources" / source_id / record["raw_captures"][0]["path"]
    raw_manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    artifact = raw_manifest["artifacts"][0]
    record["media_reviews"] = [{
        "capture_id": capture_id,
        "status": "media_curated",
        "assets": [{
            "id": "source-diagram",
            "artifact_path": artifact["path"],
            "artifact_sha256": artifact["sha256"],
            "mime_type": "image/png",
            "creator": "Author",
            "credit": "Diagram by Author",
            "rights": {
                "status": "unknown",
                "intended_use": "private_reference",
                "attribution_required": True,
                "public_reprint_allowed": False,
            },
        }],
    }]
    record_path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
    edition_path = root / "editions" / "issue-001" / "edition.yaml"
    edition = yaml.safe_load(edition_path.read_text(encoding="utf-8"))
    edition["articles"][0]["figures"] = [{
        "id": "diagram",
        "source_id": source_id,
        "asset_id": "source-diagram",
        "decision": "include",
        "criteria": ["important", "useful"],
        "rationale": "This diagram makes the article's central distinction immediately legible.",
        "caption": "The source diagram.",
        "alt_text": "A diagram from the source article.",
        "anchor": "__opener__",
        "layout": "evidence_band",
    }]
    edition_path.write_text(yaml.safe_dump(edition, sort_keys=False), encoding="utf-8")


def load_edition_with_records(root: Path):
    records = {record.id: record for record in load_records(root / "library" / "sources")}
    return load_edition(
        root,
        "issue-001",
        set(records),
        publication_name="Test Review",
        source_records=records,
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

    def test_validate_resolves_the_first_source_s_canonical_url_onto_the_article(self):
        """One url per article, from the *first* source id, or nothing.

        ``source_ids`` is authored and ordered, so the first entry is the
        article's primary source; an article carries one way back, not one per
        source, and the opener already prints the whole list.
        """
        make_project(self.root)

        edition = Magazine(self.root).validate("issue-001")

        self.assertEqual(edition.articles[0].source_url, "https://example.com/source")

    def test_a_source_without_a_canonical_url_leaves_the_article_without_one(self):
        """No canonical url is an ordinary state and never an error."""
        make_project(self.root)
        records = {
            record.id: replace(record, canonical_url="")
            for record in load_records(self.root / "library" / "sources")
        }

        edition = load_edition(
            self.root, "issue-001", set(records), source_records=records
        )

        self.assertIsNone(edition.articles[0].source_url)

    def test_an_edition_loaded_without_source_records_carries_no_source_url(self):
        make_project(self.root)

        edition = load_edition(self.root, "issue-001", {"source-one"})

        self.assertIsNone(edition.articles[0].source_url)

    def test_validate_resolves_optional_article_tail_art(self):
        make_project(self.root)
        art_path = self.root / "editions" / "issue-001" / "art" / "tail.png"
        Image.new("RGB", (1536, 1024), "white").save(art_path)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["articles"][0]["tail_art_path"] = art_path.relative_to(self.root).as_posix()
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False),
            encoding="utf-8",
        )

        edition = Magazine(self.root).validate("issue-001")

        self.assertEqual(edition.articles[0].tail_art, art_path.resolve())

    def test_validate_rejects_missing_article_tail_art(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["articles"][0]["tail_art_path"] = (
            "editions/issue-001/art/missing-tail.png"
        )
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValidationError, "does not exist"):
            Magazine(self.root).validate("issue-001")

    def test_validate_requires_a_media_triage_decision_for_every_capture(self):
        make_project(self.root)
        record_path = self.root / "library" / "sources" / "source-one" / "record.yaml"
        record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
        record.pop("media_reviews")
        record_path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "has no media triage decision"):
            Magazine(self.root).validate("issue-001")

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

    def test_validate_rejects_duplicate_closing_plate_art(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["closing_plates"][1]["art_path"] = manifest["closing_plates"][0]["art_path"]
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "art_path must be unique"):
            Magazine(self.root).validate("issue-001")

    def test_translation_requires_all_localized_closing_plate_titles(self):
        make_project(self.root)
        add_spanish_translation(self.root)
        translation_path = (
            self.root / "editions" / "issue-001" / "translations" / "es" / "edition.yaml"
        )
        translation = yaml.safe_load(translation_path.read_text(encoding="utf-8"))
        translation["closing_plate_titles"] = ["Solo una"]
        translation_path.write_text(
            yaml.safe_dump(translation, allow_unicode=True), encoding="utf-8"
        )

        with self.assertRaisesRegex(ValidationError, "requires exactly 3 closing_plate_titles"):
            Magazine(self.root).validate("issue-001")

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

    def test_load_edition_resolves_explicit_curated_figure_from_archived_source(self):
        make_project(self.root)
        add_curated_figure(self.root)

        edition = load_edition_with_records(self.root)

        figure = edition.articles[0].figures[0]
        self.assertEqual(figure.id, "diagram")
        self.assertEqual(figure.layout, "evidence_band")
        self.assertEqual(figure.credit, "Diagram by Author")
        self.assertTrue(figure.path.is_file())
        self.assertEqual(figure.rights_status, "unknown")

    def test_load_edition_rejects_more_than_three_figures(self):
        make_project(self.root)
        add_curated_figure(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        figure = manifest["articles"][0]["figures"][0]
        manifest["articles"][0]["figures"] = [
            {**figure, "id": "one"},
            {**figure, "id": "two"},
            {**figure, "id": "three"},
            {**figure, "id": "four"},
        ]
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "maximum is 3"):
            load_edition_with_records(self.root)

    def test_load_edition_rejects_figure_without_semantic_anchor(self):
        make_project(self.root)
        add_curated_figure(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["articles"][0]["figures"][0]["anchor"] = "A missing section"
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "anchor does not match"):
            load_edition_with_records(self.root)

    def test_translation_requires_hash_pinned_localized_figure_copy(self):
        make_project(self.root)
        add_curated_figure(self.root)
        base = load_edition_with_records(self.root)
        add_spanish_translation(self.root)
        translation_path = self.root / "editions" / "issue-001" / "translations" / "es" / "edition.yaml"
        translation = yaml.safe_load(translation_path.read_text(encoding="utf-8"))
        translation["base_copy_sha256"] = _edition_copy_sha256(base)
        translation["articles"][0]["figures"] = [{
            "id": "diagram",
            "caption": "El diagrama de la fuente.",
            "credit": "Diagrama de la autora.",
            "alt_text": "Un diagrama del artículo fuente.",
            "anchor": "__opener__",
            "source_caption_sha256": caption_sha256("diagram", "The source diagram."),
            "source_credit_sha256": credit_sha256("diagram", "Diagram by Author"),
        }]
        translation_path.write_text(
            yaml.safe_dump(translation, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )

        localized = load_translation(self.root.resolve(), base, "es")

        figure = localized.articles[0].figures[0]
        self.assertEqual(figure.caption, "El diagrama de la fuente.")
        self.assertEqual(figure.credit, "Diagrama de la autora.")
        self.assertEqual(figure.path, base.articles[0].figures[0].path)

    def test_translation_rejects_stale_figure_caption_pin(self):
        make_project(self.root)
        add_curated_figure(self.root)
        base = load_edition_with_records(self.root)
        add_spanish_translation(self.root)
        translation_path = self.root / "editions" / "issue-001" / "translations" / "es" / "edition.yaml"
        translation = yaml.safe_load(translation_path.read_text(encoding="utf-8"))
        translation["base_copy_sha256"] = _edition_copy_sha256(base)
        translation["articles"][0]["figures"] = [{
            "id": "diagram",
            "caption": "El diagrama.",
            "credit": "Diagrama de la autora.",
            "alt_text": "Un diagrama.",
            "anchor": "__opener__",
            "source_caption_sha256": "0" * 64,
            "source_credit_sha256": credit_sha256("diagram", "Diagram by Author"),
        }]
        translation_path.write_text(
            yaml.safe_dump(translation, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )

        with self.assertRaisesRegex(ValidationError, "caption pin is stale"):
            load_translation(self.root.resolve(), base, "es")
