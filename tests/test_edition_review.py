from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from magazine import ValidationError
from magazine.edition_review import (
    EDITION_REVIEW_SCHEMA_VERSION,
    create_edition_review,
    current_edition_bindings,
    edition_drift,
    edition_review_path,
    edition_review_status,
    load_edition_review,
    manifest_projection,
    require_approved_edition_review,
    write_edition_review,
)
from magazine.manifest import load_edition
from magazine.records import load_records
from magazine.release import rename_collecting_edition
from magazine.render_review import sha256
from test_manifest import (
    add_source,
    load_edition_with_records,
    make_project,
    set_open_edition,
)


# The whole of what an issue verdict binds: the editorial, ``edition.yaml``,
# and every manuscript.  There is no per-article verdict here -- the articles
# mapping exists so that any manuscript moving can stale the single verdict.
BINDINGS = {
    "editorial_sha256": "a" * 64,
    "manifest_sha256": "b" * 64,
    "articles": {
        "opener": {"manuscript_sha256": "1" * 64},
        "second": {"manuscript_sha256": "2" * 64},
    },
}


def bindings_with(**overrides) -> dict:
    """A copy of BINDINGS with one bound byte replaced, articles deep-copied."""
    current = {
        "editorial_sha256": BINDINGS["editorial_sha256"],
        "manifest_sha256": BINDINGS["manifest_sha256"],
        "articles": {
            article_id: dict(row) for article_id, row in BINDINGS["articles"].items()
        },
    }
    current.update(overrides)
    return current


def make_record(**overrides) -> dict:
    record = create_edition_review(
        edition_id="issue-001",
        reviewer="Managing editor",
        result="approved",
        bindings=BINDINGS,
        reviewed_at="2026-07-30T10:00:00+00:00",
    )
    record.update(overrides)
    return record


STRUCTURED_FINDING = {
    "severity": "blocking",
    "article": "editorial",
    "locator": "- | Elsewhere in this issue, Argona shows | 1",
    "category": "prose_table_of_contents",
    # Required on every authored finding since version 2, and constant on this
    # lens: ``prompts/edition-review.md`` says the arrangement of the issue is
    # the editors' own, so there is never an author to route a finding around.
    "disposition": "fix",
    "note": "The editorial introduces five pieces in sequence and stakes no claim.",
}


class EditionRecordTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "reviews" / "edition.yaml"

    def test_record_roundtrip_binds_editorial_manifest_and_every_manuscript(self):
        path = write_edition_review(self.path, make_record())

        loaded = load_edition_review(path, edition_id="issue-001")
        status = edition_review_status(loaded, edition_id="issue-001", bindings=BINDINGS)

        self.assertEqual(EDITION_REVIEW_SCHEMA_VERSION, 2)
        self.assertEqual(loaded["schema_version"], 2)
        self.assertEqual(loaded["editorial_sha256"], "a" * 64)
        self.assertEqual(loaded["manifest_sha256"], "b" * 64)
        self.assertEqual(
            loaded["articles"],
            {
                "opener": {"manuscript_sha256": "1" * 64},
                "second": {"manuscript_sha256": "2" * 64},
            },
        )
        self.assertEqual(status["status"], "approved")
        self.assertEqual(status["reviewer"], "Managing editor")
        self.assertEqual(status["reviewed_at"], "2026-07-30T10:00:00+00:00")
        self.assertEqual(status["drift"], [])

    def test_every_bound_byte_stales_the_one_verdict_on_its_own(self):
        """The load-bearing contract of this kind: the editorial, the manifest,
        and *any single* manuscript each stale the whole issue verdict by
        themselves, and the drift list names exactly the one that moved.

        There is no partial rebind here and there must not be one.  Coherence
        -- through-line, running order, redundancy, cover promise -- is a
        function of all these bytes at once, so re-reading one rewritten piece
        cannot preserve a verdict about how the pieces sit together."""
        record = make_record()

        cases = {
            "editorial": bindings_with(editorial_sha256="f" * 64),
            "edition.yaml": bindings_with(manifest_sha256="f" * 64),
            "manuscript:opener": bindings_with(
                articles={
                    "opener": {"manuscript_sha256": "f" * 64},
                    "second": {"manuscript_sha256": "2" * 64},
                }
            ),
            "manuscript:second": bindings_with(
                articles={
                    "opener": {"manuscript_sha256": "1" * 64},
                    "second": {"manuscript_sha256": "f" * 64},
                }
            ),
        }
        for name, current in cases.items():
            with self.subTest(moved=name):
                status = edition_review_status(
                    record, edition_id="issue-001", bindings=current
                )
                self.assertEqual(status["status"], "stale")
                self.assertEqual(status["drift"], [name])

    def test_drift_reports_editorial_then_manifest_then_sorted_manuscripts(self):
        record = make_record()
        current = {
            "editorial_sha256": "f" * 64,
            "manifest_sha256": "f" * 64,
            "articles": {
                "opener": {"manuscript_sha256": "f" * 64},
                "second": {"manuscript_sha256": "f" * 64},
            },
        }

        self.assertEqual(
            edition_drift(record, current),
            ["editorial", "edition.yaml", "manuscript:opener", "manuscript:second"],
        )

    def test_an_added_or_removed_article_is_drift(self):
        """A piece joining or leaving changes which issue the verdict is about,
        so both read as ``manuscript:<id>`` drift rather than as no change."""
        record = make_record()

        added = bindings_with(
            articles={
                **BINDINGS["articles"],
                "late-arrival": {"manuscript_sha256": "c" * 64},
            }
        )
        status = edition_review_status(record, edition_id="issue-001", bindings=added)
        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["drift"], ["manuscript:late-arrival"])

        removed = bindings_with(articles={"opener": {"manuscript_sha256": "1" * 64}})
        status = edition_review_status(record, edition_id="issue-001", bindings=removed)
        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["drift"], ["manuscript:second"])

    def test_an_edition_with_no_editorial_binds_null_and_is_not_stale(self):
        """An issue that opens without an editorial is an ordinary issue, not a
        broken one: the binding is stored as null, loads, and does not read as
        drift against an edition that still has none."""
        bindings = bindings_with(editorial_sha256=None)
        path = write_edition_review(
            self.path,
            create_edition_review(
                edition_id="issue-001",
                reviewer="Managing editor",
                result="approved",
                bindings=bindings,
                reviewed_at="2026-07-30T10:00:00+00:00",
            ),
        )

        loaded = load_edition_review(path, edition_id="issue-001")
        status = edition_review_status(loaded, edition_id="issue-001", bindings=bindings)

        self.assertIsNone(loaded["editorial_sha256"])
        self.assertEqual(status["status"], "approved")
        self.assertEqual(status["drift"], [])

        # ...but an editorial *appearing* is a change to the issue.
        status = edition_review_status(
            loaded, edition_id="issue-001", bindings=bindings_with()
        )
        self.assertEqual(status["drift"], ["editorial"])

    def test_a_different_edition_id_is_stale(self):
        status = edition_review_status(
            make_record(), edition_id="issue-002", bindings=BINDINGS
        )
        self.assertEqual(status["status"], "stale")

    def test_changes_required_record_needs_a_finding(self):
        with self.assertRaisesRegex(ValidationError, "needs at least one finding"):
            create_edition_review(
                edition_id="issue-001",
                reviewer="Managing editor",
                result="changes_required",
                bindings=BINDINGS,
            )

    def test_create_refuses_an_unnamed_reviewer_and_an_unknown_result(self):
        with self.assertRaisesRegex(ValidationError, "requires a reviewer"):
            create_edition_review(
                edition_id="issue-001", reviewer="  ", result="approved", bindings=BINDINGS
            )
        with self.assertRaisesRegex(ValidationError, "approved or changes_required"):
            create_edition_review(
                edition_id="issue-001",
                reviewer="Managing editor",
                result="rejected",
                bindings=BINDINGS,
            )

    def test_create_refuses_bindings_without_the_manifest_hash(self):
        """A record that does not bind ``edition.yaml`` leaves the running order
        and the cover line free to change under an approved verdict."""
        with self.assertRaisesRegex(ValidationError, "manifest_sha256"):
            create_edition_review(
                edition_id="issue-001",
                reviewer="Managing editor",
                result="approved",
                bindings={"editorial_sha256": "a" * 64, "articles": {}},
            )

    def test_load_rejects_an_absent_articles_mapping(self):
        record = make_record()
        del record["articles"]
        path = write_edition_review(self.path, record)

        with self.assertRaisesRegex(ValidationError, "requires an articles mapping"):
            load_edition_review(path, edition_id="issue-001")

    def test_load_rejects_invalid_bound_hashes(self):
        for record, expected in (
            (make_record(manifest_sha256="nope"), "invalid manifest_sha256"),
            (make_record(editorial_sha256="nope"), "invalid editorial_sha256"),
            (
                make_record(articles={"opener": {"manuscript_sha256": "nope"}}),
                "article opener has invalid manuscript_sha256",
            ),
            (make_record(articles={"opener": "1" * 64}), "article opener must be a mapping"),
        ):
            with self.subTest(expected=expected):
                path = write_edition_review(self.path, record)
                with self.assertRaisesRegex(ValidationError, expected):
                    load_edition_review(path, edition_id="issue-001")

    def test_load_rejects_an_unsupported_schema_version(self):
        path = write_edition_review(self.path, make_record(schema_version=3))

        with self.assertRaisesRegex(ValidationError, "schema_version must be 1 or 2"):
            load_edition_review(path, edition_id="issue-001")

    def test_a_version_one_record_still_loads_without_a_disposition(self):
        """Version 1 predates ``disposition`` and must not be re-read to add it.

        The field replaced the severity cap and is required of anything being
        *authored*, but a record written before it existed answered a question
        nobody asked it.  Refusing to load one would demand a re-read of a
        shipped issue to supply a key its judge was never shown -- which is the
        same bargain the evidence record already struck with its version 1
        ledger binding, and the reason the bump is a bump rather than a break.
        """

        legacy = make_record(
            schema_version=1,
            result="changes_required",
            findings=[
                {
                    "severity": "major",
                    "article": "edition",
                    "category": "uniformity",
                    "note": "Filed before dispositions existed.",
                }
            ],
        )
        path = write_edition_review(self.path, legacy)

        loaded = load_edition_review(path, edition_id="issue-001")

        self.assertEqual(loaded["schema_version"], 1)
        # Read back exactly as written: unrouted, not quietly defaulted to
        # ``fix``.  Defaulting would launder an unclassified finding into the
        # writer's pile, and the whole point of the field is that who repairs a
        # defect is stated rather than assumed.
        self.assertNotIn("disposition", loaded["findings"][0])

    def test_load_names_the_file_when_the_record_is_unparseable(self):
        """A hand-damaged record must refuse as a validation error naming the
        file, not escape as a raw YAML traceback."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("result: [unclosed", encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "edition.yaml"):
            load_edition_review(self.path, edition_id="issue-001")

    def test_load_returns_none_when_no_record_exists(self):
        self.assertIsNone(load_edition_review(self.path, edition_id="issue-001"))

    def test_edition_review_path_lives_under_the_edition_reviews_directory(self):
        self.assertEqual(
            edition_review_path(self.root / "editions", "issue-001"),
            self.root / "editions" / "issue-001" / "reviews" / "edition.yaml",
        )


class EditionFindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "reviews" / "edition.yaml"

    def test_structured_and_string_findings_survive_write_and_load(self):
        """The judge emits mappings; a human still types sentences.  Both are
        stored as authored -- asserted against the re-read YAML, because the
        bug this guards is a mapping flattened into a line of Python repr on
        the way to disk."""
        record = create_edition_review(
            edition_id="issue-001",
            reviewer="Managing editor",
            result="changes_required",
            bindings=BINDINGS,
            findings=[STRUCTURED_FINDING, "The cover deck would fit any issue."],
            reviewed_at="2026-07-30T10:00:00+00:00",
        )
        path = write_edition_review(self.path, record)

        on_disk = yaml.safe_load(path.read_text(encoding="utf-8"))
        loaded = load_edition_review(path, edition_id="issue-001")

        self.assertEqual(on_disk["findings"][0], STRUCTURED_FINDING)
        self.assertIsInstance(on_disk["findings"][0], dict)
        self.assertEqual(on_disk["findings"][1], "The cover deck would fit any issue.")
        self.assertEqual(loaded["findings"], on_disk["findings"])
        status = edition_review_status(loaded, edition_id="issue-001", bindings=BINDINGS)
        self.assertEqual(status["status"], "changes_required")
        self.assertEqual(status["findings"], on_disk["findings"])

    def test_a_whole_issue_finding_stores_article_edition(self):
        """``article: edition`` is the scope the prompt gives an issue-level
        defect (the swap test files one for the edition, not one per piece)."""
        finding = {
            "severity": "major",
            "article": "edition",
            "category": "uniformity",
            "disposition": "fix",
            "note": "Every piece closes on the same widening cadence.",
        }
        path = write_edition_review(
            self.path,
            create_edition_review(
                edition_id="issue-001",
                reviewer="Managing editor",
                result="changes_required",
                bindings=BINDINGS,
                findings=[finding],
                reviewed_at="2026-07-30T10:00:00+00:00",
            ),
        )

        loaded = load_edition_review(path, edition_id="issue-001")

        self.assertEqual(loaded["findings"][0]["article"], "edition")
        self.assertEqual(loaded["findings"][0], finding)

    def test_a_structured_finding_missing_severity_or_note_is_refused(self):
        for missing in ("severity", "note"):
            with self.subTest(missing=missing):
                finding = {key: value for key, value in STRUCTURED_FINDING.items() if key != missing}
                with self.assertRaisesRegex(ValidationError, f"requires a non-empty {missing}"):
                    create_edition_review(
                        edition_id="issue-001",
                        reviewer="Managing editor",
                        result="changes_required",
                        bindings=BINDINGS,
                        findings=[finding],
                    )

    def test_an_unknown_severity_is_refused(self):
        with self.assertRaisesRegex(ValidationError, "severity must be"):
            create_edition_review(
                edition_id="issue-001",
                reviewer="Managing editor",
                result="changes_required",
                bindings=BINDINGS,
                findings=[{**STRUCTURED_FINDING, "severity": "catastrophic"}],
            )

    def test_load_refuses_a_hand_edited_finding(self):
        record = make_record(
            result="changes_required",
            findings=[{"severity": "urgent", "note": "Hand-edited into the file."}],
        )
        path = write_edition_review(self.path, record)

        with self.assertRaisesRegex(ValidationError, "severity must be"):
            load_edition_review(path, edition_id="issue-001")


class EditionScoreTests(unittest.TestCase):
    SCORES = {
        "through_line": 2,
        "editorial_strength": 1,
        "running_order": 4,
        "balance": 3,
        "cover_promise": 4,
    }

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "reviews" / "edition.yaml"

    _DEFAULT = object()

    def scored_record(self, scores=_DEFAULT) -> dict:
        return create_edition_review(
            edition_id="issue-001",
            reviewer="Managing editor",
            result="approved",
            bindings=BINDINGS,
            scores=self.SCORES if scores is self._DEFAULT else scores,
            reviewed_at="2026-07-30T10:00:00+00:00",
        )

    def test_record_level_scores_round_trip_and_reach_the_status(self):
        """Scores belong to the record, not to an article row: one verdict on
        one issue, so one set of dimensions."""
        path = write_edition_review(self.path, self.scored_record())

        loaded = load_edition_review(path, edition_id="issue-001")
        status = edition_review_status(loaded, edition_id="issue-001", bindings=BINDINGS)

        self.assertEqual(loaded["scores"], self.SCORES)
        self.assertEqual(list(loaded["scores"]), list(self.SCORES))
        self.assertEqual(status["scores"], self.SCORES)

    def test_a_record_without_scores_stores_an_empty_map(self):
        record = self.scored_record(scores=None)
        # ``scores=None`` is the no-scores case; an empty map is what a record
        # written by a judge that scored nothing looks like.
        self.assertEqual(record["scores"], {})
        loaded = load_edition_review(
            write_edition_review(self.path, record), edition_id="issue-001"
        )
        self.assertEqual(loaded["scores"], {})
        status = edition_review_status(loaded, edition_id="issue-001", bindings=BINDINGS)
        self.assertEqual(status["scores"], {})

    def test_out_of_range_non_integer_and_boolean_scores_are_refused(self):
        for scores in ({"through_line": 0}, {"through_line": 6}, {"through_line": "4"},
                       {"through_line": 3.5}, {"through_line": True}):
            with self.subTest(scores=scores):
                with self.assertRaisesRegex(ValidationError, "must be an integer 1-5"):
                    self.scored_record(scores=scores)

    def test_load_refuses_a_hand_edited_out_of_range_score(self):
        record = make_record(scores={"through_line": 9})
        path = write_edition_review(self.path, record)

        with self.assertRaisesRegex(ValidationError, "must be an integer 1-5"):
            load_edition_review(path, edition_id="issue-001")

    def test_changing_a_score_does_not_stale_the_record(self):
        """Scores are advisory and must never participate in staleness.  A
        record whose scores were rewritten still binds the same bytes, so it is
        still a current verdict on the issue in front of it -- and nothing in
        this module may read a score to decide anything."""
        record = self.scored_record()
        self.assertEqual(
            edition_review_status(record, edition_id="issue-001", bindings=BINDINGS)["status"],
            "approved",
        )

        record["scores"] = {"through_line": 5, "editorial_strength": 5}

        status = edition_review_status(record, edition_id="issue-001", bindings=BINDINGS)
        self.assertEqual(status["status"], "approved")
        self.assertEqual(status["drift"], [])
        self.assertEqual(edition_drift(record, BINDINGS), [])
        # The gate agrees: a rewritten score cannot open or close a release.
        require_approved_edition_review(record, edition_id="issue-001", bindings=BINDINGS)


class EditionGateTests(unittest.TestCase):
    def test_an_approved_record_with_an_editor_decision_still_refuses(self):
        """The combination the whole disposition field exists to catch.

        An ``editor_decision`` finding is a real defect the lens found and was
        forbidden to hand to a writer, so it is entirely compatible with an
        approving verdict over unmoved bytes: the managing editor has said what
        is wrong and said it is not the writer's to fix.  Nothing inside the
        verdict stops the issue shipping with one outstanding, which is exactly
        the shape of the old severity cap -- a defect that survives under a word
        that means "clean".  The release gate is the only thing that can refuse
        it, and it must refuse it *separately* from the approved/stale question
        rather than folding the two together, or an approval would launder it.
        """

        record = create_edition_review(
            edition_id="issue-001",
            reviewer="Managing editor",
            result="approved",
            bindings=BINDINGS,
            findings=[
                {
                    "severity": "minor",
                    "article": "editorial",
                    "locator": "- | a retained sentence of the source author's | 1",
                    "category": "uniformity",
                    "disposition": "editor_decision",
                    "note": "The author's own phrasing; a human picks the remedy.",
                }
            ],
            reviewed_at="2026-07-30T10:00:00+00:00",
        )

        status = edition_review_status(record, edition_id="issue-001", bindings=BINDINGS)
        # Approved and current, and still carrying an unresolved ruling. Both
        # facts are reported; neither is allowed to hide the other.
        self.assertEqual(status["status"], "approved")
        self.assertEqual(status["drift"], [])
        self.assertEqual(status["editor_decisions"], 1)

        with self.assertRaisesRegex(ValidationError, "editor_decision"):
            require_approved_edition_review(
                record, edition_id="issue-001", bindings=BINDINGS
            )

        # And the refusal names the finding rather than counting it, so an
        # operator cannot clear the gate without having read what is in it.
        try:
            require_approved_edition_review(
                record, edition_id="issue-001", bindings=BINDINGS
            )
        except ValidationError as error:
            message = "\n".join(error.errors)
        self.assertIn("uniformity", message)
        self.assertIn("editorial", message)
        self.assertIn("waiting on a human ruling", message)

    def test_a_disposition_fix_finding_does_not_trip_the_editor_gate(self):
        """The gate must not fire on ordinary findings, or it fires on every
        record and gets switched off."""

        record = create_edition_review(
            edition_id="issue-001",
            reviewer="Managing editor",
            result="approved",
            bindings=BINDINGS,
            findings=[
                {
                    "severity": "minor",
                    "article": "edition",
                    "category": "uniformity",
                    "disposition": "fix",
                    "note": "A defect the writer clears.",
                }
            ],
            reviewed_at="2026-07-30T10:00:00+00:00",
        )

        self.assertEqual(
            edition_review_status(
                record, edition_id="issue-001", bindings=BINDINGS
            )["editor_decisions"],
            0,
        )
        require_approved_edition_review(
            record, edition_id="issue-001", bindings=BINDINGS
        )

    def test_gate_refuses_missing_stale_and_changes_required_records(self):
        with self.assertRaisesRegex(ValidationError, "required_before_release"):
            require_approved_edition_review(None, edition_id="issue-001", bindings=BINDINGS)

        stale = bindings_with(manifest_sha256="f" * 64)
        with self.assertRaisesRegex(ValidationError, "stale.*edition.yaml"):
            require_approved_edition_review(
                make_record(), edition_id="issue-001", bindings=stale
            )

        rejected = make_record(
            result="changes_required", findings=["The cover promises another issue."]
        )
        with self.assertRaisesRegex(ValidationError, "changes_required"):
            require_approved_edition_review(
                rejected, edition_id="issue-001", bindings=BINDINGS
            )

    def test_gate_refusal_names_the_command_that_records_the_verdict(self):
        with self.assertRaises(ValidationError) as caught:
            require_approved_edition_review(None, edition_id="issue-001", bindings=BINDINGS)

        self.assertIn("mag review record --kind edition", str(caught.exception))

    def test_gate_passes_a_current_approved_record(self):
        require_approved_edition_review(
            make_record(), edition_id="issue-001", bindings=BINDINGS
        )


class EditionBindingsTests(unittest.TestCase):
    """``current_edition_bindings`` over a real project on disk."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_project(self.root)
        self.manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"

    def add_second_article(self) -> None:
        add_source(self.root, "source-two", body="Second source body.\n")
        edition_dir = self.root / "editions" / "issue-001"
        (edition_dir / "articles" / "second.md").write_text(
            "Second source body.", encoding="utf-8"
        )
        manifest = yaml.safe_load(self.manifest_path.read_text(encoding="utf-8"))
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
        self.manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )

    def bindings(self) -> dict:
        return current_edition_bindings(
            load_edition_with_records(self.root), manifest_path=self.manifest_path
        )

    def read_manifest(self) -> dict:
        return yaml.safe_load(self.manifest_path.read_text(encoding="utf-8"))

    def write_manifest(self, manifest: dict) -> None:
        self.manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )

    def approved_record(self) -> dict:
        """An approved verdict over the edition exactly as it stands now."""
        return create_edition_review(
            edition_id="issue-001",
            reviewer="Managing editor",
            result="approved",
            bindings=self.bindings(),
            reviewed_at="2026-07-30T10:00:00+00:00",
        )

    def drift(self, record: dict) -> list[str]:
        return edition_review_status(
            record, edition_id="issue-001", bindings=self.bindings()
        )["drift"]

    def test_bindings_cover_the_editorial_the_manifest_and_every_manuscript(self):
        self.add_second_article()

        bindings = self.bindings()

        self.assertEqual(set(bindings), {"editorial_sha256", "manifest_sha256", "articles"})
        self.assertEqual(set(bindings["articles"]), {"article", "second"})
        for article_id, row in bindings["articles"].items():
            self.assertEqual(set(row), {"manuscript_sha256"}, article_id)
            self.assertRegex(row["manuscript_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(bindings["editorial_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(bindings["manifest_sha256"], r"^[0-9a-f]{64}$")

    def test_an_approved_record_goes_stale_when_any_real_file_moves(self):
        """End to end against real bytes: rewriting the editorial, the cover
        deck in ``edition.yaml``, or one manuscript each stales the verdict on
        its own, naming what moved."""
        self.add_second_article()
        edition_dir = self.root / "editions" / "issue-001"
        record = create_edition_review(
            edition_id="issue-001",
            reviewer="Managing editor",
            result="approved",
            bindings=self.bindings(),
            reviewed_at="2026-07-30T10:00:00+00:00",
        )
        self.assertEqual(
            edition_review_status(
                record, edition_id="issue-001", bindings=self.bindings()
            )["status"],
            "approved",
        )

        editorial = edition_dir / "editorial.md"
        editorial.write_text(
            editorial.read_text(encoding="utf-8") + "\n\nOne more line.", encoding="utf-8"
        )
        status = edition_review_status(
            record, edition_id="issue-001", bindings=self.bindings()
        )
        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["drift"], ["editorial"])

        # Re-record over the current bytes, then move only the cover line.
        record = create_edition_review(
            edition_id="issue-001",
            reviewer="Managing editor",
            result="approved",
            bindings=self.bindings(),
            reviewed_at="2026-07-30T11:00:00+00:00",
        )
        manifest = yaml.safe_load(self.manifest_path.read_text(encoding="utf-8"))
        manifest["cover"]["headline"] = "A different promise"
        self.manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
        status = edition_review_status(
            record, edition_id="issue-001", bindings=self.bindings()
        )
        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["drift"], ["edition.yaml"])

        # And once more with only the second manuscript rewritten.
        record = create_edition_review(
            edition_id="issue-001",
            reviewer="Managing editor",
            result="approved",
            bindings=self.bindings(),
            reviewed_at="2026-07-30T12:00:00+00:00",
        )
        manuscript = edition_dir / "articles" / "second.md"
        manuscript.write_text(
            manuscript.read_text(encoding="utf-8") + " Rewritten.", encoding="utf-8"
        )
        status = edition_review_status(
            record, edition_id="issue-001", bindings=self.bindings()
        )
        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["drift"], ["manuscript:second"])

    def test_the_running_order_the_titles_and_the_cover_deck_all_stale_it(self):
        """The three manifest facts the prompt puts in front of the judge.
        Projecting the manifest rather than hashing it must not cost any of
        them: each is an editorial change and each has to be named as
        ``edition.yaml`` drift on its own."""
        self.add_second_article()
        approved = self.approved_record()

        manifest = self.read_manifest()
        manifest["articles"].reverse()
        self.write_manifest(manifest)
        self.assertEqual(self.drift(approved), ["edition.yaml"])

        approved = self.approved_record()
        manifest = self.read_manifest()
        manifest["articles"][0]["title"] = "Second, retitled"
        manifest["articles"][0]["short_title"] = "Second"
        self.write_manifest(manifest)
        self.assertEqual(self.drift(approved), ["edition.yaml"])

        approved = self.approved_record()
        manifest = self.read_manifest()
        manifest["cover"]["deck"] = "A promise the issue now makes"
        self.write_manifest(manifest)
        self.assertEqual(self.drift(approved), ["edition.yaml"])

        approved = self.approved_record()
        manifest = self.read_manifest()
        manifest["articles"][0]["content_mode"] = "faithful_synthesis"
        self.write_manifest(manifest)
        self.assertEqual(self.drift(approved), ["edition.yaml"])

    def test_reserializing_the_manifest_unchanged_is_not_drift(self):
        """``mag pin`` and the release transaction both rewrite the file through
        ``dump_yaml``; re-wrapped lines and reordered keys are not editorial
        changes and a byte hash could not tell the difference."""
        approved = self.approved_record()

        manifest = self.read_manifest()
        self.manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=True, width=20), encoding="utf-8"
        )

        self.assertEqual(self.drift(approved), [])


class EditionRenameTests(unittest.TestCase):
    """The stable-id rename ``mag finish`` performs, against a real project.

    Renaming a collecting edition to its finished id rewrites ``edition.yaml``'s
    ``id`` and every ``editions/<id>/`` path inside it.  A verdict bound to the
    file's bytes therefore read as stale the instant an edition was finished --
    always, and for no editorial reason -- which is why the binding is a
    projection.
    """

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_project(self.root)
        set_open_edition(self.root, "issue-001", issue_number=1)

    def manifest_path(self, edition_id: str) -> Path:
        return self.root / "editions" / edition_id / "edition.yaml"

    def bindings(self, edition_id: str) -> dict:
        records = {
            record.id: record
            for record in load_records(self.root / "library" / "sources")
        }
        edition = load_edition(
            self.root,
            edition_id,
            set(records),
            publication_name="Test Review",
            source_records=records,
        )
        return current_edition_bindings(
            edition, manifest_path=self.manifest_path(edition_id)
        )

    def finish_rename(self, new_id: str) -> None:
        rename_collecting_edition(
            self.root / "library" / "release-state.yaml",
            self.root / "editions",
            old_id="issue-001",
            new_id=new_id,
        )

    def test_the_stable_id_rename_leaves_an_approved_verdict_current(self):
        write_edition_review(
            edition_review_path(self.root / "editions", "issue-001"),
            create_edition_review(
                edition_id="issue-001",
                reviewer="Managing editor",
                result="approved",
                bindings=self.bindings("issue-001"),
                reviewed_at="2026-07-30T10:00:00+00:00",
            ),
        )
        before = sha256(self.manifest_path("issue-001"))

        self.finish_rename("001-issue")

        # The file really did change: the old whole-file binding could not have
        # survived this, which is the bug the projection exists to fix.
        self.assertNotEqual(sha256(self.manifest_path("001-issue")), before)
        self.assertIn(
            "editions/001-issue/articles/article.md",
            self.manifest_path("001-issue").read_text(encoding="utf-8"),
        )

        # The rename rewrites the record's own edition_id, so it loads under the
        # finished identity exactly as it does on disk.
        record = load_edition_review(
            edition_review_path(self.root / "editions", "001-issue"),
            edition_id="001-issue",
        )
        status = edition_review_status(
            record, edition_id="001-issue", bindings=self.bindings("001-issue")
        )

        self.assertEqual(status["drift"], [])
        self.assertEqual(status["status"], "approved")

    def test_an_editorial_change_made_after_the_rename_still_stales_it(self):
        """The projection must not have bought currency by binding nothing: the
        same edition, renamed and then genuinely edited, is stale."""
        record = create_edition_review(
            edition_id="issue-001",
            reviewer="Managing editor",
            result="approved",
            bindings=self.bindings("issue-001"),
            reviewed_at="2026-07-30T10:00:00+00:00",
        )
        self.finish_rename("001-issue")

        path = self.manifest_path("001-issue")
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        manifest["cover"]["headline"] = "A different promise"
        path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

        status = edition_review_status(
            record, edition_id="001-issue", bindings=self.bindings("001-issue")
        )

        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["drift"], ["edition.yaml"])

    def test_the_projection_drops_the_identity_and_keeps_everything_else(self):
        manifest = yaml.safe_load(
            self.manifest_path("issue-001").read_text(encoding="utf-8")
        )
        manifest["status"] = "collecting"

        projection = manifest_projection(manifest, edition_id="issue-001")

        self.assertNotIn("id", projection)
        self.assertNotIn("status", projection)
        self.assertEqual(projection["title"], "Issue")
        self.assertEqual(projection["cover"], {"headline": "Issue"})
        self.assertEqual(
            projection["editorial"], "editions/<edition>/editorial.md"
        )
        self.assertEqual(
            projection["articles"][0]["manuscript"],
            "editions/<edition>/articles/article.md",
        )
        # Only this edition's own prefix is neutralized; a path into another
        # edition names a different file and stays bound as written.
        self.assertEqual(
            manifest_projection(
                {"art_direction_path": "editions/issue-002/art/illustrations.yaml"},
                edition_id="issue-001",
            ),
            {"art_direction_path": "editions/issue-002/art/illustrations.yaml"},
        )


if __name__ == "__main__":
    unittest.main()
