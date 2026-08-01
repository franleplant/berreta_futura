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

* **The line editor never sees the source.**  :class:`LineReviewInput` has no
  field that could carry one, and :func:`compose_line_prompt` accepts nothing
  else.  Because a ``faithful_edit`` manuscript legitimately *is* the source's
  sentences, a content scan alone would be unsound, so
  :func:`assert_source_withheld` checks the only thing that can honestly be
  checked: no substantial source line that the manuscript does not already
  carry may appear in the prompt.  The type is the guarantee; the scan catches
  a future edit that routes source text in by another door.

* **The manager's run A is starved on purpose.**  :func:`compose_manager_run_a`
  is handed the furniture projection and nothing else, and it is a separate
  function from :func:`compose_learning_prompt` precisely so that no call site
  can accidentally hand run A a body.  A single run cannot un-see the body,
  which is the case where the persona rubber-stamps its own takeaways.

* **A finding is an obligation; a suggestion is advice.**  The revision block
  says so in those words, and nothing in this package ever reads a finding's
  ``suggestion`` to decide whether a revision passed.

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

JUDGE_PROMPTS: Mapping[str, str] = {
    "evidence": "prompts/evidence-review.md",
    "line": "prompts/line-review.md",
    "learning": "prompts/learning-review.md",
    "edition": "prompts/edition-review.md",
}

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
    opener_intro_characters: int = 0
    """The illustrated opener's opening-paragraph budget, measured.

    Zero means the piece has no illustrated opener and no such constraint.
    Non-zero is a hard limit the build enforces and previously stated nowhere:
    see :func:`~magazine.weasyprint_adapter.illustrated_opener_intro_budget`.
    ``characters`` is an estimate of the same measurement in a countable unit,
    and is zero when there was no prose sample to derive it from.
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
        about = (
            f", about {piece.opener_intro_characters} characters"
            if piece.opener_intro_characters
            else ""
        )
        parts.append(
            f"- Opening paragraph budget: {piece.opener_intro_lines} typeset "
            f"line(s){about}"
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
            "typeset line(s)"
            + (
                f", which is roughly {piece.opener_intro_characters} characters "
                "of prose like your source's"
                if piece.opener_intro_characters
                else ""
            )
            + ". The number is measured for this article's own title and "
            "byline, so it is not a rule of thumb. A first paragraph over it "
            "does not wrap to the next page: the build refuses the edition, "
            "and the piece costs a round. Write a shorter opening paragraph "
            "and put the rest in the second one."
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
                "### Findings you must clear",
                "",
                "Every finding is an obligation: the defect it names must be "
                "gone from your draft. A `suggestion` is advisory. You are "
                "judged on whether the defect survived, never on whether you "
                "took the suggested line, so solve it however the piece is best "
                "served.",
                "",
            ]
        )
        for index, finding in enumerate(brief.findings, start=1):
            parts.extend(_finding_lines(index, finding))
        parts.append("")
    return parts


def _finding_lines(index: int, finding: Mapping[str, Any]) -> list[str]:
    severity = str(finding.get("severity") or "major")
    category = str(finding.get("category") or "unspecified")
    judge = str(finding.get("judge") or "").strip()
    header = f"{index}. [{severity}] {category}"
    if judge:
        header += f" (from the {judge})"
    lines = [header]
    for key, label in (
        ("locator", "where it shows"),
        ("repair_from", "earliest repair point"),
    ):
        value = str(finding.get(key) or "").strip()
        if value:
            lines.append(f"   - {label}: {value}")
    note = str(finding.get("note") or "").strip()
    if note:
        lines.append("   - note:")
        lines.extend(f"     {line}" for line in note.splitlines())
    suggestion = str(finding.get("suggestion") or "").strip()
    if suggestion:
        lines.append(f"   - suggestion (advisory): {suggestion}")
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
# Judge briefs.


@dataclass(frozen=True)
class EvidenceReviewInput:
    """What the fact-checker reads: the manuscript and its complete sources."""

    piece_id: str
    content_mode: str
    byline: str
    manuscript: str
    extractions: tuple[Extraction, ...] = ()
    peer_manuscripts: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class LineReviewInput:
    """What the line editor reads.  Note what is not here.

    There is no source field, and there is no way to add one from a call site:
    :func:`compose_line_prompt` takes this type and nothing else.  A line
    editor who can see the source starts fact-checking and stops reading for
    flow, and ``prompts/line-review.md`` forbids opening it -- but a
    prohibition a harness could violate is a prohibition that eventually gets
    violated, so the harness cannot.
    """

    piece_id: str
    content_mode: str
    byline: str
    max_pages: int
    manuscript: str


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


def line_identity(prompt: PromptFile, item: LineReviewInput) -> str:
    return work_identity(
        "line",
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


def compose_evidence_prompt(prompt: PromptFile, item: EvidenceReviewInput) -> str:
    parts = [prompt.text.rstrip(), "", "---", "", "# The article under audit", ""]
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
        parts.append("## The edition's articles, which this piece is checked against")
        parts.append("")
        for peer_id, text in item.peer_manuscripts:
            parts.append(f"### `{peer_id}`")
            parts.append("")
            parts.append(_fence(text))
            parts.append("")
    parts.append(_yaml_only_contract("evidence"))
    return "\n".join(parts)


def compose_line_prompt(prompt: PromptFile, item: LineReviewInput) -> str:
    """Assemble the line editor's brief from a manuscript and nothing else."""

    parts = [prompt.text.rstrip(), "", "---", "", "# The piece under review", ""]
    parts.append(f"- Article id: `{item.piece_id}`")
    parts.append(f"- content_mode: `{item.content_mode}`")
    if item.byline:
        parts.append(f"- Byline: {item.byline}")
    parts.append(f"- Page budget: {item.max_pages} rendered A5 reader page(s)")
    parts.append("")
    parts.append(
        "The source extraction is deliberately withheld. Judge how this reads, "
        "not whether it is true."
    )
    parts.append("")
    parts.append("## Manuscript")
    parts.append("")
    parts.append(_fence(item.manuscript))
    parts.append("")
    parts.append(_yaml_only_contract("line"))
    return "\n".join(parts)


def assert_source_withheld(
    prompt: str,
    extractions: Sequence[Extraction],
    *,
    manuscript: str,
    label: str,
) -> None:
    """Refuse a brief that leaks source text the manuscript does not carry.

    The check cannot simply look for source sentences: a ``faithful_edit``
    manuscript *is* the source's sentences, and the manuscript is legitimately
    in this prompt.  So the exempt set is the prose the manuscript itself
    carries, and any other substantial run of source prose found in the prompt
    is a leak by a route the type system did not close.

    Both sides are compared through :func:`_fold`, and the manuscript is
    compared as one folded body rather than as a set of lines.  A source line
    is a wrap fragment, not a unit of meaning: the same sentence sits alone on
    a source line and mid-paragraph in a manuscript, so line-for-line equality
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
                    f"{line.strip()[:60]!r}. This role is forbidden the source."
                )


# ---------------------------------------------------------------------------
# Whole-issue briefs.


@dataclass(frozen=True)
class ManagerRunAInput:
    """Run A's entire world: the editor-authored furniture.

    Marcus is two runs, not two steps of one, and the boundary is the harness's
    job rather than the model's self-restraint.  Run A cannot un-see a body it
    was never given, which is the only version of this that holds.
    """

    edition_id: str
    furniture: Mapping[str, Any]


@dataclass(frozen=True)
class LearningReviewInput:
    """Run B: run A's block verbatim, plus everything the personas need."""

    edition_id: str
    furniture: Mapping[str, Any]
    manager_takeaways: str
    explainers: tuple[tuple[str, str], ...] = ()
    articles: tuple[tuple[str, str], ...] = ()
    """The bodies Marcus adjudicates his run A claims against.

    Run A was denied these; run B needs them, and needing them is the whole
    reason the two are separate calls.
    """

    extractions: tuple[Extraction, ...] = ()
    writer_questions: tuple[str, ...] = ()


@dataclass(frozen=True)
class EditionReviewInput:
    """The managing editor's brief: the issue, never its sources."""

    edition_id: str
    manifest: Mapping[str, Any]
    editorial: str | None
    articles: tuple[tuple[str, str, str], ...] = field(default=())


def manager_run_a_identity(prompt: PromptFile, item: ManagerRunAInput) -> str:
    return work_identity(
        "manager_run_a",
        {
            "prompt_path": prompt.path,
            "prompt_sha256": prompt.sha256,
            "edition": item.edition_id,
            "furniture": _digest(_yaml_block(item.furniture)),
        },
    )


def learning_identity(prompt: PromptFile, item: LearningReviewInput) -> str:
    return work_identity(
        "learning",
        {
            "prompt_path": prompt.path,
            "prompt_sha256": prompt.sha256,
            "edition": item.edition_id,
            "furniture": _digest(_yaml_block(item.furniture)),
            "manager_takeaways": _digest(item.manager_takeaways),
            "explainers": _text_digests(item.explainers),
            "articles": _text_digests(item.articles),
            "extractions": _body_digests(item.extractions),
            "writer_questions": list(item.writer_questions),
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
            "articles": {
                article_id: [content_mode, _digest(text)]
                for article_id, content_mode, text in item.articles
            },
        },
    )


def compose_manager_run_a(prompt: PromptFile, item: ManagerRunAInput) -> str:
    """Compose run A.  This function has no parameter that could hold a body."""

    return "\n".join(
        [
            prompt.text.rstrip(),
            "",
            "---",
            "",
            "# Marcus, run A only",
            "",
            "Run ONLY the run A step of the Marcus persona. Do not run Nadia, "
            "do not run Priya, and do not run Marcus run B: the article bodies "
            "and the explainer are withheld from this call and will be supplied "
            "to a separate one. Everything you can see is below.",
            "",
            f"Edition: `{item.edition_id}`",
            "",
            "## The editor-authored furniture, in full",
            "",
            _fence(_yaml_block(item.furniture)),
            "",
            "## Output contract",
            "",
            "Return one YAML document and nothing else, carrying only a "
            "`manager_takeaways` key: one entry per article you can see "
            "furniture for, each with `article`, `decision`, and exactly three "
            "`claims`, each a sentence Marcus would say aloud. Emit no "
            "`adjudication`, no `findings`, no `result`, and no `scores`: you "
            "have not read the bodies and cannot adjudicate anything yet.",
            "",
            "```yaml",
            "manager_takeaways:",
            "  - article: <article-id>",
            "    decision: <the one decision he would make>",
            "    claims:",
            "      - <claim one>",
            "      - <claim two>",
            "      - <claim three>",
            "```",
            "",
        ]
    )


def compose_learning_prompt(prompt: PromptFile, item: LearningReviewInput) -> str:
    """Compose run B, carrying run A's block in verbatim and unrevisable."""

    parts = [prompt.text.rstrip(), "", "---", "", "# The edition under review", ""]
    parts.append(f"Edition: `{item.edition_id}`")
    parts.append("")
    parts.append("## Marcus run A, already written and closed")
    parts.append("")
    parts.append(
        "This block was produced by a separate call that saw the furniture and "
        "nothing else. It is a record, not a draft. Copy it into your answer "
        "unchanged -- the same decision and the same three claims, word for "
        "word -- and add only the `adjudication` list to each entry. A run B "
        "that improves run A's claims after reading the body has destroyed the "
        "only measurement this persona makes, and the harness refuses it."
    )
    parts.append("")
    parts.append(_fence(item.manager_takeaways))
    parts.append("")
    parts.append("## The editor-authored furniture")
    parts.append("")
    parts.append(_fence(_yaml_block(item.furniture)))
    parts.append("")
    for explainer_id, text in item.explainers:
        parts.append(f"## Explainer `{explainer_id}`")
        parts.append("")
        parts.append(_fence(text))
        parts.append("")
    if item.articles:
        parts.append("## The article bodies, for Marcus run B and nothing else")
        parts.append("")
        for article_id, text in item.articles:
            parts.append(f"### `{article_id}`")
            parts.append("")
            parts.append(_fence(text))
            parts.append("")
    if item.writer_questions:
        parts.append("## The writer's own comprehension questions")
        parts.append("")
        parts.append(
            "Nadia writes her six first and never replaces them with these; a "
            "question here that the piece cannot answer is a "
            "`comprehension_gap` all the same."
        )
        parts.append("")
        parts.extend(f"- {question}" for question in item.writer_questions)
        parts.append("")
    for extraction in item.extractions:
        parts.append(f"## Pinned extraction `{extraction.source_id}` (complete)")
        parts.append("")
        parts.append(_fence(extraction.body))
        parts.append("")
    parts.append(_yaml_only_contract("learning"))
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
    parts.append(_yaml_only_contract("edition"))
    return "\n".join(parts)


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
    return (
        "## Output contract\n\n"
        "Return one YAML document and nothing else, in exactly the shape the "
        f"{kind} review prompt above specifies. No preamble, no commentary "
        "after it. The document may carry only `result`, `findings`, `scores`, "
        "`notes`"
        + (
            ", `comprehension`, and `manager_takeaways`"
            if kind == "learning"
            else ""
        )
        + ": any other key is refused by the recorder.\n"
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
