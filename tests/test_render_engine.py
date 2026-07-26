from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import sys
import unittest

from magazine import Magazine, ValidationError
from magazine.cli import parser
from magazine import compiler as compiler_module
from magazine.render import DESIGN_LABEL, DESIGN_MONUMENT, render_a5
from magazine.render_engine import DEFAULT_ENGINE, ENGINES, reader_renderer
from magazine.weasyprint_adapter import WEASYPRINT_DESIGN, render_a5_weasyprint


def write_config(root: Path, render_table: str = "") -> None:
    (root / "magazine.toml").write_text(
        '[publication]\nname = "Test Review"\n' + render_table, encoding="utf-8"
    )


class EngineSelectionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_absent_engine_selects_weasyprint(self):
        write_config(self.root)

        self.assertEqual(Magazine(self.root).render_engine, "weasyprint")
        self.assertEqual(DEFAULT_ENGINE, "weasyprint")

    def test_configured_reportlab_selects_the_legacy_renderer(self):
        write_config(self.root, '\n[render]\nengine = "reportlab"\n')

        self.assertEqual(Magazine(self.root).render_engine, "reportlab")

    def test_unknown_engine_fails_at_load_rather_than_falling_back(self):
        write_config(self.root, '\n[render]\nengine = "prince"\n')

        with self.assertRaises(ValidationError) as caught:
            Magazine(self.root)
        message = str(caught.exception)
        self.assertIn("Unknown render engine 'prince'", message)
        for known in ENGINES:
            self.assertIn(repr(known), message)

    def test_dead_render_keys_do_not_select_an_engine(self):
        # body_size and leading are read by nothing; their presence must not
        # change which renderer runs.
        write_config(self.root, "\n[render]\nbody_size = 9.55\nleading = 12.55\n")

        self.assertEqual(Magazine(self.root).render_engine, DEFAULT_ENGINE)


class RendererIdentityTests(unittest.TestCase):
    def test_each_renderer_carries_its_own_design(self):
        self.assertEqual(reader_renderer("reportlab").design, DESIGN_MONUMENT)
        self.assertEqual(reader_renderer("weasyprint").design, WEASYPRINT_DESIGN)

    def test_each_renderer_names_the_direction_its_manifest_will_carry(self):
        # ``design_direction`` is the layout label the build writes into
        # ``edition-manifest.json``; the render review record checks it to
        # prove which engine produced the PDFs under review.  For ReportLab it
        # differs from ``design`` (config key versus rendered label).
        self.assertEqual(reader_renderer("reportlab").design_direction, DESIGN_LABEL)
        self.assertEqual(reader_renderer("weasyprint").design_direction, WEASYPRINT_DESIGN)

    def test_reportlab_design_config_never_reaches_weasyprint(self):
        # [render] design is the ReportLab engine's key.  Forwarding it would
        # make render_a5_weasyprint raise; the renderer names its own design.
        renderer = reader_renderer("weasyprint", design=DESIGN_MONUMENT)

        self.assertEqual(renderer.design, WEASYPRINT_DESIGN)
        self.assertIs(renderer.write_reader, render_a5_weasyprint)

    def test_reportlab_still_validates_an_unsupported_design_itself(self):
        renderer = reader_renderer("reportlab", design="brutalist")

        self.assertIs(renderer.write_reader, render_a5)
        with self.assertRaisesRegex(ValidationError, "Unsupported render design"):
            renderer.render(object(), Path("unused.pdf"))

    def test_neither_renderer_holds_its_typography_down_to_the_other(self):
        # WeasyPrint used to declare three shaping scaffolds -- no kerning, no
        # ligatures, no intra-token breaking -- which held Pango down to what
        # ReportLab could line-break.  They came out at the re-baseline, so both
        # renderers now set the type they are each capable of and neither has
        # anything to admit to.  The declaration itself stays because it is the
        # artifact's contract: anything a future change holds down has to be
        # named here and lands in the packaged manifest.
        self.assertEqual(reader_renderer("reportlab").shaping_scaffolds, ())
        self.assertEqual(reader_renderer("weasyprint").shaping_scaffolds, ())

    def test_rollback_engine_never_imports_the_weasyprint_path(self):
        # The rollback is only real if choosing ReportLab pulls in none of the
        # HTML path: the adapter could be deleted and a build would still run.
        # (The converse does not hold: weasyprint_adapter reuses RenderLayout
        # from render.py, a dependency that predates this switch.)
        probe = (
            "import sys;"
            "from magazine.render_engine import reader_renderer;"
            "reader_renderer('reportlab');"
            "assert 'magazine.weasyprint_adapter' not in sys.modules"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, text=True
        )

        self.assertEqual(result.returncode, 0, result.stderr)


class BuildOverrideTests(unittest.TestCase):
    """The per-build override reaches the dispatch and is not written back."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        write_config(self.root, '\n[render]\nengine = "weasyprint"\n')
        self.selected: list[object] = []
        original = compiler_module.reader_renderer

        def spy(configured=None, *, design=None):
            self.selected.append(configured)
            raise _Stop

        compiler_module.reader_renderer = spy
        self.addCleanup(setattr, compiler_module, "reader_renderer", original)

    def _build(self, **kwargs):
        with self.assertRaises(_Stop):
            Magazine(self.root).build("issue-001", **kwargs)

    def test_build_uses_the_configured_engine_by_default(self):
        self._build()

        self.assertEqual(self.selected, ["weasyprint"])

    def test_override_wins_for_one_build_and_does_not_persist(self):
        magazine = Magazine(self.root)
        config_before = (self.root / "magazine.toml").read_text(encoding="utf-8")

        with self.assertRaises(_Stop):
            magazine.build("issue-001", engine="reportlab")
        with self.assertRaises(_Stop):
            magazine.build("issue-001")

        self.assertEqual(self.selected, ["reportlab", "weasyprint"])
        self.assertEqual(magazine.render_engine, "weasyprint")
        self.assertEqual(
            (self.root / "magazine.toml").read_text(encoding="utf-8"), config_before
        )


class BuildCliTests(unittest.TestCase):
    def test_build_accepts_an_engine_flag_for_every_known_engine(self):
        for engine in ENGINES:
            args = parser().parse_args(["build", "issue-001", "--engine", engine])
            self.assertEqual(args.engine, engine)

    def test_build_without_the_flag_defers_to_configuration(self):
        self.assertIsNone(parser().parse_args(["build", "issue-001"]).engine)

    def test_build_rejects_an_unknown_engine_flag(self):
        with self.assertRaises(SystemExit):
            parser().parse_args(["build", "issue-001", "--engine", "prince"])

    def test_review_record_mirrors_the_engine_flag(self):
        base = ["review", "record", "issue-001", "--reviewer", "critic", "--result", "approved"]

        self.assertIsNone(parser().parse_args(base).engine)
        for engine in ENGINES:
            args = parser().parse_args([*base, "--engine", engine])
            self.assertEqual(args.engine, engine)


class _Stop(Exception):
    """Sentinel raised by the dispatch spy once the engine choice is observed."""


if __name__ == "__main__":
    unittest.main()
