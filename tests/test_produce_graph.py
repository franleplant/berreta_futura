"""The production graph: declared as data, traversed, and enforced.

These tests exist because of one edition.  ``rerun-004-the-systems-around-the-
model`` reached seven settled articles, its editorial's two judges both answered
``approved`` into files nothing ever read, the managing editor and the reader
personas never ran at all, and every surface said something locally true and
collectively false: ``mag produce`` printed eight cheerful lines and exited
zero, ``ready.yaml`` said ``awaiting_work``, and the workflow report said the
production checkpoint was complete.  A PDF was built from that.

So what is under test here is not any one judge.  It is whether an edition that
has stopped partway through the pipeline can be made to *look* finished by any
route: the produce report, the exit code, the ready file, the workflow
checkpoint, or the build.

**Why a role-keyed runner rather than the suite's ``ScriptedCommand``.**  That
fake recognises which judge is being called by sniffing the first heading line
of the composed brief, which couples every test using it to the wording of the
files in ``prompts/``.  The judge lenses are being renamed and multiplied right
now.  These tests are about the graph, so they key on the pipeline's own work
item -- the thing that names the piece, the role and the round -- which is
exactly the seam ``produce`` already dispatches through.  No model is invoked
here by any path; :class:`RoleRunner` cannot reach one.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from magazine.cli import main
from magazine.errors import ValidationError
from magazine.produce import Production
from magazine import produce_graph
from magazine.produce_graph import (
    AGENTIC,
    BENCH_REVIEW_KINDS,
    COMPLETE,
    EDITION_JUDGE_KIND,
    EDITION_NODE_SPECS,
    ESCALATED,
    EVERY_PIECE_SETTLED,
    INCONSISTENT,
    NOT_APPLICABLE,
    PIECE_JUDGE_KINDS,
    PIECE_JUDGE_LENSES,
    PIECE_NODE_SPECS,
    PROGRAMMATIC,
    VERDICT,
    JudgeLens,
    NodeSpec,
    ProduceGraphError,
    lens_applies,
    require_complete_production_graph,
    resolve_production_graph,
    role_order,
    stage_order,
    validate_node_specs,
    work_contracts,
)
from magazine.piece_review import ARTICLES, EXPLAINERS, PIECES
from magazine.production_record import piece_record_path
from magazine.runner import GenerationResult

from test_produce import (
    PassingGates,
    add_explainer,
    build_project,
    changes,
    draft,
    verdict,
)


EDITION = "issue-001"


class RoleRunner:
    """A text runner that answers from a table keyed by work-item role.

    Implements the two things :class:`~magazine.produce.Production` asks of a
    runner -- ``kind`` and ``backend`` -- plus ``request``, the seam a runner
    uses when it wants to know *which* call it is answering.  ``generate`` is
    present and refuses, so a path that tried to make an anonymous call would
    fail the test rather than quietly work.
    """

    kind = "text"
    backend = "fake"

    def __init__(self, **overrides: object) -> None:
        self.calls: list[tuple[str, str, int]] = []
        self.overrides = dict(overrides)
        self._rounds: dict[str, int] = {}

    def request(self, item, prompt, text, *, identity, cwd=None):
        self.calls.append((item.piece_id, item.role, item.round_number))
        return GenerationResult(
            text=self._reply(item),
            backend=self.backend,
            argv=("fake", item.key),
            stderr="",
            duration_seconds=0.0,
        )

    def generate(self, text, *, cwd=None):  # pragma: no cover - must never run
        raise AssertionError("the pipeline made an unnamed model call")

    def roles(self, piece_id: str | None = None) -> list[str]:
        return [
            role
            for piece, role, _ in self.calls
            if piece_id is None or piece == piece_id
        ]

    def _reply(self, item) -> str:
        override = self.overrides.get(f"{item.piece_id}:{item.role}")
        if override is None:
            override = self.overrides.get(item.role)
        if isinstance(override, str):
            return override
        if item.role == "writer":
            self._rounds[item.piece_id] = self._rounds.get(item.piece_id, 0) + 1
            return draft(item.piece_id, self._rounds[item.piece_id])
        return verdict("approved")


def ensure_judge_prompts(root: Path) -> None:
    """Guarantee the fixture has a prompt file for every judge the graph declares.

    The lens set is deliberately data -- one tuple, so the narrow single-concern
    passes replacing the two-judge stage cost one edit -- which means the set is
    expected to change, and to change in a commit that lands the prompt files
    and the Python at slightly different moments.  These tests are about the
    traversal rather than about what any prompt says, so a lens whose file the
    fixture has not got is given a stub.  A real prompt in the repository is
    always preferred and never overwritten; this only fills a gap.
    """

    from magazine.produce_prompts import JUDGE_PROMPTS, writer_prompt_path

    wanted = set(JUDGE_PROMPTS.values())
    wanted.update(JUDGE_PROMPTS.get(lens.kind, "") for lens in PIECE_JUDGE_LENSES)
    for mode in ("faithful_edit", "original_editorial"):
        wanted.add(writer_prompt_path(mode))
    for relative in sorted(filter(None, wanted)):
        path = root / relative
        if path.is_file():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        name = path.stem.replace("-", " ")
        path.write_text(
            f"# {name} prompt\n\nA fixture stand-in for a prompt this checkout "
            "does not carry.\n",
            encoding="utf-8",
        )


class GraphFixture(unittest.TestCase):
    """One edition carrying every kind of piece the bench distinguishes.

    A feature, an explainer and the editorial, which is the smallest edition on
    which all seven lenses have something to read: ``worth`` skips the
    editorial, ``teaching`` reads only the explainer, and a fixture missing
    either would leave the traversal's two ``not_applicable`` cases and one of
    its bench records unexercised.
    """

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.magazine = build_project(self.root)
        add_explainer(self.root)
        ensure_judge_prompts(self.root)

    def produce(self, runner: RoleRunner, *, max_rounds: int = 3, **kwargs):
        return Production(
            self.magazine,
            runner=runner,
            gates=PassingGates(),
            max_rounds=max_rounds,
        ).run(EDITION, **kwargs)

    def graph(self):
        return resolve_production_graph(self.root, self.magazine.editions_dir, EDITION)

    def states(self) -> dict[str, str]:
        return {node.id: node.state for node in self.graph().nodes}

    def run_cli(self, argv: list[str]) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = main(["--root", str(self.root), *argv])
        return code, out.getvalue()


class DeclarationTests(unittest.TestCase):
    """The order is a value, and a wrong one is an error rather than a no-op."""

    def test_every_declared_judge_lens_has_a_node_and_a_contract(self):
        """Adding a lens is one edit, and nothing else has to be told.

        The narrower single-concern lenses replacing the two-judge stage are
        declared in one tuple.  If the node set, the work contracts and the
        report order did not all derive from it, each of them would be a place
        the new lens could be silently missing -- which for a judge means an
        unasked question, which is the whole incident.
        """

        contracts = work_contracts()
        order = role_order()
        for lens in PIECE_JUDGE_LENSES:
            with self.subTest(lens=lens.kind):
                node = next(
                    (
                        spec
                        for spec in PIECE_NODE_SPECS
                        if spec.id == f"judge.{lens.kind}"
                    ),
                    None,
                )
                self.assertIsNotNone(node, f"no node declared for the {lens.kind} lens")
                self.assertEqual(node.kind, AGENTIC)
                self.assertIs(node.lens, lens)
                self.assertEqual(node.returns, VERDICT)
                self.assertIn(lens.kind, contracts)
                self.assertIn(lens.kind, order)

    def test_the_whole_issue_judge_is_declared_and_required(self):
        """The managing editor is a node, not a tail of somebody else's call.

        It is also the only whole-issue node left.  ``prompts/README.md``
        retired Marcus and Priya as lenses that bought one lens's worth of
        information for two extra calls each, so ``manager-run-a`` and
        ``learning`` are gone and ``edition`` consumes the fan-in directly.
        """

        declared = {spec.id: spec for spec in EDITION_NODE_SPECS}
        self.assertEqual(sorted(declared), ["bench", "edition"])
        self.assertEqual(declared["edition"].kind, AGENTIC)
        self.assertEqual(declared["edition"].role, EDITION_JUDGE_KIND)
        # And it fans in over every piece rather than over a fixed list, so an
        # edition with one more article cannot reach it a piece early.
        self.assertIn(EVERY_PIECE_SETTLED, declared["edition"].consumes)

    def test_a_node_that_consumes_something_undeclared_is_refused(self):
        broken = (
            NodeSpec("write", PROGRAMMATIC, "piece", (), "drafted"),
            NodeSpec("settled", PROGRAMMATIC, "piece", ("judge.nobody",), "passed"),
        )

        with self.assertRaises(ProduceGraphError) as raised:
            validate_node_specs(broken, EDITION_NODE_SPECS)

        self.assertIn("judge.nobody", str(raised.exception))

    def test_a_backward_dependency_is_refused_as_a_cycle(self):
        broken = (
            NodeSpec("write", PROGRAMMATIC, "piece", ("settled",), "drafted"),
            NodeSpec("settled", PROGRAMMATIC, "piece", (), "passed"),
        )

        with self.assertRaises(ProduceGraphError) as raised:
            validate_node_specs(broken, EDITION_NODE_SPECS)

        self.assertIn("cycle", str(raised.exception))

    def test_an_agentic_node_that_says_nothing_about_its_reply_is_refused(self):
        """A node nobody can answer can never reach its accepting state."""

        broken = (
            NodeSpec("write", AGENTIC, "piece", (), "drafted", role="writer"),
            NodeSpec("settled", PROGRAMMATIC, "piece", (), "passed"),
        )

        with self.assertRaises(ProduceGraphError) as raised:
            validate_node_specs(broken, EDITION_NODE_SPECS)

        self.assertIn("can never reach its accepting state", str(raised.exception))

    def test_a_kind_outside_the_vocabulary_is_refused(self):
        broken = (
            NodeSpec("settled", "magic", "piece", (), "passed"),
        )

        with self.assertRaises(ProduceGraphError):
            validate_node_specs(broken, EDITION_NODE_SPECS)


class SingleEditPointTests(GraphFixture):
    """Is :data:`PIECE_JUDGE_LENSES` really the one place a lens is declared?

    The claim the module makes for itself is strong and expensive if false:
    "adding an eighth lens is a row here plus a prompt file".  Every table it
    lists -- the node set, the work contracts, the report order, the run
    schedule, the completion predicate -- is supposed to grow from that tuple
    and from nothing else, and the failure mode of a second table is not a
    crash.  It is a judge that is never dispatched, which is an unasked
    question, which is the whole incident this module exists because of.

    So the tuple is grown *locally* and the derivations are re-run against the
    local copy.  Nothing here edits the module's own table: the last test
    asserts that, because a test that mutated the real one would prove the
    derivations work on a value nobody ships.
    """

    EXTRA = JudgeLens("polish", stage=3, covers=PIECES, reads_source=False)

    def grown(self):
        """The lens tuple with one more row, and the piece table it implies.

        Built through the module's own :func:`_judge_specs`, so what is under
        test is the real derivation rather than a copy of it written here.  The
        two non-judge specs are taken from the real table and ``settled`` has
        its fan-in recomputed, which is the one line this test has to restate --
        see :meth:`test_every_materialised_table_is_the_lens_tuple_re_derived`,
        which pins that restatement against the shipped table.
        """

        from dataclasses import replace

        lenses = (*PIECE_JUDGE_LENSES, self.EXTRA)
        kinds = tuple(lens.kind for lens in lenses)
        with self.patched(lenses, kinds):
            judges = produce_graph._judge_specs()
        by_id = {spec.id: spec for spec in PIECE_NODE_SPECS}
        settled = replace(
            by_id["settled"],
            consumes=("gates", *(f"judge.{kind}" for kind in kinds)),
        )
        return lenses, kinds, (by_id["write"], by_id["gates"], *judges, settled)

    def patched(self, lenses, kinds, specs=None):
        from contextlib import ExitStack
        from unittest.mock import patch

        stack = ExitStack()
        stack.enter_context(patch.object(produce_graph, "PIECE_JUDGE_LENSES", lenses))
        stack.enter_context(patch.object(produce_graph, "PIECE_JUDGE_KINDS", kinds))
        if specs is not None:
            stack.enter_context(patch.object(produce_graph, "PIECE_NODE_SPECS", specs))
        return stack

    def test_appending_a_lens_grows_every_derived_surface_at_once(self):
        lenses, kinds, specs = self.grown()
        # Produced first, and against the shipped table: what the grown table
        # has to change is the verdict on a *finished* edition, so the edition
        # has to be genuinely finished under the real bench.
        self.produce(RoleRunner())
        self.assertTrue(self.graph().complete)

        # A runnable graph, still: the grown table passes the same refusal the
        # module runs on itself at import.
        validate_node_specs(specs, EDITION_NODE_SPECS)
        with self.patched(lenses, kinds, specs):
            self.assertIn("judge.polish", [spec.id for spec in specs])
            node = next(spec for spec in specs if spec.id == "judge.polish")
            self.assertEqual((node.kind, node.returns), (AGENTIC, VERDICT))
            self.assertIs(node.lens, self.EXTRA)

            # The work contracts: a role no node dispatches cannot be answered,
            # and this one now can be.
            self.assertEqual(work_contracts()["polish"], VERDICT)

            # The report order: last of the piece judges, because it is last in
            # repair order, and still before the whole-issue lens.
            order = role_order()
            self.assertEqual(
                order["polish"], max(order[kind] for kind in PIECE_JUDGE_KINDS) + 1
            )
            self.assertLess(order["polish"], order[EDITION_JUDGE_KIND])

            # The run schedule: grouped by the stage the row declares.
            self.assertIn(self.EXTRA, dict(stage_order())[self.EXTRA.stage])

            # And the completion predicate, which is the one that matters: a
            # finished edition is no longer finished, because there is a
            # question nobody has asked.
            grown_graph = resolve_production_graph(
                self.root, self.magazine.editions_dir, EDITION
            )
            self.assertFalse(grown_graph.complete)
            self.assertEqual(
                [node.id for node in grown_graph.unreached],
                [
                    *(
                        f"{piece}/judge.polish"
                        for piece in ("article", "nutshell", "editorial")
                    ),
                    # ``issue/bench`` grows from the tuple as well, and that it
                    # does is the part worth pinning.  The bench node used to
                    # read a hardcoded list of four ``(kind, path)`` pairs that
                    # still named ``line`` and ``learning`` long after both were
                    # retired, so a lens could be declared, dispatched and
                    # judged while the bench never noticed its record was
                    # missing.  It now derives the records an edition owes from
                    # this same tuple, so a new lens is short a record until one
                    # is written -- exactly as the six shipped lenses are.
                    "issue/bench",
                ],
            )

        # Unpatched, the same edition is complete: the new node was the only
        # difference, and it came from the tuple.
        self.assertTrue(
            resolve_production_graph(
                self.root, self.magazine.editions_dir, EDITION
            ).complete
        )

    def test_a_new_lens_needs_a_prompt_row_as_well_as_a_lens_row(self):
        """Where the "one edit" claim stops being literally true, pinned.

        Growing :data:`PIECE_JUDGE_LENSES` alone grows the graph, the contracts,
        the order and the predicate -- and then the first run dispatching the
        new lens dies in ``produce._lens_job`` on ``JUDGE_PROMPTS[kind]``,
        halfway through an edition, which is the most expensive moment to learn
        a file is missing.  ``JUDGE_PROMPTS`` and the bench's record specs are
        therefore the two companion edits, and both are keyed by kind, so the
        cheap protection is to require the key sets to agree.
        """

        from magazine.produce_prompts import JUDGE_PROMPTS

        self.assertEqual(set(JUDGE_PROMPTS), set(BENCH_REVIEW_KINDS))
        _, kinds, _ = self.grown()
        self.assertNotIn("polish", JUDGE_PROMPTS)
        with self.assertRaises(KeyError):
            JUDGE_PROMPTS[kinds[-1]]

    def test_the_grown_table_is_local_and_the_shipped_one_is_untouched(self):
        self.grown()

        self.assertNotIn("polish", PIECE_JUDGE_KINDS)
        self.assertNotIn("polish", work_contracts())
        self.assertNotIn("polish", [spec.id for spec in PIECE_NODE_SPECS])
        self.assertNotIn("polish", BENCH_REVIEW_KINDS)

    def test_every_materialised_table_is_the_lens_tuple_re_derived(self):
        """The constants computed at import must be the tuple and nothing else.

        ``PIECE_NODE_SPECS`` and ``BENCH_REVIEW_KINDS`` are built when the
        module is executed, so a test cannot regrow them from a local table the
        way it can regrow ``_judge_specs()`` -- only an edit and a fresh import
        does that.  What can be checked, and is what a stale second table would
        break, is that every one of them is *exactly* what re-deriving from
        :data:`PIECE_JUDGE_LENSES` produces right now.
        """

        kinds = tuple(lens.kind for lens in PIECE_JUDGE_LENSES)
        self.assertEqual(PIECE_JUDGE_KINDS, kinds)
        self.assertEqual(
            [spec.id for spec in PIECE_NODE_SPECS if spec.id.startswith("judge.")],
            [f"judge.{kind}" for kind in kinds],
        )
        settled = next(spec for spec in PIECE_NODE_SPECS if spec.id == "settled")
        self.assertEqual(
            settled.consumes, ("gates", *(f"judge.{kind}" for kind in kinds))
        )
        self.assertEqual(BENCH_REVIEW_KINDS, (*kinds, EDITION_JUDGE_KIND))
        self.assertEqual(
            [role for role in role_order() if role in set(kinds)], list(kinds)
        )
        self.assertEqual(
            {kind: work_contracts()[kind] for kind in kinds},
            {kind: VERDICT for kind in kinds},
        )
        # And the lens set the bench records against is the same set, which is
        # the check that stops a lens being judged and never recorded.
        from magazine.review_bench import PIECE_REVIEW_KINDS

        self.assertEqual(tuple(PIECE_REVIEW_KINDS), kinds)

    def test_a_lens_declares_its_own_coverage_and_the_graph_reads_it_there(self):
        """Three coverages, and each exclusion has a reason that is not tidiness."""

        for lens in PIECE_JUDGE_LENSES:
            with self.subTest(lens=lens.kind):
                reads_editorial = lens_applies(
                    lens, piece_id="editorial", content_mode="original_editorial"
                )
                reads_feature = lens_applies(
                    lens, piece_id="article", content_mode="faithful_edit"
                )
                reads_explainer = lens_applies(
                    lens, piece_id="nutshell", content_mode="in_a_nutshell"
                )
                if lens.covers == PIECES:
                    self.assertTrue(
                        reads_editorial and reads_feature and reads_explainer
                    )
                elif lens.covers == ARTICLES:
                    self.assertFalse(reads_editorial)
                    self.assertTrue(reads_feature and reads_explainer)
                else:
                    self.assertEqual(lens.covers, EXPLAINERS)
                    self.assertTrue(reads_explainer)
                    self.assertFalse(reads_editorial or reads_feature)


class CompleteTraversalTests(GraphFixture):
    def test_a_full_run_reaches_every_node_and_says_so(self):
        result = self.produce(RoleRunner())

        self.assertTrue(
            result.complete,
            f"unreached: {result.unreached}",
        )
        self.assertEqual(result.unreached, ())
        states = self.states()
        self.assertTrue(
            all(state in (COMPLETE, NOT_APPLICABLE) for state in states.values()),
            states,
        )
        # And ``not_applicable`` is only ever a lens's declared coverage
        # speaking, never a node nobody got round to.  Anything else in that
        # state would be an unasked question wearing an accepting badge.
        self.assertEqual(
            {node for node, state in states.items() if state == NOT_APPLICABLE},
            {
                "editorial/judge.worth",
                "article/judge.teaching",
                "editorial/judge.teaching",
            },
        )

    def test_the_whole_issue_node_is_reached_and_recorded(self):
        """The stage that never ran, running -- and leaving the record to prove it."""

        self.produce(RoleRunner())

        states = self.states()
        for node_id in ("issue/edition", "issue/bench"):
            with self.subTest(node=node_id):
                self.assertEqual(states[node_id], COMPLETE)
        issue_dir = self.magazine.editions_dir / EDITION / "production" / "issue"
        self.assertTrue((issue_dir / "edition.yaml").is_file())
        # The two retired personas leave no node and no record behind them.
        for retired in ("issue/manager-run-a", "issue/learning"):
            self.assertNotIn(retired, states)
        self.assertFalse((issue_dir / "learning.yaml").exists())

    def test_the_cli_states_completion_and_exits_zero(self):
        self.produce(RoleRunner())

        code, output = self.run_cli(["produce", EDITION, "--graph"])

        self.assertEqual(code, 0, output)
        self.assertIn("production graph COMPLETE", output)

    def test_a_complete_edition_is_allowed_to_build(self):
        self.produce(RoleRunner())

        # No exception: the refusal is the thing under test, and its absence
        # here is what keeps it from being a check that simply blocks everything.
        require_complete_production_graph(
            self.root, self.magazine.editions_dir, EDITION
        )


class IssueStageReachabilityTests(GraphFixture):
    """The stage the incident lost, and the condition that decides it runs."""

    def test_the_issue_stage_runs_once_the_last_piece_passes(self):
        runner = RoleRunner()

        self.produce(runner)

        # Not merely "the records exist": the calls were actually dispatched,
        # in the order the graph declares, after the last piece and not before.
        issue_calls = [role for piece, role, _ in runner.calls if piece == "issue"]
        self.assertEqual(issue_calls, [EDITION_JUDGE_KIND])
        last_piece_pass = max(
            index
            for index, (piece, role, _) in enumerate(runner.calls)
            if piece == "editorial"
        )
        first_issue_call = min(
            index for index, (piece, _, _) in enumerate(runner.calls) if piece == "issue"
        )
        self.assertLess(last_piece_pass, first_issue_call)

    def test_a_run_that_leaves_a_piece_undrafted_never_claims_completion(self):
        """The shape of the incident: some pieces pass, the issue stage does not run.

        Producing one named piece settles it and leaves the editorial untouched,
        so the whole-issue judgments are correctly skipped -- and the run must
        say so rather than exiting on a list of successes.
        """

        result = self.produce(RoleRunner(), articles=["article"])

        self.assertFalse(result.complete)
        self.assertIn("issue/edition", result.unreached)
        self.assertIn("editorial/write", result.unreached)
        states = self.states()
        self.assertEqual(states["article/settled"], COMPLETE)
        self.assertEqual(states["issue/edition"], "blocked")

    def test_the_managing_editor_node_names_what_only_it_asks(self):
        """A node's report has to be worth reading by whoever finds it blocked."""

        self.produce(RoleRunner(), articles=["article"])

        node = self.graph().node("issue/edition")
        self.assertIn("whole issue", node.detail)


class StoppedRunReportingTests(GraphFixture):
    def test_the_cli_prints_the_unreached_nodes_and_exits_one(self):
        self.produce(RoleRunner(), articles=["article"])

        code, output = self.run_cli(["produce", EDITION, "--graph"])

        self.assertEqual(code, 1, output)
        self.assertIn("production graph INCOMPLETE", output)
        self.assertIn("issue/edition", output)
        self.assertIn("editorial/write", output)

    def test_the_graph_report_says_why_a_node_is_not_reachable(self):
        self.produce(RoleRunner(), articles=["article"])

        code, output = self.run_cli(["produce", EDITION, "--graph"])

        self.assertEqual(code, 1, output)
        self.assertIn(
            "blocked by nutshell/settled, editorial/settled", output
        )

    def test_a_dry_run_never_reports_itself_complete(self):
        """The most misleading true sentence available: "nothing to do"."""

        self.produce(RoleRunner())

        code, output = self.run_cli(["produce", EDITION, "--dry-run"])

        self.assertEqual(code, 0, output)
        self.assertIn("graph: not evaluated", output)


class BuildRefusalTests(GraphFixture):
    def test_a_build_is_refused_and_names_the_unreached_nodes(self):
        self.produce(RoleRunner(), articles=["article"])

        with self.assertRaises(ValidationError) as raised:
            self.magazine.build(EDITION)

        message = "\n".join(raised.exception.errors)
        self.assertIn("have not reached an accepting state", message)
        self.assertIn("issue/edition", message)
        self.assertIn("editorial/write", message)
        # The staging-marker refusal's shape: every unfinished thing named in
        # one error, and one command that makes progress on all of them.
        self.assertIn(f"mag produce {EDITION}", message)
        self.assertIn("--graph", message)

    def test_the_refusal_counts_every_unreached_node_rather_than_the_first(self):
        self.produce(RoleRunner(), articles=["article"])

        with self.assertRaises(ValidationError) as raised:
            self.magazine.build(EDITION)

        headline = raised.exception.errors[0]
        unreached = resolve_production_graph(
            self.root, self.magazine.editions_dir, EDITION
        ).unreached
        self.assertIn(f"{len(unreached)} production graph node(s)", headline)
        self.assertGreater(len(unreached), 1)


class EscalationTests(GraphFixture):
    """An escalated piece is terminal, and terminal is not the same as done."""

    def escalate(self):
        return self.produce(
            RoleRunner(
                **{f"article:{PIECE_JUDGE_LENSES[0].kind}": changes("still wrong")}
            ),
            max_rounds=2,
        )

    def test_an_escalated_piece_is_terminal_but_never_accepting(self):
        result = self.escalate()

        self.assertEqual(result.escalated, ("article",))
        node = self.graph().node("article/settled")
        self.assertEqual(node.state, ESCALATED)
        self.assertFalse(node.accepting)

    def test_an_escalated_piece_blocks_completion(self):
        self.escalate()

        self.assertFalse(self.graph().complete)
        self.assertIn(
            "article/settled", [node.id for node in self.graph().unreached]
        )

    def test_an_escalated_piece_refuses_the_build_and_names_the_remedy(self):
        self.escalate()

        with self.assertRaises(ValidationError) as raised:
            self.magazine.build(EDITION)

        message = "\n".join(raised.exception.errors)
        self.assertIn("article/settled", message)
        self.assertIn("escalated", message)
        self.assertIn("repair it by hand", message)

    def test_an_escalation_stops_the_issue_stage_and_the_run_says_so(self):
        runner = RoleRunner(
            **{f"article:{PIECE_JUDGE_LENSES[0].kind}": changes("still wrong")}
        )

        result = Production(
            self.magazine, runner=runner, gates=PassingGates(), max_rounds=2
        ).run(EDITION)

        self.assertNotIn("issue", [piece for piece, _, _ in runner.calls])
        self.assertFalse(result.complete)
        self.assertIn("issue/edition", result.unreached)


class InconsistencyTests(GraphFixture):
    """Finished work the records do not carry is louder than missing work.

    The editorial's ``r1-evidence`` and ``r1-line`` replies both said approved
    and both sat on disk while its record carried ``judges: {}``; a voided
    writer reply had stopped the replay at round one, so the pipeline never
    asked for judgments it already had.  No further produce run notices that on
    its own -- it is not missing an answer, it is missing the *record* of one --
    which is why the state has to be detected by comparing the two places the
    truth lives, and why it is terminal rather than merely pending.
    """

    def strand_the_editorial_judges(self) -> None:
        """Reproduce the state the audit found, byte for byte in shape."""

        self.produce(RoleRunner())
        record_path = piece_record_path(self.magazine.editions_dir, EDITION, "editorial")
        record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
        record["status"] = "drafting"
        for entry in record["rounds"]:
            entry["judges"] = {}
            entry["result"] = "changes_required"
        record_path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
        for kind in self.editorial_lenses():
            item = (
                self.magazine.editions_dir
                / EDITION
                / "production"
                / "agent"
                / "editorial"
                / f"r1-{kind.replace('_', '-')}"
            )
            item.mkdir(parents=True, exist_ok=True)
            (item / "reply.md").write_text(verdict("approved"), encoding="utf-8")

    @staticmethod
    def editorial_lenses() -> tuple[str, ...]:
        """The lenses that read the editorial, which is not all of them."""

        return tuple(
            lens.kind
            for lens in PIECE_JUDGE_LENSES
            if lens_applies(
                lens, piece_id="editorial", content_mode="original_editorial"
            )
        )

    def test_an_answered_brief_the_record_does_not_carry_is_inconsistent(self):
        self.strand_the_editorial_judges()

        states = self.states()
        for kind in self.editorial_lenses():
            with self.subTest(lens=kind):
                self.assertEqual(states[f"editorial/judge.{kind}"], INCONSISTENT)
        # A lens that never reads the editorial is not "missing an answer": it
        # is accepting, which is the whole reason ``not_applicable`` exists.
        self.assertEqual(states["editorial/judge.worth"], NOT_APPLICABLE)

    def test_an_inconsistency_is_never_accepting_and_refuses_the_build(self):
        self.strand_the_editorial_judges()

        self.assertFalse(self.graph().complete)
        with self.assertRaises(ValidationError) as raised:
            self.magazine.build(EDITION)

        message = "\n".join(raised.exception.errors)
        self.assertIn("editorial/judge.", message)
        self.assertIn("reply on disk that the record does not carry", message)

    def test_a_passed_record_bound_to_different_bytes_is_inconsistent(self):
        """What was judged must be what would be built."""

        self.produce(RoleRunner())
        manuscript = self.root / "editions" / EDITION / "articles" / "article.md"
        manuscript.write_text(
            manuscript.read_text(encoding="utf-8") + "\nA later hand edit.\n",
            encoding="utf-8",
        )

        self.assertEqual(self.states()["article/settled"], INCONSISTENT)
        with self.assertRaises(ValidationError):
            self.magazine.build(EDITION)


class UnresolvableEditionTests(GraphFixture):
    def test_a_missing_manifest_defers_to_the_loader_rather_than_burying_it(self):
        """The staging-marker precedent: do not pre-empt a better error.

        An edition with no readable manifest has no piece list, so no graph can
        be resolved -- but "the production graph is incomplete" is a far worse
        thing to tell an operator than "your edition.yaml does not parse", and
        whoever loads the edition is about to say the second.
        """

        (self.magazine.editions_dir / EDITION / "edition.yaml").unlink()

        graph = self.graph()

        self.assertTrue(graph.deferred)
        self.assertTrue(graph.problems)
        # Explains itself when asked, and stands aside when enforcing.
        self.assertIn("cannot be resolved yet", graph.summary())
        require_complete_production_graph(
            self.root, self.magazine.editions_dir, EDITION
        )


class LegacyEditionTests(GraphFixture):
    def test_an_edition_produce_never_touched_is_not_refused(self):
        """Editions authored before the pipeline existed still build.

        The graph asks whether *this* pipeline finished; it must not retroize
        into a claim that hand-authored issues were never edited.  An edition
        with no production directory at all is that case, and it is the only
        one -- a staged but undrafted edition carries staging markers, which
        ``validate`` refuses with a much better message.
        """

        graph = self.graph()

        self.assertTrue(graph.legacy)
        self.assertTrue(graph.complete)
        require_complete_production_graph(
            self.root, self.magazine.editions_dir, EDITION
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
