"""Teaching-review records: can a novice use the explainer afterwards.

This kind replaces ``learning_review``, and the replacement is a narrowing
rather than a rename.  The old kind ran three reader personas over the issue's
teaching material in two model calls, and ``prompts/README.md`` retired two of
them: Marcus's furniture-versus-body adjudication is a support relation
``evidence`` already reads for free, and Priya's furniture-versus-source check is
literally ``evidence``'s job applied to non-body text.  Nadia survives, because a
closed-book comprehension test is not obtainable any other way, and
``prompts/teaching-review.md`` is her lens alone.

Three consequences follow from the narrowing, and all three are visible here.

**It is a per-piece lens now, not a whole-issue one.**  ``learning`` produced one
verdict for the edition; ``teaching`` reads the piece whose ``content_mode`` is
``in_a_nutshell`` and files against it.  So the record is the bench's ordinary
per-piece shape (:mod:`magazine.piece_review`) with the explainer as its only
covered piece, rather than a bespoke edition-level document.

**The persona blocks are gone.**  ``comprehension`` and ``manager_takeaways``
were storage for two calls that no longer happen; the six questions and their
outcomes now go in ``notes``, because ``prompts/README.md`` requires one parser
to serve all seven lenses and a per-kind block is a second parser.  A finding no
longer carries ``persona`` either: there is one reader, and naming her on every
row said nothing.

**The binding is inherited unchanged.**  What Nadia reads is what she always
read: the explainer's manuscript, the editor-authored furniture, and -- in steps
1 and 5 only -- the pinned source.  So this record binds the manuscript, the
furniture projection, and the source extractions, and
:func:`furniture_projection` below is ``learning_review``'s function moved rather
than rewritten.  Its coverage argument is unchanged and worth keeping in front of
whoever extends it:

    Most of the furniture the prompt names has no data model.  There is no
    glossary, cheat-sheet or exercise field anywhere in ``edition.yaml`` today.
    The prompt already anticipates this and says "Judge only the furniture that
    exists", so the projection covers the editor-authored strings the manifest
    can currently express and nothing else: the edition ``title`` and
    ``subtitle``; the ``cover`` headline, deck, back text and edition label; per
    article, in id order, ``title``, ``short_title``, ``display_emphasis``,
    ``author_note``, its ``key_ideas`` lines, and each figure's ``id``,
    ``caption``, ``alt_text`` and ``anchor``; and the closing plate titles.

    An absent key is absent from the projection rather than defaulted to ``""``,
    so a field that is added and then removed hashes back to the value it had
    before -- a projection that invented empty strings would make "this manifest
    never had a deck" and "this manifest has an empty deck" hash differently, and
    only one of those is a change to what a reader saw.  A present-but-blank
    value is treated as absent for the same reason.

    Hashing ``edition.yaml`` whole was considered and rejected.  The manifest
    also carries source ids and ``source_body_sha256`` pins, manuscript paths,
    figure ``asset_id`` values, opener art credits, rights blocks and the release
    ``status`` -- none of which any reader read.  Re-pinning a source after a
    re-extraction would spuriously stale a verdict about whether a glossary entry
    is wrong.  The projection costs an explicit key list; the whole-file hash
    would have cost the signal.

    When the manifest grows a ``glossary``, ``cheat_sheet`` or ``try_it`` field
    -- and it should -- extending the ``_FURNITURE_*`` tuples here is mandatory,
    and each such extension must bump :data:`TEACHING_REVIEW_SCHEMA_VERSION`,
    because a record written before the extension bound strictly less than one
    written after and the two must not be read as the same claim.

**Explainer detection reads the manifest's own marker.**  An article declares
``content_mode: in_a_nutshell`` and that declaration is what this module reads,
rather than an id heuristic that silently missed an explainer named for its
subject.  The caller may still override with an explicit list, which is the
escape hatch for an edition whose explainer is mis-declared.  An edition with no
explainer is an ordinary state: the lens simply does not run, and the graph
reports its node ``not_applicable`` rather than unreached.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Sequence

from .piece_review import (
    EXPLAINERS,
    PieceReviewKind,
    covered_piece_ids,
    create_review,
    current_bindings,
    load_review,
    rebind_articles as _rebind_articles,
    require_approved,
    review_path,
    review_status,
    write_review,
)
from .render_review import projection_sha256

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .manifest import Edition


TEACHING_REVIEW_SCHEMA_VERSION = 1

TEACHING_REVIEW = PieceReviewKind(
    kind="teaching",
    label="Teaching review",
    covers=EXPLAINERS,
    schema_version=TEACHING_REVIEW_SCHEMA_VERSION,
    supported_versions=(1,),
    binds_extractions=True,
    binds_furniture=True,
    subject="explainer",
    reading="reading",
)

EXPLAINER_CONTENT_MODE = "in_a_nutshell"
"""The manifest's marker for the teaching explainer.

Named here rather than imported so this module keeps its manifest dependency to
``TYPE_CHECKING``; the suite asserts the string is still a registered content
mode.
"""

# --- The furniture projection ------------------------------------------------
#
# Extending any of these tuples changes what an approved record claims to have
# covered, so it must come with a TEACHING_REVIEW_SCHEMA_VERSION bump.

_FURNITURE_EDITION_KEYS = ("title", "subtitle")
_FURNITURE_COVER_KEYS = ("headline", "deck", "back_text", "edition_label")
_FURNITURE_ARTICLE_KEYS = ("title", "short_title", "display_emphasis", "author_note")
_FURNITURE_FIGURE_KEYS = ("id", "caption", "alt_text", "anchor")
# Furniture the manifest holds as a list of lines rather than one string.  The
# key-ideas box is the furniture a first-time reader answers from, so leaving it
# out of the binding would let the one thing she reads hardest be rewritten
# under an approved verdict.
_FURNITURE_ARTICLE_LIST_KEYS = ("key_ideas",)


def teaching_review_path(editions_dir: Path, edition_id: str) -> Path:
    return review_path(editions_dir, edition_id, TEACHING_REVIEW.kind)


def explainer_article_ids(edition: "Edition") -> tuple[str, ...]:
    """The edition's in-a-nutshell pieces, in running order.

    Detection by declaration: an explainer is an article whose ``content_mode``
    is :data:`EXPLAINER_CONTENT_MODE`, whatever it is called.  An edition with no
    explainer returns ``()``.
    """

    return tuple(
        article.id
        for article in edition.articles
        if article.content_mode == EXPLAINER_CONTENT_MODE
    )


def furniture_projection(edition: "Edition") -> dict[str, Any]:
    """The editor-authored strings the reader sees, as the manifest holds them.

    Built from :attr:`Edition.raw` rather than from the dataclasses, because the
    dataclasses normalize (``author_note`` is stripped, ``short_title`` and
    ``display_emphasis`` are coerced to ``""`` when absent) and the projection
    needs to distinguish an absent field from an empty one.  Absent and blank
    leaf keys are omitted; the three container keys (``cover``, ``articles``,
    ``closing_plates``) are always present so the shape of the projection does
    not depend on how much furniture an edition happens to carry.
    """

    raw: Mapping[str, Any] = edition.raw or {}
    projection: dict[str, Any] = {}
    _project_keys(projection, raw, _FURNITURE_EDITION_KEYS)

    cover: dict[str, Any] = {}
    raw_cover = raw.get("cover")
    if isinstance(raw_cover, Mapping):
        _project_keys(cover, raw_cover, _FURNITURE_COVER_KEYS)
    projection["cover"] = cover

    articles: dict[str, Any] = {}
    raw_articles = raw.get("articles")
    if isinstance(raw_articles, list):
        for row in raw_articles:
            if not isinstance(row, Mapping):
                continue
            article_id = str(row.get("id") or "").strip()
            if not article_id:
                continue
            entry: dict[str, Any] = {}
            _project_keys(entry, row, _FURNITURE_ARTICLE_KEYS)
            _project_line_keys(entry, row, _FURNITURE_ARTICLE_LIST_KEYS)
            figures: list[dict[str, Any]] = []
            raw_figures = row.get("figures")
            if isinstance(raw_figures, list):
                for figure in raw_figures:
                    if not isinstance(figure, Mapping):
                        continue
                    projected: dict[str, Any] = {}
                    _project_keys(projected, figure, _FURNITURE_FIGURE_KEYS)
                    if projected:
                        figures.append(projected)
            # Figure order is editorial -- it is the order the captions are read
            # in -- so the list is left as authored rather than sorted.
            entry["figures"] = figures
            articles[article_id] = entry
    projection["articles"] = {key: articles[key] for key in sorted(articles)}

    titles: list[str] = []
    raw_plates = raw.get("closing_plates")
    if isinstance(raw_plates, list):
        for plate in raw_plates:
            if isinstance(plate, Mapping) and str(plate.get("title") or "").strip():
                titles.append(str(plate["title"]))
    projection["closing_plates"] = titles
    return projection


def _project_keys(
    target: dict[str, Any], source: Mapping[str, Any], keys: tuple[str, ...]
) -> None:
    """Copy the named keys that carry a value, in the order the tuple names them."""

    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        text = str(value)
        if not text.strip():
            continue
        target[key] = text


def _project_line_keys(
    target: dict[str, Any], source: Mapping[str, Any], keys: tuple[str, ...]
) -> None:
    """Copy the named list-of-lines keys, as authored, dropping blank lines.

    Line order is editorial -- the key-ideas box is read top to bottom, and
    reordering it is a real change to what the box says -- so the list is kept
    as written rather than sorted.  A key that carries no line at all is
    omitted, so declaring an empty box and declaring none hash alike.
    """

    for key in keys:
        value = source.get(key)
        if not isinstance(value, list):
            continue
        lines = [str(line) for line in value if str(line or "").strip()]
        if lines:
            target[key] = lines


def furniture_sha256(edition: "Edition") -> str:
    """One hash over the whole furniture projection, canonicalized first.

    The canonicalization is the bench's shared one (see
    :func:`magazine.render_review.projection_sha256`), so this hash and the
    edition record's manifest-projection hash are computed the same way even
    though what they project is deliberately different.
    """

    return projection_sha256(furniture_projection(edition))


def teaching_explainer_ids(
    edition: "Edition", *, explainer_ids: Sequence[str] | None = None
) -> tuple[str, ...]:
    return covered_piece_ids(TEACHING_REVIEW, edition, explainer_ids=explainer_ids)


def current_teaching_bindings(
    edition: "Edition",
    sources_dir: Path,
    *,
    require_extractions: bool = False,
    explainer_ids: Sequence[str] | None = None,
) -> dict[str, dict[str, Any]]:
    return current_bindings(
        TEACHING_REVIEW,
        edition,
        sources_dir=sources_dir,
        require_extractions=require_extractions,
        explainer_ids=explainer_ids,
        furniture_sha256=furniture_sha256(edition),
    )


def load_teaching_review(path: Path, *, edition_id: str) -> dict[str, Any] | None:
    return load_review(TEACHING_REVIEW, path, edition_id=edition_id)


def teaching_review_status(
    review: Mapping[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return review_status(
        TEACHING_REVIEW, review, edition_id=edition_id, bindings=bindings
    )


def create_teaching_review(**kwargs: Any) -> dict[str, Any]:
    return create_review(TEACHING_REVIEW, **kwargs)


def rebind_articles(
    review: Mapping[str, Any] | None,
    *,
    bindings: Mapping[str, Mapping[str, Any]],
    article_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    return _rebind_articles(
        TEACHING_REVIEW, review, bindings=bindings, article_ids=article_ids
    )


def write_teaching_review(path: Path, record: Mapping[str, Any]) -> Path:
    return write_review(path, record)


def require_approved_teaching_review(
    review: Mapping[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> None:
    require_approved(
        TEACHING_REVIEW, review, edition_id=edition_id, bindings=bindings
    )
