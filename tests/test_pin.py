"""The pin refresher: recompute by machine what authors used to shasum by hand.

Every fixture here starts from ``test_manifest.make_project`` -- the same
minimal project the manifest gate is tested against -- because the refresher's
whole contract is "whatever validation expects, write that".  Each test then
makes exactly one thing stale, runs ``refresh_pins``, and checks three facts:
the report names the moved pins, the file moved *only* by those digests, and
the validation gate is satisfied again.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import unittest

import yaml

from magazine import Magazine, ValidationError
from magazine.manifest import load_translation
from magazine.media_schema import caption_sha256
from magazine.pin import refresh_pins

from test_manifest import (
    add_curated_figure,
    add_extraction,
    add_source,
    add_spanish_translation,
    load_edition_with_records,
    make_project,
    pin_ledger_source_hash,
)


def consistent_project(root: Path) -> None:
    """A project whose every derivable pin is already correct.

    The default ``make_project`` ledger carries no ``source_body_sha256`` at
    all (the released-edition shape); the refresher requires the key to exist,
    so the fixture commits an extraction and pins its true body hash before the
    Spanish overlay is written against the finished base.
    """
    make_project(root)
    pin_ledger_source_hash(root, add_extraction(root))
    add_spanish_translation(root)


class PinRefreshTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        # Resolved eagerly because refresh_pins resolves its root (macOS's
        # /var is a symlink to /private/var) and the report's paths must
        # compare equal to the fixture's.
        self.root = Path(self.temporary.name).resolve()

    def overlay_path(self) -> Path:
        return self.root / "editions" / "issue-001" / "translations" / "es" / "edition.yaml"

    def ledger_path(self) -> Path:
        return self.root / "editions" / "issue-001" / "fidelity" / "article.yaml"

    def test_a_fully_pinned_project_refreshes_as_a_no_op(self):
        consistent_project(self.root)
        overlay_before = self.overlay_path().read_bytes()
        ledger_before = self.ledger_path().read_bytes()

        report = refresh_pins(self.root, "issue-001")

        self.assertEqual(report.changes, ())
        self.assertEqual(report.files, ())
        self.assertEqual(self.overlay_path().read_bytes(), overlay_before)
        self.assertEqual(self.ledger_path().read_bytes(), ledger_before)

    def test_a_stale_editorial_pin_is_rewritten_and_validation_passes_again(self):
        consistent_project(self.root)
        editorial = self.root / "editions" / "issue-001" / "editorial.md"
        editorial.write_text(
            "---\ntitle: A Test Editorial\nbyline: The editors\nlabel: ORIGINAL EDITORIAL\n---\n\nA better argument.",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValidationError, "is stale"):
            Magazine(self.root).validate("issue-001")
        before = self.overlay_path().read_text(encoding="utf-8")

        report = refresh_pins(self.root, "issue-001")

        self.assertEqual(len(report.changes), 1)
        change = report.changes[0]
        self.assertEqual(change.path, self.overlay_path())
        self.assertEqual(change.pin, "editorial.source_sha256")
        self.assertEqual(change.new, hashlib.sha256(editorial.read_bytes()).hexdigest())
        # Minimal diff: the file after is the file before with exactly that
        # digest substituted -- comments, order, and wrapping all survive.
        self.assertEqual(
            self.overlay_path().read_text(encoding="utf-8"),
            before.replace(change.old, change.new),
        )
        Magazine(self.root).validate("issue-001")

    def test_a_stale_ledger_pin_is_recomputed_from_the_committed_extraction(self):
        make_project(self.root)
        body_sha256 = add_extraction(self.root)
        pin_ledger_source_hash(self.root, "0" * 64)
        with self.assertRaisesRegex(ValidationError, "no longer matches the committed extraction"):
            Magazine(self.root).validate("issue-001")

        report = refresh_pins(self.root, "issue-001")

        self.assertEqual(
            [(change.pin, change.old, change.new) for change in report.changes],
            [("source_body_sha256", "0" * 64, body_sha256)],
        )
        self.assertEqual(report.files, (self.ledger_path(),))
        Magazine(self.root).validate("issue-001")

    def test_a_mapping_shaped_ledger_keeps_its_json_styling_and_gets_both_pins(self):
        # Edition 003's multi-source ledgers are JSON written into a .yaml
        # file; the refresher must land on each per-source digest without
        # laundering the file through a YAML dumper.
        make_project(self.root)
        add_source(self.root, "source-two")
        first = add_extraction(self.root)
        second = add_extraction(self.root, source_id="source-two", body="Another article.\n")
        ledger = {
            "schema_version": 1,
            "source_ids": ["source-one", "source-two"],
            "source_body_sha256": {"source-one": "0" * 64, "source-two": "1" * 64},
            "paragraphs": [
                {"status": "retained", "source": "The original article.", "edited": "The original article."}
            ],
        }
        self.ledger_path().write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")

        report = refresh_pins(self.root, "issue-001")

        self.assertEqual(
            {(change.pin, change.new) for change in report.changes},
            {
                ("source_body_sha256[source-one]", first),
                ("source_body_sha256[source-two]", second),
            },
        )
        text = self.ledger_path().read_text(encoding="utf-8")
        self.assertTrue(text.startswith("{"))
        self.assertIn(f'"source-one": "{first}"', text)
        self.assertIn(f'"source-two": "{second}"', text)

    def test_stale_figure_caption_and_base_copy_pins_move_together(self):
        make_project(self.root)
        add_curated_figure(self.root)
        pin_ledger_source_hash(self.root, add_extraction(self.root))
        base = load_edition_with_records(self.root)
        add_spanish_translation(self.root)
        translation = yaml.safe_load(self.overlay_path().read_text(encoding="utf-8"))
        translation["articles"][0]["figures"] = [{
            "id": "diagram",
            "caption": "El diagrama de la fuente.",
            "credit": "Diagrama de la autora.",
            "alt_text": "Un diagrama del artículo fuente.",
            "anchor": "__opener__",
            "source_caption_sha256": "2" * 64,
            "source_credit_sha256": "3" * 64,
        }]
        self.overlay_path().write_text(
            yaml.safe_dump(translation, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        # A base caption edit is the everyday staleness event: it moves the
        # figure's caption pin *and* the whole-copy pin in the same stroke.
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["articles"][0]["figures"][0]["caption"] = "The source diagram, revised."
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

        report = refresh_pins(self.root, "issue-001")

        pins = {change.pin for change in report.changes}
        self.assertEqual(pins, {
            "base_copy_sha256",
            "articles[article].figures[diagram].source_caption_sha256",
            "articles[article].figures[diagram].source_credit_sha256",
        })
        caption_change = next(
            change for change in report.changes if "source_caption" in change.pin
        )
        self.assertEqual(
            caption_change.new, caption_sha256("diagram", "The source diagram, revised.")
        )
        base = load_edition_with_records(self.root)
        localized = load_translation(self.root.resolve(), base, "es")
        self.assertEqual(localized.articles[0].figures[0].caption, "El diagrama de la fuente.")

    def test_a_decoy_comment_cannot_absorb_a_folded_scalar_pin(self):
        # Exactly-one-match proves the digest is textually unique, and text
        # includes comments.  Spell the article's real pin as a folded scalar
        # -- a spelling the substitution pattern cannot see -- and plant the
        # same digest in a comment: the comment is now the only textual match,
        # so a refresh that trusted the match count would rewrite the comment,
        # report success, and leave the real pin stale.  The re-parse check
        # must catch this and refuse to write anything at all.
        consistent_project(self.root)
        overlay_text = self.overlay_path().read_text(encoding="utf-8")
        stale = yaml.safe_load(overlay_text)["articles"][0]["source_sha256"]
        self.overlay_path().write_text(
            overlay_text.replace(
                f"source_sha256: {stale}",
                f"# reviewed against source_sha256: {stale}\n"
                f"  source_sha256: >-\n    {stale}",
            ),
            encoding="utf-8",
        )
        # Now make the pin genuinely stale so the refresh has work to do.
        article = self.root / "editions" / "issue-001" / "articles" / "article.md"
        article.write_text("The original article, revised.", encoding="utf-8")
        before = self.overlay_path().read_bytes()

        with self.assertRaisesRegex(ValidationError, "respell the pin"):
            refresh_pins(self.root, "issue-001")

        self.assertEqual(self.overlay_path().read_bytes(), before)

    def test_a_failing_overlay_leaves_an_already_refreshed_ledger_unwritten(self):
        # Ledgers are prepared before overlays.  Make the ledger stale (so it
        # has a rewrite pending) and the overlay unrefreshable (its pin key
        # deleted): the raise from the overlay must mean *nothing* reached
        # disk, ledger included -- not a half-applied refresh whose report
        # was discarded with the exception.
        consistent_project(self.root)
        pin_ledger_source_hash(self.root, "0" * 64)
        translation = yaml.safe_load(self.overlay_path().read_text(encoding="utf-8"))
        del translation["articles"][0]["source_sha256"]
        self.overlay_path().write_text(
            yaml.safe_dump(translation, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        ledger_before = self.ledger_path().read_bytes()
        overlay_before = self.overlay_path().read_bytes()

        with self.assertRaisesRegex(ValidationError, "refresh never inserts keys"):
            refresh_pins(self.root, "issue-001")

        self.assertEqual(self.ledger_path().read_bytes(), ledger_before)
        self.assertEqual(self.overlay_path().read_bytes(), overlay_before)

    def test_a_digest_that_prefixes_a_sibling_value_matches_only_itself(self):
        # The editorial and the article pin share a key name; give the
        # editorial a stale digest that is a strict prefix of the article's.
        # Without a trailing boundary the editorial's pattern would count the
        # article's line as a second match and refuse a perfectly
        # unambiguous refresh.
        consistent_project(self.root)
        translation = yaml.safe_load(self.overlay_path().read_text(encoding="utf-8"))
        translation["editorial"]["source_sha256"] = "a" * 64
        translation["articles"][0]["source_sha256"] = "a" * 64 + "bc"
        self.overlay_path().write_text(
            yaml.safe_dump(translation, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )

        report = refresh_pins(self.root, "issue-001")

        self.assertEqual(
            {(change.pin, change.old) for change in report.changes},
            {
                ("editorial.source_sha256", "a" * 64),
                ("articles[article].source_sha256", "a" * 64 + "bc"),
            },
        )
        Magazine(self.root).validate("issue-001")

    def test_a_missing_pin_key_is_an_error_never_an_insertion(self):
        consistent_project(self.root)
        translation = yaml.safe_load(self.overlay_path().read_text(encoding="utf-8"))
        del translation["articles"][0]["source_sha256"]
        self.overlay_path().write_text(
            yaml.safe_dump(translation, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        before = self.overlay_path().read_bytes()

        with self.assertRaisesRegex(ValidationError, "refresh never inserts keys"):
            refresh_pins(self.root, "issue-001")

        self.assertEqual(self.overlay_path().read_bytes(), before)

    def test_a_ledger_without_the_pin_key_is_an_error(self):
        # make_project's default ledger has no source_body_sha256 at all --
        # the released-edition shape -- and the refresher must not invent one.
        make_project(self.root)
        add_extraction(self.root)

        with self.assertRaisesRegex(ValidationError, "refresh never inserts keys"):
            refresh_pins(self.root, "issue-001")

    def test_a_covered_source_without_an_extraction_cannot_be_refreshed(self):
        make_project(self.root)
        pin_ledger_source_hash(self.root, "0" * 64)

        with self.assertRaisesRegex(ValidationError, "no committed extraction"):
            refresh_pins(self.root, "issue-001")

    def test_review_records_are_refused_outright(self):
        make_project(self.root)
        pin_ledger_source_hash(self.root, add_extraction(self.root))
        reviews_dir = self.root / "editions" / "issue-001" / "reviews"
        reviews_dir.mkdir()
        moved = reviews_dir / "article.yaml"
        moved.write_bytes(self.ledger_path().read_bytes())
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["articles"][0]["fidelity"] = moved.relative_to(self.root).as_posix()
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "mag review record"):
            refresh_pins(self.root, "issue-001")


if __name__ == "__main__":
    unittest.main()
