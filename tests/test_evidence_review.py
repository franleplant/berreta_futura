from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from magazine import Magazine, ValidationError
from magazine.cli import parser
from magazine.evidence_review import (
    EVIDENCE_REVIEW_SCHEMA_VERSION,
    create_evidence_review,
    current_evidence_bindings,
    evidence_review_status,
    load_evidence_review,
    rebind_articles,
    require_approved_evidence_review,
    write_evidence_review,
)
from test_manifest import (
    add_extraction,
    add_source,
    load_edition_with_records,
    make_project,
    pin_article_source_hash,
    set_open_edition,
)


# A version 2 article binding: the manuscript, and every declared source's
# extraction body *and* whole-file hash.  Version 1 rows additionally carried a
# ``ledger_sha256``; the tests that still need one add it explicitly.
BINDINGS = {
    "article": {
        "manuscript_sha256": "1" * 64,
        "source_extractions": {
            "source-one": {"body_sha256": "3" * 64, "file_sha256": "4" * 64}
        },
    }
}


def add_second_article(root: Path) -> None:
    """Grow make_project's edition to two articles, each on its own source, so
    partial re-records have an untouched sibling whose audit must survive."""
    add_source(root, "source-two", body="Second source body.\n")
    edition_dir = root / "editions" / "issue-001"
    (edition_dir / "articles" / "second.md").write_text(
        "Second source body.", encoding="utf-8"
    )
    manifest_path = edition_dir / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["articles"].append(
        {
            "id": "second",
            "title": "Second",
            "short_title": "Second",
            "opener_variant": "edge_medallion",
            "author": "Author",
            "author_note": "Author is chief architect at Example Company.",
            "source_ids": ["source-two"],
            "manuscript": "editions/issue-001/articles/second.md",
        }
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def make_record(**overrides) -> dict:
    record = create_evidence_review(
        edition_id="issue-001",
        reviewer="Independent auditor",
        result="approved",
        bindings=BINDINGS,
        reviewed_at="2026-07-26T10:00:00+00:00",
    )
    record.update(overrides)
    return record


def as_version_1(record: dict, *, ledger_sha256: str = "2" * 64) -> dict:
    """The same record as the shipped editions wrote it: schema 1, with a
    ``ledger_sha256`` binding over a fidelity ledger that no longer exists."""
    record = dict(record)
    record["schema_version"] = 1
    record["articles"] = {
        article_id: {**row, "ledger_sha256": ledger_sha256}
        for article_id, row in record["articles"].items()
    }
    return record


class EvidenceRecordTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_record_roundtrip_binds_manuscript_and_extraction_hashes(self):
        path = write_evidence_review(self.root / "reviews" / "evidence.yaml", make_record())

        loaded = load_evidence_review(path, edition_id="issue-001")
        status = evidence_review_status(loaded, edition_id="issue-001", bindings=BINDINGS)

        # New records are written at version 4: the manuscript and the source
        # extractions are still the whole of what an evidence audit compares,
        # but a version 4 record also carries structured findings, advisory
        # per-article scores, and a ``disposition`` on every authored finding
        # (see the module docstring).
        self.assertEqual(EVIDENCE_REVIEW_SCHEMA_VERSION, 4)
        self.assertEqual(loaded["schema_version"], 4)
        self.assertEqual(status["status"], "approved")
        self.assertEqual(status["reviewer"], "Independent auditor")
        # A full record stamps every article with the record's own timestamp
        # beside the bound hashes.
        self.assertEqual(
            loaded["articles"],
            {
                "article": {
                    "reviewed_at": "2026-07-26T10:00:00+00:00",
                    **BINDINGS["article"],
                }
            },
        )
        self.assertEqual(
            status["articles"],
            {
                "article": {
                    "status": "current",
                    "reviewed_at": "2026-07-26T10:00:00+00:00",
                }
            },
        )

    def test_any_changed_bound_hash_makes_the_record_stale(self):
        record = make_record()
        current = {"article": {**BINDINGS["article"], "manuscript_sha256": "f" * 64}}
        status = evidence_review_status(record, edition_id="issue-001", bindings=current)
        self.assertEqual(status["status"], "stale")

        for changed in (
            {"body_sha256": "f" * 64, "file_sha256": "4" * 64},
            # Body untouched, frontmatter rewritten: the whole-file hash alone
            # must be enough to stale the record.
            {"body_sha256": "3" * 64, "file_sha256": "f" * 64},
        ):
            current = {
                "article": {
                    **BINDINGS["article"],
                    "source_extractions": {"source-one": changed},
                }
            }
            status = evidence_review_status(record, edition_id="issue-001", bindings=current)
            self.assertEqual(status["status"], "stale", changed)

    def test_a_version_1_ledger_binding_is_ignored_rather_than_drift(self):
        """Editions 003 and 004 shipped version 1 records that also bound a
        fidelity ledger.  That file is gone, but nothing the audit actually
        compared has moved, so the record must still read as approved: deleting
        a file the record merely referenced cannot retroactively invalidate an
        audit of manuscripts and extractions that are byte-for-byte unchanged."""
        path = write_evidence_review(
            self.root / "reviews" / "evidence.yaml", as_version_1(make_record())
        )

        loaded = load_evidence_review(path, edition_id="issue-001")
        status = evidence_review_status(loaded, edition_id="issue-001", bindings=BINDINGS)

        self.assertEqual(loaded["schema_version"], 1)
        self.assertEqual(status["status"], "approved")
        self.assertEqual(
            status["articles"]["article"],
            {"status": "current", "reviewed_at": "2026-07-26T10:00:00+00:00"},
        )

    def test_status_names_each_drifted_article_and_bound_input(self):
        """Staleness is per article: one drifted manuscript stales the record,
        but the untouched sibling still reports current."""
        record = make_record()
        record["articles"]["second"] = {
            "reviewed_at": "2026-07-26T10:00:00+00:00",
            "manuscript_sha256": "5" * 64,
            "source_extractions": {
                "source-two": {"body_sha256": "7" * 64, "file_sha256": "8" * 64}
            },
        }
        current = {
            "article": dict(BINDINGS["article"]),
            "second": {
                "manuscript_sha256": "f" * 64,
                "source_extractions": {
                    "source-two": {"body_sha256": "7" * 64, "file_sha256": "f" * 64}
                },
            },
        }

        status = evidence_review_status(record, edition_id="issue-001", bindings=current)

        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["articles"]["article"]["status"], "current")
        self.assertEqual(status["articles"]["second"]["status"], "drifted")
        self.assertEqual(
            status["articles"]["second"]["drift"],
            ["manuscript", "extraction:source-two"],
        )

    def test_status_marks_added_and_removed_articles_as_drift(self):
        record = make_record()

        added = {
            "article": dict(BINDINGS["article"]),
            "late-arrival": {
                "manuscript_sha256": "a" * 64,
                "source_extractions": {
                    "source-two": {"body_sha256": "c" * 64, "file_sha256": "d" * 64}
                },
            },
        }
        status = evidence_review_status(record, edition_id="issue-001", bindings=added)
        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["articles"]["late-arrival"]["status"], "unrecorded")

        status = evidence_review_status(record, edition_id="issue-001", bindings={})
        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["articles"]["article"]["status"], "removed")

    def test_legacy_rows_without_reviewed_at_still_load_and_report(self):
        """Edition 003's record predates per-article stamps: rows carry only the
        bound hashes, load under schema_version 1, and report the record-level
        timestamp per article."""
        record = as_version_1(make_record())
        record["articles"] = {
            article_id: {
                key: value for key, value in row.items() if key != "reviewed_at"
            }
            for article_id, row in record["articles"].items()
        }
        path = write_evidence_review(self.root / "reviews" / "evidence.yaml", record)

        loaded = load_evidence_review(path, edition_id="issue-001")
        status = evidence_review_status(loaded, edition_id="issue-001", bindings=BINDINGS)

        self.assertEqual(status["status"], "approved")
        self.assertEqual(
            status["articles"]["article"],
            {"status": "current", "reviewed_at": "2026-07-26T10:00:00+00:00"},
        )

    def test_load_rejects_an_unsupported_schema_version(self):
        """Only 1, 2, 3 and 4 load: a future shape must not be read as if its
        keys meant what version 4's mean."""
        path = write_evidence_review(
            self.root / "reviews" / "evidence.yaml", make_record(schema_version=5)
        )

        with self.assertRaisesRegex(
            ValidationError, "schema_version must be 1, 2, 3, or 4"
        ):
            load_evidence_review(path, edition_id="issue-001")

    def test_load_rejects_a_blank_per_article_reviewed_at(self):
        record = make_record()
        record["articles"] = {"article": {**BINDINGS["article"], "reviewed_at": "  "}}
        path = write_evidence_review(self.root / "reviews" / "evidence.yaml", record)

        with self.assertRaisesRegex(ValidationError, "reviewed_at must be a non-empty"):
            load_evidence_review(path, edition_id="issue-001")

    def test_changes_required_record_needs_a_finding(self):
        with self.assertRaisesRegex(ValidationError, "needs at least one finding"):
            create_evidence_review(
                edition_id="issue-001",
                reviewer="Independent auditor",
                result="changes_required",
                bindings=BINDINGS,
            )

    def test_load_rejects_a_record_missing_extraction_bindings(self):
        record = make_record()
        record["articles"] = {"article": {"manuscript_sha256": "1" * 64}}
        path = write_evidence_review(self.root / "reviews" / "evidence.yaml", record)

        with self.assertRaisesRegex(ValidationError, "source_extractions"):
            load_evidence_review(path, edition_id="issue-001")

    def test_load_rejects_a_flat_extraction_hash_without_the_file_binding(self):
        record = make_record()
        record["articles"] = {
            "article": {
                "manuscript_sha256": "1" * 64,
                "source_extractions": {"source-one": "3" * 64},
            }
        }
        path = write_evidence_review(self.root / "reviews" / "evidence.yaml", record)

        with self.assertRaisesRegex(
            ValidationError, "requires body_sha256 and file_sha256"
        ):
            load_evidence_review(path, edition_id="issue-001")

    def test_gate_refuses_missing_stale_and_changes_required_records(self):
        with self.assertRaisesRegex(ValidationError, "required_before_release"):
            require_approved_evidence_review(None, edition_id="issue-001", bindings=BINDINGS)

        stale_bindings = {"article": {**BINDINGS["article"], "manuscript_sha256": "f" * 64}}
        with self.assertRaisesRegex(ValidationError, "stale.*article"):
            require_approved_evidence_review(
                make_record(), edition_id="issue-001", bindings=stale_bindings
            )

        rejected = make_record(result="changes_required", findings=["Unlogged omission in §2"])
        with self.assertRaisesRegex(ValidationError, "changes_required"):
            require_approved_evidence_review(
                rejected, edition_id="issue-001", bindings=BINDINGS
            )

    def test_gate_lets_a_version_1_record_release_an_unchanged_edition(self):
        """The release gate reads the shipped records too: a version 1 record
        whose bound manuscripts and extractions still match must not block a
        re-release behind an audit nothing has invalidated."""
        require_approved_evidence_review(
            as_version_1(make_record()), edition_id="issue-001", bindings=BINDINGS
        )


class EvidenceStructuredFindingTests(unittest.TestCase):
    """Version 3 and 4's findings: what the fact-checker prompt actually emits.

    Versions 1 and 2 coerced every finding through ``str(item).strip()``, so a
    mapping survived the truthiness check and was written out as a line of
    Python repr.  A structured finding must now round-trip as a mapping, and a
    sentence typed into ``--finding`` must keep working beside it.

    Every authored finding also carries ``disposition`` from version 4 on.  This
    lens files ``fix`` on all of them by its prompt's own rule -- a claim the
    source does not make is never the author's voice to keep -- so the field is
    constant here; the write-strict/read-lenient rule behind it is tested once,
    on the shared spine, in ``test_piece_review.py``.
    """

    FINDING = {
        "severity": "blocking",
        "article": "eval-engineering",
        "locator": "Cost and latency | cuts eval cost by 40% | 1",
        "category": "number_or_name_error",
        "disposition": "fix",
        "note": "The source says roughly a third in our two pilot teams.",
    }

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_a_structured_finding_survives_the_record_as_a_mapping(self):
        record = make_record(result="changes_required")
        record = create_evidence_review(
            edition_id="issue-001",
            reviewer="Independent auditor",
            result="changes_required",
            bindings=BINDINGS,
            findings=[self.FINDING, "  A sentence a human typed.  "],
            reviewed_at="2026-07-26T10:00:00+00:00",
        )
        path = write_evidence_review(self.root / "reviews" / "evidence.yaml", record)

        # Read the file back as YAML, not the in-memory dict: the old recorder
        # looked fine in memory and only lost the finding on the way to disk.
        on_disk = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["findings"][0], self.FINDING)
        self.assertEqual(on_disk["findings"][1], "A sentence a human typed.")

        loaded = load_evidence_review(path, edition_id="issue-001")
        self.assertEqual(loaded["findings"][0], self.FINDING)
        status = evidence_review_status(loaded, edition_id="issue-001", bindings=BINDINGS)
        self.assertEqual(status["findings"][0]["category"], "number_or_name_error")

    def test_repair_from_is_stored_beside_the_locator(self):
        """``locator`` says where a defect becomes visible; ``repair_from`` says
        where it could be repaired.  A structural finding carries both, and the
        record must keep them as two distinct fields in a stable order: a
        reviser handed only the locator patches the symptom."""
        finding = {
            "severity": "major",
            "article": "eval-engineering",
            "locator": "Where the score goes | It is not a scoring problem. | 1",
            "repair_from": "- | This piece is about scoring. | 1",
            "category": "argument_order",
            "disposition": "fix",
            "note": "The frame promised in the opening is contradicted here.",
        }
        record = create_evidence_review(
            edition_id="issue-001",
            reviewer="Independent auditor",
            result="changes_required",
            bindings=BINDINGS,
            findings=[finding],
            reviewed_at="2026-07-26T10:00:00+00:00",
        )
        path = write_evidence_review(self.root / "reviews" / "evidence.yaml", record)

        stored = load_evidence_review(path, edition_id="issue-001")["findings"][0]

        self.assertEqual(stored, finding)
        self.assertEqual(
            list(stored),
            [
                "severity",
                "article",
                "locator",
                "repair_from",
                "category",
                "disposition",
                "note",
            ],
        )

    def test_a_structured_finding_needs_a_severity_a_note_and_a_disposition(self):
        for missing in ("severity", "note", "disposition"):
            finding = {key: value for key, value in self.FINDING.items() if key != missing}
            with self.assertRaisesRegex(ValidationError, f"requires a non-empty {missing}"):
                create_evidence_review(
                    edition_id="issue-001",
                    reviewer="Independent auditor",
                    result="changes_required",
                    bindings=BINDINGS,
                    findings=[finding],
                )

    def test_an_unknown_severity_is_refused(self):
        with self.assertRaisesRegex(ValidationError, "severity must be"):
            create_evidence_review(
                edition_id="issue-001",
                reviewer="Independent auditor",
                result="changes_required",
                bindings=BINDINGS,
                findings=[{**self.FINDING, "severity": "catastrophic"}],
            )

    def test_a_version_2_string_finding_still_loads(self):
        """Editions 003 and 004 recorded findings as sentences.  A structured
        recorder that could no longer read them would demand a re-audit of
        every shipped edition to fix a shape nothing depends on."""
        record = make_record(result="changes_required", findings=["Unlogged omission in §2"])
        record["schema_version"] = 2
        path = write_evidence_review(self.root / "reviews" / "evidence.yaml", record)

        loaded = load_evidence_review(path, edition_id="issue-001")

        self.assertEqual(loaded["findings"], ["Unlogged omission in §2"])


class EvidenceScoreTests(unittest.TestCase):
    """Advisory scores: stored, exposed, and load-bearing on nothing."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_scores_land_in_the_article_row_and_come_back_out_of_status(self):
        record = create_evidence_review(
            edition_id="issue-001",
            reviewer="Independent auditor",
            result="approved",
            bindings=BINDINGS,
            scores={"article": {"claim_support": 3, "quote_accuracy": 5}},
            reviewed_at="2026-07-26T10:00:00+00:00",
        )
        path = write_evidence_review(self.root / "reviews" / "evidence.yaml", record)

        loaded = load_evidence_review(path, edition_id="issue-001")
        self.assertEqual(
            loaded["articles"]["article"]["scores"],
            {"claim_support": 3, "quote_accuracy": 5},
        )
        status = evidence_review_status(loaded, edition_id="issue-001", bindings=BINDINGS)
        self.assertEqual(
            status["articles"]["article"]["scores"],
            {"claim_support": 3, "quote_accuracy": 5},
        )

    def test_a_score_never_stales_a_record(self):
        """The load-bearing property of an advisory score: it is not a binding.
        Re-scoring the same unchanged manuscript must leave the audit approved,
        and nothing anywhere may read a score to decide anything."""
        record = create_evidence_review(
            edition_id="issue-001",
            reviewer="Independent auditor",
            result="approved",
            bindings=BINDINGS,
            scores={"article": {"claim_support": 1}},
            reviewed_at="2026-07-26T10:00:00+00:00",
        )

        status = evidence_review_status(record, edition_id="issue-001", bindings=BINDINGS)

        self.assertEqual(status["status"], "approved")
        require_approved_evidence_review(
            record, edition_id="issue-001", bindings=BINDINGS
        )

    def test_out_of_range_and_non_integer_scores_are_refused(self):
        for bad in ({"claim_support": 0}, {"claim_support": 6}, {"claim_support": "4"},
                    {"claim_support": True}):
            with self.assertRaisesRegex(ValidationError, "must be an integer 1-5"):
                create_evidence_review(
                    edition_id="issue-001",
                    reviewer="Independent auditor",
                    result="approved",
                    bindings=BINDINGS,
                    scores={"article": bad},
                )

    def test_scores_for_an_unbound_article_are_refused(self):
        with self.assertRaisesRegex(ValidationError, "which this record does not bind"):
            create_evidence_review(
                edition_id="issue-001",
                reviewer="Independent auditor",
                result="approved",
                bindings=BINDINGS,
                scores={"phantom": {"claim_support": 4}},
            )

    def test_a_partial_re_record_preserves_an_untouched_article_score(self):
        record = create_evidence_review(
            edition_id="issue-001",
            reviewer="Independent auditor",
            result="approved",
            bindings=BINDINGS,
            scores={"article": {"claim_support": 3}},
            reviewed_at="2026-07-26T10:00:00+00:00",
        )
        current = {
            "article": {**BINDINGS["article"], "manuscript_sha256": "f" * 64},
            "second": {
                "manuscript_sha256": "b" * 64,
                "source_extractions": {
                    "source-two": {"body_sha256": "d" * 64, "file_sha256": "e" * 64}
                },
            },
        }
        record["articles"]["second"] = {
            "reviewed_at": "2026-07-26T10:00:00+00:00",
            **current["second"],
        }

        merged = rebind_articles(record, bindings=current, article_ids=["second"])

        self.assertEqual(merged["article"]["scores"], {"claim_support": 3})
        self.assertNotIn("scores", merged["second"])


class RebindArticlesTests(unittest.TestCase):
    """The partial re-record merge, as a pure function of record and disk."""

    CURRENT = {
        "article": {
            "manuscript_sha256": "a" * 64,
            "source_extractions": {
                "source-one": {"body_sha256": "3" * 64, "file_sha256": "4" * 64}
            },
        },
        "second": {
            "manuscript_sha256": "b" * 64,
            "source_extractions": {
                "source-two": {"body_sha256": "d" * 64, "file_sha256": "e" * 64}
            },
        },
    }

    def test_named_articles_rebind_and_the_rest_keep_binding_and_timestamp(self):
        record = make_record()

        merged = rebind_articles(
            record, bindings=self.CURRENT, article_ids=["second"]
        )

        # "second" is fresh disk state with no stamp yet; create_evidence_review
        # will stamp it with the new record's timestamp.
        self.assertEqual(merged["second"], self.CURRENT["second"])
        # "article" keeps the recorded hashes -- not the drifted disk ones --
        # and the audit timestamp it was recorded under.
        self.assertEqual(merged["article"]["manuscript_sha256"], "1" * 64)
        self.assertEqual(merged["article"]["reviewed_at"], "2026-07-26T10:00:00+00:00")

    def test_preserving_a_version_1_row_drops_its_stale_ledger_binding(self):
        """A re-record rewrites the whole file at version 2, so a preserved
        version 1 row is carried forward as the two bindings that still mean
        something.  Copying ``ledger_sha256`` into a version 2 record would
        re-assert a binding over a deleted file; the row's ``reviewed_at`` is
        real audit history and must survive."""
        record = as_version_1(make_record())

        merged = rebind_articles(
            record, bindings=self.CURRENT, article_ids=["second"]
        )

        self.assertEqual(
            merged["article"],
            {
                "reviewed_at": "2026-07-26T10:00:00+00:00",
                **BINDINGS["article"],
            },
        )
        self.assertNotIn("ledger_sha256", merged["article"])

    def test_articles_that_left_the_edition_fall_out_of_the_merge(self):
        record = make_record()
        record["articles"]["ghost"] = {
            **BINDINGS["article"], "reviewed_at": "2026-07-26T10:00:00+00:00"
        }

        merged = rebind_articles(
            record, bindings=self.CURRENT, article_ids=["second"]
        )

        self.assertEqual(set(merged), {"article", "second"})

    def test_rebinding_requires_an_existing_record(self):
        with self.assertRaisesRegex(ValidationError, "amends an existing record"):
            rebind_articles(None, bindings=self.CURRENT, article_ids=["article"])

    def test_rebinding_requires_at_least_one_article(self):
        with self.assertRaisesRegex(ValidationError, "at least one article"):
            rebind_articles(make_record(), bindings=self.CURRENT, article_ids=[" "])

    def test_rebinding_refuses_articles_the_edition_does_not_carry(self):
        with self.assertRaisesRegex(ValidationError, "does not carry: phantom"):
            rebind_articles(
                make_record(), bindings=self.CURRENT, article_ids=["phantom"]
            )

    def test_rebinding_refuses_an_unnamed_article_with_no_recorded_audit(self):
        """The edition gained "second" after the record was written; a partial
        record that neither names nor can preserve it must refuse rather than
        write a record with a silent hole."""
        with self.assertRaisesRegex(
            ValidationError, "no recorded audit to preserve: second"
        ):
            rebind_articles(
                make_record(), bindings=self.CURRENT, article_ids=["article"]
            )


class EvidenceReviewCliTests(unittest.TestCase):
    def test_review_record_defaults_to_render_and_accepts_evidence(self):
        base = ["review", "record", "issue-001", "--reviewer", "critic", "--result", "approved"]

        self.assertEqual(parser().parse_args(base).kind, "render")
        self.assertEqual(parser().parse_args([*base, "--kind", "evidence"]).kind, "evidence")

    def test_review_record_rejects_an_unknown_kind(self):
        with self.assertRaises(SystemExit):
            parser().parse_args(
                ["review", "record", "issue-001", "--reviewer", "c",
                 "--result", "approved", "--kind", "visual"]
            )

    def test_review_record_parses_articles_and_rebuild(self):
        base = ["review", "record", "issue-001", "--reviewer", "critic", "--result", "approved"]

        args = parser().parse_args([*base, "--kind", "evidence", "--articles", "a,b"])
        self.assertEqual(args.articles, "a,b")
        self.assertFalse(args.rebuild)
        self.assertIsNone(parser().parse_args(base).articles)
        self.assertTrue(parser().parse_args([*base, "--rebuild"]).rebuild)

    def test_articles_and_rebuild_are_refused_for_the_wrong_kind(self):
        """--articles narrows an evidence audit and --rebuild re-typesets a
        render package; each is meaningless for the other kind and refused
        before any record is touched."""
        from magazine.cli import main

        with TemporaryDirectory() as tmp:
            base = [
                "--root", tmp, "review", "record", "issue-001",
                "--reviewer", "c", "--result", "approved",
            ]
            self.assertEqual(main([*base, "--articles", "a"]), 2)
            self.assertEqual(main([*base, "--kind", "evidence", "--rebuild"]), 2)

    def test_an_empty_articles_flag_on_a_render_record_is_still_refused(self):
        """``--articles ""`` names no articles but still expresses the intent
        to narrow; a render record must refuse it exactly like a populated
        list rather than silently ignore it and record anyway."""
        import io
        from contextlib import redirect_stderr

        from magazine.cli import main

        with TemporaryDirectory() as tmp:
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = main([
                    "--root", tmp, "review", "record", "issue-001",
                    "--reviewer", "c", "--result", "approved", "--articles", "",
                ])
        self.assertEqual(code, 2)
        self.assertIn(
            "--articles applies only to the per-piece lenses", stderr.getvalue()
        )
        self.assertIn("a render review binds whole-language PDFs", stderr.getvalue())


class EvidenceReviewCompilerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_project(self.root)

    def test_recording_requires_a_committed_extraction(self):
        magazine = Magazine(self.root)

        with self.assertRaisesRegex(ValidationError, "requires a committed extraction"):
            magazine.record_evidence_review(
                "issue-001", reviewer="Independent auditor", result="approved"
            )

    def test_recorded_review_goes_stale_when_any_audited_input_changes(self):
        pin_article_source_hash(self.root, add_extraction(self.root))
        magazine = Magazine(self.root)

        path = magazine.record_evidence_review(
            "issue-001", reviewer="Independent auditor", result="approved"
        )

        self.assertEqual(
            path, magazine.editions_dir / "issue-001" / "reviews" / "evidence.yaml"
        )
        self.assertEqual(magazine.evidence_review_status("issue-001")["status"], "approved")

        manuscript = self.root / "editions" / "issue-001" / "articles" / "article.md"
        manuscript.write_text(manuscript.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assertEqual(magazine.evidence_review_status("issue-001")["status"], "stale")

    def test_rewriting_extraction_frontmatter_after_approval_is_stale(self):
        """Provenance is bound, not just the body: same body, new frontmatter."""
        pin_article_source_hash(self.root, add_extraction(self.root))
        magazine = Magazine(self.root)
        magazine.record_evidence_review(
            "issue-001", reviewer="Independent auditor", result="approved"
        )
        self.assertEqual(magazine.evidence_review_status("issue-001")["status"], "approved")

        extraction = self.root / "library" / "sources" / "source-one" / "extracted.md"
        extraction.write_text(
            extraction.read_text(encoding="utf-8").replace(
                "extraction_method: test fixture transcription",
                "extraction_method: retyped after approval",
            ),
            encoding="utf-8",
        )

        # The article row's source_body_sha256 pin (body bytes) still matches;
        # only the record's whole-file binding notices.
        self.assertEqual(magazine.evidence_review_status("issue-001")["status"], "stale")

    def test_a_shipped_version_1_record_on_disk_still_reports_approved(self):
        """The end-to-end form of the version 1 rule, against the status
        command a release actually consults: rewrite an approved record into
        the shape editions 003 and 004 shipped and nothing may change."""
        pin_article_source_hash(self.root, add_extraction(self.root))
        magazine = Magazine(self.root)
        path = magazine.record_evidence_review(
            "issue-001", reviewer="Independent auditor", result="approved"
        )
        path.write_text(
            yaml.safe_dump(
                as_version_1(yaml.safe_load(path.read_text(encoding="utf-8"))),
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        status = magazine.evidence_review_status("issue-001")

        self.assertEqual(status["status"], "approved")
        self.assertEqual(status["articles"]["article"]["status"], "current")

    def test_bindings_cover_every_source_the_article_declares(self):
        """The reviewer's false pass: an article over [a, b] whose record binds
        only a would leave b free to change under an approved audit.  The
        covered set is the article row's ``source_ids`` -- the same list its
        ``source_body_sha256`` pins -- so the audit and validation can never
        disagree about which sources an article was written from."""
        add_source(self.root, "source-two", body="Second source body.\n")
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["articles"][0]["source_ids"] = ["source-one", "source-two"]
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        add_extraction(self.root)
        add_extraction(self.root, source_id="source-two", body="Second source body.\n")

        bindings = current_evidence_bindings(
            load_edition_with_records(self.root),
            self.root / "library" / "sources",
            require_extractions=True,
        )

        extractions = bindings["article"]["source_extractions"]
        self.assertEqual(set(extractions), {"source-one", "source-two"})
        for source_id, entry in extractions.items():
            self.assertEqual(set(entry), {"body_sha256", "file_sha256"}, source_id)
        self.assertNotIn("ledger_sha256", bindings["article"])

    def test_open_edition_record_binds_every_declared_source(self):
        """Recording against the open edition is the strict path: every source
        the article declares must already have a committed extraction, and all
        of them land in the record."""
        add_source(self.root, "source-two", body="Second source body.\n")
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["articles"][0]["source_ids"] = ["source-one", "source-two"]
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        one = add_extraction(self.root)
        two = add_extraction(self.root, source_id="source-two", body="Second source body.\n")
        pin_article_source_hash(self.root, {"source-one": one, "source-two": two})
        set_open_edition(self.root, "issue-001")
        magazine = Magazine(self.root)

        path = magazine.record_evidence_review(
            "issue-001", reviewer="Independent auditor", result="approved"
        )

        record = load_evidence_review(path, edition_id="issue-001")
        self.assertEqual(
            set(record["articles"]["article"]["source_extractions"]),
            {"source-one", "source-two"},
        )

    def test_partial_record_rebinds_only_the_named_articles(self):
        """One drifted article is re-audited alone: the sibling's binding and
        audit timestamp ride through the re-record untouched."""
        add_second_article(self.root)
        pin_article_source_hash(self.root, add_extraction(self.root))
        pin_article_source_hash(
            self.root,
            add_extraction(self.root, source_id="source-two", body="Second source body.\n"),
            article="second",
        )
        magazine = Magazine(self.root)
        magazine.record_evidence_review(
            "issue-001",
            reviewer="Independent auditor",
            result="approved",
            reviewed_at="2026-07-26T10:00:00+00:00",
        )

        extraction = self.root / "library" / "sources" / "source-two" / "extracted.md"
        extraction.write_text(
            extraction.read_text(encoding="utf-8").replace(
                "extraction_method: test fixture transcription",
                "extraction_method: retyped after approval",
            ),
            encoding="utf-8",
        )
        status = magazine.evidence_review_status("issue-001")
        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["articles"]["article"]["status"], "current")
        self.assertEqual(status["articles"]["second"]["status"], "drifted")
        self.assertEqual(
            status["articles"]["second"]["drift"], ["extraction:source-two"]
        )

        path = magazine.record_evidence_review(
            "issue-001",
            reviewer="Independent auditor",
            result="approved",
            reviewed_at="2026-07-27T09:00:00+00:00",
            articles=["second"],
        )

        status = magazine.evidence_review_status("issue-001")
        self.assertEqual(status["status"], "approved")
        self.assertEqual(
            status["articles"]["article"]["reviewed_at"], "2026-07-26T10:00:00+00:00"
        )
        self.assertEqual(
            status["articles"]["second"]["reviewed_at"], "2026-07-27T09:00:00+00:00"
        )
        record = load_evidence_review(path, edition_id="issue-001")
        self.assertEqual(
            record["articles"]["article"]["reviewed_at"], "2026-07-26T10:00:00+00:00"
        )

    def test_partial_record_requires_an_existing_record(self):
        pin_article_source_hash(self.root, add_extraction(self.root))
        magazine = Magazine(self.root)

        with self.assertRaisesRegex(ValidationError, "amends an existing record"):
            magazine.record_evidence_review(
                "issue-001",
                reviewer="Independent auditor",
                result="approved",
                articles=["article"],
            )

    def test_status_reports_errors_instead_of_aborting(self):
        magazine = Magazine(self.root)

        status = magazine.evidence_review_status("issue-404")

        self.assertEqual(status["status"], "unavailable")
        self.assertTrue(any("issue-404" in error for error in status["errors"]))

    def test_status_degrades_when_the_record_file_is_corrupt(self):
        """A broken evidence.yaml must not abort the whole status command."""
        magazine = Magazine(self.root)
        path = magazine.editions_dir / "issue-001" / "reviews" / "evidence.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("result: [unclosed", encoding="utf-8")

        status = magazine.evidence_review_status("issue-001")

        self.assertEqual(status["status"], "unavailable")
        self.assertTrue(any("evidence.yaml" in error for error in status["errors"]))

    def test_status_is_not_required_for_editions_that_are_not_open(self):
        # make_project's open edition is 999-unreleased, so issue-001 is not
        # releasable and owes no evidence review.
        status = Magazine(self.root).evidence_review_status("issue-001")

        self.assertEqual(status["status"], "not_required")

    def test_status_still_demands_a_review_for_the_open_edition(self):
        set_open_edition(self.root, "issue-001")

        status = Magazine(self.root).evidence_review_status("issue-001")

        self.assertEqual(status["status"], "required_before_release")


if __name__ == "__main__":
    unittest.main()
