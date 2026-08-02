"""What each model call is allowed to see, and how that brief is assembled.

``produce.py`` owns the order of the pipeline.  This module owns the far more
dangerous question of *context*: which bytes reach which role.  Every hard-won
rule from the edition-4 pilots is a rule about an input boundary, so the
boundaries live here as types rather than as sentences in a prompt file:

* **One writer call sees the whole extraction.**  :func:`compose_writer_prompt`
  embeds each source's complete body.  Edition 4's duplicated VS Code example
  came from two chunks drafted independently, and the prompts' anti-duplication
  rule cannot detect what a chunked harness makes invisible.  There is no
  chunking function in this module to reach for.

* **A source-blind lens never sees the source.**  ``mechanics``, ``shape`` and
  ``craft`` take :class:`SourceBlindReviewInput`, which has no field that could
  carry an extraction, and their composer accepts nothing else.  Because a
  ``faithful_edit`` manuscript legitimately *is* the source's sentences, a
  content scan alone would be unsound, so :func:`assert_source_withheld` checks
  the only thing that can honestly be checked: no substantial source line that
  the manuscript does not already carry may appear in the prompt.  The type is
  the guarantee; the scan catches a future edit that routes source text in by
  another door.

* **One lens reads one piece.**  No per-piece composer here takes a collection.
  Batching two articles into one judge call would split the attention that
  splitting the bench into seven narrow lenses was meant to concentrate, and
  there is no signature through which a call site could do it.  ``edition`` is
  the single exception and it is the exception on purpose: whether these pieces
  belong between one set of covers is not a question about one piece.

* **A brief is complete on its own.**  Everything a worker needs is in the text
  it is handed, including the rubric, the output contract and -- for ``craft``
  and ``edition``, whose prompts cite it -- the whole of
  :data:`HOUSE_STYLE_PATH` rather than its path.  Under the cooperative backend
  the worker is often a subagent with no repository to open, so a brief that
  refers to a file is a brief that cannot be answered.

* **A finding is an obligation; a suggestion is advice.**  The revision brief
  says so in those words, and nothing in this package ever reads a finding's
  ``suggestion`` to decide whether a revision passed.  Composing N lenses'
  findings into that one document is :mod:`magazine.revision_brief`'s job, not
  this module's; here it is only rendered.

Writers answer in up to three blocks: the manuscript, then an optional
:data:`ANCHOR_MARKER` block saying which heading each registered figure now
sits under, then :data:`SCRATCH_MARKER` and their working notes.
:func:`split_reply` is the only way this package reads a writer's reply, so
neither the notes nor the anchor declaration can reach a manuscript file by
accident, and :func:`compose_writer_prompt` is the only thing that ever puts
the notes back in front of a model.

One more boundary lives here, and it is about time rather than context.
:func:`work_identity` decides when a stored answer is still an answer to the
question it was asked.  It digests the prompt file and the content of the
call and deliberately not the wording of the brief, so that rewording this
module cannot discard a fleet's finished work -- which it once did, for a
whole edition, in one commit.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import MagazineError
from .extraction import Extraction


class ProduceError(MagazineError):
    """A produce run cannot continue, and no partial state should be trusted."""


SCRATCH_MARKER = "<!-- SCRATCH: not part of the manuscript -->"
"""The line that separates a writer's manuscript from its working notes.

Everything below it is the concept graph or claim ladder that produced the
draft.  It is handed to the next round's reviser and to nothing else: not to
the manuscript file, not to a judge, not to the rendered page.
"""

ANCHOR_MARKER = "<!-- FIGURE ANCHORS -->"
"""The line that opens a writer's declaration of where each figure now sits.

A figure is pinned to an exact heading string in ``edition.yaml``, and
rewriting a piece rewrites its headings, so every rewrite used to strand its
figures -- and the pipeline's answer was to tell the writer to keep headings it
had just decided were wrong.  That is backwards: the argument decides the
headings, and the figures follow.  So a writer that renames a heading says
where each figure goes instead, in ``figure-id: heading`` lines under this
marker, and :func:`~magazine.produce.Production._reconcile_anchors` moves the
manifest to match.  The block is optional: a draft that kept every anchored
heading needs no declaration, and one that stranded a figure without declaring
a new home still fails the anchor gate by name.
"""

# Which prompt file drafts which content mode.  ``original_editorial`` is not a
# manifest ``content_mode`` -- the editorial is a path, not an article row --
# but the pipeline treats it as one piece kind among others, and this is the
# table that says so.  A mode absent here has no writer prompt, and produce
# refuses it by name rather than substituting a neighbouring one.
WRITER_PROMPTS: Mapping[str, str] = {
    "original_editorial": "prompts/opening-editorial.md",
    "faithful_edit": "prompts/faithful-edit.md",
    "faithful_synthesis": "prompts/faithful-synthesis.md",
    "in_a_nutshell": "prompts/in-a-nutshell.md",
}

# One prompt file per lens.  The keys are exactly
# ``produce_graph.BENCH_REVIEW_KINDS``, and the suite proves it: a lens declared
# in the graph with no prompt here would be dispatched and then refused at load
# time, halfway through a run, which is the most expensive moment to discover a
# missing file.
JUDGE_PROMPTS: Mapping[str, str] = {
    "worth": "prompts/worth-review.md",
    "evidence": "prompts/evidence-review.md",
    "shape": "prompts/shape-review.md",
    "teaching": "prompts/teaching-review.md",
    "craft": "prompts/craft-review.md",
    "mechanics": "prompts/mechanics-review.md",
    "edition": "prompts/edition-review.md",
}

HOUSE_STYLE_PATH = "docs/WRITING_RULES.md"
"""The corpus ``craft`` and ``edition`` are told to judge against.

Embedded in those two briefs rather than cited by path.  A judge that has to
open a repo file to understand its task has been handed an incomplete brief, and
under the cooperative backend it may have no repo to open: the brief is the
whole of what a worker gets.  Its digest goes into those lenses' work identities
for the same reason a prompt file's does -- rewriting the house style is
rewriting the question.
"""

# A source line has to be this long before its verbatim presence in a line
# editor's prompt is evidence of a leak rather than a coincidence of English.
# Measured on the folded form, which is the form the comparison happens in.
_LEAK_LINE_LENGTH = 40

# Typographic pairs that are the same prose to a reader and different bytes to
# ``in``.  Writers hand back curly quotes for the straight ones a source used
# (and the reverse), and a leak check that called those two different runs of
# text would exempt nothing it should.
_QUOTE_FOLDING = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "´": "'",
        "`": "'",
    }
)


def _fold(text: str) -> str:
    """The form in which two copies of the same prose compare equal.

    Line breaks are the reason this exists.  Extractions arrive hard-wrapped
    from the capture step and manuscripts carry a paragraph on one long line,
    so the *same sentence* is one line in the source and a fragment of a much
    longer line in the manuscript.  Collapsing every run of whitespace to a
    single space makes the comparison indifferent to where either side wrapped;
    NFKC folds non-breaking spaces and ligatures; the quote table folds the
    typography; and case-folding costs nothing at forty characters, where two
    runs that differ only in case are the same prose and not a coincidence.
    """

    folded = unicodedata.normalize("NFKC", text).translate(_QUOTE_FOLDING)
    return " ".join(folded.split()).casefold()


@dataclass(frozen=True)
class PromptFile:
    """One prompt as it sat on disk when a run used it.

    The digest is over the file's bytes, not its text, so a whitespace-only
    revision still changes it.  This is the value an execution record pins:
    edition 4's audit could not answer "which revision of the synthesis prompt
    wrote this piece", and that question is exactly one hash wide.
    """

    path: str
    sha256: str
    text: str


def load_prompt(root: Path, relative: str) -> PromptFile:
    path = root / relative
    if not path.is_file():
        raise ProduceError(
            f"Missing prompt file {relative}; produce composes its briefs from the "
            "committed prompts and will not improvise one"
        )
    raw = path.read_bytes()
    return PromptFile(
        path=relative,
        sha256=hashlib.sha256(raw).hexdigest(),
        text=raw.decode("utf-8"),
    )


def writer_prompt_path(content_mode: str) -> str:
    """The prompt that drafts ``content_mode``, or a refusal naming the gap."""

    try:
        return WRITER_PROMPTS[content_mode]
    except KeyError:
        raise ProduceError(
            f"No writer prompt exists for content_mode {content_mode!r}; produce "
            "can draft "
            + ", ".join(sorted(WRITER_PROMPTS))
            + ". Write this piece by hand, or add its prompt to prompts/."
        ) from None


# ---------------------------------------------------------------------------
# What a call *is*, as opposed to how it is worded.


def work_identity(role: str, payload: Mapping[str, Any]) -> str:
    """Digest the substance of one model call, never its phrasing.

    This is the value a cooperative worker's answer is bound to, and getting
    it wrong is expensive in a way that is easy to miss.  It used to be the
    SHA-256 of the composed brief text, which meant every stored answer in an
    edition was void the moment anyone reworded a heading in this module.
    That is not a theoretical cost: a refactor landed mid-run and a dozen
    completed, judged model calls became unreachable through the front door,
    because a formatting change is indistinguishable from a changed question
    when the only evidence is the rendered bytes.

    So the two are separated.  A call's identity is the *prompt file* it runs
    (by path and digest, so a revised prompt is a different question), the
    piece and round it names, and the content it was handed -- manuscripts,
    findings, notes and source bodies, each by digest.  How this module chose
    to lay that out on the page is provenance: the composed brief is still
    written to disk beside the item, and the execution record still pins the
    prompt digest, but neither the wording of a section heading nor the order
    of two sentences can now discard somebody's finished work.

    What still voids an answer is exactly what should: the manuscript moved,
    a source was recaptured, a judge filed a finding the writer has not seen,
    the prompt file itself was revised.  In each of those the draft on disk
    answers a question nobody is asking any more.
    """

    encoded = json.dumps(
        {"role": role, **dict(payload)},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _digest(text: str | None) -> str | None:
    if text is None:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _body_digests(extractions: Sequence[Extraction]) -> dict[str, str]:
    return {item.source_id: item.body_sha256 for item in extractions}


def _text_digests(pairs: Sequence[tuple[str, str]]) -> dict[str, str | None]:
    return {name: _digest(text) for name, text in pairs}


# ---------------------------------------------------------------------------
# The unit of authorship.


@dataclass(frozen=True)
class FigureSlot:
    """One registered figure and the heading it currently sits under.

    The caption travels with the id because the writer is being asked where
    the figure belongs, and "where does `diagram-2` go" is unanswerable
    without knowing what it shows.
    """

    id: str
    anchor: str
    caption: str = ""

    @property
    def is_opener(self) -> bool:
        return self.anchor == OPENER_ANCHOR


OPENER_ANCHOR = "__opener__"
"""The anchor of a figure that hangs off the piece rather than off a heading.

No rewrite can strand it, so it is never the writer's problem and never the
anchor gate's.
"""


@dataclass(frozen=True)
class Piece:
    """One thing the pipeline drafts and judges, article or editorial.

    ``figures`` is why this dataclass exists at all rather than the pipeline
    passing an ``Article`` around: an anchor is an exact heading string in the
    manuscript, and rewriting the manuscript is precisely what produce does.
    Carrying the figures beside the piece keeps the obligation in front of the
    writer, in front of the gate that checks it, and in front of the
    reconciliation that moves the manifest to match the draft.
    """

    id: str
    kind: str
    content_mode: str
    title: str
    byline: str
    manuscript: Path
    edition_id: str = ""
    source_ids: tuple[str, ...] = ()
    figures: tuple[FigureSlot, ...] = ()
    max_pages: int = 7
    key_ideas: tuple[str, ...] = ()
    has_opener_art: bool = True
    opener_intro_lines: int = 0
    opener_intro_safe_characters: int = 0
    """The illustrated opener's opening-paragraph budget, measured.

    Zero ``opener_intro_lines`` means the piece has no illustrated opener and
    no such constraint.  Non-zero is the hard limit the build enforces:
    see :func:`~magazine.weasyprint_adapter.illustrated_opener_intro_budget`.

    ``opener_intro_safe_characters`` is a length a writer can count towards
    while drafting, deliberately *below* the line limit rather than at it, and
    zero when there was no prose sample to derive it from.  It is not a second
    rule and must never be briefed as one: the line count is what the gate
    reads, and a paragraph over the character floor may still be perfectly
    legal.  The floor exists because the figure that used to sit here was the
    other kind of wrong -- an optimistic estimate a writer could stay under and
    still overrun.
    """

    @property
    def anchored_figures(self) -> tuple[FigureSlot, ...]:
        """The figures a rewrite can strand: everything but the opener."""

        return tuple(figure for figure in self.figures if not figure.is_opener)

    @property
    def figure_anchors(self) -> tuple[tuple[str, str], ...]:
        """Every figure as ``(id, anchor)``, opener included."""

        return tuple((figure.id, figure.anchor) for figure in self.figures)

    @property
    def anchors(self) -> tuple[str, ...]:
        """Every heading a figure is pinned to, ``__opener__`` excluded."""

        return tuple(figure.anchor for figure in self.anchored_figures)


# ---------------------------------------------------------------------------
# Writer briefs.


@dataclass(frozen=True)
class WriterBrief:
    """Everything one drafting call gets, including its predecessor's mind.

    ``previous_notes`` is the whole reason a revision round is worth more than
    a re-draft.  A finding names where a contradiction *surfaces*; the notes
    say where the argument was built, which is where it can actually be
    repaired.  The pilot reviser found the real cause only because the
    predecessor's concept graph survived, so the notes travel with the
    findings, always, and losing them is a bug rather than an economy.
    """

    piece: Piece
    edition_id: str
    edition_title: str
    extractions: tuple[Extraction, ...] = ()
    round_number: int = 1
    previous_manuscript: str | None = None
    previous_notes: str | None = None
    findings: tuple[Mapping[str, Any], ...] = ()
    gate_failures: tuple[str, ...] = ()
    peer_manuscripts: tuple[tuple[str, str], ...] = ()


def writer_identity(prompt: PromptFile, brief: WriterBrief) -> str:
    """Everything a drafting call is a function of, and nothing about layout.

    The figures appear by id and caption but *not* by anchor, because the
    brief no longer tells the writer where a figure currently sits: the
    argument decides the headings and the writer declares where the figures
    land.  Folding the anchor in here would mean that reconciling the manifest
    to a draft voided the very reply that produced it, and the loop would
    re-emit the same brief for ever.
    """

    piece = brief.piece
    return work_identity(
        "writer",
        {
            "prompt_path": prompt.path,
            "prompt_sha256": prompt.sha256,
            "piece": piece.id,
            "content_mode": piece.content_mode,
            "round": brief.round_number,
            "edition": brief.edition_id,
            "title": piece.title,
            "byline": piece.byline,
            "max_pages": piece.max_pages,
            "key_ideas": list(piece.key_ideas),
            "figures": [
                [figure.id, figure.caption] for figure in piece.anchored_figures
            ],
            "extractions": _body_digests(brief.extractions),
            "peers": _text_digests(brief.peer_manuscripts),
            "previous_manuscript": _digest(brief.previous_manuscript),
            "previous_notes": _digest(brief.previous_notes),
            "findings": [dict(finding) for finding in brief.findings],
            "gate_failures": list(brief.gate_failures),
        },
    )


def compose_writer_prompt(prompt: PromptFile, brief: WriterBrief) -> str:
    """Assemble one drafting call: the prompt file, then the whole assignment.

    Every source body goes in complete and in one call.  There is no branch
    here that splits a long extraction, and adding one would reintroduce the
    duplication the anti-duplication rules cannot see.
    """

    piece = brief.piece
    parts: list[str] = [prompt.text.rstrip(), "", "---", ""]
    parts.append("# The assignment")
    parts.append("")
    parts.append(
        "The prompt above governs. This section names the piece, supplies its "
        "complete inputs, and states the output contract."
    )
    parts.append("")
    parts.append(f"- Edition: `{brief.edition_id}` ({brief.edition_title})")
    parts.append(f"- Piece id: `{piece.id}`")
    parts.append(f"- content_mode: `{piece.content_mode}`")
    if piece.title:
        parts.append(f"- Title: {piece.title}")
    if piece.byline:
        parts.append(f"- Byline: {piece.byline}")
    parts.append(f"- Page budget: {piece.max_pages} rendered A5 reader page(s)")
    if piece.opener_intro_lines:
        floor = (
            f"; write to about {piece.opener_intro_safe_characters} characters "
            "and you are safe"
            if piece.opener_intro_safe_characters
            else ""
        )
        parts.append(
            f"- Opening paragraph budget: {piece.opener_intro_lines} typeset "
            f"line(s){floor}"
        )
    if piece.key_ideas:
        parts.append("- Key ideas box (editor furniture, do not restate verbatim):")
        parts.extend(f"  - {line}" for line in piece.key_ideas)
    parts.append("")

    if piece.opener_intro_lines:
        parts.append("")
        parts.append("## The opening paragraph has a hard length limit")
        parts.append("")
        parts.append(
            "This piece opens on an illustrated page that sets the art, the "
            "label, the title, the credit block and your first paragraph "
            f"together. The paragraph gets what is left: {piece.opener_intro_lines} "
            "typeset line(s), measured for this article's own title and byline "
            "rather than as a rule of thumb. That line count is the whole "
            "limit and the only thing checked. A first paragraph over it does "
            "not wrap to the next page: the build refuses the edition, and the "
            "piece costs a round. Write a shorter opening paragraph and put "
            "the rest in the second one."
        )
        parts.append("")
        if piece.opener_intro_safe_characters:
            parts.append(
                "Lines are hard to feel while drafting, so here is a length to "
                f"aim at: {piece.opener_intro_safe_characters} characters. That "
                "is a floor, not the limit -- it is set low enough that prose "
                "of this length has always fitted, so under it you need not "
                "think about the constraint again. It is not a second rule, "
                "and going over it is not a failure; it only means the line "
                "count is no longer guaranteed and is worth checking. Do not "
                "count characters to decide whether something fits."
            )
            parts.append("")
        parts.append(
            "To check a candidate paragraph exactly, without a build and "
            "without a model call, pipe it to the gate's own arithmetic:"
        )
        parts.append("")
        parts.append(
            "```\n"
            "printf '%s' \"<your opening paragraph>\" | \\\n"
            f"  uv run --locked mag fit {brief.edition_id} --opener {piece.id}\n"
            "```"
        )
        parts.append("")
        parts.append(
            "It prints the line count it would set as, and the lines "
            "themselves so you can see which one overflowed. Use it rather "
            "than reproducing the wrapping by hand."
        )
        parts.append("")

    if piece.anchored_figures:
        parts.append("## Figures this piece has to leave a place for")
        parts.append("")
        parts.append(
            "`edition.yaml` pins each of these registered figures to one exact "
            "`##` heading, and the renderer refuses an anchor that does not "
            "match exactly one heading in the manuscript. The figures are "
            "fixed; the headings are yours. Write the piece the argument "
            "wants, then say where each figure sits."
        )
        parts.append("")
        for figure in piece.anchored_figures:
            caption = f" -- {figure.caption}" if figure.caption else ""
            parts.append(f"- `{figure.id}`{caption}")
        parts.append("")
        parts.append(
            "After the manuscript, emit a line containing exactly "
            f"`{ANCHOR_MARKER}` and then one `figure-id: heading` line for "
            "every figure above, naming a `##` heading your draft actually "
            "carries, spelled character for character. The manifest is moved "
            "to match. Omit the block only if you are certain every figure's "
            "current heading survived your draft unchanged; a figure left "
            "with nowhere to sit fails a deterministic gate and costs the "
            "piece a round."
        )
        parts.append("")

    if brief.extractions:
        parts.append("## Source extractions")
        parts.append("")
        parts.append(
            f"{len(brief.extractions)} extraction(s), each complete. You are "
            "drafting the whole piece in this one pass from all of it: nothing "
            "else will be sent, and no later call will stitch a second half on."
        )
        parts.append("")
        for extraction in brief.extractions:
            body = extraction.body
            parts.append(
                f"### Extraction `{extraction.source_id}` "
                f"({len(body.splitlines())} lines, complete)"
            )
            parts.append("")
            parts.append(_fence(body))
            parts.append("")

    if brief.peer_manuscripts:
        parts.append("## The edition's pieces, in running order")
        parts.append("")
        parts.append(
            "The editorial is grounded in these and in nothing else. Do not "
            "introduce them one by one: a tour is the failure this piece exists "
            "to avoid."
        )
        parts.append("")
        for peer_id, text in brief.peer_manuscripts:
            parts.append(f"### `{peer_id}`")
            parts.append("")
            parts.append(_fence(text))
            parts.append("")

    # Round one is normally a fresh draft, but a finding filed from outside the
    # loop makes it a revision: there is a manuscript on disk, somebody has
    # said what is wrong with it, and a writer handed the complaint without the
    # text would rebuild from nothing and lose everything the piece got right.
    if brief.round_number > 1 or brief.findings or brief.gate_failures:
        parts.extend(_revision_block(brief))

    parts.append("## Output contract")
    parts.append("")
    parts.append(
        "Return the complete manuscript first: the frontmatter the prompt "
        "specifies, then the body, and nothing before it."
    )
    parts.append("")
    if piece.anchored_figures:
        parts.append(
            "Then, where your draft renamed any heading a figure is pinned to, "
            "a line containing exactly:"
        )
        parts.append("")
        parts.append(f"    {ANCHOR_MARKER}")
        parts.append("")
        parts.append(
            "and one `figure-id: heading` line per figure. Then a line "
            "containing exactly:"
        )
    else:
        parts.append("Then a line containing exactly:")
    parts.append("")
    parts.append(f"    {SCRATCH_MARKER}")
    parts.append("")
    parts.append(
        "Then your working notes for that draft: the concept graph or claim "
        "ladder you built the piece from, what you cut and why, and anything a "
        "later reviser would otherwise have to reconstruct. Everything below "
        "the marker is stripped before the manuscript is written and is never "
        "shown to a judge, so write it for the next writer, not for a reader. "
        "Return no other commentary, and do not wrap the manuscript in a code "
        "fence."
    )
    parts.append("")
    return "\n".join(parts)


def _revision_block(brief: WriterBrief) -> list[str]:
    opening = (
        "A previous round of this piece was judged and did not pass."
        if brief.round_number > 1
        else "This piece has already been drafted, and a defect has been filed "
        "against the draft on disk."
    )
    parts: list[str] = [
        f"## Round {brief.round_number}: revise the draft below",
        "",
        opening + " Your job is to produce the whole manuscript again, with "
        "every defect below gone. Rewrite as much as the repair needs; you are "
        "not patching sentences.",
        "",
    ]
    if brief.previous_notes:
        parts.extend(
            [
                "### Your predecessor's working notes",
                "",
                "These are the notes from the draft below, not a judgment of "
                "it. A finding says where a defect *surfaces*; these notes are "
                "usually the only way to see where it was *made*. Read them "
                "before the findings.",
                "",
                _fence(brief.previous_notes),
                "",
            ]
        )
    if brief.previous_manuscript:
        parts.extend(
            [
                "### The draft under revision",
                "",
                _fence(brief.previous_manuscript),
                "",
            ]
        )
    if brief.gate_failures:
        parts.extend(
            [
                "### Deterministic checks the draft failed",
                "",
                "These are machine checks, not opinions. Each one is exact and "
                "must pass.",
                "",
            ]
        )
        parts.extend(f"- {failure}" for failure in brief.gate_failures)
        parts.append("")
    if brief.findings:
        parts.extend(
            [
                "## Findings",
                "",
                "Seven narrow lenses read this piece; what follows is their "
                "findings composed into one worklist. Scores are not shown to "
                "you, deliberately: they are advisory telemetry, the edition "
                "this bench was built to catch scored fives across it, and a "
                "number you can see is a number you can optimise.",
                "",
            ]
        )
        parts.extend(_composed_findings(brief))
    return parts


def _composed_findings(brief: WriterBrief) -> list[str]:
    """The revision brief, composed by the one module that knows the rules.

    The findings arrive here flat, each tagged with the lens that filed it,
    because that is the shape a production record stores and the shape a filed
    finding arrives in from outside the loop.  Regrouping is cheap; the
    ordering, merging, conflict detection and the three labelled sections are
    not, and they are :mod:`magazine.revision_brief`'s, so that the rules
    ``prompts/README.md`` states live in one testable place rather than inside a
    prompt-formatting helper.

    A finding whose ``judge`` is not one of the seven lenses is one a human
    filed by hand with ``mag finding file``, and its tag is whoever filed it.
    It sorts into the last repair tier, where an obligation nobody can place is
    least likely to send a writer to do work that a structural finding above it
    is about to discard -- but it still *prints* under the name it was filed
    under, because "from the edition review" and "from the craft lens" mean
    different things to a reviser and the tier is not an attribution.  See
    :attr:`~magazine.revision_brief.BriefEntry.filed_by`.
    """

    from .produce_graph import PIECE_JUDGE_KINDS
    from .revision_brief import compose

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for finding in brief.findings:
        lens = str(finding.get("judge") or "").strip()
        if lens not in PIECE_JUDGE_KINDS:
            lens = PIECE_JUDGE_KINDS[-1]
        grouped.setdefault(lens, []).append(finding)
    composed = compose(
        brief.piece.id,
        [(kind, grouped[kind]) for kind in PIECE_JUDGE_KINDS if kind in grouped],
        manuscript=brief.previous_manuscript or "",
    )
    lines = composed.render()
    if lines:
        lines.append("")
    return lines


def split_reply(reply: str) -> tuple[str, dict[str, str], str]:
    """Split a writer's reply into manuscript, figure anchors, working notes.

    The reply is at most three blocks in a fixed order: the manuscript, then
    the optional anchor declaration under :data:`ANCHOR_MARKER`, then the
    optional working notes under :data:`SCRATCH_MARKER`.  Either marker may be
    indented or surrounded by blank lines, and either may be absent -- a reply
    with neither is all manuscript, which is a legal (if unhelpful) answer.

    An anchor marker that appears *below* the scratch marker is notes, not a
    declaration: everything under the scratch marker is the writer talking to
    the next writer, and a pipeline that reached into that text to move a
    figure would be acting on a thought rather than on a statement.
    """

    lines = reply.splitlines()
    anchor_at = _marker_line(lines, ANCHOR_MARKER)
    scratch_at = _marker_line(lines, SCRATCH_MARKER)
    if anchor_at is not None and scratch_at is not None and anchor_at > scratch_at:
        anchor_at = None
    body_end = len(lines) if scratch_at is None else scratch_at
    manuscript_end = body_end if anchor_at is None else anchor_at
    manuscript = _strip_fence("\n".join(lines[:manuscript_end]).rstrip())
    anchors = (
        {} if anchor_at is None else _parse_anchor_lines(lines[anchor_at + 1 : body_end])
    )
    notes = "" if scratch_at is None else "\n".join(lines[scratch_at + 1 :]).strip()
    return manuscript, anchors, notes


def split_scratch(reply: str) -> tuple[str, str]:
    """The manuscript and the working notes, for callers with no figures.

    A thin reading of :func:`split_reply`, kept because the two contract checks
    the agent backend makes on a reply -- that a manuscript survives the split,
    and that only one scratch marker does -- care about the manuscript boundary
    and nothing else.
    """

    manuscript, _, notes = split_reply(reply)
    return manuscript, notes


def _marker_line(lines: Sequence[str], marker: str) -> int | None:
    return next(
        (index for index, line in enumerate(lines) if line.strip() == marker), None
    )


def _parse_anchor_lines(lines: Sequence[str]) -> dict[str, str]:
    """Read ``figure-id: heading`` lines as forgivingly as is still unambiguous.

    Models reliably decorate a list: a leading dash, backticks around the id,
    a ``##`` in front of the heading, the whole thing in a fence.  None of
    those change what was said, so all of them are stripped.  A line with no
    colon says nothing this can act on and is dropped rather than guessed at:
    the anchor gate still has the last word, so a dropped line costs a named
    gate failure rather than a figure quietly moved to the wrong place.
    """

    declared: dict[str, str] = {}
    for line in lines:
        text = line.strip()
        if not text or text.startswith("```"):
            continue
        if text.startswith("- ") or text.startswith("* "):
            text = text[2:].strip()
        figure_id, separator, heading = text.partition(":")
        if not separator:
            continue
        figure_id = figure_id.strip().strip("`").strip()
        heading = heading.strip().strip("`").strip()
        if heading.startswith("## "):
            heading = heading[3:].strip()
        if figure_id and heading:
            declared[figure_id] = heading
    return declared


def contains_scratch(text: str) -> bool:
    """Whether any line of ``text`` is the scratch marker."""

    return any(line.strip() == SCRATCH_MARKER for line in text.splitlines())


# ---------------------------------------------------------------------------
# Judge briefs: one lens, one piece, and exactly the inputs its contract names.
#
# Three properties hold across every composer below, and each one is a property
# of the *types* rather than of the prompt text, because a rule a harness can
# violate is a rule that eventually gets violated.
#
# **One lens, one piece.**  No per-piece composer takes a collection of pieces.
# There is no signature here through which two articles could reach one judge
# call, so the attention-splitting that made the old broad judge miss twelve
# lowercase sentence openings cannot be reintroduced by a call site.
#
# **A source-blind lens cannot be handed a source.**  ``mechanics``, ``shape``
# and ``craft`` take :class:`SourceBlindReviewInput`, which has no field that
# could hold an extraction, and their composers accept nothing else.  The prompt
# files also say "you do not open the source", and that sentence is not what is
# relied on.  :func:`assert_source_withheld` is the second line: it catches a
# future edit that routes source text in through the manuscript or some other
# door the type system did not close.
#
# **A brief is self-contained.**  Everything a worker needs arrives in the text,
# including the rubric and the output contract -- and, for the two lenses whose
# prompts cite it, the whole house-style corpus rather than its path.  Under the
# cooperative backend the worker may be a subagent with no repository; a brief
# that says "see docs/WRITING_RULES.md" is a brief that cannot be answered.


@dataclass(frozen=True)
class SourceBlindReviewInput:
    """What a lens that may not see the source reads.  Note what is not here.

    There is no source field, and there is no way to add one from a call site:
    :func:`compose_source_blind_prompt` takes this type and nothing else.

    Three lenses share it -- ``mechanics``, ``shape`` and ``craft`` -- and they
    share it precisely because their input contract is identical: the piece as
    it stands, body and furniture, with its ``content_mode`` and byline.  Giving
    each of them a private near-identical dataclass would have been three places
    for a future edit to add an ``extractions`` field to one of them, and one
    type with no such field is a stronger guarantee than three types that
    currently happen not to have one.

    The blindness is not squeamishness.  ``prompts/README.md`` states it as an
    assignment constraint: a judge who can see the source starts fact-checking
    and stops reading for flow, so every check answerable from the manuscript
    alone belongs to a lens that reads only the manuscript.  The corollary bit
    the old bench -- ``line-review.md`` was forbidden the source *and* asked
    whether the headings mirrored the source's table of contents, and it duly
    answered a question it could not see, wrongly.  That check now lives on
    ``worth``, which reads both.
    """

    piece_id: str
    content_mode: str
    byline: str
    max_pages: int
    manuscript: str


@dataclass(frozen=True)
class WorthReviewInput:
    """What ``worth`` reads: one manuscript and its complete sources.

    The only lens whose question is explicitly a ratio -- what does our version
    give a reader that the original does not -- so it needs both sides in full.
    It never runs on the editorial, which has no source of its own.
    """

    piece_id: str
    content_mode: str
    byline: str
    title: str
    manuscript: str
    extractions: tuple[Extraction, ...] = ()


@dataclass(frozen=True)
class EvidenceReviewInput:
    """What the fact-checker reads: the manuscript and its complete sources.

    ``peer_manuscripts`` is not a second piece being batched into this call.
    ``prompts/evidence-review.md`` says it in as many words: *for the editorial
    the sources are the edition's own article manuscripts*, because every
    factual claim in an editorial must be supported by a piece in this issue.
    So for the editorial, and only for the editorial, the peers *are* the
    extraction -- there is no other truth to check it against.  Every other
    piece is composed with this field empty, and :meth:`Production._peers`
    returns nothing for them.
    """

    piece_id: str
    content_mode: str
    byline: str
    manuscript: str
    extractions: tuple[Extraction, ...] = ()
    peer_manuscripts: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class TeachingReviewInput:
    """What the explainer's reader reads: the piece, its furniture, its source.

    The source is here because ``prompts/teaching-review.md`` opens the book at
    step 1 and step 5 and closes it in between: the six questions are written
    *from the source*, and an answer the reader knows from the source but the
    piece does not carry is a failed question.  A lens that could not see the
    source could only ask questions the piece had already answered, which
    measures nothing.

    ``furniture`` is the editor-authored projection -- deck, key ideas box,
    diagram captions -- which this reader judges as hard as the body.
    """

    piece_id: str
    content_mode: str
    byline: str
    manuscript: str
    furniture: Mapping[str, Any] = field(default_factory=dict)
    extractions: tuple[Extraction, ...] = ()


@dataclass(frozen=True)
class EditionReviewInput:
    """The managing editor's brief: the issue, never its sources.

    The one lens that sees more than one piece, and the only one that may: its
    whole subject is whether these pieces belong between one set of covers.
    """

    edition_id: str
    manifest: Mapping[str, Any]
    editorial: str | None
    articles: tuple[tuple[str, str, str], ...] = field(default=())
    house_style: str = ""


# ---------------------------------------------------------------------------
# What each of those calls *is*, for the purpose of reusing a stored answer.


def source_blind_identity(
    role: str, prompt: PromptFile, item: SourceBlindReviewInput
) -> str:
    return work_identity(
        role,
        {
            "prompt_path": prompt.path,
            "prompt_sha256": prompt.sha256,
            "piece": item.piece_id,
            "content_mode": item.content_mode,
            "byline": item.byline,
            "max_pages": item.max_pages,
            "manuscript": _digest(item.manuscript),
        },
    )


def craft_identity(
    prompt: PromptFile, item: SourceBlindReviewInput, *, house_style: str
) -> str:
    """``craft``'s identity, which folds in the corpus it judges against.

    The one source-blind lens whose brief carries something besides the
    manuscript.  Rewriting ``docs/WRITING_RULES.md`` changes what "did a person
    write this" means, so a stored craft answer written against the old corpus
    is an answer to a question nobody is asking any more -- exactly the case a
    prompt-file digest already covers for every other lens.
    """

    return work_identity(
        "craft",
        {
            "prompt_path": prompt.path,
            "prompt_sha256": prompt.sha256,
            "piece": item.piece_id,
            "content_mode": item.content_mode,
            "byline": item.byline,
            "max_pages": item.max_pages,
            "manuscript": _digest(item.manuscript),
            "house_style": _digest(house_style),
        },
    )


def worth_identity(prompt: PromptFile, item: WorthReviewInput) -> str:
    return work_identity(
        "worth",
        {
            "prompt_path": prompt.path,
            "prompt_sha256": prompt.sha256,
            "piece": item.piece_id,
            "content_mode": item.content_mode,
            "byline": item.byline,
            "title": item.title,
            "manuscript": _digest(item.manuscript),
            "extractions": _body_digests(item.extractions),
        },
    )


def evidence_identity(prompt: PromptFile, item: EvidenceReviewInput) -> str:
    return work_identity(
        "evidence",
        {
            "prompt_path": prompt.path,
            "prompt_sha256": prompt.sha256,
            "piece": item.piece_id,
            "content_mode": item.content_mode,
            "byline": item.byline,
            "manuscript": _digest(item.manuscript),
            "extractions": _body_digests(item.extractions),
            "peers": _text_digests(item.peer_manuscripts),
        },
    )


def teaching_identity(prompt: PromptFile, item: TeachingReviewInput) -> str:
    return work_identity(
        "teaching",
        {
            "prompt_path": prompt.path,
            "prompt_sha256": prompt.sha256,
            "piece": item.piece_id,
            "content_mode": item.content_mode,
            "byline": item.byline,
            "manuscript": _digest(item.manuscript),
            "furniture": _digest(_yaml_block(item.furniture)),
            "extractions": _body_digests(item.extractions),
        },
    )


def edition_identity(prompt: PromptFile, item: EditionReviewInput) -> str:
    return work_identity(
        "edition",
        {
            "prompt_path": prompt.path,
            "prompt_sha256": prompt.sha256,
            "edition": item.edition_id,
            "manifest": _digest(_yaml_block(item.manifest)),
            "editorial": _digest(item.editorial),
            "house_style": _digest(item.house_style),
            "articles": {
                article_id: [content_mode, _digest(text)]
                for article_id, content_mode, text in item.articles
            },
        },
    )


# ---------------------------------------------------------------------------
# Composing each one.


def _piece_header(
    *,
    piece_id: str,
    content_mode: str,
    byline: str,
    title: str = "",
    max_pages: int = 0,
) -> list[str]:
    """The one piece this call is about, named the same way for every lens.

    One function so that a reader comparing two lenses' briefs is comparing
    their *content* rather than two spellings of the same header, and so that
    "which piece is this" cannot become a list by accident.
    """

    parts = [f"- Article id: `{piece_id}`"]
    parts.append(f"- content_mode: `{content_mode}`")
    if title:
        parts.append(f"- Title: {title}")
    if byline:
        parts.append(f"- Byline: {byline}")
    if max_pages:
        parts.append(f"- Page budget: {max_pages} rendered A5 reader page(s)")
    parts.append("")
    return parts


def compose_source_blind_prompt(
    prompt: PromptFile,
    item: SourceBlindReviewInput,
    *,
    kind: str,
    house_style: str = "",
) -> str:
    """Assemble one blind lens's brief from a manuscript and nothing else.

    ``house_style`` is the only thing that may join the manuscript here, and
    only ``craft`` passes it: ``prompts/craft-review.md`` names the corpus as an
    input and a worker cannot be assumed to have the repository.  It is prose
    about how to write, not text from the piece's source, so it does not breach
    the blindness -- and :func:`assert_source_withheld` still checks the whole
    composed brief afterwards, corpus included, in case it ever quotes one.
    """

    parts = [prompt.text.rstrip(), "", "---", "", "# The piece under review", ""]
    parts.extend(
        _piece_header(
            piece_id=item.piece_id,
            content_mode=item.content_mode,
            byline=item.byline,
            max_pages=item.max_pages,
        )
    )
    parts.append(
        "The source extraction is deliberately withheld and is not available to "
        "you by any route. Every question this lens asks is answerable from the "
        "manuscript alone; anything that would need the source belongs to "
        "`worth` or `evidence`, which read both. Do not speculate about the "
        "relationship between this piece and whatever it was written from."
    )
    parts.append("")
    parts.append("## Manuscript")
    parts.append("")
    parts.append(_fence(item.manuscript))
    parts.append("")
    if house_style:
        parts.append("## The house style corpus (`docs/WRITING_RULES.md`), in full")
        parts.append("")
        parts.append(
            "Reproduced here so this brief is complete on its own. Judge "
            "against it; do not go looking for it."
        )
        parts.append("")
        parts.append(_fence(house_style))
        parts.append("")
    parts.append(_yaml_only_contract(kind))
    return "\n".join(parts)


def compose_worth_prompt(prompt: PromptFile, item: WorthReviewInput) -> str:
    parts = [prompt.text.rstrip(), "", "---", ""]
    parts.append("# The article under review")
    parts.append("")
    parts.extend(
        _piece_header(
            piece_id=item.piece_id,
            content_mode=item.content_mode,
            byline=item.byline,
            title=item.title,
        )
    )
    parts.append("## Manuscript")
    parts.append("")
    parts.append(_fence(item.manuscript))
    parts.append("")
    for extraction in item.extractions:
        parts.append(f"## Pinned extraction `{extraction.source_id}` (complete)")
        parts.append("")
        parts.append(_fence(extraction.body))
        parts.append("")
    parts.append(_yaml_only_contract("worth"))
    return "\n".join(parts)


def compose_evidence_prompt(prompt: PromptFile, item: EvidenceReviewInput) -> str:
    parts = [prompt.text.rstrip(), "", "---", "", "# The piece under audit", ""]
    parts.append(f"- Article id: `{item.piece_id}`")
    parts.append(f"- content_mode: `{item.content_mode}`")
    if item.byline:
        parts.append(f"- Byline: {item.byline}")
    parts.append("")
    parts.append("## Manuscript")
    parts.append("")
    parts.append(_fence(item.manuscript))
    parts.append("")
    for extraction in item.extractions:
        parts.append(f"## Pinned extraction `{extraction.source_id}` (complete)")
        parts.append("")
        parts.append(_fence(extraction.body))
        parts.append("")
    if item.peer_manuscripts:
        parts.append("## This piece's sources: the edition's own articles")
        parts.append("")
        parts.append(
            "The editorial declares no source of its own, so these are its "
            "sources. Every factual claim in the manuscript above must be "
            "supported by one of them, and a claim that is not is a finding."
        )
        parts.append("")
        for peer_id, text in item.peer_manuscripts:
            parts.append(f"### `{peer_id}`")
            parts.append("")
            parts.append(_fence(text))
            parts.append("")
    parts.append(_yaml_only_contract("evidence"))
    return "\n".join(parts)


def compose_teaching_prompt(prompt: PromptFile, item: TeachingReviewInput) -> str:
    parts = [prompt.text.rstrip(), "", "---", "", "# The explainer under review", ""]
    parts.append(f"- Article id: `{item.piece_id}`")
    parts.append(f"- content_mode: `{item.content_mode}`")
    if item.byline:
        parts.append(f"- Byline: {item.byline}")
    parts.append("")
    parts.append("## The editor-authored furniture, in full")
    parts.append("")
    parts.append(
        "Judge only the furniture that exists. Absent furniture is one "
        "`missing_furniture` finding listing everything missing, never one per "
        "item."
    )
    parts.append("")
    parts.append(_fence(_yaml_block(item.furniture)))
    parts.append("")
    parts.append("## The explainer")
    parts.append("")
    parts.append(_fence(item.manuscript))
    parts.append("")
    for extraction in item.extractions:
        parts.append(f"## Pinned extraction `{extraction.source_id}` (complete)")
        parts.append("")
        parts.append(
            "For step 1 and step 5 only. Write your six questions from this, "
            "then close it and answer them from the explainer alone."
        )
        parts.append("")
        parts.append(_fence(extraction.body))
        parts.append("")
    parts.append(_yaml_only_contract("teaching"))
    return "\n".join(parts)


def compose_edition_prompt(prompt: PromptFile, item: EditionReviewInput) -> str:
    parts = [prompt.text.rstrip(), "", "---", "", "# The issue", ""]
    parts.append(f"Edition: `{item.edition_id}`")
    parts.append("")
    parts.append("## edition.yaml furniture")
    parts.append("")
    parts.append(_fence(_yaml_block(item.manifest)))
    parts.append("")
    if item.editorial is not None:
        parts.append("## The opening editorial")
        parts.append("")
        parts.append(_fence(item.editorial))
        parts.append("")
    parts.append("## The pieces, in running order")
    parts.append("")
    for article_id, content_mode, text in item.articles:
        parts.append(f"### `{article_id}` (`{content_mode}`)")
        parts.append("")
        parts.append(_fence(text))
        parts.append("")
    if item.house_style:
        parts.append("## The house style corpus (`docs/WRITING_RULES.md`), in full")
        parts.append("")
        parts.append(
            "Reproduced here so this brief is complete on its own. The swap "
            "test and the voice question are judged against it."
        )
        parts.append("")
        parts.append(_fence(item.house_style))
        parts.append("")
    parts.append(_yaml_only_contract("edition"))
    return "\n".join(parts)


def assert_source_withheld(
    prompt: str,
    extractions: Sequence[Extraction],
    *,
    manuscript: str,
    label: str,
) -> None:
    """Refuse a brief that leaks source text the manuscript does not carry.

    The second line of the source-blindness guarantee.  The first is the type:
    :class:`SourceBlindReviewInput` has no field an extraction could arrive in.
    This catches the case the type cannot -- a future edit that routes source
    text in through the manuscript, a peer, or a corpus that quotes one.

    The check cannot simply look for source sentences: a ``faithful_edit``
    manuscript *is* the source's sentences, and the manuscript is legitimately
    in this prompt.  So the exempt set is the prose the manuscript itself
    carries, and any other substantial run of source prose found in the prompt
    is a leak by a route the type system did not close.

    Both sides are compared through :func:`_fold`, and the manuscript is
    compared as one folded body rather than as a set of lines.  A source line is
    a wrap fragment, not a unit of meaning: the same sentence sits alone on a
    source line and mid-paragraph in a manuscript, so line-for-line equality
    exempted nothing real and every faithful piece tripped its own guard.
    Folding cuts both ways -- a leak that re-wrapped or re-quoted the source no
    longer slips past either.
    """

    folded_prompt = _fold(prompt)
    folded_manuscript = _fold(manuscript)
    for extraction in extractions:
        for line in extraction.body.splitlines():
            candidate = _fold(line)
            if len(candidate) < _LEAK_LINE_LENGTH:
                continue
            if candidate in folded_manuscript:
                continue
            if candidate in folded_prompt:
                raise ProduceError(
                    f"{label} brief carries source text from "
                    f"{extraction.source_id} that the manuscript does not: "
                    f"{line.strip()[:60]!r}. This lens is forbidden the source."
                )


# ---------------------------------------------------------------------------
# Reading a judge's answer.


def parse_verdict(text: str, *, label: str) -> dict[str, Any]:
    """Read the one YAML document a judge prompt promises to return.

    Models fence their YAML about as often as they do not, so a single fenced
    block is unwrapped rather than refused.  Anything else that is not a
    mapping is an error naming the judge: a verdict that cannot be parsed must
    never be silently read as "no findings".
    """

    document = _strip_fence(text.strip())
    try:
        data = yaml.safe_load(document)
    except yaml.YAMLError as error:
        raise ProduceError(
            f"The {label} did not return parseable YAML: {error}"
        ) from error
    if not isinstance(data, Mapping):
        raise ProduceError(
            f"The {label} returned {type(data).__name__}, not the one YAML "
            "mapping its prompt requires"
        )
    return dict(data)


def _yaml_only_contract(kind: str) -> str:
    """The four keys every lens returns, and the one field that is new.

    One parser serves all seven lenses, which is why the key set is identical
    and why no kind gets a block of its own any more -- the retired ``learning``
    kind carried two, and a per-kind block is a second parser by another name.

    ``disposition`` is restated here rather than left to the prompt file
    because it is the field that replaced the severity cap and the recorder
    refuses a structured finding without it.  A worker that omitted it would
    have its whole reply rejected after the call was paid for, and the sentence
    that prevents that is cheaper than the call.
    """

    return (
        "## Output contract\n\n"
        "Return one YAML document and nothing else, in exactly the shape the "
        f"{kind} review prompt above specifies. No preamble, no commentary "
        "after it. The document may carry only `result`, `findings`, `scores` "
        "and `notes`: any other key is refused by the recorder.\n\n"
        "Every finding must carry `disposition`, and it is either `fix` (the "
        "writer resolves it) or `editor_decision` (a human chooses the remedy, "
        "because the text is the source author's own in an author-voiced mode "
        "and `docs/EDITORIAL_POLICY.md` makes changing its wording "
        "review-required). Severity describes the defect; disposition says who "
        "repairs it. Never soften or drop a finding because it is the author's: "
        "file it at its true severity and route it. A finding without a "
        "disposition is refused.\n"
    )


def _yaml_block(value: Any) -> str:
    return yaml.safe_dump(
        json.loads(json.dumps(value, ensure_ascii=False)),
        sort_keys=False,
        allow_unicode=True,
    ).rstrip()


def _fence(text: str) -> str:
    """Wrap a body in a fence long enough that its own fences cannot close it."""

    longest = 0
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("`"):
            longest = max(longest, len(stripped) - len(stripped.lstrip("`")))
    marker = "`" * max(3, longest + 1)
    return f"{marker}\n{text.rstrip()}\n{marker}"


def _strip_fence(text: str) -> str:
    """Unwrap a reply that is one fenced block, and leave anything else alone."""

    lines = text.strip().splitlines()
    if len(lines) < 2 or not lines[0].lstrip().startswith("```"):
        return text.strip()
    if not lines[-1].strip().startswith("```"):
        return text.strip()
    # Only unwrap when the opening fence is the *only* one that could close the
    # block; a reply whose body carries its own fences is returned untouched.
    inner = lines[1:-1]
    if any(line.strip().startswith("```") for line in inner):
        return text.strip()
    return "\n".join(inner).strip()
