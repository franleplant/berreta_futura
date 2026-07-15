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
