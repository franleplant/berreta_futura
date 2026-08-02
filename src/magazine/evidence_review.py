"""Evidence-review records: the manuscript-versus-source audit, made durable.

An independent audit of each manuscript against the committed source extractions
(see ``prompts/evidence-review.md``), bound to the exact bytes it audited: per
piece, the SHA-256 of the manuscript and -- for every source the piece declares
in ``edition.yaml`` -- of the extraction body *and* the whole ``extracted.md``
file, so rewriting the provenance frontmatter (``raw_bundle``,
``extraction_method``) after approval is as staleness-visible as rewriting the
body.

**The kind name is deliberately unchanged.**  ``prompts/README.md`` split the
old two-judge bench into seven narrow lenses and rewrote this prompt in place,
narrowing it to one question -- is every claim in this piece the source's claim
-- and moving what did not belong to ``worth``, ``shape``, ``craft`` and
``mechanics``.  The concern is the same one and the name is load-bearing in
``src/`` and in committed review records, so ``evidence`` stays ``evidence``.
Renaming it would have voided every shipped record to describe a narrowing.

**The record shape lives in** :mod:`magazine.piece_review`.  Everything below is
this kind's declaration -- what it binds, which pieces it covers, which schema
versions still load -- plus the thin functions the rest of the package already
imports by name.  The loading, staleness, partial re-record and atomic write are
the bench's shared ones; this module grew its own once, ``line_review`` grew a
near-identical second, and seven lenses were not going to be seven copies.

**Version history, and why old records still load.**

Version 1 additionally bound the SHA-256 of a per-article fidelity ledger, a
file that no longer exists.  Those records still load and the ledger binding is
ignored rather than treated as drift; re-blessing every shipped edition would
have been a worse answer than reading the old records for the part of them that
is still true.

Version 2 dropped the ledger.  Version 3 changed what a *finding* is: versions 1
and 2 stored a finding as a string, because the only findings anyone wrote were
sentences typed into ``--finding``, and the old recorder flattened a mapping
through ``str(item).strip()`` into a line of Python repr nothing could read
back.  Version 3 also added an advisory ``scores`` map to each article row.

Version 4 adds ``disposition`` to every authored finding.  That is the field
``prompts/README.md`` uses to replace the severity cap -- severity describes the
defect, disposition says who repairs it -- and a parser that dropped it would
reintroduce the bug the cap caused.  As with every bump before it, the older
shapes still load: a finding stored before the field existed is read as it was
written rather than refused, and :mod:`magazine.review_findings` requires the
field only of a finding being *authored*.  The bump exists so that "a version 3
record" continues to name exactly one shape, not to force a re-audit.

Every finding this lens files is ``disposition: fix`` by its prompt's own rule --
the lens measures the manuscript against the source and a false claim is never
the author's voice to keep -- so in practice the field is constant here.  It is
still required, because a lens that could omit it is a lens whose findings the
composer cannot route.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping

from .piece_review import (
    ARTICLES,
    PieceReviewKind,
    article_drift as _article_drift,
    create_review,
    current_bindings,
    load_review,
    rebind_articles as _rebind_articles,
    require_approved,
    review_path,
    review_status,
    write_review,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .manifest import Edition


EVIDENCE_REVIEW_SCHEMA_VERSION = 4

EVIDENCE_REVIEW = PieceReviewKind(
    kind="evidence",
    label="Evidence review",
    # Articles rather than pieces: the editorial declares no ``source_ids``, so
    # there is nothing to bind for it.  The fact-checker still *reads* it -- its
    # sources are the edition's own article manuscripts, which
    # ``prompts/evidence-review.md`` says explicitly -- and its findings still
    # travel, record-level.  Only the hash binding is per article.
    covers=ARTICLES,
    schema_version=EVIDENCE_REVIEW_SCHEMA_VERSION,
    # 1 bound a fidelity ledger that no longer exists; 1 and 2 stored findings
    # as strings; 3 predates ``disposition``.  All four load.
    supported_versions=(1, 2, 3, 4),
    binds_extractions=True,
    subject="article",
    reading="audit",
)


def evidence_review_path(editions_dir: Path, edition_id: str) -> Path:
    return review_path(editions_dir, edition_id, EVIDENCE_REVIEW.kind)


def current_evidence_bindings(
    edition: "Edition", sources_dir: Path, *, require_extractions: bool
) -> dict[str, dict[str, Any]]:
    """The per-article hashes an evidence review binds to, as of right now.

    ``require_extractions`` is true at record time: a review cannot claim to
    have audited a manuscript against an extraction that does not exist.  The
    lenient form serves status and gate checks, where a missing extraction
    simply cannot match the recorded hash and surfaces as staleness.

    The covered sources are the article's ``source_ids`` in ``edition.yaml``,
    which is the single place an article declares what it was written from --
    and the same list its ``source_body_sha256`` pins, so the audit cannot cover
    a different set of sources than validation does.
    """

    return current_bindings(
        EVIDENCE_REVIEW,
        edition,
        sources_dir=sources_dir,
        require_extractions=require_extractions,
    )


def load_evidence_review(path: Path, *, edition_id: str) -> dict[str, Any] | None:
    return load_review(EVIDENCE_REVIEW, path, edition_id=edition_id)


def article_drift(recorded: Mapping[str, Any], current: Mapping[str, Any]) -> list[str]:
    """Name exactly which of one article's bound inputs no longer match disk.

    ``manuscript`` for the article's own file, ``extraction:<source-id>`` for
    any extraction whose body or file hash moved (or that appeared or vanished
    from the covered set).  A version 1 record's ``ledger_sha256`` is not
    compared: the file it bound no longer exists, and reporting its absence as
    drift would demand a re-audit of shipped editions that nothing has actually
    invalidated.
    """

    return _article_drift(EVIDENCE_REVIEW, recorded, current)


def evidence_review_status(
    review: Mapping[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return review_status(
        EVIDENCE_REVIEW, review, edition_id=edition_id, bindings=bindings
    )


def create_evidence_review(**kwargs: Any) -> dict[str, Any]:
    return create_review(EVIDENCE_REVIEW, **kwargs)


def rebind_articles(
    review: Mapping[str, Any] | None,
    *,
    bindings: Mapping[str, Mapping[str, Any]],
    article_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    return _rebind_articles(
        EVIDENCE_REVIEW, review, bindings=bindings, article_ids=article_ids
    )


def write_evidence_review(path: Path, record: Mapping[str, Any]) -> Path:
    return write_review(path, record)


def require_approved_evidence_review(
    review: Mapping[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> None:
    require_approved(EVIDENCE_REVIEW, review, edition_id=edition_id, bindings=bindings)
