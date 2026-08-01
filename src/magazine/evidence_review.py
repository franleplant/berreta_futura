"""Evidence-review records: the manuscript-versus-source audit, made durable.

The render review binds an independent visual decision to the exact PDFs under
review.  The evidence review is its editorial sibling: an independent audit of
each manuscript against the committed source extractions (see
``prompts/evidence-review.md``), bound to the exact bytes it audited.  The
record pins, per article, the SHA-256 of the manuscript and -- for every source
the article declares in ``edition.yaml`` -- of the extraction body *and* the
whole ``extracted.md`` file, so rewriting the provenance frontmatter
(``raw_bundle``, ``extraction_method``) after approval is as staleness-visible
as rewriting the body.

Staleness is derived *per article*: each recorded article row is compared
against the same article's current bindings, and the overall status derives
from those comparisons -- every article current and the result approved means
approved; any drifted, unrecorded, or removed article means stale, naming the
articles (and, per article, which bound input moved).  The release gate keeps
the whole-edition strictness -- one drifted article still refuses release --
but a re-audit no longer has to repeat itself: ``mag review record --kind
evidence --articles a,b`` re-binds only the named articles from disk and
preserves every other article's recorded binding and ``reviewed_at`` byte for
byte (see :func:`rebind_articles`).

Version 2 records bind those two things and nothing else.  Version 1 records
additionally bound the SHA-256 of a per-article fidelity ledger, a file that no
longer exists; they still load, and their ledger binding is simply ignored
rather than treated as drift.  Re-blessing every shipped edition would have
been a worse answer than reading the old records for the part of them that is
still true -- the manuscript and extraction bindings, which are the audit's
actual subject.  Per-article ``reviewed_at`` is likewise additive and optional,
so records written before it existed report the record-level timestamp for
every article.

Version 3 changes what a *finding* is.  Versions 1 and 2 stored a finding as a
string, because the only findings anyone wrote were sentences typed into
``--finding``.  The fact-checker prompt emits something richer -- a severity,
the article, a locator naming the exact sentence, a category, and a note -- and
the old recorder flattened a mapping through ``str(item).strip()`` into a line
of Python repr nothing could read back.  :mod:`magazine.review_findings` now
owns the shape, and a version 3 record stores structured findings and plain
strings side by side.  Version 3 also adds an advisory ``scores`` map to each
article row: the fact-checker reads one article at a time, so its 1-5
dimensions belong to the article rather than the record, and a partial
re-record must leave every other article's scores exactly where they were.
Scores gate nothing anywhere in this package -- a gated score invites generous
scoring, which would cost more than the measurement is worth.

Versions 1 and 2 still load unchanged.  A string finding is as valid at version
3 as it ever was, so the shipped records need no rewrite and no re-audit; the
bump exists so that "a version 2 record" continues to name exactly one shape.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping

from .errors import ValidationError
from .extraction import EXTRACTION_FILENAME, load_extraction
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

EVIDENCE_REVIEW_SCHEMA_VERSION = 3

_REVIEW_LABEL = "Evidence review"

# Version 1 recorded a third binding, ``ledger_sha256``, over the per-article
# fidelity ledger.  Loading still accepts those records; nothing reads that key.
# Versions 1 and 2 stored findings as strings only; version 3 stores structured
# findings and advisory per-article scores.  All three load.
_SUPPORTED_SCHEMA_VERSIONS = (1, 2, 3)

# The keys of an article row that *bind*.  Rows also carry audit metadata --
# the per-article ``reviewed_at``, and the advisory ``scores`` -- which must
# never participate in staleness: when an article was last audited, and how a
# judge rated it, say nothing about whether its bytes moved.
_ARTICLE_BINDING_KEYS = ("manuscript_sha256", "source_extractions")


def evidence_review_path(editions_dir: Path, edition_id: str) -> Path:
    return editions_dir / edition_id / "reviews" / "evidence.yaml"


def current_evidence_bindings(
    edition: "Edition", sources_dir: Path, *, require_extractions: bool
) -> dict[str, dict[str, Any]]:
    """The per-article hashes an evidence review binds to, as of right now.

    ``require_extractions`` is true at record time: a review cannot claim to
    have audited a manuscript against an extraction that does not exist.  The
    lenient form serves status and gate checks, where a missing extraction
    simply cannot match the recorded hash and surfaces as staleness.

    The covered sources are the article's ``source_ids`` in ``edition.yaml``,
    which is now the single place an article declares what it was written from
    -- and the same list its ``source_body_sha256`` pins, so the audit cannot
    cover a different set of sources than validation does.
    """

    bindings: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for article in edition.articles:
        covered = dict.fromkeys(article.source_ids)
        source_extractions: dict[str, dict[str, str]] = {}
        for source_id in covered:
            extraction = load_extraction(sources_dir, source_id)
            if extraction is None:
                if require_extractions:
                    errors.append(
                        f"Evidence review requires a committed extraction for source "
                        f"{source_id} (article {article.id}); add "
                        f"library/sources/{source_id}/{EXTRACTION_FILENAME}"
                    )
                continue
            source_extractions[source_id] = {
                "body_sha256": extraction.body_sha256,
                "file_sha256": extraction.file_sha256,
            }
        bindings[article.id] = {
            "manuscript_sha256": sha256(article.manuscript),
            "source_extractions": source_extractions,
        }
    if errors:
        raise ValidationError(errors)
    return bindings


def load_evidence_review(path: Path, *, edition_id: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = load_structured(path)
    errors: list[str] = []
    if data.get("schema_version") not in _SUPPORTED_SCHEMA_VERSIONS:
        errors.append(
            "Evidence review schema_version must be "
            + _supported_versions_phrase()
        )
    if data.get("edition_id") != edition_id:
        errors.append(
            f"Evidence review edition_id {data.get('edition_id')!r} does not match {edition_id!r}"
        )
    if str(data.get("result") or "") not in REVIEW_RESULTS:
        errors.append("Evidence review result must be approved or changes_required")
    for key in ("reviewer", "reviewed_at"):
        if not str(data.get(key) or "").strip():
            errors.append(f"Evidence review requires {key}")
    findings = data.get("findings", [])
    errors.extend(finding_errors(findings, label=_REVIEW_LABEL))
    if data.get("result") == "changes_required" and not findings:
        errors.append("A changes_required evidence review needs at least one finding")
    articles = data.get("articles")
    if not isinstance(articles, dict) or not articles:
        errors.append("Evidence review requires an articles mapping")
        articles = {}
    for article_id, row in articles.items():
        if not isinstance(row, dict):
            errors.append(f"Evidence review article {article_id} must be a mapping")
            continue
        if not _is_sha256(row.get("manuscript_sha256")):
            errors.append(
                f"Evidence review article {article_id} has invalid manuscript_sha256"
            )
        # Per-article ``reviewed_at`` postdates edition 003's record, so its
        # absence is legal (the record-level timestamp stands in); an empty
        # value is not.
        if "reviewed_at" in row and not str(row.get("reviewed_at") or "").strip():
            errors.append(
                f"Evidence review article {article_id} reviewed_at must be a "
                "non-empty string when present"
            )
        # Advisory only, and additive: a version 1 or 2 row has no scores, and
        # a version 3 row need not have any either.
        errors.extend(
            score_errors(
                row.get("scores"), label=f"{_REVIEW_LABEL} article {article_id}"
            )
        )
        extractions = row.get("source_extractions")
        if not isinstance(extractions, dict) or not extractions:
            errors.append(
                f"Evidence review article {article_id} requires a source_extractions mapping"
            )
            continue
        for source_id, value in extractions.items():
            if (
                not isinstance(value, dict)
                or not _is_sha256(value.get("body_sha256"))
                or not _is_sha256(value.get("file_sha256"))
            ):
                errors.append(
                    f"Evidence review article {article_id} extraction binding for "
                    f"{source_id} requires body_sha256 and file_sha256"
                )
    if errors:
        raise ValidationError(errors)
    return dict(data)


def _is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and set(text) <= _HEX_DIGITS


def _supported_versions_phrase() -> str:
    versions = [str(version) for version in _SUPPORTED_SCHEMA_VERSIONS]
    if len(versions) < 3:
        return " or ".join(versions)
    return ", ".join(versions[:-1]) + f", or {versions[-1]}"


def _recorded_binding(row: dict[str, Any]) -> dict[str, Any]:
    """The comparable slice of a recorded article row: hashes, not metadata."""

    return {key: row.get(key) for key in _ARTICLE_BINDING_KEYS}


def article_drift(recorded: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Name exactly which of one article's bound inputs no longer match disk.

    The names are for the human deciding what to re-audit: ``manuscript`` for
    the article's own file, ``extraction:<source-id>`` for any extraction whose
    body or file hash moved (or that appeared or vanished from the covered
    set).  A version 1 record's ``ledger_sha256`` is not compared: the file it
    bound no longer exists, and reporting its absence as drift would demand a
    re-audit of shipped editions that nothing has actually invalidated.
    """

    drift: list[str] = []
    if recorded.get("manuscript_sha256") != current.get("manuscript_sha256"):
        drift.append("manuscript")
    recorded_extractions = recorded.get("source_extractions") or {}
    current_extractions = current.get("source_extractions") or {}
    for source_id in sorted(set(recorded_extractions) | set(current_extractions)):
        if recorded_extractions.get(source_id) != current_extractions.get(source_id):
            drift.append(f"extraction:{source_id}")
    return drift


def evidence_review_status(
    review: dict[str, Any] | None,
    *,
    edition_id: str,
    bindings: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Derive the review's standing per article, then the whole from the parts.

    ``articles`` reports, for every article the edition or the record knows,
    whether its recorded binding still matches disk:

    - ``current``: every bound hash matches; ``reviewed_at`` says when this
      article was last audited (falling back to the record's timestamp for
      rows written before per-article stamps existed).
    - ``drifted``: some bound input changed; ``drift`` names which.
    - ``unrecorded``: the edition has the article but the record never bound
      it (it joined the edition after the audit).
    - ``removed``: the record bound an article the edition no longer carries.
    - ``unreviewed``: no record exists at all.

    Any article that is not ``current`` makes the whole record stale; the
    release gate stays exactly as strict as the old whole-mapping comparison,
    but the drift is now attributable article by article.
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
        # Scores travel out with the row because status is how the CLI exposes
        # them.  They are reported, never read: nothing downstream branches on
        # a score, here or anywhere else.
        if isinstance(row.get("scores"), dict) and row["scores"]:
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


def create_evidence_review(
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
    clean_findings = normalize_findings(findings, label=_REVIEW_LABEL)
    if not reviewer:
        raise ValidationError("Evidence review requires a reviewer")
    if result not in REVIEW_RESULTS:
        raise ValidationError("Evidence review result must be approved or changes_required")
    if result == "changes_required" and not clean_findings:
        raise ValidationError("A changes_required evidence review needs at least one finding")
    if not bindings:
        raise ValidationError("Evidence review requires at least one article to audit")
    # The fact-checker verifies one article against its sources, so its 1-5
    # dimensions are a fact about that article.  Scores named here overwrite a
    # preserved row's; scores omitted leave whatever the row carried in place,
    # which is what a partial re-audit of another article should do.
    parsed_scores = normalize_article_scores(
        scores, label=_REVIEW_LABEL, article_ids=bindings
    )
    timestamp = reviewed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    # Every article row records when *it* was audited.  Rows arriving without
    # a stamp were audited now (a full record, or the re-bound articles of a
    # partial one); rows that already carry one are preserved bindings whose
    # audit history must survive the re-record (see rebind_articles).
    articles: dict[str, dict[str, Any]] = {}
    for article_id, row in bindings.items():
        entry: dict[str, Any] = {"reviewed_at": timestamp, **row}
        row_scores = parsed_scores.get(article_id) or entry.get("scores")
        if row_scores:
            entry["scores"] = dict(row_scores)
        else:
            entry.pop("scores", None)
        articles[article_id] = entry
    return {
        "schema_version": EVIDENCE_REVIEW_SCHEMA_VERSION,
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
    """Merge a partial re-audit into an existing record's bindings.

    ``--articles`` names the articles whose audit was actually repeated; those
    are re-bound from ``bindings`` (current disk state) and will be stamped
    with the new record's timestamp by :func:`create_evidence_review`.  Every
    other article in the edition keeps its recorded binding *and* its recorded
    ``reviewed_at`` unchanged, so an untouched article's approval history
    survives the re-record and a drifted-but-unnamed article stays visibly
    drifted rather than being silently re-blessed.

    The edition's current article list is the universe: recorded articles that
    left the edition simply fall out of the new record, and an article that is
    in the edition but neither named nor previously recorded is refused --
    there is no audit, old or new, to carry for it.
    """

    requested = [str(item).strip() for item in article_ids if str(item).strip()]
    if not requested:
        raise ValidationError(
            "A partial evidence re-record requires at least one article id"
        )
    if review is None:
        raise ValidationError(
            "A partial evidence re-record amends an existing record, and none "
            "exists; record the full audit first with "
            "`mag review record --kind evidence`"
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
            # An untouched article's advisory scores are as much recorded
            # history as its timestamp: the judge rated that manuscript, and
            # re-auditing a sibling did not change the rating.
            if isinstance(row.get("scores"), dict) and row["scores"]:
                preserved["scores"] = dict(row["scores"])
            merged[article_id] = preserved
        else:
            unbound.append(article_id)
    if unbound:
        raise ValidationError(
            "Articles have no recorded audit to preserve: "
            + ", ".join(unbound)
            + "; name them in --articles or record the full audit"
        )
    return merged


def write_evidence_review(path: Path, record: dict[str, Any]) -> Path:
    # The render review's writer is a generic atomic YAML replacement; the
    # evidence record shares it rather than growing a second one.
    return write_render_review(path, record)


def require_approved_evidence_review(
    review: dict[str, Any] | None,
    *,
    edition_id: str,
    bindings: dict[str, dict[str, Any]],
) -> None:
    status = evidence_review_status(review, edition_id=edition_id, bindings=bindings)
    if status["status"] == "approved":
        return
    detail = f"evidence review is {status['status']}"
    if status["status"] == "stale" and review is not None:
        # The per-article rows already say exactly what moved; the error names
        # the articles so the refusal doubles as the re-audit worklist.
        drifted = [
            article_id
            for article_id, row in status["articles"].items()
            if row.get("status") != "current"
        ]
        if drifted:
            detail += "; changed since the recorded audit: " + ", ".join(drifted)
    raise ValidationError(
        [
            "Release requires a current approved evidence review recorded with "
            "`mag review record --kind evidence`.",
            detail,
        ]
    )
