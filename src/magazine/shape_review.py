"""Shape-review records: is the piece in the right order.

The second of the three lenses ``prompts/line-review.md`` split into.  Its
concern is arrangement -- argument order, duplication inside a piece, orphan
referents, one running example, where the piece opens and where it ends -- and
nothing else.

**It binds the manuscript and nothing else.**  Every check it makes is
answerable from the manuscript alone, which is precisely the assignment rule
``prompts/README.md`` states: a check about the *relationship* between manuscript
and source belongs to a lens that reads both.  The check that used to sit here
and could not be answered blind -- "headings mirror the source's table of
contents" -- moved to ``worth``, where the source is open.  It is not merely that
this lens is forbidden the source; it is that nothing it is asked needs one, so
binding one would create staleness with no signal in it.

**Craft runs after this one, never before.**  Structural repair destroys
sentence work, so ``prompts/README.md`` puts ``shape`` in stage 2 and ``craft``
in stage 3.  That ordering lives in
:data:`~magazine.produce_graph.PIECE_JUDGE_LENSES`; this module only has to
agree with it, which it does by binding the same bytes and staling together.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping

from .piece_review import (
    PIECES,
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


SHAPE_REVIEW_SCHEMA_VERSION = 1

SHAPE_REVIEW = PieceReviewKind(
    kind="shape",
    label="Shape review",
    covers=PIECES,
    schema_version=SHAPE_REVIEW_SCHEMA_VERSION,
    supported_versions=(1,),
    subject="piece",
    reading="reading",
)


def shape_review_path(editions_dir: Path, edition_id: str) -> Path:
    return review_path(editions_dir, edition_id, SHAPE_REVIEW.kind)


def current_shape_bindings(edition: "Edition") -> dict[str, dict[str, Any]]:
    """The per-piece manuscript hashes this lens binds to, as of now."""

    return current_bindings(SHAPE_REVIEW, edition)


def load_shape_review(path: Path, *, edition_id: str) -> dict[str, Any] | None:
    return load_review(SHAPE_REVIEW, path, edition_id=edition_id)


def shape_review_status(
    review: Mapping[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return review_status(SHAPE_REVIEW, review, edition_id=edition_id, bindings=bindings)


def create_shape_review(**kwargs: Any) -> dict[str, Any]:
    return create_review(SHAPE_REVIEW, **kwargs)


def rebind_articles(
    review: Mapping[str, Any] | None,
    *,
    bindings: Mapping[str, Mapping[str, Any]],
    article_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    return _rebind_articles(
        SHAPE_REVIEW, review, bindings=bindings, article_ids=article_ids
    )


def write_shape_review(path: Path, record: Mapping[str, Any]) -> Path:
    return write_review(path, record)


def require_approved_shape_review(
    review: Mapping[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> None:
    require_approved(SHAPE_REVIEW, review, edition_id=edition_id, bindings=bindings)
