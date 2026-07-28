"""The translation stage: scaffold and reconcile overlays by machine.

Fixtures start from ``test_manifest.make_project`` -- the same minimal project
the manifest gate and the pin refresher are tested against -- because the
stage's contract is bounded by both: whatever it writes must satisfy the
translation gate, and whatever pins it refreshes must go through ``pin.py``.
Each test stages, then checks three facts: the files carry the structure and
pins validation expects, the report names every placeholder, advisory, and
dropped translation out loud, and nothing outside the overlay moved.

The last test runs against a copy of the real repository: edition 003's
Spanish overlay is fully translated and fully pinned, so staging it must be a
byte-for-byte no-op with an empty backlog.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
import hashlib
import shutil
import subprocess
import unittest

import yaml

from magazine import ValidationError
from magazine import pin as pin_module
from magazine.manifest import _edition_copy_sha256, load_translation
from magazine.media_schema import caption_sha256, credit_sha256
from magazine.translate_stage import stage_translation

from test_manifest import (
    add_curated_figure,
    add_extraction,
    add_spanish_translation,
    load_edition_with_records,
    make_project,
    pin_ledger_source_hash,
)

REPOSITORY = Path(__file__).resolve().parent.parent


def tree_digest(root: Path) -> dict[str, str]:
    """Every file under ``root`` and its content hash: the no-op oracle."""
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def add_second_article(root: Path) -> None:
    """A second English article, ledger pinned so the pin refresher can run."""
    edition_dir = root / "editions" / "issue-001"
    (edition_dir / "articles" / "second.md").write_text("A second article.", encoding="utf-8")
    (edition_dir / "fidelity" / "second.yaml").write_text(
        yaml.safe_dump({
            "schema_version": 1,
            "source_ids": ["source-one"],
            "source_body_sha256": hashlib.sha256(b"The original article.\n").hexdigest(),
            "paragraphs": [
                {"status": "retained", "source": "A second article.", "edited": "A second article."}
            ],
        }),
        encoding="utf-8",
    )
    manifest_path = edition_dir / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["articles"].append({
        "id": "second",
        "title": "A Second Article",
        "short_title": "Second Article",
        "opener_variant": "edge_medallion",
        "author": "Author",
        "author_note": "Author is principal engineer at Example Company.",
        "source_ids": ["source-one"],
        "manuscript": "editions/issue-001/articles/second.md",
        "fidelity": "editions/issue-001/fidelity/second.yaml",
    })
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def remove_article(root: Path, article_id: str) -> None:
    manifest_path = root / "editions" / "issue-001" / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["articles"] = [
        row for row in manifest["articles"] if row["id"] != article_id
    ]
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


class TranslateStageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        # Resolved eagerly: the stage resolves its root, and the report's
        # paths must compare equal to the fixture's.
        self.root = Path(self.temporary.name).resolve()

    def overlay_dir(self) -> Path:
        return self.root / "editions" / "issue-001" / "translations" / "es"

    def overlay_data(self) -> dict:
        return yaml.safe_load(
            (self.overlay_dir() / "edition.yaml").read_text(encoding="utf-8")
        )

    def test_a_missing_overlay_becomes_a_full_reported_skeleton(self):
        make_project(self.root)

        report = stage_translation(self.root, "issue-001", "es")

        # The structure mirrors the base and the manuscripts are English
        # copies -- structure-valid placeholders, not translations.
        english = self.root / "editions" / "issue-001" / "articles" / "article.md"
        copied = self.overlay_dir() / "articles" / "article.md"
        self.assertEqual(copied.read_bytes(), english.read_bytes())
        editorial = self.overlay_dir() / "editorial.md"
        self.assertEqual(
            editorial.read_bytes(),
            (self.root / "editions" / "issue-001" / "editorial.md").read_bytes(),
        )
        self.assertEqual(
            set(report.created),
            {self.overlay_dir() / "edition.yaml", copied, editorial},
        )
        # Every derivable pin is computed, not left for a later refresh.
        base = load_edition_with_records(self.root)
        data = self.overlay_data()
        self.assertEqual(data["base_copy_sha256"], _edition_copy_sha256(base))
        self.assertEqual(
            data["articles"][0]["source_sha256"],
            hashlib.sha256(english.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            data["editorial"]["source_sha256"],
            hashlib.sha256(
                (self.root / "editions" / "issue-001" / "editorial.md").read_bytes()
            ).hexdigest(),
        )
        # The backlog is loud: every prose field and manuscript is named.
        pointers = {item.pointer for item in report.placeholders}
        self.assertLessEqual(
            {
                "title",
                "cover.headline",
                "closing_plate_titles[1]",
                "closing_plate_titles[2]",
                "closing_plate_titles[3]",
                "editorial.manuscript",
                "articles[article].title",
                "articles[article].short_title",
                "articles[article].author_note",
                "articles[article].manuscript",
            },
            pointers,
        )
        untranslated_title = next(
            item for item in report.placeholders if item.pointer == "articles[article].title"
        )
        self.assertEqual(untranslated_title.english, "Article")
        self.assertEqual(untranslated_title.path, self.overlay_dir() / "edition.yaml")
        # The staged overlay passes the structural translation gate as-is.
        self.assertEqual(report.validation_errors, ())
        localized = load_translation(self.root, base, "es")
        self.assertEqual(localized.articles[0].title, "Article")
        # make_project does not configure "es", and the report says so.
        self.assertTrue(any("publication.languages" in note for note in report.notes))
        self.assertTrue(report.changed)

    def test_staging_twice_changes_nothing_the_second_time(self):
        make_project(self.root)
        stage_translation(self.root, "issue-001", "es")
        before = tree_digest(self.root)

        report = stage_translation(self.root, "issue-001", "es")

        self.assertFalse(report.changed)
        self.assertEqual(report.created, ())
        self.assertEqual(report.updated, ())
        self.assertEqual(report.pin_changes, ())
        self.assertEqual(report.dropped, ())
        self.assertEqual(tree_digest(self.root), before)
        # The untranslated backlog is state, not an event: it is reported
        # every run until a human translates it away.
        self.assertTrue(report.placeholders)

    def test_reconcile_repairs_pins_adds_placeholder_figures_and_advises(self):
        make_project(self.root)
        pin_ledger_source_hash(self.root, add_extraction(self.root))
        add_spanish_translation(self.root)
        # The everyday staleness event: the English manuscript is revised and
        # a figure is added, and the Spanish overlay knows about neither.
        english = self.root / "editions" / "issue-001" / "articles" / "article.md"
        english.write_text("The original article, revised.", encoding="utf-8")
        add_curated_figure(self.root)
        # The overlay is hand-authored; a reviewer's comment must survive the
        # reconcile, because edits are targeted splices, not a YAML round-trip.
        overlay_path = self.overlay_dir() / "edition.yaml"
        overlay_path.write_text(
            "# Revisado contra la base del 15 de julio.\n"
            + overlay_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        report = stage_translation(self.root, "issue-001", "es")

        self.assertIn(
            "# Revisado contra la base del 15 de julio.",
            overlay_path.read_text(encoding="utf-8"),
        )

        # The moved manuscript hash becomes a re-translation advisory...
        self.assertIn(
            "articles[article].manuscript",
            {advisory.pointer for advisory in report.advisories},
        )
        # ...and the pins themselves are repaired through pin.refresh_pins.
        moved = {change.pin for change in report.pin_changes}
        self.assertIn("articles[article].source_sha256", moved)
        self.assertIn("base_copy_sha256", moved)
        data = self.overlay_data()
        self.assertEqual(
            data["articles"][0]["source_sha256"],
            hashlib.sha256(english.read_bytes()).hexdigest(),
        )
        # The new figure arrives as an English placeholder row with correct
        # pins, and the placeholder is reported loudly.
        figure = data["articles"][0]["figures"][0]
        self.assertEqual(figure["caption"], "The source diagram.")
        self.assertEqual(
            figure["source_caption_sha256"], caption_sha256("diagram", "The source diagram.")
        )
        self.assertEqual(
            figure["source_credit_sha256"], credit_sha256("diagram", "Diagram by Author")
        )
        self.assertIn(
            "articles[article].figures[diagram].caption",
            {item.pointer for item in report.placeholders},
        )
        # The existing translation is never overwritten by staging.
        translated = self.overlay_dir() / "articles" / "article.md"
        self.assertEqual(translated.read_text(encoding="utf-8"), "El artículo original.")
        # After staging, the structural gate passes again.
        self.assertEqual(report.validation_errors, ())
        base = load_edition_with_records(self.root)
        localized = load_translation(self.root, base, "es")
        self.assertEqual(localized.articles[0].figures[0].caption, "The source diagram.")

    def test_a_dropped_article_is_reported_with_its_localized_prose(self):
        make_project(self.root)
        pin_ledger_source_hash(self.root, add_extraction(self.root))
        add_spanish_translation(self.root)
        add_second_article(self.root)
        first = stage_translation(self.root, "issue-001", "es")
        self.assertIn(
            "articles[second].title", {item.pointer for item in first.placeholders}
        )
        # A translator does the work the placeholder asked for...
        overlay_path = self.overlay_dir() / "edition.yaml"
        data = yaml.safe_load(overlay_path.read_text(encoding="utf-8"))
        row = next(row for row in data["articles"] if row["id"] == "second")
        row["title"] = "Un segundo artículo"
        row["short_title"] = "segundo artículo"
        overlay_path.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        # ...and then the English edition drops the article.
        remove_article(self.root, "second")

        report = stage_translation(self.root, "issue-001", "es")

        # The row is gone from the overlay, but the translation is not lost:
        # the report quotes the localized prose and the manuscript stays.
        dropped = next(item for item in report.dropped if item.pointer == "articles[second]")
        self.assertEqual(dropped.content["title"], "Un segundo artículo")
        self.assertTrue((self.overlay_dir() / "articles" / "second.md").is_file())
        data = self.overlay_data()
        self.assertEqual([row["id"] for row in data["articles"]], ["article"])
        self.assertEqual(report.validation_errors, ())

    def test_out_of_scope_staleness_is_reported_even_when_the_overlay_is_current(self):
        # A stale ledger pin used to surface only when the overlay itself
        # coincidentally needed a refresh; the staleness is state, so it must
        # be reported on every run -- read-only, never rewritten.
        make_project(self.root)
        pin_ledger_source_hash(self.root, add_extraction(self.root))
        add_spanish_translation(self.root)
        pin_ledger_source_hash(self.root, "0" * 64)
        before = tree_digest(self.root)

        report = stage_translation(self.root, "issue-001", "es")

        self.assertFalse(report.changed)
        self.assertEqual(tree_digest(self.root), before)
        self.assertTrue(
            any(
                "source_body_sha256[source-one]" in note and "fidelity" in note
                for note in report.notes
            ),
            report.notes,
        )

    def test_stale_read_only_ledgers_are_reported_never_rewritten(self):
        # The old edition-wide refresh prepared every ledger too; with two
        # stale ledgers and the second unwritable, its write loop could
        # rewrite the first and then die, leaving an out-of-scope file
        # silently changed.  Scoped staging never opens a ledger for writing,
        # so both keep their stale bytes and both are named in the notes.
        make_project(self.root)
        pin_ledger_source_hash(self.root, add_extraction(self.root))
        add_spanish_translation(self.root)
        add_second_article(self.root)
        pin_ledger_source_hash(self.root, "0" * 64)
        pin_ledger_source_hash(self.root, "0" * 64, article="second")
        fidelity = self.root / "editions" / "issue-001" / "fidelity"
        (fidelity / "second.yaml").chmod(0o444)
        self.addCleanup((fidelity / "second.yaml").chmod, 0o644)
        first_before = (fidelity / "article.yaml").read_bytes()
        second_before = (fidelity / "second.yaml").read_bytes()

        report = stage_translation(self.root, "issue-001", "es")

        self.assertEqual((fidelity / "article.yaml").read_bytes(), first_before)
        self.assertEqual((fidelity / "second.yaml").read_bytes(), second_before)
        stale_notes = [note for note in report.notes if "source_body_sha256" in note]
        self.assertEqual(len(stale_notes), 2, report.notes)
        # The staged overlay still got its own work done in full.
        self.assertEqual(
            [row["id"] for row in self.overlay_data()["articles"]],
            ["article", "second"],
        )
        self.assertIn(
            "base_copy_sha256", {change.pin for change in report.pin_changes}
        )

    def test_an_io_fault_mid_refresh_write_rolls_the_whole_run_back(self):
        # pin.refresh_pins verifies everything before writing anything, but
        # the write itself belongs to the operating system.  If it dies
        # mid-file, staging must put the manifest back and re-raise, so the
        # tree is byte-for-byte as found -- not left with a half-written
        # overlay and an exception that discarded the explanation.
        make_project(self.root)
        pin_ledger_source_hash(self.root, add_extraction(self.root))
        add_spanish_translation(self.root)
        english = self.root / "editions" / "issue-001" / "articles" / "article.md"
        english.write_text("The original article, revised.", encoding="utf-8")
        before = tree_digest(self.root)

        def dying_write(pinned):
            pinned.path.write_text(
                pinned.text[: len(pinned.text) // 2], encoding="utf-8"
            )
            raise OSError("disk full mid-write")

        with mock.patch.object(pin_module._PinnedFile, "write", dying_write):
            with self.assertRaisesRegex(OSError, "disk full"):
                stage_translation(self.root, "issue-001", "es")

        self.assertEqual(tree_digest(self.root), before)

    def test_sibling_overlays_stage_one_at_a_time_without_deadlock(self):
        # Two language overlays, a new English article, and a stale pin: the
        # edition-wide refresh used to demand every sibling already carry the
        # new row, so neither language could be staged -- the module's whole
        # purpose defeated.  Scoped to its own overlay, each stages in turn.
        make_project(self.root)
        pin_ledger_source_hash(self.root, add_extraction(self.root))
        add_spanish_translation(self.root)
        fr_dir = self.root / "editions" / "issue-001" / "translations" / "fr"
        shutil.copytree(self.overlay_dir(), fr_dir)
        fr_manifest = fr_dir / "edition.yaml"
        fr_manifest.write_text(
            fr_manifest.read_text(encoding="utf-8").replace(
                "language: es", "language: fr"
            ),
            encoding="utf-8",
        )
        add_second_article(self.root)
        fr_before = tree_digest(fr_dir)

        es_report = stage_translation(self.root, "issue-001", "es")

        # The sibling was neither written nor required to be consistent...
        self.assertEqual(tree_digest(fr_dir), fr_before)
        self.assertEqual(
            [row["id"] for row in self.overlay_data()["articles"]],
            ["article", "second"],
        )
        self.assertIn(
            "base_copy_sha256", {change.pin for change in es_report.pin_changes}
        )
        # ...but its missing row is still named out loud.
        self.assertTrue(
            any("'fr'" in note and "second" in note for note in es_report.notes),
            es_report.notes,
        )

        fr_report = stage_translation(self.root, "issue-001", "fr")

        fr_data = yaml.safe_load(fr_manifest.read_text(encoding="utf-8"))
        self.assertEqual(
            [row["id"] for row in fr_data["articles"]], ["article", "second"]
        )
        self.assertIn(
            "base_copy_sha256", {change.pin for change in fr_report.pin_changes}
        )

    def test_a_figure_row_missing_its_pin_keys_is_repaired_not_fatal(self):
        # A hand-authored figure row without its caption and credit pins used
        # to be fatal -- the refresher refuses to insert keys -- while an
        # article row's missing source_sha256 was repaired.  Reconcile now
        # inserts the missing pin keys with correct digests, and only those:
        # the translated prose is left exactly as found.
        make_project(self.root)
        add_curated_figure(self.root)
        add_spanish_translation(self.root)
        overlay_path = self.overlay_dir() / "edition.yaml"
        data = yaml.safe_load(overlay_path.read_text(encoding="utf-8"))
        data["articles"][0]["figures"] = [{
            "id": "diagram",
            "caption": "El diagrama de la fuente.",
            "credit": "Diagrama de la autora.",
            "alt_text": "Un diagrama del artículo fuente.",
            "anchor": "__opener__",
        }]
        overlay_path.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )

        report = stage_translation(self.root, "issue-001", "es")

        figure = self.overlay_data()["articles"][0]["figures"][0]
        self.assertEqual(figure["caption"], "El diagrama de la fuente.")
        self.assertEqual(
            figure["source_caption_sha256"],
            caption_sha256("diagram", "The source diagram."),
        )
        self.assertEqual(
            figure["source_credit_sha256"],
            credit_sha256("diagram", "Diagram by Author"),
        )
        self.assertEqual(report.validation_errors, ())

    def test_a_null_spelled_key_is_named_for_respelling(self):
        # A bare `closing_plate_titles:` line parses as null: the key exists,
        # so staging cannot insert it, and it carries nothing, so staging
        # cannot keep it.  The error must say to respell the empty key, not
        # read like an internal insertion bug.
        make_project(self.root)
        add_spanish_translation(self.root)
        overlay_path = self.overlay_dir() / "edition.yaml"
        text = overlay_path.read_text(encoding="utf-8")
        block = "closing_plate_titles:\n- Coda uno\n- Coda dos\n- Coda tres\n"
        self.assertIn(block, text)
        overlay_path.write_text(
            text.replace(block, "closing_plate_titles:\n"), encoding="utf-8"
        )
        before = tree_digest(self.root)

        with self.assertRaisesRegex(ValidationError, "respell the empty key"):
            stage_translation(self.root, "issue-001", "es")

        self.assertEqual(tree_digest(self.root), before)

    def test_staging_the_base_language_is_refused(self):
        make_project(self.root)

        with self.assertRaisesRegex(ValidationError, "base edition's own language"):
            stage_translation(self.root, "issue-001", "en")

        self.assertFalse(
            (self.root / "editions" / "issue-001" / "translations").exists()
        )

    def test_staging_the_real_edition_003_spanish_overlay_is_a_no_op(self):
        # The real overlay is fully translated and fully pinned, so staging it
        # must change nothing and report an empty backlog.  Run against a copy
        # -- the stage is exercised, the repository is not.
        copy = self.root / "repository"
        _copy_real_project(copy)
        before = tree_digest(copy)

        report = stage_translation(copy, "003-unreleased", "es")

        self.assertEqual(tree_digest(copy), before)
        self.assertFalse(report.changed)
        self.assertEqual(report.created, ())
        self.assertEqual(report.updated, ())
        self.assertEqual(report.pin_changes, ())
        self.assertEqual(report.dropped, ())
        self.assertEqual(report.advisories, ())
        self.assertEqual(report.placeholders, ())
        self.assertEqual(report.validation_errors, ())


def _copy_real_project(target: Path) -> None:
    """Copy just enough of the real repository to stage edition 003.

    The edition directory, its manifest's declared sources, and the project
    configuration; APFS clones when available so the 100 MB costs nothing.
    """
    target.mkdir(parents=True)
    shutil.copy2(REPOSITORY / "magazine.toml", target / "magazine.toml")
    _clone(
        REPOSITORY / "editions" / "003-unreleased",
        target / "editions" / "003-unreleased",
    )
    manifest = yaml.safe_load(
        (REPOSITORY / "editions" / "003-unreleased" / "edition.yaml").read_text(encoding="utf-8")
    )
    for source_id in manifest["sources"]:
        _clone(
            REPOSITORY / "library" / "sources" / source_id,
            target / "library" / "sources" / source_id,
        )


def _clone(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["cp", "-Rc", str(source), str(destination)],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        shutil.copytree(source, destination)


if __name__ == "__main__":
    unittest.main()
