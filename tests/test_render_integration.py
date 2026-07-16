import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pypdf import PdfReader
import yaml

from magazine import Magazine, ValidationError
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
            self.assertEqual(len(manifest["inputs"]["sources"][0]["raw_captures"]), 1)
            self.assertEqual(manifest["layout"]["maximum_article_pages"], 7)
            self.assertLessEqual(manifest["layout"]["article_pages"]["article"], 7)
            self.assertEqual(manifest["layout"]["maximum_editorial_pages"], 2)
            self.assertEqual(manifest["layout"]["editorial_pages"], 1)
            reader_text = "\n".join(page.extract_text() or "" for page in PdfReader(str(result.reader_pdf)).pages)
            self.assertIn("A Test Editorial", reader_text)

    def test_build_rejects_article_over_seven_reader_pages(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_project(root)
            edition_dir = root / "editions" / "issue-001"
            paragraphs = [f"Substantive source paragraph {index} with enough words to occupy space." for index in range(420)]
            (edition_dir / "articles" / "article.md").write_text(
                "\n\n".join(paragraphs) + "\n", encoding="utf-8"
            )
            ledger = {
                "schema_version": 1,
                "source_ids": ["source-one"],
                "content_mode": "faithful_edit",
                "paragraphs": [
                    {"id": f"p{index}", "kind": "p", "status": "retained", "source": text}
                    for index, text in enumerate(paragraphs)
                ],
            }
            (edition_dir / "fidelity" / "article.yaml").write_text(
                yaml.safe_dump(ledger), encoding="utf-8"
            )

            with self.assertRaisesRegex(ValidationError, "hard cap is 7"):
                Magazine(root).build("issue-001")

    def test_edition_cannot_raise_the_hard_article_page_cap(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_project(root)
            manifest_path = root / "editions" / "issue-001" / "edition.yaml"
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            manifest["format"] = {"max_article_pages": 8}
            manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValidationError, "hard publication rule"):
                Magazine(root).build("issue-001")

    def test_build_rejects_editorial_over_two_reader_pages(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_project(root)
            editorial = root / "editions" / "issue-001" / "editorial.md"
            paragraphs = [
                f"Editorial paragraph {index} makes an original argument with sufficient detail."
                for index in range(160)
            ]
            editorial.write_text(
                "---\ntitle: A Long Editorial\nbyline: The editors\n---\n\n"
                + "\n\n".join(paragraphs),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValidationError, "Editorial spans.*hard cap is 2"):
                Magazine(root).build("issue-001")

    def test_edition_cannot_raise_the_hard_editorial_page_cap(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_project(root)
            manifest_path = root / "editions" / "issue-001" / "edition.yaml"
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            manifest["format"] = {"max_editorial_pages": 3}
            manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValidationError, "hard publication rule"):
                Magazine(root).build("issue-001")

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

    def test_articles_edition_can_append_backmatter_sections(self):
        with TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            make_project(tmp_path)
            edition_dir = tmp_path / "editions" / "issue-001"
            (edition_dir / "colophon.md").write_text("# Colophon\n\nMade with care.", encoding="utf-8")
            manifest_path = edition_dir / "edition.yaml"
            manifest = yaml.safe_load(manifest_path.read_text())
            manifest["sections"] = [{"kind": "colophon", "title": "Colophon", "path": "colophon.md"}]
            manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

            result = Magazine(tmp_path).build("issue-001")

            text = "\n".join(page.extract_text() or "" for page in PdfReader(str(result.reader_pdf)).pages)
            self.assertIn("The original article.", text)
            self.assertIn("Made with care.", text)

    def test_fenced_code_is_monospaced_line_preserving_and_safely_paginated(self):
        with TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            make_project(tmp_path)
            edition_dir = tmp_path / "editions" / "issue-001"
            code = "\n".join(f"    call_{index:03d}();" for index in range(120))
            (edition_dir / "articles" / "article.md").write_text(
                f"Before code.\n\n```java\n{code}\n```\n\nAfter code.\n",
                encoding="utf-8",
            )
            ledger = {
                "schema_version": 1,
                "source_ids": ["source-one"],
                "paragraphs": [
                    {"id": "before", "kind": "p", "status": "retained", "source": "Before code."},
                    {"id": "sample", "kind": "code", "status": "retained", "source": code},
                    {"id": "after", "kind": "p", "status": "retained", "source": "After code."},
                ],
            }
            (edition_dir / "fidelity" / "article.yaml").write_text(yaml.safe_dump(ledger), encoding="utf-8")

            result = Magazine(tmp_path).build("issue-001")

            reader = PdfReader(str(result.reader_pdf))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            self.assertGreaterEqual(len(reader.pages), 8)
            self.assertIn("call_000();", text)
            self.assertIn("call_119();", text)
            self.assertIn("After code.", text)
