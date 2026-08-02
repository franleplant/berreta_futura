"""Structured findings and advisory scores, shared by every judge's record.

The review bench used to store a finding as a string, because the only finding
anyone wrote was a sentence typed into ``--finding``.  The judge prompts
(``prompts/evidence-review.md`` and its three siblings) emit something else: a
mapping with a ``severity``, the ``article`` it lands on, a ``locator`` naming
the exact sentence, a ``category``, and a ``note``, plus ``suggestion`` on a
line finding and ``persona`` on a learning one.  Passing one of those through
the old recorder produced ``"{'severity': 'major', 'article': ...}"`` -- a
mapping survives the truthiness check and ``str(item).strip()`` then flattens
it into a line of Python repr that no tool can read back.  This module is the
one place that knows what a finding is, so every kind stores the same shape and
no kind has to re-derive it.

Three rules hold across the whole bench:

* **A finding is stored as authored.**  Known keys are written in a fixed
  order so records diff cleanly, unknown keys are preserved rather than
  dropped, and a plain string stays a plain string -- ``--finding "..."`` is
  still how a human types one, and every record written before this module
  existed is full of them.
* **A score never gates.**  Scores are parsed, bounded to the prompts' 1-5, and
  exposed; nothing in this package reads one to decide anything.  A gated score
  invites generous scoring, which would cost more than the measurement is
  worth.  They exist to be rolled up by ``mag scores`` and looked at.
* **Every authored finding says who repairs it.**  :data:`FINDING_DISPOSITIONS`
  is the field that replaced the severity cap, and the reason it is *required*
  rather than defaulted is written out below.

Ownership is a routing decision, never a severity ceiling
---------------------------------------------------------

The old bench capped findings on the source author's retained sentences at
``minor`` in the author-voiced modes.  That did not merely shield defects, it
certified cleanliness: a round-3 line review approved a piece with the note that
the actionable surface was clean *because* everything remaining was
uncapped-able, and twelve lowercase sentence openings, a subject-verb error and
six identical constructions in 495 words were inside that sentence.

``prompts/README.md`` replaced the cap with routing, and this module is where
that replacement is made structural.  Severity describes the defect;
:data:`FINDING_DISPOSITIONS` says who is allowed to repair it:

``fix``
    The writer resolves it in the next round.

``editor_decision``
    A human chooses the remedy, because the sentence is the source author's own
    retained text in ``faithful_edit`` or ``faithful_synthesis``, where
    ``docs/EDITORIAL_POLICY.md`` makes changing wording review-required.  The
    severity is still whatever the defect deserves.  An ``editor_decision``
    finding blocks the release until a human dispositions it, is never dropped,
    never softened, and never counted as clean -- which is what
    :func:`has_editor_decision` exists to let a gate say.

Because a parser that drops ``disposition`` reintroduces the bug the cap caused,
it is required of every *authored* structured finding
(:data:`DEFAULT_REQUIRED_FINDING_KEYS`, which :func:`normalize_findings` uses).
It is deliberately **not** required of a *stored* one
(:data:`STORED_REQUIRED_FINDING_KEYS`, which :func:`finding_errors` uses): every
finding committed before this field existed would otherwise stop loading, and
re-auditing a shipped edition to add a key nobody can now honestly supply is a
worse answer than reading the old record for the part of it that is still true.
That is the same bargain ``evidence_review`` already struck with its version 1
ledger binding.  New records carry it; old records load without it; nothing in
between can be written.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .errors import ValidationError


FINDING_SEVERITIES = ("blocking", "major", "minor")

FIX = "fix"
"""The writer resolves this finding in the next round."""

EDITOR_DECISION = "editor_decision"
"""A human chooses the remedy; the writer must not be sent at it.

The remedies open to that human are a silent repair, ``[sic]``, leaving it, or
not printing the piece.  An editor's note is deliberately not among them: the
magazine does not print editorial apparatus inside an article, and a note is how
a piece keeps its defect while appearing to answer one.
"""

FINDING_DISPOSITIONS = (FIX, EDITOR_DECISION)

# The keys the prompts define, in the order a record writes them.  A finding
# carrying anything else keeps it, sorted, after these -- the recorder is not
# the right place to decide a judge said too much.
#
# ``repair_from`` sits beside ``locator`` because the two answer different
# questions about the same defect: ``locator`` names where it becomes visible,
# ``repair_from`` the earliest sentence at which it could be fixed.  A pilot
# line review filed a frame contradiction at paragraph five whose cause was a
# mis-stated promise in paragraph two, and a reviser working from the locator
# alone would have patched the symptom.  It is optional on every kind and
# expected only on the structural categories.
#
# ``disposition`` sits after ``category`` because that is where every lens
# prompt writes it, and a record should read the way the judge wrote it.
#
# ``persona`` is retired but not removed.  It was required of a ``learning``
# finding, because the same sentence meant different things from Nadia (the
# piece never says this) and from Priya (the piece says this and the source
# disagrees).  ``prompts/README.md`` cut Marcus and Priya and kept Nadia as
# ``teaching``, so there is one reader now and naming her on every row says
# nothing -- but records written before the cut carry the key, and a recorder
# that dropped it on the way past would rewrite history to match the present.
# It stays in the order so those records still diff cleanly; nothing writes it.
FINDING_KEYS = (
    "severity",
    "article",
    "locator",
    "repair_from",
    "category",
    "disposition",
    "persona",
    "note",
    "suggestion",
)

# What an *authored* structured finding must carry.  Without a severity the
# finding cannot be triaged, without a note it says nothing, and without a
# disposition the bench is back to a severity cap by omission -- see the module
# docstring.  A plain-string finding typed into ``--finding`` is exempt from all
# three, since a human filing a sentence is not filing against a locator.
DEFAULT_REQUIRED_FINDING_KEYS = ("severity", "note", "disposition")

# What a *stored* structured finding must carry to be readable.  Deliberately
# short of the authored set: every finding committed before ``disposition``
# existed still loads, and its absence is reported as unrouted rather than as a
# corrupt record.  Nothing may be *written* to this weaker standard.
STORED_REQUIRED_FINDING_KEYS = ("severity", "note")

SCORE_RANGE = (1, 5)


def normalize_findings(
    findings: Iterable[Any],
    *,
    label: str,
    required: tuple[str, ...] = DEFAULT_REQUIRED_FINDING_KEYS,
) -> list[Any]:
    """Store a judge's findings faithfully, refusing what cannot be stored.

    ``label`` names the review in every refusal ("Line review finding 2 ...").
    ``required`` names the keys a *structured* finding must carry; a string
    finding is exempt, since a human typing ``--finding`` is not filing against
    a locator.  Empty strings and empty mappings are dropped, matching the
    older recorders' habit of ignoring a blank ``--finding``.
    """

    errors: list[str] = []
    normalized: list[Any] = []
    for index, item in enumerate(findings, start=1):
        if isinstance(item, Mapping):
            row, row_errors = _normalize_mapping_finding(
                item, label=label, index=index, required=required
            )
            errors.extend(row_errors)
            if row:
                normalized.append(row)
            continue
        if isinstance(item, str):
            text = item.strip()
            if text:
                normalized.append(text)
            continue
        errors.append(
            f"{label} finding {index} must be a mapping or a string, not "
            f"{type(item).__name__}"
        )
    if errors:
        raise ValidationError(errors)
    return normalized


def finding_errors(
    findings: Any,
    *,
    label: str,
    required: tuple[str, ...] = STORED_REQUIRED_FINDING_KEYS,
) -> list[str]:
    """The same checks as :func:`normalize_findings`, as a list of errors.

    Loading a record accumulates every complaint about the file before raising,
    so it cannot use the normalizer's own raise.  A record that predates
    structured findings must still load: a string finding passes here exactly
    as it always did, and so does a mapping written before ``disposition``
    existed -- the default ``required`` here is the *stored* set rather than the
    authored one, deliberately, so that reading a shipped record never demands a
    key the judge who wrote it was never asked for.
    """

    if not isinstance(findings, list):
        return [f"{label} findings must be a list"]
    errors: list[str] = []
    for index, item in enumerate(findings, start=1):
        if isinstance(item, Mapping):
            _, row_errors = _normalize_mapping_finding(
                item, label=label, index=index, required=required
            )
            errors.extend(row_errors)
        elif isinstance(item, str):
            if not item.strip():
                errors.append(f"{label} finding {index} is empty")
        else:
            errors.append(
                f"{label} finding {index} must be a mapping or a string, not "
                f"{type(item).__name__}"
            )
    return errors


def _normalize_mapping_finding(
    item: Mapping[str, Any],
    *,
    label: str,
    index: int,
    required: tuple[str, ...],
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    values: dict[str, Any] = {}
    for key, value in item.items():
        name = str(key)
        text = "" if value is None else str(value).strip()
        if text:
            values[name] = text
    for key in required:
        if key not in values:
            errors.append(f"{label} finding {index} requires a non-empty {key}")
    severity = values.get("severity")
    if severity is not None and severity not in FINDING_SEVERITIES:
        errors.append(
            f"{label} finding {index} severity must be "
            + ", ".join(FINDING_SEVERITIES)
        )
    # Checked whenever it is present, on the read path as well as the write
    # path.  A misspelled disposition is worse than a missing one: an absent
    # value is visibly unrouted, while ``editor-decision`` would be silently
    # read as "not an editor decision" and quietly counted clean.
    disposition = values.get("disposition")
    if disposition is not None and disposition not in FINDING_DISPOSITIONS:
        errors.append(
            f"{label} finding {index} disposition must be "
            + " or ".join(FINDING_DISPOSITIONS)
        )
    ordered = {key: values[key] for key in FINDING_KEYS if key in values}
    ordered.update(
        {key: values[key] for key in sorted(values) if key not in FINDING_KEYS}
    )
    return ordered, errors


def normalize_scores(scores: Any, *, label: str) -> dict[str, int]:
    """Parse one advisory ``scores`` map: named dimensions, each an integer 1-5.

    Authored order is preserved, because the prompts list their dimensions in a
    deliberate order and a record should read the way the judge wrote it.
    """

    errors = score_errors(scores, label=label)
    if errors:
        raise ValidationError(errors)
    if not scores:
        return {}
    return {str(name).strip(): int(value) for name, value in scores.items()}


def score_errors(scores: Any, *, label: str) -> list[str]:
    """Every complaint about one ``scores`` map, for accumulating loaders."""

    if scores is None or scores == {}:
        return []
    if not isinstance(scores, Mapping):
        return [f"{label} scores must be a mapping of dimension to integer"]
    low, high = SCORE_RANGE
    errors: list[str] = []
    for name, value in scores.items():
        dimension = str(name).strip()
        if not dimension:
            errors.append(f"{label} scores contain an unnamed dimension")
            continue
        # ``bool`` is an ``int`` in Python and ``True`` would silently become 1.
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(
                f"{label} score {dimension} must be an integer {low}-{high}"
            )
            continue
        if not low <= value <= high:
            errors.append(
                f"{label} score {dimension} must be an integer {low}-{high}"
            )
    return errors


def normalize_article_scores(
    scores: Any, *, label: str, article_ids: Iterable[str]
) -> dict[str, dict[str, int]]:
    """Parse per-article scores for the kinds whose judge runs once per piece.

    The line editor and the fact-checker each read one article at a time, so
    their scores belong to an article row rather than to the record: a partial
    re-record of one article must leave every other article's scores exactly as
    they were.  Scores for an article the edition does not carry are refused
    rather than stored where nothing will ever read them.
    """

    if not scores:
        return {}
    if not isinstance(scores, Mapping):
        raise ValidationError(
            f"{label} scores must be a mapping of article id to dimension scores"
        )
    known = set(article_ids)
    errors: list[str] = []
    parsed: dict[str, dict[str, int]] = {}
    for article_id, row in scores.items():
        name = str(article_id).strip()
        if name not in known:
            errors.append(
                f"{label} carries scores for {name!r}, which this record does not bind"
            )
            continue
        row_errors = score_errors(row, label=f"{label} article {name}")
        if row_errors:
            errors.extend(row_errors)
            continue
        parsed[name] = {
            str(dimension).strip(): int(value) for dimension, value in (row or {}).items()
        }
    if errors:
        raise ValidationError(errors)
    return parsed


def has_blocking_finding(findings: Iterable[Any]) -> bool:
    """Whether any stored finding is ``blocking``.

    Reported, never enforced: the prompts already say a blocking finding forces
    ``changes_required``, and it is the judge's job to have said so.  A recorder
    that re-derived the result would be second-guessing the verdict it exists
    to preserve.
    """

    return any(
        isinstance(item, Mapping) and item.get("severity") == "blocking"
        for item in findings
    )


def editor_decision_findings(findings: Iterable[Any]) -> list[Any]:
    """Every finding a human still has to rule on, in stored order.

    This is the *enforced* one, and unlike :func:`has_blocking_finding` it has
    to be.  A blocking finding already forces ``changes_required`` inside the
    verdict, so a recorder can report it and trust the judge.  An
    ``editor_decision`` finding is compatible with any result the lens likes --
    it has said the defect is real and said it is not the writer's -- so nothing
    in the verdict itself stops an issue shipping with one unresolved.  The
    release gate is the only place that can, so the per-kind
    ``require_approved_*`` refusals in :mod:`magazine.piece_review` and
    :mod:`magazine.edition_review` call this directly, and they name every
    finding it returns rather than counting them: a count is a number an
    operator can clear without reading what is in it.

    Returns the findings rather than a boolean because every caller needs them.
    A predicate would be one line shorter and would have produced exactly the
    refusal message the old bench used to give -- "there are unresolved
    findings" -- which is the sentence that teaches people to stop reading.
    """

    return [
        item
        for item in findings
        if isinstance(item, Mapping) and item.get("disposition") == EDITOR_DECISION
    ]


def has_editor_decision(findings: Iterable[Any]) -> bool:
    """Whether anything here is waiting on a human.  A convenience for reports.

    The gates use :func:`editor_decision_findings` instead, because a refusal
    has to name what it is refusing over.
    """

    return bool(editor_decision_findings(findings))


def describe_finding(finding: Any) -> str:
    """One line naming a finding, for a refusal that has to list several."""

    if not isinstance(finding, Mapping):
        return str(finding).strip().splitlines()[0] if str(finding).strip() else "?"
    severity = str(finding.get("severity") or "?")
    article = str(finding.get("article") or "").strip()
    category = str(finding.get("category") or "unspecified")
    locator = str(finding.get("locator") or "").strip()
    head = f"[{severity}] {category}"
    if article:
        head = f"{article}: {head}"
    if locator:
        head += f" at {locator}"
    return head
