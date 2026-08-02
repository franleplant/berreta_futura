"""Refusing an edition whose pieces are still unwritten staging slots.

Edition ``rerun-004-the-systems-around-the-model`` validated, built and
preflighted clean while its opening editorial was still the marker
``mag article stage`` writes, and ``EDITORIAL WORK REQUIRED`` was typeset onto
reader page four.  These tests hold the two halves of the fix apart: that the
refusal fires on the exact shape that got through, and that it stays silent on
prose that merely happens to be short or to talk about staging.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from magazine import Magazine, ValidationError
from magazine.staging_marker import (
    STAGE_STATUS_KEY,
    STAGE_STATUS_TODO,
    STAGING_LABEL,
    STAGING_TODO,
    is_staging_marker,
    staging_marker_signals,
)

from test_manifest import make_project


def staged_marker(**metadata: object) -> str:
    """The marker exactly as it reached reader page four: a real paragraph.

    The skeleton ``mag article stage`` writes puts the TODO in an HTML comment,
    which the publication parser rejects and an illustrated opener has no
    leading paragraph for.  Making it a paragraph is what let it typeset, so
    that is the shape most of these tests use.
    """

    header = {"label": STAGING_LABEL, STAGE_STATUS_KEY: STAGE_STATUS_TODO}
    header.update(metadata)
    return (
        "---\n"
        + yaml.safe_dump(header, sort_keys=False)
        + "---\n\n"
        + STAGING_TODO
        + "\n"
    )


class SignalTests(unittest.TestCase):
    """The rule is three structural signals, and length is not one of them."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "piece.md"

    def write(self, text: str) -> Path:
        self.path.write_text(text, encoding="utf-8")
        return self.path

    def test_the_staged_skeleton_raises_every_signal(self):
        self.assertEqual(
            staging_marker_signals(self.write(staged_marker())),
            ("stage_status", "label", "body"),
        )

    def test_stage_status_alone_condemns_a_written_looking_file(self):
        self.write(
            "---\ntitle: A Real Title\nlabel: FAITHFUL EDIT\n"
            f"{STAGE_STATUS_KEY}: {STAGE_STATUS_TODO}\n---\n\n"
            "Several paragraphs of entirely plausible prose.\n\n"
            "And a second one, for good measure.\n"
        )

        self.assertEqual(staging_marker_signals(self.path), ("stage_status",))

    def test_the_printed_label_alone_condemns_a_file_that_lost_the_key(self):
        self.write(
            f"---\ntitle: Untitled editorial\nlabel: {STAGING_LABEL}\n---\n\n"
            "Prose someone wrote without clearing the label.\n"
        )

        self.assertEqual(staging_marker_signals(self.path), ("label",))

    def test_a_body_that_is_only_the_todo_condemns_a_bare_file(self):
        self.write(f"---\ntitle: Untitled editorial\n---\n\n{STAGING_TODO}\n")

        self.assertEqual(staging_marker_signals(self.path), ("body",))

    def test_a_one_paragraph_editorial_of_real_prose_is_not_a_marker(self):
        self.write(
            "---\ntitle: Intelligence Needs Surroundings\nbyline: The Editors\n"
            "label: 'EDITORIAL: ORIGINAL EDITOR TEXT'\n---\n\n"
            "A model never arrives alone.\n"
        )

        self.assertFalse(is_staging_marker(self.path))

    def test_prose_that_discusses_the_marker_is_not_a_marker(self):
        """Structural, not a substring search: an article may quote the thing."""

        self.write(
            "---\ntitle: How Staging Works\nlabel: FAITHFUL EDIT\n---\n\n"
            "Staging writes a slot whose frontmatter says "
            f"`{STAGE_STATUS_KEY}: {STAGE_STATUS_TODO}` under the label "
            f"{STAGING_LABEL}.\n\n"
            "```yaml\n"
            f"{STAGE_STATUS_KEY}: {STAGE_STATUS_TODO}\n"
            f"label: {STAGING_LABEL}\n"
            "```\n\n"
            f"The body then reads: {STAGING_TODO}\n"
        )

        self.assertFalse(is_staging_marker(self.path))

    def test_a_missing_manuscript_is_the_manifest_loader_s_complaint(self):
        self.assertEqual(staging_marker_signals(self.path / "absent.md"), ())


class RefusalTests(unittest.TestCase):
    """What ``validate`` and ``build`` do about a staged piece."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_project(self.root)
        self.edition_dir = self.root / "editions" / "issue-001"

    def stage_editorial(self) -> None:
        (self.edition_dir / "editorial.md").write_text(
            staged_marker(title="Untitled editorial", byline="The Editors"),
            encoding="utf-8",
        )

    def stage_article(self) -> None:
        (self.edition_dir / "articles" / "article.md").write_text(
            staged_marker(source_ids=["source-one"], content_mode="faithful_edit"),
            encoding="utf-8",
        )

    def test_the_short_real_editorial_the_fixture_ships_still_validates(self):
        """Being short is not the signal, and must never become one."""

        editorial = (self.edition_dir / "editorial.md").read_text(encoding="utf-8")
        self.assertIn("An argument.", editorial)

        self.assertEqual(Magazine(self.root).validate("issue-001").id, "issue-001")

    def test_a_staged_editorial_refuses_validate(self):
        self.stage_editorial()

        with self.assertRaises(ValidationError) as caught:
            Magazine(self.root).validate("issue-001")

        errors = caught.exception.errors
        self.assertIn("1 piece(s) are still unwritten staging markers", errors[0])
        self.assertIn("editorial: editions/issue-001/editorial.md", errors[1])
        self.assertIn("stage_status: todo", errors[1])
        self.assertEqual(
            errors[-1],
            "Draft every piece named above with "
            "`uv run --locked mag produce issue-001`.",
        )

    def test_a_staged_editorial_refuses_build_before_anything_is_rendered(self):
        self.stage_editorial()
        output = self.root / "output"

        with self.assertRaises(ValidationError) as caught:
            Magazine(self.root).build("issue-001")

        self.assertIn("editorial", caught.exception.errors[1])
        self.assertFalse(output.exists(), "build must refuse before it renders")

    def test_a_staged_article_refuses_validate_and_build(self):
        self.stage_article()

        with self.assertRaises(ValidationError) as caught:
            Magazine(self.root).validate("issue-001")
        with self.assertRaises(ValidationError):
            Magazine(self.root).build("issue-001")

        self.assertIn(
            "article: editions/issue-001/articles/article.md",
            caught.exception.errors[1],
        )

    def test_the_refusal_names_every_unfinished_piece_at_once(self):
        """One command answers all of them, so one error reports all of them."""

        self.stage_editorial()
        self.stage_article()

        with self.assertRaises(ValidationError) as caught:
            Magazine(self.root).validate("issue-001")

        errors = caught.exception.errors
        self.assertIn("2 piece(s)", errors[0])
        self.assertEqual(
            [error.split(":")[0] for error in errors[1:-1]],
            ["article", "editorial"],
        )

    def test_release_cannot_reach_its_review_gates_with_a_staged_piece(self):
        self.stage_editorial()

        with self.assertRaises(ValidationError) as caught:
            Magazine(self.root).release("issue-001")

        self.assertIn("unwritten staging markers", caught.exception.errors[0])

    def test_a_review_record_cannot_bind_to_an_unwritten_piece(self):
        self.stage_editorial()

        with self.assertRaises(ValidationError) as caught:
            Magazine(self.root).record_craft_review(
                "issue-001", reviewer="A Reader", result="approved"
            )

        self.assertIn("unwritten staging markers", caught.exception.errors[0])

    def test_an_edition_that_cannot_be_read_at_all_reports_its_own_error(self):
        """The staging check never pre-empts the loader's own complaint."""

        (self.edition_dir / "edition.yaml").unlink()

        with self.assertRaises(ValidationError) as caught:
            Magazine(self.root).validate("issue-001")

        self.assertNotIn("staging marker", "\n".join(caught.exception.errors))
