from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from magazine import ValidationError
from magazine.learning_review import (
    EXPLAINER_CONTENT_MODE,
    LEARNING_PERSONAS,
    LEARNING_REVIEW_SCHEMA_VERSION,
    create_learning_review,
    current_learning_bindings,
    explainer_article_ids,
    furniture_projection,
    furniture_sha256,
    learning_drift,
    learning_review_path,
    learning_review_status,
    load_learning_review,
    require_approved_learning_review,
    write_learning_review,
)
from magazine.manifest import CONTENT_MODES
from test_manifest import (
    add_curated_figure,
    add_source,
    load_edition_with_records,
    make_project,
)


# What a learning record binds: one hash over the editor-authored furniture, and
# one manuscript hash per explainer.  No feature manuscript appears here, and
# that absence is the contract this module exists to keep.
BINDINGS = {
    "furniture_sha256": "1" * 64,
    "explainers": {"mcp-in-a-nutshell": {"manuscript_sha256": "2" * 64}},
}

# The prompt's own example blocks, transcribed from prompts/learning-review.md
# so the recorder is tested against the shape the judge actually emits.
COMPREHENSION = [
    {
        "persona": "nadia",
        "language": "en",
        "correct": 5,
        "of": 6,
        "questions": [
            {
                "question": "What boundary does the protocol define?",
                "answer": "Between the AI application and external programs.",
                "cite": "The Model Context Protocol defines how",
                "correct": True,
            },
            {
                # The failed question: the piece never answers it, so there is
                # no answer and no cite, and the null is the evidence.
                "question": "How many servers can one host connect at once?",
                "answer": None,
                "cite": None,
                "correct": False,
            },
        ],
    }
]

MANAGER_TAKEAWAYS = [
    {
        "article": "mcp-in-a-nutshell",
        "decision": "Pilot one MCP server behind the existing gateway this quarter.",
        "claims": [
            "Each server exposes a bounded set of actions.",
            "Servers are stateless, so we can skip session handling.",
            "One host can use several servers without merging them.",
        ],
        "adjudication": [
            {
                "item": "decision",
                "verdict": "supported",
                "cite": "The host owns intelligence and orchestration",
            },
            {
                "item": "claim-2",
                "verdict": "contradicted",
                "cite": "Remote servers use Streamable HTTP",
            },
        ],
    }
]

FINDING = {
    "severity": "blocking",
    "article": "mcp-in-a-nutshell",
    "locator": "Key ideas | Servers are stateless by default | 1",
    "category": "unsupported_inference",
    "persona": "marcus",
    "note": "Run A claim 2 was \"we can skip session handling\". The body says otherwise.",
}

SCORES = {"comprehension": 4, "standalone_sufficiency": 3, "technical_honesty": 4}


def make_record(**overrides) -> dict:
    record = create_learning_review(
        edition_id="issue-001",
        reviewer="Reader panel",
        result="approved",
        bindings=BINDINGS,
        reviewed_at="2026-07-30T10:00:00+00:00",
    )
    record.update(overrides)
    return record


def read_manifest(root: Path) -> dict:
    path = root / "editions" / "issue-001" / "edition.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_manifest(root: Path, manifest: dict) -> None:
    path = root / "editions" / "issue-001" / "edition.yaml"
    path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def add_explainer(
    root: Path,
    article_id: str = "mcp-in-a-nutshell",
    *,
    title: str = "MCP in a Nutshell",
    source_id: str = "source-two",
    content_mode: str = "in_a_nutshell",
) -> None:
    """Give make_project's edition an in-a-nutshell piece on its own source.

    ``content_mode`` is the explainer marker the manifest carries, so it is
    what the piece is declared with; the parameter exists so a test can add an
    article that is *not* an explainer through the same helper.
    """
    add_source(root, source_id, body="Explainer source body.\n")
    edition_dir = root / "editions" / "issue-001"
    (edition_dir / "articles" / f"{article_id}.md").write_text(
        "The explainer, as first written.", encoding="utf-8"
    )
    manifest = read_manifest(root)
    manifest["articles"].append(
        {
            "id": article_id,
            "title": title,
            "short_title": title,
            "opener_variant": "edge_medallion",
            "author": "Author",
            "author_note": "Author is chief architect at Example Company.",
            "content_mode": content_mode,
            "source_ids": [source_id],
            "manuscript": f"editions/issue-001/articles/{article_id}.md",
        }
    )
    write_manifest(root, manifest)


class LearningRecordTests(unittest.TestCase):
    """The record itself, as a pure function of bindings and a judge's YAML."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "reviews" / "learning.yaml"

    def test_record_roundtrip_binds_furniture_and_explainer(self):
        path = write_learning_review(self.path, make_record())

        loaded = load_learning_review(path, edition_id="issue-001")
        status = learning_review_status(loaded, edition_id="issue-001", bindings=BINDINGS)

        self.assertEqual(LEARNING_REVIEW_SCHEMA_VERSION, 1)
        self.assertEqual(loaded["schema_version"], 1)
        self.assertEqual(loaded["furniture_sha256"], "1" * 64)
        self.assertEqual(loaded["explainers"], BINDINGS["explainers"])
        self.assertEqual(status["status"], "approved")
        self.assertEqual(status["reviewer"], "Reader panel")
        self.assertEqual(status["drift"], [])

    def test_review_path_lives_beside_the_other_review_records(self):
        self.assertEqual(
            learning_review_path(self.root / "editions", "issue-001"),
            self.root / "editions" / "issue-001" / "reviews" / "learning.yaml",
        )

    def test_changes_required_record_needs_a_finding(self):
        with self.assertRaisesRegex(ValidationError, "needs at least one finding"):
            create_learning_review(
                edition_id="issue-001",
                reviewer="Reader panel",
                result="changes_required",
                bindings=BINDINGS,
            )

    def test_structured_finding_survives_write_and_load_as_a_mapping(self):
        record = create_learning_review(
            edition_id="issue-001",
            reviewer="Reader panel",
            result="changes_required",
            bindings=BINDINGS,
            findings=[FINDING],
            reviewed_at="2026-07-30T10:00:00+00:00",
        )
        path = write_learning_review(self.path, record)

        loaded = load_learning_review(path, edition_id="issue-001")

        finding = loaded["findings"][0]
        self.assertIsInstance(finding, dict)
        self.assertEqual(finding, FINDING)
        # Known keys in the shared helper's fixed order, so records diff cleanly.
        self.assertEqual(
            list(finding),
            ["severity", "article", "locator", "category", "persona", "note"],
        )
        self.assertEqual(
            learning_review_status(loaded, edition_id="issue-001", bindings=BINDINGS)[
                "findings"
            ],
            [FINDING],
        )

    def test_a_structured_finding_must_name_a_known_persona(self):
        without_persona = {"severity": "major", "note": "The glossary omits sampling."}
        with self.assertRaisesRegex(ValidationError, "requires a non-empty persona"):
            create_learning_review(
                edition_id="issue-001",
                reviewer="Reader panel",
                result="changes_required",
                bindings=BINDINGS,
                findings=[without_persona],
            )

        with self.assertRaisesRegex(ValidationError, "persona must be nadia, marcus, priya"):
            create_learning_review(
                edition_id="issue-001",
                reviewer="Reader panel",
                result="changes_required",
                bindings=BINDINGS,
                findings=[{**without_persona, "persona": "nadya"}],
            )

    def test_a_plain_string_finding_is_still_accepted(self):
        """``--finding "..."`` is how a human files one, and every record written
        before structured findings existed is full of them."""
        record = create_learning_review(
            edition_id="issue-001",
            reviewer="Reader panel",
            result="changes_required",
            bindings=BINDINGS,
            findings=["The cheat sheet contradicts the deck."],
            reviewed_at="2026-07-30T10:00:00+00:00",
        )
        path = write_learning_review(self.path, record)

        loaded = load_learning_review(path, edition_id="issue-001")

        self.assertEqual(loaded["findings"], ["The cheat sheet contradicts the deck."])

    def test_load_refuses_a_finding_the_file_carries_without_a_persona(self):
        record = make_record(
            result="changes_required",
            findings=[{"severity": "major", "note": "The glossary omits sampling."}],
        )
        path = write_learning_review(self.path, record)

        with self.assertRaisesRegex(ValidationError, "requires a non-empty persona"):
            load_learning_review(path, edition_id="issue-001")

    def test_persona_blocks_survive_write_and_load_unchanged(self):
        record = create_learning_review(
            edition_id="issue-001",
            reviewer="Reader panel",
            result="approved",
            bindings=BINDINGS,
            comprehension=COMPREHENSION,
            manager_takeaways=MANAGER_TAKEAWAYS,
            reviewed_at="2026-07-30T10:00:00+00:00",
        )
        path = write_learning_review(self.path, record)

        loaded = load_learning_review(path, edition_id="issue-001")

        self.assertEqual(loaded["comprehension"], COMPREHENSION)
        self.assertEqual(loaded["manager_takeaways"], MANAGER_TAKEAWAYS)
        # The failed question's null answer is the record of the failure and has
        # to come back as a null, not as an empty string.
        self.assertIsNone(loaded["comprehension"][0]["questions"][1]["answer"])
        self.assertIsNone(loaded["comprehension"][0]["questions"][1]["cite"])
        status = learning_review_status(loaded, edition_id="issue-001", bindings=BINDINGS)
        self.assertEqual(status["comprehension"], COMPREHENSION)
        self.assertEqual(status["manager_takeaways"], MANAGER_TAKEAWAYS)

    def test_a_short_comprehension_run_is_stored_rather_than_refused(self):
        """Counts are not enforced: losing a whole record -- findings included --
        over a five-question run would cost more than the shortfall does."""
        short = [{**COMPREHENSION[0], "correct": 1, "of": 2}]

        record = create_learning_review(
            edition_id="issue-001",
            reviewer="Reader panel",
            result="approved",
            bindings=BINDINGS,
            comprehension=short,
        )

        self.assertEqual(record["comprehension"], short)

    def test_comprehension_structural_refusals(self):
        cases = {
            "persona must be": [{**COMPREHENSION[0], "persona": "nadya"}],
            "requires a language": [{**COMPREHENSION[0], "language": " "}],
            "correct must be between 0 and of": [{**COMPREHENSION[0], "correct": 9}],
            "correct must be an integer": [{**COMPREHENSION[0], "correct": "five"}],
            "question 1 correct must be true or false": [
                {
                    **COMPREHENSION[0],
                    "questions": [
                        {**COMPREHENSION[0]["questions"][0], "correct": "yes"}
                    ],
                }
            ],
            "question 1 requires a question": [
                {
                    **COMPREHENSION[0],
                    "questions": [{**COMPREHENSION[0]["questions"][0], "question": ""}],
                }
            ],
        }
        for message, comprehension in cases.items():
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValidationError, message):
                    create_learning_review(
                        edition_id="issue-001",
                        reviewer="Reader panel",
                        result="approved",
                        bindings=BINDINGS,
                        comprehension=comprehension,
                    )

    def test_manager_takeaway_structural_refusals(self):
        cases = {
            "requires a non-empty decision": [
                {**MANAGER_TAKEAWAYS[0], "decision": "  "}
            ],
            "requires a non-empty article": [{**MANAGER_TAKEAWAYS[0], "article": ""}],
            "claims must be non-empty strings": [
                {**MANAGER_TAKEAWAYS[0], "claims": ["A claim.", ""]}
            ],
            "verdict must be supported, unsupported, contradicted": [
                {
                    **MANAGER_TAKEAWAYS[0],
                    "adjudication": [{"item": "decision", "verdict": "probably"}],
                }
            ],
            "adjudication 1 requires an item": [
                {
                    **MANAGER_TAKEAWAYS[0],
                    "adjudication": [{"item": "", "verdict": "supported"}],
                }
            ],
        }
        for message, takeaways in cases.items():
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValidationError, message):
                    create_learning_review(
                        edition_id="issue-001",
                        reviewer="Reader panel",
                        result="approved",
                        bindings=BINDINGS,
                        manager_takeaways=takeaways,
                    )

    def test_record_level_scores_roundtrip_and_reach_the_status(self):
        record = create_learning_review(
            edition_id="issue-001",
            reviewer="Reader panel",
            result="approved",
            bindings=BINDINGS,
            scores=SCORES,
            reviewed_at="2026-07-30T10:00:00+00:00",
        )
        path = write_learning_review(self.path, record)

        loaded = load_learning_review(path, edition_id="issue-001")
        status = learning_review_status(loaded, edition_id="issue-001", bindings=BINDINGS)

        self.assertEqual(loaded["scores"], SCORES)
        self.assertEqual(status["scores"], SCORES)

    def test_scores_outside_the_prompt_range_are_refused(self):
        for scores in ({"comprehension": 6}, {"comprehension": "4"}, {"comprehension": True}):
            with self.subTest(scores=scores):
                with self.assertRaisesRegex(ValidationError, "must be an integer 1-5"):
                    create_learning_review(
                        edition_id="issue-001",
                        reviewer="Reader panel",
                        result="approved",
                        bindings=BINDINGS,
                        scores=scores,
                    )

    def test_changing_a_score_never_makes_the_record_stale(self):
        """Scores are advisory by construction.  If a re-scored record went
        stale, a judge who revised a 3 to a 4 would have invalidated an approval
        over a number nothing is allowed to gate on."""
        record = make_record(scores=SCORES)
        self.assertEqual(
            learning_review_status(record, edition_id="issue-001", bindings=BINDINGS)[
                "status"
            ],
            "approved",
        )

        record["scores"] = {"comprehension": 1, "standalone_sufficiency": 1}
        status = learning_review_status(record, edition_id="issue-001", bindings=BINDINGS)

        self.assertEqual(status["status"], "approved")
        self.assertEqual(status["drift"], [])

    def test_drift_names_furniture_first_then_sorted_explainers(self):
        record = make_record()
        current = {
            "furniture_sha256": "f" * 64,
            "explainers": {
                # The recorded explainer moved, and a second one appeared.
                "mcp-in-a-nutshell": {"manuscript_sha256": "e" * 64},
                "evals-in-a-nutshell": {"manuscript_sha256": "d" * 64},
            },
        }

        self.assertEqual(
            learning_drift(record, current),
            ["furniture", "explainer:evals-in-a-nutshell", "explainer:mcp-in-a-nutshell"],
        )
        # A vanished explainer is drift too: the verdict covered a piece the
        # edition no longer carries.
        self.assertEqual(
            learning_drift(record, {"furniture_sha256": "1" * 64, "explainers": {}}),
            ["explainer:mcp-in-a-nutshell"],
        )

    def test_gate_refuses_missing_stale_and_changes_required_records(self):
        with self.assertRaisesRegex(ValidationError, "required_before_release"):
            require_approved_learning_review(
                None, edition_id="issue-001", bindings=BINDINGS
            )

        stale = {**BINDINGS, "furniture_sha256": "f" * 64}
        with self.assertRaisesRegex(ValidationError, "stale.*furniture"):
            require_approved_learning_review(
                make_record(), edition_id="issue-001", bindings=stale
            )

        rejected = make_record(
            result="changes_required", findings=[FINDING]
        )
        with self.assertRaisesRegex(ValidationError, "changes_required"):
            require_approved_learning_review(
                rejected, edition_id="issue-001", bindings=BINDINGS
            )

        # An approved record against unchanged bindings passes silently.
        require_approved_learning_review(
            make_record(), edition_id="issue-001", bindings=BINDINGS
        )

    def test_load_rejects_an_unsupported_schema_version(self):
        path = write_learning_review(self.path, make_record(schema_version=2))

        with self.assertRaisesRegex(ValidationError, "schema_version must be 1"):
            load_learning_review(path, edition_id="issue-001")

    def test_load_degrades_on_a_corrupt_record_naming_the_file(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("result: [unclosed", encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "learning.yaml"):
            load_learning_review(self.path, edition_id="issue-001")

    def test_load_rejects_a_broken_furniture_or_explainer_binding(self):
        path = write_learning_review(self.path, make_record(furniture_sha256="nope"))
        with self.assertRaisesRegex(ValidationError, "invalid furniture_sha256"):
            load_learning_review(path, edition_id="issue-001")

        path = write_learning_review(
            self.path,
            make_record(explainers={"mcp-in-a-nutshell": {"manuscript_sha256": "nope"}}),
        )
        with self.assertRaisesRegex(ValidationError, "invalid manuscript_sha256"):
            load_learning_review(path, edition_id="issue-001")

    def test_creating_a_record_requires_the_furniture_binding(self):
        with self.assertRaisesRegex(ValidationError, "missing furniture_sha256"):
            create_learning_review(
                edition_id="issue-001",
                reviewer="Reader panel",
                result="approved",
                bindings={"explainers": {}},
            )


class FurnitureBindingTests(unittest.TestCase):
    """The binding, against a real project on disk."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_project(self.root)
        add_explainer(self.root)
        self.path = learning_review_path(self.root / "editions", "issue-001")

    def bindings(self) -> dict:
        return current_learning_bindings(load_edition_with_records(self.root))

    def record(self, bindings: dict) -> dict:
        path = write_learning_review(
            self.path,
            create_learning_review(
                edition_id="issue-001",
                reviewer="Reader panel",
                result="approved",
                bindings=bindings,
                reviewed_at="2026-07-30T10:00:00+00:00",
            ),
        )
        return load_learning_review(path, edition_id="issue-001")

    def status(self, review: dict) -> dict:
        return learning_review_status(
            review, edition_id="issue-001", bindings=self.bindings()
        )

    def test_a_feature_body_edit_does_not_stale_the_verdict_but_furniture_does(self):
        """The load-bearing contract of this whole module.

        Nadia read the explainer, Marcus read the furniture with the body
        withheld, Priya read the furniture against the source.  None of them
        read the feature's third paragraph, so editing it must leave their
        verdict standing -- otherwise every typo fix in an unrelated piece
        re-opens a review nobody's inputs changed, and the bench learns to
        ignore staleness.  Editing a string they *did* read -- the cover
        headline -- must stale it immediately, and say so as ``furniture``.
        """

        original = self.bindings()
        review = self.record(original)
        self.assertEqual(self.status(review)["status"], "approved")

        manuscript = self.root / "editions" / "issue-001" / "articles" / "article.md"
        manuscript.write_text(
            manuscript.read_text(encoding="utf-8") + "\n\nA paragraph added later.\n",
            encoding="utf-8",
        )

        self.assertEqual(self.bindings(), original)
        status = self.status(review)
        self.assertEqual(status["status"], "approved")
        self.assertEqual(status["drift"], [])

        manifest = read_manifest(self.root)
        manifest["cover"]["headline"] = "Issue, retitled after approval"
        write_manifest(self.root, manifest)

        self.assertNotEqual(
            self.bindings()["furniture_sha256"], original["furniture_sha256"]
        )
        status = self.status(review)
        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["drift"], ["furniture"])

    def test_the_key_ideas_box_binds_line_by_line(self):
        """The key-ideas box is Marcus's entire run-A input and the box Nadia
        answers from, so it is the furniture the personas read hardest.  Adding
        it, rewriting a line, and reordering the lines must each move the hash;
        and an article that never declared a box must hash as it always did."""

        no_box = self.bindings()["furniture_sha256"]

        manifest = read_manifest(self.root)
        manifest["articles"][0]["key_ideas"] = [
            "The boundary is the protocol, not the model.",
            "One client per server, always.",
        ]
        write_manifest(self.root, manifest)
        original = self.bindings()
        self.assertNotEqual(original["furniture_sha256"], no_box)

        review = self.record(original)
        self.assertEqual(self.status(review)["status"], "approved")

        manifest["articles"][0]["key_ideas"][1] = "One client per server, mostly."
        write_manifest(self.root, manifest)
        self.assertEqual(self.status(review)["drift"], ["furniture"])

        # Reordering says something different to a reader who reads top to
        # bottom, so the line order is part of what is bound.
        manifest["articles"][0]["key_ideas"] = [
            "One client per server, always.",
            "The boundary is the protocol, not the model.",
        ]
        write_manifest(self.root, manifest)
        self.assertNotEqual(
            self.bindings()["furniture_sha256"], original["furniture_sha256"]
        )

    def test_an_author_note_rewrite_is_furniture_drift(self):
        original = self.bindings()
        review = self.record(original)

        manifest = read_manifest(self.root)
        manifest["articles"][0]["author_note"] = "Author is a staff engineer."
        write_manifest(self.root, manifest)

        self.assertEqual(self.status(review)["drift"], ["furniture"])

    def test_a_diagram_caption_rewrite_is_furniture_drift(self):
        """The editors' figure captions are furniture the prompt names outright,
        so a rewritten caption has to move the hash."""
        add_curated_figure(self.root)
        original = self.bindings()
        review = self.record(original)
        self.assertEqual(self.status(review)["status"], "approved")

        manifest = read_manifest(self.root)
        manifest["articles"][0]["figures"][0]["caption"] = "A rewritten caption."
        write_manifest(self.root, manifest)

        self.assertEqual(self.status(review)["drift"], ["furniture"])

    def test_manifest_fields_the_readers_never_saw_leave_the_hash_alone(self):
        """Why the whole ``edition.yaml`` is not hashed: re-pinning a source or
        changing a content mode moves manifest bytes but moves nothing any
        persona read."""
        original = self.bindings()
        review = self.record(original)

        manifest = read_manifest(self.root)
        manifest["articles"][0]["source_body_sha256"] = "a" * 64
        manifest["articles"][0]["content_mode"] = "faithful_synthesis"
        manifest["articles"][0]["minimum_reader_pages"] = 2
        write_manifest(self.root, manifest)

        self.assertEqual(self.bindings(), original)
        self.assertEqual(self.status(review)["status"], "approved")

    def test_a_field_added_and_removed_hashes_back_to_where_it_started(self):
        """Absent keys are absent from the projection rather than defaulted to
        ``""``: a subtitle that appears and is then deleted must leave the
        verdict exactly as it found it."""
        original = furniture_sha256(load_edition_with_records(self.root))

        manifest = read_manifest(self.root)
        manifest["subtitle"] = "A subtitle, briefly"
        write_manifest(self.root, manifest)
        self.assertNotEqual(furniture_sha256(load_edition_with_records(self.root)), original)

        manifest = read_manifest(self.root)
        del manifest["subtitle"]
        write_manifest(self.root, manifest)

        self.assertEqual(furniture_sha256(load_edition_with_records(self.root)), original)

    def test_the_explainer_manuscript_moving_is_named_drift(self):
        original = self.bindings()
        review = self.record(original)

        explainer = (
            self.root / "editions" / "issue-001" / "articles" / "mcp-in-a-nutshell.md"
        )
        explainer.write_text("The explainer, rewritten.", encoding="utf-8")

        status = self.status(review)
        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["drift"], ["explainer:mcp-in-a-nutshell"])

    def test_the_projection_lists_exactly_the_editor_authored_strings(self):
        projection = furniture_projection(load_edition_with_records(self.root))

        self.assertEqual(projection["cover"], {"headline": "Issue"})
        self.assertEqual(set(projection), {"title", "cover", "articles", "closing_plates"})
        self.assertEqual(
            set(projection["articles"]), {"article", "mcp-in-a-nutshell"}
        )
        self.assertEqual(
            projection["articles"]["article"],
            {
                "title": "Article",
                "short_title": "Article",
                "author_note": "Author is chief architect at Example Company.",
                "figures": [],
            },
        )
        self.assertEqual(
            projection["closing_plates"], ["Coda 1", "Coda 2", "Coda 3"]
        )


class ExplainerDetectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_project(self.root)

    def test_the_content_mode_is_a_registered_manifest_mode(self):
        """The marker is named as a string here rather than imported, so this is
        what keeps it from drifting away from the manifest's vocabulary."""
        self.assertEqual(EXPLAINER_CONTENT_MODE, "in_a_nutshell")
        self.assertIn(EXPLAINER_CONTENT_MODE, CONTENT_MODES)

    def test_the_declared_content_mode_finds_the_explainer(self):
        add_explainer(self.root)

        edition = load_edition_with_records(self.root)

        self.assertEqual(explainer_article_ids(edition), ("mcp-in-a-nutshell",))
        self.assertEqual(
            set(current_learning_bindings(edition)["explainers"]),
            {"mcp-in-a-nutshell"},
        )

    def test_an_explainer_named_for_its_subject_is_found(self):
        """The id heuristic this replaced saw only pieces named after the
        section.  An explainer titled for what it explains is the ordinary case
        and it must bind, or the verdict silently covers less than it claims."""
        add_explainer(
            self.root, "understanding-webhooks", title="Understanding Webhooks"
        )

        edition = load_edition_with_records(self.root)

        self.assertEqual(explainer_article_ids(edition), ("understanding-webhooks",))
        bindings = current_learning_bindings(edition)
        self.assertEqual(set(bindings["explainers"]), {"understanding-webhooks"})
        self.assertRegex(
            bindings["explainers"]["understanding-webhooks"]["manuscript_sha256"],
            r"^[0-9a-f]{64}$",
        )

    def test_an_in_a_nutshell_id_without_the_mode_is_not_an_explainer(self):
        """The other half of the same rule: the id says nothing, the
        declaration says everything."""
        add_explainer(
            self.root,
            "mcp-in-a-nutshell",
            title="MCP in a Nutshell",
            content_mode="faithful_synthesis",
        )

        edition = load_edition_with_records(self.root)

        self.assertEqual(explainer_article_ids(edition), ())

    def test_an_edition_with_no_explainer_still_binds_its_furniture(self):
        """An ordinary state, not a failure: the personas still have furniture."""
        edition = load_edition_with_records(self.root)

        self.assertEqual(explainer_article_ids(edition), ())
        bindings = current_learning_bindings(edition)
        self.assertEqual(bindings["explainers"], {})
        self.assertEqual(len(bindings["furniture_sha256"]), 64)

        path = write_learning_review(
            learning_review_path(self.root / "editions", "issue-001"),
            create_learning_review(
                edition_id="issue-001",
                reviewer="Reader panel",
                result="approved",
                bindings=bindings,
            ),
        )
        loaded = load_learning_review(path, edition_id="issue-001")
        status = learning_review_status(
            loaded, edition_id="issue-001", bindings=bindings
        )

        self.assertEqual(loaded["explainers"], {})
        self.assertEqual(status["status"], "approved")

    def test_an_explicit_override_wins_over_detection(self):
        add_explainer(self.root)
        edition = load_edition_with_records(self.root)

        bindings = current_learning_bindings(edition, explainer_ids=["article"])

        self.assertEqual(set(bindings["explainers"]), {"article"})

    def test_an_override_refuses_an_article_the_edition_does_not_carry(self):
        edition = load_edition_with_records(self.root)

        with self.assertRaisesRegex(ValidationError, "does not carry: ghost"):
            current_learning_bindings(edition, explainer_ids=["ghost"])

    def test_the_personas_are_the_three_the_prompt_names(self):
        self.assertEqual(LEARNING_PERSONAS, ("nadia", "marcus", "priya"))


if __name__ == "__main__":
    unittest.main()
