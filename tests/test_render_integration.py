import importlib.util
import json
import math
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pypdf import PdfReader
from pypdf.generic import ContentStream
from PIL import Image
import yaml

from magazine import Magazine, ValidationError
from magazine.capture import archive_snapshot
from magazine.media_schema import MediaCaptureReview, SourceMediaAsset
from magazine.records import load_records
from magazine.render import (
    SANS,
    SANS_BOLD,
    SANS_MEDIUM,
    SANS_SEMIBOLD,
    SERIF,
    SERIF_BOLD,
    SERIF_DISPLAY,
    SERIF_ITALIC,
    _reportlab,
)
from test_manifest import add_spanish_translation, make_project


@unittest.skipUnless(importlib.util.find_spec("reportlab") is not None, "ReportLab not installed in this runtime")
class RenderIntegrationTests(unittest.TestCase):
    def assert_cover_uses_corte_bruto_geometry(self, path: Path) -> None:
        reader = PdfReader(str(path))
        stream = ContentStream(reader.pages[0].get_contents(), reader)
        character_spacing = []
        horizontal_scales = []
        transforms = []
        for operands, operator in stream.operations:
            if operator == b"Tc":
                character_spacing.append(float(operands[0]))
            elif operator == b"Tz":
                horizontal_scales.append(float(operands[0]))
            elif operator == b"cm":
                transforms.append(tuple(float(value) for value in operands))

        self.assertIn(-3.6, character_spacing)
        self.assertIn(92.0, horizontal_scales)
        self.assertIn(104.0, horizontal_scales)
        self.assertTrue(
            any(
                abs(matrix[2] - math.tan(math.radians(10))) < 0.00001
                for matrix in transforms
            ),
            "FUTURA must retain the selected prototype's forward 10-degree shear",
        )

    def assert_tracked_labels_do_not_leak_character_spacing(self, path: Path) -> None:
        reader = PdfReader(str(path))
        saw_tracking = False
        for page in reader.pages:
            stream = ContentStream(page.get_contents(), reader)
            stack: list[float] = []
            character_spacing = 0.0
            for operands, operator in stream.operations:
                if operator == b"q":
                    stack.append(character_spacing)
                elif operator == b"Q":
                    character_spacing = stack.pop()
                elif operator == b"Tc":
                    character_spacing = float(operands[0])
                    if character_spacing:
                        saw_tracking = True
                        self.assertTrue(stack, "non-zero character spacing must be scoped by q/Q")
            self.assertEqual(character_spacing, 0.0)
            self.assertEqual(stack, [])
        self.assertTrue(saw_tracking)

    def test_build_produces_reader_booklet_and_checksums(self):
        with TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            make_project(tmp_path)
            result = Magazine(tmp_path).build("issue-001")
            self.assertTrue(result.reader_pdf.is_file())
            self.assertTrue(result.booklet_pdf.is_file())
            self.assertTrue((result.output_dir / "SHA256SUMS").is_file())
            critic = json.loads((result.output_dir / "render-critic.json").read_text())
            self.assertEqual(critic["result"], "pass")
            self.assertEqual(critic["visual_review"]["status"], "required_before_release")
            self.assertTrue(
                (result.output_dir / "render-review" / "reader-contact-sheet-01.png").is_file()
            )
            self.assertTrue(
                (result.output_dir / "render-review" / "booklet-contact-sheet-01.png").is_file()
            )
            self.assertIn("render-critic.json", (result.output_dir / "SHA256SUMS").read_text())
            reader = PdfReader(str(result.reader_pdf))
            self.assertGreaterEqual(len(reader.pages), 8)
            self.assertEqual((reader.pages[1].extract_text() or "").strip(), "")
            self.assertEqual((reader.pages[-2].extract_text() or "").strip(), "")
            preflight = json.loads((result.output_dir / "preflight.json").read_text())
            self.assertTrue(preflight["reader"]["page_count_multiple_of_four"])
            self.assertTrue(preflight["reader"]["all_pages_a5"])
            self.assertTrue(preflight["home_booklet"]["all_pages_a4_landscape"])
            self.assertEqual(preflight["result"], "home_ready_studio_blocked")
            manifest = json.loads((result.output_dir / "edition-manifest.json").read_text())
            self.assertEqual(manifest["publication"]["name"], "Test Review")
            self.assertEqual(manifest["inputs"]["sources"][0]["id"], "source-one")
            self.assertEqual(len(manifest["inputs"]["sources"][0]["raw_captures"]), 1)
            self.assertEqual(manifest["layout"]["maximum_article_pages"], 7)
            self.assertEqual(manifest["layout"]["design_direction"], "O / Monument")
            self.assertLessEqual(manifest["layout"]["article_pages"]["article"], 7)
            self.assertEqual(manifest["layout"]["maximum_editorial_pages"], 2)
            self.assertEqual(manifest["layout"]["editorial_pages"], 1)
            reader_text = "\n".join(page.extract_text() or "" for page in PdfReader(str(result.reader_pdf)).pages)
            self.assertIn("A Test Editorial", reader_text)
            self.assertIn("AN ORIGINAL ARGUMENT", reader_text)
            self.assertIn("FEATURE 01", reader_text)
            self.assertIn("FAITHFUL EDIT", reader_text)
            self.assertIn("Author writes about this subject for Example.", reader_text)
            self.assertIn("TEST REVIEW", reader_text)
            cover_text = reader.pages[0].extract_text() or ""
            self.assertIn("2026 07 15", cover_text)
            self.assertNotIn("A5", cover_text)
            self.assertNotIn("PRIVATE READER", cover_text)
            self.assertNotIn(" ".join(("NOT", "FOR", "SALE")), reader_text)
            self.assertNotIn(" ".join(("PRIVATE", "EDITION")), reader_text)
            self.assert_cover_uses_corte_bruto_geometry(result.reader_pdf)
            self.assert_tracked_labels_do_not_leak_character_spacing(result.reader_pdf)

    def test_signature_padding_uses_distinct_configured_codas_once_each(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_project(root)
            edition_dir = root / "editions" / "issue-001"
            paragraphs = [
                f"Substantive source paragraph {index} with enough words to occupy space."
                for index in range(50)
            ]
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
            manifest_path = edition_dir / "edition.yaml"
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            manifest["format"] = {"target_pages": 12}
            manifest_path.write_text(
                yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
            )

            result = Magazine(root).build("issue-001")

            reader = PdfReader(str(result.reader_pdf))
            page_text = [page.extract_text() or "" for page in reader.pages]
            full_text = "\n".join(page_text)
            self.assertEqual(len(reader.pages), 12)
            self.assertEqual(full_text.count("Coda 1"), 1)
            self.assertEqual(full_text.count("Coda 2"), 1)
            self.assertEqual(full_text.count("Coda 3"), 1)
            self.assertNotIn("Closing plate", full_text)
            self.assertEqual(page_text[-2].strip(), "")

    def test_build_places_a_curated_opener_figure_and_audits_its_print_geometry(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_project(root)
            image_path = root / "source-diagram.png"
            Image.new("RGB", (1800, 900), "white").save(image_path)

            sources_dir = root / "library" / "sources"
            record = load_records(sources_dir)[0]
            archived = archive_snapshot(
                record,
                sources_dir,
                image_path,
                method="test_figure",
            )
            capture = archived.raw_captures[-1]
            raw_manifest = json.loads(
                (sources_dir / archived.id / capture["path"]).read_text(encoding="utf-8")
            )
            artifact = raw_manifest["artifacts"][0]
            media = SourceMediaAsset(
                id="source-diagram",
                artifact_path=artifact["path"],
                artifact_sha256=artifact["sha256"],
                mime_type="image/png",
                creator="Author",
                credit="Diagram by Author",
                rights={
                    "status": "author_owned",
                    "intended_use": "publication",
                    "attribution_required": True,
                    "public_reprint_allowed": True,
                },
            )
            replace(
                archived,
                media_reviews=(
                    MediaCaptureReview(
                        next(item["id"] for item in archived.raw_captures if item["id"] != capture["id"]),
                        "no_media",
                        (),
                    ),
                    MediaCaptureReview(capture["id"], "media_curated", (media,)),
                ),
            ).write(sources_dir)

            manifest_path = root / "editions" / "issue-001" / "edition.yaml"
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            manifest["articles"][0]["figures"] = [{
                "id": "diagram",
                "source_id": "source-one",
                "asset_id": "source-diagram",
                "decision": "include",
                "criteria": ["important", "useful"],
                "rationale": "The diagram makes the central distinction legible.",
                "caption": "The source diagram.",
                "alt_text": "A diagram from the source article.",
                "anchor": "__opener__",
                "layout": "evidence_band",
            }]
            manifest_path.write_text(
                yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
            )

            result = Magazine(root).build("issue-001")

            build_manifest = json.loads(
                (result.output_dir / "edition-manifest.json").read_text(encoding="utf-8")
            )
            placement = build_manifest["layout"]["figures"][0]
            self.assertEqual(placement["id"], "diagram")
            self.assertGreaterEqual(placement["effective_ppi"], 300)
            self.assertEqual(len(placement["box_points"]), 4)
            preflight = json.loads(
                (result.output_dir / "preflight.json").read_text(encoding="utf-8")
            )
            self.assertEqual(preflight["low_resolution_figures"], [])
            self.assertEqual(preflight["invalid_figure_boxes"], [])
            self.assertEqual(preflight["figure_collisions"], [])
            self.assertEqual(preflight["figures"][0]["caption"], "The source diagram.")

    def test_build_generates_configured_spanish_reader_and_booklet_alongside_english(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_project(root)
            add_spanish_translation(root)

            result = Magazine(root).build("issue-001")

            self.assertEqual([item.language for item in result.languages], ["en", "es"])
            spanish = result.output_dir / "es"
            self.assertTrue((spanish / "reader.pdf").is_file())
            self.assertTrue((spanish / "home" / "booklet-a4.pdf").is_file())
            self.assertTrue((spanish / "preflight.json").is_file())
            self.assertTrue((spanish / "edition-manifest.json").is_file())
            self.assertTrue((spanish / "SHA256SUMS").is_file())
            text = "\n".join(
                page.extract_text() or ""
                for page in PdfReader(str(spanish / "reader.pdf")).pages
            )
            self.assertIn("Índice", text)
            self.assertIn("EDITORIAL ORIGINAL", text)
            self.assertIn("ARTÍCULO 01", text)
            self.assertIn("EDICIÓN FIEL", text)
            self.assertIn("Author escribe sobre este tema para Example.", text)
            self.assertIn("El artículo original.", text)
            self.assertNotIn(" ".join(("PROHIBIDA", "SU", "VENTA")), text)
            self.assertNotIn(" ".join(("EDICIÓN", "PRIVADA")), text)
            spanish_preflight = json.loads((spanish / "preflight.json").read_text())
            self.assertIn(
                "No están configurados",
                spanish_preflight["studio"]["blockers"][0],
            )

    def test_bundled_publication_fonts_are_registered(self):
        _, metrics, _ = _reportlab()

        expected = {
            SANS,
            SANS_MEDIUM,
            SANS_SEMIBOLD,
            SANS_BOLD,
            SERIF,
            SERIF_ITALIC,
            SERIF_BOLD,
            SERIF_DISPLAY,
        }
        self.assertTrue(expected.issubset(set(metrics.getRegisteredFontNames())))

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

    def test_build_rejects_article_below_its_editorial_page_minimum(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_project(root)
            manifest_path = root / "editions" / "issue-001" / "edition.yaml"
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            manifest["articles"][0]["minimum_reader_pages"] = 2
            manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValidationError, "editorial minimum is 2"):
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
