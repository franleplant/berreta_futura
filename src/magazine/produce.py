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

**Why the edition-wide gates have a baseline.**  ``validate`` and ``fit`` see
the whole issue, so a stub manuscript three articles away can fail them for
reasons the writer in front of us cannot fix.  Produce therefore measures them
once before any model call and again after every draft, and only a failure that
is *new*, or that names this piece, is fed back to the writer.  Everything else
is reported to the human at the end.  Without this the first piece of a fresh
edition would burn three rounds against somebody else's missing cover art.

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
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from .concurrency import ordered_map
from .errors import MagazineError, ValidationError
from .extraction import Extraction, load_extraction, verify_source_extractions
from .code_blocks import verify_manuscript_code_blocks
from .learning_review import explainer_article_ids, furniture_projection
from .line_review import EDITORIAL_ARTICLE_ID
from .manifest import Edition
from .media_schema import semantic_headings
from .produce_prompts import (
    JUDGE_PROMPTS,
    EditionReviewInput,
    EvidenceReviewInput,
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
    load_prompt,
    parse_verdict,
    split_scratch,
    writer_prompt_path,
)
from .production_record import (
    ModelCall,
    PieceRecord,
    RoundRecord,
    accumulated_findings,
    inputs_fingerprint,
    is_settled,
    load_piece_record,
    piece_record_path,
    text_sha256,
    write_issue_record,
    write_piece_record,
)
from .render_review import REVIEW_RESULTS
from .review_findings import normalize_findings
from .runner import ModelRunner

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


# ---------------------------------------------------------------------------
# Deterministic gates.


@dataclass(frozen=True)
class GateResult:
    name: str
    ok: bool
    detail: str = ""


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
    """The real checks, run through the compiler the CLI already exposes."""

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
        return tuple(results)

    def check_edition(self, edition_id: str) -> tuple[GateResult, ...]:
        return (
            _guarded("validate", lambda: self.magazine.validate(edition_id)),
            _fit_gate(self.magazine, edition_id),
        )


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
    """

    try:
        table, ok = magazine.fit(edition_id, language=magazine.primary_language)
    except MagazineError as error:
        return GateResult("fit", False, str(error))
    return GateResult("fit", ok, "" if ok else table)


def _guarded(name: str, action) -> GateResult:
    try:
        action()
    except ValidationError as error:
        return GateResult(name, False, "\n".join(error.errors))
    except MagazineError as error:
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
            settled = is_settled(
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
                    action="skip: settled" if settled else "draft and judge",
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
        if baseline:
            human_actions.extend(
                f"pre-existing gate failure ({name}): {detail.splitlines()[0]}"
                for name, detail in baseline.items()
            )

        outcomes: list[PieceOutcome] = []
        produced: list[str] = []
        for row in plan.pieces:
            piece = pieces[row.piece_id]
            if row.settled:
                outcomes.append(
                    PieceOutcome(
                        piece_id=piece.id,
                        status="settled",
                        rounds=0,
                        record=str(
                            piece_record_path(
                                self.magazine.editions_dir, edition_id, piece.id
                            )
                        ),
                    )
                )
                continue
            outcome = self._produce_piece(
                edition_id, edition, piece, row, baseline
            )
            outcomes.append(outcome)
            if outcome.status == "passed":
                produced.append(piece.id)
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
        if produced:
            edition = self._load_edition(edition_id)
            issue_reviews = self._judge_issue(edition_id, edition)
            recorded, actions = self._record_bench(
                edition_id, edition, produced, issue_reviews
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
            generated = self.runner.generate(text, cwd=self.root)
            manuscript, notes = split_scratch(generated.text)
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

            failures = self._gate_failures(edition_id, piece, extractions, baseline)
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

            verdicts = self._judge_piece(piece, extractions, manuscript, edition)
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

    # -- judging ----------------------------------------------------------

    def _judge_piece(
        self,
        piece: Piece,
        extractions: Sequence[Extraction],
        manuscript: str,
        edition: Edition,
    ) -> dict[str, "Verdict"]:
        """Run the fact-checker and the line editor over one piece, together.

        They are independent and each costs minutes, so they overlap.
        ``ordered_map`` is the package's one fan-out: results come back in
        input order and the lowest-index failure is the one raised, so the two
        judges cannot make a run's error message depend on thread scheduling.
        """

        evidence_prompt = self._prompt(JUDGE_PROMPTS["evidence"])
        line_prompt = self._prompt(JUDGE_PROMPTS["line"])
        evidence_text = compose_evidence_prompt(
            evidence_prompt,
            EvidenceReviewInput(
                piece_id=piece.id,
                content_mode=piece.content_mode,
                byline=piece.byline,
                manuscript=manuscript,
                extractions=tuple(extractions),
                peer_manuscripts=self._peers(edition, piece),
            ),
        )
        line_text = compose_line_prompt(
            line_prompt,
            LineReviewInput(
                piece_id=piece.id,
                content_mode=piece.content_mode,
                byline=piece.byline,
                max_pages=piece.max_pages,
                manuscript=manuscript,
            ),
        )
        # The type already makes a source impossible to pass; this catches a
        # future edit that smuggles one in through the manuscript or a peer.
        assert_source_withheld(
            line_text, extractions, manuscript=manuscript, label="line editor"
        )
        jobs = (
            ("evidence", evidence_prompt, evidence_text),
            ("line", line_prompt, line_text),
        )
        results = ordered_map(lambda job: self._verdict(*job), jobs, workers=2)
        return {name: verdict for (name, _, _), verdict in zip(jobs, results)}

    def _judge_issue(self, edition_id: str, edition: Edition) -> dict[str, Any]:
        """The learning personas, then the managing editor.

        The manager's two runs are the reason this is not one call.  Run A sees
        the furniture and nothing else; run B is handed A's block and the
        bodies.  A single run cannot un-see the body, and that is precisely the
        run that finds its own takeaways well supported.
        """

        learning_prompt = self._prompt(JUDGE_PROMPTS["learning"])
        furniture = furniture_projection(edition)
        run_a = self.runner.generate(
            compose_manager_run_a(
                learning_prompt,
                ManagerRunAInput(edition_id=edition_id, furniture=furniture),
            ),
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
        learning_verdict = self._verdict(
            "learning",
            learning_prompt,
            compose_learning_prompt(
                learning_prompt,
                LearningReviewInput(
                    edition_id=edition_id,
                    furniture=furniture,
                    manager_takeaways=run_a_block,
                    explainers=explainers,
                    articles=tuple(
                        (article.id, _read(article.manuscript))
                        for article in edition.articles
                    ),
                    extractions=tuple(extractions),
                ),
            ),
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
        edition_verdict = self._verdict(
            "edition",
            edition_prompt,
            compose_edition_prompt(
                edition_prompt,
                EditionReviewInput(
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
                ),
            ),
        )
        write_issue_record(
            self.magazine.editions_dir,
            edition_id,
            "edition",
            {"run": edition_verdict.to_dict()},
        )
        return {"learning": learning_verdict, "edition": edition_verdict}

    def _verdict(self, name: str, prompt: PromptFile, text: str) -> "Verdict":
        generated = self.runner.generate(text, cwd=self.root)
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

    def _gate_failures(
        self,
        edition_id: str,
        piece: Piece,
        extractions: Sequence[Extraction],
        baseline: Mapping[str, str],
    ) -> list[str]:
        """Everything this draft broke, and nothing it merely inherited.

        A per-piece gate is always the writer's problem.  An edition-wide gate
        is the writer's problem only when its complaint is new or names this
        piece: a stub three articles away failing ``validate`` is not something
        a reviser of this piece can clear, and feeding it back would spend the
        round budget on an impossible instruction.
        """

        failures = [
            f"{gate.name}: {gate.detail}"
            for gate in self.gates.check_piece(piece, extractions)
            if not gate.ok
        ]
        for gate in self.gates.check_edition(edition_id):
            if gate.ok:
                continue
            if gate.name in baseline and not _names_piece(gate.detail, piece):
                continue
            actionable, advisory = _split_translation_drift(
                _piece_slice(gate.detail, piece)
            )
            if advisory:
                # Rewriting the English manuscript stales the overlays that pin
                # it, every time, and no reviser can fix that from inside a
                # drafting round.  Reported once, to the human who will run
                # `mag translate`, rather than fed back as an impossible
                # instruction that would spend the round budget.
                self._advisories.add(
                    "language overlays are stale after this rewrite; restage them "
                    f"with `mag translate {edition_id} <language>`: " + advisory
                )
            if actionable:
                failures.append(f"{gate.name}: {actionable}")
        return failures

    # -- recording --------------------------------------------------------

    def _record_bench(
        self,
        edition_id: str,
        edition: Edition,
        produced: Sequence[str],
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
        produced_articles = [item for item in produced if item in article_ids]
        produced_pieces = list(produced)

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
        from .manifest import load_edition
        from .records import load_records

        records = {
            record.id: record for record in load_records(self.magazine.sources_dir)
        }
        return load_edition(
            self.root,
            edition_id,
            set(records),
            publication_name=self.magazine.publication_name,
            source_records=records,
            # Art is not produce's business: it must never generate one, and a
            # missing opener is reported as a human action rather than as a
            # reason the writer cannot draft.
            allow_missing_art=True,
        )

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
        return Piece(
            id=article.id,
            kind="article",
            content_mode=article.content_mode,
            title=article.title,
            byline=article.author,
            manuscript=article.manuscript,
            edition_id=edition.id,
            source_ids=tuple(article.source_ids),
            figure_anchors=tuple(
                (figure.id, figure.anchor) for figure in article.figures
            ),
            max_pages=_page_budget(edition, "max_article_pages", DEFAULT_ARTICLE_PAGES),
            key_ideas=tuple(article.key_ideas),
            has_opener_art=article.opener_art is not None,
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


def _page_budget(edition: Edition, key: str, default: int) -> int:
    fmt = (edition.raw or {}).get("format") or {}
    value = fmt.get(key)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return default


def _names_piece(detail: str, piece: Piece) -> bool:
    return piece.id in detail or str(piece.manuscript) in detail


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


def _piece_slice(detail: str, piece: Piece) -> str:
    """The lines of a multi-error gate report that concern this piece.

    ``validate`` accumulates every complaint in the edition.  Handing all of
    them to a writer who can act on one is how a revision round gets spent
    reading somebody else's problem.
    """

    lines = [line for line in detail.splitlines() if _names_piece(line, piece)]
    return "\n".join(lines) if lines else detail


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
