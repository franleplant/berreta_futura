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

Two rules hold across the whole bench:

* **A finding is stored as authored.**  Known keys are written in a fixed
  order so records diff cleanly, unknown keys are preserved rather than
  dropped, and a plain string stays a plain string -- ``--finding "..."`` is
  still how a human types one, and every record written before this module
  existed is full of them.
* **A score never gates.**  Scores are parsed, bounded to the prompts' 1-5, and
  exposed; nothing in this package reads one to decide anything.  A gated score
  invites generous scoring, which would cost more than the measurement is
  worth.  They exist to be rolled up by ``mag scores`` and looked at.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .errors import ValidationError


FINDING_SEVERITIES = ("blocking", "major", "minor")

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
FINDING_KEYS = (
    "severity",
    "article",
    "locator",
    "repair_from",
    "category",
    "persona",
    "note",
    "suggestion",
)

# Every prompt requires these two of a structured finding: without a severity
# the finding cannot be triaged, and without a note it says nothing.
DEFAULT_REQUIRED_FINDING_KEYS = ("severity", "note")

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
    required: tuple[str, ...] = DEFAULT_REQUIRED_FINDING_KEYS,
) -> list[str]:
    """The same checks as :func:`normalize_findings`, as a list of errors.

    Loading a record accumulates every complaint about the file before raising,
    so it cannot use the normalizer's own raise.  A record that predates
    structured findings must still load: a string finding passes here exactly
    as it always did.
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
    persona = values.get("persona")
    if persona is not None and not persona:
        errors.append(f"{label} finding {index} persona must be a non-empty string")
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
