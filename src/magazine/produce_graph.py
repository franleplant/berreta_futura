"""The produce pipeline's order, declared as data rather than as control flow.

``produce.py`` owns the *order* of generation and judgment, and until now it
owned it the way a program owns anything: in the shape of its statements.  The
writer ran, then the gates, then the judges, then -- three nested conditions
later -- the two whole-issue judgments.  Nothing outside that function could be
asked what the order was, which meant nothing outside that function could
notice when a step had not happened.

It did not happen.  Edition ``rerun-004-the-systems-around-the-model`` reached
seven settled articles; the managing editor and the reader personas never ran;
``editions/rerun-004-the-systems-around-the-model/production/issue/`` was never
created; and every surface the operator had -- the produce report, ``ready.yaml``
and the workflow checkpoint alike -- said something that was locally true and
collectively misleading.  The managing editor is the only judge that asks
whether the opening editorial argues from the whole issue rather than leaning on
one article, so the one question nobody asked was the one the shipped editorial
would have failed.

This module makes the order a value.  Every step is a :class:`NodeSpec` naming
its kind, its scope, what it consumes and what makes it *accepting*; the specs
are resolved against the files on disk into a :class:`ProductionGraph`; and an
edition is production-complete exactly when every resolved node is accepting.
Three consequences follow, and all three are the point:

**The order is inspectable.**  ``mag produce --graph`` prints it, node by node,
with each node's state and -- for anything unreached -- what is blocking it.
Neither a human nor a driving agent has to read this package to find out where
an edition stopped.

**Absence is a state.**  A step that has not run is a node in a non-accepting
state, which is a thing the completion predicate can see.  The failure above was
not that a condition was wrong; it was that "the whole-issue stage never ran"
had no representation anywhere, so no code could act on it and no report could
print it.

**Nodes are cheap to add.**  The two per-piece judges are about to be replaced by
several narrower single-concern lenses.  That change is one edit to
:data:`PIECE_JUDGE_LENSES` here: the graph grows the nodes, the completion
predicate requires them, the report prints them, and -- because
:mod:`magazine.produce_agent` derives its work contracts and its report order
from these same specs -- the cooperative backend learns their names without
being told twice.

**Two sources of truth, reconciled.**  A piece's production record and the
cooperative backend's reply queue are both on disk and can disagree, and once
did: the editorial's ``r1-evidence`` and ``r1-line`` replies both sat on disk
saying approved while the record carried ``judges: {}``.  A voided writer reply
had stopped the replay at round one, so the pipeline never asked for the judge
answers it already had, and nothing compared the two.  Resolution here reads the
record as authoritative and the queue as evidence *about* the record, so an
answered brief the record does not carry is not a silence -- it is
:data:`INCONSISTENT`, which is loud, terminal and non-accepting.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .edition_review import edition_review_path
from .errors import MagazineError, ValidationError
from .evidence_review import evidence_review_path
from .io import load_structured
from .learning_review import learning_review_path
from .line_review import EDITORIAL_ARTICLE_ID, line_review_path
from .production_record import (
    AGENT_DIRNAME,
    issue_record_path,
    load_piece_record,
    piece_record_path,
    production_dir,
    text_sha256,
)
from .staging_marker import declared_manuscript_paths, is_staging_marker


class ProduceGraphError(MagazineError):
    """The declared graph itself is wrong: a bad kind, a missing dependency, a cycle.

    Deliberately distinct from an *incomplete* graph, which is an ordinary state
    of an edition mid-production and is reported rather than raised.  This one
    means the declaration in this module cannot describe a runnable pipeline,
    and it is raised at import time so a malformed edit cannot reach an edition.
    """


# ---------------------------------------------------------------------------
# The vocabulary.

PROGRAMMATIC = "programmatic"
"""A step this package computes.  Arithmetic, records, files: no model call."""

AGENTIC = "agentic"
"""A step a model or a human answers.  Costs minutes and money; can be parked."""

NODE_KINDS = (PROGRAMMATIC, AGENTIC)

PIECE_SCOPE = "piece"
EDITION_SCOPE = "edition"
NODE_SCOPES = (PIECE_SCOPE, EDITION_SCOPE)

# The states a resolved node may sit in.  Only two of them are accepting, and
# the split is the whole of what "production-complete" means.
COMPLETE = "complete"
NOT_APPLICABLE = "not_applicable"
READY = "ready"
BLOCKED = "blocked"
ESCALATED = "escalated"
INCONSISTENT = "inconsistent"

NODE_STATES = (COMPLETE, NOT_APPLICABLE, READY, BLOCKED, ESCALATED, INCONSISTENT)

ACCEPTING_STATES = frozenset({COMPLETE, NOT_APPLICABLE})
"""The states that let an edition be built.

``escalated`` is terminal and is deliberately *not* here: the pipeline decided
it cannot fix the piece, which is an answer, but it is not the answer that lets
an issue ship.  A human resolves it; the graph does not.
"""

TERMINAL_STATES = frozenset({COMPLETE, NOT_APPLICABLE, ESCALATED, INCONSISTENT})

# What a work item's reply has to be.  Declared beside the node that asks for it
# so that adding a node cannot forget to say what answers it; ``produce_agent``
# reads its ``WORK_CONTRACTS`` off these rather than keeping a second list.
MANUSCRIPT = "manuscript"
VERDICT = "verdict"
TAKEAWAYS = "manager_takeaways"

ISSUE_PIECE_ID = "issue"
"""The scope name the whole-issue nodes are filed under.

The same spelling the production records and the work items already use, so
``issue/edition`` names one thing whether it is read as a node, a record path or
a brief directory.
"""


@dataclass(frozen=True)
class NodeSpec:
    """One step of the pipeline, declared.

    ``consumes`` names the steps that must be accepting before this one is
    reachable.  Within a piece it names sibling piece-scoped specs; an
    edition-scoped node may also name :data:`EVERY_PIECE_SETTLED`, which fans in
    over whatever pieces the edition actually declares -- the count is not
    knowable until an edition is loaded, and hardcoding it here would be a
    second place for the piece list to be wrong.

    ``accepting`` is prose, and it is load-bearing prose: it is what the report
    prints beside a node the operator has never heard of, and what a reviewer
    reads to decide whether the predicate below actually checks it.
    """

    id: str
    kind: str
    scope: str
    consumes: tuple[str, ...]
    accepting: str
    role: str = ""
    """The work-item role an agentic node dispatches, empty for a programmatic one."""
    returns: str = ""
    """What the role's reply must be, empty for a programmatic node."""


EVERY_PIECE_SETTLED = "piece:settled"
"""Fan-in dependency: every declared piece's ``settled`` node, whatever they are."""


PIECE_JUDGE_LENSES: tuple[str, ...] = ("evidence", "line")
"""The judges that read one piece, in the order their findings are reported.

**This tuple is the seam.**  The two-judge stage is being replaced by several
narrower single-concern lenses; that replacement is an edit to this tuple plus a
prompt per lens, and nothing in the graph, the completion predicate, the report
or the cooperative backend's contracts needs to be touched for the new set to be
declared, required and reported.  They run concurrently, so the order here
decides how a report reads and nothing else.
"""


def _judge_specs() -> tuple[NodeSpec, ...]:
    return tuple(
        NodeSpec(
            id=f"judge.{lens}",
            kind=AGENTIC,
            scope=PIECE_SCOPE,
            consumes=("gates",),
            accepting=(
                f"the piece's latest round carries an approved {lens} verdict"
            ),
            role=lens,
            returns=VERDICT,
        )
        for lens in PIECE_JUDGE_LENSES
    )


PIECE_NODE_SPECS: tuple[NodeSpec, ...] = (
    NodeSpec(
        id="write",
        kind=AGENTIC,
        scope=PIECE_SCOPE,
        consumes=(),
        accepting=(
            "a writer round is recorded and the manuscript on disk is prose "
            "rather than a staging marker"
        ),
        role="writer",
        returns=MANUSCRIPT,
    ),
    NodeSpec(
        id="gates",
        kind=PROGRAMMATIC,
        scope=PIECE_SCOPE,
        consumes=("write",),
        accepting="the latest round records no deterministic gate failure",
    ),
    *_judge_specs(),
    NodeSpec(
        id="settled",
        kind=PROGRAMMATIC,
        scope=PIECE_SCOPE,
        consumes=("gates", *(f"judge.{lens}" for lens in PIECE_JUDGE_LENSES)),
        accepting=(
            "the record says passed and still binds the manuscript's current bytes"
        ),
    ),
)


EDITION_NODE_SPECS: tuple[NodeSpec, ...] = (
    NodeSpec(
        id="manager-run-a",
        kind=AGENTIC,
        scope=EDITION_SCOPE,
        consumes=(EVERY_PIECE_SETTLED,),
        accepting="the learning record carries run A's manager takeaways",
        role="manager_run_a",
        returns=TAKEAWAYS,
    ),
    NodeSpec(
        id="learning",
        kind=AGENTIC,
        scope=EDITION_SCOPE,
        consumes=("manager-run-a",),
        accepting="the learning record carries an approved run B verdict",
        role="learning",
        returns=VERDICT,
    ),
    # The node the incident is about.  It is the only judge that reads the
    # editorial against the whole issue, so it is declared as its own required
    # node rather than as a tail of the learning call it happens to follow.
    NodeSpec(
        id="edition",
        kind=AGENTIC,
        scope=EDITION_SCOPE,
        consumes=("learning",),
        accepting="the managing editor's record carries an approved verdict",
        role="edition",
        returns=VERDICT,
    ),
    NodeSpec(
        id="bench",
        kind=PROGRAMMATIC,
        scope=EDITION_SCOPE,
        consumes=("edition", EVERY_PIECE_SETTLED),
        accepting=(
            "every judge's verdict is recorded on the review bench: the "
            "evidence, line, learning and edition review records all exist"
        ),
    ),
)


def _validate_specs() -> None:
    """Refuse a malformed declaration at import time.

    A graph that cannot be traversed is a programming error in this file, and
    the moment to say so is before an edition is ever resolved against it.  The
    checks are the three ways the table can be wrong: a value outside the
    vocabulary, a dependency naming nothing, and an order that is not one.
    """

    for specs, scope in (
        (PIECE_NODE_SPECS, PIECE_SCOPE),
        (EDITION_NODE_SPECS, EDITION_SCOPE),
    ):
        known: set[str] = set()
        for spec in specs:
            if spec.id in known:
                raise ProduceGraphError(
                    f"the production graph declares {spec.id!r} twice in the "
                    f"{scope} scope; node ids name a step and must be unique"
                )
            if spec.kind not in NODE_KINDS:
                raise ProduceGraphError(
                    f"node {spec.id!r} declares kind {spec.kind!r}; a node is "
                    + " or ".join(NODE_KINDS)
                )
            if spec.scope != scope:
                raise ProduceGraphError(
                    f"node {spec.id!r} is declared in the {scope} table but "
                    f"carries scope {spec.scope!r}"
                )
            if (spec.kind == AGENTIC) != bool(spec.role):
                raise ProduceGraphError(
                    f"node {spec.id!r} is {spec.kind} and "
                    + ("carries" if spec.role else "carries no")
                    + " a work-item role; exactly the agentic nodes dispatch one"
                )
            if bool(spec.role) != bool(spec.returns):
                raise ProduceGraphError(
                    f"node {spec.id!r} dispatches {spec.role!r} but does not say "
                    "what a reply must return; an unanswerable node can never "
                    "reach its accepting state"
                )
            for dependency in spec.consumes:
                if dependency == EVERY_PIECE_SETTLED and scope == EDITION_SCOPE:
                    continue
                if dependency not in known:
                    # Not merely "unknown": naming a later node is how a cycle
                    # is written, so the two failures share one message.
                    raise ProduceGraphError(
                        f"node {spec.id!r} consumes {dependency!r}, which is not "
                        f"a {scope}-scoped node declared before it; the table is "
                        "in traversal order and a backward reference would be a "
                        "cycle"
                    )
            known.add(spec.id)
    settled = {spec.id for spec in PIECE_NODE_SPECS}
    if "settled" not in settled:
        raise ProduceGraphError(
            "the piece scope must declare a `settled` node: it is what the "
            "whole-issue nodes fan in over"
        )


_validate_specs()


def work_contracts() -> dict[str, str]:
    """What each dispatchable role's reply must be, derived from the graph.

    The cooperative backend needs this map and used to keep its own copy, which
    is one more place a new judge lens could be forgotten.  Deriving it means a
    role that no node dispatches cannot be answered, and a node whose role has
    no contract cannot be declared (:func:`_validate_specs`).
    """

    return {
        spec.role: spec.returns
        for spec in (*PIECE_NODE_SPECS, *EDITION_NODE_SPECS)
        if spec.role
    }


def role_order() -> dict[str, int]:
    """Report order for work items, taken from the declared traversal order.

    The piece judges are composed on two threads, so their insertion order is
    thread scheduling.  This is not, and it moves when the graph is reordered,
    which is the point of deriving it.
    """

    return {
        spec.role: index
        for index, spec in enumerate(
            spec
            for spec in (*PIECE_NODE_SPECS, *EDITION_NODE_SPECS)
            if spec.role
        )
    }


# ---------------------------------------------------------------------------
# One edition, resolved.


@dataclass(frozen=True)
class GraphNode:
    """One declared step, resolved against one edition's files."""

    id: str
    spec: NodeSpec
    subject: str
    """The piece this node is about, or ``issue`` for a whole-issue node."""
    state: str
    detail: str = ""
    blocked_by: tuple[str, ...] = ()

    @property
    def accepting(self) -> bool:
        return self.state in ACCEPTING_STATES

    @property
    def kind(self) -> str:
        return self.spec.kind

    @property
    def scope(self) -> str:
        return self.spec.scope

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.spec.kind,
            "scope": self.spec.scope,
            "subject": self.subject,
            "state": self.state,
            "accepting": self.accepting,
            "consumes": list(self.spec.consumes),
            "accepting_condition": self.spec.accepting,
            "detail": self.detail,
            "blocked_by": list(self.blocked_by),
        }


@dataclass(frozen=True)
class ProductionGraph:
    """Every declared node of one edition, in traversal order, with its state."""

    edition_id: str
    nodes: tuple[GraphNode, ...]
    legacy: bool = False
    """True when the edition predates ``mag produce`` and has no records at all.

    Such an edition is reported complete, exactly as the workflow report has
    always reported it: the checkpoint asks whether the prose is there and
    settled, not whether this particular machine wrote it.  A *staged* edition
    is not this case -- its manuscripts are staging markers, which ``validate``
    refuses through :mod:`magazine.staging_marker` long before here.
    """

    problems: tuple[str, ...] = ()
    """Ways this edition cannot be traversed at all, as opposed to not yet having been."""

    @property
    def complete(self) -> bool:
        """Whether every declared node has reached an accepting terminal state."""

        return not self.problems and all(node.accepting for node in self.nodes)

    @property
    def unreached(self) -> tuple[GraphNode, ...]:
        return tuple(node for node in self.nodes if not node.accepting)

    @property
    def reached(self) -> tuple[GraphNode, ...]:
        return tuple(node for node in self.nodes if node.accepting)

    @property
    def inconsistent(self) -> tuple[GraphNode, ...]:
        return tuple(node for node in self.nodes if node.state == INCONSISTENT)

    def node(self, node_id: str) -> GraphNode | None:
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def summary(self) -> str:
        """One line an operator can read without scrolling."""

        if self.problems:
            return f"{self.edition_id}: production graph is broken"
        if self.legacy:
            return (
                f"{self.edition_id}: no production records; this edition predates "
                "`mag produce` and its graph does not apply"
            )
        total = len(self.nodes)
        done = len(self.reached)
        if self.complete:
            return (
                f"{self.edition_id}: production graph COMPLETE, "
                f"{done}/{total} node(s) accepting"
            )
        return (
            f"{self.edition_id}: production graph INCOMPLETE, "
            f"{done}/{total} node(s) accepting, {total - done} unreached"
        )

    def render(self) -> list[str]:
        """The whole traversal, node by node, for a human or a driving agent."""

        lines = [self.summary()]
        for problem in self.problems:
            lines.append(f"  broken: {problem}")
        for node in self.nodes:
            mark = "ok " if node.accepting else "-> "
            line = f"  {mark}[{node.state}] {node.id} ({node.kind})"
            if node.detail:
                line += f" -- {node.detail}"
            lines.append(line)
            if node.blocked_by:
                lines.append(
                    "        blocked by " + ", ".join(node.blocked_by)
                )
        if not self.complete and not self.problems and not self.legacy:
            lines.append(
                f"  unreached: " + ", ".join(node.id for node in self.unreached)
            )
        return lines

    def to_dict(self) -> dict[str, Any]:
        return {
            "edition_id": self.edition_id,
            "complete": self.complete,
            "legacy": self.legacy,
            "problems": list(self.problems),
            "nodes": [node.to_dict() for node in self.nodes],
            "unreached": [node.id for node in self.unreached],
        }


# ---------------------------------------------------------------------------
# Resolution.


def resolve_production_graph(
    root: Path, editions_dir: Path, edition_id: str
) -> ProductionGraph:
    """Read one edition's files and say where its traversal actually stands.

    Reads only: no model is called, no manuscript is written, no compiler is
    constructed.  That is what lets ``mag produce --graph``, ``mag build`` and
    the workflow report all ask the same question of the same files and get the
    same answer, without any of them being able to move the edition by asking.
    """

    edition_dir = editions_dir / edition_id
    manifest = _manifest(edition_dir)
    problems: list[str] = []
    if manifest is None:
        # The manifest loader's complaint, not this module's -- but a graph
        # cannot be resolved without one, and saying so beats reporting an
        # edition with no nodes as vacuously complete.
        return ProductionGraph(
            edition_id=edition_id,
            nodes=(),
            problems=(
                f"editions/{edition_id}/edition.yaml is missing or unreadable, so "
                "the pieces this edition declares are unknown and no production "
                "graph can be resolved",
            ),
        )
    pieces = declared_manuscript_paths(root, edition_dir, manifest)
    records_present = production_dir(editions_dir, edition_id).is_dir()
    if not records_present:
        return ProductionGraph(edition_id=edition_id, nodes=(), legacy=True)
    if not pieces:
        problems.append(
            f"{edition_id} declares no articles and no editorial, so there is "
            "nothing for the whole-issue judgments to read; a production graph "
            "with no pieces can never be completed"
        )

    answered = _answered_briefs(editions_dir, edition_id)
    nodes: list[GraphNode] = []
    states: dict[str, str] = {}

    for piece_id, manuscript in pieces.items():
        record = load_piece_record(editions_dir, edition_id, piece_id) or {}
        context = _PieceContext(
            piece_id=piece_id,
            manuscript=manuscript,
            record=record,
            answered=answered,
        )
        for spec in PIECE_NODE_SPECS:
            node_id = f"{piece_id}/{spec.id}"
            blocked_by = tuple(
                f"{piece_id}/{dependency}"
                for dependency in spec.consumes
                if states.get(f"{piece_id}/{dependency}") not in ACCEPTING_STATES
            )
            state, detail = _piece_node_state(spec, context)
            if state not in TERMINAL_STATES and blocked_by:
                state = BLOCKED
            nodes.append(
                GraphNode(
                    id=node_id,
                    spec=spec,
                    subject=piece_id,
                    state=state,
                    detail=detail,
                    blocked_by=blocked_by,
                )
            )
            states[node_id] = state

    settled_ids = tuple(f"{piece_id}/settled" for piece_id in pieces)
    issue = _IssueContext(
        editions_dir=editions_dir,
        edition_id=edition_id,
    )
    for spec in EDITION_NODE_SPECS:
        node_id = f"{ISSUE_PIECE_ID}/{spec.id}"
        blocked_by: list[str] = []
        for dependency in spec.consumes:
            if dependency == EVERY_PIECE_SETTLED:
                blocked_by.extend(
                    item
                    for item in settled_ids
                    if states.get(item) not in ACCEPTING_STATES
                )
                continue
            sibling = f"{ISSUE_PIECE_ID}/{dependency}"
            if states.get(sibling) not in ACCEPTING_STATES:
                blocked_by.append(sibling)
        state, detail = _edition_node_state(spec, issue)
        if state not in TERMINAL_STATES and blocked_by:
            state = BLOCKED
        nodes.append(
            GraphNode(
                id=node_id,
                spec=spec,
                subject=ISSUE_PIECE_ID,
                state=state,
                detail=detail,
                blocked_by=tuple(dict.fromkeys(blocked_by)),
            )
        )
        states[node_id] = state

    return ProductionGraph(
        edition_id=edition_id, nodes=tuple(nodes), problems=tuple(problems)
    )


@dataclass(frozen=True)
class _PieceContext:
    piece_id: str
    manuscript: Path
    record: Mapping[str, Any]
    answered: Mapping[str, int]
    """Work-item keys with a reply on disk, mapped to the round they answer."""

    @property
    def rounds(self) -> Sequence[Mapping[str, Any]]:
        rounds = self.record.get("rounds") or ()
        if isinstance(rounds, Sequence) and not isinstance(rounds, (str, bytes)):
            return [entry for entry in rounds if isinstance(entry, Mapping)]
        return []

    @property
    def last_round(self) -> Mapping[str, Any] | None:
        rounds = self.rounds
        return rounds[-1] if rounds else None

    @property
    def round_number(self) -> int:
        last = self.last_round
        if last is None:
            return 0
        number = last.get("round")
        return number if isinstance(number, int) else len(self.rounds)


def _piece_node_state(spec: NodeSpec, piece: _PieceContext) -> tuple[str, str]:
    if spec.id == "write":
        return _write_state(piece)
    if spec.id == "gates":
        return _gates_state(piece)
    if spec.id.startswith("judge."):
        return _judge_state(spec, piece)
    if spec.id == "settled":
        return _settled_state(piece)
    # Unreachable while _validate_specs passes: every declared piece node is
    # handled above.  Stated rather than assumed, because a node nobody can
    # evaluate would otherwise be silently ready for ever.
    raise ProduceGraphError(
        f"the production graph declares the piece node {spec.id!r}, and nothing "
        "knows how to decide whether it has been reached; its accepting "
        "condition can never be met"
    )


def _write_state(piece: _PieceContext) -> tuple[str, str]:
    if not piece.manuscript.is_file():
        return READY, "no manuscript on disk"
    if is_staging_marker(piece.manuscript):
        return READY, "the manuscript is still a staging marker"
    if not piece.rounds:
        # Prose with no record behind it.  Legitimate for a hand-authored
        # edition, which this module never reaches (see ``legacy``), and
        # otherwise a piece whose drafting history was lost.
        return (
            READY,
            "prose is on disk but no writer round is recorded for it",
        )
    return COMPLETE, f"round {piece.round_number} drafted"


def _gates_state(piece: _PieceContext) -> tuple[str, str]:
    last = piece.last_round
    if last is None:
        return READY, "no round to check"
    failures = last.get("gate_failures") or ()
    if not failures:
        return COMPLETE, f"round {piece.round_number} cleared every gate"
    headline = str(next(iter(failures), "")).splitlines()
    return (
        READY,
        f"round {piece.round_number} failed {len(failures)} gate(s): "
        + (headline[0] if headline else ""),
    )


def _judge_state(spec: NodeSpec, piece: _PieceContext) -> tuple[str, str]:
    lens = spec.role
    last = piece.last_round
    if last is None:
        return READY, "no round to judge"
    judges = last.get("judges")
    verdict = judges.get(lens) if isinstance(judges, Mapping) else None
    if isinstance(verdict, Mapping):
        result = str(verdict.get("result") or "").strip()
        if result == "approved":
            return COMPLETE, f"approved in round {piece.round_number}"
        return (
            READY,
            f"round {piece.round_number} returned {result or 'no result'}",
        )
    # No verdict in the record.  Before calling that "not judged yet", ask the
    # reply queue, because the two can disagree and the disagreement is the
    # defect: the editorial's judges both answered `approved` and the record
    # carried `judges: {}` while the edition was built around it.
    key = f"{piece.piece_id}/r{piece.round_number}-{lens.replace('_', '-')}"
    if piece.round_number and key in piece.answered:
        return (
            INCONSISTENT,
            f"{key} has a reply on disk that the record does not carry; the "
            "pipeline walked past finished judgment and the record is what "
            "every later step reads",
        )
    return READY, "not judged yet"


def _settled_state(piece: _PieceContext) -> tuple[str, str]:
    status = str(piece.record.get("status") or "")
    if status == "escalated":
        return (
            ESCALATED,
            "the pipeline exhausted its rounds and asked for a human; an "
            "escalation is terminal but never accepting",
        )
    if status != "passed":
        if not piece.record:
            return READY, "no production record"
        return READY, f"the record says {status or 'nothing'}, not passed"
    bound = piece.record.get("manuscript_sha256")
    current = _file_sha256(piece.manuscript)
    if current is None:
        return READY, "the record says passed but the manuscript is gone"
    if bound != current:
        return (
            INCONSISTENT,
            "the record says passed but binds different bytes than the "
            "manuscript now on disk; what was judged is not what would be built",
        )
    return COMPLETE, "passed and bound to the manuscript on disk"


@dataclass(frozen=True)
class _IssueContext:
    editions_dir: Path
    edition_id: str
    _cache: dict[str, Any] = field(default_factory=dict)

    def record(self, kind: str) -> Mapping[str, Any] | None:
        if kind not in self._cache:
            self._cache[kind] = _read_mapping(
                issue_record_path(self.editions_dir, self.edition_id, kind)
            )
        return self._cache[kind]


def _edition_node_state(spec: NodeSpec, issue: _IssueContext) -> tuple[str, str]:
    if spec.id == "manager-run-a":
        record = issue.record("learning")
        block = (record or {}).get("manager_run_a")
        if isinstance(block, Mapping) and block.get("manager_takeaways") is not None:
            return COMPLETE, "run A's takeaways are recorded"
        return READY, "the managing editor has not written run A's takeaways"
    if spec.id == "learning":
        return _verdict_node(
            issue.record("learning"),
            ("run_b",),
            "the reader personas have not read the issue",
        )
    if spec.id == "edition":
        return _verdict_node(
            issue.record("edition"),
            ("run",),
            # Named at length because this is the node the incident is about.
            "the managing editor has not read the issue; it is the only judge "
            "that asks whether the opening editorial argues from the whole "
            "issue rather than leaning on one article",
        )
    if spec.id == "bench":
        return _bench_state(issue)
    raise ProduceGraphError(
        f"the production graph declares the edition node {spec.id!r}, and "
        "nothing knows how to decide whether it has been reached; its accepting "
        "condition can never be met"
    )


def _verdict_node(
    record: Mapping[str, Any] | None, path: Sequence[str], absent: str
) -> tuple[str, str]:
    if record is None:
        return READY, absent
    node: Any = record
    for key in path:
        node = node.get(key) if isinstance(node, Mapping) else None
    if not isinstance(node, Mapping):
        return READY, absent
    result = str(node.get("result") or "").strip()
    if result == "approved":
        return COMPLETE, "approved"
    return (
        READY,
        f"returned {result or 'no result'}; a whole-issue finding needs a human "
        "editor, not another drafting round",
    )


_BENCH_RECORDS = (
    ("evidence", evidence_review_path),
    ("line", line_review_path),
    ("learning", learning_review_path),
    ("edition", edition_review_path),
)


def _bench_state(issue: _IssueContext) -> tuple[str, str]:
    missing = [
        kind
        for kind, path_of in _BENCH_RECORDS
        if not path_of(issue.editions_dir, issue.edition_id).is_file()
    ]
    if not missing:
        return COMPLETE, "every judge's verdict is recorded on the bench"
    return (
        READY,
        f"{len(missing)} review record(s) not written: " + ", ".join(missing),
    )


# ---------------------------------------------------------------------------
# The predicate, and the refusal.


def production_graph_complete(
    root: Path, editions_dir: Path, edition_id: str
) -> bool:
    """Whether every declared node of this edition is in an accepting state."""

    return resolve_production_graph(root, editions_dir, edition_id).complete


def require_complete_production_graph(
    root: Path, editions_dir: Path, edition_id: str
) -> None:
    """Refuse an edition whose production graph has unreached nodes.

    The message follows :func:`~magazine.staging_marker.require_written_manuscripts`
    deliberately, because it is the same kind of refusal: every unfinished thing
    named in one error, and one command that makes progress on all of them.
    Finding them one build at a time is how the first one got through.
    """

    graph = resolve_production_graph(root, editions_dir, edition_id)
    if graph.complete:
        return
    if graph.problems:
        raise ValidationError(
            [
                f"{edition_id}: the production graph cannot be resolved, so "
                "whether this edition was produced is unknowable.",
                *graph.problems,
            ]
        )
    named = [
        f"{node.id} ({node.kind}, {node.state}): {node.detail or node.spec.accepting}"
        + (
            "; blocked by " + ", ".join(node.blocked_by)
            if node.blocked_by
            else ""
        )
        for node in graph.unreached
    ]
    remedy = [
        f"Advance the graph with `uv run --locked mag produce {edition_id}` until "
        "it reports the graph complete; "
        f"`uv run --locked mag produce {edition_id} --graph` shows every node and "
        "what is blocking it.",
    ]
    if graph.inconsistent:
        remedy.append(
            "A node reported `inconsistent` is finished work the records do not "
            "carry, and no further produce run will notice it on its own: read "
            "the reply the message names and either record it or delete it."
        )
    escalated = [node for node in graph.unreached if node.state == ESCALATED]
    if escalated:
        remedy.append(
            "An escalated piece is terminal and never accepting; repair it by "
            "hand, then re-run produce so the repair is judged and recorded."
        )
    raise ValidationError(
        [
            f"{edition_id}: {len(graph.unreached)} production graph node(s) have "
            "not reached an accepting state and the edition cannot be built, "
            "packaged or released.",
            *named,
            *remedy,
        ]
    )


# ---------------------------------------------------------------------------
# Reading the two places the truth lives.


def _answered_briefs(editions_dir: Path, edition_id: str) -> dict[str, int]:
    """Every cooperative work item with a reply on disk, and the round it answers.

    Evidence *about* the records rather than a second copy of them.  A reply
    here that the record does not carry is the disagreement
    :data:`INCONSISTENT` exists to name.
    """

    root = production_dir(editions_dir, edition_id) / AGENT_DIRNAME
    if not root.is_dir():
        return {}
    answered: dict[str, int] = {}
    for reply in sorted(root.glob("*/*/reply.md")):
        leaf = reply.parent.name
        key = f"{reply.parent.parent.name}/{leaf}"
        round_number = 0
        if leaf.startswith("r") and "-" in leaf:
            head = leaf.split("-", 1)[0][1:]
            if head.isdigit():
                round_number = int(head)
        answered[key] = round_number
    return answered


def _manifest(edition_dir: Path) -> Mapping[str, Any] | None:
    return _read_mapping(edition_dir / "edition.yaml")


def _read_mapping(path: Path) -> Mapping[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = load_structured(path)
    except Exception:
        return None
    return data if isinstance(data, Mapping) else None


def _file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return text_sha256(path.read_text(encoding="utf-8"))


def piece_record_paths(
    editions_dir: Path, edition_id: str, piece_ids: Sequence[str]
) -> dict[str, Path]:
    """Where each named piece's record lives; a convenience for reporters."""

    return {
        piece_id: piece_record_path(editions_dir, edition_id, piece_id)
        for piece_id in piece_ids
    }
