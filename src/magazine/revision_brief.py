"""Seven finding sets in, one revision brief out.

Seven lenses now judge a piece and a writer gets one document.  Handing him
seven verdicts stapled together would undo most of what splitting the bench
bought: he would read them in whatever order they arrived, fix the sentence
craft first, and lose that work to the structural cut a different lens asked for
in a section he had not reached.  So composition is a real step with real rules,
and ``prompts/README.md`` states them.  This module is those rules.

**Ordering is repair order, not severity and not lens.**  The brief lists
findings in the order the work should be done::

    worth -> evidence -> shape -> teaching -> craft -> mechanics

which is exactly :data:`~magazine.produce_graph.PIECE_JUDGE_LENSES`, read top to
bottom.  Fixing a worth or shape finding deletes and moves the text craft and
mechanics findings point at, so any other order wastes the writer's work.
Severity still prints inline on every entry and the brief opens with a per-lens
count of blocking and major findings, so nothing is hidden by the ordering --
the order is advice about sequence, never a ranking of importance.

**Within a tier, order by where the repair starts.**  ``repair_from`` names the
earliest sentence at which a defect could be fixed, so sorting by its position
in the manuscript walks the writer forward through the piece once instead of
sending him back and forth.  Falls back to ``locator``, then to the order the
lens filed them in.

**Deduplication merges the same complaint and never the same site.**  Two
lenses landing on one sentence for two *reasons* is information, not noise, so
only a matching ``(article, normalised locator, category)`` triple merges.  A
merge keeps the highest severity, keeps the earliest-tier lens as owner, and
appends the others as "also flagged by"; severities are never averaged, and a
``blocking`` finding is never removed by deduplication.  Two findings at one
locator from different concerns print adjacent, higher tier first, and the lower
one is annotated *moot if the one above is resolved by deletion* -- because it
often is, and a writer who fixes a comma in a paragraph that is about to go has
been sent to do nothing.

**Conflicts are printed, never resolved.**  Two lenses can give contradictory
instructions: ``worth`` says the section does not pay for its length while
``teaching`` says question four is unanswerable without it; ``evidence`` says
restore the qualification while ``worth`` says you are already longer than your
source.  The composer names both findings and the tension and stops there, and
the writer must satisfy both or say in his reply which he could not and why.
What this module can honestly detect is the structural signature of those two
examples -- a lens that can only be satisfied by *more* text and a lens that can
only be satisfied by *less*, landing on the same passage -- and that is what it
detects; a semantic contradiction between two prose notes is not something a
composer can find, and pretending otherwise would produce confident nonsense.
:data:`TRUTH_PRECEDENCE` is printed beside a conflict rather than applied,
because the one rule that decides a genuine deadlock -- no lens may be satisfied
by making the piece less true -- is a rule for the human or the writer, not a
reason to drop somebody's finding.

**Three labelled sections, and the labels are the contract.**

``Must fix``
    Every ``blocking`` and ``major`` finding with ``disposition: fix``.  The
    defect must be gone.  The writer is judged on the defect, never on whether
    the reviewer's suggested line was taken.

``Consider``
    Every ``minor`` finding with ``disposition: fix``.  Declinable in one line.

``For the editor``
    Every finding with ``disposition: editor_decision``, at any severity.  Not
    the writer's to fix, and blocking on the release until a human rules.  It is
    printed in the writer's brief anyway, deliberately: he needs to know why a
    defect he can see is not on his list, or he will fix it and breach
    ``docs/EDITORIAL_POLICY.md``.

**Volume is capped, and the cap is honest about itself.**  Every blocking and
major finding prints.  Minor findings print up to :data:`MINOR_LIMIT` per piece
in tier order; the remainder are counted in the brief and held in the record, and
they reappear in the next round's brief if they are still present.  A writer who
is drowning fixes nothing.

**Scores do not appear at all.**  They are advisory telemetry, and the edition
the owner rejected scored fives across the bench.  A number a writer can see is
a number a writer can optimise, so :func:`compose` has no parameter that could
carry one.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .produce_graph import PIECE_JUDGE_KINDS
from .review_findings import (
    EDITOR_DECISION,
    FINDING_SEVERITIES,
)

MINOR_LIMIT = 10
"""Minor findings printed per piece per round, before the rest are held."""

TRUTH_PRECEDENCE: tuple[str, ...] = (
    "evidence",
    "teaching",
    "worth",
    "shape",
    "craft",
    "mechanics",
)
"""Which lens wins when two genuinely cannot both hold.

Printed beside a conflict, never applied by this module.  The rule behind it is
one sentence: **no lens may be satisfied by making the piece less true.**  Length
is always paid for by cutting something else, never by dropping a qualification,
which is already the cut order in ``prompts/faithful-synthesis.md``.
"""

# Lenses whose findings are typically cleared by *adding* text -- a restored
# qualification, a definition, an answer to a comprehension question -- and
# lenses typically cleared by *removing* it.  This is the only conflict signature
# a composer can detect without understanding the prose, and it is exactly the
# signature of both examples ``prompts/README.md`` gives.  It is a heuristic and
# it is labelled as one in the output: a conflict block asks the writer to look,
# it does not assert that two findings are incompatible.
_WANTS_MORE = frozenset({"evidence", "teaching"})
_WANTS_LESS = frozenset({"worth", "shape"})

# The three tables above name lenses, and a lens the composer has never heard of
# would fall out of the precedence, out of the conflict detector, or -- worst --
# silently into the last repair tier.  So they are checked against the lens
# declaration at import, the same bargain :mod:`magazine.review_bench` makes.
# A pure-function module has no runtime that would otherwise notice.
if frozenset(TRUTH_PRECEDENCE) != frozenset(PIECE_JUDGE_KINDS):
    raise RuntimeError(
        "revision_brief.TRUTH_PRECEDENCE covers "
        + ", ".join(sorted(TRUTH_PRECEDENCE))
        + " and the bench declares "
        + ", ".join(sorted(PIECE_JUDGE_KINDS))
        + "; a lens with no place in the precedence cannot be named in a "
        "conflict block, and one that only appears here does not exist"
    )
if not (_WANTS_MORE | _WANTS_LESS) <= frozenset(PIECE_JUDGE_KINDS):
    raise RuntimeError(
        "revision_brief's conflict signatures name a lens the bench does not "
        "declare: "
        + ", ".join(sorted((_WANTS_MORE | _WANTS_LESS) - frozenset(PIECE_JUDGE_KINDS)))
    )

_SEVERITY_RANK = {name: index for index, name in enumerate(FINDING_SEVERITIES)}

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


def normalize_locator(value: Any) -> str:
    """One locator in the form two of them can be compared in.

    ``prompts/README.md`` requires both sides to normalise curly quotes and
    apostrophes to straight ones before matching, because a writer hands back
    typographic quotes for the straight ones a source used and a comparison that
    called those two different strings would merge nothing it should.  Runs of
    whitespace collapse for the same reason: the same sentence is one line in
    one lens's quote and a wrapped fragment in another's.
    """

    text = unicodedata.normalize("NFKC", str(value or "")).translate(_QUOTE_FOLDING)
    return " ".join(text.split()).casefold()


def locator_quote(value: Any) -> str:
    """The middle field of a locator: the exact quote, without heading or index."""

    parts = str(value or "").split("|")
    if len(parts) >= 2:
        return parts[1].strip()
    return str(value or "").strip()


def locator_heading(value: Any) -> str:
    """The first field of a locator: the section heading, or ``-``."""

    parts = str(value or "").split("|")
    return parts[0].strip() if parts else ""


@dataclass(frozen=True)
class BriefEntry:
    """One finding as the brief will print it, after merging and annotation."""

    id: str
    lens: str
    finding: Mapping[str, Any]
    also_flagged_by: tuple[tuple[str, str], ...] = ()
    """``(lens, note)`` for every lens that filed the same complaint here."""

    moot_if: str = ""
    """The id of a higher-tier finding whose deletion would make this one moot."""

    @property
    def severity(self) -> str:
        return str(self.finding.get("severity") or "major")

    @property
    def disposition(self) -> str:
        return str(self.finding.get("disposition") or "").strip()

    @property
    def is_editor_decision(self) -> bool:
        return self.disposition == EDITOR_DECISION

    @property
    def category(self) -> str:
        return str(self.finding.get("category") or "unspecified")

    @property
    def filed_by(self) -> str:
        """Who to credit in the brief, which is not always the tier it sorts in.

        A finding carries ``judge`` naming whoever filed it, and for the seven
        lenses that is the lens's own name.  For a finding a human typed into
        ``mag finding file`` it is that person, or "the edition review", or
        whatever they called themselves -- and that attribution is worth
        keeping, because a reviser treats "from the edition review" differently
        from "from the craft lens", and should.

        :func:`compose` still has to sort such a finding into *some* repair
        tier, and it uses the last one.  Printing that tier as the author would
        report a hand-filed complaint as ``(mechanics)``, which is the
        attribution silently replaced by a guess.
        """

        return str(self.finding.get("judge") or "").strip() or self.lens

    def render(self, number: int) -> list[str]:
        finding = self.finding
        lines = [
            f"{number}. [{self.severity}] {self.category} "
            f"({self.filed_by}) -- {self.id}"
        ]
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
        for lens, other in self.also_flagged_by:
            lines.append(f"   - also flagged by {lens}:")
            lines.extend(f"     {line}" for line in other.splitlines())
        if self.moot_if:
            lines.append(
                f"   - moot if {self.moot_if} is resolved by deletion; read that "
                "one first and do not spend work here until you know this text "
                "survives"
            )
        suggestion = str(finding.get("suggestion") or "").strip()
        if suggestion:
            lines.append(
                f"   - suggestion (advice, not the obligation): {suggestion}"
            )
        return lines


@dataclass(frozen=True)
class Conflict:
    """Two findings that may not both be satisfiable, named and not resolved."""

    first: BriefEntry
    second: BriefEntry
    tension: str

    @property
    def escalates(self) -> bool:
        """Whether this one goes to a human instead of to the writer.

        Two ``blocking`` findings in conflict is not a thing a writer can be
        asked to reconcile: each one alone forces ``changes_required``, so
        satisfying either by giving ground on the other simply re-fails the
        piece.  ``prompts/README.md`` sends that case, and any conflict that
        recurs in two consecutive rounds, to a human.
        """

        return self.first.severity == "blocking" and self.second.severity == "blocking"

    def render(self) -> list[str]:
        lines = [
            f"conflict: {self.first.id} ({self.first.lens}) vs "
            f"{self.second.id} ({self.second.lens})",
            f"  {self.tension}",
            "  Satisfy both. If you genuinely cannot, say so in your reply and "
            "say which you could not and why.",
            "  If they truly cannot both hold: no lens may be satisfied by "
            "making the piece less true. Precedence is "
            + " > ".join(TRUTH_PRECEDENCE)
            + ". Length is paid for by cutting something else, never by "
            "dropping a qualification.",
        ]
        if self.escalates:
            lines.append(
                "  Both are blocking, so this one is a human's to settle, not "
                "yours. Flag it in your reply and do the rest."
            )
        return lines


@dataclass(frozen=True)
class RevisionBrief:
    """One piece's whole revision worklist, composed and ready to render."""

    piece_id: str
    must_fix: tuple[BriefEntry, ...] = ()
    consider: tuple[BriefEntry, ...] = ()
    for_the_editor: tuple[BriefEntry, ...] = ()
    conflicts: tuple[Conflict, ...] = ()
    held_minor: int = 0
    """Minor findings over :data:`MINOR_LIMIT`, counted rather than printed."""

    counts: Mapping[str, tuple[int, int]] = field(default_factory=dict)
    """Per lens, ``(blocking, major)``, in repair order."""

    @property
    def is_empty(self) -> bool:
        return not (self.must_fix or self.consider or self.for_the_editor)

    def render(self) -> list[str]:
        """The brief as the writer reads it.  Never carries a score."""

        if self.is_empty:
            return []
        lines: list[str] = []
        headline = [
            f"{lens}: {blocking} blocking, {major} major"
            for lens, (blocking, major) in self.counts.items()
            if blocking or major
        ]
        if headline:
            lines.append("Blocking and major findings by lens: " + "; ".join(headline))
            lines.append("")
        lines.append(
            "The findings below are in **repair order**, not severity order: "
            "worth, then evidence, then shape, then teaching, then craft, then "
            "mechanics. Work down the list. Fixing a structural finding deletes "
            "and moves the text a sentence-level finding points at, so doing "
            "them in any other order wastes your own work. Severity is printed "
            "on every entry."
        )
        lines.append("")
        for title, entries, preamble in (
            (
                "Must fix",
                self.must_fix,
                "Every one of these defects must be gone from your draft. You "
                "are judged on whether the defect survived, never on whether "
                "you took the suggested line, so solve each one however the "
                "piece is best served.",
            ),
            (
                "Consider",
                self.consider,
                "Minor findings. Take them or decline them; a declined one "
                "costs you one line in your reply saying why.",
            ),
            (
                "For the editor",
                self.for_the_editor,
                "These are NOT yours to fix. Each is a defect in text whose "
                "wording `docs/EDITORIAL_POLICY.md` makes review-required, so a "
                "human chooses the remedy. Leave them exactly as they are -- "
                "changing one is a policy breach, and adding an editor's note "
                "about one is worse, because the magazine does not print "
                "editorial apparatus inside an article. They are listed so you "
                "know why a defect you can see is not on your list.",
            ),
        ):
            if not entries:
                continue
            lines.append(f"### {title}")
            lines.append("")
            lines.append(preamble)
            lines.append("")
            for number, entry in enumerate(entries, start=1):
                lines.extend(entry.render(number))
            lines.append("")
        if self.held_minor:
            lines.append(
                f"{self.held_minor} further minor finding(s) are held in the "
                "record rather than printed: a writer who is drowning fixes "
                "nothing. They return in the next round's brief if they are "
                "still there."
            )
            lines.append("")
        if self.conflicts:
            lines.append("### Conflicts between lenses")
            lines.append("")
            lines.append(
                "Two lenses have landed on the same passage wanting opposite "
                "things. Nobody has resolved this for you, deliberately."
            )
            lines.append("")
            for conflict in self.conflicts:
                lines.extend(conflict.render())
                lines.append("")
        return lines


def compose(
    piece_id: str,
    findings_by_lens: Sequence[tuple[str, Sequence[Any]]],
    *,
    manuscript: str = "",
) -> RevisionBrief:
    """Merge N lenses' finding sets into one worklist for one piece.

    ``findings_by_lens`` is ``(lens_kind, findings)`` pairs; the order they
    arrive in is irrelevant, because tiering comes from
    :data:`~magazine.produce_graph.PIECE_JUDGE_KINDS`.  ``manuscript`` is used
    only to order findings within a tier by where in the piece the repair
    starts; a caller that has not got it gets filing order instead, which is
    worse but never wrong.

    There is no ``scores`` parameter and there must never be one.
    """

    tier = {kind: index for index, kind in enumerate(PIECE_JUDGE_KINDS)}
    haystack = normalize_locator(manuscript)

    rows: list[tuple[int, int, int, str, Mapping[str, Any]]] = []
    for lens, findings in findings_by_lens:
        for position, finding in enumerate(findings):
            if not isinstance(finding, Mapping):
                continue
            rows.append(
                (
                    tier.get(lens, len(tier)),
                    _repair_position(finding, haystack),
                    position,
                    lens,
                    finding,
                )
            )
    rows.sort(key=lambda row: (row[0], row[1], row[2], row[3]))

    entries = _merge(rows)
    _annotate_moot(entries)
    conflicts = _conflicts(entries)

    must_fix: list[BriefEntry] = []
    consider: list[BriefEntry] = []
    editor: list[BriefEntry] = []
    held = 0
    for entry in entries:
        if entry.is_editor_decision:
            # Never dropped, never capped by volume, at any severity.  This is
            # the branch the whole disposition field exists for: the old bench
            # let these disappear into a severity floor and then reported the
            # piece clean.
            editor.append(entry)
        elif entry.severity in ("blocking", "major"):
            must_fix.append(entry)
        elif len(consider) < MINOR_LIMIT:
            consider.append(entry)
        else:
            held += 1

    counts: dict[str, tuple[int, int]] = {}
    for kind in PIECE_JUDGE_KINDS:
        blocking = sum(
            1 for entry in entries if entry.lens == kind and entry.severity == "blocking"
        )
        major = sum(
            1 for entry in entries if entry.lens == kind and entry.severity == "major"
        )
        if blocking or major:
            counts[kind] = (blocking, major)

    return RevisionBrief(
        piece_id=piece_id,
        must_fix=tuple(must_fix),
        consider=tuple(consider),
        for_the_editor=tuple(editor),
        conflicts=tuple(conflicts),
        held_minor=held,
        counts=counts,
    )


def _repair_position(finding: Mapping[str, Any], haystack: str) -> int:
    """Where in the manuscript the repair starts, as a sort key.

    ``repair_from`` first, because that is the earliest sentence at which the
    defect could be fixed and therefore where the writer's cursor should go.
    ``locator`` second.  A finding with neither -- legal, for a defect with no
    single site -- sorts to the front of its tier, where a whole-piece problem
    belongs.
    """

    if not haystack:
        return 0
    for key in ("repair_from", "locator"):
        quote = normalize_locator(locator_quote(finding.get(key)))
        if quote:
            at = haystack.find(quote)
            if at >= 0:
                return at
    return 0


def _merge(
    rows: Sequence[tuple[int, int, int, str, Mapping[str, Any]]]
) -> list[BriefEntry]:
    """Fold findings that are the same complaint; never fold two complaints.

    The identity of a complaint is ``(article, normalised locator, category)``.
    Two lenses agreeing that one sentence has one defect is one obligation and
    should read as one.  Two lenses finding two different defects in one
    sentence is two obligations, and merging them would silently retire one --
    which is why the key includes the category and why nothing here compares
    notes for similarity.
    """

    merged: dict[tuple[str, ...], BriefEntry] = {}
    order: list[tuple[str, ...]] = []
    counter = 0
    for _tier, _position, _filed, lens, finding in rows:
        locator = normalize_locator(finding.get("locator"))
        key: tuple[str, ...] = (
            str(finding.get("article") or ""),
            locator,
            str(finding.get("category") or ""),
        )
        if not locator:
            # A finding with no locator has no single site, so it cannot be
            # "the same place" as anything.  Giving it a key nothing else can
            # collide with keeps it distinct without a second code path.
            key = (*key, f"#{len(order)}")
        existing = merged.get(key)
        if existing is None:
            counter += 1
            merged[key] = BriefEntry(id=f"F{counter}", lens=lens, finding=finding)
            order.append(key)
            continue
        note = str(finding.get("note") or "").strip()
        # Highest severity wins and the earliest tier keeps ownership.  Rows
        # arrive in tier order, so ``existing`` is always the earlier tier;
        # severities are compared, never averaged, because an averaged severity
        # is a severity nobody filed.
        winner = (
            finding
            if _SEVERITY_RANK.get(str(finding.get("severity")), 9)
            < _SEVERITY_RANK.get(existing.severity, 9)
            else existing.finding
        )
        merged[key] = BriefEntry(
            id=existing.id,
            lens=existing.lens,
            finding=winner,
            also_flagged_by=existing.also_flagged_by + ((lens, note),),
            moot_if=existing.moot_if,
        )
    return [merged[key] for key in order]


def _annotate_moot(entries: list[BriefEntry]) -> None:
    """Mark a finding whose site a higher-tier finding may be about to delete.

    Same locator, different concerns: ``prompts/README.md`` says print them
    adjacent in tier order and annotate the lower one.  Adjacency is already
    true -- the list is in tier order and equal locators sort together -- so
    what is left is the annotation, and it is worth more than it looks: it is
    what stops a writer polishing a sentence inside a section that ``worth`` has
    just said does not pay for its length.

    Only the same-locator case is detected.  "Inside a passage a higher-tier
    finding proposes to cut" would need the composer to understand which
    findings propose a cut and how far the cut reaches, and a wrong guess there
    would tell a writer to skip a repair he actually owes.  A missed annotation
    costs some wasted effort; a false one costs a defect.
    """

    seen: dict[str, BriefEntry] = {}
    for index, entry in enumerate(entries):
        locator = normalize_locator(entry.finding.get("locator"))
        if not locator:
            continue
        owner = seen.get(locator)
        if owner is None:
            seen[locator] = entry
            continue
        entries[index] = BriefEntry(
            id=entry.id,
            lens=entry.lens,
            finding=entry.finding,
            also_flagged_by=entry.also_flagged_by,
            moot_if=owner.id,
        )


def _conflicts(entries: Sequence[BriefEntry]) -> list[Conflict]:
    """Pair up findings on one passage that pull in opposite directions.

    Matched on the locator's *heading* rather than on the exact quote, because
    the two examples in ``prompts/README.md`` are both section-scale: worth says
    the section does not pay for its length, teaching says a question is
    unanswerable without it.  Two findings on literally the same sentence are
    usually the moot-if case above, not a conflict.
    """

    conflicts: list[Conflict] = []
    for index, first in enumerate(entries):
        for second in entries[index + 1 :]:
            if first.lens == second.lens:
                continue
            pair = {first.lens, second.lens}
            if not (pair & _WANTS_LESS and pair & _WANTS_MORE):
                continue
            heading = normalize_locator(locator_heading(first.finding.get("locator")))
            other = normalize_locator(locator_heading(second.finding.get("locator")))
            if not heading or heading != other:
                continue
            wants_less = first if first.lens in _WANTS_LESS else second
            wants_more = second if wants_less is first else first
            conflicts.append(
                Conflict(
                    first=first,
                    second=second,
                    tension=(
                        f"{wants_less.lens} wants this passage shorter or gone "
                        f"({wants_less.category}); {wants_more.lens} needs text "
                        f"here that is currently missing ({wants_more.category}). "
                        "They may both be right."
                    ),
                )
            )
    return conflicts
