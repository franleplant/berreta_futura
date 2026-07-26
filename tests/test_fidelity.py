from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from magazine.errors import ValidationError
from magazine.fidelity import fidelity_report


def write_ledger(path: Path, paragraphs: list[dict]):
    path.write_text(yaml.safe_dump({"schema_version": 1, "source_ids": ["s"], "paragraphs": paragraphs}), encoding="utf-8")


class FidelityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_fidelity_report_counts_each_edit_class(self):
        path = self.root / "ledger.yaml"
        write_ledger(path, [
        {"status": "retained", "source": "one two three", "edited": "one two three"},
        {"status": "boilerplate_removed", "source": "subscribe now"},
        {"status": "substantive_cut", "source": "important aside"},
        {"status": "modified", "source": "bad extraction", "edited": "bad extraction fixed"},
        {"status": "editorial_addition", "edited": "our context", "label": "Editor's note"},
        ])
        report = fidelity_report(path)
        self.assertEqual(report.source_words, 9)
        self.assertEqual(report.retained_words, 3)
        self.assertEqual(report.modified_edited_words, 3)
        self.assertEqual(report.editorial_addition_words, 2)
        self.assertEqual(report.retention_percent, 33.3)

    def test_editorial_addition_requires_visible_label(self):
        path = self.root / "ledger.yaml"
        write_ledger(path, [{"status": "editorial_addition", "edited": "unlabelled context"}])
        with self.assertRaisesRegex(ValidationError, "requires a visible label"):
            fidelity_report(path)

    def test_report_compares_reader_visible_manuscript_with_ledger(self):
        path = self.root / "ledger.yaml"
        manuscript = self.root / "article.md"
        write_ledger(path, [
            {"id": "p1", "kind": "p", "status": "retained", "source": "Read the source."},
            {"id": "web", "kind": "boilerplate", "status": "boilerplate_removed", "source": "Subscribe now"},
        ])
        manuscript.write_text(
            "---\ntitle: A manifest-supplied title\nauthor: An Author\n---\n\n"
            "Read [the source](https://example.com/a/very/long/path).\n",
            encoding="utf-8",
        )

        report = fidelity_report(path, manuscript)

        self.assertEqual(report.manuscript_blocks, 1)
        self.assertEqual(report.ledger_blocks, 1)
        self.assertIn("Manuscript integrity | PASS", report.as_markdown("Article"))

    def test_untracked_manuscript_expansion_is_actionable(self):
        path = self.root / "ledger.yaml"
        manuscript = self.root / "article.md"
        write_ledger(path, [{"id": "source-link", "kind": "p", "status": "retained", "source": "source"}])
        manuscript.write_text("Source: https://example.com/private/code\n", encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, r"diverges.*word 1.*ledger derives 1 visible words.*contains 2"):
            fidelity_report(path, manuscript)

    def test_modified_and_editorial_text_must_be_present(self):
        path = self.root / "ledger.yaml"
        manuscript = self.root / "article.md"
        write_ledger(path, [
            {"id": "m1", "kind": "p", "status": "modified", "source": "teh source", "edited": "the source"},
            {"id": "e1", "kind": "p", "status": "editorial_addition", "edited": "Editor's context", "label": "Editor's note"},
        ])
        manuscript.write_text("the source\n\n**Editor's note:** Editor's context\n", encoding="utf-8")

        report = fidelity_report(path, manuscript)

        self.assertEqual(report.modified_edited_words, 2)
        self.assertEqual(report.editorial_addition_words, 2)

    def test_ledger_compares_against_lists_breaks_and_quotes_as_rendered(self):
        """The gate reads ordered lists, nested lists, ``---`` and quotes as the reader does.

        The old line scanner folded ``1. First point`` into a paragraph and
        counted the ``---`` as a visible word; the renderer printed an ``<ol>``
        and drew the break as furniture.  The ledger carries the visible words
        only -- no list markers, nothing for the thematic break -- and matches.
        """
        path = self.root / "ledger.yaml"
        manuscript = self.root / "article.md"
        write_ledger(path, [
            {"id": "o1", "kind": "ordered", "status": "retained", "source": "First point"},
            {"id": "o2", "kind": "ordered", "status": "retained", "source": "Second point"},
            {"id": "b1", "kind": "bullet", "status": "retained", "source": "Outer point"},
            {"id": "b2", "kind": "bullet", "status": "retained", "source": "Inner point"},
            {"id": "q1", "kind": "quote", "status": "retained", "source": "A quoted claim."},
            {"id": "q2", "kind": "quote", "status": "retained", "source": "Its continuation."},
        ])
        manuscript.write_text(
            "1. First point\n2. Second point\n\n---\n\n"
            "- Outer point\n  - Inner point\n\n"
            "> A quoted claim.\n>\n> Its continuation.\n",
            encoding="utf-8",
        )

        report = fidelity_report(path, manuscript)

        self.assertEqual(report.manuscript_blocks, 6)
        self.assertEqual(report.ledger_blocks, 6)

    def test_an_ordered_item_missing_from_the_ledger_is_refused(self):
        """An ordered list can no longer hide words from the word-stream gate."""
        path = self.root / "ledger.yaml"
        manuscript = self.root / "article.md"
        write_ledger(path, [
            {"id": "o1", "kind": "ordered", "status": "retained", "source": "First point"},
        ])
        manuscript.write_text("1. First point\n2. Second point\n", encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "diverges from ledger-derived edited text"):
            fidelity_report(path, manuscript)

    def test_code_indentation_and_line_structure_are_substantive(self):
        path = self.root / "ledger.yaml"
        manuscript = self.root / "article.md"
        write_ledger(path, [{
            "id": "code-1",
            "kind": "code",
            "status": "retained",
            "source": "if ready:\n    publish()",
        }])
        manuscript.write_text("```python\nif ready:\npublish()\n```\n", encoding="utf-8")

        with self.assertRaisesRegex(
            ValidationError,
            r"code block 1 diverges.*code-1.*line 2.*indentation are substantive",
        ):
            fidelity_report(path, manuscript)

    def test_manuscript_with_unsupported_vocabulary_is_refused_naming_the_file(self):
        """A parse failure is a gate refusal that identifies the manuscript."""
        path = self.root / "ledger.yaml"
        manuscript = self.root / "article.md"
        write_ledger(path, [{"id": "p1", "kind": "p", "status": "retained", "source": "A paragraph."}])
        manuscript.write_text("A paragraph with <span>x</span> inline HTML.\n", encoding="utf-8")

        with self.assertRaisesRegex(
            ValidationError,
            r"article\.md: Unsupported Markdown inline token: html_inline",
        ):
            fidelity_report(path, manuscript)

    def test_faithful_synthesis_requires_mapped_material_condensation(self):
        path = self.root / "ledger.yaml"
        path.write_text(yaml.safe_dump({
            "schema_version": 1,
            "source_ids": ["s"],
            "content_mode": "faithful_synthesis",
            "paragraphs": [{
                "id": "synthesis",
                "kind": "p",
                "status": "modified",
                "source": "A long source argument with evidence context qualifications and conclusions.",
                "edited": "A condensed argument.",
            }],
        }), encoding="utf-8")

        report = fidelity_report(path)

        self.assertGreater(report.modified_source_words, report.modified_edited_words)

    def test_faithful_synthesis_rejects_unmapped_or_uncondensed_copy(self):
        path = self.root / "ledger.yaml"
        path.write_text(yaml.safe_dump({
            "schema_version": 1,
            "source_ids": ["s"],
            "content_mode": "faithful_synthesis",
            "paragraphs": [{"status": "retained", "source": "No actual synthesis."}],
        }), encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "requires source-to-edited mappings"):
            fidelity_report(path)

    def test_faithful_synthesis_rejects_added_narration_about_bylined_author(self):
        path = self.root / "ledger.yaml"
        path.write_text(yaml.safe_dump({
            "schema_version": 1,
            "source_ids": ["s"],
            "content_mode": "faithful_synthesis",
            "paragraphs": [{
                "id": "synthesis",
                "status": "modified",
                "source": "I distinguish a model's floor from its ceiling, then explain the consequences in detail.",
                "edited": "Narayanan argues that a model's floor differs from its ceiling.",
            }],
        }), encoding="utf-8")

        with self.assertRaisesRegex(
            ValidationError,
            r"adds detached narration.*Preserve the source's grammatical person",
        ):
            fidelity_report(path, source_author="Arvind Narayanan")

    def test_faithful_synthesis_rejects_generic_author_narration(self):
        path = self.root / "ledger.yaml"
        path.write_text(yaml.safe_dump({
            "schema_version": 1,
            "source_ids": ["s"],
            "content_mode": "faithful_synthesis",
            "paragraphs": [{
                "id": "synthesis",
                "status": "modified",
                "source": "I explain the distinction, its evidence, and its consequences at length.",
                "edited": "The author explains the distinction and its consequences.",
            }],
        }), encoding="utf-8")

        with self.assertRaisesRegex(ValidationError, "adds detached narration"):
            fidelity_report(path, source_author="James Hassabis")

    def test_faithful_synthesis_allows_exact_source_sentence_naming_author(self):
        path = self.root / "ledger.yaml"
        source = (
            "The introduction names Arvind Narayanan as the keynote speaker. "
            "It then presents a much longer argument with evidence and qualifications."
        )
        path.write_text(yaml.safe_dump({
            "schema_version": 1,
            "source_ids": ["s"],
            "content_mode": "faithful_synthesis",
            "paragraphs": [{
                "id": "synthesis",
                "status": "modified",
                "source": source,
                "edited": "The introduction names Arvind Narayanan as the keynote speaker.",
            }],
        }), encoding="utf-8")

        report = fidelity_report(path, source_author="Arvind Narayanan")

        self.assertGreater(report.modified_source_words, report.modified_edited_words)

    def test_report_labels_can_be_rendered_in_spanish(self):
        path = self.root / "ledger.yaml"
        write_ledger(path, [{"status": "retained", "source": "texto fuente"}])

        markdown = fidelity_report(path).as_markdown("Artículo", language="es")

        self.assertIn("| Medida | Valor |", markdown)
        self.assertIn("Palabras sustantivas originales", markdown)
        self.assertNotIn("| Measure | Value |", markdown)
