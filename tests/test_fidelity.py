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

    def test_report_labels_can_be_rendered_in_spanish(self):
        path = self.root / "ledger.yaml"
        write_ledger(path, [{"status": "retained", "source": "texto fuente"}])

        markdown = fidelity_report(path).as_markdown("Artículo", language="es")

        self.assertIn("| Medida | Valor |", markdown)
        self.assertIn("Palabras sustantivas originales", markdown)
        self.assertNotIn("| Measure | Value |", markdown)
