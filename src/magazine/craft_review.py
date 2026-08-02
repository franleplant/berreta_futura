"""Craft-review records: did a person write this.

The third of the three lenses ``prompts/line-review.md`` split into, and the one
that runs last.  Its concern is the sentence: register, sentence shapes, dead
words, banned tics, economy.  Not truth, not order, not grammar -- four other
lenses own those.

**It binds the manuscript and nothing else**, for the same reason ``mechanics``
and ``shape`` do: everything it is asked is answerable blind, so a source binding
would manufacture staleness carrying no signal.

**It is the most expensive lens to run early.**  ``prompts/README.md`` puts it in
stage 3 and says why: sentence work is destroyed by every structural or factual
repair above it, so craft notes on a paragraph about to be cut are wasted calls,
and running it before ``worth``, ``evidence`` and ``shape`` have settled buys a
re-run.  The staging that enforces that lives in
:data:`~magazine.produce_graph.PIECE_JUDGE_LENSES`.

**This is the lens where ``editor_decision`` is load-bearing.**  A retained
sentence of the source author's own is where the old severity cap did its damage,
and craft is where such sentences are judged hardest.  Here the finding is filed
at its honest severity and routed to a human, who picks between a silent repair,
``[sic]``, leaving it, or not printing the piece.  The record therefore has to
carry that routing structurally, and :func:`~magazine.piece_review.require_approved`
refuses a release that still has one outstanding.
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


CRAFT_REVIEW_SCHEMA_VERSION = 1

CRAFT_REVIEW = PieceReviewKind(
    kind="craft",
    label="Craft review",
    covers=PIECES,
    schema_version=CRAFT_REVIEW_SCHEMA_VERSION,
    supported_versions=(1,),
    subject="piece",
    reading="reading",
)


def craft_review_path(editions_dir: Path, edition_id: str) -> Path:
    return review_path(editions_dir, edition_id, CRAFT_REVIEW.kind)


def current_craft_bindings(edition: "Edition") -> dict[str, dict[str, Any]]:
    """The per-piece manuscript hashes this lens binds to, as of now."""

    return current_bindings(CRAFT_REVIEW, edition)


def load_craft_review(path: Path, *, edition_id: str) -> dict[str, Any] | None:
    return load_review(CRAFT_REVIEW, path, edition_id=edition_id)


def craft_review_status(
    review: Mapping[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return review_status(CRAFT_REVIEW, review, edition_id=edition_id, bindings=bindings)


def create_craft_review(**kwargs: Any) -> dict[str, Any]:
    return create_review(CRAFT_REVIEW, **kwargs)


def rebind_articles(
    review: Mapping[str, Any] | None,
    *,
    bindings: Mapping[str, Mapping[str, Any]],
    article_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    return _rebind_articles(
        CRAFT_REVIEW, review, bindings=bindings, article_ids=article_ids
    )


def write_craft_review(path: Path, record: Mapping[str, Any]) -> Path:
    return write_review(path, record)


def require_approved_craft_review(
    review: Mapping[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> None:
    require_approved(CRAFT_REVIEW, review, edition_id=edition_id, bindings=bindings)
