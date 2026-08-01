from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import copy
import hashlib
import unittest

import yaml
from PIL import Image

from magazine import Magazine, ValidationError
from magazine.capture import archive_snapshot
from magazine.extraction import SourcePin
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
    # Validation requires the release ledger to exist so it can name the open
    # edition.  The fixture's open edition is deliberately *not* issue-001, so
    # issue-001 validates like a released edition (no extraction requirement);
    # tests about the open-edition gate call ``set_open_edition``.
    set_open_edition(root, "999-unreleased", issue_number=999)
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
    cover_variants = {}
    for index, variant in enumerate(
        ("synthetic", "art_directed", "wildcard"),
        start=1,
    ):
        art_path = edition_dir / "art" / f"cover-candidate-{variant}.png"
        Image.new("RGB", (1000, 1000), (index * 50, 20, 40)).save(art_path)
        cover_variants[variant] = {
            "art_path": f"art/cover-candidate-{variant}.png",
            "asset_sha256": hashlib.sha256(art_path.read_bytes()).hexdigest(),
            "generation_method": "imagegen",
            "direction": f"{variant} test direction",
        }
    (edition_dir / "art" / "cover-candidates.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "selection_status": "pending_editor_choice",
                "editorial_reading": "A test cover reading.",
                "variants": cover_variants,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    manifest = {
        "id": "issue-001", "issue_number": "001", "title": "Issue", "publication_date": "2026-07-15",
        "editorial": "editions/issue-001/editorial.md", "cover": {"headline": "Issue"},
        "closing_plates": closing_plates,
        "articles": [{"id": "article", "title": "Article", "short_title": "Article",
                      "opener_variant": "edge_medallion", "author": "Author",
                      "author_note": "Author is chief architect at Example Company.", "source_ids": [source_id],
                      "manuscript": "editions/issue-001/articles/article.md"}],
    }
    (edition_dir / "edition.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def set_open_edition(
    root: Path,
    edition_id: str = "issue-001",
    *,
    issue_number: int = 1,
    source_ids: tuple[str, ...] = (),
) -> None:
    """Write ``library/release-state.yaml`` naming the open edition."""
    state_path = root / "library" / "release-state.yaml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        yaml.safe_dump({
            "schema_version": 1,
            "open_edition": {
                "id": edition_id,
                "issue_number": issue_number,
                "status": "collecting",
                "source_ids": list(source_ids),
            },
            "released_editions": [],
        }, sort_keys=False),
        encoding="utf-8",
    )


def add_source(root: Path, source_id: str, *, body: str = "Another article.\n") -> None:
    """Archive a second minimal source record alongside make_project's."""
    source = {
        "schema_version": 1, "id": source_id, "title": source_id, "author": "Author",
        "canonical_url": f"https://example.com/{source_id}",
        "submitted_url": f"https://example.com/{source_id}",
        "captured_at": "2026-07-15T12:00:00Z", "publication_date": None, "kind": "article",
        "status": "extracted", "content_hash": None, "provenance": [], "rights": {}, "metadata": {}, "notes": "",
    }
    fixture = root / f"raw-{source_id}.txt"
    fixture.write_text(body, encoding="utf-8")
    archived = archive_snapshot(
        SourceRecord.from_dict(source), root / "library" / "sources", fixture, method="test_fixture"
    )
    archived.write(root / "library" / "sources")


def add_extraction(
    root: Path,
    *,
    source_id: str = "source-one",
    body: str = "The original article.\n",
) -> str:
    """Write the source's ``extracted.md`` and return its body SHA-256."""
    record = yaml.safe_load(
        (root / "library" / "sources" / source_id / "record.yaml").read_text(encoding="utf-8")
    )
    bundle = record["raw_captures"][0]["id"]
    (root / "library" / "sources" / source_id / "extracted.md").write_text(
        "---\n"
        "schema_version: 1\n"
        f"source_id: {source_id}\n"
        f"raw_bundle: {bundle}\n"
        "extraction_method: test fixture transcription\n"
        "---\n" + body,
        encoding="utf-8",
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def pin_article_source_hash(
    root: Path,
    body_sha256: str | dict[str, str],
    *,
    article: str = "article",
) -> None:
    """Write one article row's ``source_body_sha256`` in ``edition.yaml``.

    The pin lives in the article row now, so pinning is a manifest edit rather
    than a second file -- which is the whole point of the re-homing: one place
    declares which sources an article uses and what their extraction bodies
    hashed to when it was written.
    """
    manifest_path = root / "editions" / "issue-001" / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    for row in manifest["articles"]:
        if row["id"] == article:
            row["source_body_sha256"] = body_sha256
            break
    else:
        raise AssertionError(f"no article row {article!r} to pin")
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


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
            "author_note": "Author es responsable de arquitectura en Example Company.",
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
            "Author is chief architect at Example Company.",
        )
        self.assertEqual(edition.articles[0].source_ids, ("source-one",))

    def test_malformed_nested_manifest_shapes_raise_validation_errors(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        original = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        cases = (
            ("sources", lambda row: row.update({"sources": {"source-one": True}})),
            (
                "source_ids",
                lambda row: row["articles"][0].update({"source_ids": 7}),
            ),
            ("cover", lambda row: row.update({"cover": "not-a-mapping"})),
            ("sections", lambda row: row.update({"sections": {}})),
            ("closing_plates", lambda row: row.update({"closing_plates": {}})),
            (
                "editorial",
                lambda row: row.update({"editorial": {"path": "editorial.md"}}),
            ),
        )
        for label, mutate in cases:
            with self.subTest(label=label):
                manifest = copy.deepcopy(original)
                mutate(manifest)
                manifest_path.write_text(
                    yaml.safe_dump(manifest, sort_keys=False),
                    encoding="utf-8",
                )
                with self.assertRaises(ValidationError):
                    load_edition(self.root, "issue-001", {"source-one"})

    def test_schema_two_source_requires_the_captured_author_identity(self):
        make_project(self.root)
        record_path = (
            self.root / "library" / "sources" / "source-one" / "record.yaml"
        )
        record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
        capture_id = record["raw_captures"][0]["id"]
        record["schema_version"] = 2
        record["author_profile"] = {
            "note": "Author is principal engineer at Example Company.",
            "evidence": [{
                "url": "https://example.com/author",
                "capture_id": capture_id,
            }],
        }
        record_path.write_text(
            yaml.safe_dump(record, sort_keys=False), encoding="utf-8"
        )

        with self.assertRaisesRegex(
            ValidationError, "must match the captured author biography"
        ):
            Magazine(self.root).validate("issue-001")

        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["articles"][0]["author_note"] = (
            "Author is principal engineer at Example Company."
        )
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )

        edition = Magazine(self.root).validate("issue-001")
        self.assertEqual(
            edition.articles[0].author_note,
            "Author is principal engineer at Example Company.",
        )

    def test_schema_two_source_cannot_enter_an_edition_while_identity_is_pending(self):
        make_project(self.root)
        record_path = (
            self.root / "library" / "sources" / "source-one" / "record.yaml"
        )
        record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
        record["schema_version"] = 2
        record.pop("author_profile", None)
        record_path.write_text(
            yaml.safe_dump(record, sort_keys=False), encoding="utf-8"
        )

        with self.assertRaisesRegex(
            ValidationError, "has no captured author identity"
        ):
            Magazine(self.root).validate("issue-001")

    def test_schema_two_source_requires_the_captured_author_byline(self):
        make_project(self.root)
        record_path = (
            self.root / "library" / "sources" / "source-one" / "record.yaml"
        )
        record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
        capture_id = record["raw_captures"][0]["id"]
        record["schema_version"] = 2
        record["author_profile"] = {
            "note": "Author is chief architect at Example Company.",
            "evidence": [{
                "url": "https://example.com/author",
                "capture_id": capture_id,
            }],
        }
        record_path.write_text(
            yaml.safe_dump(record, sort_keys=False), encoding="utf-8"
        )
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["articles"][0]["author"] = "Example Company"
        manifest["articles"][0]["author_note"] = (
            "Author is chief architect at Example Company."
        )
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )

        with self.assertRaisesRegex(
            ValidationError, "byline must match captured source author"
        ):
            Magazine(self.root).validate("issue-001")

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

    def test_an_empty_or_mistyped_source_ids_declaration_is_an_error(self):
        """A wrongly spelled declaration must never verify vacuously.

        ``source_ids`` is the only place an article says what it was written
        from, so a row whose list cannot be read has no provenance to check --
        it must fail loudly rather than validate against nothing.
        """
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        original = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        for declared in ("source-one", [], [""], [7], {"source-one": True}):
            with self.subTest(declared=declared):
                manifest = copy.deepcopy(original)
                manifest["articles"][0]["source_ids"] = declared
                manifest_path.write_text(
                    yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
                )
                with self.assertRaises(ValidationError) as caught:
                    Magazine(self.root).validate("issue-001")
                self.assertIn("source_ids", str(caught.exception))

    def test_an_article_row_requires_a_manuscript_and_never_a_fidelity_ledger(self):
        """The ledger was a required article key and is not one any more.

        What an article row cannot omit is the manuscript: the ledger was
        deleted outright, so a row that never mentions one is the normal shape,
        not a row awaiting a file.
        """
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        self.assertNotIn("fidelity", manifest["articles"][0])

        Magazine(self.root).validate("issue-001")

        manifest["articles"][0].pop("manuscript")
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
        with self.assertRaisesRegex(ValidationError, "Article article missing: manuscript"):
            Magazine(self.root).validate("issue-001")

    def test_load_edition_reads_an_unpinned_article_row_as_one_empty_pin_per_source(self):
        """Released editions predate committed extractions, so an article row
        with no ``source_body_sha256`` is a legal shape and still yields one
        pin slot per declared source rather than an empty tuple."""
        make_project(self.root)

        edition = Magazine(self.root).validate("issue-001")

        self.assertEqual(
            edition.articles[0].source_pins, (SourcePin("source-one", None),)
        )

    def test_load_edition_normalizes_the_single_source_pin_shape(self):
        make_project(self.root)
        body_sha256 = add_extraction(self.root)
        pin_article_source_hash(self.root, body_sha256)

        edition = Magazine(self.root).validate("issue-001")

        self.assertEqual(
            edition.articles[0].source_pins, (SourcePin("source-one", body_sha256),)
        )

    def test_load_edition_normalizes_the_multi_source_pin_mapping(self):
        """One pin per ``source_ids`` entry, in the row's declared order, so no
        source can hide behind another's hash."""
        make_project(self.root)
        add_source(self.root, "source-two")
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["articles"][0]["source_ids"] = ["source-two", "source-one"]
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
        one_sha256 = add_extraction(self.root)
        two_sha256 = add_extraction(
            self.root, source_id="source-two", body="Another article.\n"
        )
        pin_article_source_hash(
            self.root, {"source-one": one_sha256, "source-two": two_sha256}
        )

        edition = Magazine(self.root).validate("issue-001")

        self.assertEqual(
            edition.articles[0].source_pins,
            (SourcePin("source-two", two_sha256), SourcePin("source-one", one_sha256)),
        )

    def test_validate_rejects_a_malformed_source_pin_naming_the_article(self):
        """A malformed pin fails the manifest, not some later stage, and the
        error names the article row an author has to open."""
        make_project(self.root)
        pin_article_source_hash(self.root, "not-a-hash")

        with self.assertRaisesRegex(
            ValidationError,
            r"Article article: source_body_sha256 for source-one must be a 64-character",
        ):
            Magazine(self.root).validate("issue-001")

    def test_validate_rejects_a_bare_digest_for_a_multi_source_article(self):
        make_project(self.root)
        add_source(self.root, "source-two")
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["articles"][0]["source_ids"] = ["source-one", "source-two"]
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
        pin_article_source_hash(self.root, add_extraction(self.root))

        with self.assertRaisesRegex(
            ValidationError,
            r"Article article: source_body_sha256 must be a mapping keyed by source id",
        ):
            Magazine(self.root).validate("issue-001")

    def test_validate_rejects_a_pin_for_a_source_the_article_does_not_declare(self):
        make_project(self.root)
        pin_article_source_hash(
            self.root, {"source-one": add_extraction(self.root), "source-two": "0" * 64}
        )

        with self.assertRaisesRegex(
            ValidationError, "does not declare in source_ids: source-two"
        ):
            Magazine(self.root).validate("issue-001")

    def test_validate_allows_an_article_to_omit_author_note(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text())
        manifest["articles"][0].pop("author_note")
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

        result = Magazine(self.root).validate("issue-001")

        self.assertEqual(result.articles[0].author_note, "")

    def test_validate_rejects_an_overlong_article_author_note(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text())
        manifest["articles"][0]["author_note"] = "x" * 161
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "single line of at most 160"):
            Magazine(self.root).validate("issue-001")

    def test_validate_rejects_an_author_note_for_the_editors(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text())
        manifest["articles"][0]["author"] = "The Editors"
        manifest["articles"][0]["author_note"] = "The Editors summarize the sources."
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "must omit author_note"):
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

    def test_illustrated_article_opener_resolves_required_art(self):
        make_project(self.root)
        art_path = (
            self.root
            / "editions"
            / "issue-001"
            / "art"
            / "article-opener.png"
        )
        Image.new("RGB", (1600, 900), "white").save(art_path)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["format"] = {
            "article_opener": "illustrated_paper_spots_v1"
        }
        manifest["art_direction_path"] = "art/illustrations.yaml"
        manifest["articles"][0]["opener_art"] = {
            "path": "art/article-opener.png",
            "alt_text": "A boy and robot connect two systems.",
            "credit": "Original illustration.",
        }
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )

        edition = load_edition(self.root, "issue-001", {"source-one"})

        self.assertEqual(
            edition.raw["format"]["article_opener"],
            "illustrated_paper_spots_v1",
        )
        self.assertEqual(edition.articles[0].opener_art.path, art_path.resolve())
        self.assertEqual(
            edition.articles[0].opener_art.alt_text,
            "A boy and robot connect two systems.",
        )
        self.assertEqual(
            edition.articles[0].opener_art.credit, "Original illustration."
        )

    def test_illustrated_article_opener_requires_an_illustration_plan(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["format"] = {
            "article_opener": "illustrated_paper_spots_v1"
        }
        manifest["articles"][0]["opener_art"] = {
            "path": "art/article-opener.png",
            "alt_text": "A boy and robot connect two systems.",
            "credit": "Original illustration.",
        }
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )

        with self.assertRaisesRegex(ValidationError, "requires art_direction_path"):
            load_edition(
                self.root,
                "issue-001",
                {"source-one"},
                allow_missing_art=True,
            )

    def test_illustrated_article_opener_requires_author_biography(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["format"] = {
            "article_opener": "illustrated_paper_spots_v1"
        }
        manifest["art_direction_path"] = "art/illustrations.yaml"
        manifest["articles"][0].pop("author_note")
        manifest["articles"][0]["opener_art"] = {
            "path": "art/article-opener.png",
            "alt_text": "A boy and robot connect two systems.",
            "credit": "Original illustration.",
        }
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )

        with self.assertRaisesRegex(ValidationError, "requires author_note"):
            load_edition(
                self.root,
                "issue-001",
                {"source-one"},
                allow_missing_art=True,
            )

    def test_illustrated_article_opener_exempts_the_house_byline(self):
        """An editor-voiced piece signs itself and has no biography to print.

        The house byline already refuses an ``author_note``, so requiring one
        here would leave ``in_a_nutshell`` and ``original_synthesis`` unusable
        in an illustrated edition -- no value of the field would validate.
        """

        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["format"] = {"article_opener": "illustrated_paper_spots_v1"}
        manifest["art_direction_path"] = "art/illustrations.yaml"
        manifest["articles"][0].pop("author_note")
        manifest["articles"][0]["author"] = "The editors"
        manifest["articles"][0]["content_mode"] = "in_a_nutshell"
        manifest["articles"][0]["opener_art"] = {
            "path": "art/article-opener.png",
            "alt_text": "A boy and robot connect two systems.",
            "credit": "Original illustration.",
        }
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )

        edition = load_edition(
            self.root, "issue-001", {"source-one"}, allow_missing_art=True
        )

        self.assertEqual(edition.articles[0].author, "The editors")
        self.assertEqual(edition.articles[0].author_note, "")

    def test_illustrated_article_opener_still_refuses_a_house_biography(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["format"] = {"article_opener": "illustrated_paper_spots_v1"}
        manifest["art_direction_path"] = "art/illustrations.yaml"
        manifest["articles"][0]["author"] = "The editors"
        manifest["articles"][0]["content_mode"] = "in_a_nutshell"
        manifest["articles"][0]["author_note"] = "The editors explain the source."
        manifest["articles"][0]["opener_art"] = {
            "path": "art/article-opener.png",
            "alt_text": "A boy and robot connect two systems.",
            "credit": "Original illustration.",
        }
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )

        with self.assertRaisesRegex(ValidationError, "must omit author_note"):
            load_edition(
                self.root, "issue-001", {"source-one"}, allow_missing_art=True
            )

    def test_illustrated_article_opener_requires_complete_art_mapping(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["format"] = {
            "article_opener": "illustrated_paper_spots_v1"
        }
        manifest["art_direction_path"] = "art/illustrations.yaml"
        manifest["articles"][0]["opener_art"] = {
            "path": "art/article-opener.png",
            "alt_text": "",
        }
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )

        with self.assertRaisesRegex(
            ValidationError, "opener_art requires non-empty alt_text, credit"
        ):
            load_edition(self.root, "issue-001", {"source-one"})

    def test_illustrated_article_opener_art_honors_missing_art_mode_and_safe_paths(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["format"] = {
            "article_opener": "illustrated_paper_spots_v1"
        }
        manifest["art_direction_path"] = "art/illustrations.yaml"
        manifest["articles"][0]["opener_art"] = {
            "path": "art/not-generated-yet.png",
            "alt_text": "A boy and robot connect two systems.",
            "credit": "Original illustration.",
        }
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )

        with self.assertRaisesRegex(ValidationError, "does not exist"):
            load_edition(self.root, "issue-001", {"source-one"})

        edition = load_edition(
            self.root,
            "issue-001",
            {"source-one"},
            allow_missing_art=True,
        )
        self.assertEqual(
            edition.articles[0].opener_art.path,
            (
                self.root
                / "editions"
                / "issue-001"
                / "art"
                / "not-generated-yet.png"
            ).resolve(),
        )

        manifest["articles"][0]["opener_art"]["path"] = "../../../outside.png"
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
        with self.assertRaisesRegex(ValidationError, "Path escapes project root"):
            load_edition(
                self.root,
                "issue-001",
                {"source-one"},
                allow_missing_art=True,
            )

    def test_illustrated_article_opener_requires_opening_paragraph(self):
        make_project(self.root)
        art_path = (
            self.root
            / "editions"
            / "issue-001"
            / "art"
            / "article-opener.png"
        )
        Image.new("RGB", (1600, 900), "white").save(art_path)
        manuscript_path = (
            self.root
            / "editions"
            / "issue-001"
            / "articles"
            / "article.md"
        )
        manuscript_path.write_text(
            "## A heading\n\nThe first paragraph.", encoding="utf-8"
        )
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["format"] = {
            "article_opener": "illustrated_paper_spots_v1"
        }
        manifest["art_direction_path"] = "art/illustrations.yaml"
        manifest["articles"][0]["opener_art"] = {
            "path": "art/article-opener.png",
            "alt_text": "A boy and robot connect two systems.",
            "credit": "Original illustration.",
        }
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )

        with self.assertRaisesRegex(
            ValidationError, "first manuscript block must be a paragraph"
        ):
            load_edition(self.root, "issue-001", {"source-one"})

    def test_validate_rejects_unknown_declared_edition_source(self):
        make_project(self.root)
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text())
        manifest["sources"] = ["missing-source"]
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "Edition references unknown sources"):
            Magazine(self.root).validate("issue-001")

    def test_validate_requires_the_release_ledger_file(self):
        """A missing release-state must not silently disable the extraction
        gate by defaulting the open edition id."""
        make_project(self.root)
        (self.root / "library" / "release-state.yaml").unlink()

        with self.assertRaisesRegex(ValidationError, "Release state not found"):
            Magazine(self.root).validate("issue-001")

    def test_open_edition_requires_an_extraction_and_pin_for_every_declared_source(self):
        """The reviewer's false pass, made structurally impossible.

        An article used to declare its sources twice -- once in ``source_ids``
        and once in its ledger -- and only the ledger's shorter list was
        verified, so article [a, b] with ledger [a] passed.  There is one list
        now, and it is the one the open edition holds to account: adding a
        source to the row immediately owes that source an extraction and a pin.
        """
        make_project(self.root)
        add_source(self.root, "source-two")
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["articles"][0]["source_ids"] = ["source-one", "source-two"]
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        pin_article_source_hash(self.root, {"source-one": add_extraction(self.root)})
        set_open_edition(self.root, "issue-001")

        with self.assertRaisesRegex(
            ValidationError,
            r"edition\.yaml: article article: source source-two has no committed extraction",
        ):
            Magazine(self.root).validate("issue-001")

        # Only the open edition is held to the full chain; pointing the release
        # ledger at another edition restores released-edition behavior, where
        # pins are verified opportunistically.
        set_open_edition(self.root, "999-unreleased", issue_number=999)
        Magazine(self.root).validate("issue-001")

    def test_open_edition_requires_a_pin_for_a_source_it_already_extracted(self):
        """An extraction without a pin proves nothing about *this* article: it
        records that the source was captured, not which capture was written
        from.  The error carries the digest to paste in."""
        make_project(self.root)
        body_sha256 = add_extraction(self.root)
        set_open_edition(self.root, "issue-001")

        with self.assertRaisesRegex(
            ValidationError,
            rf"declares no source_body_sha256 for source-one; pin the extraction "
            rf"body hash {body_sha256}",
        ):
            Magazine(self.root).validate("issue-001")

        pin_article_source_hash(self.root, body_sha256)
        Magazine(self.root).validate("issue-001")

    def test_validate_rejects_a_pin_that_no_longer_matches_the_extraction(self):
        """Unconditional, released editions included: a pin and an extraction
        that both exist must agree, or the source moved underneath the
        manuscript after it was written."""
        make_project(self.root)
        add_extraction(self.root)
        pin_article_source_hash(self.root, "0" * 64)

        with self.assertRaisesRegex(
            ValidationError, "no longer matches the committed extraction"
        ):
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

    def test_translation_localizes_the_article_author_when_declared(self):
        make_project(self.root)
        add_spanish_translation(self.root)
        translation_path = (
            self.root / "editions" / "issue-001" / "translations" / "es" / "edition.yaml"
        )
        translation = yaml.safe_load(translation_path.read_text(encoding="utf-8"))
        translation["articles"][0]["author"] = "La redacción"
        translation_path.write_text(
            yaml.safe_dump(translation, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        base = Magazine(self.root).validate("issue-001")

        localized = load_translation(self.root.resolve(), base, "es")

        self.assertEqual(localized.articles[0].author, "La redacción")

    def test_translation_without_an_author_keeps_the_base_byline(self):
        make_project(self.root)
        add_spanish_translation(self.root)
        base = Magazine(self.root).validate("issue-001")

        localized = load_translation(self.root.resolve(), base, "es")

        self.assertEqual(localized.articles[0].author, base.articles[0].author)

    def test_translation_refuses_a_blank_author(self):
        make_project(self.root)
        add_spanish_translation(self.root)
        translation_path = (
            self.root / "editions" / "issue-001" / "translations" / "es" / "edition.yaml"
        )
        translation = yaml.safe_load(translation_path.read_text(encoding="utf-8"))
        translation["articles"][0]["author"] = "   "
        translation_path.write_text(
            yaml.safe_dump(translation, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )

        with self.assertRaisesRegex(ValidationError, "author cannot be blank"):
            Magazine(self.root).validate("issue-001")

    def test_translation_carries_the_base_article_source_pins_through_unchanged(self):
        """A translation renders the same article from the same sources.

        Provenance belongs to the article, not to the language, so the overlay
        neither re-derives nor re-pins it -- and it re-emits the pin into the
        translated raw manifest in the shape ``edition.yaml`` authors it, so a
        consumer reading the localized manifest sees the same declaration.
        """
        make_project(self.root)
        body_sha256 = add_extraction(self.root)
        pin_article_source_hash(self.root, body_sha256)
        add_spanish_translation(self.root)
        base = Magazine(self.root).validate("issue-001")

        localized = load_translation(self.root.resolve(), base, "es")

        self.assertEqual(
            localized.articles[0].source_pins, (SourcePin("source-one", body_sha256),)
        )
        self.assertEqual(
            localized.articles[0].source_pins, base.articles[0].source_pins
        )
        row = localized.raw["articles"][0]
        self.assertEqual(row["source_ids"], ["source-one"])
        self.assertEqual(row["source_body_sha256"], body_sha256)

    def test_translation_re_emits_multi_source_pins_as_a_mapping(self):
        make_project(self.root)
        add_source(self.root, "source-two")
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["articles"][0]["source_ids"] = ["source-one", "source-two"]
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
        one_sha256 = add_extraction(self.root)
        two_sha256 = add_extraction(
            self.root, source_id="source-two", body="Another article.\n"
        )
        pin_article_source_hash(
            self.root, {"source-one": one_sha256, "source-two": two_sha256}
        )
        add_spanish_translation(self.root)
        base = Magazine(self.root).validate("issue-001")

        localized = load_translation(self.root.resolve(), base, "es")

        self.assertEqual(
            localized.raw["articles"][0]["source_body_sha256"],
            {"source-one": one_sha256, "source-two": two_sha256},
        )

    def test_translation_of_an_unpinned_article_emits_no_source_pin(self):
        """A released edition has nothing to pin, and the overlay must not
        invent a digest to fill the key."""
        make_project(self.root)
        add_spanish_translation(self.root)
        base = Magazine(self.root).validate("issue-001")

        localized = load_translation(self.root.resolve(), base, "es")

        self.assertEqual(
            localized.articles[0].source_pins, (SourcePin("source-one", None),)
        )
        self.assertIsNone(localized.raw["articles"][0]["source_body_sha256"])

    def test_validate_rejects_translation_after_english_source_changes(self):
        make_project(self.root)
        add_spanish_translation(self.root)
        editorial = self.root / "editions" / "issue-001" / "editorial.md"
        editorial.write_text(
            "---\ntitle: A Test Editorial\nbyline: The editors\nlabel: ORIGINAL EDITORIAL\n---\n\nA revised argument.",
            encoding="utf-8",
        )

        # The error must state the digest the overlay should carry, so the fix
        # is a review followed by a re-pin rather than a shasum expedition.
        expected = hashlib.sha256(editorial.read_bytes()).hexdigest()
        with self.assertRaisesRegex(
            ValidationError,
            rf"is stale: source_sha256 is .* but editorial\.md hashes to {expected}",
        ):
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

        expected = caption_sha256("diagram", "The source diagram.")
        with self.assertRaisesRegex(
            ValidationError,
            rf"caption pin is stale: .* the base caption hashes to {expected}",
        ):
            load_translation(self.root.resolve(), base, "es")

    STRUCTURED_ARTICLE = (
        "The original article.\n\n"
        "1. First point\n2. Second point\n\n"
        "---\n\n"
        "- Outer point\n  - Inner point\n\n"
        "> A quoted claim.\n>\n> Its continuation.\n"
    )
    STRUCTURED_TRANSLATION = (
        "El artículo original.\n\n"
        "1. Primer punto\n2. Segundo punto\n\n"
        "---\n\n"
        "- Punto exterior\n  - Punto interior\n\n"
        "> Una afirmación citada.\n>\n> Su continuación.\n"
    )

    def _project_with_structured_article(self):
        """A project whose article uses edition 003's vocabulary: ordered and
        nested lists, a thematic break, and a multi-child block quote."""
        make_project(self.root)
        article = self.root / "editions" / "issue-001" / "articles" / "article.md"
        article.write_text(self.STRUCTURED_ARTICLE, encoding="utf-8")
        add_spanish_translation(self.root)
        return self.root / "editions" / "issue-001" / "translations" / "es" / "articles" / "article.md"

    def _structured_base(self):
        # ``Magazine.validate`` itself validates every configured translation,
        # so the refusal tests load the base edition directly and point the
        # translation gate at it.
        return load_edition(
            self.root.resolve(), "issue-001", {"source-one"}, publication_name="Test Review"
        )

    def test_translation_preserving_lists_breaks_and_quotes_validates(self):
        translated = self._project_with_structured_article()
        translated.write_text(self.STRUCTURED_TRANSLATION, encoding="utf-8")

        # The full validation gate, translations included, accepts it.
        edition = Magazine(self.root).validate("issue-001")

        localized = load_translation(self.root.resolve(), self._structured_base(), "es")
        self.assertEqual(edition.articles[0].id, "article")
        self.assertEqual(localized.articles[0].title, "Artículo")

    def test_translation_flattening_an_ordered_list_into_prose_is_refused(self):
        # The historical blind spot: the old line scanner read `1. …` as a
        # paragraph, so a translation could fold the list into prose and the
        # reader would print an <ol> in one language and a <p> in the other.
        translated = self._project_with_structured_article()
        translated.write_text(
            self.STRUCTURED_TRANSLATION.replace(
                "1. Primer punto\n2. Segundo punto", "Primer punto. Segundo punto."
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            ValidationError, "does not preserve the source Markdown block structure"
        ):
            load_translation(self.root.resolve(), self._structured_base(), "es")

    def test_translation_dropping_a_thematic_break_is_refused(self):
        translated = self._project_with_structured_article()
        translated.write_text(
            self.STRUCTURED_TRANSLATION.replace("---\n\n", ""), encoding="utf-8"
        )

        with self.assertRaisesRegex(
            ValidationError, "does not preserve the source Markdown block structure"
        ):
            load_translation(self.root.resolve(), self._structured_base(), "es")

    def test_translation_regrouping_a_nested_list_is_refused(self):
        translated = self._project_with_structured_article()
        translated.write_text(
            self.STRUCTURED_TRANSLATION.replace(
                "- Punto exterior\n  - Punto interior",
                "- Punto exterior\n- Punto interior",
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            ValidationError, "does not preserve the source Markdown block structure"
        ):
            load_translation(self.root.resolve(), self._structured_base(), "es")

    def test_translation_with_unsupported_vocabulary_is_refused_naming_the_file(self):
        # A parse failure in the translated manuscript surfaces as a collected
        # gate error that names the malformed side and its path.
        translated = self._project_with_structured_article()
        translated.write_text(
            self.STRUCTURED_TRANSLATION + "\nUn párrafo con <span>x</span> HTML.\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            ValidationError,
            r"Translation 'es' article article translation .*translations.es.articles.article\.md "
            r"cannot be parsed as a publication document: "
            r"Unsupported Markdown inline token: html_inline",
        ):
            load_translation(self.root.resolve(), self._structured_base(), "es")

    def test_malformed_english_source_is_refused_naming_the_file(self):
        # The gate parses each side separately, so an unparseable English
        # source is reported with its own path rather than blamed on the
        # translation.
        translated = self._project_with_structured_article()
        translated.write_text(self.STRUCTURED_TRANSLATION, encoding="utf-8")
        base = self._structured_base()
        base.articles[0].manuscript.write_text(
            self.STRUCTURED_ARTICLE + "\nA paragraph with <span>x</span> HTML.\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            ValidationError,
            r"Translation 'es' article article English source .*articles.article\.md "
            r"cannot be parsed as a publication document: "
            r"Unsupported Markdown inline token: html_inline",
        ):
            load_translation(self.root.resolve(), base, "es")
