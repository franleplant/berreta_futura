"""The pipeline that owns the order of generation and judgment.

Until now the order lived in an operating agent's head: draft a piece, remember
to fact-check it, remember that the line editor must not be shown the source,
remember that a revision needs the previous draft's notes and not just the
findings.  Every one of those was reliably remembered until the run that
mattered.  ``mag produce`` moves the order into code, where forgetting is a
test failure rather than a shipped defect.

The shape, per piece::

    writer  ->  deterministic gates  ->  fact-checker + line editor (parallel)
                                              |
                       findings + the writer's own notes back to the writer
                                              |
                                       at most three rounds

and then, once every piece has passed, the two whole-issue judgments: the
learning personas, then the managing editor.

**Why the gates come first.**  A judge costs a model call and several minutes.
Pin verification, the code-fence check, figure-anchor reconciliation,
``mag validate`` and ``mag fit`` are arithmetic, and a draft that fails any of
them is going back to the writer whatever a judge would have said.  Running
them first is not only cheaper, it keeps the judges' findings about the writing
rather than about a broken build.

**Why an edition-wide gate is routed rather than broadcast.**  ``validate`` and
``fit`` see the whole issue, so one stub manuscript, or one article that runs a
page long, fails them for the entire edition.  A gate failure is not the
edition's, though: it belongs to whichever piece's prose is wrong, and only
that piece's writer can clear it.  So every complaint an edition-wide gate
makes is attributed -- ``fit`` by the measurement, which knows which article it
measured, ``validate`` by the piece its message names -- and reaches that one
writer's round and nobody else's.  A complaint that belongs to no piece belongs
to no round: it fails nothing and is reported to the human, the way a stale
translation overlay already is.  Produce also measures both gates once before
any model call, so the state the edition arrived in can be told apart from the
state this run put it in.  Without this the first piece of a fresh edition
would burn three rounds against somebody else's missing cover art.

**What produce will not do.**  It never generates an image: the illustration
runner is not imported here and no path through this module can reach one.  A
piece with no registered art is reported as a human action.  It never writes
into a released edition.  And it never re-drafts a piece whose inputs, prompt,
and manuscript are unchanged and whose judges approved -- see
:func:`~magazine.production_record.is_settled`.

The seams are the same two this package already uses elsewhere: a
:class:`~magazine.runner.CommandRunner` is injected so the suite never invokes a
model, and a :class:`ProductionGates` adapter is injected the way
``workflow.WorkflowAdapter`` is, so a test can exercise the state machine
without paginating an edition for every round.

**Editing this module while an edition is in flight is a schema migration.**
Under the agent backend a piece's finished work lives on disk as replies bound
to the identity of the question they answered.  That identity is now the prompt
file plus the content of the call
(:func:`~magazine.produce_prompts.work_identity`), so reformatting a brief is
free -- but changing the identity functions, the prompt files, or what a call is
handed will void every stored answer for the affected role, exactly as altering
a primary key would.  It is a supported change; it is not a safe one to make
under a running fleet.  Finish the edition, or expect to recover replies by hand.

**Who makes the call is not this module's business.**  Every model call goes
through one dispatch function, which is handed a :class:`WorkItem` naming the
piece, the role and the round.  An autonomous backend ignores the name and
shells out.  A cooperative backend (:mod:`magazine.produce_agent`) uses it to
look the answer up, and, when there is no answer yet, raises :class:`WorkParked`
so this pipeline can move on to work that *is* answerable and report the whole
set at once.  Nothing else about the order, the gates, the round budget, the
escalation or the records changes between the two: that is the point of putting
the seam here rather than around here.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from .concurrency import ordered_map
from .errors import MagazineError, ValidationError
from .extraction import Extraction, load_extraction, verify_source_extractions
from .footnotes import verify_manuscript_footnotes
from .code_blocks import verify_manuscript_code_blocks
from .learning_review import explainer_article_ids, furniture_projection
from .line_review import EDITORIAL_ARTICLE_ID
from .manifest import Edition
from .media_schema import semantic_headings
from .publication_document import DocumentParseError
from .produce_prompts import (
    JUDGE_PROMPTS,
    EditionReviewInput,
    EvidenceReviewInput,
    FigureSlot,
    LearningReviewInput,
    LineReviewInput,
    ManagerRunAInput,
    Piece,
    ProduceError,
    PromptFile,
    WriterBrief,
    assert_source_withheld,
    compose_edition_prompt,
    compose_evidence_prompt,
    compose_learning_prompt,
    compose_line_prompt,
    compose_manager_run_a,
    compose_writer_prompt,
    contains_scratch,
    edition_identity,
    evidence_identity,
    learning_identity,
    line_identity,
    load_prompt,
    manager_run_a_identity,
    parse_verdict,
    split_reply,
    writer_identity,
    writer_prompt_path,
)
from .production_record import (
    ModelCall,
    PieceRecord,
    RoundRecord,
    accumulated_findings,
    close_filed_findings,
    inputs_fingerprint,
    is_settled,
    issue_record_path,
    load_piece_record,
    open_filed_findings,
    piece_record_path,
    text_sha256,
    write_issue_record,
    write_piece_record,
)
from .render_review import REVIEW_RESULTS
from .review_findings import normalize_findings
from .runner import ModelRunner
from .translate_stage import set_figure_anchors

if TYPE_CHECKING:  # pragma: no cover - import cycle avoidance only
    from .compiler import Magazine


MAX_ROUNDS = 3
"""Rounds a piece gets before the pipeline stops and asks a human.

Three is not arbitrary.  Round one is a draft, round two clears what a judge
actually found, and round three clears what fixing round two broke.  A piece
still failing after that is failing for a reason the loop cannot see, and a
fourth round spends a model call to learn nothing.
"""

DEFAULT_EDITORIAL_PAGES = 1
DEFAULT_ARTICLE_PAGES = 7

# The two judges that read one piece, in the order their findings are reported.
# They run concurrently; this tuple decides only how the report reads.
PIECE_JUDGES = ("evidence", "line")

ISSUE_PIECE_ID = "issue"
"""The ``piece_id`` under which the two whole-issue judgments are named.

They belong to no single piece, and the production records already spell that
``production/issue/``; work items spell it the same way.
"""


# ---------------------------------------------------------------------------
# Naming one model call.


@dataclass(frozen=True)
class WorkItem:
    """One model call the pipeline wants made, named so a worker can be told.

    The autonomous backends never need this: they are handed a prompt and hand
    back an answer, and the identity of the call lives only in the stack frame
    that made it.  A cooperative backend has no stack frame to live in -- the
    answer arrives in a later process -- so the call needs a name that survives
    a crash, is stable across a replay, and is short enough for a human to type.
    """

    piece_id: str
    role: str
    round_number: int = 0

    @property
    def key(self) -> str:
        """The name a driver uses, and the path under ``production/agent/``."""

        role = self.role.replace("_", "-")
        if self.round_number:
            return f"{self.piece_id}/r{self.round_number}-{role}"
        return f"{self.piece_id}/{role}"


class WorkParked(Exception):
    """Signal that a cooperative backend cannot answer this call yet.

    Deliberately not a :class:`~magazine.errors.MagazineError`: it is control
    flow, not a failure, and the handlers that turn a ``MagazineError`` into a
    reported problem must not see it.  The pipeline catches it at exactly two
    places -- around one piece, and around the whole-issue judgments -- and each
    one turns it into "this unit is waiting" rather than "this run is over", so
    the remaining independent units still get their briefs composed.
    """

    def __init__(self, item: WorkItem) -> None:
        super().__init__(f"work item {item.key} has no answer yet")
        self.item = item


@dataclass(frozen=True)
class ReadyItem:
    """One brief a worker may pick up right now, with everything it needs.

    ``prompt`` is the whole composed brief, byte for byte what an autonomous
    backend would have been sent, so a worker needs nothing else.
    ``work_sha256`` is what makes a late answer refusable.  It digests the
    *question*: the prompt file, the manuscript, the findings and the notes
    this call was handed, each by digest, and never the wording this module
    chose for them.  So an answer is void when the piece moved under it and
    survives when a brief was merely reworded -- which is the difference
    between a reviser's work being asked again and a dozen finished model
    calls being thrown away by a refactor.  See
    :func:`~magazine.produce_prompts.work_identity`.
    """

    item: WorkItem
    prompt: str
    work_sha256: str
    prompt_path: str
    prompt_sha256: str
    returns: str
    brief_path: str = ""
    reply_path: str = ""

    @property
    def key(self) -> str:
        return self.item.key

    def to_dict(self) -> dict[str, Any]:
        return {
            "item": self.item.key,
            "piece_id": self.item.piece_id,
            "role": self.item.role,
            "round": self.item.round_number,
            "returns": self.returns,
            "prompt_path": self.prompt_path,
            "prompt_sha256": self.prompt_sha256,
            "work_sha256": self.work_sha256,
            "brief": self.brief_path,
            "reply": self.reply_path,
        }


# ---------------------------------------------------------------------------
# Deterministic gates.


# What a gate is allowed to raise and still be *a failing gate* rather than a
# crashed run.  ``DocumentParseError`` is here because it is what a manuscript
# that is still a staging marker produces: an HTML comment is a block the
# publication parser refuses, so the very first produce run of a freshly staged
# edition -- the one this pipeline exists to serve -- would otherwise abort with
# a traceback instead of reporting a gate.
_GATE_FAILURES = (MagazineError, DocumentParseError)


@dataclass(frozen=True)
class Breach:
    """One thing a gate is unhappy about, and the piece that can clear it.

    ``piece_id`` is ``None`` when the complaint belongs to the edition rather
    than to anybody's prose -- a manifest that will not load, a missing plate.
    No writer can be sent to fix one of those from inside a drafting round, so
    an unowned breach fails no piece and is reported to the human instead.
    """

    piece_id: str | None
    detail: str


@dataclass(frozen=True)
class GateResult:
    """One check's verdict, and -- where the check knows -- whose it is.

    ``breaches`` is how an edition-wide gate says which piece each of its
    complaints is about, so produce can hand it to that piece's writer and to
    nobody else.  ``fit`` knows, because it measures article by article.  A
    gate that leaves ``breaches`` empty is read line by line against the
    edition's piece names instead (:func:`_attributed`), which is all a check
    that can only raise a sentence has to offer.
    """

    name: str
    ok: bool
    detail: str = ""
    breaches: tuple[Breach, ...] = ()


class ProductionGates(Protocol):
    """The deterministic checks a draft must survive before a judge reads it."""

    def check_piece(
        self, piece: Piece, extractions: Sequence[Extraction]
    ) -> tuple[GateResult, ...]:
        ...

    def check_edition(self, edition_id: str) -> tuple[GateResult, ...]:
        ...


@dataclass
class DefaultProductionGates:
    """The real checks, run through the compiler the CLI already exposes.

    ``check_edition`` is memoized on the content of the tree it reads.  Both
    of its checks cost minutes on a real edition and both are pure functions
    of the files on disk, and this pipeline asks for them constantly: once as
    a baseline per invocation, once after every draft, and an agent-driven
    edition is dozens of invocations most of which change nothing.  The memo
    is :class:`~magazine.workflow.ProbeMemo`, which is the same one the
    workflow report uses for the same two checks -- reusing it rather than
    writing a second one keeps a single definition of which files a verdict
    depends on, so a hit provably means the tree is byte-identical.

    A fresh memo is built on every call, deliberately: a produce round installs
    a manuscript between calls, and a memo held across that write would key the
    new tree's question against the old tree's answer.
    """

    magazine: "Magazine"

    def check_piece(
        self, piece: Piece, extractions: Sequence[Extraction]
    ) -> tuple[GateResult, ...]:
        results: list[GateResult] = []
        label = f"{piece.manuscript}: piece {piece.id}"
        if piece.source_ids:
            results.append(
                _guarded(
                    "source_pins",
                    lambda: verify_source_extractions(
                        label,
                        _pins_for(self.magazine, piece),
                        self.magazine.sources_dir,
                        require_extractions=True,
                    ),
                )
            )
            results.append(
                _guarded(
                    "code_blocks",
                    lambda: verify_manuscript_code_blocks(
                        piece.manuscript, extractions
                    ),
                )
            )
        results.append(_anchor_gate(piece))
        # Also an edition-wide validation error, but named per piece here so
        # the writer that typed the marker is the one told about it, in the
        # same round rather than after the whole issue fails.
        results.append(
            _guarded(
                "footnotes",
                lambda: verify_manuscript_footnotes(
                    f"{piece.manuscript}: piece {piece.id}", piece.manuscript
                ),
            )
        )
        return tuple(results)

    def check_edition(self, edition_id: str) -> tuple[GateResult, ...]:
        from .workflow import ProbeMemo

        memo = ProbeMemo(self.magazine.root, edition_id)
        results: list[GateResult] = []
        for name, run in (
            ("validate", lambda: _guarded("validate", lambda: self.magazine.validate(edition_id))),
            ("fit", lambda: _fit_gate(self.magazine, edition_id)),
        ):
            # The memo's own kind namespace: the workflow report stores its
            # `fit` under that name and means every configured language, while
            # this one means the primary language alone.  Two answers to two
            # different questions must never share a slot.
            kind = f"produce:{name}"
            stored = memo.get(kind)
            if stored is not None and isinstance(stored.get("ok"), bool):
                results.append(
                    GateResult(
                        name,
                        stored["ok"],
                        str(stored.get("detail") or ""),
                        _stored_breaches(stored.get("breaches")),
                    )
                )
                continue
            gate = run()
            # Attribution is stored with the verdict.  A memo that kept only
            # the sentence would turn every hit into an unattributed gate and
            # quietly restore the misrouting this pairing exists to stop.
            memo.set(
                kind,
                {
                    "ok": gate.ok,
                    "detail": gate.detail,
                    "breaches": [
                        [breach.piece_id, breach.detail] for breach in gate.breaches
                    ],
                },
            )
            results.append(gate)
        return tuple(results)


def _pins_for(magazine: "Magazine", piece: Piece):
    from .extraction import normalize_source_pins

    row = _manifest_row(magazine, piece)
    return normalize_source_pins(
        f"piece {piece.id}", piece.source_ids, (row or {}).get("source_body_sha256")
    )


def _manifest_row(magazine: "Magazine", piece: Piece) -> dict[str, Any] | None:
    """One article's row in ``edition.yaml``, as authored.

    Read from the file rather than from the loaded :class:`Article` because the
    fingerprint that decides whether a piece may be skipped has to move when
    *any* authored key moves, including keys the dataclass normalizes away.
    """

    from .io import load_structured

    path = magazine.editions_dir / piece.edition_id / "edition.yaml"
    if not path.is_file():
        return None
    data = load_structured(path)
    for row in data.get("articles") or ():
        if isinstance(row, Mapping) and str(row.get("id")) == piece.id:
            return dict(row)
    return None


def _fit_gate(magazine: "Magazine", edition_id: str) -> GateResult:
    """Paginate the language produce actually writes, and only that one.

    ``mag fit`` measures every configured language, which is the right answer
    before a release and the wrong one here: rewriting an English manuscript
    makes the Spanish overlay's ``source_sha256`` stale by construction, and a
    reviser cannot restage a translation.  Restaging is ``mag translate``'s
    job and a translator's.  The primary language is the one this draft can be
    held to.

    The verdict is read off the measurement rather than off ``mag fit``'s
    table.  The table is a report for an eye -- one row per piece, most of them
    saying OK -- and handing it back as a gate failure told four writers about
    a fifth writer's overlong article.  The measurement knows which article
    each breach came from, so this states the breaches and who owns them and
    nothing else.  Pagination that refuses outright -- an opening paragraph
    that cannot fit its illustrated opener, say -- never reaches a measurement,
    and its message is then the only handle on ownership there is.
    """

    try:
        measurement = magazine.measure(edition_id, language=magazine.primary_language)
    except _GATE_FAILURES as error:
        return GateResult("fit", False, str(error))
    breaches = tuple(
        Breach(piece_id, detail)
        for piece_id, detail in measurement.attributed_breaches
    )
    if not breaches:
        return GateResult("fit", True)
    return GateResult(
        "fit",
        False,
        "\n".join(breach.detail for breach in breaches),
        breaches,
    )


def _guarded(name: str, action) -> GateResult:
    try:
        action()
    except ValidationError as error:
        return GateResult(name, False, "\n".join(error.errors))
    except _GATE_FAILURES as error:
        return GateResult(name, False, str(error))
    return GateResult(name, True)


def _anchor_gate(piece: Piece) -> GateResult:
    """Prove every figure anchor still names exactly one heading.

    Rewriting a piece rewrites its headings, and ``render.py`` refuses an
    anchor that does not match exactly one of them.  The failure mode this
    exists to prevent is not a crash at build time; it is a figure quietly
    losing its place and a human deciding to drop it under deadline.  So the
    reconciliation is stated as an obligation on the writer (the brief lists
    the headings) and proved here, and a lost anchor names the figure, the
    heading it wanted, and the headings the draft actually has.
    """

    wanted = piece.anchors
    if not wanted:
        return GateResult("figure_anchors", True)
    if not piece.manuscript.is_file():
        return GateResult(
            "figure_anchors", False, f"{piece.manuscript} does not exist"
        )
    present = semantic_headings(piece.manuscript)
    lost = [
        (figure_id, anchor)
        for figure_id, anchor in piece.figure_anchors
        if anchor != "__opener__" and anchor not in present
    ]
    if not lost:
        return GateResult("figure_anchors", True)
    available = ", ".join(sorted(f"'{item}'" for item in present)) or "none"
    detail = "\n".join(
        f"figure {figure_id!r} is anchored to the heading {anchor!r}, which this "
        "draft no longer contains. Restore that heading exactly, or the figure "
        "has nowhere to sit. Headings in the draft: " + available
        for figure_id, anchor in lost
    )
    return GateResult("figure_anchors", False, detail)


# ---------------------------------------------------------------------------
# Plan and report.


@dataclass(frozen=True)
class PiecePlan:
    piece_id: str
    content_mode: str
    prompt_path: str
    prompt_sha256: str
    inputs_sha256: str
    manuscript: str
    source_ids: tuple[str, ...]
    anchors: tuple[str, ...]
    settled: bool
    action: str
    filed_findings: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "piece_id": self.piece_id,
            "content_mode": self.content_mode,
            "action": self.action,
            "prompt_path": self.prompt_path,
            "prompt_sha256": self.prompt_sha256,
            "inputs_sha256": self.inputs_sha256,
            "manuscript": self.manuscript,
            "source_ids": list(self.source_ids),
            "figure_anchors": list(self.anchors),
            "settled": self.settled,
            "filed_findings": self.filed_findings,
        }


@dataclass(frozen=True)
class ProducePlan:
    edition_id: str
    backend: str
    model: str | None
    max_rounds: int
    pieces: tuple[PiecePlan, ...]
    human_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "edition_id": self.edition_id,
            "backend": self.backend,
            "model": self.model,
            "max_rounds": self.max_rounds,
            "pieces": [piece.to_dict() for piece in self.pieces],
            "human_actions": list(self.human_actions),
        }


@dataclass(frozen=True)
class PieceOutcome:
    piece_id: str
    status: str
    rounds: int
    record: str
    findings: tuple[Any, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "piece_id": self.piece_id,
            "status": self.status,
            "rounds": self.rounds,
            "record": self.record,
            "findings": list(self.findings),
        }


@dataclass(frozen=True)
class ProduceResult:
    plan: ProducePlan
    dry_run: bool
    outcomes: tuple[PieceOutcome, ...] = ()
    issue_reviews: Mapping[str, Any] = field(default_factory=dict)
    recorded: Mapping[str, str] = field(default_factory=dict)
    human_actions: tuple[str, ...] = ()
    ready: tuple[ReadyItem, ...] = ()
    """Briefs a worker may answer now.  Always empty under an autonomous run."""

    @property
    def escalated(self) -> tuple[str, ...]:
        return tuple(
            outcome.piece_id
            for outcome in self.outcomes
            if outcome.status == "escalated"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.to_dict(),
            "dry_run": self.dry_run,
            "ready": [item.to_dict() for item in self.ready],
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
            "issue_reviews": {
                kind: verdict.to_dict() if hasattr(verdict, "to_dict") else verdict
                for kind, verdict in self.issue_reviews.items()
            },
            "recorded": dict(self.recorded),
            "human_actions": list(self.human_actions),
        }


# ---------------------------------------------------------------------------
# The driver.


class Production:
    """One produce run: the pipeline, its state machine, and its records."""

    def __init__(
        self,
        magazine: "Magazine",
        *,
        runner: ModelRunner,
        model: str | None = None,
        gates: ProductionGates | None = None,
        max_rounds: int = MAX_ROUNDS,
        reviewer: str | None = None,
    ) -> None:
        if runner.kind != "text":
            # Belt and braces over the fact that this module never imports the
            # image resolver: the owner is out of image credits, and a produce
            # run that generated art would be an expensive surprise.
            raise ProduceError(
                f"produce runs text generation only; it was handed a "
                f"{runner.kind!r} runner. Illustration is never part of a "
                "produce run."
            )
        if max_rounds < 1:
            raise ProduceError("produce needs at least one round")
        self.magazine = magazine
        self.root = magazine.root
        self.runner = runner
        self.model = model
        self.gates: ProductionGates = gates or DefaultProductionGates(magazine)
        self.max_rounds = max_rounds
        self.reviewer = reviewer or f"mag produce ({runner.backend})"
        # One indirection for every model call in this module.  A runner that
        # wants to know *which* call it is being asked for exposes ``request``;
        # the two autonomous ones do not, and take the identical path they
        # always took.
        request = getattr(runner, "request", None)
        self._dispatch = request if request is not None else _direct_dispatch(runner)
        self._prompts: dict[str, PromptFile] = {}
        # Failures a human must clear that no revision round could.  Collected
        # as a set because the same overlay goes stale on every round of every
        # piece, and reporting it once is the useful number.
        self._advisories: set[str] = set()

    # -- planning ---------------------------------------------------------

    def plan(self, edition_id: str, *, articles: Sequence[str] | None = None) -> ProducePlan:
        edition = self._load_edition(edition_id)
        pieces = self._select(edition, articles)
        human_actions: list[str] = list(self._art_actions(edition, pieces))
        rows: list[PiecePlan] = []
        for piece in pieces:
            prompt = self._prompt(writer_prompt_path(piece.content_mode))
            extractions = self._extractions(piece)
            fingerprint = self._fingerprint(edition, piece, prompt, extractions)
            record = load_piece_record(self.magazine.editions_dir, edition_id, piece.id)
            filed = open_filed_findings(
                self.magazine.editions_dir, edition_id, piece.id
            )
            # A filed finding outranks settledness by construction: the whole
            # point of filing one is that the approved draft is wrong in a way
            # its judges did not catch, so "the judges approved and nothing
            # moved" is exactly the state it has to override.
            settled = not filed and is_settled(
                record,
                inputs_sha256=fingerprint,
                manuscript_sha256=_file_sha256(piece.manuscript),
            )
            rows.append(
                PiecePlan(
                    piece_id=piece.id,
                    content_mode=piece.content_mode,
                    prompt_path=prompt.path,
                    prompt_sha256=prompt.sha256,
                    inputs_sha256=fingerprint,
                    manuscript=_relative(self.root, piece.manuscript),
                    source_ids=piece.source_ids,
                    anchors=piece.anchors,
                    settled=settled,
                    filed_findings=len(filed),
                    action=_plan_action(settled, len(filed)),
                )
            )
        return ProducePlan(
            edition_id=edition_id,
            backend=self.runner.backend,
            model=self.model,
            max_rounds=self.max_rounds,
            pieces=tuple(rows),
            human_actions=tuple(human_actions),
        )

    # -- running ----------------------------------------------------------

    def run(
        self,
        edition_id: str,
        *,
        articles: Sequence[str] | None = None,
        dry_run: bool = False,
    ) -> ProduceResult:
        self._require_open(edition_id)
        plan = self.plan(edition_id, articles=articles)
        if dry_run:
            # Nothing below this line has run, and nothing on disk has moved.
            return ProduceResult(
                plan=plan, dry_run=True, human_actions=plan.human_actions
            )

        edition = self._load_edition(edition_id)
        pieces = {piece.id: piece for piece in self._select(edition, articles)}
        human_actions: list[str] = list(plan.human_actions)
        baseline = self._edition_gate_failures(edition_id)
        human_actions.extend(self._baseline_actions(baseline, edition, plan))

        outcomes: list[PieceOutcome] = []
        produced: list[str] = []
        # Every piece that is *now* approved, whether this invocation drafted it
        # or found it already settled.  The bench binds the edition as it stands
        # on disk, not as this process happened to witness it, and a run that
        # resumed -- or, under the agent backend, one of a dozen invocations that
        # each carried one piece -- would otherwise offer the recorder a subset
        # and be told there is no record to amend.
        finished: list[str] = []
        # Pieces whose work is out with a worker.  Empty for the whole of an
        # autonomous run, which is why every branch that consults it below is
        # dead code under ``codex`` and ``claude``.
        parked: list[str] = []
        for row in plan.pieces:
            piece = pieces[row.piece_id]
            record_path = str(
                piece_record_path(self.magazine.editions_dir, edition_id, piece.id)
            )
            if row.settled:
                finished.append(piece.id)
                outcomes.append(
                    PieceOutcome(
                        piece_id=piece.id,
                        status="settled",
                        rounds=0,
                        record=record_path,
                    )
                )
                continue
            if parked and _grounded_in_the_other_pieces(piece):
                # The editorial reads the pieces, so drafting it while one of
                # them is still out would ground it in text that is about to
                # change.  A sequential run gets this from the order alone; a
                # fan-out has to be told.
                outcomes.append(
                    PieceOutcome(
                        piece_id=piece.id,
                        status="waiting",
                        rounds=0,
                        record=record_path,
                    )
                )
                continue
            try:
                outcome = self._produce_piece(
                    edition_id, edition, piece, row, baseline
                )
            except WorkParked as signal:
                parked.append(piece.id)
                outcomes.append(
                    PieceOutcome(
                        piece_id=piece.id,
                        status="parked",
                        rounds=max(signal.item.round_number - 1, 0),
                        record=record_path,
                    )
                )
                continue
            outcomes.append(outcome)
            if outcome.status == "passed":
                produced.append(piece.id)
                finished.append(piece.id)
            else:
                # A piece that could not be settled makes every judgment
                # downstream of it meaningless: the learning personas and the
                # managing editor read the issue, and the issue is not finished.
                human_actions.append(
                    f"{piece.id} exhausted {outcome.rounds} round(s) and needs a "
                    f"human; see {outcome.record}"
                )
                return ProduceResult(
                    plan=plan,
                    dry_run=False,
                    outcomes=tuple(outcomes),
                    human_actions=tuple(human_actions + sorted(self._advisories)),
                )

        issue_reviews: dict[str, Any] = {}
        recorded: dict[str, str] = {}
        issue_due = produced or not self._issue_records_present(edition_id)
        if finished and not parked and issue_due:
            # The learning personas and the managing editor read the finished
            # issue.  With a piece still out, there is no finished issue, and
            # nothing may be recorded against one.
            edition = self._load_edition(edition_id)
            try:
                issue_reviews = self._judge_issue(edition_id, edition)
            except WorkParked:
                parked.append(ISSUE_PIECE_ID)
            else:
                recorded, actions = self._record_bench(
                    edition_id, edition, finished, issue_reviews
                )
                human_actions.extend(actions)
        return ProduceResult(
            plan=plan,
            dry_run=False,
            outcomes=tuple(outcomes),
            issue_reviews=issue_reviews,
            recorded=recorded,
            human_actions=tuple(human_actions + sorted(self._advisories)),
        )

    # -- one piece --------------------------------------------------------

    def _produce_piece(
        self,
        edition_id: str,
        edition: Edition,
        piece: Piece,
        row: PiecePlan,
        baseline: Mapping[str, str],
    ) -> PieceOutcome:
        prompt = self._prompt(row.prompt_path)
        extractions = self._extractions(piece)
        record = PieceRecord(
            edition_id=edition_id,
            piece_id=piece.id,
            content_mode=piece.content_mode,
            inputs_sha256=row.inputs_sha256,
            produced_at=_now(),
        )
        previous_manuscript: str | None = None
        previous_notes: str | None = None
        findings: tuple[Mapping[str, Any], ...] = ()
        gate_failures: tuple[str, ...] = ()
        # A finding filed from outside the loop makes round one a revision:
        # the draft it complains about is the one on disk, and a writer asked
        # to clear a defect without being shown the text carrying it would
        # start from nothing and lose everything else the piece got right.
        filed = open_filed_findings(self.magazine.editions_dir, edition_id, piece.id)
        if filed:
            findings = tuple(filed)
            if piece.manuscript.is_file():
                previous_manuscript = _read(piece.manuscript)
                previous_notes = _last_round_notes(
                    self.magazine.editions_dir, edition_id, piece.id
                )

        for round_number in range(1, self.max_rounds + 1):
            brief = WriterBrief(
                piece=piece,
                edition_id=edition_id,
                edition_title=edition.title,
                extractions=extractions,
                round_number=round_number,
                previous_manuscript=previous_manuscript,
                previous_notes=previous_notes,
                findings=findings,
                gate_failures=gate_failures,
                peer_manuscripts=self._peers(edition, piece),
            )
            text = compose_writer_prompt(prompt, brief)
            generated = self._dispatch(
                WorkItem(piece.id, "writer", round_number),
                prompt,
                text,
                identity=writer_identity(prompt, brief),
                cwd=self.root,
            )
            manuscript, declared_anchors, notes = split_reply(generated.text)
            if not manuscript.strip():
                raise ProduceError(
                    f"The writer returned no manuscript for {piece.id}: its whole "
                    "reply sat below the scratch marker"
                )
            if contains_scratch(manuscript):
                # Two markers in one reply would put the second block on the
                # page.  Refuse rather than guess which one was meant.
                raise ProduceError(
                    f"The writer's reply for {piece.id} carries more than one "
                    "scratch marker; the manuscript boundary is ambiguous"
                )
            _install(piece.manuscript, manuscript)
            # Before the gates, and before anything is recorded: the draft on
            # disk is now the fact, and the manifest's anchors are a claim
            # about a heading list that no longer exists.  Reconciling here
            # means the anchor gate below judges the reconciled state, which
            # is the state `mag validate` will judge too.
            piece, reconciled = self._reconcile_anchors(piece, declared_anchors)
            if reconciled:
                # The manifest row moved, so the fingerprint that decides
                # whether this piece may be skipped next time has to move with
                # it -- otherwise the very next invocation recomputes a
                # different digest, calls a settled piece unsettled, and
                # redrafts it for ever.
                record.inputs_sha256 = self._fingerprint(
                    edition, piece, prompt, extractions
                )
            round_record = RoundRecord(
                round_number=round_number,
                writer=ModelCall(
                    role="writer",
                    prompt_path=prompt.path,
                    prompt_sha256=prompt.sha256,
                    backend=generated.backend,
                    model=self.model,
                    argv=tuple(generated.argv),
                    duration_seconds=generated.duration_seconds,
                    output_sha256=text_sha256(generated.text),
                ),
                manuscript_sha256=text_sha256(_read(piece.manuscript)),
                notes=notes,
                anchors_reconciled=piece.anchors,
            )
            record.rounds.append(round_record)
            record.manuscript_sha256 = round_record.manuscript_sha256
            write_piece_record(self.magazine.editions_dir, record)

            failures = self._gate_failures(
                edition_id, edition, piece, extractions, baseline
            )
            if failures:
                round_record.gate_failures = tuple(failures)
                round_record.result = "changes_required"
                write_piece_record(self.magazine.editions_dir, record)
                previous_manuscript, previous_notes = manuscript, notes
                # Judge findings from an earlier round are deliberately *not*
                # cleared here.  A gate failure means no judge read this draft,
                # so nothing has established that the last round's findings were
                # cleared, and dropping them would quietly retire them.
                gate_failures = tuple(failures)
                continue

            verdicts = self._judge_piece(
                piece, extractions, manuscript, edition, round_number=round_number
            )
            round_record.judges = {
                name: verdict.to_dict() for name, verdict in verdicts.items()
            }
            changed = [
                verdict for verdict in verdicts.values() if verdict.result != "approved"
            ]
            round_record.result = "approved" if not changed else "changes_required"
            write_piece_record(self.magazine.editions_dir, record)
            if not changed:
                record.status = "passed"
                write_piece_record(self.magazine.editions_dir, record)
                if filed:
                    close_filed_findings(
                        self.magazine.editions_dir,
                        edition_id,
                        piece.id,
                        round_number=round_number,
                    )
                return PieceOutcome(
                    piece_id=piece.id,
                    status="passed",
                    rounds=round_number,
                    record=str(
                        piece_record_path(
                            self.magazine.editions_dir, edition_id, piece.id
                        )
                    ),
                )
            previous_manuscript, previous_notes = manuscript, notes
            gate_failures = ()
            findings = tuple(
                {**finding, "judge": name}
                for name in PIECE_JUDGES
                if name in verdicts
                for finding in verdicts[name].findings
                if isinstance(finding, Mapping)
            )

        record.status = "escalated"
        accumulated = accumulated_findings(record.to_dict())
        record.escalation = {
            "reason": (
                f"{self.max_rounds} rounds did not clear every finding. The last "
                "draft is left on disk so the defects can be read in place; the "
                "rounds below carry every finding each round produced."
            ),
            "findings": accumulated,
        }
        write_piece_record(self.magazine.editions_dir, record)
        return PieceOutcome(
            piece_id=piece.id,
            status="escalated",
            rounds=self.max_rounds,
            record=str(
                piece_record_path(self.magazine.editions_dir, edition_id, piece.id)
            ),
            findings=tuple(accumulated),
        )

    # -- anchors ----------------------------------------------------------

    def _reconcile_anchors(
        self, piece: Piece, declared: Mapping[str, str]
    ) -> tuple[Piece, bool]:
        """Move each stranded figure to the heading the new draft gives it.

        The old rule was that a rewrite must preserve every heading a figure
        was pinned to, and the gate enforced it.  That is the wrong way round:
        a piece is rewritten because its argument changed, and a heading the
        argument no longer wants is not worth a figure's place.  So the writer
        declares where each figure now sits and this moves the manifest to
        match -- one edit, in the one file that is authoritative, made by the
        process that caused the change.

        Only a *stranded* figure is moved.  A figure whose current anchor is
        still a heading of the draft is left alone even when the writer named
        a different one, because the manifest is the editor's and a writer
        does not get to relocate a figure that was never in danger.  And a
        declaration naming a heading the draft does not carry is ignored: that
        is a second stranded anchor, not a repair, and the gate's report --
        which lists the headings the draft actually has -- is the more useful
        answer.
        """

        if piece.kind != "article" or not piece.anchored_figures:
            return piece, False
        if not piece.manuscript.is_file():
            return piece, False
        headings = semantic_headings(piece.manuscript)
        wanted: dict[str, str] = {}
        for figure in piece.anchored_figures:
            if figure.anchor in headings:
                continue
            candidate = str(declared.get(figure.id) or "").strip()
            if candidate and candidate in headings:
                wanted[figure.id] = candidate
        if not wanted:
            return piece, False
        manifest = self.magazine.editions_dir / piece.edition_id / "edition.yaml"
        if not set_figure_anchors(manifest, piece.id, wanted):
            return piece, False
        return (
            replace(
                piece,
                figures=tuple(
                    replace(figure, anchor=wanted.get(figure.id, figure.anchor))
                    for figure in piece.figures
                ),
            ),
            True,
        )

    # -- judging ----------------------------------------------------------

    def _judge_piece(
        self,
        piece: Piece,
        extractions: Sequence[Extraction],
        manuscript: str,
        edition: Edition,
        *,
        round_number: int,
    ) -> dict[str, "Verdict"]:
        """Run the fact-checker and the line editor over one piece, together.

        They are independent and each costs minutes, so they overlap.
        ``ordered_map`` is the package's one fan-out: results come back in
        input order and the lowest-index failure is the one raised, so the two
        judges cannot make a run's error message depend on thread scheduling.
        """

        evidence_prompt = self._prompt(JUDGE_PROMPTS["evidence"])
        line_prompt = self._prompt(JUDGE_PROMPTS["line"])
        evidence_input = EvidenceReviewInput(
            piece_id=piece.id,
            content_mode=piece.content_mode,
            byline=piece.byline,
            manuscript=manuscript,
            extractions=tuple(extractions),
            peer_manuscripts=self._peers(edition, piece),
        )
        line_input = LineReviewInput(
            piece_id=piece.id,
            content_mode=piece.content_mode,
            byline=piece.byline,
            max_pages=piece.max_pages,
            manuscript=manuscript,
        )
        evidence_text = compose_evidence_prompt(evidence_prompt, evidence_input)
        line_text = compose_line_prompt(line_prompt, line_input)
        # The type already makes a source impossible to pass; this catches a
        # future edit that smuggles one in through the manuscript or a peer.
        assert_source_withheld(
            line_text, extractions, manuscript=manuscript, label="line editor"
        )
        jobs = (
            (
                "evidence",
                evidence_prompt,
                evidence_text,
                evidence_identity(evidence_prompt, evidence_input),
            ),
            ("line", line_prompt, line_text, line_identity(line_prompt, line_input)),
        )
        # Both jobs run whatever either does, so under a cooperative backend
        # both briefs are composed and offered even though the first one to
        # find no answer is the one whose signal escapes.  That is what makes
        # the fact-checker and the line editor a *pair* a driver can fan out.
        results = ordered_map(
            lambda job: self._verdict(
                job[0],
                job[1],
                job[2],
                piece_id=piece.id,
                identity=job[3],
                round_number=round_number,
            ),
            jobs,
            workers=2,
        )
        return {job[0]: verdict for job, verdict in zip(jobs, results)}

    def _issue_records_present(self, edition_id: str) -> bool:
        """Whether both whole-issue judgments have already been made.

        A run that produced nothing new has nothing to re-judge, which is why
        the whole-issue personas are normally skipped in that case: they are the
        most expensive calls in the pipeline and re-running them over unchanged
        text buys nothing.  But "produced nothing new" is also what the *last*
        invocation of an agent-driven loop looks like -- every piece settled two
        invocations ago and only the manager's runs are left -- so the skip has
        to be conditioned on the judgments actually existing rather than on this
        process having drafted something.
        """

        return all(
            issue_record_path(self.magazine.editions_dir, edition_id, kind).is_file()
            for kind in ("learning", "edition")
        )

    def _judge_issue(self, edition_id: str, edition: Edition) -> dict[str, Any]:
        """The learning personas, then the managing editor.

        The manager's two runs are the reason this is not one call.  Run A sees
        the furniture and nothing else; run B is handed A's block and the
        bodies.  A single run cannot un-see the body, and that is precisely the
        run that finds its own takeaways well supported.
        """

        learning_prompt = self._prompt(JUDGE_PROMPTS["learning"])
        furniture = furniture_projection(edition)
        run_a_input = ManagerRunAInput(edition_id=edition_id, furniture=furniture)
        run_a = self._dispatch(
            WorkItem(ISSUE_PIECE_ID, "manager_run_a"),
            learning_prompt,
            compose_manager_run_a(learning_prompt, run_a_input),
            identity=manager_run_a_identity(learning_prompt, run_a_input),
            cwd=self.root,
        )
        takeaways_document = parse_verdict(run_a.text, label="manager run A")
        takeaways = takeaways_document.get("manager_takeaways") or []
        run_a_block = _takeaways_block(takeaways)

        explainer_ids = set(explainer_article_ids(edition))
        explainers = tuple(
            (article.id, _read(article.manuscript))
            for article in edition.articles
            if article.id in explainer_ids
        )
        extractions: list[Extraction] = []
        for article in edition.articles:
            if article.id not in explainer_ids:
                continue
            extractions.extend(self._extractions_for(article.source_ids))
        learning_input = LearningReviewInput(
            edition_id=edition_id,
            furniture=furniture,
            manager_takeaways=run_a_block,
            explainers=explainers,
            articles=tuple(
                (article.id, _read(article.manuscript))
                for article in edition.articles
            ),
            extractions=tuple(extractions),
        )
        learning_verdict = self._verdict(
            "learning",
            learning_prompt,
            compose_learning_prompt(learning_prompt, learning_input),
            piece_id=ISSUE_PIECE_ID,
            identity=learning_identity(learning_prompt, learning_input),
        )
        _require_unrevised_takeaways(takeaways, learning_verdict.document)
        write_issue_record(
            self.magazine.editions_dir,
            edition_id,
            "learning",
            {
                "manager_run_a": {
                    "call": ModelCall(
                        role="manager_run_a",
                        prompt_path=learning_prompt.path,
                        prompt_sha256=learning_prompt.sha256,
                        backend=run_a.backend,
                        model=self.model,
                        argv=tuple(run_a.argv),
                        duration_seconds=run_a.duration_seconds,
                        output_sha256=text_sha256(run_a.text),
                    ).to_dict(),
                    "manager_takeaways": takeaways,
                },
                "run_b": learning_verdict.to_dict(),
            },
        )

        edition_prompt = self._prompt(JUDGE_PROMPTS["edition"])
        edition_input = EditionReviewInput(
            edition_id=edition_id,
            manifest=_issue_furniture(edition),
            editorial=(
                _read(edition.editorial.path)
                if edition.editorial is not None
                else None
            ),
            articles=tuple(
                (article.id, article.content_mode, _read(article.manuscript))
                for article in edition.articles
            ),
        )
        edition_verdict = self._verdict(
            "edition",
            edition_prompt,
            compose_edition_prompt(edition_prompt, edition_input),
            piece_id=ISSUE_PIECE_ID,
            identity=edition_identity(edition_prompt, edition_input),
        )
        write_issue_record(
            self.magazine.editions_dir,
            edition_id,
            "edition",
            {"run": edition_verdict.to_dict()},
        )
        return {"learning": learning_verdict, "edition": edition_verdict}

    def _verdict(
        self,
        name: str,
        prompt: PromptFile,
        text: str,
        *,
        piece_id: str,
        identity: str,
        round_number: int = 0,
    ) -> "Verdict":
        generated = self._dispatch(
            WorkItem(piece_id, name, round_number),
            prompt,
            text,
            identity=identity,
            cwd=self.root,
        )
        document = parse_verdict(generated.text, label=f"{name} judge")
        result = str(document.get("result") or "").strip()
        if result not in REVIEW_RESULTS:
            raise ProduceError(
                f"The {name} judge returned result {result!r}; the prompt allows "
                + " or ".join(sorted(REVIEW_RESULTS))
            )
        findings = normalize_findings(
            document.get("findings") or (), label=f"{name} review"
        )
        return Verdict(
            name=name,
            result=result,
            findings=tuple(findings),
            scores=dict(document.get("scores") or {}),
            notes=str(document.get("notes") or ""),
            document=document,
            call=ModelCall(
                role=f"{name}_judge",
                prompt_path=prompt.path,
                prompt_sha256=prompt.sha256,
                backend=generated.backend,
                model=self.model,
                argv=tuple(generated.argv),
                duration_seconds=generated.duration_seconds,
                output_sha256=text_sha256(generated.text),
            ),
        )

    # -- gates ------------------------------------------------------------

    def _edition_gate_failures(self, edition_id: str) -> dict[str, str]:
        return {
            gate.name: gate.detail
            for gate in self.gates.check_edition(edition_id)
            if not gate.ok
        }

    def _baseline_actions(
        self, baseline: Mapping[str, str], edition: Edition, plan: ProducePlan
    ) -> list[str]:
        """How the edition's gates already stood, before a model was called.

        Worth stating: a run that begins on a failing edition ends on one
        unless the drafting happens to clear it, and an operator should not
        have to infer that.  But a failure that names only pieces this run is
        about to draft is not a fault at all -- an unwritten piece fails
        ``validate`` by definition, and ``mag produce`` is the command that
        writes it -- so it is stated as the expected thing it is.  Reported as
        a fault on every invocation, as it was, it teaches an operator to skim
        past the line where a real failure will one day appear.
        """

        drafting = {row.piece_id for row in plan.pieces if not row.settled}
        names = _piece_names(edition)
        actions: list[str] = []
        for gate_name, detail in baseline.items():
            named = {
                piece_id
                for piece_id, needles in names.items()
                if _names_piece(detail, needles)
            }
            headline = detail.splitlines()[0] if detail.splitlines() else detail
            if named and named <= drafting:
                actions.append(
                    f"pre-existing gate failure ({gate_name}), expected and "
                    "cleared by this run, which is drafting every piece it "
                    f"names: {headline}"
                )
            else:
                actions.append(f"pre-existing gate failure ({gate_name}): {headline}")
        return actions

    def _gate_failures(
        self,
        edition_id: str,
        edition: Edition,
        piece: Piece,
        extractions: Sequence[Extraction],
        baseline: Mapping[str, str],
    ) -> list[str]:
        """Everything this draft broke, and nothing that is somebody else's.

        A per-piece gate is always this writer's problem.  An edition-wide gate
        is a report about the whole issue, and every complaint inside it
        belongs to somebody: to one piece, whose writer is told and is the only
        one told, or to the edition, which no writer can be sent to fix and
        which therefore fails nobody and goes to the human instead.

        The routing is the point.  ``fit`` measures the edition, so one article
        whose opening paragraph will not fit its opener used to fail every
        other piece in the round -- four writers handed an instruction to
        shorten a paragraph in an article they cannot edit, every round, until
        somebody fixed the fifth piece by hand.
        """

        failures = [
            f"{gate.name}: {gate.detail}"
            for gate in self.gates.check_piece(piece, extractions)
            if not gate.ok
        ]
        names = _piece_names(edition)
        for gate in self.gates.check_edition(edition_id):
            if gate.ok:
                continue
            inherited = baseline.get(gate.name, "")
            mine: list[str] = []
            for breach in _attributed(gate, names):
                actionable, drift = _split_translation_drift(breach.detail)
                if drift:
                    # Rewriting the English manuscript stales the overlays that
                    # pin it, every time, and no reviser can fix that from
                    # inside a drafting round.  Reported once, to the human who
                    # will run `mag translate`, rather than fed back as an
                    # impossible instruction that would spend the round budget.
                    self._advisories.add(
                        "language overlays are stale after this rewrite; restage "
                        f"them with `mag translate {edition_id} <language>`: "
                        + drift
                    )
                if not actionable:
                    continue
                if breach.piece_id is None:
                    if actionable in inherited:
                        # The edition arrived in this state and the pre-existing
                        # report has already said so, once, before any model was
                        # called.  Repeating it per piece per round is how the
                        # one that matters gets skimmed past.
                        continue
                    self._advisories.add(
                        f"{gate.name} fails for {edition_id} as a whole, and no "
                        "single piece's rewrite can clear it: " + actionable
                    )
                    continue
                if breach.piece_id == piece.id:
                    mine.append(actionable)
            if mine:
                failures.append(f"{gate.name}: " + "\n".join(mine))
        return failures

    # -- recording --------------------------------------------------------

    def _record_bench(
        self,
        edition_id: str,
        edition: Edition,
        finished: Sequence[str],
        issue_reviews: Mapping[str, Any],
    ) -> tuple[dict[str, str], list[str]]:
        """Bind each judge's verdict through the bench's own recorder.

        Nothing here writes a review file directly.  The recorders re-derive
        the hash bindings from disk and re-run ``validate`` on the way past,
        which is exactly the independence a recorded verdict is supposed to
        have -- and it means a produce run cannot record an approval over bytes
        that are no longer there.
        """

        from .evidence_review import evidence_review_path, load_evidence_review
        from .line_review import line_review_path, load_line_review

        recorded: dict[str, str] = {}
        actions: list[str] = []
        article_ids = {article.id for article in edition.articles}
        produced_articles = [item for item in finished if item in article_ids]
        produced_pieces = list(finished)

        for kind, ids, loader, path_of, recorder in (
            (
                "evidence",
                produced_articles,
                load_evidence_review,
                evidence_review_path,
                self.magazine.record_evidence_review,
            ),
            (
                "line",
                produced_pieces,
                load_line_review,
                line_review_path,
                self.magazine.record_line_review,
            ),
        ):
            if not ids:
                continue
            # The editorial has no ``source_ids`` row, so the evidence record
            # cannot bind it -- but the fact-checker did read it against the
            # issue, and dropping its findings would lose the only audit the
            # editorial gets.  Findings are record-level, so they travel;
            # only the bindings are per-article.
            findings, scores = self._bench_payload(
                edition_id, kind, produced_pieces, score_ids=ids
            )
            existing = None
            try:
                existing = loader(
                    path_of(self.magazine.editions_dir, edition_id),
                    edition_id=edition_id,
                )
            except ValidationError:
                existing = None
            whole = set(ids) >= self._bench_universe(kind, edition)
            if existing is None and not whole:
                # ``rebind_articles`` refuses a partial amendment with no record
                # to amend, and it is right to: recording the whole edition here
                # would re-bless pieces this run never judged.
                actions.append(
                    f"no {kind} review record exists to amend, and this run "
                    f"produced only {', '.join(sorted(ids))}. Produce the whole "
                    f"edition, or record the full {kind} review by hand, before "
                    "the per-piece verdicts can be bound."
                )
                continue
            try:
                recorded[kind] = str(
                    recorder(
                        edition_id,
                        reviewer=self.reviewer,
                        result="approved",
                        findings=findings,
                        scores=scores,
                        notes=f"Recorded by mag produce; {len(ids)} piece(s) judged.",
                        articles=None if whole and existing is None else sorted(ids),
                    )
                )
            except MagazineError as error:
                actions.append(f"could not record the {kind} review: {error}")

        for kind in ("learning", "edition"):
            verdict = issue_reviews.get(kind)
            if verdict is None:
                continue
            recorder = (
                self.magazine.record_learning_review
                if kind == "learning"
                else self.magazine.record_edition_review
            )
            extra: dict[str, Any] = {}
            if kind == "learning":
                extra = {
                    "comprehension": verdict.document.get("comprehension") or (),
                    "manager_takeaways": verdict.document.get("manager_takeaways")
                    or (),
                }
            try:
                recorded[kind] = str(
                    recorder(
                        edition_id,
                        reviewer=self.reviewer,
                        result=verdict.result,
                        findings=verdict.findings,
                        scores=verdict.scores or None,
                        notes=verdict.notes,
                        **extra,
                    )
                )
            except MagazineError as error:
                actions.append(f"could not record the {kind} review: {error}")
            if verdict.result != "approved":
                actions.append(
                    f"the {kind} review returned changes_required; its findings "
                    "are whole-issue and need a human editor, not another "
                    "drafting round"
                )
        return recorded, actions

    def _bench_universe(self, kind: str, edition: Edition) -> set[str]:
        ids = {article.id for article in edition.articles}
        if kind == "line" and edition.editorial is not None:
            ids.add(EDITORIAL_ARTICLE_ID)
        return ids

    def _bench_payload(
        self,
        edition_id: str,
        kind: str,
        ids: Sequence[str],
        *,
        score_ids: Sequence[str],
    ) -> tuple[list[Any], dict[str, dict[str, int]]]:
        """The findings and scores the approving round left, read back off disk.

        Read back from the production records rather than carried in memory so
        that a resumed run records what actually happened rather than what this
        process happened to witness.
        """

        findings: list[Any] = []
        scores: dict[str, dict[str, int]] = {}
        for piece_id in ids:
            record = load_piece_record(
                self.magazine.editions_dir, edition_id, piece_id
            )
            if not isinstance(record, Mapping):
                continue
            rounds = record.get("rounds") or ()
            if not rounds:
                continue
            last = rounds[-1]
            judge = (last.get("judges") or {}).get(kind)
            if not isinstance(judge, Mapping):
                continue
            findings.extend(judge.get("findings") or ())
            row = judge.get("scores")
            if piece_id in set(score_ids) and isinstance(row, Mapping) and row:
                scores[piece_id] = {
                    str(name): int(value)
                    for name, value in row.items()
                    if isinstance(value, int) and not isinstance(value, bool)
                }
        return findings, scores

    # -- edition plumbing -------------------------------------------------

    def _require_open(self, edition_id: str) -> None:
        """Refuse a released edition, and refuse an edition that is not there.

        The one thing produce must never do is rewrite prose a reader has
        already been handed, so a released id is refused outright and the
        refusal names the remedy: regenerate into a sibling workspace.

        A sibling workspace is an edition directory that exists and is not in
        the release ledger at all -- deliberately not queued, because the point
        of a rerun is to be compared against the shipped issue rather than
        shipped itself.  Requiring it to be *collecting* would mean the only
        way to take the remedy above is to put the rerun in the queue it must
        stay out of, so the guard asks for a manifest instead: an id with no
        ``edition.yaml`` behind it is the typo -- or the un-opened edition --
        that the ledger check was really catching.
        """

        state = self.magazine._require_release_state()
        if edition_id in state.collecting_edition_ids:
            return
        released = {str(row.get("id")) for row in state.released_editions}
        if edition_id in released:
            raise ProduceError(
                f"{edition_id} is released. Produce never rewrites a released "
                "edition's manuscripts; regenerate it deliberately into a "
                "sibling workspace instead."
            )
        if (self.magazine.editions_dir / edition_id / "edition.yaml").is_file():
            return
        raise ProduceError(
            f"{edition_id} has no editions/{edition_id}/edition.yaml and is not "
            "a collecting edition; open it with `mag collect`, or stage the "
            "sibling workspace you meant to produce into"
        )

    def _load_edition(self, edition_id: str) -> Edition:
        return load_producible_edition(self.magazine, edition_id)

    def _select(
        self, edition: Edition, articles: Sequence[str] | None
    ) -> list[Piece]:
        pieces = [self._article_piece(edition, article) for article in edition.articles]
        if edition.editorial is not None:
            # Last: the editorial is grounded in the pieces, so drafting it
            # before them would ground it in text that is about to change.
            pieces.append(self._editorial_piece(edition))
        if articles is None:
            return pieces
        wanted = [str(item).strip() for item in articles if str(item).strip()]
        known = {piece.id: piece for piece in pieces}
        unknown = sorted(set(wanted) - set(known))
        if unknown:
            raise ProduceError(
                f"{edition.id} has no piece(s) named " + ", ".join(unknown) + "; it "
                "carries " + ", ".join(sorted(known))
            )
        return [piece for piece in pieces if piece.id in set(wanted)]

    def _article_piece(self, edition: Edition, article: Any) -> Piece:
        budget = opener_intro_budget(self.magazine, edition, article)
        return Piece(
            id=article.id,
            kind="article",
            content_mode=article.content_mode,
            title=article.title,
            byline=article.author,
            manuscript=article.manuscript,
            edition_id=edition.id,
            source_ids=tuple(article.source_ids),
            figures=tuple(
                FigureSlot(figure.id, figure.anchor, figure.caption)
                for figure in article.figures
            ),
            max_pages=_page_budget(edition, "max_article_pages", DEFAULT_ARTICLE_PAGES),
            key_ideas=tuple(article.key_ideas),
            has_opener_art=article.opener_art is not None,
            opener_intro_lines=budget.lines if budget else 0,
            opener_intro_safe_characters=budget.safe_characters if budget else 0,
        )

    def _editorial_piece(self, edition: Edition) -> Piece:
        editorial = edition.editorial
        return Piece(
            id=EDITORIAL_ARTICLE_ID,
            kind="editorial",
            content_mode="original_editorial",
            title=editorial.title,
            byline=editorial.byline,
            manuscript=editorial.path,
            edition_id=edition.id,
            max_pages=_page_budget(
                edition, "max_editorial_pages", DEFAULT_EDITORIAL_PAGES
            ),
        )

    def _peers(self, edition: Edition, piece: Piece) -> tuple[tuple[str, str], ...]:
        """The other pieces, supplied only where a role is judged against them.

        The editorial is the one piece whose truth lives in the edition rather
        than in a source, so it -- and only it -- carries the articles.
        """

        if piece.kind != "editorial":
            return ()
        return tuple(
            (article.id, _read(article.manuscript))
            for article in edition.articles
            if article.manuscript.is_file()
        )

    def _extractions(self, piece: Piece) -> tuple[Extraction, ...]:
        return self._extractions_for(piece.source_ids)

    def _extractions_for(self, source_ids: Iterable[str]) -> tuple[Extraction, ...]:
        found: list[Extraction] = []
        missing: list[str] = []
        for source_id in source_ids:
            extraction = load_extraction(self.magazine.sources_dir, source_id)
            if extraction is None:
                missing.append(source_id)
                continue
            found.append(extraction)
        if missing:
            raise ProduceError(
                "Cannot draft from sources with no committed extraction: "
                + ", ".join(missing)
                + ". A writer that has not been given the source will invent one."
            )
        return tuple(found)

    def _fingerprint(
        self,
        edition: Edition,
        piece: Piece,
        prompt: PromptFile,
        extractions: Sequence[Extraction],
    ) -> str:
        peers = None
        if piece.kind == "editorial":
            peers = {
                article.id: text_sha256(_read(article.manuscript))
                for article in edition.articles
                if article.manuscript.is_file()
            }
        return inputs_fingerprint(
            content_mode=piece.content_mode,
            prompt_sha256=prompt.sha256,
            manifest_row=_manifest_row(self.magazine, piece)
            if piece.kind == "article"
            else {"editorial": str(piece.manuscript), "title": piece.title},
            extraction_body_sha256={
                extraction.source_id: extraction.body_sha256
                for extraction in extractions
            },
            peer_manuscript_sha256=peers,
        )

    def _art_actions(self, edition: Edition, pieces: Sequence[Piece]) -> list[str]:
        """Art a piece is missing, reported and never generated.

        Produce has no image runner and will not acquire one here.  The owner
        is out of image credits; more to the point, generating art as a side
        effect of a text pipeline is how an edition ends up with art nobody
        chose.
        """

        actions: list[str] = []
        for piece in pieces:
            if piece.kind == "editorial" or piece.has_opener_art:
                continue
            actions.append(
                f"{piece.id} has no registered opener art. Produce never "
                "generates an image; register one with `mag interior-art "
                "register` or leave the piece without an opener."
            )
        return actions

    def _prompt(self, relative: str) -> PromptFile:
        if relative not in self._prompts:
            self._prompts[relative] = load_prompt(self.root, relative)
        return self._prompts[relative]


@dataclass(frozen=True)
class Verdict:
    name: str
    result: str
    findings: tuple[Any, ...]
    scores: Mapping[str, Any]
    notes: str
    document: Mapping[str, Any]
    call: ModelCall

    def to_dict(self) -> dict[str, Any]:
        return {
            "result": self.result,
            "findings": list(self.findings),
            "scores": dict(self.scores),
            "notes": self.notes,
            "call": self.call.to_dict(),
        }


# ---------------------------------------------------------------------------
# Helpers.


def _direct_dispatch(runner: ModelRunner):
    """Call a runner that neither knows nor cares which item it is answering.

    This is the whole of what the two autonomous backends see of the work-item
    machinery: the name is composed, handed to this function, and dropped.
    """

    def call(
        item: WorkItem,
        prompt: PromptFile,
        text: str,
        *,
        identity: str,
        cwd: Path,
    ):
        return runner.generate(text, cwd=cwd)

    return call


def _plan_action(settled: bool, filed: int) -> str:
    if filed:
        return f"draft and judge: {filed} filed finding(s) to clear"
    return "skip: settled" if settled else "draft and judge"


def _last_round_notes(editions_dir: Path, edition_id: str, piece_id: str) -> str | None:
    """The working notes of the last recorded round, if there was one.

    A filed finding arrives long after the process that drafted the piece has
    exited, so the predecessor's mind is only where it was durably put.  This
    is the case the notes were made durable for.
    """

    record = load_piece_record(editions_dir, edition_id, piece_id)
    rounds = (record or {}).get("rounds") or ()
    if not isinstance(rounds, Sequence) or not rounds:
        return None
    last = rounds[-1]
    notes = str(last.get("notes") or "") if isinstance(last, Mapping) else ""
    return notes or None


def _grounded_in_the_other_pieces(piece: Piece) -> bool:
    """Whether this piece may only be drafted once every other one is settled.

    One piece answers yes.  The editorial is written from the articles, and
    ``_select`` already puts it last for that reason; this states the same
    constraint in the form a fan-out can check, because a fan-out has no order
    to inherit it from.
    """

    return piece.kind == "editorial"


def _takeaways_block(takeaways: Any) -> str:
    import yaml

    return yaml.safe_dump(
        {"manager_takeaways": takeaways}, sort_keys=False, allow_unicode=True
    ).rstrip()


def _require_unrevised_takeaways(
    run_a: Any, document: Mapping[str, Any]
) -> None:
    """Refuse a run B that improved run A's claims after reading the body.

    The whole measurement is whether the body supports what a manager took away
    from the furniture alone.  A run B that quietly rewrites a claim it cannot
    support has answered a different, easier question, and no reader of the
    record could tell.
    """

    if not isinstance(run_a, Sequence) or isinstance(run_a, (str, bytes)):
        return
    written = {
        str(entry.get("article")): _claim_set(entry)
        for entry in run_a
        if isinstance(entry, Mapping)
    }
    if not written:
        return
    adjudicated = document.get("manager_takeaways") or ()
    if not isinstance(adjudicated, Sequence) or isinstance(adjudicated, (str, bytes)):
        raise ProduceError(
            "The learning judge returned no manager_takeaways; run A's block "
            "must come back adjudicated, not dropped"
        )
    seen: set[str] = set()
    for entry in adjudicated:
        if not isinstance(entry, Mapping):
            continue
        article = str(entry.get("article"))
        seen.add(article)
        if article not in written:
            continue
        if _claim_set(entry) != written[article]:
            raise ProduceError(
                f"Run B rewrote run A's manager takeaways for {article!r}. Run A "
                "is written before the body is visible and is never revised: an "
                "adjudication of improved claims measures nothing."
            )
    dropped = sorted(set(written) - seen)
    if dropped:
        raise ProduceError(
            "Run B dropped run A's manager takeaways for " + ", ".join(dropped)
        )


def _claim_set(entry: Mapping[str, Any]) -> tuple[str, tuple[str, ...]]:
    claims = entry.get("claims") or ()
    if isinstance(claims, (str, bytes)) or not isinstance(claims, Sequence):
        claims = ()
    return (
        str(entry.get("decision") or "").strip(),
        tuple(str(claim).strip() for claim in claims),
    )


def _issue_furniture(edition: Edition) -> dict[str, Any]:
    raw = edition.raw or {}
    return {
        "id": edition.id,
        "title": raw.get("title"),
        "subtitle": raw.get("subtitle"),
        "cover": raw.get("cover") or {},
        "format": raw.get("format") or {},
        "contents": [
            {
                "id": article.id,
                "title": article.title,
                "content_mode": article.content_mode,
            }
            for article in edition.articles
        ],
    }


def load_producible_edition(magazine: Any, edition_id: str) -> Edition:
    """Load an edition the way produce needs it: mid-draft, not finished.

    Module level rather than a :class:`Production` method because the two
    callers that are not a produce run -- the opener fit check among them --
    need the same tolerances and must not have to build a runner to get them.
    """

    from .manifest import load_edition
    from .records import load_records

    records = {record.id: record for record in load_records(magazine.sources_dir)}
    return load_edition(
        magazine.root,
        edition_id,
        set(records),
        publication_name=magazine.publication_name,
        source_records=records,
        # Art is not produce's business: it must never generate one, and a
        # missing opener is reported as a human action rather than as a
        # reason the writer cannot draft.
        allow_missing_art=True,
        # A stranded figure anchor is the one validation error produce is
        # *for*: the anchor gate names the figure, the heading it wanted and
        # the headings the draft has, and hands that to the next round.
        # Refusing to load the edition would turn the repairable case into
        # an unloadable one, which is what a resumed or agent-driven run --
        # one that re-reads the tree between rounds -- would hit first.
        allow_unanchored_figures=True,
    )


def opener_fit(
    magazine: Any, edition_id: str, article_id: str, intro: str
) -> tuple[str, bool]:
    """Answer, for one candidate opening paragraph, the question the gate asks.

    The writer's own check, and the reason it exists: the arithmetic was
    reachable only by importing the typesetter and reproducing the folding by
    hand, so the first writer to need it did exactly that -- after the round it
    had already lost.  This is the same arithmetic through the front door.

    Returns the report to print and whether the paragraph fits, so the caller
    can make the verdict an exit code.  It refuses loudly rather than guessing
    when the piece is not one the constraint governs, because a cheerful
    ``fits`` for an article with no illustrated opener is the answer to a
    question nobody asked.
    """

    edition = load_producible_edition(magazine, edition_id)
    articles = {article.id: article for article in edition.articles}
    article = articles.get(article_id)
    if article is None:
        raise ProduceError(
            f"{edition_id} has no article {article_id!r}; it carries "
            + ", ".join(sorted(articles))
        )
    budget = opener_intro_budget(magazine, edition, article)
    if budget is None:
        raise ProduceError(
            f"{article_id} has no illustrated opener, so its first paragraph "
            "has no length limit to check: it flows onto the following page "
            "like any other paragraph"
        )
    text = " ".join(intro.split())
    if not text:
        raise ProduceError(
            "The opening paragraph to check is read from standard input, and "
            f"nothing arrived. Pipe it in: printf '%s' \"...\" | mag fit "
            f"{edition_id} --opener {article_id}"
        )
    lines = budget.wrapped(text)
    ok = len(lines) <= budget.lines
    report = [
        f"{article_id}: {len(lines)} of {budget.lines} typeset line(s), "
        f"{len(text)} character(s) -- {'fits' if ok else 'OVER'}",
    ]
    if budget.safe_characters:
        report.append(
            f"a paragraph of {budget.safe_characters} character(s) or fewer "
            "always fits; past that this check is the only answer"
        )
    report.append("")
    report.extend(
        f"  {number:>2}  {line}" for number, line in enumerate(lines, start=1)
    )
    if not ok:
        report.append("")
        report.append(
            f"Cut to {budget.lines} line(s). The build refuses an edition whose "
            "opener paragraph overruns; it does not reflow onto page two."
        )
    return "\n".join(report), ok


def opener_intro_budget(magazine: Any, edition: Edition, article: Any):
    """This article's opening-paragraph budget, exactly as its brief states it.

    One function so that one number exists.  The brief a writer is given and
    the check a writer runs against a candidate paragraph (``mag fit --opener``,
    :meth:`~magazine.compiler.Magazine.opener_fit`) both come through here, and
    both therefore see the same sample and quote the same floor.  Splitting
    them would let the advice drift from the answer, which is the failure this
    whole area already had once.
    """

    return _opener_intro_budget(
        edition, article, _source_prose_quietly(magazine, article)
    )


def _source_prose_quietly(magazine: Any, article: Any) -> str:
    """This article's source prose, for measuring characters per line.

    Quietly, because a missing extraction is a refusal the drafting path
    already makes with a much better message; failing to state a character
    floor is not worth pre-empting it here.
    """

    bodies: list[str] = []
    for source_id in getattr(article, "source_ids", ()) or ():
        try:
            extraction = load_extraction(magazine.sources_dir, source_id)
        except MagazineError:
            continue
        if extraction is not None:
            bodies.append(extraction.body)
    return "\n".join(bodies)


def _opener_intro_budget(edition: Edition, article: Any, sample: str):
    """This article's opening-paragraph budget, or ``None`` when it has none.

    The constraint belongs to one composition: an illustrated opener, which
    needs both the edition-level format and this article's own opener art.
    An article without either flows its first paragraph like any other and is
    told nothing, because a limit that does not apply is a limit a writer will
    eventually work around for no reason.

    Every failure is silent.  A brief that could not state the number is worse
    than one that states it, and far better than a produce run that aborted
    while measuring an advisory.
    """

    raw_format = (edition.raw or {}).get("format")
    if not isinstance(raw_format, Mapping):
        return None
    if str(raw_format.get("article_opener") or "") != "illustrated_paper_spots_v1":
        return None
    if getattr(article, "opener_art", None) is None:
        return None
    try:
        from .weasyprint_adapter import illustrated_opener_intro_budget

        return illustrated_opener_intro_budget(
            title=str(article.title or ""),
            byline=str(getattr(article, "author", "") or ""),
            author_note=str(getattr(article, "author_note", "") or ""),
            sample=sample,
        )
    except Exception:
        return None


def _page_budget(edition: Edition, key: str, default: int) -> int:
    fmt = (edition.raw or {}).get("format") or {}
    value = fmt.get(key)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return default


def _piece_names(edition: Edition) -> dict[str, tuple[str, ...]]:
    """What a gate's report would call each piece of this edition.

    Its id and the path of the manuscript it lives in: between them those are
    everything a gate says when it means one piece.
    """

    names = {
        article.id: (article.id, str(article.manuscript))
        for article in edition.articles
    }
    if edition.editorial is not None:
        names[EDITORIAL_ARTICLE_ID] = (
            EDITORIAL_ARTICLE_ID,
            str(edition.editorial.path),
        )
    return names


@lru_cache(maxsize=None)
def _whole_word(name: str) -> re.Pattern[str]:
    """One piece's name, matched whole rather than as a substring.

    ``editorial`` is a substring of ``editorial minimum``, which is the phrase
    ``fit`` uses when an *article* runs short, so a plain ``in`` test hands
    that article's complaint to the editorial's writer as well.
    """

    return re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])")


def _names_piece(text: str, names: Sequence[str]) -> bool:
    return any(_whole_word(name).search(text) for name in names)


def _attributed(
    gate: GateResult, names: Mapping[str, Sequence[str]]
) -> tuple[Breach, ...]:
    """One gate's report, split into the pieces its complaints are about.

    A gate that already knows is believed: ``fit`` measures article by article
    and hands back its breaches already owned.  Everything else -- ``validate``
    above all -- accumulates the whole edition's complaints into one message,
    and the only handle left on ownership is which piece a line names.  A line
    naming pieces belongs to them; a line naming none belongs to the edition,
    and so to no writer's round.

    Reading the message is the second choice and is taken only where there is
    no measurement to read instead: ``validate`` raises sentences, and it would
    have to carry an owner on every error it accumulates before this could be
    anything better.
    """

    if gate.breaches:
        return gate.breaches
    found: list[Breach] = []
    for line in gate.detail.splitlines():
        if not line.strip():
            continue
        owners = [
            piece_id
            for piece_id, needles in names.items()
            if _names_piece(line, needles)
        ]
        if owners:
            found.extend(Breach(owner, line) for owner in owners)
        else:
            found.append(Breach(None, line))
    return tuple(found)


def _stored_breaches(raw: Any) -> tuple[Breach, ...]:
    """Rebuild a memoized gate's attribution.

    A cache entry written before gates carried attribution has none, and a
    gate with none is read by naming -- the same answer the miss would give.
    """

    if not isinstance(raw, list):
        return ()
    return tuple(
        Breach(item[0] if isinstance(item[0], str) else None, str(item[1]))
        for item in raw
        if isinstance(item, (list, tuple)) and len(item) == 2
    )


_TRANSLATION_MARKERS = ("Translation ", "translation manifest", "/translations/")


def _split_translation_drift(detail: str) -> tuple[str, str]:
    """Separate what a reviser can fix from what a translator must.

    Returned as ``(actionable, advisory)``.  Either may be empty; a gate whose
    every complaint is about an overlay yields no actionable text at all and so
    does not cost the piece a round.
    """

    actionable: list[str] = []
    advisory: list[str] = []
    for line in detail.splitlines():
        target = (
            advisory
            if any(marker in line for marker in _TRANSLATION_MARKERS)
            else actionable
        )
        target.append(line)
    return "\n".join(actionable).strip(), "\n".join(advisory).strip()


def _install(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = text if text.endswith("\n") else text + "\n"
    path.write_text(body, encoding="utf-8")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return text_sha256(_read(path))


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
