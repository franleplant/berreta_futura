from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from magazine import ValidationError
from magazine.line_review import (
    EDITORIAL_ARTICLE_ID,
    LINE_REVIEW_SCHEMA_VERSION,
    article_drift,
    create_line_review,
    current_line_bindings,
    line_review_path,
    line_review_status,
    load_line_review,
    rebind_articles,
    require_approved_line_review,
    write_line_review,
)
from test_manifest import load_edition_with_records, make_project


# A line review binds one thing per piece: the manuscript it read.  There is
# deliberately no source hash here -- the line editor is forbidden to open the
# extraction, so its bytes cannot invalidate the reading.
BINDINGS = {"article": {"manuscript_sha256": "1" * 64}}

TWO_ARTICLES = {
    "article": {"manuscript_sha256": "1" * 64},
    "second": {"manuscript_sha256": "5" * 64},
}

# The shape prompts/line-review.md emits: a mapping, not a sentence.
STRUCTURED_FINDING = {
    "severity": "major",
    "article": "article",
    "locator": "Where the score goes | It is not a scoring problem. | 1",
    "category": "repeated_cadence",
    # The prompt writes ``note`` as a block scalar, so it is genuinely
    # multi-line and must survive YAML as the same string.
    "note": "The piece closes three sections on the same antithesis.\nOne is a point; three is a tic.",
    "suggestion": "Specification is where the difficulty actually sits.",
}


def make_record(**overrides) -> dict:
    record = create_line_review(
        edition_id="issue-001",
        reviewer="Line editor",
        result="approved",
        bindings=BINDINGS,
        reviewed_at="2026-07-26T10:00:00+00:00",
    )
    record.update(overrides)
    return record


class LineRecordTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_record_roundtrip_binds_the_manuscript_and_nothing_else(self):
        path = write_line_review(line_review_path(self.root, "issue-001"), make_record())

        loaded = load_line_review(path, edition_id="issue-001")
        status = line_review_status(loaded, edition_id="issue-001", bindings=BINDINGS)

        self.assertEqual(path, self.root / "issue-001" / "reviews" / "line.yaml")
        self.assertEqual(LINE_REVIEW_SCHEMA_VERSION, 1)
        self.assertEqual(loaded["schema_version"], 1)
        self.assertEqual(status["status"], "approved")
        self.assertEqual(status["reviewer"], "Line editor")
        # The whole of an article row: when it was read, and the bytes read.
        # A leaked source binding here would mean a re-extraction could send a
        # line editor back to a piece whose prose never moved.
        self.assertEqual(
            set(loaded["articles"]["article"]), {"reviewed_at", "manuscript_sha256"}
        )
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

    def test_the_editorial_is_bound_and_read_like_any_other_piece(self):
        """The prompt line-reviews the opening editorial too, under the article
        id ``editorial``: it is prose with an opening, an ending, and the house
        tics, and nothing about it makes it exempt from a reading."""
        make_project(self.root)
        edition = load_edition_with_records(self.root)

        bindings = current_line_bindings(edition)

        self.assertEqual(set(bindings), {"article", EDITORIAL_ARTICLE_ID})
        self.assertEqual(EDITORIAL_ARTICLE_ID, "editorial")
        for article_id, row in bindings.items():
            self.assertEqual(set(row), {"manuscript_sha256"}, article_id)
        # Distinct files, distinct hashes: the editorial is its own subject.
        self.assertNotEqual(
            bindings["article"]["manuscript_sha256"],
            bindings[EDITORIAL_ARTICLE_ID]["manuscript_sha256"],
        )

        record = create_line_review(
            edition_id="issue-001",
            reviewer="Line editor",
            result="approved",
            bindings=bindings,
        )
        status = line_review_status(record, edition_id="issue-001", bindings=bindings)
        self.assertEqual(status["status"], "approved")
        self.assertEqual(status["articles"][EDITORIAL_ARTICLE_ID]["status"], "current")

        # Rewriting the editorial stales the record exactly as rewriting an
        # article would.
        editorial = self.root / "editions" / "issue-001" / "editorial.md"
        editorial.write_text(editorial.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        moved = current_line_bindings(load_edition_with_records(self.root))
        status = line_review_status(record, edition_id="issue-001", bindings=moved)
        self.assertEqual(status["status"], "stale")
        self.assertEqual(
            status["articles"][EDITORIAL_ARTICLE_ID]["drift"], ["manuscript"]
        )

    def test_an_edition_without_an_editorial_simply_has_no_editorial_row(self):
        """Not every edition carries an opening editorial; its absence is an
        ordinary state, not a missing binding to refuse."""
        make_project(self.root)
        edition = load_edition_with_records(self.root)
        without = type(edition)(
            **{
                field: (None if field == "editorial" else getattr(edition, field))
                for field in edition.__dataclass_fields__
            }
        )

        bindings = current_line_bindings(without)

        self.assertEqual(set(bindings), {"article"})

    def test_a_moved_manuscript_byte_makes_the_record_stale(self):
        record = make_record()
        current = {"article": {"manuscript_sha256": "f" * 64}}

        status = line_review_status(record, edition_id="issue-001", bindings=current)

        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["articles"]["article"]["status"], "drifted")
        self.assertEqual(status["articles"]["article"]["drift"], ["manuscript"])

    def test_drift_names_the_manuscript_and_an_untouched_sibling_is_current(self):
        record = create_line_review(
            edition_id="issue-001",
            reviewer="Line editor",
            result="approved",
            bindings=TWO_ARTICLES,
            reviewed_at="2026-07-26T10:00:00+00:00",
        )
        current = {
            "article": {"manuscript_sha256": "1" * 64},
            "second": {"manuscript_sha256": "f" * 64},
        }

        status = line_review_status(record, edition_id="issue-001", bindings=current)

        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["articles"]["article"]["status"], "current")
        self.assertEqual(status["articles"]["second"]["status"], "drifted")
        self.assertEqual(status["articles"]["second"]["drift"], ["manuscript"])
        self.assertEqual(
            article_drift({"manuscript_sha256": "1" * 64}, {"manuscript_sha256": "1" * 64}),
            [],
        )

    def test_status_marks_added_and_removed_articles_as_drift(self):
        record = make_record()

        added = {
            "article": {"manuscript_sha256": "1" * 64},
            "late-arrival": {"manuscript_sha256": "a" * 64},
        }
        status = line_review_status(record, edition_id="issue-001", bindings=added)
        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["articles"]["late-arrival"]["status"], "unrecorded")

        status = line_review_status(record, edition_id="issue-001", bindings={})
        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["articles"]["article"]["status"], "removed")

    def test_status_with_no_record_is_required_before_release(self):
        status = line_review_status(None, edition_id="issue-001", bindings=BINDINGS)

        self.assertEqual(status["status"], "required_before_release")
        self.assertEqual(
            status["articles"], {"article": {"status": "unreviewed", "reviewed_at": None}}
        )

    def test_changes_required_record_needs_a_finding(self):
        with self.assertRaisesRegex(ValidationError, "needs at least one finding"):
            create_line_review(
                edition_id="issue-001",
                reviewer="Line editor",
                result="changes_required",
                bindings=BINDINGS,
            )

    def test_create_refuses_a_missing_reviewer_bad_result_and_empty_bindings(self):
        with self.assertRaisesRegex(ValidationError, "requires a reviewer"):
            create_line_review(
                edition_id="issue-001", reviewer="  ", result="approved", bindings=BINDINGS
            )
        with self.assertRaisesRegex(ValidationError, "approved or changes_required"):
            create_line_review(
                edition_id="issue-001", reviewer="Line editor", result="ok", bindings=BINDINGS
            )
        with self.assertRaisesRegex(ValidationError, "at least one article"):
            create_line_review(
                edition_id="issue-001", reviewer="Line editor", result="approved", bindings={}
            )

    def test_gate_refuses_missing_stale_and_changes_required_records(self):
        with self.assertRaisesRegex(ValidationError, "required_before_release"):
            require_approved_line_review(None, edition_id="issue-001", bindings=BINDINGS)

        stale_bindings = {"article": {"manuscript_sha256": "f" * 64}}
        with self.assertRaisesRegex(ValidationError, "stale.*article"):
            require_approved_line_review(
                make_record(), edition_id="issue-001", bindings=stale_bindings
            )

        rejected = make_record(
            result="changes_required", findings=["Orphan referent in the second section"]
        )
        with self.assertRaisesRegex(ValidationError, "changes_required"):
            require_approved_line_review(rejected, edition_id="issue-001", bindings=BINDINGS)

    def test_gate_names_the_line_kind_in_its_refusal(self):
        """The refusal is the operator's next command; pointing at the wrong
        --kind would send them to re-run the evidence audit."""
        with self.assertRaisesRegex(ValidationError, r"--kind line"):
            require_approved_line_review(None, edition_id="issue-001", bindings=BINDINGS)

    def test_gate_passes_a_current_approved_record(self):
        require_approved_line_review(
            make_record(), edition_id="issue-001", bindings=BINDINGS
        )


class LineFindingTests(unittest.TestCase):
    """Structured findings, as the judge prompt actually emits them."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_a_structured_finding_survives_write_and_load_as_a_mapping(self):
        record = create_line_review(
            edition_id="issue-001",
            reviewer="Line editor",
            result="changes_required",
            bindings=BINDINGS,
            findings=[STRUCTURED_FINDING, "  A sentence a human typed.  "],
            reviewed_at="2026-07-26T10:00:00+00:00",
        )
        path = write_line_review(line_review_path(self.root, "issue-001"), record)

        # Read the file itself, not the in-memory record: the failure this
        # guards against is a mapping flattened to "{'severity': ...}" on the
        # way to YAML, which only the bytes on disk can disprove.
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertIsInstance(raw["findings"][0], dict)
        self.assertEqual(raw["findings"][0], STRUCTURED_FINDING)
        self.assertEqual(raw["findings"][1], "A sentence a human typed.")

        loaded = load_line_review(path, edition_id="issue-001")
        self.assertEqual(loaded["findings"], raw["findings"])
        self.assertEqual(
            line_review_status(loaded, edition_id="issue-001", bindings=BINDINGS)["findings"],
            raw["findings"],
        )

    def test_a_finding_missing_severity_or_note_is_refused(self):
        for missing in ("severity", "note"):
            finding = {key: value for key, value in STRUCTURED_FINDING.items() if key != missing}
            with self.assertRaisesRegex(ValidationError, f"requires a non-empty {missing}"):
                create_line_review(
                    edition_id="issue-001",
                    reviewer="Line editor",
                    result="changes_required",
                    bindings=BINDINGS,
                    findings=[finding],
                )

    def test_an_unknown_severity_is_refused(self):
        with self.assertRaisesRegex(ValidationError, "severity must be"):
            create_line_review(
                edition_id="issue-001",
                reviewer="Line editor",
                result="changes_required",
                bindings=BINDINGS,
                findings=[{**STRUCTURED_FINDING, "severity": "catastrophic"}],
            )

    def test_load_refuses_a_hand_edited_finding_that_lost_its_note(self):
        record = make_record(
            result="changes_required",
            findings=[{key: value for key, value in STRUCTURED_FINDING.items() if key != "note"}],
        )
        path = write_line_review(line_review_path(self.root, "issue-001"), record)

        with self.assertRaisesRegex(ValidationError, "requires a non-empty note"):
            load_line_review(path, edition_id="issue-001")


class LineScoreTests(unittest.TestCase):
    """Per-article advisory scores: stored, reported, never binding."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def scored_record(self, **overrides) -> dict:
        return create_line_review(
            edition_id="issue-001",
            reviewer="Line editor",
            result="approved",
            bindings=BINDINGS,
            scores={"article": {"structure": 4, "flow": 3, "house_style": 2}},
            reviewed_at="2026-07-26T10:00:00+00:00",
            **overrides,
        )

    def test_scores_land_in_the_article_row_and_come_back_through_status(self):
        path = write_line_review(line_review_path(self.root, "issue-001"), self.scored_record())

        loaded = load_line_review(path, edition_id="issue-001")
        status = line_review_status(loaded, edition_id="issue-001", bindings=BINDINGS)

        self.assertEqual(
            loaded["articles"]["article"],
            {
                "reviewed_at": "2026-07-26T10:00:00+00:00",
                "manuscript_sha256": "1" * 64,
                "scores": {"structure": 4, "flow": 3, "house_style": 2},
            },
        )
        # Authored order survives: the prompt lists its dimensions deliberately.
        self.assertEqual(
            list(loaded["articles"]["article"]["scores"]),
            ["structure", "flow", "house_style"],
        )
        self.assertEqual(
            status["articles"]["article"]["scores"],
            {"structure": 4, "flow": 3, "house_style": 2},
        )
        # A row with no scores carries no scores key, in the record or the status.
        plain = make_record()
        self.assertNotIn("scores", plain["articles"]["article"])
        plain_status = line_review_status(plain, edition_id="issue-001", bindings=BINDINGS)
        self.assertNotIn("scores", plain_status["articles"]["article"])

    def test_changed_scores_never_make_a_record_stale(self):
        """The load-bearing advisory property.  A score is a reading of a piece,
        not a fact about its bytes: re-scoring the same manuscript cannot
        invalidate the reading, and a score that could stale a record would be
        a score that gates."""
        recorded = self.scored_record()
        rescored = self.scored_record()
        rescored["articles"]["article"]["scores"] = {"structure": 1, "flow": 1}

        for record in (recorded, rescored):
            status = line_review_status(record, edition_id="issue-001", bindings=BINDINGS)
            self.assertEqual(status["status"], "approved")
            self.assertEqual(status["articles"]["article"]["status"], "current")
        # And the gate agrees: scores are not part of the comparison at all.
        require_approved_line_review(rescored, edition_id="issue-001", bindings=BINDINGS)

    def test_scores_outside_one_to_five_are_refused(self):
        for value in (0, 6, -1):
            with self.assertRaisesRegex(ValidationError, "must be an integer 1-5"):
                create_line_review(
                    edition_id="issue-001",
                    reviewer="Line editor",
                    result="approved",
                    bindings=BINDINGS,
                    scores={"article": {"structure": value}},
                )

    def test_non_integer_scores_are_refused(self):
        for value in ("4", 4.5, True, None):
            with self.assertRaisesRegex(ValidationError, "must be an integer 1-5"):
                create_line_review(
                    edition_id="issue-001",
                    reviewer="Line editor",
                    result="approved",
                    bindings=BINDINGS,
                    scores={"article": {"structure": value}},
                )

    def test_scores_for_an_unbound_article_are_refused(self):
        with self.assertRaisesRegex(ValidationError, "does not bind"):
            create_line_review(
                edition_id="issue-001",
                reviewer="Line editor",
                result="approved",
                bindings=BINDINGS,
                scores={"phantom": {"structure": 4}},
            )

    def test_load_refuses_a_hand_edited_out_of_range_article_score(self):
        record = self.scored_record()
        record["articles"]["article"]["scores"] = {"structure": 9}
        path = write_line_review(line_review_path(self.root, "issue-001"), record)

        with self.assertRaisesRegex(
            ValidationError, "Line review article article score structure"
        ):
            load_line_review(path, edition_id="issue-001")


class RebindArticlesTests(unittest.TestCase):
    """The partial re-record merge, as a pure function of record and disk."""

    CURRENT = {
        "article": {"manuscript_sha256": "a" * 64},
        "second": {"manuscript_sha256": "b" * 64},
    }

    def two_article_record(self) -> dict:
        return create_line_review(
            edition_id="issue-001",
            reviewer="Line editor",
            result="approved",
            bindings=TWO_ARTICLES,
            scores={"article": {"structure": 4}, "second": {"structure": 2}},
            reviewed_at="2026-07-26T10:00:00+00:00",
        )

    def test_named_articles_rebind_and_the_rest_keep_binding_stamp_and_scores(self):
        record = self.two_article_record()

        merged = rebind_articles(record, bindings=self.CURRENT, article_ids=["second"])

        # "second" is fresh disk state with no stamp yet; create_line_review
        # will stamp it with the new record's timestamp.
        self.assertEqual(merged["second"], self.CURRENT["second"])
        # "article" keeps the recorded hash -- not the drifted disk one -- plus
        # the timestamp and the scores of the reading that produced it.
        self.assertEqual(
            merged["article"],
            {
                "reviewed_at": "2026-07-26T10:00:00+00:00",
                "manuscript_sha256": "1" * 64,
                "scores": {"structure": 4},
            },
        )

        rerecorded = create_line_review(
            edition_id="issue-001",
            reviewer="Line editor",
            result="approved",
            bindings=merged,
            reviewed_at="2026-07-27T09:00:00+00:00",
        )
        self.assertEqual(
            rerecorded["articles"]["article"]["reviewed_at"], "2026-07-26T10:00:00+00:00"
        )
        self.assertEqual(
            rerecorded["articles"]["second"]["reviewed_at"], "2026-07-27T09:00:00+00:00"
        )
        # The re-read piece was not re-scored, so it carries no stale score.
        self.assertNotIn("scores", rerecorded["articles"]["second"])

    def test_a_row_without_scores_is_preserved_without_inventing_one(self):
        record = create_line_review(
            edition_id="issue-001",
            reviewer="Line editor",
            result="approved",
            bindings=TWO_ARTICLES,
            reviewed_at="2026-07-26T10:00:00+00:00",
        )

        merged = rebind_articles(record, bindings=self.CURRENT, article_ids=["second"])

        self.assertEqual(
            merged["article"],
            {"reviewed_at": "2026-07-26T10:00:00+00:00", "manuscript_sha256": "1" * 64},
        )

    def test_articles_that_left_the_edition_fall_out_of_the_merge(self):
        record = self.two_article_record()
        record["articles"]["ghost"] = {
            "reviewed_at": "2026-07-26T10:00:00+00:00",
            "manuscript_sha256": "c" * 64,
        }

        merged = rebind_articles(record, bindings=self.CURRENT, article_ids=["second"])

        self.assertEqual(set(merged), {"article", "second"})

    def test_rebinding_requires_an_existing_record(self):
        with self.assertRaisesRegex(ValidationError, "amends an existing record"):
            rebind_articles(None, bindings=self.CURRENT, article_ids=["article"])

    def test_rebinding_requires_at_least_one_article(self):
        with self.assertRaisesRegex(ValidationError, "at least one article"):
            rebind_articles(
                self.two_article_record(), bindings=self.CURRENT, article_ids=[" "]
            )

    def test_rebinding_refuses_articles_the_edition_does_not_carry(self):
        with self.assertRaisesRegex(ValidationError, "does not carry: phantom"):
            rebind_articles(
                self.two_article_record(), bindings=self.CURRENT, article_ids=["phantom"]
            )

    def test_rebinding_refuses_an_unnamed_article_with_no_recorded_review(self):
        """The edition gained "second" after the record was written; a partial
        record that neither names nor can preserve it must refuse rather than
        write a record with a silent hole."""
        with self.assertRaisesRegex(
            ValidationError, "no recorded review to preserve: second"
        ):
            rebind_articles(make_record(), bindings=self.CURRENT, article_ids=["article"])


class LoadDegradationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = line_review_path(self.root, "issue-001")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def test_a_missing_record_is_no_record_rather_than_an_error(self):
        self.assertIsNone(load_line_review(self.path, edition_id="issue-001"))

    def test_an_unparseable_record_refuses_and_names_the_file(self):
        self.path.write_text("result: [unclosed", encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "line.yaml"):
            load_line_review(self.path, edition_id="issue-001")

    def test_load_rejects_an_unsupported_schema_version(self):
        write_line_review(self.path, make_record(schema_version=2))

        with self.assertRaisesRegex(ValidationError, "schema_version must be 1"):
            load_line_review(self.path, edition_id="issue-001")

    def test_load_rejects_a_mismatched_edition_and_a_missing_reviewer(self):
        write_line_review(self.path, make_record(reviewer=""))

        with self.assertRaises(ValidationError) as caught:
            load_line_review(self.path, edition_id="issue-002")
        message = str(caught.exception)
        self.assertIn("does not match", message)
        self.assertIn("requires reviewer", message)

    def test_load_rejects_a_blank_per_article_reviewed_at(self):
        record = make_record()
        record["articles"] = {"article": {**BINDINGS["article"], "reviewed_at": "  "}}
        write_line_review(self.path, record)

        with self.assertRaisesRegex(ValidationError, "reviewed_at must be a non-empty"):
            load_line_review(self.path, edition_id="issue-001")

    def test_load_rejects_a_record_with_no_articles_and_a_bad_hash(self):
        write_line_review(self.path, make_record(articles={}))
        with self.assertRaisesRegex(ValidationError, "requires an articles mapping"):
            load_line_review(self.path, edition_id="issue-001")

        write_line_review(
            self.path, make_record(articles={"article": {"manuscript_sha256": "nope"}})
        )
        with self.assertRaisesRegex(ValidationError, "invalid manuscript_sha256"):
            load_line_review(self.path, edition_id="issue-001")

    def test_load_rejects_a_changes_required_record_with_no_findings(self):
        write_line_review(self.path, make_record(result="changes_required"))

        with self.assertRaisesRegex(ValidationError, "needs at least one finding"):
            load_line_review(self.path, edition_id="issue-001")


if __name__ == "__main__":
    unittest.main()
