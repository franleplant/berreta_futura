import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pypdf import PdfReader
import yaml

from magazine import Magazine
from test_manifest import make_project


@unittest.skipUnless(importlib.util.find_spec("reportlab") is not None, "ReportLab not installed in this runtime")
class RenderIntegrationTests(unittest.TestCase):
    def test_build_produces_reader_booklet_and_checksums(self):
        with TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            make_project(tmp_path)
            result = Magazine(tmp_path).build("issue-001")
            self.assertTrue(result.reader_pdf.is_file())
            self.assertTrue(result.booklet_pdf.is_file())
            self.assertTrue((result.output_dir / "SHA256SUMS").is_file())
            self.assertGreaterEqual(len(PdfReader(str(result.reader_pdf)).pages), 5)
            preflight = json.loads((result.output_dir / "preflight.json").read_text())
            self.assertTrue(preflight["reader"]["page_count_multiple_of_four"])
            self.assertTrue(preflight["reader"]["all_pages_a5"])
            self.assertTrue(preflight["home_booklet"]["all_pages_a4_landscape"])
            self.assertEqual(preflight["result"], "home_ready_studio_blocked")
            manifest = json.loads((result.output_dir / "edition-manifest.json").read_text())
            self.assertEqual(manifest["inputs"]["sources"][0]["id"], "source-one")

    def test_sections_edition_packages_explicit_blocked_fidelity_status(self):
        with TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            make_project(tmp_path)
            edition_dir = tmp_path / "editions" / "issue-001"
            (edition_dir / "section.md").write_text("A source-safe section.", encoding="utf-8")
            fidelity_dir = edition_dir / "fidelity"
            (fidelity_dir / "source-edition-status.yaml").write_text(
                yaml.safe_dump({
                    "source_id": "source-one",
                    "content_mode": "faithful_edit",
                    "status": "blocked",
                    "blockers": ["rights_status_unknown"],
                    "metrics": {"unlabeled_additions": 0},
                }),
                encoding="utf-8",
            )
            manifest_path = edition_dir / "edition.yaml"
            manifest = yaml.safe_load(manifest_path.read_text())
            manifest.pop("editorial")
            manifest.pop("articles")
            manifest["sources"] = ["source-one"]
            manifest["sections"] = [{"kind": "production_note", "title": "Status", "path": "section.md"}]
            manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

            result = Magazine(tmp_path).build("issue-001")

            report = (result.output_dir / "fidelity.md").read_text()
            self.assertIn("Status: **blocked**", report)
            self.assertIn("rights_status_unknown", report)
