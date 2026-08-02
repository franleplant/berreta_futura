"""Worth-review records: is this better than reading the source.

The lens ``prompts/README.md`` says the old bench was missing entirely.  Every
judge on that bench measured compliance, so ``mcp-in-a-nutshell`` scored 5/4/5/5/5
while being a paraphrase of its source with every method name, every JSON
exchange and every pseudo-code block removed -- 1,900 source words became 1,155,
and for that 40% saving the reader lost everything they would have typed.
Nothing was allowed to notice.  ``worth`` is what notices.

**It reads both sides, and that is what makes it this kind.**  The question is a
relation between the manuscript and the source -- what does our version give a
reader that the original does not -- so the record binds the manuscript *and*
every declared extraction, exactly as ``evidence`` does.  A re-capture genuinely
invalidates the comparison, and the record has to say so.

**It does not run on the editorial.**  The editorial has no source of its own,
so its worth question is whether it says something no single article says, and
``prompts/README.md`` assigns that to ``edition``'s ``single_source_editorial``
and ``thin_derivation``.  Hence :data:`~magazine.piece_review.ARTICLES` rather
than ``PIECES``: a lens asked about a piece it cannot judge would bind bytes
nobody read.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping

from .piece_review import (
    ARTICLES,
    PieceReviewKind,
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


WORTH_REVIEW_SCHEMA_VERSION = 1

WORTH_REVIEW = PieceReviewKind(
    kind="worth",
    label="Worth review",
    covers=ARTICLES,
    schema_version=WORTH_REVIEW_SCHEMA_VERSION,
    supported_versions=(1,),
    binds_extractions=True,
    subject="article",
    reading="reading",
)


def worth_review_path(editions_dir: Path, edition_id: str) -> Path:
    return review_path(editions_dir, edition_id, WORTH_REVIEW.kind)


def current_worth_bindings(
    edition: "Edition", sources_dir: Path, *, require_extractions: bool = False
) -> dict[str, dict[str, Any]]:
    return current_bindings(
        WORTH_REVIEW,
        edition,
        sources_dir=sources_dir,
        require_extractions=require_extractions,
    )


def load_worth_review(path: Path, *, edition_id: str) -> dict[str, Any] | None:
    return load_review(WORTH_REVIEW, path, edition_id=edition_id)


def worth_review_status(
    review: Mapping[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return review_status(WORTH_REVIEW, review, edition_id=edition_id, bindings=bindings)


def create_worth_review(**kwargs: Any) -> dict[str, Any]:
    return create_review(WORTH_REVIEW, **kwargs)


def rebind_articles(
    review: Mapping[str, Any] | None,
    *,
    bindings: Mapping[str, Mapping[str, Any]],
    article_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    return _rebind_articles(
        WORTH_REVIEW, review, bindings=bindings, article_ids=article_ids
    )


def write_worth_review(path: Path, record: Mapping[str, Any]) -> Path:
    return write_review(path, record)


def require_approved_worth_review(
    review: Mapping[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> None:
    require_approved(WORTH_REVIEW, review, edition_id=edition_id, bindings=bindings)
