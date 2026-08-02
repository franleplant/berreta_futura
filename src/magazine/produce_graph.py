"""The produce pipeline's order, declared as data rather than as control flow.

``produce.py`` owns the *order* of generation and judgment, and until now it
owned it the way a program owns anything: in the shape of its statements.  The
writer ran, then the gates, then the judges, then -- three nested conditions
later -- the whole-issue judgments.  Nothing outside that function could be
asked what the order was, which meant nothing outside that function could
notice when a step had not happened.

It did not happen.  Edition ``rerun-004-the-systems-around-the-model`` reached
seven settled articles; the whole-issue stage never ran;
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

**Nodes are cheap to add, and that claim has now been cashed.**  The two broad
per-piece judges were replaced by six narrow single-concern lenses, and it was
one edit to :data:`PIECE_JUDGE_LENSES` here: the graph grew the nodes, the
completion predicate required them, the report printed them, the cooperative
backend learned their names and their report order from the same specs
(:mod:`magazine.produce_agent`), :mod:`magazine.review_bench` derived which
review records the bench must carry, and the CLI derived its ``--kind`` values.

Two places did *not* come along for free and both were fixed rather than worked
around, because a seam that leaks is worse than no seam.  ``_BENCH_RECORDS`` was
a hardcoded tuple of four ``(kind, path_function)`` pairs, and it still named
``line`` and ``learning`` -- it is now :func:`bench_record_path`, derived.  The
``bench`` node's accepting sentence spelled the four kinds out in prose, and now
joins :data:`BENCH_REVIEW_KINDS`.  Both were second copies of this tuple wearing
different clothes.

**Two sources of truth, reconciled.**  A piece's production record and the
cooperative backend's reply queue are both on disk and can disagree, and once
did: two of the editorial's judge replies both sat on disk saying approved while
the record carried ``judges: {}``.  A voided writer reply
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
from .io import load_structured
from .piece_review import (
    ARTICLES,
    EDITORIAL_ARTICLE_ID,
    EXPLAINERS,
    PIECES,
    review_path,
)
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
    lens: "JudgeLens | None" = None
    """The lens this node runs, for a judge node; ``None`` for everything else.

    Carried on the spec rather than looked up by name so that resolution can ask
    a node which pieces it applies to without a second table to consult.
    """


EVERY_PIECE_SETTLED = "piece:settled"
"""Fan-in dependency: every declared piece's ``settled`` node, whatever they are."""


@dataclass(frozen=True)
class JudgeLens:
    """One narrow single-concern reader, and everything derived from it.

    A lens is not just a name, and pretending it was is what made the previous
    version of this tuple insufficient.  Four facts about a lens have downstream
    consequences and every one of them used to be restated somewhere else:

    ``stage``
        Which of ``prompts/README.md``'s four stages it runs in.  The staging
        exists to stop paying for judgment that is about to be invalidated:
        craft notes on a paragraph ``worth`` is about to have cut are wasted
        calls.  :func:`stage_order` turns this into the run plan.

    ``covers``
        Which pieces the lens is **dispatched for**, in
        :mod:`magazine.piece_review`'s vocabulary.  ``worth`` does not run on
        the editorial and ``teaching`` runs only on the explainer, so a node for
        a piece outside a lens's coverage resolves ``not_applicable`` rather
        than sitting unreached for ever.

        This is dispatch coverage, and it is deliberately allowed to be *wider*
        than what the lens's record binds.  Exactly one lens uses that latitude
        and it is worth naming: ``evidence`` is dispatched for every piece
        including the editorial -- ``prompts/evidence-review.md`` says the
        editorial's sources are the edition's own article manuscripts -- but
        ``EVIDENCE_REVIEW`` binds articles only, because the editorial declares
        no ``source_ids`` and there is no extraction hash to pin it by.  Its
        findings still travel, record-level, so the audit is not lost; only the
        hash binding is narrower.  :mod:`magazine.review_bench` checks the
        containment at import so the two tables can differ but never diverge
        by accident.

    ``gates_release``
        Whether ``Magazine.release`` actually refuses on this lens today.  Only
        ``evidence`` does.  The other six are recorded, reported and checkpointed
        but not enforced, because their severities are still being calibrated
        and gating a release on a judgment the bench does not yet trust would
        block work over a measurement problem.  Declared here rather than as a
        literal in the workflow report so that flipping one on is an edit to
        this table and to nothing else.

    ``reads_source``
        Whether the lens may see an extraction *at all*.  Nothing branches on
        this to decide what to send -- the brief types in
        :mod:`magazine.produce_prompts` make a source structurally unreachable
        for a blind lens -- but the graph states it so that the declaration and
        the types can be checked against each other rather than merely
        believed.

    ``blocking_halts_piece``
        Whether a ``blocking`` finding from this lens stops the piece for the
        rest of the round.  True only for ``worth``: a piece that should not
        exist at this length makes every downstream finding worthless.  A
        mechanics blocking finding is local and does not move what the other
        lenses read, so stage 2 still runs.
    """

    kind: str
    stage: int
    covers: str
    reads_source: bool
    blocking_halts_piece: bool = False
    gates_release: bool = False

    @property
    def is_source_blind(self) -> bool:
        return not self.reads_source


PIECE_JUDGE_LENSES: tuple[JudgeLens, ...] = (
    JudgeLens("worth", stage=1, covers=ARTICLES, reads_source=True,
              blocking_halts_piece=True),
    JudgeLens("evidence", stage=2, covers=PIECES, reads_source=True,
              gates_release=True),
    JudgeLens("shape", stage=2, covers=PIECES, reads_source=False),
    JudgeLens("teaching", stage=3, covers=EXPLAINERS, reads_source=True),
    JudgeLens("craft", stage=3, covers=PIECES, reads_source=False),
    JudgeLens("mechanics", stage=1, covers=PIECES, reads_source=False),
)
"""The lenses that read one piece, in **repair order**.

**This tuple is the seam.**  It went from two broad judges to seven narrow ones
without any other table being edited: the graph grows the nodes, the completion
predicate requires them, the report prints them, the cooperative backend derives
its work contracts and its report order from them, the bench derives which review
records must exist, and the CLI derives its ``--kind`` values.  Adding an eighth
lens is a row here plus a prompt file.

The order is the order the *work should be done in*, which
``prompts/README.md`` sets out and which is deliberately neither severity order
nor stage order:

    worth -> evidence -> shape -> teaching -> craft -> mechanics

Fixing a worth or shape finding deletes and moves the text that craft and
mechanics findings point at, so any other order in a revision brief wastes the
writer's work.  ``stage`` is a separate field precisely because the cheapest
*running* order is not the repair order: mechanics is the cheapest call on the
bench and its findings survive any later change, so it runs in stage 1 and is
reported last.  Reading this tuple top to bottom gives a writer his worklist;
reading it by ``stage`` gives the pipeline its schedule.  Conflating the two is
what a single ordered list of names could not express.
"""

PIECE_JUDGE_KINDS: tuple[str, ...] = tuple(
    lens.kind for lens in PIECE_JUDGE_LENSES
)
"""Just the names, in repair order, for the many callers that want only those."""

PIECE_JUDGE_LENSES_BY_KIND: Mapping[str, JudgeLens] = {
    lens.kind: lens for lens in PIECE_JUDGE_LENSES
}

EDITION_JUDGE_KIND = "edition"
"""The one whole-issue lens.  Stage 4, and the only lens that sees the pieces together."""

BENCH_REVIEW_KINDS: tuple[str, ...] = (*PIECE_JUDGE_KINDS, EDITION_JUDGE_KIND)
"""Every kind that must have a record on the bench before an edition can ship."""


def stage_order() -> tuple[tuple[int, tuple[JudgeLens, ...]], ...]:
    """The lenses grouped by stage, cheapest-and-blocking-first.

    Derived rather than declared, so a lens whose ``stage`` is edited moves in
    the run plan and nowhere else has to be told.  Within a stage the lenses are
    independent and run concurrently; the order inside a group is repair order,
    which decides only how a report reads.
    """

    stages = sorted({lens.stage for lens in PIECE_JUDGE_LENSES})
    return tuple(
        (stage, tuple(lens for lens in PIECE_JUDGE_LENSES if lens.stage == stage))
        for stage in stages
    )


def lens_applies(lens: JudgeLens, *, piece_id: str, content_mode: str) -> bool:
    """Whether this lens is asked about this piece at all.

    The three coverages are ``prompts/README.md``'s, and each exclusion has a
    reason that is not tidiness.  ``worth`` skips the editorial because the
    editorial has no source of its own, so its worth question belongs to
    ``edition``.  ``teaching`` runs only on the ``in_a_nutshell`` explainer
    because a closed-book comprehension test of a feature article measures
    nothing.  Everything else reads every piece.
    """

    from .teaching_review import EXPLAINER_CONTENT_MODE

    if lens.covers == PIECES:
        return True
    if lens.covers == ARTICLES:
        return piece_id != EDITORIAL_ARTICLE_ID
    return content_mode == EXPLAINER_CONTENT_MODE


def _judge_specs() -> tuple[NodeSpec, ...]:
    return tuple(
        NodeSpec(
            id=f"judge.{lens.kind}",
            kind=AGENTIC,
            scope=PIECE_SCOPE,
            consumes=("gates",),
            accepting=(
                f"the piece's latest round carries an approved {lens.kind} "
                f"verdict, or the {lens.kind} lens does not read this piece"
            ),
            role=lens.kind,
            returns=VERDICT,
            lens=lens,
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
        consumes=("gates", *(f"judge.{kind}" for kind in PIECE_JUDGE_KINDS)),
        accepting=(
            "the record says passed and still binds the manuscript's current bytes"
        ),
    ),
)


EDITION_NODE_SPECS: tuple[NodeSpec, ...] = (
    # Stage 4, and the node the edition-004 incident is about.  It is the only
    # lens that reads the editorial against the whole issue, so it is declared
    # as its own required node rather than as a tail of something else.  The
    # two reader-persona nodes that used to precede it -- ``manager-run-a`` and
    # ``learning`` -- are gone: ``prompts/README.md`` retired Marcus and Priya
    # as lenses that bought one lens's worth of information for two extra calls
    # each, and Nadia survives per piece as ``teaching``.
    NodeSpec(
        id="edition",
        kind=AGENTIC,
        scope=EDITION_SCOPE,
        consumes=(EVERY_PIECE_SETTLED,),
        accepting="the managing editor's record carries an approved verdict",
        role=EDITION_JUDGE_KIND,
        returns=VERDICT,
    ),
    NodeSpec(
        id="bench",
        kind=PROGRAMMATIC,
        scope=EDITION_SCOPE,
        consumes=("edition", EVERY_PIECE_SETTLED),
        accepting=(
            "every lens's verdict is recorded on the review bench: the "
            + ", ".join(BENCH_REVIEW_KINDS)
            + " review records all exist"
        ),
    ),
)


def validate_node_specs(
    piece_specs: Sequence[NodeSpec], edition_specs: Sequence[NodeSpec]
) -> None:
    """Refuse a malformed declaration.

    A graph that cannot be traversed is a programming error in the table, and
    the moment to say so is before an edition is ever resolved against it --
    which is why the module calls this on itself at import.  The checks are the
    ways the table can be wrong: a value outside the vocabulary, a node that
    dispatches work nothing can answer, a dependency naming nothing, and an
    order that is not one.

    Takes the tables as arguments rather than reading the module's, so that the
    suite can prove each refusal against a deliberately broken table instead of
    trusting that this function would have caught it.
    """

    for specs, scope in (
        (piece_specs, PIECE_SCOPE),
        (edition_specs, EDITION_SCOPE),
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
    if "settled" not in {spec.id for spec in piece_specs}:
        raise ProduceGraphError(
            "the piece scope must declare a `settled` node: it is what the "
            "whole-issue nodes fan in over"
        )


validate_node_specs(PIECE_NODE_SPECS, EDITION_NODE_SPECS)


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

    deferred: bool = False
    """True when a better-placed check owns this edition's failure.

    An edition with no readable ``edition.yaml`` has no piece list, so no graph
    can be resolved -- but the manifest loader is about to say so far more
    usefully than this module could, and
    :func:`~magazine.staging_marker.require_written_manuscripts` already sets
    the precedent for not pre-empting it: burying a specific error under a
    general one costs an operator the diagnosis.  So the report still explains
    why it cannot answer, and the refusal stands aside.
    """

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

        if self.deferred:
            return f"{self.edition_id}: production graph cannot be resolved yet"
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
        return ProductionGraph(
            edition_id=edition_id,
            nodes=(),
            deferred=True,
            problems=(
                f"editions/{edition_id}/edition.yaml is missing or unreadable, so "
                "the pieces this edition declares are unknown and no production "
                "graph can be resolved; whoever loads the edition will say why",
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

    content_modes = _declared_content_modes(manifest)
    for piece_id, manuscript in pieces.items():
        record = load_piece_record(editions_dir, edition_id, piece_id) or {}
        context = _PieceContext(
            piece_id=piece_id,
            manuscript=manuscript,
            record=record,
            answered=answered,
            content_mode=content_modes.get(piece_id, ""),
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
        owed_bench_kinds=owed_bench_kinds(content_modes),
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


def _declared_content_modes(manifest: Mapping[str, Any]) -> dict[str, str]:
    """Each piece's declared ``content_mode``, read raw from the manifest.

    Raw for the same reason :func:`declared_manuscript_paths` is: a manifest
    that will not load for an unrelated reason must still resolve a graph, and
    which lenses apply to a piece is exactly the sort of question an operator
    asks *because* something is wrong.  The editorial has no article row, and
    its mode is the one the pipeline gives it.
    """

    modes: dict[str, str] = {}
    rows = manifest.get("articles")
    for index, row in enumerate(rows if isinstance(rows, list) else (), start=1):
        if not isinstance(row, Mapping):
            continue
        piece_id = str(row.get("id") or "").strip() or f"article-{index}"
        modes[piece_id] = str(row.get("content_mode") or "").strip()
    if manifest.get("editorial"):
        modes[EDITORIAL_ARTICLE_ID] = "original_editorial"
    return modes


@dataclass(frozen=True)
class _PieceContext:
    piece_id: str
    manuscript: Path
    record: Mapping[str, Any]
    answered: Mapping[str, int]
    """Work-item keys with a reply on disk, mapped to the round they answer."""

    content_mode: str = ""
    """What the manifest declares this piece is, for deciding which lenses apply."""

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
    # A lens that does not read this piece is *accepting*, not unreached.  The
    # distinction is the whole reason ``not_applicable`` is in the vocabulary:
    # ``worth`` has nothing to say about the editorial and ``teaching`` has
    # nothing to say about a feature, and a node that could never be reached
    # would make every such edition permanently incomplete.
    if spec.lens is not None and not lens_applies(
        spec.lens, piece_id=piece.piece_id, content_mode=piece.content_mode
    ):
        return (
            NOT_APPLICABLE,
            f"the {lens} lens does not read this piece",
        )
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
    owed_bench_kinds: tuple[str, ...] = BENCH_REVIEW_KINDS
    """The bench records this particular edition actually owes.

    Not :data:`BENCH_REVIEW_KINDS` unconditionally, which is what it was and
    which was wrong in one case that matters.  ``teaching`` reads the
    ``in_a_nutshell`` explainer; an edition that declares none is an ordinary
    edition, ``_record_bench`` correctly writes no teaching record for it, and
    :func:`_judge_state` correctly resolves every ``judge.teaching`` node
    ``not_applicable``.  ``bench`` was the one surface that disagreed, so such
    an edition sat permanently one node short: ``issue/bench`` stuck at ``ready``
    reporting "1 review record(s) not written: teaching", ``mag produce``
    exiting 1 for ever, ``ready.yaml`` calling a fully settled edition
    ``stalled``, and ``mag build`` refusing it -- all demanding a record the
    recorder would refuse to write, because there is no explainer to bind.

    That is the same failure the whole ``not_applicable`` state exists to
    prevent, arriving through the one node that was not asking the question per
    piece.  Four surfaces now agree instead of three.
    """

    _cache: dict[str, Any] = field(default_factory=dict)

    def record(self, kind: str) -> Mapping[str, Any] | None:
        if kind not in self._cache:
            self._cache[kind] = _read_mapping(
                issue_record_path(self.editions_dir, self.edition_id, kind)
            )
        return self._cache[kind]


def _edition_node_state(spec: NodeSpec, issue: _IssueContext) -> tuple[str, str]:
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


def bench_record_path(editions_dir: Path, edition_id: str, kind: str) -> Path:
    """Where one bench kind's record lives.

    Derived from the kind's name rather than from a table of functions, which
    is what this used to be.  The table was a second place the lens set was
    written down, and it named ``line`` and ``learning`` for as long as it took
    somebody to notice -- which is the failure mode
    :data:`PIECE_JUDGE_LENSES` exists to remove.  ``edition_review_path`` is the
    one kind whose path is not derived, because it predates the convention and
    its filename is part of committed records.
    """

    if kind == EDITION_JUDGE_KIND:
        return edition_review_path(editions_dir, edition_id)
    return review_path(editions_dir, edition_id, kind)


def _bench_state(issue: _IssueContext) -> tuple[str, str]:
    missing = [
        kind
        for kind in issue.owed_bench_kinds
        if not bench_record_path(
            issue.editions_dir, issue.edition_id, kind
        ).is_file()
    ]
    if not missing:
        return COMPLETE, "every lens that reads this edition has recorded a verdict"
    return (
        READY,
        f"{len(missing)} review record(s) not written: " + ", ".join(missing),
    )


def owed_bench_kinds(content_modes: Mapping[str, str]) -> tuple[str, ...]:
    """Which bench records this edition owes, given the pieces it declares.

    A per-piece lens is owed a record when at least one declared piece is in
    its coverage; ``edition`` is owed unconditionally, because an issue is
    always an issue.  Asked of the manifest rather than of the record
    directory, so "no teaching record" and "no explainer to teach about" stay
    two different answers -- conflating them would let a missing record excuse
    itself.
    """

    owed = [
        lens.kind
        for lens in PIECE_JUDGE_LENSES
        if any(
            lens_applies(lens, piece_id=piece_id, content_mode=content_mode)
            for piece_id, content_mode in content_modes.items()
        )
    ]
    return (*owed, EDITION_JUDGE_KIND)


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
    if graph.complete or graph.deferred:
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
