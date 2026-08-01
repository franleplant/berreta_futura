"""The cooperative backend: emit, ingest, and everything that must not change.

Nothing here runs a model, and unlike ``test_produce.py`` nothing here even has
a runner to fake: under ``--backend agent`` the pipeline writes briefs to disk
and reads replies back, so the tests *are* the driver.  That is also what makes
the context assertions cheap -- the brief a role was shown is a file.

The stand-in driver is :class:`Fleet`, which answers every brief in a ready set
the way a subagent fan-out would.  A test that cares about a particular answer
scripts it by ``(role, piece)``; everything else gets a plausible default.
"""

import hashlib
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from magazine import Magazine
from magazine.cli import main
from magazine.produce import MAX_ROUNDS
from magazine.produce_agent import (
    AgentSession,
    agent_dir,
    load_replies,
    ready_path,
)
from magazine.produce_prompts import SCRATCH_MARKER, ProduceError
from magazine.production_record import piece_record_path
from magazine.runner import AGENT_BACKEND, TEXT_BACKENDS, RunnerConfig, RunnerError

from test_manifest import add_extraction, add_source, make_project, pin_article_source_hash
from test_produce import (
    EXTRACTION_BODY,
    MANAGER_RUN_A,
    LEARNING_RUN_B,
    SOURCE_ONLY,
    PassingGates,
    build_project,
    changes,
    draft,
    snapshot,
    verdict,
)


SECOND_ONLY = "The second source counted forty-two separate incident reports."
SECOND_BODY = (
    "A second original article.\n"
    f"{SECOND_ONLY}\n"
    "And a closing paragraph about the same operational consequences.\n"
)


def build_two_article_project(root: Path) -> Magazine:
    """``build_project`` plus a second, independently sourced article.

    Two independent articles is the smallest edition that can prove the thing
    the agent backend exists for: that both writer briefs are offered at once
    rather than one after the other.
    """

    build_project(root)
    add_source(root, "source-two", body=SECOND_BODY)
    digest = add_extraction(root, source_id="source-two", body=SECOND_BODY)
    manifest_path = root / "editions" / "issue-001" / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["articles"].append(
        {
            "id": "second",
            "title": "Second",
            "short_title": "Second",
            "opener_variant": "edge_medallion",
            "author": "Author",
            "author_note": "Author is chief architect at Example Company.",
            "source_ids": ["source-two"],
            "source_body_sha256": digest,
            "manuscript": "editions/issue-001/articles/second.md",
        }
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    (root / "editions" / "issue-001" / "articles" / "second.md").write_text(
        "A second original article.\n", encoding="utf-8"
    )
    return Magazine(root)


class Fleet:
    """A driver's subagents, standing still: answers every brief in a set.

    ``script[(role, piece)]`` supplies replies in order and repeats the last
    one, exactly as ``test_produce``'s scripted command does, so the two files
    describe the same runs in the same vocabulary.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.script: dict[tuple[str, str], list[str]] = {}
        self.seen: list[tuple[str, str]] = []
        self.briefs: dict[str, str] = {}

    def work(self, result) -> list[str]:
        """Answer every ready brief; return the item names that were answered."""

        answered: list[str] = []
        for item in result.ready:
            brief = (self.root / item.brief_path).read_text(encoding="utf-8")
            self.briefs[item.key] = brief
            self.seen.append((item.item.role, item.item.piece_id))
            (self.root / item.reply_path).write_text(
                self.reply(item), encoding="utf-8"
            )
            answered.append(item.key)
        return answered

    def reply(self, item) -> str:
        role, piece = item.item.role, item.item.piece_id
        scripted = self.script.get((role, piece)) or self.script.get((role, "*"))
        if scripted:
            return scripted.pop(0) if len(scripted) > 1 else scripted[0]
        if role == "writer":
            return draft(piece, item.item.round_number)
        if role == "manager_run_a":
            return MANAGER_RUN_A
        if role == "learning":
            return LEARNING_RUN_B
        return verdict("approved")

    def brief(self, item_key: str) -> str:
        return self.briefs[item_key]


class AgentFixture(unittest.TestCase):
    articles = 1

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.magazine = (
            build_two_article_project(self.root)
            if self.articles == 2
            else build_project(self.root)
        )
        self.gates = PassingGates()
        self.fleet = Fleet(self.root)
        self.reports: list = []

    def session(self, *, max_rounds: int = MAX_ROUNDS) -> AgentSession:
        return AgentSession(
            self.magazine, gates=self.gates, max_rounds=max_rounds
        )

    def advance(self, *, max_rounds: int = MAX_ROUNDS, **kwargs):
        result = self.session(max_rounds=max_rounds).advance("issue-001", **kwargs)
        self.reports.append(result)
        return result

    @property
    def recorded(self) -> set[str]:
        """Every bench record any invocation of the loop wrote."""

        return {kind for report in self.reports for kind in report.recorded}

    def keys(self, result) -> list[str]:
        return [item.key for item in result.ready]

    def drive(self, *, rounds: int = 12, max_rounds: int = MAX_ROUNDS, **kwargs):
        """Run the whole loop the way a driver would, and return the last report."""

        result = self.advance(max_rounds=max_rounds, **kwargs)
        for _ in range(rounds):
            if not result.ready:
                return result
            self.fleet.work(result)
            result = self.advance(max_rounds=max_rounds, **kwargs)
        raise AssertionError("the emit/ingest loop did not settle")

    def record(self, piece_id: str) -> dict:
        path = piece_record_path(self.magazine.editions_dir, "issue-001", piece_id)
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def manuscript(self, name: str = "articles/article.md") -> str:
        return (self.root / "editions" / "issue-001" / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Emitting.


class ReadySetTests(AgentFixture):
    articles = 2

    def test_every_independent_writer_brief_is_emitted_at_once(self):
        """The whole point: a fleet fans out, so a fleet is handed a set."""

        result = self.advance()

        self.assertEqual(
            self.keys(result), ["article/r1-writer", "second/r1-writer"]
        )
        for item in result.ready:
            self.assertEqual(item.returns, "manuscript")
            self.assertTrue((self.root / item.brief_path).is_file())
            self.assertFalse((self.root / item.reply_path).exists())

    def test_the_editorial_waits_for_the_pieces_it_is_grounded_in(self):
        result = self.advance()

        self.assertNotIn("editorial/r1-writer", self.keys(result))
        waiting = {
            outcome.piece_id: outcome.status for outcome in result.outcomes
        }
        self.assertEqual(waiting["editorial"], "waiting")
        self.assertEqual(waiting["article"], "parked")

    def test_the_editorial_is_emitted_once_every_article_has_passed(self):
        result = self.advance()
        while "editorial/r1-writer" not in self.keys(result):
            self.assertTrue(result.ready, "the loop stalled before the editorial")
            self.fleet.work(result)
            result = self.advance()

        brief = self.fleet.brief("article/r1-writer")
        editorial = (
            self.root
            / [
                item.brief_path
                for item in result.ready
                if item.key == "editorial/r1-writer"
            ][0]
        ).read_text(encoding="utf-8")
        self.assertIn("The original article.", brief)
        # Grounded in the finished articles, never in the staged stubs.
        self.assertIn("A draft of article, round 1.", editorial)
        self.assertIn("A draft of second, round 1.", editorial)


class ParallelJudgeTests(AgentFixture):
    def test_both_piece_judges_are_ready_at_the_same_time(self):
        first = self.advance()
        self.fleet.work(first)

        second = self.advance()

        self.assertEqual(
            self.keys(second), ["article/r1-evidence", "article/r1-line"]
        )
        self.assertEqual(
            [item.returns for item in second.ready], ["verdict", "verdict"]
        )

    def test_a_brief_carries_everything_the_worker_needs(self):
        result = self.advance()

        item = result.ready[0]
        brief = (self.root / item.brief_path).read_text(encoding="utf-8")
        # The prompt file, the assignment, the whole extraction, the contract.
        self.assertTrue(brief.startswith("# Faithful-edit production prompt"), brief[:60])
        self.assertIn("- Piece id: `article`", brief)
        for line in EXTRACTION_BODY.strip().splitlines():
            self.assertIn(line, brief)
        self.assertIn(SCRATCH_MARKER, brief)
        descriptor = yaml.safe_load(
            (self.root / item.brief_path).parent.joinpath("item.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(descriptor["item"], "article/r1-writer")
        self.assertEqual(descriptor["prompt_path"], "prompts/faithful-edit.md")
        self.assertEqual(
            descriptor["brief_sha256"], hashlib.sha256(brief.encode()).hexdigest()
        )


# ---------------------------------------------------------------------------
# Ingesting.


class IngestTests(AgentFixture):
    def test_a_submitted_reply_advances_the_state_machine(self):
        first = self.advance()

        result = self.session().submit(
            "issue-001", "article/r1-writer", draft("article", 1)
        )

        self.assertEqual(self.keys(first), ["article/r1-writer"])
        self.assertEqual(
            self.keys(result), ["article/r1-evidence", "article/r1-line"]
        )
        self.assertIn("A draft of article, round 1.", self.manuscript())
        self.assertEqual(self.record("article")["rounds"][0]["round"], 1)

    def test_a_reply_dropped_beside_the_brief_is_ingested_too(self):
        """The file is the protocol; --submit is the same write, checked first."""

        first = self.advance()
        (self.root / first.ready[0].reply_path).write_text(
            draft("article", 1), encoding="utf-8"
        )

        result = self.advance()

        self.assertEqual(
            self.keys(result), ["article/r1-evidence", "article/r1-line"]
        )

    def test_an_unknown_item_is_refused_by_name(self):
        self.advance()

        with self.assertRaises(ProduceError) as raised:
            self.session().submit("issue-001", "article/r9-writer", draft("article", 9))

        self.assertIn("no work item named 'article/r9-writer'", str(raised.exception))
        self.assertIn("--backend agent", str(raised.exception))

    def test_a_malformed_item_name_is_refused_rather_than_resolved(self):
        for name in ("../../etc/passwd", "article", "article/../../x"):
            with self.subTest(name=name):
                with self.assertRaises(ProduceError):
                    self.session().submit("issue-001", name, "text")

    def redraft(self, text: str) -> None:
        """Replace the stored round-one draft, as a re-run writer would."""

        (
            agent_dir(self.magazine.editions_dir, "issue-001")
            / "article"
            / "r1-writer"
            / "reply.md"
        ).write_text(text, encoding="utf-8")

    def test_a_stale_reply_is_refused_and_the_brief_is_reissued(self):
        """A judge brief embeds the manuscript, so a redraft voids it."""

        self.fleet.work(self.advance())
        judged = self.advance()
        line = [item for item in judged.ready if item.key == "article/r1-line"][0]
        stale_brief = (self.root / line.brief_path).read_text(encoding="utf-8")
        # The line editor is still reading while the writer is re-run.
        self.redraft(draft("article", 1, headings=("A section the judge never saw",)))
        (self.root / line.reply_path).write_text(verdict("approved"), encoding="utf-8")

        result = self.advance()

        self.assertTrue(
            any("was not applied" in action for action in result.human_actions),
            result.human_actions,
        )
        directory = self.root / Path(line.reply_path).parent
        self.assertTrue((directory / "reply.superseded.md").is_file())
        self.assertFalse((directory / "reply.md").exists())
        reissued = (directory / "brief.md").read_text(encoding="utf-8")
        self.assertNotEqual(reissued, stale_brief)
        self.assertIn("article/r1-line", self.keys(result))

    def test_submitting_a_verdict_on_a_superseded_draft_raises(self):
        self.fleet.work(self.advance())
        self.advance()
        self.redraft(draft("article", 1, headings=("A section the judge never saw",)))

        with self.assertRaises(ProduceError) as raised:
            self.session().submit("issue-001", "article/r1-line", verdict("approved"))

        self.assertIn("was not applied", str(raised.exception))
        self.assertIn("recomposed", str(raised.exception))

    def test_a_moved_prompt_voids_the_draft_written_against_the_old_one(self):
        self.fleet.work(self.advance())
        prompt = self.root / "prompts" / "faithful-edit.md"
        prompt.write_bytes(prompt.read_bytes() + b"\nOne more rule.\n")

        result = self.advance()

        self.assertEqual(self.keys(result), ["article/r1-writer"])
        self.assertTrue(
            any("recomposed" in action for action in result.human_actions),
            result.human_actions,
        )

    def test_a_verdict_that_is_not_the_bench_s_contract_is_refused(self):
        self.fleet.work(self.advance())
        self.advance()

        with self.assertRaises(ProduceError) as raised:
            self.session().submit(
                "issue-001", "article/r1-line", "It reads pretty well to me.\n"
            )
        self.assertIn("article/r1-line", str(raised.exception))
        self.assertIn("the one YAML mapping its prompt requires", str(raised.exception))

        with self.assertRaises(ProduceError) as raised:
            self.session().submit(
                "issue-001", "article/r1-line", "result: looks_fine\nfindings: []\n"
            )
        self.assertIn("returned result 'looks_fine'", str(raised.exception))
        self.assertIn("approved or changes_required", str(raised.exception))

    def test_unparseable_yaml_is_refused_with_the_parser_s_complaint(self):
        self.fleet.work(self.advance())
        self.advance()

        with self.assertRaises(ProduceError) as raised:
            self.session().submit(
                "issue-001", "article/r1-line", "result: approved\n  findings: ]\n"
            )

        self.assertIn("did not return parseable YAML", str(raised.exception))

    def test_a_manuscript_that_is_only_notes_is_refused(self):
        self.advance()

        with self.assertRaises(ProduceError) as raised:
            self.session().submit(
                "issue-001", "article/r1-writer", f"{SCRATCH_MARKER}\nonly notes\n"
            )

        self.assertIn("no manuscript", str(raised.exception))
        self.assertFalse(
            (
                agent_dir(self.magazine.editions_dir, "issue-001")
                / "article"
                / "r1-writer"
                / "reply.md"
            ).exists()
        )

    def test_a_finding_the_bench_cannot_store_is_refused(self):
        self.fleet.work(self.advance())
        self.advance()

        with self.assertRaises(ProduceError) as raised:
            self.session().submit(
                "issue-001",
                "article/r1-line",
                yaml.safe_dump(
                    {
                        "result": "changes_required",
                        "findings": [{"note": "it repeats"}],
                    },
                    sort_keys=False,
                ),
            )

        self.assertIn("article/r1-line", str(raised.exception))

    def test_a_stored_answer_the_pipeline_refuses_names_the_way_out(self):
        """A run B that improved run A's claims wedges a deterministic replay."""

        revised = yaml.safe_load(LEARNING_RUN_B)
        revised["manager_takeaways"][0]["claims"] = [
            "Claim one.",
            "A better claim the body happens to support.",
            "Claim three.",
        ]
        self.fleet.script[("learning", "issue")] = [
            yaml.safe_dump(revised, sort_keys=False)
        ]

        with self.assertRaises(ProduceError) as raised:
            self.drive()

        message = str(raised.exception)
        self.assertIn("rewrote run A", message)
        self.assertIn("editions/issue-001/production/agent", message)
        self.assertIn("brief reissued", message)

    def test_a_bad_reply_left_on_disk_keeps_the_item_ready_and_says_why(self):
        first = self.advance()
        (self.root / first.ready[0].reply_path).write_text(
            f"{SCRATCH_MARKER}\nonly notes\n", encoding="utf-8"
        )

        result = self.advance()

        self.assertEqual(self.keys(result), ["article/r1-writer"])
        self.assertTrue(
            any("no manuscript" in action for action in result.human_actions),
            result.human_actions,
        )


# ---------------------------------------------------------------------------
# The whole loop.


class EndToEndTests(AgentFixture):
    def test_a_full_edition_completes_through_emit_and_ingest_only(self):
        result = self.drive()

        self.assertEqual(result.ready, ())
        self.assertEqual(
            [(outcome.piece_id, outcome.status) for outcome in result.outcomes],
            [("article", "settled"), ("editorial", "settled")],
        )
        self.assertEqual(self.recorded, {"evidence", "line", "learning", "edition"})
        for kind in ("evidence", "line", "learning", "edition"):
            self.assertTrue(
                (
                    self.root / "editions" / "issue-001" / "reviews" / f"{kind}.yaml"
                ).is_file(),
                kind,
            )
        # The roles ran in the pipeline's order, not the driver's.
        self.assertEqual(
            self.fleet.seen[:3],
            [("writer", "article"), ("evidence", "article"), ("line", "article")],
        )
        self.assertEqual(
            self.fleet.seen[-3:],
            [
                ("manager_run_a", "issue"),
                ("learning", "issue"),
                ("edition", "issue"),
            ],
        )

    def test_the_provenance_record_names_the_agent_and_the_brief_it_answered(self):
        self.drive()

        writer = self.record("article")["rounds"][0]["writer"]
        self.assertEqual(writer["backend"], AGENT_BACKEND)
        self.assertEqual(writer["prompt_path"], "prompts/faithful-edit.md")
        self.assertIn("--submit", writer["argv"])
        self.assertIn("article/r1-writer", writer["argv"])
        self.assertIn("--brief-sha256", writer["argv"])
        self.assertEqual(len(writer["prompt_sha256"]), 64)

    def test_the_ready_file_answers_where_this_edition_is(self):
        first = self.advance()

        state = yaml.safe_load(
            ready_path(self.magazine.editions_dir, "issue-001").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(state["state"], "awaiting_work")
        self.assertEqual([row["item"] for row in state["ready"]], self.keys(first))

        self.drive()

        state = yaml.safe_load(
            ready_path(self.magazine.editions_dir, "issue-001").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(state["state"], "complete")
        self.assertEqual(state["ready"], [])

    def test_a_settled_edition_emits_nothing_and_costs_no_work(self):
        self.drive()

        again = self.advance()

        self.assertEqual(again.ready, ())
        self.assertEqual(
            {outcome.status for outcome in again.outcomes}, {"settled"}
        )


class ResumeTests(AgentFixture):
    articles = 2

    def test_re_emitting_mid_fleet_is_byte_identical_and_never_duplicates(self):
        """A driver that crashes and re-emits must get the set, not a second copy."""

        first = self.advance()
        before = snapshot(self.root)

        again = self.advance()

        self.assertEqual(self.keys(again), self.keys(first))
        self.assertEqual(snapshot(self.root), before)

    def test_a_half_answered_fleet_resumes_on_exactly_what_is_left(self):
        first = self.advance()
        answered = [item for item in first.ready if item.key == "second/r1-writer"][0]
        (self.root / answered.reply_path).write_text(
            draft("second", 1), encoding="utf-8"
        )

        result = self.advance()

        self.assertEqual(
            self.keys(result),
            ["article/r1-writer", "second/r1-evidence", "second/r1-line"],
        )


class EscalationTests(AgentFixture):
    def test_three_rounds_then_escalation_with_every_finding_accumulated(self):
        self.fleet.script[("line", "article")] = [changes("round one repeats")]

        result = self.drive(articles=["article"])

        outcome = result.outcomes[0]
        self.assertEqual((outcome.status, outcome.rounds), ("escalated", MAX_ROUNDS))
        record = self.record("article")
        self.assertEqual(record["status"], "escalated")
        self.assertEqual(len(record["rounds"]), MAX_ROUNDS)
        notes = [finding["note"] for finding in record["escalation"]["findings"]]
        self.assertEqual(notes.count("round one repeats"), MAX_ROUNDS)
        self.assertFalse(
            any(role == "manager_run_a" for role, _ in self.fleet.seen),
            "an unfinished issue must not reach the whole-issue judges",
        )

    def test_the_escalation_names_how_a_driver_offers_the_piece_a_fresh_start(self):
        self.fleet.script[("line", "article")] = [changes("round one repeats")]

        result = self.drive(articles=["article"])

        self.assertTrue(
            any(
                "delete editions/issue-001/production/agent/article" in action
                for action in result.human_actions
            ),
            result.human_actions,
        )

    def test_discarding_a_piece_s_answers_redrafts_it_from_round_one(self):
        self.fleet.script[("line", "article")] = [changes("round one repeats")]
        self.drive(articles=["article"])
        import shutil

        shutil.rmtree(agent_dir(self.magazine.editions_dir, "issue-001") / "article")

        result = self.advance(articles=["article"])

        self.assertEqual(self.keys(result), ["article/r1-writer"])


# ---------------------------------------------------------------------------
# Every boundary the autonomous path enforces, enforced on this path too.


class BoundaryTests(AgentFixture):
    def test_the_line_editor_s_brief_never_carries_the_source(self):
        self.fleet.work(self.advance())
        self.advance()

        line = self.fleet.brief  # populated by the next work() call
        self.fleet.work(self.advance())
        self.assertNotIn(SOURCE_ONLY, line("article/r1-line"))
        self.assertIn(SOURCE_ONLY, line("article/r1-evidence"))
        self.assertIn(
            "source extraction is deliberately withheld", line("article/r1-line")
        )

    def test_the_manager_s_two_runs_stay_two_briefs_and_run_a_is_starved(self):
        self.drive()

        run_a = self.fleet.brief("issue/manager-run-a")
        run_b = self.fleet.brief("issue/learning")
        self.assertIn("Marcus, run A only", run_a)
        self.assertNotIn("A draft of article, round 1.", run_a)
        self.assertNotIn(SOURCE_ONLY, run_a)
        self.assertIn("A draft of article, round 1.", run_b)
        self.assertIn("Pilot the thing this quarter.", run_b)

    def test_scratch_notes_reach_the_next_writer_and_nothing_else(self):
        self.fleet.script[("line", "article")] = [
            changes("the second example repeats the first"),
            verdict("approved"),
        ]

        self.drive(articles=["article"])

        self.assertNotIn("concept graph", self.manuscript())
        self.assertNotIn(SCRATCH_MARKER, self.manuscript())
        for role in ("evidence", "line"):
            self.assertNotIn("concept graph", self.fleet.brief(f"article/r1-{role}"))
        second = self.fleet.brief("article/r2-writer")
        self.assertIn("concept graph for article round 1", second)
        self.assertIn("the second example repeats the first", second)

    def test_a_gate_failure_costs_a_round_and_never_reaches_a_judge(self):
        self.gates = _RoundOneGates("the fence is not the source's")

        self.drive(articles=["article"])

        self.assertNotIn("article/r1-evidence", self.fleet.briefs)
        self.assertIn("article/r2-evidence", self.fleet.briefs)
        self.assertIn(
            "the fence is not the source's", self.fleet.brief("article/r2-writer")
        )

    def test_no_image_runner_is_reachable_from_the_cooperative_backend(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "magazine"
            / "produce_agent.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("resolve_image_runner", source)
        self.assertNotIn("image_backend", source)


class FirstRunTests(unittest.TestCase):
    """The very first produce run of a freshly staged edition.

    Every manuscript is still the staging marker ``mag article stage`` wrote,
    and an HTML comment is a block the publication parser refuses. Through the
    real gates that used to escape as a bare ``DocumentParseError`` and abort
    the command, which is the one run the front door must survive.
    """

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.magazine = build_project(self.root)
        (self.root / "editions" / "issue-001" / "articles" / "article.md").write_text(
            "---\nstage_status: todo\nlabel: EDITORIAL WORK REQUIRED\n---\n\n"
            "<!-- TODO(editor): Replace this staging marker. -->\n",
            encoding="utf-8",
        )

    def test_a_staged_stub_is_a_reported_gate_failure_not_a_traceback(self):
        from magazine.produce import DefaultProductionGates

        session = AgentSession(
            self.magazine, gates=DefaultProductionGates(self.magazine)
        )

        result = session.advance("issue-001", articles=["article"])

        self.assertEqual([item.key for item in result.ready], ["article/r1-writer"])
        self.assertTrue(
            any(
                "pre-existing gate failure" in action
                for action in result.human_actions
            ),
            result.human_actions,
        )


class _RoundOneGates:
    """Refuse any draft that still says it is round one.

    Every invocation replays the pipeline, so the gates run again from the top
    each time.  A fake that popped a queue would therefore answer differently on
    each replay and make the loop non-deterministic -- which is exactly the
    property the real gates do not have, being a function of the bytes on disk.
    This one is a function of the bytes too.
    """

    def __init__(self, detail: str, *, piece_id: str = "article") -> None:
        self.detail = detail
        self.piece_id = piece_id

    def check_piece(self, piece, extractions):
        from magazine.produce import GateResult

        text = piece.manuscript.read_text(encoding="utf-8")
        if piece.id == self.piece_id and "round 1." in text:
            return (GateResult("scripted", False, self.detail),)
        return (GateResult("scripted", True),)

    def check_edition(self, edition_id):
        from magazine.produce import GateResult

        return (GateResult("validate", True), GateResult("fit", True))


class FigureAnchorTests(unittest.TestCase):
    """A rewrite changes headings, and a figure anchor is an exact heading."""

    def setUp(self):
        from test_manifest import add_curated_figure

        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.magazine = build_project(self.root)
        add_curated_figure(self.root)
        edition_path = self.root / "editions" / "issue-001" / "edition.yaml"
        edition = yaml.safe_load(edition_path.read_text(encoding="utf-8"))
        edition["articles"][0]["figures"][0]["anchor"] = "The kill chain"
        edition_path.write_text(
            yaml.safe_dump(edition, sort_keys=False), encoding="utf-8"
        )
        (self.root / "editions" / "issue-001" / "articles" / "article.md").write_text(
            "The original article.\n\n## The kill chain\n\nSomething.\n",
            encoding="utf-8",
        )

    def test_a_stranded_figure_fails_the_gate_and_the_brief_says_so(self):
        from test_produce import _AnchorOnlyGates

        session = AgentSession(self.magazine, gates=_AnchorOnlyGates())
        fleet = Fleet(self.root)
        fleet.script[("writer", "article")] = [
            draft("article", 1, headings=("A different heading",)),
            draft("article", 2, headings=("The kill chain",)),
        ]
        result = session.advance("issue-001", articles=["article"])
        for _ in range(8):
            if not result.ready:
                break
            fleet.work(result)
            result = session.advance("issue-001", articles=["article"])

        self.assertEqual(result.outcomes[0].status, "settled")
        # Round one stranded the figure, so no judge was ever paid for it.
        self.assertNotIn("article/r1-evidence", fleet.briefs)
        self.assertIn("article/r2-evidence", fleet.briefs)
        self.assertIn(
            "figure 'diagram' is anchored to the heading 'The kill chain'",
            fleet.brief("article/r2-writer"),
        )


# ---------------------------------------------------------------------------
# Selection and the CLI.


class BackendSelectionTests(AgentFixture):
    def test_the_backend_is_named_the_same_way_as_the_other_two(self):
        self.assertIn(AGENT_BACKEND, TEXT_BACKENDS)
        path = self.root / "magazine.toml"
        path.write_text(
            path.read_text(encoding="utf-8") + '\ntext_backend = "agent"\n',
            encoding="utf-8",
        )

        self.assertEqual(RunnerConfig.load(self.root).text_backend, AGENT_BACKEND)

    def test_the_agent_backend_resolves_no_process(self):
        config = RunnerConfig.load(self.root).with_text_backend(AGENT_BACKEND)

        from magazine.runner import resolve_text_runner

        with self.assertRaises(RunnerError) as raised:
            resolve_text_runner(config)

        self.assertIn("runs no process", str(raised.exception))

    def test_submit_is_refused_for_a_backend_that_calls_the_model_itself(self):
        with self.assertRaises(ProduceError) as raised:
            self.magazine.produce(
                "issue-001", backend="codex", submit=("article/r1-writer", "text")
            )

        self.assertIn("--submit", str(raised.exception))

    def test_a_dry_run_writes_nothing_at_all(self):
        before = snapshot(self.root)

        result = self.magazine.produce(
            "issue-001", backend=AGENT_BACKEND, dry_run=True, gates=self.gates
        )

        self.assertTrue(result.dry_run)
        self.assertEqual(result.ready, ())
        self.assertEqual(snapshot(self.root), before)


class CliTests(AgentFixture):
    def run_cli(self, argv: list[str], *, stdin: str | None = None) -> tuple[int, str]:
        import sys
        from unittest.mock import patch

        out = io.StringIO()
        with patch.object(sys, "stdin", io.StringIO(stdin or "")):
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                code = main(["--root", str(self.root), *argv])
        return code, out.getvalue()

    def test_emit_then_submit_is_the_whole_loop(self):
        code, output = self.run_cli(["produce", "issue-001", "--backend", "agent"])

        self.assertEqual(code, 0, output)
        self.assertIn("ready: article/r1-writer (manuscript)", output)
        self.assertIn(
            "editions/issue-001/production/agent/article/r1-writer/brief.md", output
        )
        self.assertIn("next: answer the 1 brief(s) above", output)

        code, output = self.run_cli(
            [
                "produce",
                "issue-001",
                "--backend",
                "agent",
                "--submit",
                "article/r1-writer",
            ],
            stdin=draft("article", 1),
        )

        self.assertEqual(code, 0, output)
        self.assertIn("ready: article/r1-evidence", output)
        self.assertIn("ready: article/r1-line", output)

    def test_a_reply_file_is_accepted_instead_of_stdin(self):
        self.run_cli(["produce", "issue-001", "--backend", "agent"])
        reply = self.root / "reply.md"
        reply.write_text(draft("article", 1), encoding="utf-8")

        code, output = self.run_cli(
            [
                "produce",
                "issue-001",
                "--backend",
                "agent",
                "--submit",
                "article/r1-writer",
                "--reply",
                str(reply),
            ]
        )

        self.assertEqual(code, 0, output)
        self.assertIn("ready: article/r1-evidence", output)

    def test_the_json_report_carries_the_ready_set_a_driver_scripts_on(self):
        import json

        code, output = self.run_cli(
            ["produce", "issue-001", "--backend", "agent", "--json"]
        )

        self.assertEqual(code, 0, output)
        payload = json.loads(output)
        self.assertEqual(
            [row["item"] for row in payload["ready"]], ["article/r1-writer"]
        )
        row = payload["ready"][0]
        self.assertEqual(row["returns"], "manuscript")
        self.assertEqual(
            row["brief"], "editions/issue-001/production/agent/article/r1-writer/brief.md"
        )
        self.assertEqual(
            row["reply"], "editions/issue-001/production/agent/article/r1-writer/reply.md"
        )

    def test_an_empty_submission_is_refused_rather_than_ingested(self):
        self.run_cli(["produce", "issue-001", "--backend", "agent"])

        code, _ = self.run_cli(
            [
                "produce",
                "issue-001",
                "--backend",
                "agent",
                "--submit",
                "article/r1-writer",
            ],
            stdin="   \n",
        )

        self.assertEqual(code, 2)
        self.assertEqual(
            load_replies(self.magazine.editions_dir, "issue-001"), {}
        )


if __name__ == "__main__":
    unittest.main()
