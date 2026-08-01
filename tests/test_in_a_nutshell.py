"""The "In a Nutshell" bundle: the explainer, its furniture, and its budget.

The section ships as four separable pieces of vocabulary, and this file holds
each of them to the same standard -- that it survives every path an edition
takes, in both languages, not merely that the loader accepts it:

* ``content_mode: in_a_nutshell``, the marker that *identifies* the explainer.
  Nothing else names it: a judge, a reviewer or a renderer asks the article row
  what kind of piece it is and gets an answer, so there is no ``explainer:``
  field and no title-sniffing anywhere.
* ``glossary``, ``try_it`` and ``cheat_sheet``, three new kinds on the section
  mechanism the edition already had.
* ``key_ideas``, the explainer's closing box, budgeted in words before layout
  and mutually exclusive with tail art.

The end-to-end test is the load-bearing one.  Everything else here could pass
against a manifest loader that no renderer agrees with; only a real build
proves the bundle prints.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

import yaml

from magazine import Magazine, ValidationError
from magazine.article_stage import ArticleBrief, stage_article
from magazine.html_edition import render_html_edition
from magazine.manifest import (
    CONTENT_MODES,
    EDITOR_VOICE_CONTENT_MODES,
    KEY_IDEAS_WORD_BUDGET,
    SECTION_KINDS,
    load_translation,
)
from magazine.render import UI_COPY, _content_mode_label, _section_label
from magazine.translate_stage import stage_translation

from test_article_stage import _add_source as add_staging_source
from test_article_stage import _make_project as make_staging_project
from test_manifest import add_source, load_edition_with_records, make_project


_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "edition.schema.json"

# The explainer teaches one running example and never walks a specification's
# table of contents, so its headings state ideas.  They are also exactly what
# `edition.yaml`'s figure anchors are matched against, which is why the key
# ideas box below is emitted as a labelled paragraph and not as a heading.
NUTSHELL_MANUSCRIPT = """The team had one connector per tool, and eleven of them to keep alive.

## Why one connector per tool did not scale

Every new tool meant a new adapter, and every adapter meant a new way to
break. The team maintained eleven of them, and each release was eleven
regression suites nobody owned.

## What putting the boundary in one place buys you

Move the boundary and the host stops caring which tool answers. The host owns
the decision about when to act; the server owns the list of what can be done at
all. Neither has to know the other's release schedule.
"""

GLOSSARY = """The terms this issue uses, once each, in the order a reader meets them.

- Host: the application the reader is actually using.
- Server: the program that states what it can do.
"""

TRY_IT = """Fifteen minutes, one terminal, nothing to install beyond the runtime.

1. Create a directory and change into it.
2. Write a two-line configuration file naming one server.
3. Start the host and ask it which tools it now has.
"""

CHEAT_SHEET = """One page, three rules, no prose.

- The host decides when.
- The server decides what.
- Neither owns the other's release schedule.
"""

KEY_IDEAS = [
    "One host can drive several servers without merging them.",
    "A server states what it can do; the host decides when to do it.",
    "Neither side needs to know when the other ships a release.",
]


def make_bundle(root: Path, *, engine: str | None = None) -> None:
    """A validated edition carrying a whole In a Nutshell bundle.

    One ordinary article so the edition is not all explainer, the explainer
    itself with its key ideas, and the three auxiliary sections in the order
    they are read: the exercise straight after the piece, then the back matter.
    """

    make_project(root, engine=engine)
    add_source(root, "source-two", body="A specification.\n")
    edition_dir = root / "editions" / "issue-001"
    (edition_dir / "articles" / "mcp-in-a-nutshell.md").write_text(
        NUTSHELL_MANUSCRIPT, encoding="utf-8"
    )
    for name, text in (
        ("try-it.md", TRY_IT),
        ("glossary.md", GLOSSARY),
        ("cheat-sheet.md", CHEAT_SHEET),
    ):
        (edition_dir / name).write_text(text, encoding="utf-8")
    manifest_path = edition_dir / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["sources"] = ["source-one", "source-two"]
    manifest["articles"].append(
        {
            "id": "mcp-in-a-nutshell",
            "title": "MCP in a Nutshell",
            "short_title": "MCP in a Nutshell",
            "display_emphasis": "MCP",
            "opener_variant": "split_axis",
            # The Teacher writes in the magazine's voice, so the byline is the
            # editors' and there is no author biography to carry.
            "author": "The editors",
            "content_mode": "in_a_nutshell",
            "source_ids": ["source-two"],
            "manuscript": "editions/issue-001/articles/mcp-in-a-nutshell.md",
            "key_ideas": list(KEY_IDEAS),
        }
    )
    manifest["sections"] = [
        {"kind": "try_it", "title": "Try It in Fifteen Minutes", "path": "try-it.md"},
        {"kind": "glossary", "title": "Glossary", "path": "glossary.md"},
        {"kind": "cheat_sheet", "title": "Cheat Sheet", "path": "cheat-sheet.md"},
    ]
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def set_nutshell_row(root: Path, **changes: object) -> None:
    """Apply ``changes`` to the explainer's row in ``edition.yaml``."""

    manifest_path = root / "editions" / "issue-001" / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    row = next(row for row in manifest["articles"] if row["id"] == "mcp-in-a-nutshell")
    for key, value in changes.items():
        if value is None:
            row.pop(key, None)
        else:
            row[key] = value
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def reader_prose(pdf: Path) -> str:
    """The whole reader as one whitespace-normalised string."""

    executable = shutil.which("pdftotext")
    if executable is None:  # pragma: no cover - poppler is a build requirement
        raise unittest.SkipTest("Reading a built reader requires Poppler's pdftotext")
    completed = subprocess.run(
        [executable, str(pdf), "-"], capture_output=True, text=True, check=True
    )
    return " ".join(completed.stdout.split())


class BundleBuildTests(unittest.TestCase):
    """The bundle end to end, on the engine a real ``mag build`` selects."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_a_whole_bundle_builds_and_prints_every_piece_of_it(self):
        """The explainer, its key ideas, and all three sections reach the page.

        No engine is named, so this is exactly what ``mag build`` does out of
        the box.  The assertions are on printed words rather than on internal
        state: a bundle that validates but does not print is not shipped.
        """
        make_bundle(self.root)

        result = Magazine(self.root).build("issue-001")

        printed = reader_prose(result.reader_pdf)
        self.assertIn("IN A NUTSHELL", printed)
        self.assertIn("KEY IDEAS", printed)
        for idea in KEY_IDEAS:
            self.assertIn(idea, printed)
        for label in ("TRY IT", "GLOSSARY", "CHEAT SHEET"):
            self.assertIn(label, printed)
        self.assertIn("Fifteen minutes, one terminal", printed)
        self.assertIn("Host: the application the reader is actually using.", printed)
        self.assertIn("The host decides when.", printed)
        build_manifest = json.loads(
            (result.output_dir / "edition-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            [row["kind"] for row in build_manifest["inputs"]["sections"]],
            ["try_it", "glossary", "cheat_sheet"],
        )

    def test_the_reportlab_escape_hatch_still_prints_the_whole_bundle(self):
        """New vocabulary may not be default-engine-only.

        ReportLab is no longer a rollback, but it is still the escape hatch if
        the HTML path ever cannot build an edition at all -- which is worth
        nothing if the escape hatch cannot set the new furniture.
        """
        make_bundle(self.root, engine="reportlab")

        result = Magazine(self.root).build("issue-001")

        printed = reader_prose(result.reader_pdf)
        self.assertIn("IN A NUTSHELL", printed)
        self.assertIn("KEY IDEAS", printed)
        self.assertIn(KEY_IDEAS[0], printed)
        for label in ("TRY IT", "GLOSSARY", "CHEAT SHEET"):
            self.assertIn(label, printed)


class SemanticEditionTests(unittest.TestCase):
    """What the mode and the new kinds look like in the semantic HTML."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_bundle(self.root)
        self.edition = load_edition_with_records(self.root)

    def test_the_mode_round_trips_from_manifest_to_html_as_its_own_label(self):
        explainer = self.edition.articles[1]
        self.assertEqual(explainer.content_mode, "in_a_nutshell")
        self.assertEqual(explainer.key_ideas, tuple(KEY_IDEAS))
        self.assertEqual(explainer.author, "The editors")
        self.assertEqual(explainer.author_note, "")

        html = render_html_edition(self.edition).html

        self.assertIn('data-content-mode="in_a_nutshell"', html)
        self.assertIn(
            '<span class="label-secondary">IN A NUTSHELL</span>', html
        )
        self.assertEqual(_content_mode_label(self.edition, "in_a_nutshell"), "In a nutshell")

    def test_the_key_ideas_box_is_labelled_furniture_and_not_a_heading(self):
        """A heading here would enter the article's own heading sequence.

        Figure anchors are matched against article headings and a duplicate or
        an unmatched anchor is a hard validation failure, so the box states its
        name in a labelled paragraph -- the same way every other kicker in the
        publication does.
        """
        html = render_html_edition(self.edition).html

        self.assertIn('<aside class="key-ideas" data-key-ideas="3"', html)
        self.assertIn('<p class="key-ideas-label">KEY IDEAS</p>', html)
        for idea in KEY_IDEAS:
            self.assertIn(f"<li>{idea}</li>", html)
        # The box closes the article: it stands before the end mark, inside the
        # article element, and nothing follows it but the sign-off.
        article = html.split('data-article-id="mcp-in-a-nutshell"', 1)[1]
        self.assertLess(article.index("key-ideas"), article.index("end-mark"))
        self.assertNotIn("<h1", article.split("key-ideas", 1)[1].split("</article>", 1)[0])

    def test_each_new_section_kind_renders_with_its_own_kicker(self):
        html = render_html_edition(self.edition).html

        for kind, label in (
            ("try_it", "TRY IT"),
            ("glossary", "GLOSSARY"),
            ("cheat_sheet", "CHEAT SHEET"),
        ):
            self.assertIn(f'data-section-kind="{kind}"', html)
            self.assertIn(f'<span class="label-primary">{label}</span>', html)
            self.assertEqual(_section_label(self.edition, kind), label)
        self.assertIn("Fifteen minutes, one terminal", html)
        self.assertIn("The host decides when.", html)

    def test_the_spanish_edition_names_the_mode_the_kinds_and_the_box(self):
        """Castellano labels, in the register the existing ES labels use."""
        spanish = replace(self.edition, language="es", locale="es-AR")

        html = render_html_edition(spanish).html

        self.assertIn(
            '<span class="label-secondary">EN POCAS PALABRAS</span>', html
        )
        self.assertIn('<p class="key-ideas-label">IDEAS CLAVE</p>', html)
        for label in ("PRUÉBALO", "GLOSARIO", "HOJA DE REFERENCIA"):
            self.assertIn(f'<span class="label-primary">{label}</span>', html)
        self.assertEqual(_content_mode_label(spanish, "in_a_nutshell"), "En pocas palabras")
        self.assertEqual(_section_label(spanish, "cheat_sheet"), "HOJA DE REFERENCIA")

    def test_an_article_that_closes_on_key_ideas_emits_no_tail_ornament(self):
        html = render_html_edition(self.edition).html

        explainer = html.split('data-article-id="mcp-in-a-nutshell"', 1)[1]
        self.assertNotIn("article-tail", explainer.split("</article>", 1)[0])


class RegistryTests(unittest.TestCase):
    """One registry per concept, and everything that reads it agreeing."""

    def test_every_known_section_kind_has_a_label_in_both_renderers(self):
        """Adding a kind means adding its four labels, and this is what says so.

        The HTML renderer falls back to a shouted kind name rather than
        raising, so an unauthored kind would pass a "produces something" check
        in silence.  What is asserted instead is that each label was
        *authored*: present in ReportLab's map, and -- in Spanish, where the
        fallback is always wrong -- different from the mechanical fallback in
        both renderers.

        The two maps are deliberately not required to agree.  ``_ui`` is keyed
        by one namespace for two vocabularies, so ``original_synthesis`` is a
        content mode to the HTML renderer ("ORIGINAL SYNTHESIS") and a section
        kind to ReportLab ("READING MAP"); that collision predates the new
        kinds and is not this test's to freeze either way.
        """
        from magazine.html_edition import _ui as html_ui

        spanish = _label_probe("es")
        for kind in SECTION_KINDS:
            with self.subTest(kind):
                fallback = kind.replace("_", " ").upper()
                for language in ("en", "es"):
                    self.assertIn(kind, UI_COPY[language], f"render.py has no {kind}")
                self.assertNotEqual(UI_COPY["es"][kind], fallback)
                self.assertNotEqual(html_ui(spanish, kind), fallback)

    def test_every_content_mode_has_a_label_and_a_defined_voice(self):
        edition = _label_probe("en")
        spanish = _label_probe("es")
        for mode in CONTENT_MODES:
            self.assertTrue(_content_mode_label(edition, mode))
            self.assertTrue(_content_mode_label(spanish, mode))
        self.assertIn("in_a_nutshell", CONTENT_MODES)
        self.assertIn("in_a_nutshell", EDITOR_VOICE_CONTENT_MODES)
        self.assertNotIn("faithful_synthesis", EDITOR_VOICE_CONTENT_MODES)

    def test_the_json_schema_declares_the_registries_the_loader_enforces(self):
        """The published schema is not allowed to drift from the loader.

        It is documentation with no runtime reader, which is exactly why it
        needs a test: the only thing that can keep it honest is an assertion
        that its enumerations are the code's own.
        """
        schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
        properties = schema["properties"]
        articles = properties["articles"]["items"]

        self.assertEqual(
            properties["sections"]["items"]["properties"]["kind"]["enum"],
            list(SECTION_KINDS),
        )
        self.assertEqual(
            set(articles["properties"]["content_mode"]["enum"]), set(CONTENT_MODES)
        )
        # An edition is either editorial-plus-articles or sections-only, which
        # is the loader's own rule and used to be spelled here as "articles are
        # always required".
        self.assertNotIn("articles", schema["required"])
        self.assertNotIn("editorial", schema["required"])
        self.assertEqual(
            [sorted(branch["required"]) for branch in schema["anyOf"]],
            [["articles", "editorial"], ["sections"]],
        )
        # One closing object per article, stated as a schema refusal too.
        self.assertEqual(sorted(articles["not"]["required"]), ["key_ideas", "tail_art_path"])
        self.assertEqual(articles["properties"]["key_ideas"]["minItems"], 1)


class KeyIdeasValidationTests(unittest.TestCase):
    """The budget and the one-closing-object rule, refused before layout."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_bundle(self.root)

    def validate(self):
        return Magazine(self.root).validate("issue-001")

    def test_the_word_budget_is_counted_across_the_whole_box(self):
        """The box is one closing object and is measured as one.

        Each line here is comfortably short; together they are not, which is
        the failure a per-line limit would let through.
        """
        over_budget = [f"Claim number {index} about the boundary and its parts." for index in range(12)]
        self.assertGreater(sum(len(line.split()) for line in over_budget), KEY_IDEAS_WORD_BUDGET)
        set_nutshell_row(self.root, key_ideas=over_budget)

        with self.assertRaises(ValidationError) as raised:
            self.validate()

        self.assertIn("key_ideas run to", str(raised.exception))
        self.assertIn(str(KEY_IDEAS_WORD_BUDGET), str(raised.exception))

    def test_a_box_exactly_on_the_budget_is_accepted(self):
        exact = [" ".join(["word"] * KEY_IDEAS_WORD_BUDGET)]
        set_nutshell_row(self.root, key_ideas=exact)

        self.assertEqual(self.validate().articles[1].key_ideas, tuple(exact))

    def test_an_article_may_not_close_on_two_objects(self):
        art = self.root / "editions" / "issue-001" / "art" / "coda-1.png"
        set_nutshell_row(
            self.root, tail_art_path=art.relative_to(self.root).as_posix()
        )

        with self.assertRaises(ValidationError) as raised:
            self.validate()

        message = str(raised.exception)
        self.assertIn("both key_ideas and tail_art_path", message)
        self.assertIn("closes with one object, not two", message)

    def test_malformed_key_ideas_are_refused_by_shape(self):
        art = self.root / "editions" / "issue-001" / "art" / "coda-1.png"
        cases = {
            "empty list": [],
            "not a list": "One idea.",
            "blank entry": ["A real claim.", "   "],
            "multi-line entry": ["A claim\nsplit over lines."],
            "non-string entry": ["A real claim.", 7],
        }
        for name, value in cases.items():
            with self.subTest(name):
                set_nutshell_row(self.root, key_ideas=value)
                with self.assertRaises(ValidationError) as raised:
                    self.validate()
                self.assertIn(
                    "key_ideas must be a non-empty list of single-line strings",
                    str(raised.exception),
                )
        self.assertTrue(art.is_file())  # The fixture's art is untouched throughout.

    def test_an_article_without_key_ideas_is_the_ordinary_case(self):
        set_nutshell_row(self.root, key_ideas=None)

        self.assertEqual(self.validate().articles[1].key_ideas, ())


class SectionKindValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_bundle(self.root)

    def test_an_unknown_section_kind_names_the_whole_registry(self):
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["sections"][0]["kind"] = "try_it_in_fifteen_minutes"
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

        with self.assertRaises(ValidationError) as raised:
            Magazine(self.root).validate("issue-001")

        message = str(raised.exception)
        self.assertIn("unknown kind 'try_it_in_fifteen_minutes'", message)
        self.assertIn("cheat_sheet", message)

    def test_a_section_takes_its_kind_s_default_title(self):
        manifest_path = self.root / "editions" / "issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        for row in manifest["sections"]:
            row.pop("title")
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

        edition = Magazine(self.root).validate("issue-001")

        self.assertEqual(
            [section.title for section in edition.sections],
            ["Try It in Fifteen Minutes", "Glossary", "Cheat Sheet"],
        )


class TranslationTests(unittest.TestCase):
    """The bundle through the overlay: sections mirror, key ideas localize."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        # Staging resolves the project root, so the fixture has to as well or
        # the two disagree about /var and /private/var on macOS.
        self.root = Path(self.temporary.name).resolve()
        make_bundle(self.root)
        (self.root / "magazine.toml").write_text(
            '[publication]\nname = "Test Review"\nlanguage = "en"\n'
            'languages = ["en", "es"]\n',
            encoding="utf-8",
        )
        self.overlay = self.root / "editions" / "issue-001" / "translations" / "es"

    def test_staging_mirrors_the_new_kinds_and_the_key_ideas_lines(self):
        report = stage_translation(self.root, "issue-001", "es")

        overlay = yaml.safe_load((self.overlay / "edition.yaml").read_text(encoding="utf-8"))
        self.assertEqual(
            [row["kind"] for row in overlay["sections"]],
            ["try_it", "glossary", "cheat_sheet"],
        )
        row = next(row for row in overlay["articles"] if row["id"] == "mcp-in-a-nutshell")
        self.assertEqual(row["key_ideas"], KEY_IDEAS)
        # English standing in for Spanish is a placeholder, never a
        # translation, so the staging report has to name it.
        pointers = {field.pointer for field in report.placeholders}
        self.assertIn("articles[mcp-in-a-nutshell].key_ideas", pointers)
        self.assertIn("sections[1].title", pointers)
        self.assertIn("sections[3].title", pointers)

    def test_a_translated_bundle_loads_and_carries_its_own_furniture(self):
        stage_translation(self.root, "issue-001", "es")
        self.translate_overlay()

        base = load_edition_with_records(self.root)
        translated = load_translation(self.root, base, "es")

        self.assertEqual(
            [section.kind for section in translated.sections],
            ["try_it", "glossary", "cheat_sheet"],
        )
        self.assertEqual(
            [section.title for section in translated.sections],
            ["Pruébalo en quince minutos", "Glosario", "Hoja de referencia"],
        )
        explainer = translated.articles[1]
        self.assertEqual(explainer.content_mode, "in_a_nutshell")
        self.assertEqual(
            explainer.key_ideas,
            (
                "Un anfitrión puede usar varios servidores sin fusionarlos.",
                "El servidor declara qué puede hacer; el anfitrión decide cuándo.",
                "Ninguna parte necesita saber cuando la otra publica una version.",
            ),
        )

    def test_a_translation_may_neither_drop_nor_invent_key_ideas(self):
        stage_translation(self.root, "issue-001", "es")
        self.translate_overlay()
        base = load_edition_with_records(self.root)
        overlay_path = self.overlay / "edition.yaml"
        original = yaml.safe_load(overlay_path.read_text(encoding="utf-8"))

        def load_with(mutate) -> str:
            overlay = yaml.safe_load(yaml.safe_dump(original, allow_unicode=True))
            mutate(overlay)
            overlay_path.write_text(
                yaml.safe_dump(overlay, sort_keys=False, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaises(ValidationError) as raised:
                load_translation(self.root, base, "es")
            return str(raised.exception)

        def row(overlay):
            return next(r for r in overlay["articles"] if r["id"] == "mcp-in-a-nutshell")

        self.assertIn(
            "requires key_ideas",
            load_with(lambda overlay: row(overlay).pop("key_ideas")),
        )
        self.assertIn(
            "must translate all 3 key_ideas lines, not 2",
            load_with(lambda overlay: row(overlay).__setitem__("key_ideas", ["Uno.", "Dos."])),
        )
        self.assertIn(
            "must omit key_ideas",
            load_with(
                lambda overlay: overlay["articles"][0].__setitem__("key_ideas", ["Uno."])
            ),
        )

    def translate_overlay(self) -> None:
        """Replace every English placeholder in the staged overlay."""

        for name, text in (
            ("try-it.md", "Quince minutos, una terminal y nada más que instalar.\n\n"
                                   "1. Crea un directorio y entra en él.\n"
                                   "2. Escribe un archivo de dos líneas que nombre un servidor.\n"
                                   "3. Arranca el anfitrión y pregúntale qué herramientas tiene.\n"),
            ("glossary.md", "Los términos de este número, una vez cada uno.\n\n"
                                     "- Anfitrión: la aplicación que el lector usa.\n"
                                     "- Servidor: el programa que declara qué puede hacer.\n"),
            ("cheat-sheet.md", "Una página, tres reglas, sin prosa.\n\n"
                                        "- El anfitrión decide cuándo.\n"
                                        "- El servidor decide qué.\n"
                                        "- Ninguno manda en el calendario del otro.\n"),
        ):
            (self.overlay / name).write_text(text, encoding="utf-8")
        overlay_path = self.overlay / "edition.yaml"
        overlay = yaml.safe_load(overlay_path.read_text(encoding="utf-8"))
        overlay["title"] = "Número"
        overlay["cover"] = {"headline": "Número"}
        for title, row in zip(
            ("Pruébalo en quince minutos", "Glosario", "Hoja de referencia"),
            overlay["sections"],
        ):
            row["title"] = title
        for row in overlay["articles"]:
            row["title"] = f"{row['title']} es"
            row["short_title"] = row["title"][:40]
            if row["id"] == "mcp-in-a-nutshell":
                row["key_ideas"] = [
                    "Un anfitrión puede usar varios servidores sin fusionarlos.",
                    "El servidor declara qué puede hacer; el anfitrión decide cuándo.",
                    "Ninguna parte necesita saber cuando la otra publica una version.",
                ]
        overlay_path.write_text(
            yaml.safe_dump(overlay, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )


class ArticleStagingTests(unittest.TestCase):
    """Staging an explainer: the byline is stated, never inferred."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        make_staging_project(self.root)
        add_staging_source(self.root, "source-one")

    def brief(self, **changes) -> ArticleBrief:
        fields = {
            "schema_version": 1,
            "edition_id": "issue-a",
            "id": "mcp-in-a-nutshell",
            "title": "MCP in a Nutshell",
            "short_title": "MCP in a Nutshell",
            "opener_variant": "edge_medallion",
            "content_mode": "in_a_nutshell",
            "editor_byline": "The editors",
            "source_ids": ("source-one",),
        }
        fields.update(changes)
        return ArticleBrief(**fields)

    def test_an_explainer_stages_with_the_brief_s_own_byline(self):
        """The source's captured author is not this piece's author.

        Every other mode republishes the person who wrote the source, so the
        row's byline is derived from the source record.  The Teacher is the
        magazine, so the brief states the byline and no biography is carried
        across -- but the pin still is: the explainer is grounded in the
        committed extraction like any other piece.
        """
        stage_article(self.root, self.brief())

        manifest = yaml.safe_load(
            (self.root / "editions" / "issue-a" / "edition.yaml").read_text(encoding="utf-8")
        )
        row = manifest["articles"][0]
        self.assertEqual(row["author"], "The editors")
        self.assertNotIn("author_note", row)
        self.assertEqual(row["content_mode"], "in_a_nutshell")
        self.assertEqual(len(row["source_body_sha256"]), 64)
        manuscript = self.root / "editions" / "issue-a" / "articles" / "mcp-in-a-nutshell.md"
        self.assertIn("content_mode: in_a_nutshell", manuscript.read_text(encoding="utf-8"))

    def test_an_explainer_without_a_byline_is_refused_rather_than_guessed(self):
        with self.assertRaises(ValidationError) as raised:
            stage_article(self.root, self.brief(editor_byline=""))

        self.assertIn("requires an explicit editor_byline", str(raised.exception))

    def test_a_source_authored_mode_may_not_override_its_captured_byline(self):
        with self.assertRaises(ValidationError) as raised:
            stage_article(
                self.root,
                self.brief(content_mode="faithful_synthesis", editor_byline="The editors"),
            )

        self.assertIn("must omit editor_byline", str(raised.exception))

    def test_original_synthesis_is_still_refused_by_name(self):
        """Unchanged: the decision was to add a mode, not to widen an old one."""
        with self.assertRaises(ValidationError) as raised:
            stage_article(self.root, self.brief(content_mode="original_synthesis"))

        self.assertIn("cannot infer an editor byline", str(raised.exception))


def _label_probe(language: str):
    """The smallest thing the label helpers read: an edition with a language."""

    class _Probe:
        def __init__(self, language: str) -> None:
            self.language = language
            self.locale = language

    return _Probe(language)


if __name__ == "__main__":
    unittest.main()
