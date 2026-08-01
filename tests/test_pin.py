"""The pin refresher: recompute by machine what authors used to shasum by hand.

Every fixture here starts from ``test_manifest.make_project`` -- the same
minimal project the manifest gate is tested against -- because the refresher's
whole contract is "whatever validation expects, write that".  Each test then
makes exactly one thing stale, runs ``refresh_pins``, and checks three facts:
the report names the moved pins, the file moved *only* by those digests, and
the validation gate is satisfied again.

Source provenance pins now live in ``edition.yaml`` beside the ``source_ids``
they pin, not in a per-article file of their own.  That collapses the old
one-file-per-article rewrite into a single rewrite of one hand-authored
manifest -- which is convenient, and also raises the stakes: a bad nested-YAML
edit no longer damages one article's bookkeeping, it damages the whole issue's
manifest.  Several tests below exist only to hold that blast radius at zero.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import os
import unittest
from unittest.mock import patch

import yaml

import magazine.pin as pin_module
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
    pin_article_source_hash,
    set_open_edition,
)


def consistent_project(root: Path) -> None:
    """A project whose every derivable pin is already correct.

    The default ``make_project`` article row carries no ``source_body_sha256``
    at all (the released-edition shape); the refresher requires the key to
    exist, so the fixture commits an extraction and pins its true body hash
    before the Spanish overlay is written against the finished base.
    """
    make_project(root)
    pin_article_source_hash(root, add_extraction(root))
    add_spanish_translation(root)


# A stale digest that is unambiguously a *string* to YAML.  ``"0" * 64`` reads
# back as the integer zero when it is written unquoted, which is a fixture
# hazard rather than a fact about the refresher.
STALE_DIGEST = "deadbeef" * 8


def hand_authored_articles_block(second_pin: str) -> str:
    """Two article rows as a person would actually type them.

    Blank lines, a leading comment, a mid-row comment, and a row that already
    carries its pin.  ``yaml.safe_dump`` would render none of this, so the only
    way to prove the structural repair leaves an author's manuscript alone is
    to start from text no dumper would produce.
    """
    return f"""articles:
  # The anchor piece: everything else in the issue answers it.
  - id: article
    title: Article
    short_title: Article
    opener_variant: edge_medallion
    author: Author
    author_note: Author is chief architect at Example Company.
    # Checked by hand against the archived capture on 2026-07-15.
    source_ids: [source-one]

    manuscript: editions/issue-001/articles/article.md
  - id: second
    title: Second
    short_title: Second
    opener_variant: split_axis
    author: Author

    # The second piece runs from its own source.
    author_note: Author is chief architect at Example Company.
    source_ids: [source-two]
    source_body_sha256: {second_pin}
    manuscript: editions/issue-001/articles/second.md
"""


def two_article_project(root: Path, *, second_pin: str | None = None) -> tuple[str, str]:
    """A collecting issue-001 with a hand-authored two-article manifest.

    The first row declares its source but no pin at all; the second row's pin
    is whatever the caller asks for (its true digest by default).  Returns both
    sources' true extraction body hashes.
    """
    make_project(root)
    add_source(root, "source-two")
    first = add_extraction(root)
    second = add_extraction(root, source_id="source-two", body="Another article.\n")
    (root / "editions" / "issue-001" / "articles" / "second.md").write_text(
        "Another article.", encoding="utf-8"
    )
    manifest_path = root / "editions" / "issue-001" / "edition.yaml"
    text = manifest_path.read_text(encoding="utf-8")
    head, separator, _ = text.partition("\narticles:\n")
    assert separator, "make_project's manifest no longer ends with its articles block"
    manifest_path.write_text(
        head + "\n" + hand_authored_articles_block(second if second_pin is None else second_pin),
        encoding="utf-8",
    )
    set_open_edition(root, "issue-001", source_ids=("source-one", "source-two"))
    return first, second


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

    def manifest_path(self) -> Path:
        return self.root / "editions" / "issue-001" / "edition.yaml"

    def manifest_data(self) -> dict:
        return yaml.safe_load(self.manifest_path().read_text(encoding="utf-8"))

    def article_pin(self, article: str = "article"):
        row = next(
            row for row in self.manifest_data()["articles"] if row["id"] == article
        )
        return row.get("source_body_sha256")

    def test_a_fully_pinned_project_refreshes_as_a_no_op(self):
        consistent_project(self.root)
        overlay_before = self.overlay_path().read_bytes()
        manifest_before = self.manifest_path().read_bytes()

        report = refresh_pins(self.root, "issue-001")

        self.assertEqual(report.changes, ())
        self.assertEqual(report.files, ())
        self.assertEqual(self.overlay_path().read_bytes(), overlay_before)
        self.assertEqual(self.manifest_path().read_bytes(), manifest_before)

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

    def test_a_stale_article_pin_is_recomputed_from_the_committed_extraction(self):
        make_project(self.root)
        body_sha256 = add_extraction(self.root)
        pin_article_source_hash(self.root, "0" * 64)
        with self.assertRaisesRegex(ValidationError, "no longer matches the committed extraction"):
            Magazine(self.root).validate("issue-001")
        before = self.manifest_path().read_text(encoding="utf-8")

        report = refresh_pins(self.root, "issue-001")

        self.assertEqual(
            [(change.pin, change.old, change.new) for change in report.changes],
            [("articles[article].source_body_sha256", "0" * 64, body_sha256)],
        )
        # One manifest rewritten, not one file per article: the pins of the
        # whole issue now move in a single atomic replacement.
        self.assertEqual(report.files, (self.manifest_path(),))
        self.assertEqual(
            self.manifest_path().read_text(encoding="utf-8"),
            before.replace("0" * 64, body_sha256),
        )
        Magazine(self.root).validate("issue-001")

    def test_a_mapping_shaped_pin_moves_each_per_source_digest_surgically(self):
        # A multi-source article keys its pins by source id.  Each per-source
        # digest must be found and replaced where the author wrote it, with the
        # surrounding manifest -- other articles, comments, key order --
        # untouched: the refresher never launders edition.yaml through a dumper.
        make_project(self.root)
        add_source(self.root, "source-two")
        first = add_extraction(self.root)
        second = add_extraction(self.root, source_id="source-two", body="Another article.\n")
        manifest_path = self.manifest_path()
        text = manifest_path.read_text(encoding="utf-8")
        manifest_path.write_text(
            text.replace(
                "- id: article\n",
                "# The issue's only piece, written from two captures.\n- id: article\n",
            ).replace(
                "  source_ids:\n  - source-one\n",
                "  source_ids:\n  - source-one\n  - source-two\n"
                "  source_body_sha256:\n"
                f"    source-one: {'a' * 64}\n"
                f"    source-two: {'b' * 64}\n",
            ),
            encoding="utf-8",
        )
        before = manifest_path.read_text(encoding="utf-8")

        report = refresh_pins(self.root, "issue-001")

        self.assertEqual(
            {(change.pin, change.new) for change in report.changes},
            {
                ("articles[article].source_body_sha256[source-one]", first),
                ("articles[article].source_body_sha256[source-two]", second),
            },
        )
        self.assertEqual(
            manifest_path.read_text(encoding="utf-8"),
            before.replace("a" * 64, first).replace("b" * 64, second),
        )
        Magazine(self.root).validate("issue-001")

    def test_stale_figure_caption_and_base_copy_pins_move_together(self):
        make_project(self.root)
        add_curated_figure(self.root)
        pin_article_source_hash(self.root, add_extraction(self.root))
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
        manifest_path = self.manifest_path()
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

    def test_the_manifest_and_an_overlay_are_refreshed_in_one_batch(self):
        # The manifest and the overlays are two different hand-authored files
        # with two different kinds of pin, and an author who edits a manuscript
        # and re-extracts its source has made both stale at once.  One run must
        # settle both, and the report must name both files.
        consistent_project(self.root)
        pin_article_source_hash(self.root, "0" * 64)
        article = self.root / "editions" / "issue-001" / "articles" / "article.md"
        article.write_text("The original article, revised.", encoding="utf-8")
        with self.assertRaises(ValidationError):
            Magazine(self.root).validate("issue-001")

        report = refresh_pins(self.root, "issue-001")

        self.assertEqual(report.files, (self.manifest_path(), self.overlay_path()))
        self.assertEqual(
            {(change.path, change.pin) for change in report.changes},
            {
                (self.manifest_path(), "articles[article].source_body_sha256"),
                (self.overlay_path(), "articles[article].source_sha256"),
            },
        )
        Magazine(self.root).validate("issue-001")

    def test_a_failing_overlay_leaves_the_already_refreshed_manifest_unwritten(self):
        # The manifest is prepared before the overlays.  Make the manifest pin
        # stale (so it has a rewrite pending) and the overlay unrefreshable (its
        # pin key deleted): the raise from the overlay must mean *nothing*
        # reached disk, the manifest included -- not a half-applied refresh
        # whose report was discarded with the exception.  All the pins of an
        # issue live in that one manifest now, so a half-applied batch would
        # leave every article's provenance in a state no author asked for.
        consistent_project(self.root)
        pin_article_source_hash(self.root, "0" * 64)
        translation = yaml.safe_load(self.overlay_path().read_text(encoding="utf-8"))
        del translation["articles"][0]["source_sha256"]
        self.overlay_path().write_text(
            yaml.safe_dump(translation, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        manifest_before = self.manifest_path().read_bytes()
        overlay_before = self.overlay_path().read_bytes()

        with self.assertRaisesRegex(ValidationError, "refresh never inserts keys"):
            refresh_pins(self.root, "issue-001")

        self.assertEqual(self.manifest_path().read_bytes(), manifest_before)
        self.assertEqual(self.overlay_path().read_bytes(), overlay_before)

    def test_a_failing_overlay_leaves_a_pending_structural_repair_unwritten(self):
        # Same contract, but with the manifest's pending edit being a structural
        # repair rather than a digest substitution -- the repair writes through
        # a different code path (a composed-node splice, not a regex), and it
        # must respect the same verify-everything-then-write-everything rule.
        consistent_project(self.root)
        manifest = self.manifest_data()
        del manifest["articles"][0]["source_body_sha256"]
        self.manifest_path().write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
        set_open_edition(self.root, "issue-001", source_ids=("source-one",))
        translation = yaml.safe_load(self.overlay_path().read_text(encoding="utf-8"))
        del translation["articles"][0]["source_sha256"]
        self.overlay_path().write_text(
            yaml.safe_dump(translation, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        manifest_before = self.manifest_path().read_bytes()

        with self.assertRaisesRegex(ValidationError, "refresh never inserts keys"):
            refresh_pins(self.root, "issue-001")

        self.assertEqual(self.manifest_path().read_bytes(), manifest_before)

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

    def test_a_released_article_row_without_the_pin_key_is_an_error(self):
        # make_project's default article row has no source_body_sha256 at all
        # -- the released-edition shape, which is legal because released
        # editions predate committed extractions -- and issue-001 is not the
        # collecting edition, so the refresher must not invent a pin for it.
        # Only a collecting edition's structure is the machine's to derive.
        make_project(self.root)
        add_extraction(self.root)
        before = self.manifest_path().read_bytes()

        with self.assertRaisesRegex(ValidationError, "refresh never inserts keys"):
            refresh_pins(self.root, "issue-001")

        self.assertEqual(self.manifest_path().read_bytes(), before)

    def test_a_released_row_missing_one_of_its_mapped_pins_is_an_error(self):
        # The mapping shape has the same rule one level down: a released row
        # that pins one of its two sources and not the other is missing a key,
        # and refresh reports that rather than filling the gap in.
        make_project(self.root)
        add_source(self.root, "source-two")
        add_extraction(self.root)
        add_extraction(self.root, source_id="source-two", body="Another article.\n")
        manifest = self.manifest_data()
        manifest["articles"][0]["source_ids"] = ["source-one", "source-two"]
        manifest["articles"][0]["source_body_sha256"] = {"source-one": "0" * 64}
        self.manifest_path().write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
        before = self.manifest_path().read_bytes()

        with self.assertRaisesRegex(ValidationError, "refresh never inserts keys"):
            refresh_pins(self.root, "issue-001")

        self.assertEqual(self.manifest_path().read_bytes(), before)

    def test_a_collecting_article_row_gets_its_missing_derived_pin_by_machine(self):
        make_project(self.root)
        expected = add_extraction(self.root)
        set_open_edition(
            self.root,
            "issue-001",
            source_ids=("source-one",),
        )

        report = refresh_pins(self.root, "issue-001")

        self.assertEqual(len(report.changes), 1)
        self.assertEqual(report.changes[0].pin, "articles[article].source_body_sha256")
        self.assertEqual(report.changes[0].old, "<missing>")
        self.assertEqual(report.changes[0].new, expected)
        self.assertEqual(self.article_pin(), expected)

    def test_a_collecting_multi_source_row_gets_canonical_mapping_shape(self):
        # One digest cannot pin two sources.  A collecting row that says so is
        # malformed in a way the extractions themselves settle, so the repair
        # reshapes it rather than asking the author to retype two hashes.
        make_project(self.root)
        add_source(self.root, "source-two")
        first = add_extraction(self.root)
        second = add_extraction(
            self.root,
            source_id="source-two",
            body="Another article.\n",
        )
        manifest = self.manifest_data()
        manifest["articles"][0]["source_ids"] = ["source-one", "source-two"]
        manifest["articles"][0]["source_body_sha256"] = "0" * 64
        self.manifest_path().write_text(
            yaml.safe_dump(manifest, sort_keys=False),
            encoding="utf-8",
        )
        set_open_edition(
            self.root,
            "issue-001",
            source_ids=("source-one", "source-two"),
        )

        refresh_pins(self.root, "issue-001")

        self.assertEqual(
            self.article_pin(),
            {"source-one": first, "source-two": second},
        )

    def test_a_structural_repair_and_a_digest_refresh_share_one_manifest_rewrite(self):
        # Every article's pin lives in the same file now, so a single run can
        # have to insert one row's missing structure *and* move another row's
        # stale digest -- a splice and a substitution against the same text,
        # each of which must survive the other.  One file is rewritten; two
        # pins move.
        first, second = two_article_project(self.root, second_pin=STALE_DIGEST)

        report = refresh_pins(self.root, "issue-001")

        self.assertEqual(report.files, (self.manifest_path(),))
        self.assertEqual(
            [(change.pin, change.old, change.new) for change in report.changes],
            [
                ("articles[article].source_body_sha256", "<missing>", first),
                ("articles[second].source_body_sha256", STALE_DIGEST, second),
            ],
        )
        self.assertEqual(self.article_pin("article"), first)
        self.assertEqual(self.article_pin("second"), second)
        # And what the manifest loader reads back is what validation checks.
        base = load_edition_with_records(self.root)
        self.assertEqual(
            {
                article.id: tuple(pin.body_sha256 for pin in article.source_pins)
                for article in base.articles
            },
            {"article": (first,), "second": (second,)},
        )

    def test_two_articles_over_one_source_each_get_their_own_pin_moved(self):
        # Every article's pin used to live in its own ledger file, so a digest
        # was unique by construction.  They now share one ``edition.yaml``, and
        # two articles written from the same source carry the *same* digest
        # under the same key.  An unscoped textual search finds both and
        # refuses to move either -- precisely when a re-extraction has made the
        # refresh necessary.  The search is therefore scoped to the row.
        make_project(self.root)
        second_article = self.root / "editions" / "issue-001" / "articles" / "second.md"
        second_article.write_text("The original article.", encoding="utf-8")
        original = add_extraction(self.root)
        manifest = self.manifest_path()
        data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        row = dict(data["articles"][0])
        row.update({"id": "second", "title": "Second", "short_title": "Second",
                    "opener_variant": "split_axis",
                    "manuscript": "editions/issue-001/articles/second.md"})
        data["articles"] = [
            {**data["articles"][0], "source_body_sha256": original},
            {**row, "source_body_sha256": original},
        ]
        manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        set_open_edition(self.root, "issue-001", source_ids=("source-one",))
        self.assertEqual(refresh_pins(self.root, "issue-001").changes, ())

        # Re-extract the shared source: both rows are now stale by the same
        # digest, and both must move.
        revised = add_extraction(self.root, body="The original article, revised.\n")
        second_article.write_text("The original article, revised.", encoding="utf-8")
        (self.root / "editions" / "issue-001" / "articles" / "article.md").write_text(
            "The original article, revised.", encoding="utf-8"
        )

        report = refresh_pins(self.root, "issue-001")

        self.assertEqual(
            [(change.pin, change.old, change.new) for change in report.changes],
            [
                ("articles[article].source_body_sha256", original, revised),
                ("articles[second].source_body_sha256", original, revised),
            ],
        )
        self.assertEqual(self.article_pin("article"), revised)
        self.assertEqual(self.article_pin("second"), revised)
        Magazine(self.root).validate("issue-001")

    def test_a_structural_repair_preserves_unrelated_keys_comments_and_blank_lines(self):
        # The repair edits one entry of one row inside a file that carries the
        # whole issue.  Everything else -- the other row, the comments, the
        # blank lines, the inline ``source_ids`` flow sequence the author chose
        # -- must come through byte-for-byte.  Asserting the exact expected text
        # is the point: a diff-shaped assertion is the only one that fails when
        # a nested edit quietly reflows the file.
        first, _ = two_article_project(self.root)
        before = self.manifest_path().read_text(encoding="utf-8")

        report = refresh_pins(self.root, "issue-001")

        self.assertEqual(len(report.changes), 1)
        self.assertEqual(
            self.manifest_path().read_text(encoding="utf-8"),
            before.replace(
                "\n    manuscript: editions/issue-001/articles/article.md\n",
                f"\n    source_body_sha256: {first}"
                "\n    manuscript: editions/issue-001/articles/article.md\n",
            ),
        )

    def test_a_structural_repair_keeps_the_comments_around_the_key_it_replaces(self):
        # The replacement branch splices over the lines the old entry occupied,
        # which is where an author's annotation of *why* a pin says what it says
        # would be.  Comments and blank lines between the repaired key and the
        # next one survive the splice.
        make_project(self.root)
        add_source(self.root, "source-two")
        first = add_extraction(self.root)
        second = add_extraction(self.root, source_id="source-two", body="Another article.\n")
        manifest_path = self.manifest_path()
        manifest_path.write_text(
            manifest_path.read_text(encoding="utf-8").replace(
                "  source_ids:\n  - source-one\n",
                "  source_ids:\n  - source-one\n  - source-two\n"
                f"  source_body_sha256: {STALE_DIGEST}\n"
                "  # Re-pinned after the second capture was re-extracted.\n"
                "\n",
            ),
            encoding="utf-8",
        )
        set_open_edition(
            self.root, "issue-001", source_ids=("source-one", "source-two")
        )
        before = manifest_path.read_text(encoding="utf-8")

        refresh_pins(self.root, "issue-001")

        after = manifest_path.read_text(encoding="utf-8")
        self.assertEqual(
            after,
            before.replace(
                f"  source_body_sha256: {STALE_DIGEST}\n",
                "  source_body_sha256:\n"
                f"    source-one: {first}\n"
                f"    source-two: {second}\n",
            ),
        )
        self.assertIn(
            "  # Re-pinned after the second capture was re-extracted.\n\n", after
        )

    def test_a_covered_source_without_an_extraction_cannot_be_refreshed(self):
        make_project(self.root)
        pin_article_source_hash(self.root, "0" * 64)

        with self.assertRaisesRegex(ValidationError, "no committed extraction"):
            refresh_pins(self.root, "issue-001")

    def test_within_confines_the_sweep_to_the_named_directory(self):
        # A manifest whose pin key is missing aborts the whole edition-wide
        # sweep; scoped to the overlay directory, the manifest is not this
        # refresh's business -- not read, not required, not written -- and
        # the overlay's own stale pin is still repaired.
        consistent_project(self.root)
        manifest = self.manifest_data()
        del manifest["articles"][0]["source_body_sha256"]
        self.manifest_path().write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
        article = self.root / "editions" / "issue-001" / "articles" / "article.md"
        article.write_text("The original article, revised.", encoding="utf-8")
        manifest_before = self.manifest_path().read_bytes()

        # The default sweep still demands the whole edition be refreshable.
        with self.assertRaisesRegex(ValidationError, "refresh never inserts keys"):
            refresh_pins(self.root, "issue-001")

        report = refresh_pins(
            self.root, "issue-001", within=[self.overlay_path().parent]
        )

        self.assertEqual(
            [change.pin for change in report.changes],
            ["articles[article].source_sha256"],
        )
        self.assertEqual(report.files, (self.overlay_path(),))
        self.assertEqual(self.manifest_path().read_bytes(), manifest_before)

    def test_review_records_are_refused_outright(self):
        # A review record is a signed statement of what a reviewer actually
        # saw.  Nothing in this module may rewrite one, whatever pins it
        # happens to carry, and the refusal names the command that is allowed
        # to write it.  The guard is checked on the resolved path, so pointing
        # a pinned location at a review record through a symlink is refused
        # too -- which is the only way a real sweep could reach one.
        make_project(self.root)
        pin_article_source_hash(self.root, add_extraction(self.root))
        edition_dir = self.root / "editions" / "issue-001"
        reviews_dir = edition_dir / "reviews"
        (reviews_dir / "es").mkdir(parents=True)
        record = reviews_dir / "es" / "edition.yaml"
        record.write_text(
            "schema_version: 2\nrecorded_at: 2026-07-15T12:00:00Z\n"
            f"base_copy_sha256: {'0' * 64}\n",
            encoding="utf-8",
        )
        before = record.read_bytes()

        with self.assertRaisesRegex(ValidationError, "mag review record"):
            pin_module._PinnedFile(record, reviews_dir)

        translations_dir = edition_dir / "translations"
        translations_dir.mkdir()
        (translations_dir / "es").symlink_to(reviews_dir / "es", target_is_directory=True)

        with self.assertRaisesRegex(ValidationError, "mag review record"):
            refresh_pins(self.root, "issue-001")

        self.assertEqual(record.read_bytes(), before)

    def test_write_failure_rolls_back_every_pin_file(self):
        consistent_project(self.root)
        pin_article_source_hash(self.root, "0" * 64)
        article = self.root / "editions" / "issue-001" / "articles" / "article.md"
        article.write_text("The original article, revised.\n", encoding="utf-8")
        manifest_before = self.manifest_path().read_bytes()
        overlay_before = self.overlay_path().read_bytes()
        real_replace = os.replace
        calls = 0

        def fail_second(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected pin replacement failure")
            return real_replace(source, destination)

        with patch("magazine.pin.os.replace", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "injected pin replacement failure"):
                refresh_pins(self.root, "issue-001")

        self.assertEqual(self.manifest_path().read_bytes(), manifest_before)
        self.assertEqual(self.overlay_path().read_bytes(), overlay_before)

    def test_concurrent_pin_file_edit_aborts_before_writes_and_is_preserved(self):
        consistent_project(self.root)
        pin_article_source_hash(self.root, "0" * 64)
        article = self.root / "editions" / "issue-001" / "articles" / "article.md"
        article.write_text("The original article, revised.\n", encoding="utf-8")
        manifest_before = self.manifest_path().read_bytes()
        real_replace = os.replace
        calls = 0

        def concurrent_edit(source, destination):
            nonlocal calls
            calls += 1
            if calls == 1:
                with self.overlay_path().open("a", encoding="utf-8") as handle:
                    handle.write("# concurrent translator note\n")
            return real_replace(source, destination)

        with patch("magazine.pin.os.replace", side_effect=concurrent_edit):
            with self.assertRaisesRegex(ValidationError, "stale"):
                refresh_pins(self.root, "issue-001")

        self.assertEqual(self.manifest_path().read_bytes(), manifest_before)
        self.assertTrue(
            self.overlay_path().read_text(encoding="utf-8").endswith(
                "# concurrent translator note\n"
            )
        )

    def test_destination_created_inside_pin_write_is_never_overwritten(self):
        consistent_project(self.root)
        pin_article_source_hash(self.root, "0" * 64)
        original_write = pin_module._PinnedFile.write
        injected = False

        def concurrent_write(pinned):
            nonlocal injected
            if pinned.path == self.manifest_path() and not injected:
                injected = True
                pinned.path.write_bytes(b"CONCURRENT EDIT")
            return original_write(pinned)

        with patch.object(
            pin_module._PinnedFile,
            "write",
            concurrent_write,
        ):
            with self.assertRaisesRegex(ValidationError, "preserved"):
                refresh_pins(self.root, "issue-001")

        self.assertEqual(self.manifest_path().read_bytes(), b"CONCURRENT EDIT")

    def test_invalid_edition_id_is_rejected_before_path_lookup(self):
        consistent_project(self.root)
        before = self.manifest_path().read_bytes()

        with self.assertRaisesRegex(ValidationError, "Edition id"):
            refresh_pins(self.root, "../outside")

        self.assertEqual(self.manifest_path().read_bytes(), before)

    def test_symlinked_edition_directory_is_rejected(self):
        consistent_project(self.root)
        editions_dir = self.root / "editions"
        (editions_dir / "linked-issue").symlink_to(
            editions_dir / "issue-001",
            target_is_directory=True,
        )

        with self.assertRaisesRegex(ValidationError, "symlink path component"):
            refresh_pins(self.root, "linked-issue")


if __name__ == "__main__":
    unittest.main()
