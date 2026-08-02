"""The bench as a lookup: one kind name in, everything about that kind out.

Seven lenses need a record, a ``--kind`` value, a status row, a workflow
checkpoint and a line in the scores roll-up.  Before this module each of those
five surfaces kept its own list of kinds, and each list was a separate
opportunity to forget one.  They did forget: ``produce_graph`` named ``line``
and ``learning`` in a hardcoded tuple of bench records long after
:data:`~magazine.produce_graph.PIECE_JUDGE_LENSES` was documented as the seam
that made such a tuple unnecessary.

So the surfaces stop keeping lists.  :data:`PIECE_REVIEW_KINDS` is derived from
``PIECE_JUDGE_LENSES`` -- the lens declaration is still the single edit point --
and everything a caller needs to record, load, status or gate one kind is
reachable from the :class:`~magazine.piece_review.PieceReviewKind` it maps to.

The one thing this module does *not* flatten is the binding call.  A lens binds
what it reads, and what it reads differs: ``mechanics`` needs an edition and
nothing else, ``worth`` and ``evidence`` need the sources directory too, and
``teaching`` needs both plus the furniture projection and the explainer
override.  :func:`current_bindings_for` is the one place that difference is
written down, and it is written as a branch on what the spec *declares it
binds* rather than on the kind's name -- so a new lens that binds extractions
gets the right call by declaring ``binds_extractions``, not by being added to a
list here.

``edition`` is deliberately absent from :data:`PIECE_REVIEW_KINDS`.  It is not a
per-piece record: it binds the editorial, the manifest projection and every
manuscript at once, has no per-article rows and no partial rebind, and
``edition_review`` says at length why.  It appears in
:data:`~magazine.produce_graph.BENCH_REVIEW_KINDS` because it must exist before
an edition ships, and nowhere else here.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from .craft_review import CRAFT_REVIEW
from .evidence_review import EVIDENCE_REVIEW
from .mechanics_review import MECHANICS_REVIEW
from .piece_review import PieceReviewKind, current_bindings
from .piece_review import ARTICLES, EXPLAINERS, PIECES
from .produce_graph import (
    BENCH_REVIEW_KINDS,
    EDITION_JUDGE_KIND,
    PIECE_JUDGE_KINDS,
    PIECE_JUDGE_LENSES,
)
from .shape_review import SHAPE_REVIEW
from .teaching_review import TEACHING_REVIEW, furniture_sha256
from .worth_review import WORTH_REVIEW

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .manifest import Edition


_SPECS: tuple[PieceReviewKind, ...] = (
    WORTH_REVIEW,
    EVIDENCE_REVIEW,
    SHAPE_REVIEW,
    TEACHING_REVIEW,
    CRAFT_REVIEW,
    MECHANICS_REVIEW,
)

PIECE_REVIEW_KINDS: Mapping[str, PieceReviewKind] = {
    spec.kind: spec for spec in _SPECS
}

# Proved at import rather than asserted in a test that might not be run: the
# lens table and the record specs must name the same seven things, in the same
# order, or one of them is stale and the bench is silently short a record.
if tuple(PIECE_REVIEW_KINDS) != PIECE_JUDGE_KINDS:
    raise RuntimeError(
        "the review bench declares "
        + ", ".join(PIECE_REVIEW_KINDS)
        + " and produce_graph.PIECE_JUDGE_LENSES declares "
        + ", ".join(PIECE_JUDGE_KINDS)
        + "; a lens with no record shape cannot be recorded, and a record shape "
        "no lens produces can never be written"
    )

# The two tables state coverage for two different purposes and are allowed to
# differ -- a lens may be *dispatched* for pieces its record cannot *bind*, and
# ``evidence`` is, because the editorial has no ``source_ids`` to pin it by.
# What they may not do is diverge in the other direction: a record that binds a
# piece no lens ever reads would be a hash over bytes nobody judged, which is
# the exact shape of a verdict that certifies cleanliness it did not establish.
# Checked at import, because the two files are edited months apart.
_COVERAGE_WIDTH = {EXPLAINERS: 0, ARTICLES: 1, PIECES: 2}
for _lens in PIECE_JUDGE_LENSES:
    _spec = PIECE_REVIEW_KINDS[_lens.kind]
    if _COVERAGE_WIDTH[_spec.covers] > _COVERAGE_WIDTH[_lens.covers]:
        raise RuntimeError(
            f"the {_lens.kind} record binds {_spec.covers} while the lens is "
            f"only dispatched for {_lens.covers}; a record cannot bind a piece "
            "its lens never reads"
        )


def piece_review_spec(kind: str) -> PieceReviewKind:
    """The record shape for one per-piece kind, or a refusal naming the set."""

    try:
        return PIECE_REVIEW_KINDS[kind]
    except KeyError:
        raise KeyError(
            f"{kind!r} is not a per-piece review kind; the bench carries "
            + ", ".join(PIECE_REVIEW_KINDS)
            + f", and {EDITION_JUDGE_KIND} as a whole-issue record"
        ) from None


def current_bindings_for(
    kind: str,
    edition: "Edition",
    sources_dir: Path,
    *,
    require_extractions: bool = False,
    explainer_ids: Sequence[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """What this kind would bind if it were recorded right now.

    One signature for every per-piece kind, so a caller that is iterating the
    bench does not have to know which lenses read a source.  The extras are
    supplied only where the spec says the kind binds them: handing a
    source-blind lens a sources directory it would ignore is harmless here, but
    computing a furniture hash for a lens that does not bind one would put a key
    in the record that nothing compares.
    """

    spec = piece_review_spec(kind)
    return current_bindings(
        spec,
        edition,
        sources_dir=sources_dir if spec.binds_extractions else None,
        require_extractions=require_extractions,
        explainer_ids=explainer_ids,
        furniture_sha256=furniture_sha256(edition) if spec.binds_furniture else None,
    )


__all__ = [
    "BENCH_REVIEW_KINDS",
    "EDITION_JUDGE_KIND",
    "PIECE_REVIEW_KINDS",
    "current_bindings_for",
    "piece_review_spec",
]
