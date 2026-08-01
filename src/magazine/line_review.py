"""Line-review records: how a piece *reads*, made durable and bound to bytes.

The evidence review audits a manuscript against the sources it was written
from, so its record binds both.  The line review is the opposite kind of
judgement: ``prompts/line-review.md`` forbids the line editor from opening the
source extraction at all, because a line editor who can see the source starts
fact-checking and stops reading for flow.  That prohibition is not just prompt
etiquette -- it decides the shape of this record.  **A line review binds the
manuscript SHA-256 and nothing else.**  Storing a source hash here would assert
that a source's bytes can invalidate a reading the reviewer was forbidden to
base on them, which would send the line editor back to re-read a piece whose
prose did not move.  Nothing about sources belongs in this binding.

The opening editorial is line-reviewed like any other piece -- the prompt says
so, and it is exactly the kind of text that ships with an orphan referent or a
closing antithesis -- so it is bound under the article id ``editorial``
(:data:`EDITORIAL_ARTICLE_ID`).  An edition with no editorial simply has no
``editorial`` row: that is an ordinary state, not an error.

Staleness is derived *per article*, the way the evidence record derives it:
each recorded row is compared against the same article's current binding, and
the whole derives from the parts -- every article current and the result
approved means approved; any drifted, unrecorded, or removed article means
stale, naming the articles.  A partial re-read (``mag review record --kind line
--articles a,b``) re-binds only the named articles from disk and preserves
every other article's recorded binding, ``reviewed_at``, and scores byte for
byte (see :func:`rebind_articles`).

Scores are per *article* here, not per record: the line editor reads one piece
at a time and scores that piece's structure, flow, sentence craft, house style,
and voice consistency.  They are advisory in the strong sense -- they are
stored, reported, and rolled up, and they never gate and never stale.  See
:data:`_ARTICLE_BINDING_KEYS`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping

from .errors import ValidationError
from .io import load_structured
from .render_review import REVIEW_RESULTS, sha256, write_render_review
from .review_findings import (
    finding_errors,
    normalize_article_scores,
    normalize_findings,
    score_errors,
)

if TYPE_CHECKING:
    from .manifest import Edition

_HEX_DIGITS = set("0123456789abcdef")

LINE_REVIEW_SCHEMA_VERSION = 1

_SUPPORTED_SCHEMA_VERSIONS = (1,)

# The article id the opening editorial is reviewed under.  ``edition.yaml``
# gives the editorial no id of its own -- it is a path, not an article row --
# so the review bench needs one name for it, and the prompt's locator domain
# already uses this one.
EDITORIAL_ARTICLE_ID = "editorial"

# The keys of an article row that *bind*.  Rows also carry review metadata --
# the per-article ``reviewed_at`` and ``scores`` -- which must never participate
# in staleness: when a piece was last read says nothing about whether its bytes
# moved, and neither does what the reader thought of it.  A score that could
# stale a record would be a score that gates, which is exactly what
# ``review_findings`` refuses to let scores become.
_ARTICLE_BINDING_KEYS = ("manuscript_sha256",)


def line_review_path(editions_dir: Path, edition_id: str) -> Path:
    return editions_dir / edition_id / "reviews" / "line.yaml"


def current_line_bindings(edition: "Edition") -> dict[str, dict[str, Any]]:
    """The per-article manuscript hashes a line review binds to, as of now.

    Unlike the evidence bindings this needs no sources directory and no strict
    or lenient mode: everything it binds is a manuscript already on disk, so
    there is nothing that can be missing and nothing to refuse.  The editorial
    joins the mapping under :data:`EDITORIAL_ARTICLE_ID`; an edition that has
    not written one yet simply contributes no row.
    """

    bindings: dict[str, dict[str, Any]] = {}
    for article in edition.articles:
        bindings[article.id] = {"manuscript_sha256": sha256(article.manuscript)}
    if edition.editorial is not None:
        bindings[EDITORIAL_ARTICLE_ID] = {
            "manuscript_sha256": sha256(edition.editorial.path)
        }
    return bindings


def load_line_review(path: Path, *, edition_id: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = load_structured(path)
    errors: list[str] = []
    if data.get("schema_version") not in _SUPPORTED_SCHEMA_VERSIONS:
        errors.append(
            "Line review schema_version must be "
            + " or ".join(str(version) for version in _SUPPORTED_SCHEMA_VERSIONS)
        )
    if data.get("edition_id") != edition_id:
        errors.append(
            f"Line review edition_id {data.get('edition_id')!r} does not match {edition_id!r}"
        )
    if str(data.get("result") or "") not in REVIEW_RESULTS:
        errors.append("Line review result must be approved or changes_required")
    for key in ("reviewer", "reviewed_at"):
        if not str(data.get(key) or "").strip():
            errors.append(f"Line review requires {key}")
    findings = data.get("findings", [])
    errors.extend(finding_errors(findings, label="Line review"))
    if data.get("result") == "changes_required" and not findings:
        errors.append("A changes_required line review needs at least one finding")
    articles = data.get("articles")
    if not isinstance(articles, dict) or not articles:
        errors.append("Line review requires an articles mapping")
        articles = {}
    for article_id, row in articles.items():
        if not isinstance(row, dict):
            errors.append(f"Line review article {article_id} must be a mapping")
            continue
        if not _is_sha256(row.get("manuscript_sha256")):
            errors.append(f"Line review article {article_id} has invalid manuscript_sha256")
        # Per-article ``reviewed_at`` and ``scores`` are additive and optional:
        # a record written before either existed is still a valid record (the
        # record-level timestamp stands in, and an unscored piece is normal).
        # Present-but-empty is not the same thing and is refused.
        if "reviewed_at" in row and not str(row.get("reviewed_at") or "").strip():
            errors.append(
                f"Line review article {article_id} reviewed_at must be a "
                "non-empty string when present"
            )
        errors.extend(
            score_errors(row.get("scores"), label=f"Line review article {article_id}")
        )
    if errors:
        raise ValidationError(errors)
    return dict(data)


def _is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and set(text) <= _HEX_DIGITS


def _recorded_binding(row: dict[str, Any]) -> dict[str, Any]:
    """The comparable slice of a recorded article row: the hash, not the verdict."""

    return {key: row.get(key) for key in _ARTICLE_BINDING_KEYS}


def article_drift(recorded: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Name which of one article's bound inputs no longer matches disk.

    There is only ever one: ``manuscript``.  The function keeps the evidence
    record's list-of-names shape anyway, because the CLI renders both kinds
    through the same column and because a one-element list reads honestly as
    "here is everything that moved".
    """

    drift: list[str] = []
    if recorded.get("manuscript_sha256") != current.get("manuscript_sha256"):
        drift.append("manuscript")
    return drift


def line_review_status(
    review: dict[str, Any] | None,
    *,
    edition_id: str,
    bindings: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Derive the review's standing per article, then the whole from the parts.

    ``articles`` reports, for every article the edition or the record knows,
    whether its recorded manuscript hash still matches disk:

    - ``current``: the manuscript is the one that was read; ``reviewed_at``
      says when (falling back to the record's own timestamp).
    - ``drifted``: the manuscript moved; ``drift`` names it.
    - ``unrecorded``: the edition has the piece but the record never bound it
      (it was written after the read).
    - ``removed``: the record bound a piece the edition no longer carries.
    - ``unreviewed``: no record exists at all.

    A recorded row's ``scores`` travel out through the per-article entry: the
    status mapping is how the CLI and ``mag scores`` see a record, so a score
    that did not travel would be a score nobody could read.
    """

    articles: dict[str, Any] = {}
    base: dict[str, Any] = {
        "status": "required_before_release",
        "reviewer": None,
        "reviewed_at": None,
        "result": None,
        "findings": [],
        "articles": articles,
    }
    if review is None:
        for article_id in bindings:
            articles[article_id] = {"status": "unreviewed", "reviewed_at": None}
        return base
    base.update(
        {
            "reviewer": review.get("reviewer"),
            "reviewed_at": review.get("reviewed_at"),
            "result": review.get("result"),
            "findings": list(review.get("findings", [])),
        }
    )
    recorded = review.get("articles") or {}
    fallback_reviewed_at = review.get("reviewed_at")
    any_drift = False
    for article_id in sorted(set(bindings) | set(recorded)):
        row = recorded.get(article_id)
        current = bindings.get(article_id)
        if not isinstance(row, dict):
            articles[article_id] = {"status": "unrecorded", "reviewed_at": None}
            any_drift = True
            continue
        entry: dict[str, Any] = {
            "reviewed_at": row.get("reviewed_at") or fallback_reviewed_at
        }
        if row.get("scores"):
            entry["scores"] = dict(row["scores"])
        if current is None:
            entry["status"] = "removed"
            any_drift = True
        else:
            drift = article_drift(row, current)
            if drift:
                entry["status"] = "drifted"
                entry["drift"] = drift
                any_drift = True
            else:
                entry["status"] = "current"
        articles[article_id] = entry
    if review.get("edition_id") != edition_id or any_drift:
        base["status"] = "stale"
    elif review.get("result") == "approved":
        base["status"] = "approved"
    else:
        base["status"] = "changes_required"
    return base


def create_line_review(
    *,
    edition_id: str,
    reviewer: str,
    result: str,
    bindings: dict[str, dict[str, Any]],
    findings: Iterable[Any] = (),
    scores: Mapping[str, Mapping[str, int]] | None = None,
    notes: str = "",
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    reviewer = reviewer.strip()
    result = result.strip()
    clean_findings = normalize_findings(findings, label="Line review")
    if not reviewer:
        raise ValidationError("Line review requires a reviewer")
    if result not in REVIEW_RESULTS:
        raise ValidationError("Line review result must be approved or changes_required")
    if result == "changes_required" and not clean_findings:
        raise ValidationError("A changes_required line review needs at least one finding")
    if not bindings:
        raise ValidationError("Line review requires at least one article to read")
    parsed_scores = normalize_article_scores(
        scores, label="Line review", article_ids=bindings
    )
    timestamp = reviewed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    # Every article row records when *it* was read.  Rows arriving without a
    # stamp were read now (a full record, or the re-bound articles of a partial
    # one); rows that already carry one are preserved bindings whose reading
    # history must survive the re-record (see rebind_articles).
    articles: dict[str, dict[str, Any]] = {
        article_id: {"reviewed_at": timestamp, **row} for article_id, row in bindings.items()
    }
    for article_id, row_scores in parsed_scores.items():
        if row_scores:
            articles[article_id]["scores"] = row_scores
    return {
        "schema_version": LINE_REVIEW_SCHEMA_VERSION,
        "edition_id": edition_id,
        "reviewer": reviewer,
        "reviewed_at": timestamp,
        "result": result,
        "findings": clean_findings,
        "notes": notes.strip(),
        "articles": articles,
    }


def rebind_articles(
    review: dict[str, Any] | None,
    *,
    bindings: dict[str, dict[str, Any]],
    article_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    """Merge a partial re-read into an existing record's bindings.

    ``--articles`` names the pieces that were actually read again; those are
    re-bound from ``bindings`` (current disk state) and will be stamped with the
    new record's timestamp by :func:`create_line_review`.  Every other article
    in the edition keeps its recorded binding, its recorded ``reviewed_at``,
    *and* its recorded ``scores``, so an untouched piece's reading survives the
    re-record intact and a drifted-but-unnamed piece stays visibly drifted
    rather than being silently re-blessed by a read that never happened.

    The edition's current article list is the universe: recorded articles that
    left the edition simply fall out of the new record, and an article that is
    in the edition but neither named nor previously recorded is refused --
    there is no reading, old or new, to carry for it.
    """

    requested = [str(item).strip() for item in article_ids if str(item).strip()]
    if not requested:
        raise ValidationError("A partial line re-record requires at least one article id")
    if review is None:
        raise ValidationError(
            "A partial line re-record amends an existing record, and none "
            "exists; record the full review first with "
            "`mag review record --kind line`"
        )
    unknown = sorted(set(requested) - set(bindings))
    if unknown:
        raise ValidationError(
            "Cannot re-bind articles the edition does not carry: " + ", ".join(unknown)
        )
    recorded = review.get("articles") or {}
    fallback_reviewed_at = review.get("reviewed_at")
    merged: dict[str, dict[str, Any]] = {}
    unbound: list[str] = []
    named = set(requested)
    for article_id, current in bindings.items():
        if article_id in named:
            merged[article_id] = dict(current)
        elif isinstance(recorded.get(article_id), dict):
            row = recorded[article_id]
            preserved: dict[str, Any] = {
                "reviewed_at": row.get("reviewed_at") or fallback_reviewed_at
            }
            preserved.update(_recorded_binding(row))
            # The scores belong to the reading that produced them; a re-record
            # that dropped them would quietly erase an untouched piece's
            # measurement along with nothing else.
            if row.get("scores"):
                preserved["scores"] = dict(row["scores"])
            merged[article_id] = preserved
        else:
            unbound.append(article_id)
    if unbound:
        raise ValidationError(
            "Articles have no recorded review to preserve: "
            + ", ".join(unbound)
            + "; name them in --articles or record the full review"
        )
    return merged


def write_line_review(path: Path, record: dict[str, Any]) -> Path:
    # The render review's writer is a generic atomic YAML replacement; the line
    # record shares it rather than growing a third one.
    return write_render_review(path, record)


def require_approved_line_review(
    review: dict[str, Any] | None,
    *,
    edition_id: str,
    bindings: dict[str, dict[str, Any]],
) -> None:
    """The release gate for a line review, written but deliberately not wired.

    Nothing in the release path calls this yet: the prompt's severities are
    still being calibrated against edition 4, and turning a gate on before the
    judge agrees with a human about what ``blocking`` means would block a
    release over a taste dispute.  The function exists so the calibration has a
    gate to switch on; flipping it on is a follow-up.
    """

    status = line_review_status(review, edition_id=edition_id, bindings=bindings)
    if status["status"] == "approved":
        return
    detail = f"line review is {status['status']}"
    if status["status"] == "stale" and review is not None:
        # The per-article rows already say exactly what moved; the error names
        # the articles so the refusal doubles as the re-read worklist.
        drifted = [
            article_id
            for article_id, row in status["articles"].items()
            if row.get("status") != "current"
        ]
        if drifted:
            detail += "; changed since the recorded review: " + ", ".join(drifted)
    raise ValidationError(
        [
            "Release requires a current approved line review recorded with "
            "`mag review record --kind line`.",
            detail,
        ]
    )
