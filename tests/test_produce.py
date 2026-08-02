"""The produce pipeline: its order, its boundaries, and its refusals.

Nothing here runs a model.  Every call goes through a scripted
:class:`CommandRunner` that answers by role, which is also how the tests can
assert the two things that actually matter about this pipeline: *which roles
were asked at all*, and *what each of them was shown*.  Both are only visible
in the calls the fake received -- a lens the staging skipped is a brief that was
never composed, and a context constraint can only be tested by reading the
prompt that was sent.

Nothing here names the lens set either.  It is read off
:data:`~magazine.produce_graph.PIECE_JUDGE_LENSES`, because a suite that listed
the lenses would pass unchanged on the day a lens was declared and never
dispatched, which is exactly the failure the single declaration exists to make
impossible.

``[runner] codex_binary`` points at ``/bin/echo`` so backend resolution
succeeds without Codex installed; the fake intercepts the invocation long
before anything is executed.
"""

import hashlib
import io
import re
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
    Breach,
    DefaultProductionGates,
    GateResult,
    Production,
    ProductionGates,
)
from magazine.produce_graph import (
    BENCH_REVIEW_KINDS,
    EDITION_JUDGE_KIND,
    PIECE_JUDGE_KINDS,
    PIECE_JUDGE_LENSES,
    lens_applies,
)
from magazine.produce_prompts import (
    ANCHOR_MARKER,
    HOUSE_STYLE_PATH,
    JUDGE_PROMPTS,
    SCRATCH_MARKER,
    ProduceError,
    SourceBlindReviewInput,
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


# Prose to measure an opener budget against, and to cut candidate paragraphs
# out of.  Long enough that its word-length distribution is a real one, and
# deliberately mixed: the short Anglo-Saxon words that pack a line tightly, and
# the polysyllables and hyphenated compounds that end one early.  A fixture of
# uniformly short words would let an optimistic estimate pass.
OPENER_PROSE = (
    "The infrastructure that surrounds a model has become the interesting "
    "part of the problem, and the reason is unglamorous: the model is bought "
    "and the surroundings are built. Retrieval, evaluation, orchestration, "
    "observability and the unromantic business of retrying a failed call all "
    "sit outside the weights, and all of them are where a deployment actually "
    "succeeds or quietly stops working.\n\n"
    "Consider evaluation. A team that cannot say whether last week's change "
    "helped is not engineering, it is redecorating, and the instrumentation "
    "that answers the question is neither cheap nor interesting to build. It "
    "is nonetheless the difference between a system that improves and one "
    "that merely changes. The same is true of retrieval: the embedding model "
    "is a commodity and the chunking strategy is not.\n\n"
    "What follows from this is a reallocation of attention rather than a new "
    "technology. The organisations doing well are not the ones with "
    "privileged access to capability; they are the ones that treated "
    "reliability, measurement and unremarkable operational discipline as "
    "first-class engineering concerns rather than as overhead to be minimised "
    "once the demonstration worked.\n\n"
    "None of this is a counsel of despair about models. Capability keeps "
    "arriving, and arriving faster than the surrounding systems can absorb "
    "it, which is precisely the argument: the bottleneck moved. A team that "
    "spends another quarter waiting for a better model, when its own "
    "evaluation harness cannot detect a regression, is optimising the half of "
    "the problem somebody else is already solving for it.\n"
)


def prose_windows(sample: str, limit: int, *, step: int = 3) -> list[str]:
    """Every ``limit``-character paragraph that can be cut from ``sample``.

    Cut at word boundaries, from a sliding start, and only where the sample
    had enough words left to reach within a word of the limit -- a short tail
    would pass trivially and prove nothing.  Sliding the start is the point:
    the same prose broken in a different place wraps differently, and that
    difference is exactly what a character count cannot see.
    """

    words = " ".join(sample.split()).split()
    windows: list[str] = []
    for start in range(0, max(len(words) - 4, 1), step):
        chunk: list[str] = []
        total = 0
        for word in words[start:]:
            length = len(word) + (1 if chunk else 0)
            if total + length > limit:
                break
            chunk.append(word)
            total += length
        if total >= limit - 12:
            windows.append(" ".join(chunk))
    return windows


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


REPO = Path(__file__).resolve().parents[1]


def finding(
    note: str,
    *,
    severity: str = "major",
    category: str = "duplication",
    disposition: str = "fix",
    **extra,
) -> dict:
    """One authored finding, always carrying the field that replaced the cap.

    ``disposition`` is required of every authored structured finding, on every
    lens, because a parser that lets one through without it is back to the
    severity ceiling that certified a piece clean while twelve lowercase
    sentence openings sat inside it.  Every fake verdict in this suite goes
    through here so that no fixture can quietly reintroduce that hole.
    """

    row = {
        "severity": severity,
        "category": category,
        "locator": "- | a sentence | 1",
        "repair_from": "- | an earlier sentence | 1",
        "disposition": disposition,
        "note": note,
        "suggestion": "an advisory replacement line",
    }
    row.update(extra)
    return row


def verdict(result: str = "approved", **extra) -> str:
    document = {"result": result, "findings": [], "notes": "read it", **extra}
    return yaml.safe_dump(document, sort_keys=False)


def changes(
    note: str,
    *,
    category: str = "duplication",
    severity: str = "major",
    disposition: str = "fix",
) -> str:
    return verdict(
        "changes_required",
        findings=[
            finding(
                note,
                severity=severity,
                category=category,
                disposition=disposition,
            )
        ],
    )


def blocks(note: str, *, category: str = "thin_derivation") -> str:
    """A verdict carrying a ``blocking`` finding: the thing that skips a stage.

    The staging skips are conditioned on severity, not on the result, so a
    fixture that only said ``changes_required`` would exercise none of them.
    """

    return changes(note, category=category, severity="blocking")


# Which lenses read which piece, taken from the declaration rather than typed
# out again.  A test that listed them would pass unchanged the day a lens was
# added and never dispatched, which is the failure the single tuple exists to
# make impossible.
ARTICLE_LENSES = tuple(
    lens.kind
    for lens in PIECE_JUDGE_LENSES
    if lens_applies(lens, piece_id="article", content_mode="faithful_edit")
)
EDITORIAL_LENSES = tuple(
    lens.kind
    for lens in PIECE_JUDGE_LENSES
    if lens_applies(lens, piece_id="editorial", content_mode="original_editorial")
)


class ScriptedCommand:
    """A ``CommandRunner`` that answers by role and records every brief.

    Roles are recognised from the prompt file each brief opens with, which is
    the same thing a human reading the transcript would key on.  Replies come
    from ``script[(role, piece_id)]``, consumed in order and repeating the last
    entry once exhausted, so a test scripts only the rounds it cares about.

    The markers are read off the committed prompt files rather than typed here.
    The bench went from two judges to seven in one edit to
    :data:`~magazine.produce_graph.PIECE_JUDGE_LENSES`, and a hardcoded table of
    headings in the fake would have been the one place that edit did not reach:
    an unrecognised judge brief classifies as ``writer`` and the failure lands
    somewhere else entirely.
    """

    ROLES = tuple(
        (
            (REPO / relative).read_text(encoding="utf-8").splitlines()[0].strip(),
            kind,
        )
        for kind, relative in JUDGE_PROMPTS.items()
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


def build_project(root: Path, *, body: str = EXTRACTION_BODY) -> Magazine:
    make_project(root)
    # Produce composes its briefs from the project's own ``prompts/``, so the
    # fixture is a project with prompts in it.  Copying rather than pointing at
    # the repository's also lets a test move a prompt without touching it.
    shutil.copytree(REPO / "prompts", root / "prompts")
    # ``craft`` and ``edition`` embed the house-style corpus in their briefs
    # rather than citing its path, because under the cooperative backend the
    # worker may have no repository to open.  It is loaded through the same
    # prompt loader, so a fixture without it fails the way a missing prompt
    # file does -- by name, halfway through a run.
    (root / HOUSE_STYLE_PATH).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / HOUSE_STYLE_PATH, root / HOUSE_STYLE_PATH)
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


EXPLAINER_ONLY = "The explainer's source counted nineteen distinct call shapes."
EXPLAINER_BODY = (
    "An explainer source.\n"
    f"{EXPLAINER_ONLY}\n"
    "It goes on to describe the handshake in unhelpful detail.\n"
)


def add_explainer(root: Path, *, piece_id: str = "nutshell") -> None:
    """Give the fixture edition the one piece ``teaching`` reads.

    ``teaching`` covers explainers, which is a coverage of exactly one piece in
    a real issue and of none at all in the default fixture.  An edition without
    one is a legitimate edition -- the lens simply does not run -- but it is not
    the edition the bench was designed around, so anything that has to see the
    whole seven-lens traversal builds this instead.
    """

    from test_manifest import add_extraction, add_source

    add_source(root, "source-explainer", body=EXPLAINER_BODY)
    digest = add_extraction(root, source_id="source-explainer", body=EXPLAINER_BODY)
    manifest_path = root / "editions" / "issue-001" / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["articles"].append(
        {
            "id": piece_id,
            "title": "A Protocol in a Nutshell",
            "short_title": "Nutshell",
            "opener_variant": "split_axis",
            # The Teacher writes in the magazine's voice, so the byline is the
            # editors' and there is no author biography to carry.
            "author": "The editors",
            "content_mode": "in_a_nutshell",
            "source_ids": ["source-explainer"],
            "source_body_sha256": digest,
            "manuscript": f"editions/issue-001/articles/{piece_id}.md",
            "key_ideas": ["The first idea.", "The second.", "The third."],
        }
    )
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    (root / "editions" / "issue-001" / "articles" / f"{piece_id}.md").write_text(
        "An explainer source.\n", encoding="utf-8"
    )


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
        # The order is the contract: writer, then every lens that reads that
        # piece, per piece; the editorial after the pieces it is grounded in;
        # and the one whole-issue lens, once, at the end.  Lenses inside a stage
        # overlap, so their order relative to each other is scheduling and is
        # deliberately not asserted -- but *which* of them ran is.
        roles = self.command.roles()
        article, editorial = len(ARTICLE_LENSES), len(EDITORIAL_LENSES)
        self.assertEqual(roles[0], "writer")
        self.assertEqual(sorted(roles[1 : 1 + article]), sorted(ARTICLE_LENSES))
        self.assertEqual(roles[1 + article], "writer")
        self.assertEqual(
            sorted(roles[2 + article : 2 + article + editorial]),
            sorted(EDITORIAL_LENSES),
        )
        self.assertEqual(roles[2 + article + editorial :], [EDITION_JUDGE_KIND])
        self.assertEqual(
            [piece for _, piece, _ in self.command.calls][: 2 + article + editorial],
            ["article"] * (1 + article) + ["editorial"] * (1 + editorial),
        )
        # Every bench kind but ``teaching``: it binds explainers only, and this
        # fixture carries no ``in_a_nutshell`` piece for it to read.
        self.assertEqual(
            set(result.recorded), set(BENCH_REVIEW_KINDS) - {"teaching"}
        )
        for kind in result.recorded:
            self.assertTrue(
                (self.root / "editions" / "issue-001" / "reviews" / f"{kind}.yaml").is_file(),
                kind,
            )

    def test_the_retired_lenses_are_never_dispatched_again(self):
        """``line`` and ``learning`` are gone, and gone means never called.

        Both names survived in half a dozen tables after the design retired
        them, and a name that is still dispatchable is a call somebody still
        pays for.  Asserting on the roles the fake was actually asked for is the
        only place that can be seen.
        """

        self.run_produce()

        for retired in ("line", "learning", "manager_run_a"):
            self.assertNotIn(retired, self.command.roles())
        self.assertNotIn("line", PIECE_JUDGE_KINDS)
        self.assertNotIn("learning", PIECE_JUDGE_KINDS)

    def test_the_gates_run_before_any_judge(self):
        order: list[str] = []
        self.gates.check_piece = lambda piece, extractions: (
            order.append(f"gate:{piece.id}") or (GateResult("scripted", True),)
        )
        self.command.hook = lambda role, piece, prompt: order.append(f"{role}:{piece}")

        self.run_produce()

        self.assertEqual(order[:2], ["writer:article", "gate:article"])
        # Stage 1's two lenses overlap, so their order between themselves is not
        # the contract; that they both follow the gate is.
        self.assertEqual(
            sorted(order[2:4]), ["mechanics:article", "worth:article"]
        )

    def test_the_editorial_is_drafted_from_the_articles_and_bound_as_editorial(self):
        self.run_produce()

        brief = self.command.briefs("writer", "editorial")[0]
        self.assertIn("The edition's pieces, in running order", brief)
        self.assertIn("A draft of article, round 1.", brief)
        # ``craft`` is a whole-pieces lens, so its record binds the editorial as
        # well as the articles.
        craft_record = yaml.safe_load(
            (self.root / "editions" / "issue-001" / "reviews" / "craft.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(set(craft_record["articles"]), {"article", "editorial"})


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
        for role in ARTICLE_LENSES:
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


class SourceBlindBoundaryTests(ProduceFixture):
    """Which lens may see the source is an assignment constraint, not a habit.

    ``prompts/README.md`` states it as one: every check about the relationship
    between manuscript and source belongs to a lens that reads both, and every
    check answerable from the manuscript alone belongs to a lens that reads only
    the manuscript.  The old broad judge was forbidden the source *and* asked
    whether the headings mirrored the source's table of contents, and it duly
    answered a question it could not see -- wrongly, and under an approval.
    """

    def test_a_blind_lens_is_not_given_the_source_and_a_reading_lens_is(self):
        self.run_produce(articles=["article"])

        for lens in PIECE_JUDGE_LENSES:
            if not lens_applies(
                lens, piece_id="article", content_mode="faithful_edit"
            ):
                continue
            with self.subTest(lens=lens.kind):
                brief = self.command.briefs(lens.kind, "article")[0]
                if lens.reads_source:
                    self.assertIn(SOURCE_ONLY, brief)
                else:
                    self.assertNotIn(SOURCE_ONLY, brief)
                    self.assertIn(
                        "source extraction is deliberately withheld", brief
                    )

    def test_the_input_type_has_nowhere_to_put_a_source(self):
        """The prohibition is structural, not a sentence a caller may ignore.

        One type serves all three blind lenses precisely so that there is one
        place, rather than three, where a future edit could add an
        ``extractions`` field to a lens that must not have one.
        """

        fields = set(SourceBlindReviewInput.__dataclass_fields__)
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
                label="craft lens",
            )
        # A faithful_edit manuscript is the source's sentences, and carrying it
        # is the whole point of the brief.  That must not read as a leak.
        assert_source_withheld(
            f"a brief carrying {SOURCE_ONLY}",
            [extraction],
            manuscript=SOURCE_ONLY,
            label="craft lens",
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
                    label="craft lens",
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
                        label="craft lens",
                    )
                self.assertIn("forbidden the source", str(raised.exception))


class LiveJudgeRoundTripTests(ProduceFixture):
    """A round driven end to end over a realistically shaped source.

    Every other test in this file runs on ``EXTRACTION_BODY``, whose three
    short lines no fixture manuscript repeats, so the blind lenses' guard was
    never asked the question round one of a real run asks it first.  It said
    no, and the run died there -- which meant no judge had ever run, and every
    step after the guard was untested against a live pipeline: a verdict
    parsed, written into the round record, and carried into the next writer's
    brief.  This class walks that path on a source that would have failed.
    """

    BODY = WRAPPED_SOURCE

    def setUp(self):
        super().setUp()
        # A faithful manuscript: the source's own sentences, reflowed.  Round
        # two returns a *different* one, because a reviser who hands back the
        # bytes he was given has moved nothing, and the re-run rule then
        # correctly carries every round-one verdict forward untouched -- see
        # ``CarriedVerdictTests``.  A fixture that repeated its draft would
        # therefore loop to escalation and prove nothing about revision.
        self.command.script[("writer", "article")] = [
            f"{reflow(WRAPPED_SOURCE)}\n{SCRATCH_MARKER}\nthe claim ladder",
            f"{reflow(WRAPPED_SOURCE)}\nThe repair.\n{SCRATCH_MARKER}\nthe claim ladder",
        ]

    def test_a_faithful_manuscript_reaches_every_lens(self):
        result = self.run_produce(articles=["article"])

        self.assertEqual(result.outcomes[0].status, "passed")
        shape_brief = self.command.briefs("shape", "article")[0]
        self.assertIn("it is the volume, at machine speed", shape_brief)
        self.assertIn("source extraction is deliberately withheld", shape_brief)

    def test_a_verdict_reaches_the_record_and_the_next_writer_s_brief(self):
        self.command.script[("shape", "article")] = [
            changes("the kill chain is told twice"),
            verdict("approved"),
        ]

        result = self.run_produce(articles=["article"])

        outcome = result.outcomes[0]
        self.assertEqual((outcome.status, outcome.rounds), ("passed", 2))
        first, second = self.record("article")["rounds"]
        # Parsed, and parsed into the record rather than merely counted.  A
        # ``major`` finding does not skip a stage, so every applicable lens ran.
        self.assertEqual(first["result"], "changes_required")
        self.assertEqual(set(first["judges"]), set(ARTICLE_LENSES))
        self.assertEqual(first["judges"]["shape"]["result"], "changes_required")
        self.assertEqual(
            [entry["note"] for entry in first["judges"]["shape"]["findings"]],
            ["the kill chain is told twice"],
        )
        self.assertEqual(first["judges"]["evidence"]["result"], "approved")
        self.assertEqual(second["judges"]["shape"]["result"], "approved")
        # And carried forward: a finding the writer never sees is not a loop.
        brief = self.command.briefs("writer", "article")[1]
        self.assertIn("### Must fix", brief)
        self.assertIn("[major] duplication (shape)", brief)
        self.assertIn("the kill chain is told twice", brief)


class ParallelJudgeTests(ProduceFixture):
    def test_the_lenses_of_one_stage_overlap(self):
        """Proved by a barrier: a serial pipeline can never clear it."""

        barrier = threading.Barrier(2, timeout=10)
        reached: list[str] = []

        def hook(role, piece, prompt):
            if role in ("evidence", "shape"):
                reached.append(role)
                barrier.wait()

        self.command.hook = hook

        self.run_produce(articles=["article"])

        self.assertEqual(sorted(reached), ["evidence", "shape"])

    def test_results_come_back_in_a_fixed_order_whatever_the_schedule(self):
        """Stage order, then repair order inside a stage; never thread order."""

        self.command.script[("evidence", "article")] = [changes("a fact moved")]
        self.command.script[("shape", "article")] = [changes("a sentence repeats")]

        self.run_produce(articles=["article"])

        round_one = self.record("article")["rounds"][0]
        self.assertEqual(
            list(round_one["judges"]),
            ["worth", "mechanics", "evidence", "shape", "craft"],
        )


class RevisionTests(ProduceFixture):
    def test_a_piece_that_fails_once_then_passes(self):
        self.command.script[("craft", "article")] = [
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
        self.command.script[("craft", "article")] = [
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
        self.command.script[("craft", "article")] = [
            changes("the second example repeats the first"),
            verdict("approved"),
        ]

        self.run_produce(articles=["article"])

        second = self.command.briefs("writer", "article")[1]
        self.assertIn("suggestion (advice, not the obligation)", second)
        self.assertIn(
            "judged on whether the defect survived, never on whether you", second
        )

    def test_three_rounds_then_escalation_with_every_finding_accumulated(self):
        self.command.script[("evidence", "article")] = [
            changes("round one number is wrong", category="number_or_name_error")
        ]
        self.command.script[("craft", "article")] = [changes("round one repeats")]

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
        # An escalated piece stops the run: the whole-issue lens reads a
        # finished issue, and this one is not.
        self.assertNotIn(EDITION_JUDGE_KIND, self.command.roles())
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


class EditionLensBoundaryTests(ProduceFixture):
    """The one lens that may see more than one piece, and what it is handed."""

    def test_the_issue_lens_reads_every_piece_and_the_house_style(self):
        self.run_produce()

        brief = self.command.briefs(EDITION_JUDGE_KIND)[0]
        self.assertIn("A draft of article, round 1.", brief)
        self.assertIn("A draft of editorial, round 1.", brief)
        self.assertIn("The house style corpus", brief)
        self.assertIn(
            (self.root / "docs" / "WRITING_RULES.md")
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()[0],
            brief,
        )
        # It judges the pieces against each other, never against their sources.
        self.assertNotIn(SOURCE_ONLY, brief)

    def test_it_runs_once_after_every_piece_and_never_per_piece(self):
        self.run_produce()

        self.assertEqual(len(self.command.briefs(EDITION_JUDGE_KIND)), 1)
        roles = self.command.roles()
        self.assertEqual(roles.index(EDITION_JUDGE_KIND), len(roles) - 1)


class StagingTests(ProduceFixture):
    """Which lenses run, and which are skipped, and why the two skips differ.

    ``prompts/README.md`` gives the staging a cost rationale rather than a
    tidiness one, and the rationale is what the two different skips encode.  A
    ``worth`` blocking finding stops the piece: craft notes on a paragraph that
    is about to be cut are wasted calls.  A blocking finding anywhere in stages
    1 or 2 stops stage 3 only, because craft is the lens most sensitive to text
    churn.  Mechanics blocking deliberately stops neither stage 2 nor the piece:
    its repairs are local and do not move what evidence and shape read.

    Every assertion here is on the briefs the fake runner was actually asked
    for, because a skip that saved no call is not a skip.
    """

    def lenses_asked(self, piece_id: str = "article") -> list[str]:
        return [
            role
            for role, piece, _ in self.command.calls
            if piece == piece_id and role != "writer"
        ]

    def test_a_worth_blocking_finding_stops_stages_two_and_three(self):
        self.command.script[("worth", "article")] = [
            blocks("a 40% shorter paraphrase with every identifier stripped")
        ]

        self.run_produce(articles=["article"], max_rounds=1)

        # Stage 1 in full -- mechanics is not conditioned on worth -- and then
        # nothing.  Four calls a round, saved, for as long as the piece should
        # not exist at this length.
        self.assertEqual(sorted(self.lenses_asked()), ["mechanics", "worth"])
        for skipped in ("evidence", "shape", "craft", "teaching"):
            self.assertEqual(self.command.briefs(skipped, "article"), [], skipped)

    def test_a_worth_blocked_round_never_passes_on_the_lenses_that_did_run(self):
        """An unrun applicable lens is absent, and absent is never approving.

        The failure this prevents is quiet and total: a worth-blocked piece
        whose two stage-1 lenses both returned ``approved`` would pass with
        evidence, shape and craft having never read it.
        """

        self.command.script[("worth", "article")] = [
            verdict("approved", findings=[finding("blocking, under an approval",
                                                  severity="blocking")])
        ]

        with self.assertRaises(ProduceError) as raised:
            self.run_produce(articles=["article"], max_rounds=1)

        message = str(raised.exception)
        self.assertIn("did not run", message)
        self.assertIn("an unrun lens is absent, never approving", message)
        for skipped in ("craft", "evidence", "shape"):
            self.assertIn(skipped, message)

    def test_a_mechanics_blocking_finding_stops_stage_three_but_not_stage_two(self):
        """Its repairs are local; they do not move what evidence and shape read."""

        self.command.script[("mechanics", "article")] = [
            blocks("a subject-verb error in the standfirst", category="agreement")
        ]

        self.run_produce(articles=["article"], max_rounds=1)

        self.assertEqual(
            sorted(self.lenses_asked()),
            ["evidence", "mechanics", "shape", "worth"],
        )
        self.assertEqual(self.command.briefs("craft", "article"), [])

    def test_stage_three_runs_when_stages_one_and_two_found_nothing_blocking(self):
        """The skips have to be conditional, or they are just a shorter bench."""

        self.command.script[("evidence", "article")] = [
            changes("a qualification was dropped", category="unsupported_claim")
        ]

        self.run_produce(articles=["article"], max_rounds=1)

        # ``changes_required`` at ``major`` is not ``blocking``: the piece is
        # coming back, but nothing about it makes craft's reading worthless.
        self.assertEqual(sorted(self.lenses_asked()), sorted(ARTICLE_LENSES))
        self.assertEqual(len(self.command.briefs("craft", "article")), 1)

    def test_the_skip_is_the_round_s_and_the_next_round_asks_again(self):
        self.command.script[("worth", "article")] = [
            blocks("the piece does not pay for its length"),
            verdict("approved"),
        ]

        self.run_produce(articles=["article"], max_rounds=2)

        self.assertEqual(len(self.command.briefs("worth", "article")), 2)
        # Round one bought two calls; round two bought the whole bench.
        self.assertEqual(len(self.command.briefs("craft", "article")), 1)
        rounds = self.record("article")["rounds"]
        self.assertEqual(set(rounds[0]["judges"]), {"worth", "mechanics"})
        self.assertEqual(set(rounds[1]["judges"]), set(ARTICLE_LENSES))


class LensCoverageTests(ProduceFixture):
    """A lens that does not read a piece is never dispatched for it.

    Coverage is declared on the lens and read through
    :func:`~magazine.produce_graph.lens_applies`, so these assert the dispatch
    the declaration produces rather than restating the table.
    """

    def judge(self, *, content_mode: str | None = None, piece_id: str = "article",
              manuscript: str = "A draft of article, round 1.\n", carried=None):
        """Run one piece through the bench, without the drafting loop around it.

        Coverage is decided per piece from its ``content_mode``, so varying that
        one field is the whole experiment; going through the manifest instead
        would add an article, a source and an extraction to say the same thing,
        and the explainer's full traversal is proved end to end in
        ``test_produce_graph`` where the fixture carries one.  No model is
        reachable either way: the injected :class:`ScriptedCommand` answers
        every call.
        """

        from dataclasses import replace as _replace

        run = production(self.magazine, self.command, gates=self.gates)
        edition = run._load_edition("issue-001")
        piece = run._select(edition, [piece_id])[0]
        if content_mode is not None:
            piece = _replace(piece, content_mode=content_mode)
        return run._judge_piece(
            piece,
            run._extractions(piece),
            manuscript,
            edition,
            round_number=1,
            carried=carried or {},
        )

    def test_worth_is_never_asked_about_the_editorial(self):
        """It has no source of its own, so its worth question is the edition's.

        ``prompts/README.md`` routes it to ``edition``'s
        ``single_source_editorial`` and ``thin_derivation`` rather than leaving
        a lens to answer a ratio against a source that does not exist.
        """

        self.run_produce()

        self.assertEqual(self.command.briefs("worth", "editorial"), [])
        self.assertEqual(len(self.command.briefs("worth", "article")), 1)
        self.assertNotIn("worth", self.record("editorial")["rounds"][0]["judges"])

    def test_teaching_is_asked_only_about_the_explainer(self):
        verdicts = self.judge(content_mode="in_a_nutshell")

        self.assertIn("teaching", verdicts)
        self.assertEqual(len(self.command.briefs("teaching", "article")), 1)
        # And the explainer's reader gets the furniture and the source, which is
        # what a closed-book comprehension test is written from.
        brief = self.command.briefs("teaching", "article")[0]
        self.assertIn("The editor-authored furniture, in full", brief)
        self.assertIn(SOURCE_ONLY, brief)

    def test_teaching_is_not_asked_about_a_feature(self):
        """A closed-book comprehension test of a feature measures nothing."""

        verdicts = self.judge(content_mode="faithful_edit")

        self.assertNotIn("teaching", verdicts)
        self.assertEqual(self.command.briefs("teaching", "article"), [])
        self.assertEqual(set(verdicts), set(ARTICLE_LENSES))


class CarriedVerdictTests(ProduceFixture):
    """A lens re-runs only when its own declared inputs moved.

    The cache key is the lens's work identity -- the same digest the
    cooperative backend binds a stored reply to -- so "this answer is still
    current" means one thing whether it is asked of a reply on disk or of a
    verdict in a record.
    """

    def judge(self, *, manuscript: str, carried=None):
        run = production(self.magazine, self.command, gates=self.gates)
        edition = run._load_edition("issue-001")
        piece = run._select(edition, ["article"])[0]
        return run._judge_piece(
            piece,
            run._extractions(piece),
            manuscript,
            edition,
            round_number=1,
            carried=carried or {},
        )

    def test_an_unmoved_lens_costs_no_model_call_at_all(self):
        first = self.judge(manuscript="The draft, unchanged.\n")
        calls = len(self.command.calls)
        self.assertEqual(calls, len(ARTICLE_LENSES))

        second = self.judge(manuscript="The draft, unchanged.\n", carried=first)

        self.assertEqual(len(self.command.calls), calls)
        self.assertEqual(set(second), set(ARTICLE_LENSES))
        for kind in ARTICLE_LENSES:
            self.assertIs(second[kind], first[kind], kind)

    def test_every_carried_verdict_states_the_inputs_it_answered(self):
        """Without the key there is nothing to compare, and everything re-runs."""

        verdicts = self.judge(manuscript="The draft, unchanged.\n")

        for kind, entry in verdicts.items():
            with self.subTest(lens=kind):
                self.assertEqual(len(entry.inputs_sha256), 64, kind)
        self.assertEqual(
            len({entry.inputs_sha256 for entry in verdicts.values()}),
            len(verdicts),
            "two lenses sharing an identity would carry each other's answers",
        )

    def test_a_moved_manuscript_re_runs_every_lens_that_reads_it(self):
        first = self.judge(manuscript="The draft, unchanged.\n")
        calls = len(self.command.calls)

        self.judge(manuscript="The draft, revised.\n", carried=first)

        self.assertEqual(len(self.command.calls), calls + len(ARTICLE_LENSES))

    def test_the_re_run_key_reaches_the_round_record(self):
        """Carry-forward has to survive a crash, so the key is written down."""

        self.run_produce(articles=["article"])

        judges = self.record("article")["rounds"][0]["judges"]
        for kind in ARTICLE_LENSES:
            self.assertEqual(len(judges[kind]["inputs_sha256"]), 64, kind)


class RevisionBriefTests(ProduceFixture):
    """Seven finding sets in, one document out, and what the writer may see.

    Two rules from ``prompts/README.md`` are load-bearing here and neither is
    visible anywhere else.  The obligations are split into three *labelled*
    sections, because an ``editor_decision`` finding sent to a writer as a
    "must fix" is an instruction to breach ``docs/EDITORIAL_POLICY.md``.  And
    no score reaches the writer at all: the edition this bench was built to
    catch scored fives across it, so a number a writer can see is a number a
    writer can optimise.
    """

    MUST_FIX = "the same construction opens six sentences"
    MINOR = "a dead word in the third paragraph"
    EDITOR = "the author's own retained sentence has no main verb"

    def brief(self) -> str:
        self.command.script[("craft", "article")] = [
            verdict(
                "changes_required",
                findings=[
                    finding(
                        self.MUST_FIX,
                        category="repetition",
                        locator="- | six sentences | 1",
                    ),
                    finding(
                        self.MINOR,
                        severity="minor",
                        category="dead_words",
                        locator="- | a dead word | 1",
                    ),
                    finding(
                        self.EDITOR,
                        category="agreement",
                        disposition="editor_decision",
                        locator="- | the retained sentence | 1",
                    ),
                ],
                scores={"human_authorship": 5},
            ),
            verdict("approved"),
        ]
        self.run_produce(articles=["article"])
        return self.command.briefs("writer", "article")[1]

    @staticmethod
    def section(brief: str, title: str) -> str:
        """One labelled section of the composed brief, up to the next one."""

        head = f"### {title}"
        assert head in brief, f"{title} is not a section of the brief"
        rest = brief.split(head, 1)[1]
        return rest.split("\n### ", 1)[0]

    def test_the_brief_carries_the_three_labelled_sections(self):
        brief = self.brief()

        for title in ("Must fix", "Consider", "For the editor"):
            self.assertIn(f"### {title}", brief)
        self.assertIn(self.MUST_FIX, self.section(brief, "Must fix"))
        self.assertIn(self.MINOR, self.section(brief, "Consider"))

    def test_an_editor_decision_lands_with_the_editor_and_never_in_must_fix(self):
        """Routing, not a severity ceiling: it is a major finding, printed as one.

        The old bench capped a finding on the author's retained text at
        ``minor`` and then reported the piece clean.  The finding now keeps its
        true severity and changes *hands*, and a writer who fixed it would
        breach the policy that put it there.
        """

        brief = self.brief()

        editor = self.section(brief, "For the editor")
        self.assertIn(self.EDITOR, editor)
        self.assertIn("[major] agreement (craft)", editor)
        self.assertNotIn(self.EDITOR, self.section(brief, "Must fix"))
        self.assertNotIn(self.EDITOR, self.section(brief, "Consider"))
        self.assertIn("NOT yours to fix", editor)
        # Never dropped and never softened: it still counts as a major finding
        # in the headline the brief opens with.
        self.assertIn("craft: 0 blocking, 2 major", brief)

    def test_no_score_reaches_the_writer(self):
        brief = self.brief()

        self.assertNotIn("human_authorship", brief)
        # And the brief says why, so a writer does not go looking for one.
        self.assertIn(
            "Scores are not shown to you, deliberately", brief.replace("\n", " ")
        )

    def test_the_findings_are_ordered_by_repair_order_not_by_severity(self):
        """Fixing a structural finding moves the text a craft finding points at."""

        self.command.script[("shape", "article")] = [
            changes("the argument arrives in the wrong order", category="ordering"),
            verdict("approved"),
        ]
        self.command.script[("mechanics", "article")] = [
            changes("a lowercase sentence opening", category="capitalisation"),
            verdict("approved"),
        ]
        self.run_produce(articles=["article"])

        brief = self.command.briefs("writer", "article")[1]
        self.assertLess(
            brief.index("the argument arrives in the wrong order"),
            brief.index("a lowercase sentence opening"),
        )
        self.assertIn("in **repair order**, not severity order", brief)


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
        self.assertEqual(set(judges), set(ARTICLE_LENSES))
        for kind in ARTICLE_LENSES:
            with self.subTest(lens=kind):
                self.assertEqual(
                    judges[kind]["call"]["prompt_path"], JUDGE_PROMPTS[kind]
                )
                self.assertEqual(judges[kind]["call"]["role"], f"{kind}_judge")

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

        # ``evidence`` and ``worth`` bind articles only, and ``article`` is all
        # of them, so those records are whole and land.  The whole-pieces lenses
        # also bind the editorial, which this run did not read.
        self.assertEqual(set(result.recorded), {"evidence", "worth"})
        for kind in ("mechanics", "shape", "craft"):
            with self.subTest(lens=kind):
                self.assertTrue(
                    any(
                        f"no {kind} review record exists to amend" in action
                        for action in result.human_actions
                    ),
                    result.human_actions,
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
                # And it reads as the expected state it is: every piece the
                # baseline complains about is one this run is drafting, so an
                # operator is not sent looking for a fault.
                and "expected and cleared by this run" in action
                for action in result.human_actions
            ),
            result.human_actions,
        )
        self.assertFalse(is_staging_marker(edition_dir / "articles" / "article.md"))
        self.assertFalse(is_staging_marker(edition_dir / "editorial.md"))
        # And the edition it hands back validates, which is the whole point.
        self.assertEqual(self.magazine.validate("issue-001").id, "issue-001")


class _ScriptedEditionGates:
    """Edition-wide gates a test can script call by call.

    The first call is produce's baseline, taken before any model runs; every
    call after it is one round's re-check.  ``rounds`` is popped one per call
    and ``settled`` answers every call past its end, so a test can say both
    "this breach is new" and "this breach never clears".  Per-piece gates
    always pass: what is under test here is where an edition-wide complaint
    ends up, not whether a piece has its own.
    """

    def __init__(self, *rounds: GateResult | None, settled: GateResult | None = None):
        self.rounds = list(rounds)
        self.settled = settled
        self.calls: list[str] = []

    def check_piece(self, piece, extractions) -> tuple[GateResult, ...]:
        return (GateResult("scripted", True),)

    def check_edition(self, edition_id: str) -> tuple[GateResult, ...]:
        self.calls.append(edition_id)
        gate = self.rounds.pop(0) if self.rounds else self.settled
        return (gate or GateResult("fit", True),)


class GateAttributionTests(ProduceFixture):
    """An edition-wide gate fails the piece it is about, and nobody else.

    ``fit`` and ``validate`` measure the whole issue, so one article a page
    over budget fails the gate for every piece in the round.  Sending that back
    to all of them costs a model call each and hands every writer but one an
    instruction it has no power to carry out: shorten a paragraph in an article
    it cannot edit.
    """

    OVERLONG = "en: article article spans 8 pages (maximum 7)"
    EDITION_WIDE = "issue-001: the closing plate roll has a gap at plate 2"

    def test_one_article_s_breach_reaches_only_that_article(self):
        gates = _ScriptedEditionGates(
            None,
            GateResult(
                "fit",
                False,
                self.OVERLONG,
                (Breach("article", self.OVERLONG),),
            ),
        )

        result = self.run_produce(gates=gates)

        self.assertEqual(
            [(outcome.piece_id, outcome.status, outcome.rounds) for outcome in result.outcomes],
            [("article", "passed", 2), ("editorial", "passed", 1)],
        )
        # The article hears it, in its own record and in its own next brief.
        self.assertEqual(
            self.record("article")["rounds"][0]["gate_failures"],
            [f"fit: {self.OVERLONG}"],
        )
        briefs = self.command.briefs("writer", "article")
        self.assertEqual(len(briefs), 2)
        self.assertIn(self.OVERLONG, briefs[1])
        # The editorial does not: it was drafted once, cleanly, and was never
        # asked to shorten somebody else's article.
        editorial = self.command.briefs("writer", "editorial")
        self.assertEqual(len(editorial), 1)
        self.assertNotIn(self.OVERLONG, editorial[0])
        self.assertEqual(
            [round_["gate_failures"] for round_ in self.record("editorial")["rounds"]],
            [[]],
        )

    def test_a_breach_that_belongs_to_the_edition_fails_nobody(self):
        """No writer can close a gap in the plate roll from a drafting round."""

        gates = _ScriptedEditionGates(
            None, settled=GateResult("validate", False, self.EDITION_WIDE)
        )

        result = self.run_produce(gates=gates)

        self.assertEqual(
            [(outcome.piece_id, outcome.status, outcome.rounds) for outcome in result.outcomes],
            [("article", "passed", 1), ("editorial", "passed", 1)],
        )
        for piece_id in ("article", "editorial"):
            self.assertEqual(
                [
                    round_["gate_failures"]
                    for round_ in self.record(piece_id)["rounds"]
                ],
                [[]],
                piece_id,
            )
            self.assertEqual(len(self.command.briefs("writer", piece_id)), 1)
        # Reported once, to the human, the way a stale overlay is.
        self.assertEqual(
            [
                action
                for action in result.human_actions
                if self.EDITION_WIDE in action
            ],
            [
                "validate fails for issue-001 as a whole, and no single piece's "
                f"rewrite can clear it: {self.EDITION_WIDE}"
            ],
        )

    def test_a_piece_with_a_breach_of_its_own_still_fails(self):
        """Routing, not leniency: the piece named still spends its rounds."""

        gates = _ScriptedEditionGates(
            None,
            settled=GateResult(
                "fit", False, self.OVERLONG, (Breach("article", self.OVERLONG),)
            ),
        )

        result = self.run_produce(gates=gates, max_rounds=1)

        self.assertEqual(
            [(outcome.piece_id, outcome.status) for outcome in result.outcomes],
            [("article", "escalated")],
        )
        self.assertEqual(
            self.record("article")["rounds"][0]["gate_failures"],
            [f"fit: {self.OVERLONG}"],
        )
        self.assertEqual(self.record("article")["status"], "escalated")

    def test_an_unattributed_report_is_read_line_by_line(self):
        """``validate`` raises sentences, so its owner is the piece it names.

        One message, three complaints, two owners and one that is nobody's:
        each line goes where it belongs and no line goes anywhere else.
        """

        detail = "\n".join(
            (
                self.EDITION_WIDE,
                "article: editions/issue-001/articles/article.md has no byline",
                "editorial: editions/issue-001/editorial.md has no byline",
            )
        )
        failing = GateResult("validate", False, detail)
        # Baseline, then the first round of each piece; each piece's second
        # round finds the gate clear, so both pass and both records can be
        # read.
        gates = _ScriptedEditionGates(None, failing, None, failing)

        self.run_produce(gates=gates)

        for piece_id in ("article", "editorial"):
            failures = self.record(piece_id)["rounds"][0]["gate_failures"]
            self.assertEqual(
                failures, [f"validate: {piece_id}: {self.line_for(piece_id)}"]
            )
            self.assertNotIn(self.EDITION_WIDE, "".join(failures))

    def test_a_pre_existing_failure_this_run_will_clear_reads_as_expected(self):
        """The state produce exists to clear is not a fault to report as one."""

        detail = "\n".join(
            (
                "issue-001: 2 piece(s) are still unwritten staging markers",
                "article: editions/issue-001/articles/article.md is a staging marker",
                "editorial: editions/issue-001/editorial.md is a staging marker",
            )
        )
        gates = _ScriptedEditionGates(GateResult("validate", False, detail))

        result = self.run_produce(gates=gates)

        self.assertIn(
            "pre-existing gate failure (validate), expected and cleared by this "
            "run, which is drafting every piece it names: issue-001: 2 piece(s) "
            "are still unwritten staging markers",
            result.human_actions,
        )

    def test_a_pre_existing_failure_about_a_piece_this_run_skips_is_a_fault(self):
        """A run that is not going to clear it must not call it expected."""

        detail = "editorial: editions/issue-001/editorial.md is a staging marker"
        gates = _ScriptedEditionGates(GateResult("validate", False, detail))

        result = self.run_produce(gates=gates, articles=["article"])

        self.assertIn(
            f"pre-existing gate failure (validate): {detail}", result.human_actions
        )

    def test_an_inherited_edition_wide_breach_is_reported_once(self):
        """It was there before the run; saying it again each round is noise."""

        gates = _ScriptedEditionGates(
            settled=GateResult("validate", False, self.EDITION_WIDE)
        )

        result = self.run_produce(gates=gates)

        self.assertEqual(
            [action for action in result.human_actions if self.EDITION_WIDE in action],
            [f"pre-existing gate failure (validate): {self.EDITION_WIDE}"],
        )

    @staticmethod
    def line_for(piece_id: str) -> str:
        path = (
            "editions/issue-001/articles/article.md"
            if piece_id == "article"
            else "editions/issue-001/editorial.md"
        )
        return f"{path} has no byline"


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

        self.assertIn("passed: article after 1 round(s)", output)
        self.assertIn("passed: editorial after 1 round(s)", output)
        for kind in set(BENCH_REVIEW_KINDS) - {"teaching"}:
            self.assertIn(f"recorded: {kind} ->", output)
        # This fixture declares no explainer, so no teaching record is owed and
        # none is written.  Every other lens records, the graph completes, and
        # the run exits zero.  It exited one until ``issue/bench`` learned to
        # ask which records an edition *owes* rather than which kinds exist --
        # see ``test_an_edition_with_no_explainer_finishes_without_a_teaching_record``.
        self.assertNotIn("recorded: teaching ->", output)
        self.assertEqual(code, 0, output)
        self.assertIn("COMPLETE", output)

    def test_an_edition_with_no_explainer_finishes_without_a_teaching_record(self):
        """Four surfaces have to agree that a lens with nothing to read is done.

        ``teaching`` covers explainers, and an edition with no ``in_a_nutshell``
        piece is an ordinary edition rather than an incomplete one.  Three
        surfaces always got that right -- the judge nodes resolve
        ``not_applicable``, ``_record_bench`` writes no record, and
        ``piece_review.review_status`` reports ``not_applicable`` because the
        alternative "is a demand no run could ever satisfy".  ``issue/bench``
        was the fourth and it disagreed: it required a file on disk for every
        kind in ``BENCH_REVIEW_KINDS``, so such an edition sat permanently one
        node short, ``mag produce`` exited one for ever, ``ready.yaml`` called a
        fully settled edition ``stalled``, and ``mag build`` refused it -- all
        demanding a record the recorder would itself refuse to write, because
        there is no explainer to bind.

        The bench node now asks which records this edition *owes*
        (``produce_graph.owed_bench_kinds``) rather than which kinds exist.
        """

        self.run_produce()

        graph = self.magazine.production_graph("issue-001")
        self.assertEqual([node.id for node in graph.unreached], [])
        self.assertTrue(graph.complete)
        bench = graph.node("issue/bench")
        self.assertEqual(bench.state, "complete")
        # The record genuinely is not there, and the node is complete anyway.
        # Those two facts together are the whole point: absence is only a
        # failure when something was owed.
        self.assertFalse(
            (self.root / "editions/issue-001/reviews/teaching.yaml").exists()
        )
        for piece_id in ("article", "editorial"):
            node = graph.node(f"{piece_id}/judge.teaching")
            self.assertEqual(node.state, "not_applicable", piece_id)

    def test_an_edition_with_an_explainer_does_owe_a_teaching_record(self):
        """The other half, or the fix above would just be the check deleted.

        A gate that is satisfied by having nothing to check is not a gate. This
        pins that the exemption is conditioned on the edition's pieces and not
        on the kind: give the edition an explainer and the record is owed again.
        """

        from magazine.produce_graph import owed_bench_kinds

        self.assertNotIn("teaching", owed_bench_kinds({"article": "faithful_edit"}))
        self.assertIn(
            "teaching",
            owed_bench_kinds(
                {"article": "faithful_edit", "explainer": "in_a_nutshell"}
            ),
        )
        # And `edition` is owed whatever the pieces are: an issue is always an
        # issue.
        self.assertIn("edition", owed_bench_kinds({}))

    def test_a_full_run_serializes_to_json(self):
        import json

        code, output = self.run_cli_scripted(["produce", "issue-001", "--json"])

        payload = json.loads(output)
        self.assertEqual(code, 0, output)
        self.assertEqual(payload["dry_run"], False)
        self.assertTrue(payload["complete"], output)
        self.assertEqual(payload["graph"]["unreached"], [])
        self.assertEqual(
            [row["status"] for row in payload["outcomes"]], ["passed", "passed"]
        )
        self.assertEqual(
            payload["issue_reviews"][EDITION_JUDGE_KIND]["result"], "approved"
        )
        self.assertEqual(
            payload["plan"]["pieces"][0]["manuscript"],
            "editions/issue-001/articles/article.md",
        )

    def test_an_escalation_exits_one(self):
        self.command.script[("craft", "article")] = [changes("it repeats")]

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
        self.assertIn("### Must fix", brief)
        self.assertIn("The deprecation claim is wrong.", brief)
        self.assertIn("paragraph twelve", brief)
        # A hand-filed finding names no lens, so the composer sorts it into the
        # last repair tier -- where an obligation nobody can place is least
        # likely to send a writer at work a structural finding above it is
        # about to discard.  It still prints under the name it was filed under:
        # a reviser treats "from the edition review" differently from "from the
        # craft lens", and a tier is not an attribution.  Printing the fallback
        # tier as the author would replace a real attribution with a guess.
        self.assertIn("(edition review)", brief)
        self.assertNotIn(f"({PIECE_JUDGE_KINDS[-1]})", brief)
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

            def measure(self, edition_id, language=None):
                # The fit gate reads the measurement rather than the printed
                # table, because the measurement knows which article each
                # breach belongs to.  It is still the one expensive call the
                # fit gate makes, and still what is counted here.
                calls.append("fit")
                return magazine.measure(edition_id, language=language)

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
        self.assertGreater(budget.safe_characters, 0)
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

    def test_the_character_figure_sits_below_the_packed_estimate(self):
        """Conservative by construction, and pinned so it stays that way.

        The figure this replaced was the rail over the sample's mean glyph
        advance -- what a line would hold if greedy wrapping ever filled one to
        the last point.  Recomputing that here and requiring the stated floor
        to be strictly under it is what stops the optimistic number coming
        back as a simplification.
        """

        from magazine.weasyprint_adapter import _plain, _string_width

        budget = self.budget(sample=OPENER_PROSE)
        text = _plain(" ".join(OPENER_PROSE.split()))
        packed = budget.lines * int(
            348.0 // (_string_width(text, "serif", 9.6) / len(text))
        )

        self.assertGreater(budget.safe_characters, 0)
        self.assertLess(budget.safe_characters, packed)

    def test_prose_at_the_stated_floor_fits_wherever_it_is_cut(self):
        """The floor is a promise, and one paragraph is not evidence of it.

        Where a paragraph wraps depends on where its word boundaries fall, so a
        single specimen at the stated length proves only that that specimen
        fitted.  Every word offset of a body of real prose is cut to the stated
        count instead, and every one of them has to clear the line limit.
        """

        budget = self.budget(sample=OPENER_PROSE)

        checked = 0
        for candidate in prose_windows(OPENER_PROSE, budget.safe_characters):
            checked += 1
            self.assertTrue(
                budget.fits(candidate),
                f"{len(candidate)} characters, the stated floor being "
                f"{budget.safe_characters}, wrapped to "
                f"{len(budget.wrapped(candidate))} lines of {budget.lines}: "
                f"{candidate}",
            )
        self.assertGreater(checked, 40)


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

    def test_the_brief_names_the_check_rather_than_the_arithmetic(self):
        """A writer near the edge must have somewhere to ask."""

        add_article_opener(self.root)

        brief = self.brief()

        self.assertIn("uv run --locked mag fit issue-001 --opener article", brief)


class OpenerBudgetPromiseTests(unittest.TestCase):
    """Whatever the brief says, prose of that length has to clear the gate.

    The brief is the only place these numbers are ever read, so this reads
    them there -- out of the composed text, by the same parse a writer would
    do -- rather than from the dataclass that produced them.  A wording change
    that dropped the floor, or a refactor that quoted a different number in
    the assignment than the one measured, both fail here.
    """

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.magazine = build_project(self.root, body=OPENER_PROSE)
        add_article_opener(self.root)
        self.command = ScriptedCommand()

    def stated(self) -> tuple[int, int]:
        """The two numbers the assignment states, read back out of the brief."""

        production(self.magazine, self.command, gates=PassingGates()).run(
            "issue-001", articles=["article"]
        )
        brief = self.command.briefs("writer", "article")[0]
        stated = re.search(
            r"- Opening paragraph budget: (\d+) typeset line\(s\); "
            r"write to about (\d+) characters",
            brief,
        )
        self.assertIsNotNone(stated, brief)
        return int(stated.group(1)), int(stated.group(2))

    def test_the_stated_floor_is_one_the_gate_accepts(self):
        from magazine.weasyprint_adapter import _wrap

        lines, characters = self.stated()

        self.assertGreater(characters, 0)
        checked = 0
        for candidate in prose_windows(OPENER_PROSE, characters):
            checked += 1
            wrapped = _wrap(candidate, "serif", 9.6, 348.0)
            self.assertLessEqual(
                len(wrapped),
                lines,
                f"the brief offers {characters} characters against {lines} "
                f"line(s); {len(candidate)} characters set as {len(wrapped)} "
                f"lines: {candidate}",
            )
        self.assertGreater(checked, 40)

    def test_the_floor_is_worth_stating(self):
        """A safe number nobody can write to would be no better than none.

        The point of quoting characters at all is that lines are hard to feel
        while drafting, so the useful half of the bargain is pinned as well as
        the safe half.  Fifty characters a line is the tripwire: the bound that
        would be a theorem -- widest glyph in the face, longest word deducted
        -- lands near thirty, which is safe, useless, and the reason that bound
        was not taken.  The measured floor runs around sixty-five, so this
        fails a collapse without failing on ordinary variation between samples.
        """

        lines, characters = self.stated()

        self.assertGreaterEqual(characters, lines * 50)


class OpenerFitCommandTests(unittest.TestCase):
    """``mag fit --opener``: the check the brief tells a writer to run.

    The whole reason it exists is that the arithmetic had to be reproduced by
    hand once, so these run it the way a writer would -- through the command
    line, with the paragraph on standard input -- rather than through the
    dataclass underneath.
    """

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        build_project(self.root, body=OPENER_PROSE)

    def run_check(self, intro: str, *argv: str) -> tuple[int, str]:
        from unittest.mock import patch

        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            with patch("sys.stdin", io.StringIO(intro)):
                code = main(["--root", str(self.root), "fit", "issue-001", *argv])
        return code, out.getvalue()

    def budget(self):
        from magazine.produce import load_producible_edition, opener_intro_budget

        magazine = Magazine(self.root)
        edition = load_producible_edition(magazine, "issue-001")
        return opener_intro_budget(magazine, edition, edition.articles[0])

    def test_a_paragraph_within_the_budget_is_reported_and_exits_zero(self):
        add_article_opener(self.root)
        budget = self.budget()

        code, output = self.run_check(
            prose_windows(OPENER_PROSE, budget.safe_characters)[0],
            "--opener",
            "article",
        )

        self.assertEqual(code, 0, output)
        self.assertIn(f"of {budget.lines} typeset line(s)", output)
        self.assertIn("fits", output)
        # The lines themselves, so a writer can see where the prose sat.
        self.assertIn("   1  The infrastructure", output)

    def test_an_overlong_paragraph_exits_one_and_shows_the_overflow(self):
        add_article_opener(self.root)
        budget = self.budget()
        overlong = " ".join(OPENER_PROSE.split())

        code, output = self.run_check(overlong, "--opener", "article")

        self.assertEqual(code, 1)
        self.assertIn("OVER", output)
        self.assertIn(f"Cut to {budget.lines} line(s)", output)
        # A breach is the command's answer, so it must not read as a crash.
        self.assertIn(f"{len(overlong)} character(s)", output)

    def test_the_floor_the_brief_quotes_is_the_floor_the_check_quotes(self):
        """One number, or the advice and the answer can disagree."""

        add_article_opener(self.root)
        budget = self.budget()

        _, output = self.run_check("A short opening.", "--opener", "article")

        self.assertIn(
            f"a paragraph of {budget.safe_characters} character(s) or fewer", output
        )

    def test_a_piece_the_constraint_does_not_govern_is_refused(self):
        """Not `fits`: there is no budget to be inside of."""

        code, output = self.run_check("A short opening.", "--opener", "article")

        self.assertEqual(code, 2, output)

    def test_an_empty_paragraph_is_refused_rather_than_passed(self):
        add_article_opener(self.root)

        code, _ = self.run_check("   \n", "--opener", "article")

        self.assertEqual(code, 2)

    def test_the_edition_wide_verdict_is_untouched(self):
        """``--opener`` is a second question, not a replacement for the first."""

        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = main(["--root", str(self.root), "fit", "issue-001"])

        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("every page budget holds", out.getvalue())
