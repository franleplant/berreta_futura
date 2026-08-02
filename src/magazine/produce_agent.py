"""The cooperative text backend: the pipeline emits briefs and ingests answers.

``codex exec`` and ``claude -p`` are both *callable*: produce hands them a
prompt and blocks until an answer comes back.  Two of the three ways this
magazine actually gets written are not callable at all.  A Claude Code agent
driving an edition has a subagent fleet, and no Python process can spawn one.  A
human has a text editor.  Neither can be shelled out to, so under the autonomous
model neither could be driven by the pipeline -- and when the autonomous backend
hit a bug, the driving agent went around the pipeline and hand-fired writer
subagents itself, which is exactly the ad-hoc orchestration ``mag produce``
exists to abolish.

So the call is inverted.  Under ``--backend agent`` a "model call" writes the
composed brief to disk and reports it; a later invocation finds the answer
beside it and carries on.  Everything above that seam is unchanged, and that is
the entire point: the pipeline still owns the drafting order, the deterministic
gates, which judge runs when, the round count, escalation at three rounds, the
provenance records and the recorded verdicts.  The worker supplies text.

**The whole ready set, not the next item.**  Emitting one brief at a time would
serialise a fleet, so :meth:`AgentSession.advance` composes every brief that is
unblocked *right now* and reports them together: several writers at once while
their pieces are independent, and a whole stage of a piece's lenses together the
moment its draft clears the gates.  A stage is two calls wide, so the fan-out is
real and it is the unit a driver picks up.  The pipeline reaches that set
by running normally and treating an unanswered call as a park rather than a
failure (:class:`~magazine.produce.WorkParked`), so the set is derived from the
real state machine and can never drift from it.

**Everything is derived; nothing is remembered.**  There is no session cursor.
Each invocation replays the pipeline from the answers on disk, which is what
makes the loop crash-proof and idempotent: a driver that dies mid-fleet and
re-emits gets the same set back, not a second copy of it.  It is also what makes
staleness free.  A work item is identified by
:func:`~magazine.produce_prompts.work_identity` -- a digest of the prompt file
and of the content the call was handed, each part by digest -- so a reply
written against a manuscript, a finding or a set of notes that has since moved
no longer matches the question it answered, and is set aside rather than
applied.

That identity deliberately excludes how a brief is *worded*.  It used to be the
digest of the composed text, and the consequence was found the hard way: a
refactor of the prompt composer landed while an edition was in flight, every
stored answer stopped matching at once, and a dozen completed and judged model
calls became unreachable through the front door.  Rewording a section heading
is not a change of question, and it must not cost a round.  Editing the prompt
*files* still does, correctly -- a revised prompt is a different instruction --
and so does editing this pipeline's own identity functions, which is the one
refactor to keep away from a running edition.

The layout under ``editions/<edition-id>/production/agent/``::

    ready.yaml                       the current ready set, at a glance
    <piece-id>/r<n>-<role>/
        brief.md                     the complete composed prompt
        item.yaml                    what it is, and the digest it answers
        reply.md                     written by the worker
    issue/<role>/                    the two whole-issue judgments

One property this rests on and does not enforce: the deterministic gates must be
a function of the tree, not of how many times they have been called.  The real
ones (:class:`~magazine.produce.DefaultProductionGates`) are, since they are
``validate`` and ``fit`` over the files on disk.  A gates adapter with a memory
would answer differently on each replay and make the ready set wander.

``reply.md`` is the whole protocol.  A driver may write it with a subagent, an
editor, or ``cat >``; ``mag produce --submit`` is the same write with the
contract checked first.  Nothing here is provenance -- that stays in the piece
records beside it -- so an item directory may be deleted at any time, and
deleting a piece's directory is how an escalated piece is offered a fresh start.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .errors import MagazineError
from .io import load_structured
from .produce import (
    MAX_ROUNDS,
    Production,
    ProductionGates,
    ProduceResult,
    ReadyItem,
    WorkItem,
    WorkParked,
)
from .produce_graph import (
    ESCALATED,
    INCONSISTENT,
    resolve_production_graph,
    role_order,
    work_contracts,
)
from .produce_prompts import (
    ProduceError,
    PromptFile,
    contains_scratch,
    parse_verdict,
    split_scratch,
)
from .production_record import AGENT_DIRNAME, production_dir, text_sha256
from .render_review import REVIEW_RESULTS, write_render_review
from .review_findings import normalize_findings
from .runner import AGENT_BACKEND, GenerationResult

if TYPE_CHECKING:  # pragma: no cover - import cycle avoidance only
    from .compiler import Magazine


AGENT_SCHEMA_VERSION = 1

READY_FILENAME = "ready.yaml"
BRIEF_FILENAME = "brief.md"
ITEM_FILENAME = "item.yaml"
REPLY_FILENAME = "reply.md"

# What each role's reply has to be for the pipeline to accept it.  These are the
# two contracts the autonomous path already enforces, named here so a brief can
# state its own on the way out and an ingest can check it on the way in.  There
# were three: ``manager_takeaways`` went with the manager persona that
# ``prompts/README.md`` retired, and a contract nothing can dispatch is a
# contract nothing can answer.
MANUSCRIPT = "manuscript"
VERDICT = "verdict"

# Both maps below are *derived* from the declared graph rather than restated.
# They were restated, and a second list of roles is a second place for a new
# judge lens to be forgotten -- which matters now, because the two piece judges
# are about to become several narrower ones.  Declaring a node in
# ``produce_graph`` is what makes its brief answerable and gives it a place in
# the report; there is no second edit.
WORK_CONTRACTS: Mapping[str, str] = work_contracts()

# Report order for a ready set.  The pipeline composes the piece judges on
# several threads, so their insertion order is scheduling; this is not.
_ROLE_RANK = role_order()

_ITEM_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")


# ---------------------------------------------------------------------------
# Where a work item lives.


def agent_dir(editions_dir: Path, edition_id: str) -> Path:
    return production_dir(editions_dir, edition_id) / AGENT_DIRNAME


def item_dir(editions_dir: Path, edition_id: str, item_key: str) -> Path:
    """The directory that holds one work item's brief and its reply.

    The key *is* the path, so a driver that has been told ``article/r2-line``
    can find the brief without consulting an index, and a human who is looking
    at a directory knows what to type.
    """

    if not _ITEM_KEY.match(item_key):
        raise ProduceError(
            f"{item_key!r} is not a work item name; they are spelled "
            "`<piece-id>/r<round>-<role>`, as in `article/r1-writer`, or "
            "`issue/<role>` for a whole-issue judgment"
        )
    piece, _, leaf = item_key.partition("/")
    return agent_dir(editions_dir, edition_id) / piece / leaf


def ready_path(editions_dir: Path, edition_id: str) -> Path:
    return agent_dir(editions_dir, edition_id) / READY_FILENAME


# ---------------------------------------------------------------------------
# Reading a reply.


def validate_reply(returns: str, text: str, *, item_key: str) -> None:
    """Refuse a reply that the pipeline could not have used.

    Deliberately the same two checks the autonomous path makes on a model's
    answer, in the same words, because the point of the agent backend is that
    the work is identical and only the courier changed.  Checking here as well
    means a worker learns its reply is unusable while it still has the context
    to fix it, rather than three items later.
    """

    if not text.strip():
        raise ProduceError(f"The reply for {item_key} is empty")
    if returns == MANUSCRIPT:
        manuscript, _ = split_scratch(text)
        if not manuscript.strip():
            raise ProduceError(
                f"The reply for {item_key} carries no manuscript: its whole text "
                "sat below the scratch marker"
            )
        if contains_scratch(manuscript):
            raise ProduceError(
                f"The reply for {item_key} carries more than one scratch marker; "
                "the manuscript boundary is ambiguous"
            )
        return
    document = parse_verdict(text, label=f"reply for {item_key}")
    result = str(document.get("result") or "").strip()
    if result not in REVIEW_RESULTS:
        raise ProduceError(
            f"The reply for {item_key} returned result {result!r}; the prompt "
            "allows " + " or ".join(sorted(REVIEW_RESULTS))
        )
    try:
        normalize_findings(document.get("findings") or (), label=f"reply for {item_key}")
    except MagazineError as error:
        raise ProduceError(str(error)) from error


@dataclass(frozen=True)
class StoredReply:
    """One answer sitting on disk, and the work digest it was written against.

    The contract it has to satisfy is not stored beside it: that comes from the
    item's role, which the pipeline knows and a stale ``item.yaml`` might not.
    """

    text: str
    work_sha256: str


def load_replies(editions_dir: Path, edition_id: str) -> dict[str, StoredReply]:
    """Every answer a worker has left, keyed by work item.

    An item directory with no ``reply.md`` is simply outstanding.  One whose
    ``item.yaml`` will not parse is skipped rather than raised on: this is a
    work queue, and a corrupted queue entry must cost a re-emit, never the run.
    """

    root = agent_dir(editions_dir, edition_id)
    if not root.is_dir():
        return {}
    replies: dict[str, StoredReply] = {}
    for descriptor in sorted(root.glob(f"*/*/{ITEM_FILENAME}")):
        reply = descriptor.parent / REPLY_FILENAME
        if not reply.is_file():
            continue
        try:
            data = load_structured(descriptor)
        except Exception:
            continue
        if not isinstance(data, Mapping):
            continue
        key = str(data.get("item") or "")
        # ``brief_sha256`` is the superseded spelling, when the digest was
        # over the composed brief's bytes.  It is still read so that an item
        # written by an older build is *refused by name* rather than skipped
        # as unparseable: a driver whose in-flight work stops being applied
        # deserves the sentence explaining why.
        digest = str(data.get("work_sha256") or data.get("brief_sha256") or "")
        if not key or not digest:
            continue
        replies[key] = StoredReply(
            text=reply.read_text(encoding="utf-8"), work_sha256=digest
        )
    return replies


# ---------------------------------------------------------------------------
# The runner that answers from disk, or parks.


class CooperativeRunner:
    """A text runner that never runs anything.

    It satisfies the small surface :class:`~magazine.produce.Production` asks of
    a runner -- ``kind``, ``backend``, and a way to make one call -- and answers
    that call from the replies already on disk.  When there is no usable answer
    it records the brief and raises :class:`~magazine.produce.WorkParked`, which
    the pipeline reads as "this unit is waiting" rather than "this run failed".
    """

    kind = "text"
    backend = AGENT_BACKEND

    def __init__(self, edition_id: str, replies: Mapping[str, StoredReply]) -> None:
        self.edition_id = edition_id
        self.replies = dict(replies)
        self.pending: dict[str, ReadyItem] = {}
        self.rejected: dict[str, str] = {}
        # Stored answers this replay actually consumed.  Everything on disk
        # that is neither here nor pending is work the run never reached, and
        # a driver is told so rather than left to notice a missing directory.
        self.answered: set[str] = set()
        # A stage's lenses are composed concurrently, so every mutation below
        # is shared state.  Every brief in the stage must survive; only one
        # signal escapes ``ordered_map``, and losing the siblings' briefs would
        # halve every ready set.
        self._lock = threading.Lock()

    def request(
        self,
        item: WorkItem,
        prompt: PromptFile,
        text: str,
        *,
        identity: str,
        cwd: Path | None = None,
    ) -> GenerationResult:
        # ``identity`` rather than a digest of ``text``: a reply is bound to
        # the question it answered, not to the wording the question happened
        # to be asked in.  See ``produce_prompts.work_identity``.
        digest = identity
        returns = WORK_CONTRACTS.get(item.role, VERDICT)
        with self._lock:
            stored = self.replies.get(item.key)
            rejection = self._rejection(item, stored, digest)
            if stored is not None and rejection is None:
                self.answered.add(item.key)
                return _answered(self.edition_id, item, stored.text, digest)
            if rejection is not None:
                self.rejected[item.key] = rejection
            self.pending[item.key] = ReadyItem(
                item=item,
                prompt=text,
                work_sha256=digest,
                prompt_path=prompt.path,
                prompt_sha256=prompt.sha256,
                returns=returns,
            )
        raise WorkParked(item)

    def _rejection(
        self, item: WorkItem, stored: StoredReply | None, digest: str
    ) -> str | None:
        """Why this answer cannot be applied, or ``None`` when it can."""

        if stored is None:
            return None
        if stored.work_sha256 != digest:
            return (
                "the question it answers has changed since it was asked -- the "
                "manuscript, a source, a finding or the prompt file moved -- so "
                "the reply is void; a fresh brief has been written and the old "
                "answer is kept beside it as reply.superseded.md"
            )
        try:
            validate_reply(
                WORK_CONTRACTS.get(item.role, VERDICT), stored.text, item_key=item.key
            )
        except ProduceError as error:
            return str(error)
        return None


def _answered(
    edition_id: str, item: WorkItem, text: str, digest: str
) -> GenerationResult:
    """Dress a worker's reply as the generation result the records expect.

    ``argv`` is the honest answer to "how was this produced": the command a
    driver ran, naming the item and the exact brief the text answers.  The
    duration is zero because the pipeline spent none; how long the worker took
    is not a fact this process has.
    """

    return GenerationResult(
        text=text,
        backend=AGENT_BACKEND,
        argv=(
            "mag",
            "produce",
            edition_id,
            "--backend",
            AGENT_BACKEND,
            "--submit",
            item.key,
            "--work-sha256",
            digest,
        ),
        stderr="",
        duration_seconds=0.0,
    )


# ---------------------------------------------------------------------------
# The driver's surface.


class AgentSession:
    """Emit the ready briefs, ingest the finished ones, report where we are.

    One object, two verbs, and no state of its own: both verbs replay the
    pipeline over whatever is on disk.  :meth:`advance` is the loop
    (``emit -> work -> emit``); :meth:`submit` is the same thing with one reply
    written first and its contract checked eagerly, so a worker that answered
    the wrong shape is told immediately instead of discovering it later.
    """

    def __init__(
        self,
        magazine: "Magazine",
        *,
        model: str | None = None,
        gates: ProductionGates | None = None,
        max_rounds: int = MAX_ROUNDS,
        reviewer: str | None = None,
    ) -> None:
        self.magazine = magazine
        self.model = model
        self.gates = gates
        self.max_rounds = max_rounds
        self.reviewer = reviewer

    # -- the loop ---------------------------------------------------------

    def advance(
        self,
        edition_id: str,
        *,
        articles: Sequence[str] | None = None,
        dry_run: bool = False,
    ) -> ProduceResult:
        """Apply every finished reply, then report every brief now ready."""

        result, _ = self._advance(edition_id, articles=articles, dry_run=dry_run)
        return result

    def submit(
        self,
        edition_id: str,
        item_key: str,
        text: str,
        *,
        articles: Sequence[str] | None = None,
    ) -> ProduceResult:
        """Take one worker's finished text and advance the pipeline on it."""

        directory = item_dir(self.magazine.editions_dir, edition_id, item_key)
        descriptor = directory / ITEM_FILENAME
        if not descriptor.is_file():
            raise ProduceError(
                f"{edition_id} has no work item named {item_key!r}. Run "
                f"`mag produce {edition_id} --backend agent` to see the briefs "
                "that are ready; only an emitted item can be answered."
            )
        data = load_structured(descriptor)
        returns = str((data or {}).get("returns") or VERDICT)
        validate_reply(returns, text, item_key=item_key)
        _write_text(directory / REPLY_FILENAME, text)

        result, rejected = self._advance(edition_id, articles=articles)
        reason = rejected.get(item_key)
        if reason is not None:
            raise ProduceError(f"The reply for {item_key} was not applied: {reason}")
        return result

    # -- one replay -------------------------------------------------------

    def _advance(
        self,
        edition_id: str,
        *,
        articles: Sequence[str] | None = None,
        dry_run: bool = False,
    ) -> tuple[ProduceResult, dict[str, str]]:
        editions_dir = self.magazine.editions_dir
        replies = load_replies(editions_dir, edition_id)
        runner = CooperativeRunner(edition_id, replies)
        production = Production(
            self.magazine,
            runner=runner,
            model=self.model,
            gates=self.gates,
            max_rounds=self.max_rounds,
            reviewer=self.reviewer,
        )
        try:
            result = production.run(edition_id, articles=articles, dry_run=dry_run)
        except ProduceError as error:
            # A reply whose shape was fine but whose *content* the pipeline
            # refuses -- a run B that improved run A's claims is the standing
            # example -- would otherwise wedge every later invocation with the
            # same message and no way out named.  The refusal stands; the way
            # out goes with it.  Only when there are stored answers to blame:
            # a missing prompt file or an unextracted source raises the same
            # type and has nothing to do with the queue.
            if not replies:
                raise
            raise ProduceError(
                f"{error} A stored answer produced this, and replaying the same "
                "answers will produce it again: rewrite the reply the message "
                "names, or delete its directory under "
                f"{_relative(self.magazine.root, agent_dir(editions_dir, edition_id))} "
                "to have the brief reissued."
            ) from error
        if dry_run:
            return result, {}
        ready = self._materialise(edition_id, runner)
        # Re-read the graph now that this replay's briefs are on disk.  The one
        # the pipeline attached was resolved before ``_materialise`` ran, and on
        # an edition's very first advance that is a moment when nothing under
        # ``production/`` exists yet -- which reads as an edition that predates
        # the pipeline, and so as vacuously complete.  Resolving after the write
        # asks the question of the tree the next command will actually see.
        graph = resolve_production_graph(
            self.magazine.root, editions_dir, edition_id
        )
        result = replace(result, graph=graph)
        actions = list(result.human_actions)
        actions.extend(
            f"the reply for {key} was not applied: {reason}"
            for key, reason in sorted(runner.rejected.items())
        )
        actions.extend(_unreached_actions(runner))
        actions.extend(self._escalation_actions(edition_id, result))
        actions.extend(_graph_actions(result, ready))
        result = replace(result, ready=ready, human_actions=tuple(actions))
        _write_ready(editions_dir, edition_id, result, root=self.magazine.root)
        return result, dict(runner.rejected)

    def _materialise(
        self, edition_id: str, runner: CooperativeRunner
    ) -> tuple[ReadyItem, ...]:
        """Write every ready brief to disk, and set aside every void reply.

        A reply that cannot be applied is renamed rather than deleted.  It is
        somebody's work, it is often most of the answer the fresh brief wants,
        and a pipeline that silently destroyed it would be a pipeline nobody
        left a fleet running against.
        """

        editions_dir = self.magazine.editions_dir
        root = self.magazine.root
        ready: list[ReadyItem] = []
        for key in sorted(runner.pending, key=lambda name: _rank(runner.pending[name])):
            item = runner.pending[key]
            directory = item_dir(editions_dir, edition_id, key)
            directory.mkdir(parents=True, exist_ok=True)
            if key in runner.rejected:
                superseded = directory / REPLY_FILENAME
                if superseded.is_file():
                    superseded.replace(directory / "reply.superseded.md")
            brief = directory / BRIEF_FILENAME
            reply = directory / REPLY_FILENAME
            item = replace(
                item,
                brief_path=_relative(root, brief),
                reply_path=_relative(root, reply),
            )
            _write_text(brief, item.prompt)
            write_render_review(directory / ITEM_FILENAME, _descriptor(edition_id, item))
            ready.append(item)
        return tuple(ready)

    def _escalation_actions(
        self, edition_id: str, result: ProduceResult
    ) -> list[str]:
        """Tell a driver how an escalated piece is offered a fresh start.

        Under an autonomous backend a re-run asks the model again and gets a
        different answer.  A replay of stored replies is deterministic and would
        re-escalate for ever, so the way out has to be named: discard the piece's
        answers and the pipeline drafts it from round one again.
        """

        actions: list[str] = []
        for piece_id in result.escalated:
            directory = agent_dir(self.magazine.editions_dir, edition_id) / piece_id
            actions.append(
                f"{piece_id} escalated on stored answers, and a replay of the same "
                f"answers escalates again. Fix the manuscript by hand, or delete "
                f"{_relative(self.magazine.root, directory)} to redraft the piece "
                "from round one."
            )
        return actions


def _graph_actions(
    result: ProduceResult, ready: Sequence[ReadyItem]
) -> list[str]:
    """Say what the graph knows that the ready set cannot express.

    Two things, and both were invisible on the run this exists because of.  A
    node in :data:`~magazine.produce_graph.INCONSISTENT` is finished work the
    records do not carry, and no amount of re-running notices it, because the
    pipeline asks for answers it thinks it is missing and this one it thinks it
    has.  And an edition with no emittable briefs that is still short of
    complete is stalled: the loop has nothing left to hand a worker and is not
    done, which is the one combination a driver must never read as success.
    """

    graph = result.graph
    if graph is None or graph.complete:
        return []
    actions = [
        f"{node.id}: {node.detail}"
        for node in graph.nodes
        if node.state == INCONSISTENT
    ]
    if not ready and not result.escalated:
        blocking = ", ".join(
            node.id
            for node in graph.unreached
            if node.state not in {ESCALATED}
        )
        actions.append(
            "the production graph is incomplete and this run emitted no brief, "
            "so nothing a worker can answer will advance it. Unreached: "
            + (blocking or "none")
            + ". Resolve the nodes above by hand; the edition is not finished "
            "and must not be built."
        )
    return actions


def _unreached_actions(runner: CooperativeRunner) -> list[str]:
    """Name the finished work this replay walked past, and never delete it.

    An earlier round's answer being refused strands every answer after it: the
    pipeline replays from round one, stops where the refusal is, and the
    later rounds' replies are simply never asked for.  They are still on disk
    and they are still hours of somebody's work, so silence here reads as
    "the pipeline lost my drafts" -- which, from the driver's chair, is
    indistinguishable from the truth.

    This is the loud half of the bargain.  The quiet half is
    ``produce_prompts.work_identity``, which stops a reworded brief from
    voiding anything in the first place; when something genuinely does move,
    the count of what went unreached is the number an operator needs to decide
    whether to re-run or to recover by hand.
    """

    unreached = sorted(set(runner.replies) - runner.answered - set(runner.pending))
    if not unreached:
        return []
    return [
        f"{len(unreached)} stored repl(y/ies) were not reached this run and are "
        "still on disk: "
        + ", ".join(unreached)
        + ". They answer rounds the pipeline stopped short of, normally because "
        "an earlier round's answer was refused. Nothing was deleted; clearing "
        "the earlier refusal makes them reachable again."
    ]


def _rank(item: ReadyItem) -> tuple[str, int, int, str]:
    return (
        item.item.piece_id,
        item.item.round_number,
        _ROLE_RANK.get(item.item.role, 99),
        item.item.role,
    )


def _descriptor(edition_id: str, item: ReadyItem) -> dict[str, Any]:
    return {
        "schema_version": AGENT_SCHEMA_VERSION,
        "edition_id": edition_id,
        **item.to_dict(),
    }


def _write_ready(
    editions_dir: Path, edition_id: str, result: ProduceResult, *, root: Path
) -> Path:
    """One file that answers "where is this edition" without running anything.

    Deliberately carries no timestamp, and every path in it is project-relative.
    Re-emitting an unchanged ready set must leave the tree byte-identical -- so
    that a driver which crashed and restarted cannot tell, and neither can a
    diff, that it ran twice.

    ``state`` is read off the production graph and never off the size of the
    ready set.  It used to be the latter, and the two are not the same question:
    an edition whose editorial was unjudged and whose managing editor had never
    run reported ``awaiting_work`` for one outstanding writer brief, which is
    what "one small thing left" looks like.  ``complete`` here now means what it
    says -- every declared node accepting -- and an edition that has run out of
    emittable work without getting there is ``stalled``, which is a different
    word on purpose.
    """

    graph = result.graph
    if graph is not None and graph.complete:
        state = "complete"
    elif result.escalated:
        state = "escalated"
    elif result.ready:
        state = "awaiting_work"
    elif graph is None:
        state = "complete"
    else:
        # No brief to emit, no escalation, and the graph is still short of its
        # accepting states.  Nothing a worker can pick up will move it, so
        # naming it as ordinary progress would be the exact lie that shipped an
        # unjudged editorial.
        state = "stalled"
    payload_graph: dict[str, Any] = {}
    if graph is not None:
        payload_graph = {
            "complete": graph.complete,
            "unreached": [node.id for node in graph.unreached],
        }
    return write_render_review(
        ready_path(editions_dir, edition_id),
        {
            "schema_version": AGENT_SCHEMA_VERSION,
            "edition_id": edition_id,
            "backend": AGENT_BACKEND,
            "state": state,
            "graph": payload_graph,
            "ready": [item.to_dict() for item in result.ready],
            "pieces": [
                {**outcome.to_dict(), "record": _relative(root, Path(outcome.record))}
                for outcome in result.outcomes
            ],
            "recorded": {
                kind: _relative(root, Path(path))
                for kind, path in result.recorded.items()
            },
            "human_actions": list(result.human_actions),
        },
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = text if text.endswith("\n") else text + "\n"
    path.write_text(body, encoding="utf-8")


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
