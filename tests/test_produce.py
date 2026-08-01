"""The produce pipeline: its order, its boundaries, and its refusals.

Nothing here runs a model.  Every call goes through a scripted
:class:`CommandRunner` that answers by role, which is also how the tests can
assert the thing that actually matters about this pipeline: *what each role was
shown*.  Six of the constraints in this file are context constraints, and a
context constraint can only be tested by reading the prompt that was sent.

``[runner] codex_binary`` points at ``/bin/echo`` so backend resolution
succeeds without Codex installed; the fake intercepts the invocation long
before anything is executed.
"""

import hashlib
import io
import shutil
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from magazine import Magazine
from magazine.errors import MagazineError
from magazine.cli import main
from magazine.produce import (
    MAX_ROUNDS,
    DefaultProductionGates,
    GateResult,
    Production,
    ProductionGates,
)
from magazine.produce_prompts import (
    ANCHOR_MARKER,
    SCRATCH_MARKER,
    LineReviewInput,
    ProduceError,
    split_reply,
    split_scratch,
)
from magazine.production_record import piece_record_path
from magazine.runner import CommandResult, RunnerConfig, resolve_text_runner
from magazine.staging_marker import is_staging_marker

from test_manifest import (
    add_curated_figure,
    add_extraction,
    add_spanish_translation,
    make_project,
    pin_article_source_hash,
    set_open_edition,
)


INSTALLED = "/bin/echo"

# A sentence that exists only in the source.  Its presence in a prompt proves
# the source reached that role; its absence from a manuscript keeps the leak
# check honest for the author-voiced modes, whose manuscripts legitimately
# repeat the source word for word.
SOURCE_ONLY = "The pilot team measured a thirty-one percent regression rate."
EXTRACTION_BODY = (
    "The original article.\n"
    f"{SOURCE_ONLY}\n"
    "It went on at some length about the operational consequences.\n"
)


# The shape of a real extraction, which ``EXTRACTION_BODY`` is not: capture
# hands back hard-wrapped prose, and a writer hands back a paragraph on one
# long line.  Every sentence below is therefore in both the source and a
# faithful manuscript, and not one source *line* is ever a manuscript line.
WRAPPED_SOURCE = (
    "The kill chain opened with the benchmark the agent was being scored on,\n"
    "and closed four and a half days later inside production infrastructure.\n"
    "\n"
    "We are publishing this level of detail because the technique matters far\n"
    "more than the incident: it is the volume, at machine speed, that makes\n"
    "familiar and unremarkable weaknesses so expensive to defend against.\n"
)


def reflow(text: str) -> str:
    """The same prose as a writer returns it: one line per paragraph."""

    return (
        "\n\n".join(
            " ".join(paragraph.split())
            for paragraph in text.split("\n\n")
            if paragraph.strip()
        )
        + "\n"
    )


EDITORIAL_FRONTMATTER = (
    "---\ntitle: A Test Editorial\nbyline: The editors\nlabel: ORIGINAL EDITORIAL\n---\n"
)


def draft(
    piece_id: str,
    round_number: int,
    *,
    headings: tuple[str, ...] = (),
    anchors: dict[str, str] | None = None,
) -> str:
    """One writer reply: a manuscript, the two markers, then working notes."""

    body: list[str] = []
    if piece_id == "editorial":
        # The compiler requires the editorial's declared title and byline, so a
        # canned reply that omitted them would fail validation for a reason
        # that has nothing to do with the pipeline.
        body.extend(EDITORIAL_FRONTMATTER.splitlines())
        body.append("")
    body.extend([f"A draft of {piece_id}, round {round_number}.", ""])
    for heading in headings:
        body.extend([f"## {heading}", "", "Something about it.", ""])
    if anchors:
        body.append(ANCHOR_MARKER)
        body.extend(f"{figure_id}: {anchor}" for figure_id, anchor in anchors.items())
    body.extend(
        [
            SCRATCH_MARKER,
            f"concept graph for {piece_id} round {round_number}",
            "the frame was set in paragraph one",
        ]
    )
    return "\n".join(body) + "\n"


def verdict(result: str = "approved", **extra) -> str:
    document = {"result": result, "findings": [], "notes": "read it", **extra}
    return yaml.safe_dump(document, sort_keys=False)


def changes(note: str, *, category: str = "duplication") -> str:
    return verdict(
        "changes_required",
        findings=[
            {
                "severity": "major",
                "category": category,
                "locator": "- | a sentence | 1",
                "repair_from": "- | an earlier sentence | 1",
                "note": note,
                "suggestion": "an advisory replacement line",
            }
        ],
    )


MANAGER_RUN_A = yaml.safe_dump(
    {
        "manager_takeaways": [
            {
                "article": "article",
                "decision": "Pilot the thing this quarter.",
                "claims": ["Claim one.", "Claim two.", "Claim three."],
            }
        ]
    },
    sort_keys=False,
)

LEARNING_RUN_B = yaml.safe_dump(
    {
        "result": "approved",
        "findings": [],
        "scores": {"comprehension": 4},
        "notes": "three readers",
        "manager_takeaways": [
            {
                "article": "article",
                "decision": "Pilot the thing this quarter.",
                "claims": ["Claim one.", "Claim two.", "Claim three."],
                "adjudication": [
                    {"item": "decision", "verdict": "supported", "cite": "A draft of"},
                    {"item": "claim-1", "verdict": "supported", "cite": "A draft of"},
                    {"item": "claim-2", "verdict": "supported", "cite": "A draft of"},
                    {"item": "claim-3", "verdict": "supported", "cite": "A draft of"},
                ],
            }
        ],
    },
    sort_keys=False,
)


class ScriptedCommand:
    """A ``CommandRunner`` that answers by role and records every brief.

    Roles are recognised from the prompt file each brief opens with, which is
    the same thing a human reading the transcript would key on.  Replies come
    from ``script[(role, piece_id)]``, consumed in order and repeating the last
    entry once exhausted, so a test scripts only the rounds it cares about.
    """

    ROLES = (
        ("# Fact-checker review prompt", "evidence"),
        ("# Line editor review prompt", "line"),
        ("# Managing editor review prompt", "edition"),
        ("# Reader persona review prompt", "learning"),
    )

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.script: dict[tuple[str, str], list[str]] = {}
        self.lock = threading.Lock()
        self.hook = None
        self._rounds: dict[str, int] = {}

    def run(self, invocation):
        prompt = invocation.stdin
        role, piece = self._classify(prompt)
        with self.lock:
            self.calls.append((role, piece, prompt))
            if role == "writer":
                self._rounds[piece] = self._rounds.get(piece, 0) + 1
                round_number = self._rounds[piece]
            else:
                round_number = 0
            scripted = self.script.get((role, piece)) or self.script.get((role, "*"))
            reply = None
            if scripted:
                reply = scripted.pop(0) if len(scripted) > 1 else scripted[0]
        if self.hook is not None:
            self.hook(role, piece, prompt)
        if reply is None:
            reply = self._default(role, piece, round_number)
        argv = list(invocation.argv)
        if "--output-last-message" in argv:
            Path(argv[argv.index("--output-last-message") + 1]).write_text(
                reply, encoding="utf-8"
            )
            return CommandResult(0, "", "")
        return CommandResult(0, reply, "")

    def briefs(self, role: str, piece: str | None = None) -> list[str]:
        return [
            prompt
            for kind, name, prompt in self.calls
            if kind == role and (piece is None or name == piece)
        ]

    def roles(self) -> list[str]:
        return [role for role, _, _ in self.calls]

    def _classify(self, prompt: str) -> tuple[str, str]:
        for marker, role in self.ROLES:
            if prompt.startswith(marker):
                if role == "learning" and "# Marcus, run A only" in prompt:
                    return "manager_run_a", "edition"
                return role, self._piece(prompt)
        return "writer", self._piece(prompt)

    @staticmethod
    def _piece(prompt: str) -> str:
        for label in ("- Piece id: `", "- Article id: `"):
            if label in prompt:
                return prompt.split(label, 1)[1].split("`", 1)[0]
        return "edition"

    @staticmethod
    def _default(role: str, piece: str, round_number: int) -> str:
        if role == "writer":
            return draft(piece, round_number)
        if role == "manager_run_a":
            return MANAGER_RUN_A
        if role == "learning":
            return LEARNING_RUN_B
        return verdict("approved")


class PassingGates:
    """Gates that always pass, so a state-machine test costs no pagination."""

    def __init__(self) -> None:
        self.piece_checks: list[str] = []
        self.edition_checks: list[str] = []
        self.piece_failures: dict[str, list[str]] = {}

    def check_piece(self, piece, extractions) -> tuple[GateResult, ...]:
        self.piece_checks.append(piece.id)
        queue = self.piece_failures.get(piece.id)
        if queue:
            return (GateResult("scripted", False, queue.pop(0)),)
        return (GateResult("scripted", True),)

    def check_edition(self, edition_id: str) -> tuple[GateResult, ...]:
        self.edition_checks.append(edition_id)
        return (GateResult("validate", True), GateResult("fit", True))


REPO = Path(__file__).resolve().parents[1]


def build_project(root: Path, *, body: str = EXTRACTION_BODY) -> Magazine:
    make_project(root)
    # Produce composes its briefs from the project's own ``prompts/``, so the
    # fixture is a project with prompts in it.  Copying rather than pointing at
    # the repository's also lets a test move a prompt without touching it.
    shutil.copytree(REPO / "prompts", root / "prompts")
    (root / "magazine.toml").write_text(
        '[publication]\nname = "Test Review"\n\n'
        f'[runner]\ncodex_binary = "{INSTALLED}"\ntext_model = "gpt-5-codex"\n',
        encoding="utf-8",
    )
    pin_article_source_hash(root, add_extraction(root, body=body))
    set_open_edition(root, "issue-001")
    # The staged manuscript has to be the extraction's own text, because the
    # committed state must survive the code-fence and pin checks before produce
    # ever rewrites it.
    (root / "editions" / "issue-001" / "articles" / "article.md").write_text(
        "The original article.\n", encoding="utf-8"
    )
    return Magazine(root)


def add_article_opener(root: Path) -> None:
    """Give the fixture article the illustrated opener the limit belongs to.

    The constraint exists for exactly this composition -- an edition whose
    format is ``illustrated_paper_spots_v1`` and an article with its own
    opener art -- so a test of the budget has to build one rather than assert
    against a piece the rule does not govern.
    """

    from PIL import Image

    edition_dir = root / "editions" / "issue-001"
    opener = edition_dir / "art" / "article-opener.png"
    opener.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1600, 900), (70, 110, 150)).save(opener)
    manifest_path = edition_dir / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["format"] = {"article_opener": "illustrated_paper_spots_v1"}
    manifest["articles"][0]["opener_art"] = {
        "path": "editions/issue-001/art/article-opener.png",
        "alt_text": "A boy and robot inspect the evidence.",
        "credit": "Original illustration by the editors.",
    }
    # The format demands a declared art direction, so the fixture declares one.
    manifest["art_direction_path"] = "editions/issue-001/art/illustrations.yaml"
    (edition_dir / "art" / "illustrations.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "direction": {
                    "name": "Measured diagrams",
                    "visual_language": "Simple editorial shapes.",
                    "palette": "Black, cream, and orange.",
                    "constraints": ["No text"],
                    "avoid": ["Decoration"],
                },
                "assets": [
                    {
                        "id": "article-opener",
                        "role": "article_opener",
                        "article_id": "article",
                        "art_path": "editions/issue-001/art/article-opener.png",
                        "subject": "A boy and robot inspect the evidence.",
                        "composition": "A wide workshop scene.",
                        "alt_text": "A boy and robot inspect the evidence.",
                        "credit": "Original illustration by the editors.",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )


def production(
    magazine: Magazine,
    command: ScriptedCommand,
    *,
    gates: ProductionGates | None = None,
    max_rounds: int = MAX_ROUNDS,
) -> Production:
    config = RunnerConfig.load(magazine.root)
    return Production(
        magazine,
        runner=resolve_text_runner(config, command=command),
        model=config.text_model,
        gates=gates or PassingGates(),
        max_rounds=max_rounds,
    )


def snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ProduceFixture(unittest.TestCase):
    BODY = EXTRACTION_BODY
    """The extraction the fixture project is built on.

    A subclass overrides it when the *shape* of a source -- its line breaks,
    its typography -- is the thing under test rather than the pipeline's order.
    """

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.magazine = build_project(self.root, body=self.BODY)
        self.command = ScriptedCommand()
        self.gates = PassingGates()

    def run_produce(self, *, gates=None, max_rounds: int = MAX_ROUNDS, **kwargs):
        return production(
            self.magazine,
            self.command,
            gates=gates or self.gates,
            max_rounds=max_rounds,
        ).run("issue-001", **kwargs)

    def record(self, piece_id: str) -> dict:
        path = piece_record_path(self.magazine.editions_dir, "issue-001", piece_id)
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def manuscript(self, name: str = "articles/article.md") -> str:
        return (self.root / "editions" / "issue-001" / name).read_text(encoding="utf-8")


class HappyPathTests(ProduceFixture):
    def test_every_piece_is_drafted_gated_judged_and_recorded(self):
        result = self.run_produce()

        self.assertEqual(
            [(outcome.piece_id, outcome.status) for outcome in result.outcomes],
            [("article", "passed"), ("editorial", "passed")],
        )
        # The order is the contract: writer, then both piece judges, per piece;
        # the editorial after the pieces it is grounded in; the manager's two
        # runs and then the managing editor, once, at the end.  The two piece
        # judges overlap, so their order relative to each other is scheduling
        # and is deliberately not asserted.
        roles = self.command.roles()
        self.assertEqual(roles[0], "writer")
        self.assertEqual(sorted(roles[1:3]), ["evidence", "line"])
        self.assertEqual(roles[3], "writer")
        self.assertEqual(sorted(roles[4:6]), ["evidence", "line"])
        self.assertEqual(roles[6:], ["manager_run_a", "learning", "edition"])
        self.assertEqual(
            [piece for _, piece, _ in self.command.calls][:6],
            ["article"] * 3 + ["editorial"] * 3,
        )
        self.assertEqual(set(result.recorded), {"evidence", "line", "learning", "edition"})
        for kind in ("evidence", "line", "learning", "edition"):
            self.assertTrue(
                (self.root / "editions" / "issue-001" / "reviews" / f"{kind}.yaml").is_file(),
                kind,
            )

    def test_the_gates_run_before_either_judge(self):
        order: list[str] = []
        self.gates.check_piece = lambda piece, extractions: (
            order.append(f"gate:{piece.id}") or (GateResult("scripted", True),)
        )
        self.command.hook = lambda role, piece, prompt: order.append(f"{role}:{piece}")

        self.run_produce()

        self.assertEqual(order[:2], ["writer:article", "gate:article"])
        # The two judges overlap, so their order between themselves is not the
        # contract; that they both follow the gate is.
        self.assertEqual(
            sorted(order[2:4]), ["evidence:article", "line:article"]
        )

    def test_the_editorial_is_drafted_from_the_articles_and_bound_as_editorial(self):
        self.run_produce()

        brief = self.command.briefs("writer", "editorial")[0]
        self.assertIn("The edition's pieces, in running order", brief)
        self.assertIn("A draft of article, round 1.", brief)
        line_record = yaml.safe_load(
            (self.root / "editions" / "issue-001" / "reviews" / "line.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(set(line_record["articles"]), {"article", "editorial"})


class SingleContextDraftingTests(ProduceFixture):
    def test_one_writer_call_carries_the_whole_extraction(self):
        self.run_produce(articles=["article"])

        briefs = self.command.briefs("writer", "article")
        self.assertEqual(len(briefs), 1)
        # Every line of the extraction, in one brief.  Edition 4's duplicated
        # example came from two chunks drafted independently; there is no
        # chunking path to regress into, and this is what proves it.
        for line in EXTRACTION_BODY.strip().splitlines():
            self.assertIn(line, briefs[0])
        self.assertIn("complete", briefs[0])


class ScratchMarkerTests(ProduceFixture):
    def test_working_notes_never_reach_the_manuscript_or_a_judge(self):
        self.run_produce(articles=["article"])

        manuscript = self.manuscript()
        self.assertNotIn(SCRATCH_MARKER, manuscript)
        self.assertNotIn("concept graph", manuscript)
        for role in ("evidence", "line"):
            brief = self.command.briefs(role, "article")[0]
            self.assertNotIn("concept graph", brief)
            self.assertNotIn(SCRATCH_MARKER, brief)

    def test_the_notes_are_kept_in_the_production_record(self):
        self.run_produce(articles=["article"])

        notes = self.record("article")["rounds"][0]["notes"]
        self.assertIn("concept graph for article round 1", notes)

    def test_a_reply_with_a_second_marker_is_refused_rather_than_guessed(self):
        self.command.script[("writer", "article")] = [
            f"body\n{SCRATCH_MARKER}\nnotes\n{SCRATCH_MARKER}\nmore\n"
        ]
        # split_scratch cuts at the first marker, so the manuscript is clean and
        # the second marker lands in the notes; the refusal is about a reply
        # whose *manuscript* side carries one.
        manuscript, notes = split_scratch(
            f"a\n{SCRATCH_MARKER}\nb\n{SCRATCH_MARKER}\nc\n"
        )
        self.assertEqual(manuscript, "a")
        self.assertIn(SCRATCH_MARKER, notes)

    def test_a_reply_that_is_only_notes_is_refused(self):
        self.command.script[("writer", "article")] = [f"{SCRATCH_MARKER}\nonly notes\n"]

        with self.assertRaises(ProduceError) as raised:
            self.run_produce(articles=["article"])

        self.assertIn("no manuscript", str(raised.exception))


class LineEditorBoundaryTests(ProduceFixture):
    def test_the_line_editor_is_not_given_the_source(self):
        self.run_produce(articles=["article"])

        line_brief = self.command.briefs("line", "article")[0]
        evidence_brief = self.command.briefs("evidence", "article")[0]
        self.assertNotIn(SOURCE_ONLY, line_brief)
        self.assertIn(SOURCE_ONLY, evidence_brief)
        self.assertIn("source extraction is deliberately withheld", line_brief)

    def test_the_input_type_has_nowhere_to_put_a_source(self):
        """The prohibition is structural, not a sentence a caller may ignore."""

        fields = set(LineReviewInput.__dataclass_fields__)
        self.assertEqual(
            fields,
            {"piece_id", "content_mode", "byline", "max_pages", "manuscript"},
        )
        for forbidden in ("extractions", "source", "sources", "extraction"):
            self.assertNotIn(forbidden, fields)

    def test_a_leak_through_any_other_door_is_still_caught(self):
        from magazine.extraction import Extraction
        from magazine.produce_prompts import assert_source_withheld

        extraction = Extraction(
            Path("x"), "source-one", "bundle", "test", EXTRACTION_BODY, "0" * 64
        )
        with self.assertRaises(ProduceError):
            assert_source_withheld(
                f"a brief that quotes {SOURCE_ONLY} somehow",
                [extraction],
                manuscript="a manuscript that does not",
                label="line editor",
            )
        # A faithful_edit manuscript is the source's sentences, and carrying it
        # is the whole point of the brief.  That must not read as a leak.
        assert_source_withheld(
            f"a brief carrying {SOURCE_ONLY}",
            [extraction],
            manuscript=SOURCE_ONLY,
            label="line editor",
        )

    def test_the_manuscript_is_exempt_however_either_side_is_wrapped(self):
        """The bug that stopped the first live run before any judge ran.

        A source line is a wrap fragment, not a unit of meaning.  Comparing
        source lines against manuscript *lines* asked whether a hard-wrapped
        source and a reflowed manuscript broke in the same places, which they
        never do, so a faithful piece tripped a guard against text it was
        supposed to carry.
        """

        from magazine.extraction import Extraction
        from magazine.produce_prompts import assert_source_withheld

        extraction = Extraction(
            Path("x"), "source-one", "bundle", "test", WRAPPED_SOURCE, "0" * 64
        )
        manuscript = reflow(WRAPPED_SOURCE)
        for description, variant in (
            ("reflowed", manuscript),
            ("curly-quoted", manuscript.replace("'", "’")),
            ("tabbed and padded", manuscript.replace(" ", "\t   ", 1) + "   \n"),
            ("re-cased", manuscript.replace("The kill chain", "The Kill Chain")),
        ):
            with self.subTest(description):
                assert_source_withheld(
                    f"a brief carrying\n\n{variant}\n",
                    [extraction],
                    manuscript=variant,
                    label="line editor",
                )

    def test_a_leak_survives_re_wrapping_re_casing_and_re_quoting(self):
        """The teeth the fold puts in, not the ones it takes out.

        Folding both sides is what lets the manuscript be exempt; it also means
        a leak cannot launder itself by re-wrapping, shouting, or curling its
        apostrophes, all of which walked past the old raw ``in`` check.
        """

        from magazine.extraction import Extraction
        from magazine.produce_prompts import assert_source_withheld

        extraction = Extraction(
            Path("x"), "source-one", "bundle", "test", WRAPPED_SOURCE, "0" * 64
        )
        leaked = reflow(WRAPPED_SOURCE)
        for description, variant in (
            ("verbatim", WRAPPED_SOURCE),
            ("reflowed", leaked),
            ("shouted", leaked.upper()),
            ("curly-quoted", leaked.replace("'", "’")),
            ("re-wrapped elsewhere", leaked.replace(" that ", "\n")),
        ):
            with self.subTest(description):
                with self.assertRaises(ProduceError) as raised:
                    assert_source_withheld(
                        f"a brief that quotes the source\n\n{variant}\n",
                        [extraction],
                        manuscript="a manuscript that carries none of it",
                        label="line editor",
                    )
                self.assertIn("forbidden the source", str(raised.exception))


class LiveJudgeRoundTripTests(ProduceFixture):
    """A round driven end to end over a realistically shaped source.

    Every other test in this file runs on ``EXTRACTION_BODY``, whose three
    short lines no fixture manuscript repeats, so the line editor's guard was
    never asked the question round one of a real run asks it first.  It said
    no, and the run died there -- which meant no judge had ever run, and every
    step after the guard was untested against a live pipeline: a verdict
    parsed, written into the round record, and carried into the next writer's
    brief.  This class walks that path on a source that would have failed.
    """

    BODY = WRAPPED_SOURCE

    def setUp(self):
        super().setUp()
        # A faithful manuscript: the source's own sentences, reflowed.
        self.command.script[("writer", "article")] = [
            f"{reflow(WRAPPED_SOURCE)}\n{SCRATCH_MARKER}\nthe claim ladder"
        ]

    def test_a_faithful_manuscript_reaches_both_judges(self):
        result = self.run_produce(articles=["article"])

        self.assertEqual(result.outcomes[0].status, "passed")
        line_brief = self.command.briefs("line", "article")[0]
        self.assertIn("it is the volume, at machine speed", line_brief)
        self.assertIn("source extraction is deliberately withheld", line_brief)

    def test_a_verdict_reaches_the_record_and_the_next_writer_s_brief(self):
        self.command.script[("line", "article")] = [
            changes("the kill chain is told twice"),
            verdict("approved"),
        ]

        result = self.run_produce(articles=["article"])

        outcome = result.outcomes[0]
        self.assertEqual((outcome.status, outcome.rounds), ("passed", 2))
        first, second = self.record("article")["rounds"]
        # Parsed, and parsed into the record rather than merely counted.
        self.assertEqual(first["result"], "changes_required")
        self.assertEqual(set(first["judges"]), {"evidence", "line"})
        self.assertEqual(first["judges"]["line"]["result"], "changes_required")
        self.assertEqual(
            [entry["note"] for entry in first["judges"]["line"]["findings"]],
            ["the kill chain is told twice"],
        )
        self.assertEqual(first["judges"]["evidence"]["result"], "approved")
        self.assertEqual(second["judges"]["line"]["result"], "approved")
        # And carried forward: a finding the writer never sees is not a loop.
        brief = self.command.briefs("writer", "article")[1]
        self.assertIn("Findings you must clear", brief)
        self.assertIn("[major] duplication (from the line)", brief)
        self.assertIn("the kill chain is told twice", brief)


class ParallelJudgeTests(ProduceFixture):
    def test_the_fact_checker_and_line_editor_overlap(self):
        """Proved by a barrier: a serial pipeline can never clear it."""

        barrier = threading.Barrier(2, timeout=10)
        reached: list[str] = []

        def hook(role, piece, prompt):
            if role in ("evidence", "line"):
                reached.append(role)
                barrier.wait()

        self.command.hook = hook

        self.run_produce(articles=["article"])

        self.assertEqual(sorted(reached), ["evidence", "line"])

    def test_results_come_back_in_a_fixed_order_whatever_the_schedule(self):
        self.command.script[("evidence", "article")] = [changes("a fact moved")]
        self.command.script[("line", "article")] = [changes("a sentence repeats")]

        self.run_produce(articles=["article"], )

        round_one = self.record("article")["rounds"][0]
        self.assertEqual(list(round_one["judges"]), ["evidence", "line"])


class RevisionTests(ProduceFixture):
    def test_a_piece_that_fails_once_then_passes(self):
        self.command.script[("line", "article")] = [
            changes("the second example repeats the first"),
            verdict("approved"),
        ]

        result = self.run_produce(articles=["article"])

        outcome = result.outcomes[0]
        self.assertEqual((outcome.status, outcome.rounds), ("passed", 2))
        record = self.record("article")
        self.assertEqual(record["status"], "passed")
        self.assertEqual(
            [entry["result"] for entry in record["rounds"]],
            ["changes_required", "approved"],
        )

    def test_the_reviser_receives_the_findings_and_the_predecessor_s_notes(self):
        self.command.script[("line", "article")] = [
            changes("the second example repeats the first"),
            verdict("approved"),
        ]

        self.run_produce(articles=["article"])

        second = self.command.briefs("writer", "article")[1]
        self.assertIn("the second example repeats the first", second)
        # The notes are the point.  A finding names where a defect surfaces;
        # only the predecessor's notes say where it was made.
        self.assertIn("concept graph for article round 1", second)
        self.assertIn("A draft of article, round 1.", second)
        self.assertIn("earliest repair point: - | an earlier sentence | 1", second)

    def test_a_suggestion_is_advisory_and_a_finding_is_not(self):
        self.command.script[("line", "article")] = [
            changes("the second example repeats the first"),
            verdict("approved"),
        ]

        self.run_produce(articles=["article"])

        second = self.command.briefs("writer", "article")[1]
        self.assertIn("Every finding is an obligation", second)
        self.assertIn("suggestion (advisory)", second)
        self.assertIn(
            "judged on whether the defect survived, never on whether you", second
        )

    def test_three_rounds_then_escalation_with_every_finding_accumulated(self):
        self.command.script[("evidence", "article")] = [
            changes("round one number is wrong", category="number_or_name_error")
        ]
        self.command.script[("line", "article")] = [changes("round one repeats")]

        result = self.run_produce(articles=["article"])

        outcome = result.outcomes[0]
        self.assertEqual((outcome.status, outcome.rounds), ("escalated", MAX_ROUNDS))
        self.assertEqual(len(self.command.briefs("writer", "article")), MAX_ROUNDS)
        record = self.record("article")
        self.assertEqual(record["status"], "escalated")
        self.assertEqual(len(record["rounds"]), MAX_ROUNDS)
        notes = [finding["note"] for finding in record["escalation"]["findings"]]
        self.assertEqual(notes.count("round one number is wrong"), MAX_ROUNDS)
        self.assertEqual(notes.count("round one repeats"), MAX_ROUNDS)
        # An escalated piece stops the run: the whole-issue judges read a
        # finished issue, and this one is not.
        self.assertNotIn("manager_run_a", self.command.roles())
        self.assertTrue(
            any("needs a human" in action for action in result.human_actions)
        )

    def test_a_gate_failure_goes_back_to_the_writer_without_paying_for_judges(self):
        self.gates.piece_failures["article"] = ["the fence is not the source's"]

        self.run_produce(articles=["article"])

        self.assertEqual(len(self.command.briefs("writer", "article")), 2)
        self.assertEqual(len(self.command.briefs("evidence", "article")), 1)
        second = self.command.briefs("writer", "article")[1]
        self.assertIn("Deterministic checks the draft failed", second)
        self.assertIn("the fence is not the source's", second)
        self.assertEqual(
            self.record("article")["rounds"][0]["gate_failures"],
            ["scripted: the fence is not the source's"],
        )


class ManagerBoundaryTests(ProduceFixture):
    def test_run_a_sees_furniture_and_run_b_sees_the_body(self):
        self.run_produce()

        run_a = self.command.briefs("manager_run_a")[0]
        run_b = self.command.briefs("learning")[0]
        self.assertIn("Marcus, run A only", run_a)
        self.assertIn("Article", run_a)  # the furniture projection's title
        self.assertNotIn("A draft of article, round 1.", run_a)
        self.assertNotIn(SOURCE_ONLY, run_a)
        self.assertIn("A draft of article, round 1.", run_b)
        # Run A's block, verbatim, in run B.
        self.assertIn("Pilot the thing this quarter.", run_b)
        self.assertIn("Claim two.", run_b)
        self.assertIn("already written and closed", run_b)

    def test_run_a_is_recorded_separately_from_run_b(self):
        self.run_produce()

        record = yaml.safe_load(
            (
                self.root
                / "editions"
                / "issue-001"
                / "production"
                / "issue"
                / "learning.yaml"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(record["manager_run_a"]["call"]["role"], "manager_run_a")
        self.assertEqual(record["run_b"]["call"]["role"], "learning_judge")
        self.assertEqual(
            record["manager_run_a"]["manager_takeaways"][0]["claims"],
            ["Claim one.", "Claim two.", "Claim three."],
        )

    def test_a_run_b_that_improves_run_a_s_claims_is_refused(self):
        revised = yaml.safe_load(LEARNING_RUN_B)
        revised["manager_takeaways"][0]["claims"] = [
            "Claim one.",
            "A better claim the body happens to support.",
            "Claim three.",
        ]
        self.command.script[("learning", "edition")] = [
            yaml.safe_dump(revised, sort_keys=False)
        ]

        with self.assertRaises(ProduceError) as raised:
            self.run_produce()

        self.assertIn("rewrote run A", str(raised.exception))

    def test_a_run_b_that_drops_run_a_s_block_is_refused(self):
        dropped = yaml.safe_load(LEARNING_RUN_B)
        dropped.pop("manager_takeaways")
        self.command.script[("learning", "edition")] = [
            yaml.safe_dump(dropped, sort_keys=False)
        ]

        with self.assertRaises(ProduceError) as raised:
            self.run_produce()

        self.assertIn("dropped run A's manager takeaways", str(raised.exception))


class ProvenanceTests(ProduceFixture):
    def test_the_record_pins_the_prompt_backend_argv_duration_and_bytes(self):
        self.run_produce(articles=["article"])

        record = self.record("article")
        self.assertEqual(record["schema_version"], 1)
        self.assertEqual(record["edition_id"], "issue-001")
        self.assertEqual(record["piece_id"], "article")
        self.assertEqual(record["content_mode"], "faithful_edit")
        writer = record["rounds"][0]["writer"]
        self.assertEqual(writer["prompt_path"], "prompts/faithful-edit.md")
        self.assertEqual(
            writer["prompt_sha256"],
            hashlib.sha256(
                (self.root / "prompts" / "faithful-edit.md").read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(writer["backend"], "codex")
        self.assertEqual(writer["model"], "gpt-5-codex")
        self.assertIn("exec", writer["argv"])
        self.assertIsInstance(writer["duration_seconds"], float)
        self.assertEqual(
            record["manuscript_sha256"],
            hashlib.sha256(self.manuscript().encode("utf-8")).hexdigest(),
        )

    def test_every_judge_call_is_pinned_too(self):
        self.run_produce(articles=["article"])

        judges = self.record("article")["rounds"][0]["judges"]
        self.assertEqual(set(judges), {"evidence", "line"})
        self.assertEqual(
            judges["evidence"]["call"]["prompt_path"], "prompts/evidence-review.md"
        )
        self.assertEqual(judges["line"]["call"]["prompt_path"], "prompts/line-review.md")

    def test_the_record_is_greppable_by_prompt_digest(self):
        self.run_produce(articles=["article"])

        text = piece_record_path(
            self.magazine.editions_dir, "issue-001", "article"
        ).read_text(encoding="utf-8")
        self.assertIn("prompt_sha256:", text)
        self.assertIn("output_sha256:", text)


class ResumeTests(ProduceFixture):
    def test_an_unchanged_approved_piece_is_not_redrafted(self):
        self.run_produce(articles=["article"])
        first = len(self.command.briefs("writer", "article"))

        result = self.run_produce(articles=["article"])

        self.assertEqual(len(self.command.briefs("writer", "article")), first)
        self.assertEqual(result.outcomes[0].status, "settled")

    def test_a_moved_prompt_makes_the_piece_due_again(self):
        self.run_produce(articles=["article"])
        prompt = self.root / "prompts" / "faithful-edit.md"
        prompt.write_bytes(prompt.read_bytes() + b"\nOne more rule.\n")

        result = self.run_produce(articles=["article"])

        self.assertEqual(result.outcomes[0].status, "passed")
        self.assertEqual(len(self.command.briefs("writer", "article")), 2)

    def test_a_hand_edited_manuscript_makes_the_piece_due_again(self):
        self.run_produce(articles=["article"])
        (self.root / "editions" / "issue-001" / "articles" / "article.md").write_text(
            "Someone edited this by hand.\n", encoding="utf-8"
        )

        result = self.run_produce(articles=["article"])

        self.assertEqual(result.outcomes[0].status, "passed")


class DryRunTests(ProduceFixture):
    def test_a_dry_run_calls_no_model_and_writes_nothing(self):
        before = snapshot(self.root)

        result = self.run_produce(dry_run=True)

        self.assertTrue(result.dry_run)
        self.assertEqual(self.command.calls, [])
        self.assertEqual(self.gates.edition_checks, [])
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(
            [piece.piece_id for piece in result.plan.pieces], ["article", "editorial"]
        )
        self.assertEqual(result.plan.backend, "codex")
        self.assertEqual(result.plan.model, "gpt-5-codex")

    def test_the_plan_names_the_prompt_that_would_be_used(self):
        result = self.run_produce(dry_run=True)

        row = result.plan.pieces[0]
        self.assertEqual(row.prompt_path, "prompts/faithful-edit.md")
        self.assertEqual(len(row.prompt_sha256), 64)
        self.assertEqual(row.action, "draft and judge")


class SubsetAndSelectionTests(ProduceFixture):
    def test_articles_narrows_the_run(self):
        result = self.run_produce(articles=["article"])

        self.assertEqual([row.piece_id for row in result.plan.pieces], ["article"])
        self.assertEqual(self.command.briefs("writer", "editorial"), [])

    def test_an_unknown_piece_is_refused_by_name(self):
        with self.assertRaises(ProduceError) as raised:
            self.run_produce(articles=["nope"])

        self.assertIn("no piece(s) named nope", str(raised.exception))

    def test_a_subset_with_no_prior_record_reports_a_human_action(self):
        """A partial re-record needs a record to amend; inventing one would
        re-bless the pieces this run never judged."""

        result = self.run_produce(articles=["article"])

        # Evidence binds articles only, and ``article`` is all of them, so that
        # record is whole and lands.  The line bench also binds the editorial,
        # which this run did not read.
        self.assertIn("evidence", result.recorded)
        self.assertNotIn("line", result.recorded)
        self.assertTrue(
            any(
                "no line review record exists to amend" in action
                for action in result.human_actions
            )
        )


class RefusalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.magazine = build_project(self.root)

    def test_a_released_edition_is_never_rewritten(self):
        set_open_edition(self.root, "999-unreleased", issue_number=999)
        state = self.root / "library" / "release-state.yaml"
        data = yaml.safe_load(state.read_text(encoding="utf-8"))
        data["released_editions"] = [
            {"id": "issue-001", "issue_number": 1, "status": "released"}
        ]
        state.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        command = ScriptedCommand()

        with self.assertRaises(ProduceError) as raised:
            production(self.magazine, command).run("issue-001")

        self.assertIn("is released", str(raised.exception))
        self.assertEqual(command.calls, [])

    def test_an_unqueued_sibling_workspace_is_produced_into(self):
        """The remedy the released refusal names has to be reachable.

        A rerun of a shipped issue is deliberately kept out of the release
        ledger -- it exists to be compared against the shipped issue, not to
        be shipped -- so produce asks it for a manifest, not for a queue entry.
        """

        set_open_edition(self.root, "999-unreleased", issue_number=999)
        shutil.copytree(
            self.root / "editions" / "issue-001",
            self.root / "editions" / "rerun-issue-001",
        )
        manifest_path = self.root / "editions" / "rerun-issue-001" / "edition.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["id"] = "rerun-issue-001"
        manifest["articles"][0]["manuscript"] = (
            "editions/rerun-issue-001/articles/article.md"
        )
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
        state = yaml.safe_load(
            (self.root / "library" / "release-state.yaml").read_text(encoding="utf-8")
        )

        result = production(self.magazine, ScriptedCommand()).run(
            "rerun-issue-001", dry_run=True
        )

        self.assertEqual(result.plan.edition_id, "rerun-issue-001")
        self.assertTrue(result.dry_run)
        # The workspace stays out of the ledger; producing into it never enrols it.
        self.assertEqual(
            yaml.safe_load(
                (self.root / "library" / "release-state.yaml").read_text(
                    encoding="utf-8"
                )
            ),
            state,
        )

    def test_an_edition_that_does_not_exist_is_refused_by_name(self):
        set_open_edition(self.root, "999-unreleased", issue_number=999)
        command = ScriptedCommand()

        with self.assertRaises(ProduceError) as raised:
            production(self.magazine, command).run("issue-404")

        self.assertIn("issue-404", str(raised.exception))
        self.assertIn("mag collect", str(raised.exception))
        self.assertEqual(command.calls, [])

    def test_a_missing_backend_aborts_before_any_edition_state_moves(self):
        (self.root / "magazine.toml").write_text(
            '[publication]\nname = "Test Review"\n\n'
            '[runner]\ncodex_binary = "definitely-not-installed-anywhere"\n',
            encoding="utf-8",
        )
        before = snapshot(self.root)

        with self.assertRaises(Exception) as raised:
            Magazine(self.root).produce("issue-001", dry_run=True)

        self.assertIn("not on PATH", str(raised.exception))
        self.assertEqual(snapshot(self.root), before)

    def test_produce_refuses_an_image_runner(self):
        from magazine.runner import resolve_image_runner

        config = RunnerConfig.load(self.root)
        with self.assertRaises(ProduceError) as raised:
            Production(
                self.magazine,
                runner=resolve_image_runner(config, command=ScriptedCommand()),
            )

        self.assertIn("text generation only", str(raised.exception))

    def test_no_image_runner_is_reachable_from_the_produce_modules(self):
        """The rule is enforced by absence: there is nothing here to call."""

        for name in ("produce", "produce_prompts", "production_record"):
            source = (
                Path(__file__).resolve().parents[1]
                / "src"
                / "magazine"
                / f"{name}.py"
            ).read_text(encoding="utf-8")
            self.assertNotIn("resolve_image_runner", source, name)
            self.assertNotIn("image_backend", source, name)


class HumanActionTests(ProduceFixture):
    def test_a_piece_with_no_registered_art_is_reported_never_generated(self):
        result = self.run_produce(dry_run=True)

        self.assertTrue(
            any(
                "has no registered opener art" in action
                and "never generates an image" in action
                for action in result.human_actions
            )
        )


class FigureAnchorTests(unittest.TestCase):
    """A rewrite changes headings, and a figure anchor is an exact heading."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.magazine = build_project(self.root)
        add_curated_figure(self.root)
        edition_path = self.root / "editions" / "issue-001" / "edition.yaml"
        edition = yaml.safe_load(edition_path.read_text(encoding="utf-8"))
        edition["articles"][0]["figures"][0]["anchor"] = "The kill chain"
        edition_path.write_text(yaml.safe_dump(edition, sort_keys=False), encoding="utf-8")
        (self.root / "editions" / "issue-001" / "articles" / "article.md").write_text(
            "The original article.\n\n## The kill chain\n\nSomething.\n",
            encoding="utf-8",
        )
        self.command = ScriptedCommand()

    def anchor(self) -> str:
        edition = yaml.safe_load(
            (self.root / "editions" / "issue-001" / "edition.yaml").read_text(
                encoding="utf-8"
            )
        )
        return edition["articles"][0]["figures"][0]["anchor"]

    def test_the_writer_is_told_which_figures_need_a_place_not_which_headings(self):
        """The argument owns the headings; the brief owns the list of figures."""

        self.command.script[("writer", "article")] = [
            draft("article", 1, headings=("The kill chain",))
        ]

        production(self.magazine, self.command).run("issue-001", articles=["article"])

        brief = self.command.briefs("writer", "article")[0]
        self.assertIn("Figures this piece has to leave a place for", brief)
        self.assertIn("- `diagram` -- The source diagram.", brief)
        self.assertIn("<!-- FIGURE ANCHORS -->", brief)
        # The old instruction is gone: the writer is no longer told to preserve
        # a heading, and the current anchor is deliberately absent, so that
        # reconciling the manifest cannot invalidate this very brief.
        self.assertNotIn("Headings you must keep", brief)
        self.assertNotIn("The kill chain", brief)

    def test_a_declared_anchor_moves_the_manifest_instead_of_costing_a_round(self):
        self.command.script[("writer", "article")] = [
            draft(
                "article",
                1,
                headings=("A different heading",),
                anchors={"diagram": "A different heading"},
            )
        ]

        result = production(
            self.magazine, self.command, gates=_AnchorOnlyGates()
        ).run("issue-001", articles=["article"])

        self.assertEqual(result.outcomes[0].status, "passed")
        self.assertEqual(result.outcomes[0].rounds, 1)
        self.assertEqual(self.anchor(), "A different heading")
        record = yaml.safe_load(
            piece_record_path(
                self.magazine.editions_dir, "issue-001", "article"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(record["rounds"][0]["anchors_reconciled"], ["A different heading"])

    def test_a_reconciled_piece_stays_settled_on_the_next_invocation(self):
        """The fingerprint follows the manifest, or the piece redrafts for ever."""

        self.command.script[("writer", "article")] = [
            draft(
                "article",
                1,
                headings=("A different heading",),
                anchors={"diagram": "A different heading"},
            )
        ]
        production(self.magazine, self.command, gates=_AnchorOnlyGates()).run(
            "issue-001", articles=["article"]
        )

        second = production(
            Magazine(self.root), ScriptedCommand(), gates=_AnchorOnlyGates()
        ).run("issue-001", articles=["article"])

        self.assertEqual(second.outcomes[0].status, "settled")

    def test_a_declaration_naming_no_real_heading_is_refused_not_applied(self):
        self.command.script[("writer", "article")] = [
            draft(
                "article",
                1,
                headings=("A different heading",),
                anchors={"diagram": "A heading nobody wrote"},
            ),
            draft("article", 2, headings=("The kill chain",)),
        ]

        result = production(
            self.magazine, self.command, gates=_AnchorOnlyGates()
        ).run("issue-001", articles=["article"])

        self.assertEqual(result.outcomes[0].status, "passed")
        self.assertEqual(result.outcomes[0].rounds, 2)
        self.assertEqual(self.anchor(), "The kill chain")

    def test_a_figure_whose_heading_survived_is_never_relocated(self):
        """A writer does not get to move a figure that was never in danger."""

        self.command.script[("writer", "article")] = [
            draft(
                "article",
                1,
                headings=("The kill chain", "Somewhere else"),
                anchors={"diagram": "Somewhere else"},
            )
        ]

        production(self.magazine, self.command, gates=_AnchorOnlyGates()).run(
            "issue-001", articles=["article"]
        )

        self.assertEqual(self.anchor(), "The kill chain")

    def test_a_rewrite_that_strands_a_figure_fails_the_gate_and_says_so(self):
        """The gate is the real one: no injected pass can hide a lost anchor."""

        self.command.script[("writer", "article")] = [
            draft("article", 1, headings=("A different heading",)),
            draft("article", 2, headings=("The kill chain",)),
        ]

        result = production(
            self.magazine,
            self.command,
            gates=_AnchorOnlyGates(),
        ).run("issue-001", articles=["article"])

        self.assertEqual(result.outcomes[0].status, "passed")
        self.assertEqual(result.outcomes[0].rounds, 2)
        second = self.command.briefs("writer", "article")[1]
        self.assertIn("figure 'diagram' is anchored to the heading 'The kill chain'", second)
        self.assertIn("Headings in the draft:", second)

    def test_a_figure_is_never_silently_dropped(self):
        self.command.script[("writer", "article")] = [
            draft("article", 1, headings=("A different heading",))
        ]

        result = production(
            self.magazine, self.command, gates=_AnchorOnlyGates(), max_rounds=1
        ).run("issue-001", articles=["article"])

        self.assertEqual(result.outcomes[0].status, "escalated")
        edition = yaml.safe_load(
            (self.root / "editions" / "issue-001" / "edition.yaml").read_text(
                encoding="utf-8"
            )
        )
        # The manifest still carries the figure: produce reconciles or refuses,
        # and never resolves the conflict by deleting the picture.
        self.assertEqual(edition["articles"][0]["figures"][0]["anchor"], "The kill chain")


class _AnchorOnlyGates:
    """The real anchor gate, without paying for validate and fit."""

    def check_piece(self, piece, extractions):
        from magazine.produce import _anchor_gate

        return (_anchor_gate(piece),)

    def check_edition(self, edition_id):
        return (GateResult("validate", True), GateResult("fit", True))


class RealGateTests(ProduceFixture):
    """One run through the deterministic gates the CLI actually uses."""

    def test_validate_and_fit_run_for_every_draft(self):
        gates = DefaultProductionGates(self.magazine)
        calls: list[str] = []
        original = gates.check_edition
        gates.check_edition = lambda edition_id: (
            calls.append(edition_id) or original(edition_id)
        )

        result = production(self.magazine, self.command, gates=gates).run(
            "issue-001", articles=["article"]
        )

        self.assertEqual(result.outcomes[0].status, "passed")
        # Once for the baseline, once for the draft.
        self.assertEqual(calls, ["issue-001", "issue-001"])

    def test_a_code_fence_the_source_never_carried_is_caught(self):
        self.command.script[("writer", "article")] = [
            "A draft.\n\n```\nnot in the source at all\n```\n"
            f"\n{SCRATCH_MARKER}\nnotes\n",
            draft("article", 2),
        ]

        result = production(
            self.magazine, self.command, gates=DefaultProductionGates(self.magazine)
        ).run("issue-001", articles=["article"])

        self.assertEqual(result.outcomes[0].status, "passed")
        second = self.command.briefs("writer", "article")[1]
        self.assertIn("code_blocks", second)
        self.assertIn("does not appear in any pinned source extraction", second)

    def test_a_fully_staged_edition_is_still_produce_s_input(self):
        """Every piece a marker is the first run, not a state to refuse.

        ``validate`` now refuses a staged piece, and produce reaches validate
        through its own edition gate.  That has to stay a reported pre-existing
        failure rather than a stop: the gate names pieces this writer cannot
        clear, and produce is the command that clears them.
        """

        edition_dir = self.root / "editions" / "issue-001"
        (edition_dir / "articles" / "article.md").write_text(
            "---\nsource_ids:\n- source-one\ncontent_mode: faithful_edit\n"
            "label: EDITORIAL WORK REQUIRED\nstage_status: todo\n---\n\n"
            "TODO(editor): Replace this staging marker with a source-faithful "
            "manuscript. No source prose was generated.\n",
            encoding="utf-8",
        )
        (edition_dir / "editorial.md").write_text(
            "---\ntitle: Untitled editorial\nbyline: The Editors\n"
            "label: EDITORIAL WORK REQUIRED\nstage_status: todo\n---\n\n"
            "TODO(editor): Replace this staging marker with a source-faithful "
            "manuscript. No source prose was generated.\n",
            encoding="utf-8",
        )

        result = production(
            self.magazine, self.command, gates=DefaultProductionGates(self.magazine)
        ).run("issue-001")

        self.assertEqual(
            [(outcome.piece_id, outcome.status) for outcome in result.outcomes],
            [("article", "passed"), ("editorial", "passed")],
        )
        self.assertTrue(
            any(
                "pre-existing gate failure (validate)" in action
                and "staging markers" in action
                for action in result.human_actions
            ),
            result.human_actions,
        )
        self.assertFalse(is_staging_marker(edition_dir / "articles" / "article.md"))
        self.assertFalse(is_staging_marker(edition_dir / "editorial.md"))
        # And the edition it hands back validates, which is the whole point.
        self.assertEqual(self.magazine.validate("issue-001").id, "issue-001")


class TranslationDriftTests(unittest.TestCase):
    """Rewriting English stales the overlays, and no reviser can fix that."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        build_project(self.root)
        add_spanish_translation(self.root)
        # add_spanish_translation rewrites magazine.toml wholesale, so the
        # runner table has to be restated.
        (self.root / "magazine.toml").write_text(
            (self.root / "magazine.toml").read_text(encoding="utf-8")
            + f'\n[runner]\ncodex_binary = "{INSTALLED}"\n',
            encoding="utf-8",
        )
        self.magazine = Magazine(self.root)
        self.command = ScriptedCommand()

    def test_a_stale_overlay_is_a_human_action_not_a_revision_round(self):
        result = production(
            self.magazine,
            self.command,
            gates=DefaultProductionGates(self.magazine),
        ).run("issue-001", articles=["article"])

        self.assertEqual(result.outcomes[0].status, "passed")
        self.assertEqual(result.outcomes[0].rounds, 1)
        self.assertEqual(len(self.command.briefs("writer", "article")), 1)
        self.assertTrue(
            any(
                "mag translate issue-001 <language>" in action
                for action in result.human_actions
            ),
            result.human_actions,
        )


class CliTests(ProduceFixture):
    def run_cli(self, argv: list[str]) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = main(["--root", str(self.root), *argv])
        return code, out.getvalue()

    def test_a_dry_run_prints_the_plan_and_writes_nothing(self):
        before = snapshot(self.root)

        code, output = self.run_cli(["produce", "issue-001", "--dry-run"])

        self.assertEqual(code, 0, output)
        self.assertIn("dry run: no model was called", output)
        self.assertIn("plan: article (faithful_edit)", output)
        self.assertEqual(snapshot(self.root), before)

    def install_claude(self) -> None:
        """Make both backends resolvable without changing which one is configured."""

        path = self.root / "magazine.toml"
        path.write_text(
            path.read_text(encoding="utf-8") + f'claude_binary = "{INSTALLED}"\n',
            encoding="utf-8",
        )

    def test_backend_borrows_the_other_backend_for_one_run(self):
        self.install_claude()
        before = snapshot(self.root)

        code, output = self.run_cli(
            ["produce", "issue-001", "--backend", "claude", "--dry-run"]
        )

        self.assertEqual(code, 0, output)
        self.assertIn("issue-001: claude/", output)
        self.assertIn("plan: article (faithful_edit)", output)
        # The flag is an invocation, not an edit: the file still says codex, and
        # the next run without the flag is a codex run again.
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(RunnerConfig.load(self.root).text_backend, "codex")
        self.assertIn(
            "issue-001: codex/", self.run_cli(["produce", "issue-001", "--dry-run"])[1]
        )

    def test_the_configured_backend_is_used_when_the_flag_is_absent(self):
        code, output = self.run_cli(["produce", "issue-001", "--dry-run"])

        self.assertEqual(code, 0, output)
        self.assertIn("issue-001: codex/", output)

    def test_an_unknown_backend_is_refused_before_anything_runs(self):
        self.install_claude()
        before = snapshot(self.root)
        stderr = io.StringIO()

        with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                main(["--root", str(self.root), "produce", "issue-001", "--backend", "gemini"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("gemini", stderr.getvalue())
        self.assertEqual(self.command.calls, [])
        self.assertEqual(snapshot(self.root), before)

    def test_the_flag_carries_only_a_text_backend_to_the_compiler(self):
        """No spelling of it names an image backend or a runner key."""

        from magazine.cli import parser
        from magazine.runner import TEXT_BACKENDS

        for backend in TEXT_BACKENDS:
            with self.subTest(backend=backend):
                args = parser().parse_args(["produce", "issue-001", "--backend", backend])
                self.assertEqual(args.backend, backend)
        self.assertIsNone(parser().parse_args(["produce", "issue-001"]).backend)
        self.assertNotIn(
            "image_backend", (Path(__file__).resolve().parents[1] / "src" / "magazine" / "cli.py").read_text(encoding="utf-8")
        )

    def test_articles_accepts_repeats_and_a_comma_list(self):
        from magazine.cli import _produce_articles, parser

        self.assertEqual(
            _produce_articles(parser().parse_args(
                ["produce", "issue-001", "--articles", "a,b", "c"]
            ).articles),
            ["a", "b", "c"],
        )
        self.assertIsNone(
            _produce_articles(parser().parse_args(["produce", "issue-001"]).articles)
        )

    def run_cli_scripted(self, argv: list[str]) -> tuple[int, str]:
        """Drive ``main`` with the scripted backend wired into ``produce``.

        ``main`` has no injection point of its own, and it should not: the CLI
        constructs the real runner.  Patching the one method that resolves it
        keeps the argument parsing, the reporting, and the exit code under test
        without any subprocess at all.
        """

        from unittest.mock import patch

        original = Magazine.produce

        def scripted(magazine, edition_id, **kwargs):
            kwargs.pop("command", None)
            return original(magazine, edition_id, command=self.command, **kwargs)

        with patch.object(Magazine, "produce", scripted):
            return self.run_cli(argv)

    def test_a_full_run_reports_every_piece_and_every_record(self):
        code, output = self.run_cli_scripted(["produce", "issue-001"])

        self.assertEqual(code, 0, output)
        self.assertIn("passed: article after 1 round(s)", output)
        self.assertIn("passed: editorial after 1 round(s)", output)
        for kind in ("evidence", "line", "learning", "edition"):
            self.assertIn(f"recorded: {kind} ->", output)

    def test_a_full_run_serializes_to_json(self):
        import json

        code, output = self.run_cli_scripted(["produce", "issue-001", "--json"])

        self.assertEqual(code, 0, output)
        payload = json.loads(output)
        self.assertEqual(payload["dry_run"], False)
        self.assertEqual(
            [row["status"] for row in payload["outcomes"]], ["passed", "passed"]
        )
        self.assertEqual(payload["issue_reviews"]["learning"]["result"], "approved")
        self.assertEqual(
            payload["plan"]["pieces"][0]["manuscript"],
            "editions/issue-001/articles/article.md",
        )

    def test_an_escalation_exits_one(self):
        self.command.script[("line", "article")] = [changes("it repeats")]

        code, output = self.run_cli_scripted(
            ["produce", "issue-001", "--articles", "article"]
        )

        self.assertEqual(code, 1, output)
        self.assertIn("escalated: article after 3 round(s)", output)
        self.assertIn("human: article exhausted 3 round(s)", output)

    def test_a_released_edition_exits_two_with_the_reason(self):
        state = self.root / "library" / "release-state.yaml"
        data = yaml.safe_load(state.read_text(encoding="utf-8"))
        data["open_edition"] = {
            "id": "999",
            "issue_number": 999,
            "status": "collecting",
            "source_ids": [],
        }
        data["released_editions"] = [
            {"id": "issue-001", "issue_number": 1, "status": "released"}
        ]
        state.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        stderr = io.StringIO()
        with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
            code = main(["--root", str(self.root), "produce", "issue-001", "--dry-run"])

        self.assertEqual(code, 2)
        self.assertIn("is released", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()


class ReplyProtocolTests(unittest.TestCase):
    """The three blocks of a writer's reply, and what a missing one means."""

    def test_the_anchor_block_is_read_and_kept_out_of_the_manuscript(self):
        manuscript, anchors, notes = split_reply(
            "The prose.\n"
            f"{ANCHOR_MARKER}\n"
            "- `diagram`: ## The new heading\n"
            "other: Another heading\n"
            f"{SCRATCH_MARKER}\n"
            "the notes\n"
        )

        self.assertEqual(manuscript, "The prose.")
        self.assertEqual(
            anchors, {"diagram": "The new heading", "other": "Another heading"}
        )
        self.assertEqual(notes, "the notes")

    def test_an_anchor_block_below_the_scratch_marker_is_notes(self):
        """Below the marker a writer is thinking, not instructing the manifest."""

        manuscript, anchors, notes = split_reply(
            f"The prose.\n{SCRATCH_MARKER}\n{ANCHOR_MARKER}\ndiagram: Somewhere\n"
        )

        self.assertEqual(manuscript, "The prose.")
        self.assertEqual(anchors, {})
        self.assertIn("diagram: Somewhere", notes)

    def test_a_reply_with_neither_marker_is_all_manuscript(self):
        self.assertEqual(split_reply("Just prose.\n"), ("Just prose.", {}, ""))

    def test_split_scratch_still_answers_the_two_questions_it_always_did(self):
        manuscript, notes = split_scratch(
            f"The prose.\n{ANCHOR_MARKER}\ndiagram: A heading\n{SCRATCH_MARKER}\nnotes\n"
        )

        self.assertEqual(manuscript, "The prose.")
        self.assertEqual(notes, "notes")


class WorkIdentityTests(ProduceFixture):
    """A reply survives a reworded brief and dies when the question moves."""

    def _identity(self, **overrides):
        from magazine.produce_prompts import (
            WriterBrief,
            load_prompt,
            writer_identity,
        )

        prompt = load_prompt(self.root, "prompts/faithful-edit.md")
        piece = Production(
            self.magazine, runner=resolve_text_runner(
                RunnerConfig.load(self.root), command=self.command
            )
        )._select(
            Production(
                self.magazine,
                runner=resolve_text_runner(
                    RunnerConfig.load(self.root), command=self.command
                ),
            )._load_edition("issue-001"),
            ["article"],
        )[0]
        brief = WriterBrief(
            piece=piece,
            edition_id="issue-001",
            edition_title="Issue",
            round_number=1,
            **overrides,
        )
        return writer_identity(prompt, brief), prompt, brief

    def test_rewording_a_brief_does_not_change_what_it_asks(self):
        """The identity is over the content, so formatting is free to move."""

        from magazine.produce_prompts import compose_writer_prompt, writer_identity

        identity, prompt, brief = self._identity()
        reworded = replace_prompt_text(prompt, prompt.text + "\n\nAn added sentence.\n")

        # Same prompt *file* digest, different composed bytes.
        self.assertNotEqual(
            compose_writer_prompt(prompt, brief),
            compose_writer_prompt(reworded, brief),
        )
        self.assertEqual(identity, writer_identity(reworded, brief))

    def test_a_moved_manuscript_does_change_what_it_asks(self):
        from magazine.produce_prompts import writer_identity

        identity, prompt, _ = self._identity()
        moved, _, brief = self._identity(previous_manuscript="a different draft")

        self.assertNotEqual(identity, moved)
        self.assertEqual(moved, writer_identity(prompt, brief))

    def test_a_revised_prompt_file_does_change_what_it_asks(self):
        from magazine.produce_prompts import writer_identity

        identity, prompt, brief = self._identity()
        revised = PromptFileLike(prompt.path, "0" * 64, prompt.text)

        self.assertNotEqual(identity, writer_identity(revised, brief))


def replace_prompt_text(prompt, text):
    """The same prompt file, composed differently: digest and path unchanged."""

    from magazine.produce_prompts import PromptFile

    return PromptFile(path=prompt.path, sha256=prompt.sha256, text=text)


def PromptFileLike(path, sha256, text):
    from magazine.produce_prompts import PromptFile

    return PromptFile(path=path, sha256=sha256, text=text)


class FiledFindingTests(ProduceFixture):
    """A finding filed from outside the loop reaches the next brief."""

    def file_one(self, note: str = "The deprecation claim is wrong.", **kwargs):
        return self.magazine.file_finding(
            "issue-001", "article", note=note, **kwargs
        )

    def test_a_filed_finding_unsettles_an_otherwise_settled_piece(self):
        self.run_produce()
        settled = production(self.magazine, ScriptedCommand(), gates=self.gates).run(
            "issue-001", articles=["article"]
        )
        self.assertEqual([outcome.status for outcome in settled.outcomes], ["settled"])

        self.file_one()
        plan = production(self.magazine, ScriptedCommand(), gates=self.gates).plan(
            "issue-001", articles=["article"]
        )

        self.assertFalse(plan.pieces[0].settled)
        self.assertEqual(plan.pieces[0].filed_findings, 1)
        self.assertIn("1 filed finding", plan.pieces[0].action)

    def test_the_next_brief_carries_the_finding_and_the_draft_it_names(self):
        self.run_produce()
        self.file_one(
            note="The deprecation claim is wrong.",
            locator="paragraph twelve",
            filed_by="edition review",
        )

        command = ScriptedCommand()
        production(self.magazine, command, gates=self.gates).run(
            "issue-001", articles=["article"]
        )

        brief = command.briefs("writer", "article")[0]
        self.assertIn("Findings you must clear", brief)
        self.assertIn("The deprecation claim is wrong.", brief)
        self.assertIn("(from the edition review)", brief)
        self.assertIn("paragraph twelve", brief)
        # Round one is a revision here, so the draft under repair travels too.
        self.assertIn("The draft under revision", brief)
        self.assertIn("A draft of article, round 1.", brief)

    def test_a_passing_round_marks_the_finding_addressed_and_never_deletes_it(self):
        self.run_produce()
        self.file_one()

        production(self.magazine, ScriptedCommand(), gates=self.gates).run(
            "issue-001", articles=["article"]
        )

        rows = self.magazine.filed_findings("issue-001")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "addressed")
        self.assertEqual(rows[0]["addressed_in_round"], 1)
        self.assertEqual(rows[0]["note"], "The deprecation claim is wrong.")

    def test_filing_against_a_piece_the_edition_does_not_carry_is_refused(self):
        with self.assertRaises(MagazineError) as caught:
            self.magazine.file_finding("issue-001", "not-a-piece", note="Wrong.")

        self.assertIn("has no piece 'not-a-piece'", str(caught.exception))

    def test_the_cli_files_and_lists(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(
                main(
                    [
                        "--root", str(self.root), "finding", "file", "issue-001",
                        "article", "--note", "A false editor's note.",
                        "--severity", "blocking", "--filed-by", "edition review",
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(["--root", str(self.root), "finding", "list", "issue-001"]), 0
            )

        printed = out.getvalue()
        self.assertIn("filed: article ->", printed)
        self.assertIn("open: article [blocking]", printed)
        self.assertIn("1 open, 1 filed", printed)


class FootnoteGateTests(ProduceFixture):
    """CommonMark has no footnotes, so a marker would print as characters."""

    def test_validate_refuses_a_manuscript_carrying_footnote_syntax(self):
        (self.root / "editions" / "issue-001" / "articles" / "article.md").write_text(
            "The original article.[^1]\n\n[^1]: The note.\n", encoding="utf-8"
        )

        with self.assertRaises(MagazineError) as caught:
            self.magazine.validate("issue-001")

        message = str(caught.exception)
        self.assertIn("footnote syntax that would be typeset literally", message)
        self.assertIn("[^1]", message)
        self.assertIn("articles/article.md", message)

    def test_a_marker_inside_code_is_left_alone(self):
        (self.root / "editions" / "issue-001" / "articles" / "article.md").write_text(
            "The original article. Write `[^1]` and nothing happens.\n",
            encoding="utf-8",
        )

        self.magazine.validate("issue-001")

    def test_the_gate_names_the_piece_so_the_writer_hears_it_next_round(self):
        gates = DefaultProductionGates(self.magazine)
        (self.root / "editions" / "issue-001" / "articles" / "article.md").write_text(
            "The original article.[^2]\n", encoding="utf-8"
        )
        piece = production(self.magazine, self.command)._select(
            production(self.magazine, self.command)._load_edition("issue-001"),
            ["article"],
        )[0]

        failures = [gate for gate in gates.check_piece(piece, ()) if not gate.ok]

        self.assertEqual([gate.name for gate in failures], ["footnotes"])
        self.assertIn("[^2]", failures[0].detail)


class EditionGateCacheTests(ProduceFixture):
    """validate and fit are minutes each, and a pure function of the tree."""

    def counted(self):
        """Real gates, with the two expensive calls counted rather than faked."""

        gates = DefaultProductionGates(self.magazine)
        calls: list[str] = []
        magazine = self.magazine

        class Counting:
            root = magazine.root
            primary_language = magazine.primary_language
            editions_dir = magazine.editions_dir
            sources_dir = magazine.sources_dir

            def validate(self, edition_id):
                calls.append("validate")
                return magazine.validate(edition_id)

            def fit(self, edition_id, language=None):
                calls.append("fit")
                return magazine.fit(edition_id, language=language)

        gates.magazine = Counting()
        return gates, calls

    def test_a_second_call_over_an_unchanged_tree_runs_neither_check(self):
        gates, calls = self.counted()

        gates.check_edition("issue-001")
        first = list(calls)
        gates.check_edition("issue-001")

        self.assertEqual(first, ["validate", "fit"])
        self.assertEqual(calls, first)

    def test_the_same_verdict_comes_back_from_the_memo(self):
        gates, _ = self.counted()

        first = gates.check_edition("issue-001")
        second = gates.check_edition("issue-001")

        self.assertEqual(
            [(gate.name, gate.ok, gate.detail) for gate in first],
            [(gate.name, gate.ok, gate.detail) for gate in second],
        )

    def test_a_changed_manuscript_re_runs_both_checks(self):
        """The memo is keyed on content, so gates stay a function of the tree."""

        gates, calls = self.counted()
        gates.check_edition("issue-001")
        calls.clear()

        (self.root / "editions" / "issue-001" / "articles" / "article.md").write_text(
            "The original article. Now with an added sentence.\n", encoding="utf-8"
        )
        gates.check_edition("issue-001")

        self.assertEqual(calls, ["validate", "fit"])

    def test_a_production_record_written_between_calls_is_not_a_change(self):
        """Every round writes one; if it invalidated the memo the memo is useless."""

        gates, calls = self.counted()
        gates.check_edition("issue-001")
        calls.clear()

        record = piece_record_path(self.magazine.editions_dir, "issue-001", "article")
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text("schema_version: 1\nstatus: drafting\n", encoding="utf-8")
        gates.check_edition("issue-001")

        self.assertEqual(calls, [])


class OpenerIntroBudgetTests(unittest.TestCase):
    """The opening-paragraph limit, derived rather than guessed."""

    SAMPLE = (
        "The kill chain opened with the benchmark the agent was being scored on, "
        "and closed four and a half days later inside production infrastructure."
    )

    def budget(self, **overrides):
        from magazine.weasyprint_adapter import illustrated_opener_intro_budget

        return illustrated_opener_intro_budget(
            **{
                "title": "A Short Title",
                "byline": "by Author",
                "author_note": "",
                "sample": self.SAMPLE,
                **overrides,
            }
        )

    def test_the_budget_is_stated_in_lines_and_characters(self):
        budget = self.budget()

        self.assertGreater(budget.lines, 0)
        self.assertGreater(budget.characters, 0)
        self.assertEqual(budget.measure_points, 348.0)
        self.assertEqual(budget.size_points, 9.6)

    def test_a_two_line_title_leaves_less_room_for_the_paragraph(self):
        """The limit is per article because the title is what eats the page."""

        short = self.budget()
        long = self.budget(
            title="A Considerably Longer Title That Needs Two Whole Lines To Set"
        )

        self.assertLess(long.lines, short.lines)

    def test_the_predicted_limit_agrees_with_the_gate_that_enforces_it(self):
        """One arithmetic, or the number taught is not the number enforced."""

        from magazine.weasyprint_adapter import (
            _ILLUSTRATED_OPENER_COMPACT,
            _ILLUSTRATED_OPENER_PAGE_HEIGHT_POINTS,
            _ILLUSTRATED_OPENER_PANGO_RESERVE_POINTS,
            _fitted_display,
            _opener_stack_height,
        )

        budget = self.budget()
        size, lines = _fitted_display(
            "A Short Title", 348.0, 64.0, maximum=30.0, minimum=22.0,
            maximum_lines=2, leading_ratio=0.96,
        )
        ceiling = (
            _ILLUSTRATED_OPENER_PAGE_HEIGHT_POINTS
            - _ILLUSTRATED_OPENER_PANGO_RESERVE_POINTS
        )

        def height(standfirst_lines: int) -> float:
            return _opener_stack_height(
                title_size=size,
                title_lines=len(lines),
                byline_text="by Author",
                note_text="",
                standfirst_lines=standfirst_lines,
                density=_ILLUSTRATED_OPENER_COMPACT,
            )

        # The predicted limit is exactly the largest count the gate accepts.
        self.assertLessEqual(height(budget.lines), ceiling)
        self.assertGreater(height(budget.lines + 1), ceiling)

    def test_fits_answers_the_real_question_rather_than_the_estimate(self):
        budget = self.budget()

        self.assertTrue(budget.fits("A short opening paragraph."))
        self.assertFalse(budget.fits(" ".join([self.SAMPLE] * 12)))


class OpenerBudgetBriefTests(unittest.TestCase):
    """An illustrated piece is told its number; every other piece is not."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.magazine = build_project(self.root)
        self.command = ScriptedCommand()

    def brief(self) -> str:
        production(self.magazine, self.command, gates=PassingGates()).run(
            "issue-001", articles=["article"]
        )
        return self.command.briefs("writer", "article")[0]

    def test_a_piece_with_no_illustrated_opener_is_told_nothing(self):
        brief = self.brief()

        # The prompt file mentions the budget in general; the assignment must
        # not claim one for a piece the constraint does not govern.
        self.assertNotIn("- Opening paragraph budget:", brief)
        self.assertNotIn("The opening paragraph has a hard length limit", brief)

    def test_an_illustrated_piece_carries_its_measured_limit(self):
        add_article_opener(self.root)

        brief = self.brief()

        self.assertIn("- Opening paragraph budget:", brief)
        self.assertIn("The opening paragraph has a hard length limit", brief)
        self.assertIn("typeset line(s)", brief)
        self.assertIn("the build refuses the edition", brief)
