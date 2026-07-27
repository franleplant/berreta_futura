"""Evidence-review records: the manuscript-versus-source audit, made durable.

The render review binds an independent visual decision to the exact PDFs under
review.  The evidence review is its editorial sibling: an independent audit of
each manuscript against its fidelity ledger and the committed source
extractions (see ``prompts/evidence-review.md``), bound to the exact bytes it
audited.  The record pins, per article, the SHA-256 of the manuscript, of the
fidelity ledger, and -- for every source the article or its ledger declares --
of the extraction body *and* the whole ``extracted.md`` file, so rewriting the
provenance frontmatter (``raw_bundle``, ``extraction_method``) after approval
is as staleness-visible as rewriting the body.  Any change to any bound input
makes the record stale, and ``mag release`` refuses a missing, stale, or
changes-required evidence review.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .errors import ValidationError
from .extraction import EXTRACTION_FILENAME, ledger_source_ids, load_extraction
from .io import load_structured
from .render_review import REVIEW_RESULTS, sha256, write_render_review

if TYPE_CHECKING:
    from .manifest import Edition

_HEX_DIGITS = set("0123456789abcdef")


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

    The covered sources are the union of the article's ``source_ids`` in
    ``edition.yaml`` and the ledger's declared sources, so neither declaration
    can smuggle a source out of the audit.
    """

    bindings: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for article in edition.articles:
        covered = dict.fromkeys(
            (
                *article.source_ids,
                *ledger_source_ids(article.fidelity, load_structured(article.fidelity)),
            )
        )
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
            "ledger_sha256": sha256(article.fidelity),
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
    if data.get("schema_version") != 1:
        errors.append("Evidence review schema_version must be 1")
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
    if not isinstance(findings, list) or any(not str(item).strip() for item in findings):
        errors.append("Evidence review findings must be a list of non-empty strings")
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
        for key in ("manuscript_sha256", "ledger_sha256"):
            if not _is_sha256(row.get(key)):
                errors.append(f"Evidence review article {article_id} has invalid {key}")
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


def evidence_review_status(
    review: dict[str, Any] | None,
    *,
    edition_id: str,
    bindings: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "status": "required_before_release",
        "reviewer": None,
        "reviewed_at": None,
        "result": None,
        "findings": [],
        "articles": bindings,
    }
    if review is None:
        return base
    base.update(
        {
            "reviewer": review.get("reviewer"),
            "reviewed_at": review.get("reviewed_at"),
            "result": review.get("result"),
            "findings": list(review.get("findings", [])),
        }
    )
    if review.get("edition_id") != edition_id or review.get("articles") != bindings:
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
    findings: list[str] | tuple[str, ...] = (),
    notes: str = "",
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    reviewer = reviewer.strip()
    result = result.strip()
    clean_findings = [str(item).strip() for item in findings if str(item).strip()]
    if not reviewer:
        raise ValidationError("Evidence review requires a reviewer")
    if result not in REVIEW_RESULTS:
        raise ValidationError("Evidence review result must be approved or changes_required")
    if result == "changes_required" and not clean_findings:
        raise ValidationError("A changes_required evidence review needs at least one finding")
    if not bindings:
        raise ValidationError("Evidence review requires at least one article to audit")
    timestamp = reviewed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "schema_version": 1,
        "edition_id": edition_id,
        "reviewer": reviewer,
        "reviewed_at": timestamp,
        "result": result,
        "findings": clean_findings,
        "notes": notes.strip(),
        "articles": bindings,
    }


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
        recorded = review.get("articles", {})
        drifted = [
            article_id
            for article_id in sorted(set(recorded) | set(bindings))
            if recorded.get(article_id) != bindings.get(article_id)
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
