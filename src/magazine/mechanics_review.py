"""Mechanics-review records: is the English correct as typeset.

One of the three lenses ``prompts/line-review.md`` split into.  The old judge
held seven concerns at once -- structure, transitions, sentence craft, house
style, voice, cadence and explainer shape -- and attention spread over seven
catches less than attention on one, which is how twelve broken sentence openings
and a subject-verb error shipped under a verdict of ``approved``.  This lens
holds exactly one: typography, heading form, banned characters, missing labels,
capitalisation, grammar.

**It binds the manuscript and nothing else.**  ``prompts/mechanics-review.md``
forbids opening the source, and the record has to agree: storing a source hash
here would assert that a source's bytes can invalidate a reading the reviewer was
forbidden to base on them, and would send this lens back to re-read a piece whose
prose did not move.  The prohibition is a fact about the binding, not only about
the prompt.

**It is the lens with no discount.**  Capitalisation and grammar are never voice,
so nothing here is capped, softened or dropped because a sentence is the source
author's own: it files at true severity and routes with ``disposition``.  That
routing is the whole reason :mod:`magazine.review_findings` makes the field
required -- a mechanics record that lost it would be the severity cap back under
a new name.
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


MECHANICS_REVIEW_SCHEMA_VERSION = 1

MECHANICS_REVIEW = PieceReviewKind(
    kind="mechanics",
    label="Mechanics review",
    covers=PIECES,
    schema_version=MECHANICS_REVIEW_SCHEMA_VERSION,
    supported_versions=(1,),
    subject="piece",
    reading="reading",
)


def mechanics_review_path(editions_dir: Path, edition_id: str) -> Path:
    return review_path(editions_dir, edition_id, MECHANICS_REVIEW.kind)


def current_mechanics_bindings(edition: "Edition") -> dict[str, dict[str, Any]]:
    """The per-piece manuscript hashes this lens binds to, as of now.

    Unlike the source-reading kinds this needs no sources directory and no
    strict or lenient mode: everything it binds is a manuscript already on disk,
    so there is nothing that can be missing and nothing to refuse.
    """

    return current_bindings(MECHANICS_REVIEW, edition)


def load_mechanics_review(path: Path, *, edition_id: str) -> dict[str, Any] | None:
    return load_review(MECHANICS_REVIEW, path, edition_id=edition_id)


def mechanics_review_status(
    review: Mapping[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return review_status(
        MECHANICS_REVIEW, review, edition_id=edition_id, bindings=bindings
    )


def create_mechanics_review(**kwargs: Any) -> dict[str, Any]:
    return create_review(MECHANICS_REVIEW, **kwargs)


def rebind_articles(
    review: Mapping[str, Any] | None,
    *,
    bindings: Mapping[str, Mapping[str, Any]],
    article_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    return _rebind_articles(
        MECHANICS_REVIEW, review, bindings=bindings, article_ids=article_ids
    )


def write_mechanics_review(path: Path, record: Mapping[str, Any]) -> Path:
    return write_review(path, record)


def require_approved_mechanics_review(
    review: Mapping[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> None:
    require_approved(MECHANICS_REVIEW, review, edition_id=edition_id, bindings=bindings)
