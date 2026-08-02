"""The shared per-piece record spine, tested once instead of six times.

``prompts/README.md`` split one broad judge into six per-piece lenses plus
``edition``.  Every one of the six stores the same document -- a verdict, a list
of findings, an advisory score row per piece, and the SHA-256 of the exact bytes
the lens read -- so :mod:`magazine.piece_review` holds the shape and each kind
module is a declaration.  That is the reason this file exists: the properties
below are properties of the spine, and asserting them once against every
declared kind is what stops a seventh lens shipping with a sixth of the
behaviour.

Three things are tested harder than the rest, because each one is a defect the
old bench actually shipped.

**``disposition`` is required to write and optional to read.**  It is the field
that replaced the severity cap, and a parser that drops it reintroduces the bug
the cap caused -- a round-3 line review that approved a piece with twelve
lowercase sentence openings in it, on the grounds that everything remaining was
uncapped-able.  So an authored finding without one is refused at the write,
where the reviewer can still supply it, and a finding committed before the field
existed still loads, because re-auditing a shipped edition to add a key nobody
can now honestly supply is a worse answer than reading the old record for the
part of it that is still true.  A *misspelled* one is refused on both paths:
absent is visibly unrouted, but ``editor-decision`` would be silently read as
"not an editor decision" and quietly counted clean.

**An ``editor_decision`` finding blocks the release on its own.**  Never
dropped, never softened, never counted as clean.  It is compatible with any
verdict the lens likes, so an approving record with one outstanding is exactly
the combination the field exists for, and the gate refuses it separately from
and in addition to the approved/stale question.

**A lens binds what it reads and nothing else.**  Source-blindness is per lens,
so a source-blind kind's record has no ``source_extractions`` key at all --
storing one would send a reader who was forbidden the source back to re-read a
piece whose prose did not move.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from magazine import Magazine, ValidationError
from magazine.piece_review import (
    EDITORIAL_ARTICLE_ID,
    covered_piece_ids,
    create_review,
    current_bindings,
    load_review,
    rebind_articles,
    require_approved,
    review_path,
    review_status,
    write_review,
)
from magazine.review_bench import PIECE_REVIEW_KINDS, current_bindings_for
from magazine.teaching_review import furniture_sha256

from test_manifest import (
    add_extraction,
    add_source,
    load_edition_with_records,
    make_project,
    pin_article_source_hash,
    set_open_edition,
)


# The kinds by the axis each group of tests is about, written out rather than
# derived from the specs: a lens that silently changed what it covers or what it
# binds would otherwise re-derive the expectation and pass.
SOURCE_BLIND_KINDS = ("shape", "craft", "mechanics")
SOURCE_READING_KINDS = ("worth", "evidence", "teaching")
PIECE_COVERING_KINDS = ("shape", "craft", "mechanics")
ARTICLE_ONLY_KINDS = ("worth", "evidence")

FIX_FINDING = {
    "severity": "minor",
    "article": "article",
    "locator": "- | The original article. | 1",
    "category": "dead_words",
    "disposition": "fix",
    "note": "Three qualifiers in one clause.",
}

EDITOR_DECISION_FINDING = {
    "severity": "major",
    "article": "article",
    "locator": "Where the problem lives | factories is not a token | 1",
    "category": "agreement",
    "disposition": "editor_decision",
    "note": "The source author's own retained sentence disagrees with its subject.",
}


def synthetic_bindings(kind: str, *piece_ids: str) -> dict[str, dict]:
    """One plausible binding row per piece, shaped by what the kind declares.

    The hashes are invented: everything the spine does with a binding is compare
    it, so a fixture that hashed real files would only be testing ``sha256``.
    """

    spec = PIECE_REVIEW_KINDS[kind]
    bindings: dict[str, dict] = {}
    for index, piece_id in enumerate(piece_ids, start=1):
        row: dict = {"manuscript_sha256": str(index) * 64}
        if spec.binds_extractions:
            row["source_extractions"] = {
                "source-one": {"body_sha256": "a" * 64, "file_sha256": "b" * 64}
            }
        if spec.binds_furniture:
            row["furniture_sha256"] = "c" * 64
        bindings[piece_id] = row
    return bindings


def make_record(kind: str, *, findings=(), result: str = "approved", **overrides):
    """One valid record of the given kind, bound to one piece called ``article``."""

    record = create_review(
        PIECE_REVIEW_KINDS[kind],
        edition_id="issue-001",
        reviewer="A reader",
        result=result,
        bindings=synthetic_bindings(kind, "article"),
        findings=findings,
        reviewed_at="2026-08-01T10:00:00+00:00",
    )
    record.update(overrides)
    return record


def add_explainer(root: Path, *, key_ideas=("The host decides when.",)) -> str:
    """Give make_project's edition an ``in_a_nutshell`` piece to teach from.

    Detection is by declaration, so what makes this the explainer is the
    ``content_mode`` on its row and nothing about its id.
    """

    article_id = "mcp-in-a-nutshell"
    body = "A specification.\n"
    add_source(root, "source-two", body=body)
    edition_dir = root / "editions" / "issue-001"
    (edition_dir / "articles" / f"{article_id}.md").write_text(
        body.strip(), encoding="utf-8"
    )
    manifest_path = edition_dir / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["articles"].append(
        {
            "id": article_id,
            "title": "MCP in a Nutshell",
            "short_title": "MCP in a Nutshell",
            "opener_variant": "split_axis",
            # The Teacher writes in the magazine's voice, so the byline is the
            # editors' and there is no author biography to carry.
            "author": "The editors",
            "content_mode": "in_a_nutshell",
            "source_ids": ["source-two"],
            "manuscript": f"editions/issue-001/articles/{article_id}.md",
            "key_ideas": list(key_ideas),
        }
    )
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    pin_article_source_hash(
        root,
        add_extraction(root, source_id="source-two", body=body),
        article=article_id,
    )
    return article_id


def set_key_ideas(root: Path, article_id: str, key_ideas) -> None:
    """Rewrite one article's key-ideas box, which is bound furniture."""

    manifest_path = root / "editions" / "issue-001" / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    row = next(row for row in manifest["articles"] if row["id"] == article_id)
    row["key_ideas"] = list(key_ideas)
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )


class DispositionWriteAndReadTests(unittest.TestCase):
    """The asymmetry: strict on the way in, lenient on the way out."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def path(self, kind: str) -> Path:
        return self.root / "reviews" / f"{kind}.yaml"

    def test_no_kind_may_author_a_structured_finding_without_a_disposition(self):
        """The write path is the last moment the field can still be supplied.

        Looped over every declared kind rather than asserted on one, because the
        rule is a property of the spine: a lens that could omit ``disposition``
        is a lens whose findings the composer cannot sort into "must fix" and
        "for the editor", which is the severity cap back under a new name.
        """

        unrouted = {
            key: value
            for key, value in FIX_FINDING.items()
            if key != "disposition"
        }
        for kind in PIECE_REVIEW_KINDS:
            with self.subTest(kind=kind), self.assertRaisesRegex(
                ValidationError, "finding 1 requires a non-empty disposition"
            ):
                create_review(
                    PIECE_REVIEW_KINDS[kind],
                    edition_id="issue-001",
                    reviewer="A reader",
                    result="changes_required",
                    bindings=synthetic_bindings(kind, "article"),
                    findings=[unrouted],
                )

    def test_a_committed_finding_without_a_disposition_still_loads(self):
        """The other half of the bargain, and the reason the halves differ.

        Every finding committed before the field existed would otherwise stop
        loading, and a shipped edition cannot be re-audited to add a key nobody
        can now honestly supply.  The finding comes back exactly as it was
        written -- unrouted and visibly so -- rather than defaulted to ``fix``,
        which would launder it into the writer's pile.
        """

        stored = {
            key: value
            for key, value in FIX_FINDING.items()
            if key != "disposition"
        }
        record = make_record("craft", result="changes_required", findings=[FIX_FINDING])
        record["findings"] = [stored]
        path = write_review(self.path("craft"), record)

        loaded = load_review(
            PIECE_REVIEW_KINDS["craft"], path, edition_id="issue-001"
        )

        self.assertEqual(loaded["findings"], [stored])
        self.assertNotIn("disposition", loaded["findings"][0])

    def test_a_committed_record_of_every_kind_loads_without_the_field(self):
        """The leniency belongs to the spine, not to the one kind that had a
        version 1 ledger: ``teaching`` and ``worth`` are new, but a record
        written between the bench landing and this field landing is still a
        record nobody can re-author."""

        stored = {
            key: value
            for key, value in FIX_FINDING.items()
            if key != "disposition"
        }
        for kind in PIECE_REVIEW_KINDS:
            record = make_record(
                kind, result="changes_required", findings=[FIX_FINDING]
            )
            record["findings"] = [stored]
            path = write_review(self.path(kind), record)

            loaded = load_review(
                PIECE_REVIEW_KINDS[kind], path, edition_id="issue-001"
            )

            self.assertEqual(loaded["findings"], [stored], kind)

    def test_a_misspelled_disposition_is_refused_when_authored(self):
        """Absent is unrouted and visible; misspelled is worse than either.

        ``editor-decision`` and ``maybe`` both compare unequal to
        ``editor_decision``, so a gate reading them would count a finding a
        human has to rule on as clean.  The value is checked, not merely the
        key's presence.
        """

        for bad in ("editor-decision", "Editor_Decision", "maybe", "fixed"):
            with self.subTest(disposition=bad), self.assertRaisesRegex(
                ValidationError, "disposition must be fix or editor_decision"
            ):
                create_review(
                    PIECE_REVIEW_KINDS["craft"],
                    edition_id="issue-001",
                    reviewer="A reader",
                    result="changes_required",
                    bindings=synthetic_bindings("craft", "article"),
                    findings=[{**FIX_FINDING, "disposition": bad}],
                )

    def test_a_misspelled_disposition_is_refused_when_read_back(self):
        """The read path is lenient about *absence* only.

        A hand-edited record whose finding says ``editor-decision`` must not
        load: leniency exists so that records written before the field can still
        be read, and a typo is not a record written before the field.
        """

        for bad in ("editor-decision", "maybe"):
            record = make_record(
                "craft", result="changes_required", findings=[FIX_FINDING]
            )
            record["findings"] = [{**FIX_FINDING, "disposition": bad}]
            path = write_review(self.path("craft"), record)

            with self.subTest(disposition=bad), self.assertRaisesRegex(
                ValidationError, "disposition must be fix or editor_decision"
            ):
                load_review(
                    PIECE_REVIEW_KINDS["craft"], path, edition_id="issue-001"
                )

    def test_a_sentence_a_human_typed_is_exempt_from_all_of_it(self):
        """``--finding "..."`` is still how a human files one, and a human
        filing a sentence is not filing against a locator.  Every record written
        before structured findings existed is full of them."""

        record = create_review(
            PIECE_REVIEW_KINDS["craft"],
            edition_id="issue-001",
            reviewer="A reader",
            result="changes_required",
            bindings=synthetic_bindings("craft", "article"),
            findings=["  Unlogged omission in the second section.  "],
            reviewed_at="2026-08-01T10:00:00+00:00",
        )
        path = write_review(self.path("craft"), record)

        loaded = load_review(
            PIECE_REVIEW_KINDS["craft"], path, edition_id="issue-001"
        )

        self.assertEqual(
            loaded["findings"], ["Unlogged omission in the second section."]
        )


class EditorDecisionGateTests(unittest.TestCase):
    """Never dropped, never softened, never counted as clean."""

    def test_an_outstanding_ruling_blocks_an_approved_and_current_record(self):
        """The whole point of the redesign, in one assertion.

        The lens approved the piece and nothing has drifted, and the release is
        still refused: an ``editor_decision`` finding says a real defect exists
        that the lens was forbidden to route to the writer, so the verdict says
        nothing at all about whether anybody has dealt with it.  A gate that
        read the verdict alone would let an approval launder the one thing the
        field exists to keep visible.
        """

        bindings = synthetic_bindings("craft", "article")
        record = make_record(
            "craft", result="approved", findings=[EDITOR_DECISION_FINDING]
        )

        status = review_status(
            PIECE_REVIEW_KINDS["craft"],
            record,
            edition_id="issue-001",
            bindings=bindings,
        )
        self.assertEqual(status["status"], "approved")
        self.assertEqual(status["editor_decisions"], 1)

        with self.assertRaises(ValidationError) as caught:
            require_approved(
                PIECE_REVIEW_KINDS["craft"],
                record,
                edition_id="issue-001",
                bindings=bindings,
            )

        message = "\n".join(caught.exception.errors)
        self.assertIn("waiting on a human ruling", message)
        # Named, not counted: an operator who cannot see which finding it is
        # cannot rule on it, and would clear the gate by re-recording.
        self.assertIn("article: [major] agreement at Where the problem lives", message)

    def test_the_ruling_refusal_is_separate_from_and_added_to_the_stale_one(self):
        """Two different facts, so two refusals.

        A stale record and an unresolved ruling are independent problems, and
        folding them into one line would let the operator fix the staleness,
        re-record, and never learn about the ruling.
        """

        record = make_record(
            "craft", result="approved", findings=[EDITOR_DECISION_FINDING]
        )
        drifted = {"article": {"manuscript_sha256": "f" * 64}}

        with self.assertRaises(ValidationError) as caught:
            require_approved(
                PIECE_REVIEW_KINDS["craft"],
                record,
                edition_id="issue-001",
                bindings=drifted,
            )

        errors = caught.exception.errors
        self.assertTrue(any("craft reading is stale" in error for error in errors))
        self.assertTrue(any("waiting on a human ruling" in error for error in errors))

    def test_every_outstanding_ruling_is_named_not_just_the_first(self):
        second = {
            **EDITOR_DECISION_FINDING,
            "article": "editorial",
            "category": "register",
            "locator": "- | It is what it is. | 1",
        }
        bindings = synthetic_bindings("craft", "article")
        record = make_record(
            "craft",
            result="approved",
            findings=[EDITOR_DECISION_FINDING, FIX_FINDING, second],
        )

        with self.assertRaises(ValidationError) as caught:
            require_approved(
                PIECE_REVIEW_KINDS["craft"],
                record,
                edition_id="issue-001",
                bindings=bindings,
            )

        message = "\n".join(caught.exception.errors)
        self.assertIn("2 craft finding(s)", message)
        self.assertIn("article: [major] agreement", message)
        self.assertIn("editorial: [major] register", message)

    def test_a_finding_routed_to_the_writer_does_not_block_the_release(self):
        """The complement, so the gate is not simply "any finding blocks".

        A ``fix`` finding on an approved record is the ordinary residue of a
        round the writer already answered; only a ruling nobody has made stops
        the issue.
        """

        bindings = synthetic_bindings("craft", "article")
        record = make_record("craft", result="approved", findings=[FIX_FINDING])

        require_approved(
            PIECE_REVIEW_KINDS["craft"],
            record,
            edition_id="issue-001",
            bindings=bindings,
        )

    def test_every_kind_enforces_the_ruling_the_same_way(self):
        """The gate is on the spine, so no lens can be the one that lets one
        through -- including ``mechanics``, which ``prompts/README.md`` singles
        out as having no discount at all."""

        for kind in PIECE_REVIEW_KINDS:
            bindings = synthetic_bindings(kind, "article")
            record = make_record(
                kind, result="approved", findings=[EDITOR_DECISION_FINDING]
            )

            with self.subTest(kind=kind), self.assertRaisesRegex(
                ValidationError, "waiting on a human ruling"
            ):
                require_approved(
                    PIECE_REVIEW_KINDS[kind],
                    record,
                    edition_id="issue-001",
                    bindings=bindings,
                )


class CoverageTests(unittest.TestCase):
    """Which pieces each lens is asked about, against a real edition."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_project(self.root)
        pin_article_source_hash(self.root, add_extraction(self.root))
        self.explainer = add_explainer(self.root)
        self.edition = load_edition_with_records(self.root)

    def test_worth_and_evidence_do_not_cover_the_editorial(self):
        """The editorial has no source of its own.

        ``worth``'s question is a comparison against a source, and the
        editorial's version of it -- does it say something no single article
        says -- is ``edition``'s ``single_source_editorial``.  ``evidence`` is
        excluded because the editorial declares no ``source_ids`` and there is
        nothing to bind.  A lens asked about a piece it cannot judge would
        report an unrecorded row for ever, which reads as staleness no re-run
        can clear.
        """

        for kind in ARTICLE_ONLY_KINDS:
            covered = covered_piece_ids(PIECE_REVIEW_KINDS[kind], self.edition)
            self.assertEqual(covered, ("article", self.explainer), kind)
            self.assertNotIn(EDITORIAL_ARTICLE_ID, covered, kind)

    def test_shape_craft_and_mechanics_cover_the_editorial_too(self):
        """"Piece" means the articles plus the editorial, and everything these
        three ask is answerable from a manuscript -- which the editorial has."""

        for kind in PIECE_COVERING_KINDS:
            covered = covered_piece_ids(PIECE_REVIEW_KINDS[kind], self.edition)
            self.assertEqual(
                covered, ("article", self.explainer, EDITORIAL_ARTICLE_ID), kind
            )

    def test_teaching_covers_the_declared_explainer_alone(self):
        self.assertEqual(
            covered_piece_ids(PIECE_REVIEW_KINDS["teaching"], self.edition),
            (self.explainer,),
        )


class BindingShapeTests(unittest.TestCase):
    """A lens binds what it reads, and a record shows which lens wrote it."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_project(self.root)
        pin_article_source_hash(self.root, add_extraction(self.root))
        self.explainer = add_explainer(self.root)
        self.edition = load_edition_with_records(self.root)
        self.sources_dir = self.root / "library" / "sources"

    def test_a_source_blind_kind_has_no_source_extractions_key_at_all(self):
        """Not an empty mapping -- absent.

        ``prompts/mechanics-review.md`` and its two siblings forbid opening the
        source, and the record has to agree: a source hash stored here would
        assert that a source's bytes can invalidate a reading the reviewer was
        forbidden to base on them, and would send the lens back to re-read a
        piece whose prose did not move.  Passing the sources directory anyway,
        as ``current_bindings_for`` does for every kind alike, must not put one
        in.
        """

        for kind in SOURCE_BLIND_KINDS:
            bindings = current_bindings_for(kind, self.edition, self.sources_dir)
            for piece_id, row in bindings.items():
                self.assertEqual(set(row), {"manuscript_sha256"}, (kind, piece_id))

    def test_worth_and_evidence_bind_every_extraction_the_piece_declares(self):
        for kind in ARTICLE_ONLY_KINDS:
            bindings = current_bindings_for(kind, self.edition, self.sources_dir)
            self.assertEqual(
                set(bindings["article"]),
                {"manuscript_sha256", "source_extractions"},
                kind,
            )
            self.assertEqual(
                set(bindings["article"]["source_extractions"]), {"source-one"}, kind
            )
            self.assertEqual(
                set(bindings["article"]["source_extractions"]["source-one"]),
                {"body_sha256", "file_sha256"},
                kind,
            )

    def test_teaching_binds_the_furniture_projection_beside_the_rest(self):
        """Nadia reads the deck and the key-ideas box as hard as she reads the
        body, so the editor-authored furniture is bound too."""

        bindings = current_bindings_for("teaching", self.edition, self.sources_dir)

        self.assertEqual(set(bindings), {self.explainer})
        self.assertEqual(
            set(bindings[self.explainer]),
            {"manuscript_sha256", "source_extractions", "furniture_sha256"},
        )
        self.assertEqual(
            bindings[self.explainer]["furniture_sha256"],
            furniture_sha256(self.edition),
        )

    def test_a_record_is_written_where_the_bench_looks_for_it(self):
        for kind in PIECE_REVIEW_KINDS:
            self.assertEqual(
                review_path(self.root / "editions", "issue-001", kind),
                self.root / "editions" / "issue-001" / "reviews" / f"{kind}.yaml",
            )


class TeachingStalenessTests(unittest.TestCase):
    """What moves a teaching verdict, and what must not."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_project(self.root)
        pin_article_source_hash(self.root, add_extraction(self.root))
        self.explainer = add_explainer(self.root)
        set_open_edition(self.root, "issue-001")
        self.magazine = Magazine(self.root)
        self.magazine.record_teaching_review(
            "issue-001", reviewer="Nadia's panel", result="approved"
        )

    def test_rewriting_the_key_ideas_box_stales_the_reading(self):
        """The box is the furniture a first-time reader answers from, so
        rewriting it under an approved verdict must be visible.  Hashing
        ``edition.yaml`` whole was rejected for the opposite failure: re-pinning
        a source would spuriously stale a verdict about a glossary entry."""

        self.assertEqual(
            self.magazine.teaching_review_status("issue-001")["status"], "approved"
        )

        set_key_ideas(self.root, self.explainer, ["The host decides when, and how."])

        status = self.magazine.teaching_review_status("issue-001")
        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["articles"][self.explainer]["drift"], ["furniture"])

    def test_an_unrelated_articles_manuscript_does_not_stale_the_reading(self):
        """A lens re-runs only when its own declared inputs moved.  The
        explainer's reading does not depend on another piece's prose, and a
        record that staled on it would buy a re-run of the most expensive call
        on the bench for nothing."""

        manuscript = self.root / "editions" / "issue-001" / "articles" / "article.md"
        manuscript.write_text(
            manuscript.read_text(encoding="utf-8") + "\n\nA further paragraph.\n",
            encoding="utf-8",
        )

        status = self.magazine.teaching_review_status("issue-001")

        self.assertEqual(status["status"], "approved")
        self.assertEqual(status["articles"][self.explainer]["status"], "current")

    def test_the_explainers_own_manuscript_still_stales_it(self):
        manuscript = (
            self.root / "editions" / "issue-001" / "articles" / f"{self.explainer}.md"
        )
        manuscript.write_text(
            manuscript.read_text(encoding="utf-8") + "\n", encoding="utf-8"
        )

        status = self.magazine.teaching_review_status("issue-001")

        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["articles"][self.explainer]["drift"], ["manuscript"])


class TeachingWithoutAnExplainerTests(unittest.TestCase):
    """An edition with no explainer must not sit permanently red."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_project(self.root)
        pin_article_source_hash(self.root, add_extraction(self.root))
        set_open_edition(self.root, "issue-001")

    def test_teaching_reports_not_applicable_rather_than_required(self):
        """``required_before_release`` here would be a demand no run could
        satisfy: there is no piece to read, so no record can be written, so the
        checkpoint would sit red for ever and teach an operator to ignore it.
        The other five lenses do owe a record on the same edition, which is what
        makes ``not_applicable`` a statement about the edition rather than a way
        of switching a checkpoint off."""

        magazine = Magazine(self.root)

        self.assertEqual(
            magazine.teaching_review_status("issue-001")["status"], "not_applicable"
        )
        for kind in ("worth", "evidence", "shape", "craft", "mechanics"):
            self.assertEqual(
                magazine.piece_review_status(kind, "issue-001")["status"],
                "required_before_release",
                kind,
            )

    def test_the_gate_lets_an_edition_with_no_explainer_through(self):
        spec = PIECE_REVIEW_KINDS["teaching"]
        edition = load_edition_with_records(self.root)
        bindings = current_bindings_for(
            "teaching", edition, self.root / "library" / "sources"
        )

        self.assertEqual(bindings, {})
        require_approved(spec, None, edition_id="issue-001", bindings=bindings)

    def test_a_recorded_reading_still_gates_once_an_explainer_exists(self):
        """The escape hatch closes the moment there is something to read: an
        edition that gains an explainer owes a teaching record like any other
        piece owes its lens."""

        add_explainer(self.root)
        edition = load_edition_with_records(self.root)
        bindings = current_bindings_for(
            "teaching", edition, self.root / "library" / "sources"
        )

        with self.assertRaisesRegex(ValidationError, "required_before_release"):
            require_approved(
                PIECE_REVIEW_KINDS["teaching"],
                None,
                edition_id="issue-001",
                bindings=bindings,
            )


class PartialRebindTests(unittest.TestCase):
    """``--articles`` names what was re-read; everything else rides through."""

    def test_an_untouched_piece_keeps_its_binding_timestamp_and_scores(self):
        """Edition 003's evidence record was re-recorded three times in a day
        because one article moved.  A partial re-record must therefore carry the
        other pieces forward exactly as recorded -- binding, ``reviewed_at`` and
        advisory scores -- so that an untouched piece's reading survives and a
        drifted-but-unnamed piece stays visibly drifted rather than being
        silently re-blessed by a read that never happened.
        """

        spec = PIECE_REVIEW_KINDS["craft"]
        recorded = create_review(
            spec,
            edition_id="issue-001",
            reviewer="Craft reader",
            result="approved",
            bindings=synthetic_bindings("craft", "one", "two", EDITORIAL_ARTICLE_ID),
            scores={
                "one": {"register": 4},
                "two": {"register": 2, "economy": 3},
                EDITORIAL_ARTICLE_ID: {"register": 5},
            },
            reviewed_at="2026-08-01T10:00:00+00:00",
        )
        # "two" was revised and re-read; "one" and the editorial were not, and
        # "one" has drifted on disk without being named.
        current = synthetic_bindings("craft", "one", "two", EDITORIAL_ARTICLE_ID)
        current["one"]["manuscript_sha256"] = "f" * 64
        current["two"]["manuscript_sha256"] = "e" * 64

        merged = rebind_articles(
            spec, recorded, bindings=current, article_ids=["two"]
        )
        rewritten = create_review(
            spec,
            edition_id="issue-001",
            reviewer="Craft reader",
            result="approved",
            bindings=merged,
            reviewed_at="2026-08-02T09:00:00+00:00",
        )

        for piece_id in ("one", EDITORIAL_ARTICLE_ID):
            self.assertEqual(
                rewritten["articles"][piece_id],
                recorded["articles"][piece_id],
                piece_id,
            )
        self.assertEqual(
            rewritten["articles"]["two"],
            {
                "reviewed_at": "2026-08-02T09:00:00+00:00",
                "manuscript_sha256": "e" * 64,
            },
        )
        # The unnamed drifted piece is still drifted: preserving its binding is
        # what keeps the record honest rather than what hides the drift.
        status = review_status(
            spec, rewritten, edition_id="issue-001", bindings=current
        )
        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["articles"]["one"]["drift"], ["manuscript"])
        self.assertEqual(status["articles"]["two"]["status"], "current")

    def test_a_preserved_row_keeps_every_key_the_kind_binds(self):
        """The same rule for the widest binding on the bench: ``teaching``
        preserves the furniture hash and the extraction map, not only the
        manuscript, or a partial re-record would quietly narrow what an
        approved record claims to have covered."""

        spec = PIECE_REVIEW_KINDS["teaching"]
        recorded = create_review(
            spec,
            edition_id="issue-001",
            reviewer="Nadia's panel",
            result="approved",
            bindings=synthetic_bindings("teaching", "explainer", "second"),
            reviewed_at="2026-08-01T10:00:00+00:00",
        )
        current = synthetic_bindings("teaching", "explainer", "second")
        current["explainer"]["furniture_sha256"] = "d" * 64

        merged = rebind_articles(
            spec, recorded, bindings=current, article_ids=["second"]
        )

        self.assertEqual(merged["explainer"], recorded["articles"]["explainer"])
        self.assertEqual(merged["explainer"]["furniture_sha256"], "c" * 64)

    def test_a_partial_re_record_refuses_a_piece_it_can_neither_read_nor_preserve(self):
        spec = PIECE_REVIEW_KINDS["craft"]
        recorded = make_record("craft")

        with self.assertRaisesRegex(
            ValidationError, "no recorded reading to preserve: newcomer"
        ):
            rebind_articles(
                spec,
                recorded,
                bindings=synthetic_bindings("craft", "article", "newcomer"),
                article_ids=["article"],
            )


class ScoresNeverGateTests(unittest.TestCase):
    """A score that could stale a record would be a score that gates."""

    def test_rescoring_an_unchanged_piece_leaves_the_record_approved(self):
        spec = PIECE_REVIEW_KINDS["worth"]
        bindings = synthetic_bindings("worth", "article")
        record = create_review(
            spec,
            edition_id="issue-001",
            reviewer="A reader",
            result="approved",
            bindings=bindings,
            scores={"article": {"reader_gain": 1}},
            reviewed_at="2026-08-01T10:00:00+00:00",
        )

        status = review_status(spec, record, edition_id="issue-001", bindings=bindings)

        self.assertEqual(status["status"], "approved")
        self.assertEqual(status["articles"]["article"]["scores"], {"reader_gain": 1})
        require_approved(spec, record, edition_id="issue-001", bindings=bindings)


class UnrecordedPieceTests(unittest.TestCase):
    """A record that binds less than the edition carries is not approved."""

    def test_a_piece_the_record_never_bound_reads_as_drift(self):
        spec = PIECE_REVIEW_KINDS["mechanics"]
        record = make_record("mechanics")
        current = synthetic_bindings("mechanics", "article", "late-arrival")

        status = review_status(spec, record, edition_id="issue-001", bindings=current)

        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["articles"]["late-arrival"]["status"], "unrecorded")
        with self.assertRaisesRegex(ValidationError, "late-arrival"):
            require_approved(spec, record, edition_id="issue-001", bindings=current)


class BindingsRefusalTests(unittest.TestCase):
    """A binding a kind declares and cannot compute is a refusal, not a hole."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_project(self.root)
        pin_article_source_hash(self.root, add_extraction(self.root))
        # ``teaching`` covers the explainer alone, so an edition without one
        # binds nothing and has nothing to refuse.  The explainer is here so
        # that all three source-reading kinds are actually exercised.
        add_explainer(self.root)
        self.edition = load_edition_with_records(self.root)

    def test_a_source_reading_kind_needs_somewhere_to_read_the_sources_from(self):
        for kind in SOURCE_READING_KINDS:
            with self.subTest(kind=kind), self.assertRaisesRegex(
                ValidationError, "no sources directory"
            ):
                current_bindings(PIECE_REVIEW_KINDS[kind], self.edition)

    def test_recording_refuses_a_source_with_no_committed_extraction(self):
        """``require_extractions`` is true at record time: a review cannot claim
        to have read a manuscript against an extraction that does not exist."""

        (self.root / "library" / "sources" / "source-one" / "extracted.md").unlink()

        with self.assertRaisesRegex(ValidationError, "requires a committed extraction"):
            current_bindings(
                PIECE_REVIEW_KINDS["worth"],
                load_edition_with_records(self.root),
                sources_dir=self.root / "library" / "sources",
                require_extractions=True,
            )


if __name__ == "__main__":
    unittest.main()
