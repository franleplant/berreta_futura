import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from magazine.errors import ValidationError
from magazine.extraction import (
    SourcePin,
    load_extraction,
    normalize_source_pins,
    verify_source_extractions,
)


BODY = "The captured article body.\n\nA second paragraph.\n"
BODY_SHA = hashlib.sha256(BODY.encode("utf-8")).hexdigest()

LABEL = "editions/issue-001/edition.yaml: article some-article"


def write_source(sources_dir: Path, source_id: str = "source-one", *, bundle: str = "a" * 64) -> None:
    bundle_dir = sources_dir / source_id / "raw" / bundle
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "manifest.json").write_text("{}", encoding="utf-8")


def write_extraction(
    sources_dir: Path,
    source_id: str = "source-one",
    *,
    bundle: str = "a" * 64,
    declared_source: str | None = None,
    method: str = "verbatim transcription of artifacts/article.txt",
    body: str = BODY,
) -> Path:
    path = sources_dir / source_id / "extracted.md"
    path.write_text(
        "---\n"
        "schema_version: 1\n"
        f"source_id: {declared_source or source_id}\n"
        f"raw_bundle: {bundle}\n"
        f"extraction_method: {method}\n"
        "---\n" + body,
        encoding="utf-8",
    )
    return path


class ExtractionLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.sources = Path(self.temporary.name)

    def test_body_hash_covers_exact_bytes_after_the_frontmatter_delimiter(self):
        write_source(self.sources)
        write_extraction(self.sources)

        extraction = load_extraction(self.sources, "source-one")

        self.assertEqual(extraction.body, BODY)
        self.assertEqual(extraction.body_sha256, BODY_SHA)
        self.assertEqual(extraction.raw_bundle, "a" * 64)

    def test_file_hash_covers_the_whole_file_frontmatter_included(self):
        write_source(self.sources)
        path = write_extraction(self.sources)

        extraction = load_extraction(self.sources, "source-one")

        self.assertEqual(
            extraction.file_sha256, hashlib.sha256(path.read_bytes()).hexdigest()
        )
        self.assertNotEqual(extraction.file_sha256, extraction.body_sha256)

    def test_missing_extraction_is_none_not_an_error(self):
        write_source(self.sources)
        self.assertIsNone(load_extraction(self.sources, "source-one"))

    def test_crlf_line_endings_are_rejected_not_normalized(self):
        write_source(self.sources)
        path = self.sources / "source-one" / "extracted.md"
        path.write_bytes(
            b"---\r\nschema_version: 1\r\nsource_id: source-one\r\n---\r\nBody.\r\n"
        )

        with self.assertRaisesRegex(
            ValidationError, r"extracted\.md.*carriage return"
        ):
            load_extraction(self.sources, "source-one")

    def test_a_lone_cr_anywhere_in_the_body_is_rejected(self):
        write_source(self.sources)
        write_extraction(self.sources, body="First line.\rSecond line.\n")

        with self.assertRaisesRegex(ValidationError, "carriage return"):
            load_extraction(self.sources, "source-one")

    def test_a_utf8_bom_is_rejected_naming_the_bom(self):
        write_source(self.sources)
        path = write_extraction(self.sources)
        path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())

        with self.assertRaisesRegex(ValidationError, "BOM"):
            load_extraction(self.sources, "source-one")

    def test_invalid_utf8_is_rejected_naming_the_file(self):
        write_source(self.sources)
        path = self.sources / "source-one" / "extracted.md"
        path.write_bytes(b"---\nschema_version: 1\n---\n\xff\xfe body\n")

        with self.assertRaisesRegex(ValidationError, r"extracted\.md.*not valid UTF-8"):
            load_extraction(self.sources, "source-one")

    def test_malformed_frontmatter_is_an_error_naming_the_file(self):
        write_source(self.sources)
        path = self.sources / "source-one" / "extracted.md"
        path.write_text("no frontmatter at all\n", encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "extracted.md.*frontmatter"):
            load_extraction(self.sources, "source-one")

    def test_extraction_must_reference_a_committed_raw_bundle(self):
        write_source(self.sources)
        write_extraction(self.sources, bundle="b" * 64)

        with self.assertRaisesRegex(ValidationError, "not a committed raw bundle"):
            load_extraction(self.sources, "source-one")

    def test_extraction_source_id_must_match_its_directory(self):
        write_source(self.sources)
        write_extraction(self.sources, declared_source="another-source")

        with self.assertRaisesRegex(ValidationError, "does not match source"):
            load_extraction(self.sources, "source-one")

    def test_extraction_requires_method_and_nonempty_body(self):
        write_source(self.sources)
        write_extraction(self.sources, method="", body="   \n")

        with self.assertRaises(ValidationError) as caught:
            load_extraction(self.sources, "source-one")

        message = str(caught.exception)
        self.assertIn("extraction_method", message)
        self.assertIn("body is empty", message)


class SourcePinNormalizationTests(unittest.TestCase):
    """``source_body_sha256`` in an article row, read as one pin per source."""

    def test_an_absent_declaration_yields_one_unpinned_entry_per_source(self):
        """Released editions predate extractions, so unpinned is a legal shape.

        It is refused later, by ``verify_source_extractions``, and only for the
        open edition -- ``normalize_source_pins`` never guesses which edition it
        is reading."""
        self.assertEqual(
            normalize_source_pins(LABEL, ("a", "b"), None),
            (SourcePin("a", None), SourcePin("b", None)),
        )

    def test_single_source_article_declares_one_hex_digest(self):
        self.assertEqual(
            normalize_source_pins(LABEL, ("a",), BODY_SHA),
            (SourcePin("a", BODY_SHA),),
        )

    def test_multi_source_article_must_key_hashes_by_source_id(self):
        """A lone digest could only ever prove one of several sources."""
        with self.assertRaisesRegex(ValidationError, "mapping keyed by source id"):
            normalize_source_pins(LABEL, ("a", "b"), BODY_SHA)

        self.assertEqual(
            normalize_source_pins(LABEL, ("a", "b"), {"a": BODY_SHA}),
            (SourcePin("a", BODY_SHA), SourcePin("b", None)),
        )

    def test_pins_follow_the_declared_source_order_not_the_mapping_order(self):
        other = "b" * 64
        self.assertEqual(
            normalize_source_pins(LABEL, ("a", "b"), {"b": other, "a": BODY_SHA}),
            (SourcePin("a", BODY_SHA), SourcePin("b", other)),
        )

    def test_mapping_cannot_name_sources_the_article_does_not_declare(self):
        """A pin for a source outside ``source_ids`` verifies nothing and hides
        the fact that the article never read it."""
        with self.assertRaisesRegex(
            ValidationError, "does not declare in source_ids: c"
        ):
            normalize_source_pins(LABEL, ("a", "b"), {"c": BODY_SHA})

    def test_pins_must_be_lowercase_hex_sha256(self):
        for declared in ("not-a-hash", BODY_SHA.upper(), BODY_SHA[:-1]):
            with self.subTest(declared=declared):
                with self.assertRaisesRegex(ValidationError, "64-character"):
                    normalize_source_pins(LABEL, ("a",), declared)

        with self.assertRaisesRegex(ValidationError, "64-character"):
            normalize_source_pins(LABEL, ("a", "b"), {"a": "not-a-hash"})

    def test_a_present_but_mistyped_declaration_is_an_error_not_a_vacuous_pass(self):
        """A wrongly spelled pin must never read as "nothing to check"."""
        for declared in (7, True, [BODY_SHA], {"a": ["x"]}, {"a": None}):
            with self.subTest(declared=declared):
                with self.assertRaises(ValidationError):
                    normalize_source_pins(LABEL, ("a",), declared)

    def test_errors_are_prefixed_with_the_caller_s_label(self):
        """The label names the manifest and the article, because the reader of
        the error has to find the row that is wrong."""
        with self.assertRaisesRegex(ValidationError, r"article some-article"):
            normalize_source_pins(LABEL, ("a",), "not-a-hash")


class SourceExtractionVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.sources = self.root / "sources"

    def test_matching_pin_passes_and_returns_the_extraction(self):
        write_source(self.sources)
        write_extraction(self.sources)

        found = verify_source_extractions(
            LABEL, (SourcePin("source-one", BODY_SHA),), self.sources,
            require_extractions=True,
        )

        self.assertEqual([extraction.source_id for extraction in found], ["source-one"])
        self.assertEqual(found[0].body, BODY)

    def test_mismatching_pin_fails_whether_or_not_required(self):
        """The one unconditional rule: a pin and an extraction that both exist
        must agree, or the source moved underneath the manuscript."""
        write_source(self.sources)
        write_extraction(self.sources)

        for required in (True, False):
            with self.subTest(require_extractions=required):
                with self.assertRaisesRegex(
                    ValidationError, "no longer matches the committed extraction"
                ):
                    verify_source_extractions(
                        LABEL, (SourcePin("source-one", "0" * 64),), self.sources,
                        require_extractions=required,
                    )

    def test_released_edition_without_extraction_is_skipped(self):
        """Editions 001 and 002 pinned hashes before extractions existed."""
        write_source(self.sources)

        found = verify_source_extractions(
            LABEL, (SourcePin("source-one", "0" * 64),), self.sources,
            require_extractions=False,
        )

        self.assertEqual(found, ())

    def test_open_edition_requires_extraction_and_pin(self):
        write_source(self.sources)
        pins = (SourcePin("source-one", None),)

        with self.assertRaisesRegex(ValidationError, "has no committed extraction"):
            verify_source_extractions(
                LABEL, pins, self.sources, require_extractions=True
            )

        write_extraction(self.sources)
        with self.assertRaisesRegex(
            ValidationError, f"pin the extraction body hash {BODY_SHA}"
        ):
            verify_source_extractions(
                LABEL, pins, self.sources, require_extractions=True
            )

    def test_an_unpinned_released_article_with_an_extraction_is_accepted(self):
        """Released editions have nothing to compare, so absence is not drift --
        but the extraction is still returned for the code-fence check."""
        write_source(self.sources)
        write_extraction(self.sources)

        found = verify_source_extractions(
            LABEL, (SourcePin("source-one", None),), self.sources,
            require_extractions=False,
        )

        self.assertEqual([extraction.source_id for extraction in found], ["source-one"])

    def test_open_edition_with_zero_declared_sources_is_an_error(self):
        write_source(self.sources)

        self.assertEqual(
            verify_source_extractions(LABEL, (), self.sources, require_extractions=False),
            (),
        )

        with self.assertRaisesRegex(ValidationError, "declare the source_ids"):
            verify_source_extractions(LABEL, (), self.sources, require_extractions=True)

    def test_multi_source_article_verifies_each_source_pin(self):
        write_source(self.sources, "source-one")
        write_extraction(self.sources, "source-one")
        write_source(self.sources, "source-two", bundle="c" * 64)
        other_body = "Another captured body.\n"
        other_sha = hashlib.sha256(other_body.encode("utf-8")).hexdigest()
        write_extraction(self.sources, "source-two", bundle="c" * 64, body=other_body)

        found = verify_source_extractions(
            LABEL,
            (SourcePin("source-one", BODY_SHA), SourcePin("source-two", other_sha)),
            self.sources,
            require_extractions=True,
        )
        self.assertEqual(
            [extraction.source_id for extraction in found], ["source-one", "source-two"]
        )

        with self.assertRaisesRegex(ValidationError, "source-two"):
            verify_source_extractions(
                LABEL,
                (SourcePin("source-one", BODY_SHA), SourcePin("source-two", "0" * 64)),
                self.sources,
                require_extractions=True,
            )

    def test_extractions_come_back_in_declared_order_skipping_missing_ones(self):
        """The code-fence check reads the returned bodies, so their order is the
        article's declared source order and an uncaptured source is simply
        absent rather than a hole in the tuple."""
        write_source(self.sources, "source-one")
        write_extraction(self.sources, "source-one")
        write_source(self.sources, "source-two", bundle="c" * 64)
        write_source(self.sources, "source-three", bundle="d" * 64)
        third_body = "A third captured body.\n"
        write_extraction(self.sources, "source-three", bundle="d" * 64, body=third_body)

        found = verify_source_extractions(
            LABEL,
            (
                SourcePin("source-three", hashlib.sha256(third_body.encode("utf-8")).hexdigest()),
                SourcePin("source-two", None),
                SourcePin("source-one", BODY_SHA),
            ),
            self.sources,
            require_extractions=False,
        )

        self.assertEqual(
            [extraction.source_id for extraction in found],
            ["source-three", "source-one"],
        )

    def test_malformed_extraction_surfaces_through_verification(self):
        write_source(self.sources)
        (self.sources / "source-one" / "extracted.md").write_text("broken", encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "frontmatter"):
            verify_source_extractions(
                LABEL, (SourcePin("source-one", BODY_SHA),), self.sources,
                require_extractions=False,
            )

    def test_every_failing_source_is_reported_not_just_the_first(self):
        """Collected errors let an author fix a multi-source article in one
        pass instead of re-running validation per source."""
        write_source(self.sources, "source-one")
        write_extraction(self.sources, "source-one")
        write_source(self.sources, "source-two", bundle="c" * 64)

        with self.assertRaises(ValidationError) as caught:
            verify_source_extractions(
                LABEL,
                (SourcePin("source-one", "0" * 64), SourcePin("source-two", "1" * 64)),
                self.sources,
                require_extractions=True,
            )

        message = str(caught.exception)
        self.assertIn("source-one", message)
        self.assertIn("source-two", message)


if __name__ == "__main__":
    unittest.main()
