import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from magazine.errors import ValidationError
from magazine.extraction import (
    declared_source_hashes,
    ledger_source_ids,
    load_extraction,
    verify_ledger_source_extractions,
)


BODY = "The captured article body.\n\nA second paragraph.\n"
BODY_SHA = hashlib.sha256(BODY.encode("utf-8")).hexdigest()


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


class LedgerSourceHashTests(unittest.TestCase):
    def test_ledger_source_ids_accepts_list_and_scalar_forms(self):
        self.assertEqual(
            ledger_source_ids(Path("l.yaml"), {"source_ids": ["a", "b"]}), ("a", "b")
        )
        self.assertEqual(ledger_source_ids(Path("l.yaml"), {"source_id": "a"}), ("a",))
        self.assertEqual(ledger_source_ids(Path("l.yaml"), {}), ())

    def test_mistyped_or_empty_source_ids_declaration_is_an_error(self):
        """A wrongly spelled declaration must never verify vacuously."""
        for declared in ("source-one", {"source-one": True}, [], [""]):
            with self.assertRaisesRegex(
                ValidationError, "source_ids must be a non-empty list", msg=repr(declared)
            ):
                ledger_source_ids(Path("l.yaml"), {"source_ids": declared})

    def test_mistyped_scalar_source_id_is_an_error(self):
        for declared in ("", ["a"], 7):
            with self.assertRaisesRegex(
                ValidationError, "source_id must be a non-empty source id", msg=repr(declared)
            ):
                ledger_source_ids(Path("l.yaml"), {"source_id": declared})

    def test_single_source_ledger_declares_one_hex_digest(self):
        declared = declared_source_hashes(Path("l.yaml"), {"source_body_sha256": BODY_SHA}, ("a",))
        self.assertEqual(declared, {"a": BODY_SHA})

    def test_multi_source_ledger_must_key_hashes_by_source_id(self):
        with self.assertRaisesRegex(ValidationError, "mapping keyed by source id"):
            declared_source_hashes(
                Path("l.yaml"), {"source_body_sha256": BODY_SHA}, ("a", "b")
            )

        declared = declared_source_hashes(
            Path("l.yaml"), {"source_body_sha256": {"a": BODY_SHA}}, ("a", "b")
        )
        self.assertEqual(declared, {"a": BODY_SHA, "b": None})

    def test_mapping_cannot_name_sources_the_ledger_does_not_cover(self):
        with self.assertRaisesRegex(ValidationError, "does not cover: c"):
            declared_source_hashes(
                Path("l.yaml"), {"source_body_sha256": {"c": BODY_SHA}}, ("a", "b")
            )

    def test_pins_must_be_lowercase_hex_sha256(self):
        with self.assertRaisesRegex(ValidationError, "64-character"):
            declared_source_hashes(
                Path("l.yaml"), {"source_body_sha256": "not-a-hash"}, ("a",)
            )


class LedgerVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.sources = self.root / "sources"

    def write_ledger(self, data: dict) -> Path:
        path = self.root / "ledger.yaml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return path

    def test_matching_pin_passes(self):
        write_source(self.sources)
        write_extraction(self.sources)
        ledger = self.write_ledger(
            {"source_ids": ["source-one"], "source_body_sha256": BODY_SHA, "paragraphs": []}
        )

        verify_ledger_source_extractions(ledger, self.sources, require_extractions=True)

    def test_mismatching_pin_fails_whether_or_not_required(self):
        write_source(self.sources)
        write_extraction(self.sources)
        ledger = self.write_ledger(
            {"source_ids": ["source-one"], "source_body_sha256": "0" * 64, "paragraphs": []}
        )

        for required in (True, False):
            with self.assertRaisesRegex(ValidationError, "no longer matches the committed extraction"):
                verify_ledger_source_extractions(
                    ledger, self.sources, require_extractions=required
                )

    def test_released_edition_without_extraction_is_skipped(self):
        """Editions 001 and 002 pinned hashes before extractions existed."""
        write_source(self.sources)
        ledger = self.write_ledger(
            {"source_ids": ["source-one"], "source_body_sha256": "0" * 64, "paragraphs": []}
        )

        verify_ledger_source_extractions(ledger, self.sources, require_extractions=False)

    def test_open_edition_requires_extraction_and_pin(self):
        write_source(self.sources)
        ledger = self.write_ledger({"source_ids": ["source-one"], "paragraphs": []})

        with self.assertRaisesRegex(ValidationError, "has no committed extraction"):
            verify_ledger_source_extractions(ledger, self.sources, require_extractions=True)

        write_extraction(self.sources)
        with self.assertRaisesRegex(ValidationError, f"pin the extraction body hash {BODY_SHA}"):
            verify_ledger_source_extractions(ledger, self.sources, require_extractions=True)

    def test_open_edition_requires_ledger_and_article_source_set_equality(self):
        """The reviewer's false pass: article [a, b], ledger [a] verified fine."""
        write_source(self.sources)
        write_extraction(self.sources)
        ledger = self.write_ledger(
            {"source_ids": ["source-one"], "source_body_sha256": BODY_SHA, "paragraphs": []}
        )

        verify_ledger_source_extractions(
            ledger, self.sources, require_extractions=True,
            article_source_ids=("source-one",),
        )

        with self.assertRaisesRegex(
            ValidationError, "absent from the ledger: source-two"
        ):
            verify_ledger_source_extractions(
                ledger, self.sources, require_extractions=True,
                article_source_ids=("source-one", "source-two"),
            )

        # Released editions keep their recorded divergence (001 already
        # diverges); the equality rule is scoped to the open edition.
        verify_ledger_source_extractions(
            ledger, self.sources, require_extractions=False,
            article_source_ids=("source-one", "source-two"),
        )

    def test_open_edition_rejects_ledger_sources_the_article_never_declares(self):
        write_source(self.sources)
        write_extraction(self.sources)
        ledger = self.write_ledger({
            "source_ids": ["source-one", "source-two"],
            "source_body_sha256": {"source-one": BODY_SHA},
            "paragraphs": [],
        })

        with self.assertRaisesRegex(
            ValidationError, "absent from the article: source-two"
        ):
            verify_ledger_source_extractions(
                ledger, self.sources, require_extractions=True,
                article_source_ids=("source-one",),
            )

    def test_open_edition_with_zero_covered_sources_is_an_error(self):
        write_source(self.sources)
        ledger = self.write_ledger({"paragraphs": []})

        verify_ledger_source_extractions(ledger, self.sources, require_extractions=False)

        with self.assertRaisesRegex(ValidationError, "declare the source_ids"):
            verify_ledger_source_extractions(
                ledger, self.sources, require_extractions=True
            )

    def test_multi_source_ledger_verifies_each_source_pin(self):
        write_source(self.sources, "source-one")
        write_extraction(self.sources, "source-one")
        write_source(self.sources, "source-two", bundle="c" * 64)
        other_body = "Another captured body.\n"
        write_extraction(self.sources, "source-two", bundle="c" * 64, body=other_body)
        ledger = self.write_ledger({
            "source_ids": ["source-one", "source-two"],
            "source_body_sha256": {
                "source-one": BODY_SHA,
                "source-two": hashlib.sha256(other_body.encode("utf-8")).hexdigest(),
            },
            "paragraphs": [],
        })

        verify_ledger_source_extractions(ledger, self.sources, require_extractions=True)

        ledger = self.write_ledger({
            "source_ids": ["source-one", "source-two"],
            "source_body_sha256": {"source-one": BODY_SHA, "source-two": "0" * 64},
            "paragraphs": [],
        })
        with self.assertRaisesRegex(ValidationError, "source-two"):
            verify_ledger_source_extractions(ledger, self.sources, require_extractions=True)

    def test_malformed_extraction_surfaces_through_ledger_verification(self):
        write_source(self.sources)
        (self.sources / "source-one" / "extracted.md").write_text("broken", encoding="utf-8")
        ledger = self.write_ledger(
            {"source_ids": ["source-one"], "source_body_sha256": BODY_SHA, "paragraphs": []}
        )

        with self.assertRaisesRegex(ValidationError, "frontmatter"):
            verify_ledger_source_extractions(ledger, self.sources, require_extractions=False)


if __name__ == "__main__":
    unittest.main()
