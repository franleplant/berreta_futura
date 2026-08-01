"""The one deterministic check that survived the fidelity ledger's deletion.

The ledger used to compare a manuscript's fenced code against the ledger's own
``source``/``edited`` columns -- which the same writer had produced in the same
sitting, and which nothing ever checked against the real source.  The check is
now pointed at the committed source extraction instead, so passing it means the
code in the magazine is traceably the code the source published.

That is worth keeping deterministic for one reason: a reader can copy a code
sample out of the magazine and run it.  Everything else about faithfulness is
now an LLM fact-checker's judgment, and an LLM judge is exactly the wrong
instrument for noticing that one line of a config block went missing.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
import itertools
import unittest

import pytest

from magazine import Magazine, ValidationError
from magazine.code_blocks import (
    manuscript_code_blocks,
    verify_manuscript_code_blocks,
    visible_code,
)
from magazine.extraction import load_extraction
from test_manifest import (
    add_extraction,
    make_project,
    pin_article_source_hash,
    set_open_edition,
)

_projects = itertools.count()


SAMPLE = """def widen(rows):
    for row in rows:
        if row.width < 4:
            row.width = 4
    return rows
"""


def extraction_with(tmp_path: Path, body: str):
    """A committed extraction whose body contains ``body``, loaded."""

    root = tmp_path / f"source-project-{next(_projects)}"
    root.mkdir()
    make_project(root)
    add_extraction(root, body=body)
    extraction = load_extraction(root / "library" / "sources", "source-one")
    assert extraction is not None
    return extraction


def manuscript_with(tmp_path: Path, name: str, code: str) -> Path:
    path = tmp_path / f"{name}.md"
    path.write_text(f"An opening paragraph.\n\n```python\n{code}```\n", encoding="utf-8")
    return path


class VisibleCodeTests(unittest.TestCase):
    """What the normalization forgives, and what it refuses to forgive.

    The line between them is what a reader can act on.  A tab and four spaces
    print identically and copy identically; a missing line does not.
    """

    def test_tabs_expand_and_trailing_whitespace_goes(self):
        self.assertEqual(visible_code("\tif x:\n\t\treturn 1   \n"), "    if x:\n        return 1")

    def test_blank_edges_inside_the_fence_are_typography(self):
        self.assertEqual(visible_code("\n\nreturn 1\n\n\n"), "return 1")

    def test_interior_blank_lines_survive(self):
        """A blank line between two statements is the author's paragraphing."""

        self.assertEqual(visible_code("a = 1\n\nb = 2\n"), "a = 1\n\nb = 2")

    def test_indentation_depth_is_substantive(self):
        self.assertNotEqual(visible_code("  return 1"), visible_code("    return 1"))


class ManuscriptCodeBlockTests(unittest.TestCase):
    """The blocks come from the renderer's own parse, not a line scanner."""

    def test_fences_are_read_in_reading_order(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "m.md"
            path.write_text(
                "Intro.\n\n```\nfirst\n```\n\nMiddle.\n\n```py\nsecond\n```\n",
                encoding="utf-8",
            )
            self.assertEqual(manuscript_code_blocks(path), ["first", "second"])

    def test_a_fence_nested_in_a_list_item_is_still_a_fence(self):
        """A line scanner would miss this; the CommonMark parse does not."""

        with TemporaryDirectory() as directory:
            path = Path(directory) / "m.md"
            path.write_text(
                "Intro.\n\n- Step one:\n\n  ```\n  make build\n  ```\n",
                encoding="utf-8",
            )
            self.assertEqual(manuscript_code_blocks(path), ["make build"])


@pytest.fixture()
def source(tmp_path: Path):
    return extraction_with(
        tmp_path, f"Prose before the sample.\n\n```python\n{SAMPLE}```\n\nProse after.\n"
    )


def test_an_identical_fence_passes(tmp_path: Path, source) -> None:
    manuscript = manuscript_with(tmp_path, "ok", SAMPLE)
    assert verify_manuscript_code_blocks(manuscript, [source]) == 1


def test_a_fence_differing_by_one_line_is_rejected(tmp_path: Path, source) -> None:
    """The whole reason this check outlived the ledger.

    One changed comparison in the middle of an otherwise perfect block is
    precisely what a prose judge reads straight past, and precisely what breaks
    for a reader who copies the sample and runs it.
    """

    corrupted = SAMPLE.replace("row.width < 4", "row.width < 5")
    manuscript = manuscript_with(tmp_path, "off-by-one", corrupted)
    with pytest.raises(ValidationError) as caught:
        verify_manuscript_code_blocks(manuscript, [source])
    (message,) = caught.value.errors
    assert "code block 1 diverges" in message
    # The block matches for two lines and breaks on the third; the author is
    # sent to that line, not to the top of the block.
    assert "at line 3" in message
    assert "row.width < 5" in message


def test_a_dropped_line_is_rejected(tmp_path: Path, source) -> None:
    manuscript = manuscript_with(
        tmp_path, "dropped", SAMPLE.replace("            row.width = 4\n", "")
    )
    with pytest.raises(ValidationError, match="diverges"):
        verify_manuscript_code_blocks(manuscript, [source])


def test_reindentation_is_rejected(tmp_path: Path, source) -> None:
    """Indentation is meaning in this magazine's usual languages."""

    manuscript = manuscript_with(
        tmp_path, "reindented", SAMPLE.replace("    for row", "  for row")
    )
    with pytest.raises(ValidationError, match="diverges"):
        verify_manuscript_code_blocks(manuscript, [source])


def test_tab_and_trailing_whitespace_differences_are_forgiven(
    tmp_path: Path, source
) -> None:
    """Invisible-on-the-page differences must not cost an author a rewrite."""

    retyped = SAMPLE.replace("    ", "\t", 1).replace("return rows", "return rows   ")
    manuscript = manuscript_with(tmp_path, "retyped", retyped)
    assert verify_manuscript_code_blocks(manuscript, [source]) == 1


def test_a_block_that_appears_nowhere_gets_the_blunter_message(
    tmp_path: Path, source
) -> None:
    """With no near miss to point at, the error must not invent one.

    Naming a line number against an unrelated part of the extraction would send
    the author hunting through the wrong passage.
    """

    manuscript = manuscript_with(tmp_path, "invented", "print('hello')\n")
    with pytest.raises(ValidationError) as caught:
        verify_manuscript_code_blocks(manuscript, [source])
    (message,) = caught.value.errors
    assert "does not appear in any pinned source extraction" in message
    assert "source-one" in message


def test_any_one_of_several_pinned_extractions_may_carry_the_block(
    tmp_path: Path, source
) -> None:
    """A multi-source article's code may come from any source it cites."""

    other = extraction_with(tmp_path, "An unrelated source with no code at all.\n")
    manuscript = manuscript_with(tmp_path, "multi", SAMPLE)
    assert verify_manuscript_code_blocks(manuscript, [other, source]) == 1


def test_a_manuscript_without_fences_always_passes(tmp_path: Path, source) -> None:
    path = tmp_path / "prose.md"
    path.write_text("Just prose, no code.\n", encoding="utf-8")
    assert verify_manuscript_code_blocks(path, [source]) == 0


def test_an_article_without_committed_extractions_is_skipped(tmp_path: Path) -> None:
    """Released editions predate committed extractions.

    There is nothing to compare against, which is a historical state and not a
    failure -- exactly the rule the pin verification already follows.
    """

    manuscript = manuscript_with(tmp_path, "released", SAMPLE)
    assert verify_manuscript_code_blocks(manuscript, []) == 0


def test_validate_rejects_a_corrupted_fence_end_to_end(tmp_path: Path) -> None:
    """The check is wired into ``mag validate``, not merely importable."""

    root = tmp_path / "project"
    root.mkdir()
    make_project(root)
    set_open_edition(root, "issue-001", issue_number=1, source_ids=("source-one",))
    body = f"The original article.\n\n```python\n{SAMPLE}```\n"
    pin_article_source_hash(root, add_extraction(root, body=body))
    manuscript = root / "editions" / "issue-001" / "articles" / "article.md"

    manuscript.write_text(
        f"The original article.\n\n```python\n{SAMPLE}```\n", encoding="utf-8"
    )
    assert Magazine(root).validate("issue-001").id == "issue-001"

    manuscript.write_text(
        "The original article.\n\n```python\n"
        + SAMPLE.replace("row.width = 4", "row.width = 40")
        + "```\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="code block 1 diverges"):
        Magazine(root).validate("issue-001")


def test_a_moved_source_is_still_detected_after_the_ledger_is_gone(
    tmp_path: Path,
) -> None:
    """Provenance survived the deletion: this is the class-B value re-homed.

    The pin used to live in the fidelity ledger.  It now lives in the article's
    own ``edition.yaml`` row, beside the ``source_ids`` it covers, and it still
    catches the case that actually matters -- a source whose text moved after we
    republished it.
    """

    root = tmp_path / "project"
    root.mkdir()
    make_project(root)
    set_open_edition(root, "issue-001", issue_number=1, source_ids=("source-one",))
    pin_article_source_hash(root, add_extraction(root))
    assert Magazine(root).validate("issue-001").id == "issue-001"

    add_extraction(root, body="The original article, quietly revised.\n")
    with pytest.raises(ValidationError) as caught:
        Magazine(root).validate("issue-001")
    (message,) = caught.value.errors
    assert "article article: source_body_sha256 for source-one" in message
    assert "no longer matches the committed extraction" in message
