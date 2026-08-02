import contextlib
import io
import unittest

from magazine.cli import REVIEW_KINDS, parser
from magazine.produce_graph import BENCH_REVIEW_KINDS


def _record_args(*extra: str):
    return parser().parse_args(
        [
            "review",
            "record",
            "001-issue",
            "--reviewer",
            "A reader",
            "--result",
            "approved",
            *extra,
        ]
    )


class ReviewKindTests(unittest.TestCase):
    """``--kind`` is the operator's door onto the bench, and it went stale.

    ``REVIEW_KINDS`` was a hand-typed literal, so ``line`` and ``learning``
    stayed selectable for an entire redesign after the lens table stopped
    naming them: an operator could record a verdict for a judge that no longer
    exists and no surface would ever read it back.
    """

    def test_the_selectable_kinds_are_the_bench_plus_the_render_decision(self):
        self.assertEqual(REVIEW_KINDS, ("render", *BENCH_REVIEW_KINDS))
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

    def test_every_bench_kind_is_selectable_and_render_stays_the_default(self):
        self.assertEqual(_record_args().kind, "render")
        for kind in REVIEW_KINDS:
            with self.subTest(kind=kind):
                self.assertEqual(_record_args("--kind", kind).kind, kind)

    def test_the_retired_judges_are_refused_rather_than_recorded(self):
        for kind in ("line", "learning"):
            with self.subTest(kind=kind), self.assertRaises(SystemExit):
                _record_args("--kind", kind)

    def test_the_kind_help_names_each_lens_by_its_own_concern(self):
        """Seven names in a list teach an operator nothing about which to pick.

        The whole reason the bench went from two broad judges to seven narrow
        lenses is that one reader asked seven questions answers none of them,
        so the help has to carry each lens's single concern, not just its name.
        """

        printed = io.StringIO()
        with contextlib.redirect_stdout(printed), self.assertRaises(SystemExit):
            parser().parse_args(["review", "record", "--help"])
        # argparse hard-wraps help text, so compare against one flat line.
        help_text = " ".join(printed.getvalue().split())
        for phrase in (
            "better than reading the source",
            "is every claim the source's",
            "in the right order",
            "can a novice use the explainer",
            "did a person write this",
            "correct as typeset",
            "one set of covers",
        ):
            self.assertIn(phrase, help_text)


class CliTests(unittest.TestCase):
    def test_finish_defaults_the_final_id_and_accepts_an_override(self):
        automatic = parser().parse_args(["finish", "004-unreleased"])
        explicit = parser().parse_args(
            [
                "finish",
                "004-unreleased",
                "--as",
                "004-systems",
            ]
        )

        self.assertEqual(automatic.command, "finish")
        self.assertIsNone(automatic.final_id)
        self.assertEqual(explicit.final_id, "004-systems")

    def test_capture_requires_author_identity_mode(self):
        with self.assertRaises(SystemExit):
            parser().parse_args([
                "capture",
                "https://example.com/article",
                "--snapshot",
                "article.html",
                "--author",
                "A. Writer",
            ])

    def test_capture_accepts_provenance_backed_author_note(self):
        args = parser().parse_args([
            "capture",
            "https://example.com/article",
            "--snapshot",
            "article.html",
            "--author",
            "A. Writer",
            "--author-note",
            "A. Writer is chief architect at Example Company.",
            "--author-evidence",
            "https://example.com/author",
            "author.html",
        ])

        self.assertEqual(args.author, "A. Writer")
        self.assertEqual(
            args.author_evidence,
            [["https://example.com/author", "author.html"]],
        )

    def test_capture_accepts_explicit_institutional_author(self):
        args = parser().parse_args([
            "capture",
            "https://example.com/article",
            "--snapshot",
            "article.html",
            "--author",
            "Example Research",
            "--institutional-author",
        ])

        self.assertTrue(args.institutional_author)
        self.assertIsNone(args.author_note)
