"""Build integration for the reader engines.

WeasyPrint is the publication's default renderer, so :class:`DefaultEngineTests`
writes no ``[render] engine`` key at all and exercises exactly what ``mag build``
does out of the box.  ReportLab is no longer a rollback -- selecting it changes
the publication rather than restoring it -- but it is still a supported escape
hatch, so :class:`ReportLabRollbackTests` pins it explicitly and re-runs
:class:`ReaderEngineContract` -- the behaviour any reader engine has to keep --
plus the assertions that are about that renderer specifically.

Two things this file deliberately does *not* do.

It does not read a built page's *text* with ``pypdf``.  Poppler recovers word
boundaries from glyph geometry, which is what a PDF viewer, a text search and
``tools/compare_pipelines.py``'s G3 gate all do; ``pypdf`` reports the space
characters a producer chose to write, which is a fact about the encoding rather
than about the page (see :func:`page_texts`).  ``pypdf`` is still used for what
it reads faithfully: page count, font resources and content-stream operators.

It does not pin either engine's error strings.  A page cap is a rule of the
publication, so the refusals below are asserted as *the rule* -- the cap taken
from the engine's own constant, the offending article named, and nothing
published -- rather than as one renderer's wording.  The two engines phrase
these three refusals differently, which is a wart, not a fact worth freezing.
"""

import importlib.util
import json
import shutil
import subprocess
from contextlib import contextmanager
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
from magazine.render_engine import DEFAULT_ENGINE, reader_renderer
from test_manifest import add_spanish_translation, make_project


def page_texts(pdf: Path) -> list[str]:
    """Each page's text, with word boundaries recovered from glyph geometry.

    Poppler derives a word boundary from the glyph advance rather than from a
    written space, which is what a PDF viewer, a text search and
    ``tools/compare_pipelines.py``'s G3 gate all do.  Reading the page that way
    is what makes the same assertion mean the same thing under either engine,
    whose producers encode inter-word space differently -- ReportLab writes a
    whole line at a time, WeasyPrint one inline box at a time.  ``pdftoppm``
    from the same package is already a hard requirement of every build here
    (``render_critic``), so this adds no dependency.

    This used to be a workaround as well as a principle: the retired
    ``.reader-token { white-space: nowrap }`` shaping scaffold put one inline
    box around every whitespace token, and WeasyPrint emits no space glyph
    between two boxes, so ``pypdf`` read the prose back as
    ``Theoriginalarticle.``  That is fixed -- a built reader's text layer now
    carries real spaces, asserted in
    ``tests/test_weasyprint_adapter.py`` -- and ``pdftotext`` is kept here on
    the principle alone.
    """
    executable = shutil.which("pdftotext")
    if executable is None:  # pragma: no cover - poppler is a build requirement
        raise unittest.SkipTest("Reading a built reader requires Poppler's pdftotext")
    completed = subprocess.run(
        [executable, str(pdf), "-"], capture_output=True, text=True, check=True
    )
    pages = completed.stdout.split("\f")
    if pages and not pages[-1]:  # pdftotext ends the last page with a form feed too
        pages.pop()
    return pages


def reader_prose(pdf: Path) -> str:
    """The whole reader as one whitespace-normalised string.

    Line breaking is the one thing the two engines are *not* required to agree
    on beyond the frozen edition, so a phrase that fits one measure may wrap in
    the other.  Collapsing whitespace keeps ``assertIn`` an assertion about the
    words on the page rather than about where they happened to break.
    """
    return " ".join(" ".join(page_texts(pdf)).split())


def embedded_base_fonts(pages) -> set[str]:
    """Every ``/BaseFont`` named by the given pages' resources."""
    names: set[str] = set()
    for page in pages:
        resources = page.get("/Resources")
        fonts = (resources or {}).get("/Font") or {}
        if hasattr(fonts, "get_object"):
            fonts = fonts.get_object()
        for value in fonts.values():
            names.add(str(value.get_object().get("/BaseFont")))
    return names


class ReaderEngineContract:
    """What a reader engine must do, whichever engine the project selects.

    Subclassed once per engine below.  ``ENGINE`` is what the project's
    ``[render] engine`` key says; ``None`` writes no key, which is how a real
    project selects the shipped default.  ``MAX_*`` come from the engine's own
    constants so that each refusal is checked against the rule that engine is
    actually enforcing -- :class:`PublicationPageRuleTests` pins the two sets of
    constants to each other.
    """

    ENGINE: str | None = None
    MAX_ARTICLE_PAGES: int
    MAX_EDITORIAL_PAGES: int
    # What the engine calls its design in a packaged manifest.  ReportLab keeps
    # two names -- ``DESIGN_MONUMENT`` is the configuration key the dispatch
    # passes it, ``DESIGN_LABEL`` is what it records -- while WeasyPrint uses one
    # string for both.  This is the recorded one, from the engine's own module.
    DESIGN_DIRECTION: str

    def project(self, root: Path) -> None:
        make_project(root, engine=self.ENGINE)

    def renderer(self):
        return reader_renderer(self.ENGINE)

    def assert_build_refuses(self, root: Path, *expected: str) -> None:
        """The build stops with a ``ValidationError`` and publishes no reader.

        ``expected`` are the facts the message has to carry -- the rule's number,
        the offending item -- never one engine's phrasing of them.  Refusing is
        only half of it: an edition that broke a hard rule must also leave no
        packaged reader behind for someone to pick up and print.
        """
        with self.assertRaises(ValidationError) as raised:
            Magazine(root).build("issue-001")
        message = str(raised.exception)
        for fragment in expected:
            self.assertRegex(message, fragment)
        self.assertFalse(
            (root / "output" / "issue-001" / "reader.pdf").exists(),
            "a refused build must not publish a reader",
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
            self.project(tmp_path)
            tail_art = tmp_path / "editions" / "issue-001" / "art" / "tail.png"
            Image.new("RGB", (1536, 1024), "white").save(tail_art)
            manifest_path = tmp_path / "editions" / "issue-001" / "edition.yaml"
            manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            manifest_data["articles"][0]["tail_art_path"] = (
                tail_art.relative_to(tmp_path).as_posix()
            )
            manifest_path.write_text(
                yaml.safe_dump(manifest_data, sort_keys=False),
                encoding="utf-8",
            )
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
            cover_raster = Image.open(
                result.output_dir / "render-review" / "reader-pages" / "page-001.png"
            ).convert("RGB")
            expected_orange = (240, 87, 56)
            self.assertTrue(
                all(
                    all(channel >= 253 for channel in pixel)
                    for pixel in (cover_raster.getpixel((cover_raster.width - 1, y)) for y in range(cover_raster.height))
                ),
                "the tab's paper reveal must own the outermost trim pixel for the full page height",
            )
            self.assertTrue(
                all(
                    max(abs(channel - expected) for channel, expected in zip(pixel, expected_orange)) <= 2
                    for pixel in (
                        cover_raster.getpixel((cover_raster.width - 8, y))
                        for y in range(cover_raster.height)
                    )
                ),
                "the orange band must run unbroken from the head trim to the foot trim",
            )
            tab_pixels = round(21 * 2)
            tab = cover_raster.crop((cover_raster.width - tab_pixels, 0, cover_raster.width, cover_raster.height))
            for label, vertical_slice in (
                ("issue", (0, cover_raster.height // 3)),
                ("identity", (cover_raster.height * 2 // 3, cover_raster.height)),
            ):
                top, bottom = vertical_slice
                ink = Image.eval(
                    tab.crop((0, top, tab.width, bottom)).convert("L"),
                    lambda value: 255 if value < 80 else 0,
                )
                bbox = ink.getbbox()
                self.assertIsNotNone(bbox, f"missing {label} text in the orange tab")
                assert bbox is not None
                text_center = (bbox[0] + bbox[2]) / 2
                self.assertLessEqual(
                    abs(text_center - tab.width / 2),
                    2,
                    f"{label} text must be optically centered in the orange tab",
                )
            # The package inventory, stated in full.  A checksum list is a
            # claim about what a release contains, so an artifact silently
            # appearing or disappearing from it is exactly the change worth
            # failing on -- ``fidelity.md`` left this list when the ledger was
            # deleted, and nothing was asserting that either way.  The contact
            # sheets are excluded because how many the critic renders is a
            # function of the page count, not of the package's shape.
            inventory = {
                line.split("  ", 1)[1]
                for line in (result.output_dir / "SHA256SUMS").read_text().splitlines()
            }
            self.assertEqual(
                {name for name in inventory if not name.startswith("render-review/")},
                {
                    "edition-manifest.json",
                    "home/booklet-a4-cover.pdf",
                    "home/booklet-a4-interior.pdf",
                    "home/booklet-a4.pdf",
                    "home/printing-instructions.md",
                    "preflight.json",
                    "reader.pdf",
                    "render-critic.json",
                    "studio/README.md",
                },
            )
            pages = page_texts(result.reader_pdf)
            self.assertGreaterEqual(len(PdfReader(str(result.reader_pdf)).pages), 8)
            self.assertEqual(len(pages), len(PdfReader(str(result.reader_pdf)).pages))
            self.assertEqual(pages[1].strip(), "")
            self.assertEqual(pages[-2].strip(), "")
            contents_lines = [line.strip() for line in pages[2].splitlines()]
            self.assertNotIn("01", contents_lines, "contents must not repeat the issue in a medallion")
            preflight = json.loads((result.output_dir / "preflight.json").read_text())
            self.assertTrue(preflight["reader"]["page_count_multiple_of_four"])
            self.assertTrue(preflight["reader"]["all_pages_a5"])
            self.assertTrue(preflight["home_booklet"]["all_pages_a4_landscape"])
            self.assertEqual(preflight["result"], "home_ready_studio_blocked")
            manifest = json.loads((result.output_dir / "edition-manifest.json").read_text())
            self.assertEqual(manifest["publication"]["name"], "Test Review")
            self.assertEqual(manifest["inputs"]["sources"][0]["id"], "source-one")
            self.assertEqual(len(manifest["inputs"]["sources"][0]["raw_captures"]), 1)
            self.assertEqual(
                manifest["inputs"]["articles"][0]["tail_art"]["path"],
                "editions/issue-001/art/tail.png",
            )
            self.assertNotIn(
                "opener_art",
                manifest["inputs"]["articles"][0],
                "legacy package manifests must retain their historical shape",
            )
            # The fidelity ledger is gone, so the manifest no longer claims a
            # per-article ledger file or an edition-wide fidelity status.  A
            # package that still named them would be pointing at files nothing
            # writes.
            self.assertNotIn("fidelity", manifest["inputs"]["articles"][0])
            self.assertNotIn("fidelity_status", manifest["inputs"])
            self.assertEqual(manifest["layout"]["maximum_article_pages"], self.MAX_ARTICLE_PAGES)
            self.assertLessEqual(
                manifest["layout"]["article_pages"]["article"], self.MAX_ARTICLE_PAGES
            )
            self.assertEqual(manifest["layout"]["maximum_editorial_pages"], self.MAX_EDITORIAL_PAGES)
            self.assertEqual(manifest["layout"]["editorial_pages"], 1)
            # The packaged artifact has to say which renderer set it, and admit
            # to any typography the renderer is holding down to match the other.
            # Both come from the renderer's own identity, never from a literal.
            renderer = self.renderer()
            self.assertEqual(manifest["layout"]["design_direction"], self.DESIGN_DIRECTION)
            self.assertEqual(
                manifest["layout"].get("shaping_scaffolds"),
                list(renderer.shaping_scaffolds) or None,
            )
            reader_text = reader_prose(result.reader_pdf)
            self.assertIn("A Test Editorial", reader_text)
            self.assertIn("AN ORIGINAL ARGUMENT", reader_text)
            self.assertIn("FEATURE 01", reader_text)
            self.assertIn("FAITHFUL EDIT", reader_text)
            self.assertIn("Author is chief architect at Example Company.", reader_text)
            self.assertIn("TEST REVIEW", reader_text)
            self.assertNotIn(" ".join(("NOT", "FOR", "SALE")), reader_text)
            self.assertNotIn(" ".join(("PRIVATE", "EDITION")), reader_text)
            self.assert_tracked_labels_do_not_leak_character_spacing(result.reader_pdf)

    def test_build_generates_configured_spanish_reader_and_booklet_alongside_english(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.project(root)
            add_spanish_translation(root, engine=self.ENGINE)

            result = Magazine(root).build("issue-001")

            self.assertEqual([item.language for item in result.languages], ["en", "es"])
            spanish = result.output_dir / "es"
            self.assertTrue((spanish / "reader.pdf").is_file())
            self.assertTrue((spanish / "home" / "booklet-a4.pdf").is_file())
            self.assertTrue((spanish / "preflight.json").is_file())
            self.assertTrue((spanish / "edition-manifest.json").is_file())
            self.assertTrue((spanish / "SHA256SUMS").is_file())
            text = reader_prose(spanish / "reader.pdf")
            self.assertIn("Índice", text)
            self.assertIn("EDITORIAL ORIGINAL", text)
            self.assertIn("ARTÍCULO 01", text)
            self.assertIn("EDICIÓN FIEL", text)
            self.assertIn("Author es responsable de arquitectura en Example Company.", text)
            self.assertIn("El artículo original.", text)
            self.assertNotIn(" ".join(("PROHIBIDA", "SU", "VENTA")), text)
            self.assertNotIn(" ".join(("EDICIÓN", "PRIVADA")), text)
            spanish_preflight = json.loads((spanish / "preflight.json").read_text())
            self.assertIn(
                "No están configurados",
                spanish_preflight["studio"]["blockers"][0],
            )

    def test_build_rejects_article_over_the_hard_article_page_cap(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.project(root)
            edition_dir = root / "editions" / "issue-001"
            paragraphs = [f"Substantive source paragraph {index} with enough words to occupy space." for index in range(420)]
            (edition_dir / "articles" / "article.md").write_text(
                "\n\n".join(paragraphs) + "\n", encoding="utf-8"
            )

            self.assert_build_refuses(
                root, r"\barticle\b", rf"(?<!\d){self.MAX_ARTICLE_PAGES}(?!\d)"
            )

    def test_edition_cannot_raise_the_hard_article_page_cap(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.project(root)
            manifest_path = root / "editions" / "issue-001" / "edition.yaml"
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            manifest["format"] = {"max_article_pages": self.MAX_ARTICLE_PAGES + 1}
            manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

            self.assert_build_refuses(root, "hard publication rule")

    def test_build_rejects_article_below_its_editorial_page_minimum(self):
        # minimum_reader_pages is an editorial floor declared per article and
        # carried through translation, so it binds whichever engine sets the
        # page.  WeasyPrint did not enforce it until this suite covered it.
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.project(root)
            manifest_path = root / "editions" / "issue-001" / "edition.yaml"
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            manifest["articles"][0]["minimum_reader_pages"] = 2
            manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

            self.assert_build_refuses(root, r"\barticle\b", "(?i)minimum", r"(?<!\d)2(?!\d)")

    def test_build_rejects_editorial_over_the_hard_editorial_page_cap(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.project(root)
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

            self.assert_build_refuses(
                root, "(?i)editorial", rf"(?<!\d){self.MAX_EDITORIAL_PAGES}(?!\d)"
            )

    def test_edition_cannot_raise_the_hard_editorial_page_cap(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.project(root)
            manifest_path = root / "editions" / "issue-001" / "edition.yaml"
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            manifest["format"] = {"max_editorial_pages": self.MAX_EDITORIAL_PAGES + 1}
            manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

            self.assert_build_refuses(root, "hard publication rule")


@unittest.skipUnless(
    importlib.util.find_spec("weasyprint") is not None, "WeasyPrint not installed in this runtime"
)
class DefaultEngineTests(ReaderEngineContract, unittest.TestCase):
    """The engine a project gets when it says nothing: WeasyPrint.

    ``ENGINE = None`` is the point of this class -- the fixture writes no
    ``[render]`` table, so an accidental change to ``DEFAULT_ENGINE`` moves this
    whole class onto the other renderer rather than passing silently.
    """

    from magazine.weasyprint_adapter import (  # noqa: PLC0415 - engine's own rule
        WEASYPRINT_DESIGN as DESIGN_DIRECTION,
        _MAX_ARTICLE_PAGES as MAX_ARTICLE_PAGES,
        _MAX_EDITORIAL_PAGES as MAX_EDITORIAL_PAGES,
    )

    ENGINE = None

    def test_the_default_is_the_engine_this_class_believes_it_is_testing(self):
        self.assertEqual(DEFAULT_ENGINE, "weasyprint")
        self.assertEqual(self.renderer().engine, "weasyprint")

    def test_signature_padding_uses_distinct_configured_codas_once_each(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.project(root)
            edition_dir = root / "editions" / "issue-001"
            paragraphs = [
                f"Substantive source paragraph {index} with enough words to occupy space."
                for index in range(130)
            ]
            (edition_dir / "articles" / "article.md").write_text(
                "\n\n".join(paragraphs) + "\n", encoding="utf-8"
            )
            manifest_path = edition_dir / "edition.yaml"
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            manifest["format"] = {"target_pages": 16}
            manifest_path.write_text(
                yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
            )

            result = Magazine(root).build("issue-001")

            page_text = page_texts(result.reader_pdf)
            full_text = " ".join(" ".join(page_text).split())
            self.assertEqual(len(page_text), 16)
            self.assertEqual(full_text.count("Coda 1"), 1)
            self.assertEqual(full_text.count("Coda 2"), 1)
            self.assertEqual(full_text.count("Coda 3"), 1)
            self.assertNotIn("Closing plate", full_text)
            self.assertEqual(page_text[-2].strip(), "")

    def test_build_places_a_curated_opener_figure_and_audits_its_print_geometry(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.project(root)
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

    def test_reader_sets_every_page_in_the_bundled_publication_faces(self):
        """No page may fall back to a host font.

        WeasyPrint installs ``@font-face`` only for the font configuration it is
        also laid out with; miss that and Pango silently sets the whole reader in
        whatever fontconfig prefers, at the wrong measure.  The bundled faces are
        embedded as ``Magazine-*`` subsets, and the spliced cover is the one page
        that is not this renderer's work.
        """
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.project(root)

            result = Magazine(root).build("issue-001")

            # Pages 1-2 and the last two are the spliced cover and its blank
            # inside faces; everything between them is this renderer's own work.
            interior = PdfReader(str(result.reader_pdf)).pages[2:-2]
            fonts = embedded_base_fonts(interior)

            self.assertTrue(interior and fonts, "the reader embedded no fonts at all")
            self.assertEqual(
                {font for font in fonts if "+Magazine-" not in font},
                set(),
                f"a reader page fell back to a host font: {sorted(fonts)}",
            )

    def test_an_edition_of_sections_alone_still_builds_a_whole_package(self):
        """An edition with no editorial and no articles is still an edition.

        This case used to be asserted through ``output/<ed>/fidelity.md``: with
        no article ledgers to summarise, the compiler fell back to reporting
        the edition-wide ``fidelity/source-edition-status.yaml``, and the test
        read that report back.  Both the report and the status file are gone
        with the ledger, so those assertions are gone with them -- but the
        build path they happened to exercise is not covered anywhere else, and
        "the article loop is empty" is precisely the shape that breaks when the
        loop is rewritten.  So the fixture stays and the claim moves to what a
        reader can check: the section prints, and the package is complete.
        """
        with TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            self.project(tmp_path)
            edition_dir = tmp_path / "editions" / "issue-001"
            (edition_dir / "section.md").write_text("A source-safe section.", encoding="utf-8")
            manifest_path = edition_dir / "edition.yaml"
            manifest = yaml.safe_load(manifest_path.read_text())
            manifest.pop("editorial")
            manifest.pop("articles")
            manifest["sources"] = ["source-one"]
            manifest["sections"] = [{"kind": "production_note", "title": "Status", "path": "section.md"}]
            manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

            result = Magazine(tmp_path).build("issue-001")

            self.assertIn("A source-safe section.", reader_prose(result.reader_pdf))
            self.assertTrue(result.booklet_pdf.is_file())
            self.assertTrue((result.output_dir / "SHA256SUMS").is_file())
            build_manifest = json.loads(
                (result.output_dir / "edition-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(build_manifest["inputs"]["articles"], [])
            self.assertEqual(
                [row["kind"] for row in build_manifest["inputs"]["sections"]],
                ["production_note"],
            )

    def test_articles_edition_can_append_backmatter_sections(self):
        with TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            self.project(tmp_path)
            edition_dir = tmp_path / "editions" / "issue-001"
            (edition_dir / "production-note.md").write_text(
                "# Production note\n\nMade with care.",
                encoding="utf-8",
            )
            manifest_path = edition_dir / "edition.yaml"
            manifest = yaml.safe_load(manifest_path.read_text())
            manifest["sections"] = [
                {
                    "kind": "production_note",
                    "title": "Production note",
                    "path": "production-note.md",
                }
            ]
            manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

            result = Magazine(tmp_path).build("issue-001")

            text = reader_prose(result.reader_pdf)
            self.assertIn("The original article.", text)
            self.assertIn("Made with care.", text)

    def test_colophon_sections_are_rejected(self):
        with TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            self.project(tmp_path)
            edition_dir = tmp_path / "editions" / "issue-001"
            (edition_dir / "legacy.md").write_text("Legacy colophon.", encoding="utf-8")
            manifest_path = edition_dir / "edition.yaml"
            manifest = yaml.safe_load(manifest_path.read_text())
            manifest["sections"] = [
                {"kind": "COLOPHON", "title": "Colophon", "path": "legacy.md"}
            ]
            manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

            with self.assertRaisesRegex(ValidationError, "Colophon sections are no longer supported"):
                Magazine(tmp_path).build("issue-001")

    def test_fenced_code_is_monospaced_line_preserving_and_safely_paginated(self):
        with TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            self.project(tmp_path)
            edition_dir = tmp_path / "editions" / "issue-001"
            code = "\n".join(f"    call_{index:03d}();" for index in range(120))
            (edition_dir / "articles" / "article.md").write_text(
                f"Before code.\n\n```java\n{code}\n```\n\nAfter code.\n",
                encoding="utf-8",
            )

            result = Magazine(tmp_path).build("issue-001")

            pages = page_texts(result.reader_pdf)
            self.assertGreaterEqual(len(pages), 8)
            # Every source line survives as its own printed line, in order, with
            # none dropped at the three page breaks the fence spans.  That is
            # what "line preserving" and "safely paginated" mean for a code
            # block, and it is what re-flowing the fence would destroy.  The
            # leading whitespace is deliberately not asserted here: extraction
            # reports a line's column on the page, not the indent in the source.
            printed = [line.strip() for page in pages for line in page.splitlines()]
            expected = [f"call_{index:03d}();" for index in range(120)]
            self.assertEqual([line for line in printed if "call_" in line], expected)
            self.assertIn("After code.", reader_prose(result.reader_pdf))


@unittest.skipUnless(
    importlib.util.find_spec("reportlab") is not None, "ReportLab not installed in this runtime"
)
class ReportLabRollbackTests(ReaderEngineContract, unittest.TestCase):
    """The rollback engine, pinned explicitly, on the same contract.

    This is the minority set on purpose: ``engine = "reportlab"`` is a supported
    escape hatch that has to keep packaging a complete edition and keep refusing
    the same manuscripts, but the publication is not developed against it.
    """

    from magazine.render import (  # noqa: PLC0415 - engine's own rule
        DESIGN_LABEL as DESIGN_DIRECTION,
        MAX_ARTICLE_PAGES,
        MAX_EDITORIAL_PAGES,
    )

    ENGINE = "reportlab"

    def test_the_rollback_is_not_silently_the_default(self):
        self.assertNotEqual(DEFAULT_ENGINE, self.ENGINE)
        self.assertEqual(self.renderer().engine, self.ENGINE)

    def test_bundled_publication_fonts_are_registered(self):
        # The WeasyPrint counterpart of this -- that a built reader embeds only
        # the bundled Magazine-* subsets -- is
        # DefaultEngineTests.test_reader_sets_every_page_in_the_bundled_publication_faces.
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


@contextmanager
def declared_scaffolds(scaffolds: tuple[str, ...]):
    """Build against the selected renderer, altered only in what it declares.

    The renderer is the real one -- same engine, same design, same
    ``write_reader`` -- so the build under test is the shipped build and the one
    thing that differs is the tuple whose plumbing is being exercised.
    """
    from magazine import compiler as compiler_module

    original = compiler_module.reader_renderer

    def declaring(configured=None, *, design=None):
        return replace(original(configured, design=design), shaping_scaffolds=scaffolds)

    compiler_module.reader_renderer = declaring
    try:
        yield
    finally:
        compiler_module.reader_renderer = original


class ShapingScaffoldDeclarationTests(unittest.TestCase):
    """That a declared scaffold reaches the packaged manifest, on a renderer that has one.

    ``SHAPING_SCAFFOLDS`` is ``()`` on WeasyPrint and ``()`` on ReportLab, so
    :class:`ReaderEngineContract`'s own clause -- ``manifest["layout"].get(
    "shaping_scaffolds") == list(renderer.shaping_scaffolds) or None`` -- reduces
    to ``assertEqual(None, None)`` under both engines and would keep passing if
    the compiler stopped writing the key at all.  The empty tuple is still worth
    asserting, because "this renderer holds nothing down" is the claim the
    artifact makes; but the mechanism behind it is only exercised by a renderer
    that declares something, which no engine currently does.  So one is
    synthesised here, and the empty case is run through the same assertion so
    that the two answers are distinguished by the input rather than by luck.
    """

    SCAFFOLDS = ("font-kerning: none", ".reader-token { white-space: nowrap }")

    def test_only_a_declaring_renderer_writes_shaping_scaffolds(self):
        for scaffolds in ((), self.SCAFFOLDS):
            with self.subTest(scaffolds=scaffolds), TemporaryDirectory() as temporary:
                root = Path(temporary)
                make_project(root)
                with declared_scaffolds(scaffolds):
                    result = Magazine(root).build("issue-001")
                manifest = json.loads(
                    (result.output_dir / "edition-manifest.json").read_text()
                )

                self.assertEqual(
                    manifest["layout"].get("shaping_scaffolds"), list(scaffolds) or None
                )

    def test_no_shipped_engine_declares_a_scaffold(self):
        """The empty tuples the contract clause above is asserted against."""
        for engine in ("weasyprint", "reportlab"):
            with self.subTest(engine=engine):
                self.assertEqual(reader_renderer(engine).shaping_scaffolds, ())


class PublicationPageRuleTests(unittest.TestCase):
    """The page caps are the publication's, so both engines must hold the same ones.

    Each engine keeps its own constant (``render.MAX_ARTICLE_PAGES`` and
    ``weasyprint_adapter._MAX_ARTICLE_PAGES``) and the classes above assert each
    refusal against the engine's own.  That is only sound while the two agree,
    which is what this pins -- a cap raised on one engine alone is a rollback
    that changes what the publication accepts.
    """

    def test_both_engines_enforce_the_same_page_caps(self):
        from magazine import render, weasyprint_adapter

        self.assertEqual(render.MAX_ARTICLE_PAGES, weasyprint_adapter._MAX_ARTICLE_PAGES)
        self.assertEqual(render.MAX_EDITORIAL_PAGES, weasyprint_adapter._MAX_EDITORIAL_PAGES)
        self.assertEqual(render.MAX_ARTICLE_PAGES, 7)
        self.assertEqual(render.MAX_EDITORIAL_PAGES, 2)
