"""The CLI and compiler seams over the seven editorial lenses.

The per-kind record shapes are tested beside their modules and the shared spine
they all wear is tested in ``test_piece_review.py``; this file tests the part a
human touches: that ``mag review record --kind`` reaches the right recorder,
that a flag meaningful to one kind is refused by the kinds it cannot mean
anything to, that the judge's YAML verdict document actually lands in the record
instead of being retyped as strings, and that ``mag scores`` rolls the committed
records up.

``craft`` stands in for the per-piece lenses wherever one of them has to be
picked: it is what the retired ``line`` kind became on the axes these tests care
about -- it covers every piece including the editorial, and it binds the
manuscript and nothing else.
"""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from magazine import Magazine
from magazine.cli import PER_ARTICLE_REVIEW_KINDS, REVIEW_KINDS, main, parser

from test_manifest import (
    add_extraction,
    make_project,
    pin_article_source_hash,
    set_open_edition,
)


RECORD = ["review", "record", "issue-001", "--reviewer", "critic", "--result", "approved"]


def write_verdict(path: Path, payload: dict) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


class ReviewKindParsingTests(unittest.TestCase):
    def test_every_bench_kind_parses_and_render_stays_the_default(self):
        """The seven lenses in repair order, plus the render decision.

        ``line`` and ``learning`` stayed selectable in ``--kind`` for a whole
        release after the lens table stopped naming them, so the literal is
        asserted here rather than derived from the same tuple the CLI reads."""
        self.assertEqual(
            REVIEW_KINDS,
            (
                "render",
                "worth",
                "evidence",
                "shape",
                "teaching",
                "craft",
                "mechanics",
                "edition",
            ),
        )
        self.assertEqual(parser().parse_args(RECORD).kind, "render")
        for kind in REVIEW_KINDS:
            self.assertEqual(
                parser().parse_args([*RECORD, "--kind", kind]).kind, kind
            )

    def test_an_unknown_kind_is_still_refused(self):
        with self.assertRaises(SystemExit):
            parser().parse_args([*RECORD, "--kind", "prose"])

    def test_the_verdict_path_parses(self):
        args = parser().parse_args([*RECORD, "--kind", "craft", "--verdict", "v.yaml"])
        self.assertEqual(args.verdict, Path("v.yaml"))
        self.assertIsNone(parser().parse_args(RECORD).verdict)


class ReviewFlagScopeTests(unittest.TestCase):
    """Each flag is refused by every kind it cannot mean anything to."""

    def refuse(self, argv: list[str]) -> str:
        stderr = io.StringIO()
        with TemporaryDirectory() as tmp:
            with redirect_stderr(stderr):
                code = main(["--root", tmp, *argv])
        self.assertEqual(code, 2, stderr.getvalue())
        return stderr.getvalue()

    def test_engine_and_rebuild_are_refused_by_every_editorial_kind(self):
        for kind in (*PER_ARTICLE_REVIEW_KINDS, "edition"):
            self.assertIn(
                "--engine applies only to render reviews",
                self.refuse([*RECORD, "--kind", kind, "--engine", "weasyprint"]),
            )
            self.assertIn(
                "--rebuild applies only to render reviews",
                self.refuse([*RECORD, "--kind", kind, "--rebuild"]),
            )

    def test_articles_is_refused_by_the_whole_issue_kinds(self):
        """``--articles`` narrows a per-piece review.  A whole-issue verdict is
        not divisible by article -- that is the point of it -- so naming
        articles must be refused rather than quietly ignored."""
        self.assertEqual(
            PER_ARTICLE_REVIEW_KINDS,
            ("worth", "evidence", "shape", "teaching", "craft", "mechanics"),
        )
        for kind in ("edition",):
            message = self.refuse([*RECORD, "--kind", kind, "--articles", "article"])
            self.assertIn(
                "--articles applies only to the per-piece lenses "
                "(worth, evidence, shape, teaching, craft, mechanics)",
                message,
            )
            self.assertIn(f"a {kind} review binds the whole issue", message)

    def test_a_render_review_still_refuses_articles_and_now_refuses_a_verdict(self):
        self.assertIn(
            "--articles applies only to the per-piece lenses "
            "(worth, evidence, shape, teaching, craft, mechanics)",
            self.refuse([*RECORD, "--articles", ""]),
        )
        self.assertIn(
            "--verdict carries an editorial judge's findings",
            self.refuse([*RECORD, "--verdict", "v.yaml"]),
        )


class VerdictDocumentTests(unittest.TestCase):
    """``--verdict`` is how a judge's YAML document reaches the record."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_project(self.root)
        pin_article_source_hash(self.root, add_extraction(self.root))
        set_open_edition(self.root, "issue-001")
        self.verdict = self.root / "verdict.yaml"

    def record(self, argv: list[str]) -> int:
        with redirect_stdout(io.StringIO()):
            return main(["--root", str(self.root), *argv])

    def refuse(self, argv: list[str]) -> str:
        stderr = io.StringIO()
        with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
            code = main(["--root", str(self.root), *argv])
        self.assertEqual(code, 2, stderr.getvalue())
        return stderr.getvalue()

    def test_a_craft_verdict_lands_as_structured_findings_and_article_scores(self):
        write_verdict(
            self.verdict,
            {
                "result": "changes_required",
                "findings": [
                    {
                        "severity": "major",
                        "article": "article",
                        "locator": "- | The original article. | 1",
                        "repair_from": "- | The original article. | 1",
                        "category": "repeated_cadence",
                        "disposition": "fix",
                        "note": "The piece closes three sections on one shape.",
                        "suggestion": "Specification is where the difficulty sits.",
                    }
                ],
                "scores": {"structure": 4, "flow": 3},
                "notes": "One paragraph on how the piece reads.",
            },
        )

        # A per-piece lens reads one piece at a time, so the full review is
        # recorded once and then amended per piece; --articles names the piece
        # this verdict is about, which is also what makes its flat score map
        # unambiguous.
        self.assertEqual(
            self.record(
                [
                    "review", "record", "issue-001", "--reviewer", "Craft reader",
                    "--result", "approved", "--kind", "craft",
                ]
            ),
            0,
        )
        code = self.record(
            [
                "review", "record", "issue-001", "--reviewer", "Craft reader",
                "--result", "changes_required", "--kind", "craft",
                "--articles", "article", "--verdict", str(self.verdict),
            ]
        )

        self.assertEqual(code, 0)
        record = yaml.safe_load(
            (self.root / "editions" / "issue-001" / "reviews" / "craft.yaml")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(record["findings"][0]["category"], "repeated_cadence")
        self.assertEqual(record["findings"][0]["disposition"], "fix")
        self.assertEqual(
            record["findings"][0]["repair_from"], "- | The original article. | 1"
        )
        self.assertEqual(record["notes"], "One paragraph on how the piece reads.")
        self.assertEqual(
            record["articles"]["article"]["scores"], {"structure": 4, "flow": 3}
        )

    def test_a_verdict_finding_without_a_disposition_never_reaches_the_record(self):
        """The routing field the severity cap was replaced by, at the CLI seam.

        A lens whose verdict document omits ``disposition`` is a lens whose
        findings the composer cannot route into "must fix" or "for the editor",
        and a recorder that stored one anyway would be the severity cap back
        under a new name.  The refusal has to happen at the write, which is the
        last moment the field can still be supplied."""
        write_verdict(
            self.verdict,
            {
                "result": "changes_required",
                "findings": [
                    {
                        "severity": "major",
                        "article": "article",
                        "category": "repeated_cadence",
                        "note": "The piece closes three sections on one shape.",
                    }
                ],
            },
        )

        message = self.refuse(
            [
                "review", "record", "issue-001", "--reviewer", "Craft reader",
                "--result", "changes_required", "--kind", "craft",
                "--verdict", str(self.verdict),
            ]
        )

        self.assertIn("finding 1 requires a non-empty disposition", message)
        self.assertFalse(
            (self.root / "editions" / "issue-001" / "reviews" / "craft.yaml").exists()
        )

    def test_a_flat_score_map_needs_the_one_article_it_belongs_to(self):
        """Every per-piece prompt scores the piece in front of it, so a flat
        dimension map is only unambiguous when the recording names one article.
        Guessing which piece it meant would file a judgement against a
        manuscript nobody read."""
        write_verdict(self.verdict, {"scores": {"structure": 4}})

        message = self.refuse(
            [
                "review", "record", "issue-001", "--reviewer", "Craft reader",
                "--result", "approved", "--kind", "craft",
                "--verdict", str(self.verdict),
            ]
        )

        self.assertIn("A flat scores map belongs to one article", message)

    def test_a_verdict_result_must_agree_with_the_recorded_result(self):
        write_verdict(self.verdict, {"result": "changes_required", "findings": []})

        message = self.refuse(
            [
                "review", "record", "issue-001", "--reviewer", "Managing editor",
                "--result", "approved", "--kind", "edition",
                "--verdict", str(self.verdict),
            ]
        )

        self.assertIn("but --result says 'approved'", message)

    def test_a_verdict_carrying_keys_the_record_does_not_store_is_refused(self):
        """Silently dropping a block the judge emitted would lose a verdict the
        operator believes was recorded."""
        write_verdict(self.verdict, {"comprehension_notes": "stray"})

        message = self.refuse(
            [
                "review", "record", "issue-001", "--reviewer", "Reader panel",
                "--result", "approved", "--kind", "teaching",
                "--verdict", str(self.verdict),
            ]
        )

        self.assertIn("keys a teaching review does not record", message)

    def test_a_retired_persona_block_is_refused_rather_than_dropped(self):
        """``comprehension`` and ``manager_takeaways`` were storage for two model
        calls that no longer happen: ``prompts/README.md`` retired Marcus and
        Priya into ``evidence``, and Nadia's six questions now go in ``notes``
        because one parser has to serve all seven lenses.  A verdict that still
        carries the old blocks must be refused, not silently stripped -- the
        operator would otherwise believe a persona verdict was recorded."""
        for block in ("comprehension", "manager_takeaways"):
            write_verdict(self.verdict, {"result": "approved", block: []})

            message = self.refuse(
                [
                    "review", "record", "issue-001", "--reviewer", "Reader panel",
                    "--result", "approved", "--kind", "teaching",
                    "--verdict", str(self.verdict),
                ]
            )

            self.assertIn(f"does not record: {block}", message)


class ReviewStatusTests(unittest.TestCase):
    """The compiler's status seam, one method per kind, resilient like evidence's."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_project(self.root)

    # ``teaching`` is deliberately absent from the two blanket status tests
    # below: the fixture edition carries no ``in_a_nutshell`` piece, so that
    # lens reports ``not_applicable`` rather than owing a record.  That
    # asymmetry is the point of it and is tested in ``test_piece_review.py``.
    STATUS_KINDS = ("worth", "evidence", "shape", "craft", "mechanics")

    def test_each_kind_reports_required_before_release_for_the_open_edition(self):
        set_open_edition(self.root, "issue-001")
        magazine = Magazine(self.root)

        for kind in self.STATUS_KINDS:
            status = magazine.piece_review_status(kind, "issue-001")
            self.assertEqual(status["status"], "required_before_release", kind)
        self.assertEqual(
            magazine.edition_review_status("issue-001")["status"],
            "required_before_release",
        )

    def test_each_kind_is_not_required_for_an_edition_that_cannot_be_released(self):
        magazine = Magazine(self.root)

        for kind in self.STATUS_KINDS:
            status = magazine.piece_review_status(kind, "issue-001")
            self.assertEqual(status["status"], "not_required", kind)
        self.assertEqual(
            magazine.edition_review_status("issue-001")["status"], "not_required"
        )

    def test_a_corrupt_record_degrades_instead_of_aborting_the_command(self):
        """Status is a diagnostic surface: a hand-damaged record must be
        reported, not raised through the CLI as a traceback.  Every kind on the
        bench, because ``mag review status`` lists them all at once and one
        broken record must not take the other six down with it."""
        magazine = Magazine(self.root)
        for kind in (*PER_ARTICLE_REVIEW_KINDS, "edition"):
            path = self.root / "editions" / "issue-001" / "reviews" / f"{kind}.yaml"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("result: [unclosed", encoding="utf-8")

        statuses = [
            (kind, magazine.piece_review_status(kind, "issue-001"))
            for kind in PER_ARTICLE_REVIEW_KINDS
        ]
        statuses.append(("edition", magazine.edition_review_status("issue-001")))
        for kind, status in statuses:
            self.assertEqual(status["status"], "unavailable", kind)
            self.assertTrue(
                any(f"{kind}.yaml" in error for error in status["errors"]), kind
            )

    def test_an_unknown_edition_reports_its_errors(self):
        status = Magazine(self.root).craft_review_status("issue-404")

        self.assertEqual(status["status"], "unavailable")
        self.assertTrue(any("issue-404" in error for error in status["errors"]))

    def test_a_recorded_craft_review_reads_back_approved_and_stales_on_an_edit(self):
        pin_article_source_hash(self.root, add_extraction(self.root))
        set_open_edition(self.root, "issue-001")
        magazine = Magazine(self.root)

        magazine.record_craft_review(
            "issue-001", reviewer="Craft reader", result="approved"
        )
        status = magazine.craft_review_status("issue-001")
        self.assertEqual(status["status"], "approved")
        # The editorial is craft-read like any other piece.
        self.assertEqual(status["articles"]["editorial"]["status"], "current")

        manuscript = self.root / "editions" / "issue-001" / "articles" / "article.md"
        manuscript.write_text(
            manuscript.read_text(encoding="utf-8") + "\n", encoding="utf-8"
        )

        status = magazine.craft_review_status("issue-001")
        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["articles"]["article"]["drift"], ["manuscript"])
        self.assertEqual(status["articles"]["editorial"]["status"], "current")

    def test_a_whole_issue_review_stales_on_the_manifest_and_on_any_manuscript(self):
        """The edition verdict binds every piece at once, so there is nothing
        to narrow: coherence is a function of all of them."""
        pin_article_source_hash(self.root, add_extraction(self.root))
        set_open_edition(self.root, "issue-001")
        magazine = Magazine(self.root)
        magazine.record_edition_review(
            "issue-001", reviewer="Managing editor", result="approved"
        )
        self.assertEqual(
            magazine.edition_review_status("issue-001")["status"], "approved"
        )

        manuscript = self.root / "editions" / "issue-001" / "articles" / "article.md"
        manuscript.write_text(
            manuscript.read_text(encoding="utf-8") + "\n", encoding="utf-8"
        )

        status = magazine.edition_review_status("issue-001")
        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["drift"], ["manuscript:article"])


class ScoresCommandTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_project(self.root)
        pin_article_source_hash(self.root, add_extraction(self.root))
        set_open_edition(self.root, "issue-001")

    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["--root", str(self.root), *argv])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_scores_regenerates_the_rollup_from_the_committed_records(self):
        Magazine(self.root).record_craft_review(
            "issue-001",
            reviewer="Craft reader",
            result="approved",
            scores={"article": {"structure": 4, "flow": 3}},
            reviewed_at="2026-08-01T10:00:00+00:00",
        )

        code, out, _ = self.run_cli(["scores"])

        self.assertEqual(code, 0)
        path = self.root / "editions" / "scores.yaml"
        self.assertIn(str(path), out)
        text = path.read_text(encoding="utf-8")
        self.assertIn("Do not edit by hand", text)
        rows = yaml.safe_load(text)["rows"]
        self.assertEqual(
            {(row["kind"], row["article"], row["dimension"], row["score"]) for row in rows},
            {("craft", "article", "structure", 4), ("craft", "article", "flow", 3)},
        )
        self.assertTrue(all(row["rounds_to_approval"] == 1 for row in rows))

    def test_check_passes_on_a_current_rollup_and_refuses_a_stale_one(self):
        """``editions/scores.yaml`` is derived, exactly like ``sources.md``: the
        check exists so a hand edit or a forgotten regeneration is caught rather
        than read as data."""
        self.assertEqual(self.run_cli(["scores"])[0], 0)
        self.assertEqual(self.run_cli(["scores", "--check"])[0], 0)

        Magazine(self.root).record_edition_review(
            "issue-001",
            reviewer="Managing editor",
            result="approved",
            scores={"through_line": 5},
        )

        code, _, err = self.run_cli(["scores", "--check"])
        self.assertEqual(code, 2)
        self.assertIn("does not match the committed review records", err)

    def test_check_refuses_a_missing_rollup(self):
        code, _, err = self.run_cli(["scores", "--check"])

        self.assertEqual(code, 2)
        self.assertIn("regenerate it with `mag scores`", err)


if __name__ == "__main__":
    unittest.main()
