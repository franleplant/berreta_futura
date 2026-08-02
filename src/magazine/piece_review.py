"""One per-piece review record, written once and worn by seven lenses.

Every lens on the bench that reads *one piece at a time* stores the same thing:
a verdict, a list of findings, an advisory score row per piece, and -- the part
that makes a record evidence rather than a note -- the SHA-256 of the exact
bytes the lens read.  ``evidence_review`` and ``line_review`` each grew that
independently, and by the time the bench went from two lenses to seven the two
files had drifted into 900 lines that differed in the word "audit" and in one
extra binding key.  Writing five more copies of it was not an option, so the
shape moved here and the per-kind modules became declarations.

**What a kind declares, and what it inherits.**  A :class:`PieceReviewKind`
names the file, the prose a refusal uses, the schema versions that still load,
which pieces of an edition the lens covers, and what it binds.  Everything
else -- loading, staleness, partial re-records, the atomic write -- is this
module's and is identical across kinds by construction.  The atomic writer is
``render_review.write_render_review``, shared rather than reimplemented, which
is also where the hashing lives.

**Binding is per lens because source-blindness is per lens.**
``prompts/README.md`` states the constraint as an assignment rule: a lens that
cannot see the source cannot be invalidated by the source moving.  So
``mechanics``, ``shape`` and ``craft`` bind the manuscript and nothing else --
storing a source hash there would send a source-blind reader back to re-read a
piece whose prose did not move -- while ``worth`` and ``evidence`` bind the
manuscript *and* every declared extraction, because a re-capture genuinely does
invalidate what they concluded.  ``teaching`` binds both of those plus the
furniture projection, because Nadia reads the deck and the key-ideas box as much
as she reads the body.

**Staleness is derived per piece, and the whole derives from the parts.**  Each
recorded row is compared against the same piece's current binding: every row
current and the result approved means approved; any drifted, unrecorded or
removed row means stale, naming the pieces and, per piece, which bound input
moved.  A partial re-read (``mag review record --kind craft --articles a,b``)
re-binds only the named pieces from disk and preserves every other piece's
recorded binding, ``reviewed_at`` and scores byte for byte
(:func:`rebind_articles`).  Scores never participate in staleness: a score that
could stale a record would be a score that gates, which is precisely what
:mod:`magazine.review_findings` refuses to let a score become.

**An ``editor_decision`` finding blocks the release.**
:func:`require_approved` refuses an issue that still carries one at any
severity, and it refuses it *separately* from the approved/stale question,
because the two are different facts: the lens is happy with the piece and a
human has still not said what to do about a defect the lens was forbidden to
route to the writer.  A gate that folded them together would let an approval
launder the one thing the disposition field exists to keep visible.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .errors import ValidationError
from .extraction import EXTRACTION_FILENAME, load_extraction
from .io import load_structured
from .render_review import REVIEW_RESULTS, sha256, write_render_review
from .review_findings import (
    describe_finding,
    editor_decision_findings,
    finding_errors,
    normalize_article_scores,
    normalize_findings,
    score_errors,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .manifest import Edition

_HEX_DIGITS = set("0123456789abcdef")


EDITORIAL_ARTICLE_ID = "editorial"
"""The article id the opening editorial is reviewed under.

``edition.yaml`` gives the editorial no id of its own -- it is a path, not an
article row -- so the bench needs one name for it, and the lens prompts' locator
domain already uses this one.  An edition with no editorial simply has no
``editorial`` row: that is an ordinary state, not an error.
"""


# Which pieces of an edition a lens covers.  Not a stylistic distinction: a lens
# asked about a piece it cannot judge would either bind bytes nobody read or
# report an unrecorded row for ever, and both read as staleness that no re-run
# can clear.
ARTICLES = "articles"
"""Every article, editorial excluded.  ``worth`` and ``evidence``.

``worth`` is excluded from the editorial by ``prompts/README.md``: the editorial
has no source of its own, so its worth question is whether it says something no
single article says, and that is ``edition``'s.  ``evidence`` is excluded
because the editorial declares no ``source_ids`` and there is nothing to bind --
its findings still travel, record-level, so the audit is not lost.
"""

PIECES = "pieces"
"""Every article plus the editorial.  ``mechanics``, ``shape``, ``craft``."""

EXPLAINERS = "explainers"
"""Only the ``in_a_nutshell`` piece(s).  ``teaching``."""

PIECE_SETS = (ARTICLES, PIECES, EXPLAINERS)


@dataclass(frozen=True)
class PieceReviewKind:
    """One per-piece lens, as a record shape rather than as a module.

    ``supported_versions`` is the list of shapes that still load, and it is
    always a superset of ``schema_version``.  The precedent is
    ``evidence_review``'s: a bump exists so that "a version 2 record" continues
    to name exactly one shape, not so that shipped editions have to be
    re-audited.  Adding to what a kind *binds* is the change that must bump it,
    because a record written before the addition claims to have covered less.
    """

    kind: str
    label: str
    covers: str
    schema_version: int
    supported_versions: tuple[int, ...]
    binds_extractions: bool = False
    binds_furniture: bool = False
    subject: str = "piece"
    """The word a refusal uses for one unit: ``piece``, ``article``, ``explainer``."""

    reading: str = "review"
    """The word a refusal uses for the act: ``review``, ``audit``, ``reading``."""

    def __post_init__(self) -> None:
        if self.covers not in PIECE_SETS:
            raise ValueError(
                f"{self.kind} covers {self.covers!r}; a lens covers "
                + ", ".join(PIECE_SETS)
            )
        if self.schema_version not in self.supported_versions:
            raise ValueError(
                f"{self.kind} writes schema_version {self.schema_version} and "
                "does not list it among the versions it can read"
            )

    @property
    def binding_keys(self) -> tuple[str, ...]:
        """The keys of a piece row that *bind*.

        Rows also carry review metadata -- ``reviewed_at`` and ``scores`` --
        which must never participate in staleness: when a piece was last read,
        and what the reader thought of it, say nothing about whether its bytes
        moved.
        """

        keys = ["manuscript_sha256"]
        if self.binds_extractions:
            keys.append("source_extractions")
        return tuple(keys)


def review_path(editions_dir: Path, edition_id: str, kind: str) -> Path:
    """Where one kind's record lives.  One rule, so no kind can invent a path."""

    return editions_dir / edition_id / "reviews" / f"{kind}.yaml"


# ---------------------------------------------------------------------------
# What the lens would be reading, as of right now.


def covered_piece_ids(
    spec: PieceReviewKind,
    edition: "Edition",
    *,
    explainer_ids: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """The pieces this lens is asked about, in running order.

    ``explainer_ids`` overrides the ``in_a_nutshell`` detection, which is the
    escape hatch for an edition whose explainer is mis-declared.  It is ignored
    by every kind that does not cover explainers.
    """

    article_ids = tuple(article.id for article in edition.articles)
    if spec.covers == ARTICLES:
        return article_ids
    if spec.covers == PIECES:
        if edition.editorial is not None:
            return article_ids + (EDITORIAL_ARTICLE_ID,)
        return article_ids
    if explainer_ids is not None:
        requested = [str(item).strip() for item in explainer_ids if str(item).strip()]
        unknown = sorted(set(requested) - set(article_ids))
        if unknown:
            raise ValidationError(
                f"{spec.label} cannot bind explainers the edition does not "
                "carry: " + ", ".join(unknown)
            )
        return tuple(dict.fromkeys(requested))
    from .teaching_review import EXPLAINER_CONTENT_MODE

    return tuple(
        article.id
        for article in edition.articles
        if article.content_mode == EXPLAINER_CONTENT_MODE
    )


def current_bindings(
    spec: PieceReviewKind,
    edition: "Edition",
    *,
    sources_dir: Path | None = None,
    require_extractions: bool = False,
    explainer_ids: Sequence[str] | None = None,
    furniture_sha256: str | None = None,
) -> dict[str, dict[str, Any]]:
    """The per-piece hashes this lens's verdict depends on, hashed now.

    ``require_extractions`` is true at record time: a review cannot claim to
    have read a manuscript against an extraction that does not exist.  The
    lenient form serves status and gate checks, where a missing extraction
    simply cannot match the recorded hash and surfaces as staleness.
    """

    manuscripts: dict[str, Path] = {
        article.id: article.manuscript for article in edition.articles
    }
    source_ids: dict[str, tuple[str, ...]] = {
        article.id: tuple(article.source_ids) for article in edition.articles
    }
    if edition.editorial is not None:
        manuscripts[EDITORIAL_ARTICLE_ID] = edition.editorial.path
        source_ids[EDITORIAL_ARTICLE_ID] = ()

    bindings: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for piece_id in covered_piece_ids(spec, edition, explainer_ids=explainer_ids):
        row: dict[str, Any] = {"manuscript_sha256": sha256(manuscripts[piece_id])}
        if spec.binds_extractions:
            if sources_dir is None:
                raise ValidationError(
                    f"{spec.label} binds source extractions and was given no "
                    "sources directory to read them from"
                )
            extractions: dict[str, dict[str, str]] = {}
            for source_id in dict.fromkeys(source_ids[piece_id]):
                extraction = load_extraction(sources_dir, source_id)
                if extraction is None:
                    if require_extractions:
                        errors.append(
                            f"{spec.label} requires a committed extraction for "
                            f"source {source_id} ({spec.subject} {piece_id}); add "
                            f"library/sources/{source_id}/{EXTRACTION_FILENAME}"
                        )
                    continue
                extractions[source_id] = {
                    "body_sha256": extraction.body_sha256,
                    "file_sha256": extraction.file_sha256,
                }
            row["source_extractions"] = extractions
        if spec.binds_furniture:
            if furniture_sha256 is None:
                raise ValidationError(
                    f"{spec.label} binds the edition's furniture and was given "
                    "no furniture hash"
                )
            row["furniture_sha256"] = furniture_sha256
        bindings[piece_id] = row
    if errors:
        raise ValidationError(errors)
    return bindings


# ---------------------------------------------------------------------------
# Reading a record back.


def load_review(
    spec: PieceReviewKind,
    path: Path,
    *,
    edition_id: str,
    extra_checks: Callable[[Mapping[str, Any]], list[str]] | None = None,
) -> dict[str, Any] | None:
    """Read one record, accumulating every complaint before refusing.

    A record with a bad severity, an out-of-range score and a broken hash
    should report all three, so this collects and raises once.  Findings are
    checked at the *stored* standard (see
    :mod:`magazine.review_findings`): a record written before ``disposition``
    existed still loads.
    """

    if not path.is_file():
        return None
    data = load_structured(path)
    errors: list[str] = []
    if data.get("schema_version") not in spec.supported_versions:
        errors.append(
            f"{spec.label} schema_version must be "
            + _versions_phrase(spec.supported_versions)
        )
    if data.get("edition_id") != edition_id:
        errors.append(
            f"{spec.label} edition_id {data.get('edition_id')!r} does not match "
            f"{edition_id!r}"
        )
    if str(data.get("result") or "") not in REVIEW_RESULTS:
        errors.append(f"{spec.label} result must be approved or changes_required")
    for key in ("reviewer", "reviewed_at"):
        if not str(data.get(key) or "").strip():
            errors.append(f"{spec.label} requires {key}")
    findings = data.get("findings", [])
    errors.extend(finding_errors(findings, label=spec.label))
    if data.get("result") == "changes_required" and not findings:
        errors.append(
            f"A changes_required {spec.label.lower()} needs at least one finding"
        )
    articles = data.get("articles")
    if not isinstance(articles, dict) or not articles:
        errors.append(f"{spec.label} requires an articles mapping")
        articles = {}
    for piece_id, row in articles.items():
        errors.extend(_row_errors(spec, piece_id, row))
    if extra_checks is not None:
        errors.extend(extra_checks(data))
    if errors:
        raise ValidationError(errors)
    return dict(data)


def _row_errors(spec: PieceReviewKind, piece_id: str, row: Any) -> list[str]:
    if not isinstance(row, dict):
        return [f"{spec.label} {spec.subject} {piece_id} must be a mapping"]
    errors: list[str] = []
    if not is_sha256(row.get("manuscript_sha256")):
        errors.append(
            f"{spec.label} {spec.subject} {piece_id} has invalid manuscript_sha256"
        )
    # Per-piece ``reviewed_at`` and ``scores`` are additive and optional: a
    # record written before either existed is still valid (the record-level
    # timestamp stands in, and an unscored piece is normal).  Present-but-empty
    # is not the same thing and is refused.
    if "reviewed_at" in row and not str(row.get("reviewed_at") or "").strip():
        errors.append(
            f"{spec.label} {spec.subject} {piece_id} reviewed_at must be a "
            "non-empty string when present"
        )
    errors.extend(
        score_errors(row.get("scores"), label=f"{spec.label} {spec.subject} {piece_id}")
    )
    if spec.binds_furniture and not is_sha256(row.get("furniture_sha256")):
        errors.append(
            f"{spec.label} {spec.subject} {piece_id} has invalid furniture_sha256"
        )
    if spec.binds_extractions:
        extractions = row.get("source_extractions")
        # Non-empty, deliberately: a lens that binds extractions was asked to
        # read the piece *against* them, and a row that covers none is a record
        # of a read that could not have happened.
        if not isinstance(extractions, dict) or not extractions:
            errors.append(
                f"{spec.label} {spec.subject} {piece_id} requires a "
                "source_extractions mapping"
            )
            return errors
        for source_id, value in extractions.items():
            if (
                not isinstance(value, dict)
                or not is_sha256(value.get("body_sha256"))
                or not is_sha256(value.get("file_sha256"))
            ):
                errors.append(
                    f"{spec.label} {spec.subject} {piece_id} extraction binding "
                    f"for {source_id} requires body_sha256 and file_sha256"
                )
    return errors


def is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and set(text) <= _HEX_DIGITS


def _versions_phrase(versions: Sequence[int]) -> str:
    names = [str(version) for version in versions]
    if len(names) < 3:
        return " or ".join(names)
    return ", ".join(names[:-1]) + f", or {names[-1]}"


# ---------------------------------------------------------------------------
# Staleness.


def article_drift(
    spec: PieceReviewKind, recorded: Mapping[str, Any], current: Mapping[str, Any]
) -> list[str]:
    """Name exactly which of one piece's bound inputs no longer match disk.

    The names are for the human deciding what to re-read: ``manuscript`` for
    the piece's own file, ``furniture`` for the editor-authored projection, and
    ``extraction:<source-id>`` for any extraction whose body or file hash moved
    (or that appeared or vanished from the covered set).  A key an older schema
    bound and this one does not is simply not compared: reporting the absence of
    a binding nothing reads any more would demand a re-read that nothing has
    actually invalidated.
    """

    drift: list[str] = []
    if recorded.get("manuscript_sha256") != current.get("manuscript_sha256"):
        drift.append("manuscript")
    if spec.binds_furniture and recorded.get("furniture_sha256") != current.get(
        "furniture_sha256"
    ):
        drift.append("furniture")
    if spec.binds_extractions:
        was = recorded.get("source_extractions") or {}
        now = current.get("source_extractions") or {}
        for source_id in sorted(set(was) | set(now)):
            if was.get(source_id) != now.get(source_id):
                drift.append(f"extraction:{source_id}")
    return drift


def review_status(
    spec: PieceReviewKind,
    review: Mapping[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Derive the record's standing per piece, then the whole from the parts.

    ``articles`` reports, for every piece the edition or the record knows:

    - ``current``: every bound hash matches; ``reviewed_at`` says when (falling
      back to the record's own timestamp for rows written before per-piece
      stamps existed).
    - ``drifted``: some bound input changed; ``drift`` names which.
    - ``unrecorded``: the edition has the piece but the record never bound it.
    - ``removed``: the record bound a piece the edition no longer carries.
    - ``unreviewed``: no record exists at all.

    ``editor_decisions`` is the count of findings still routed to a human.  It
    is reported at every status, including ``approved``, because that is the
    combination the field exists for: an approving lens and an unresolved
    defect it was forbidden to hand to the writer.
    """

    articles: dict[str, Any] = {}
    base: dict[str, Any] = {
        "status": "required_before_release",
        "reviewer": None,
        "reviewed_at": None,
        "result": None,
        "findings": [],
        "editor_decisions": 0,
        "articles": articles,
    }
    if review is None and not bindings and spec.covers == EXPLAINERS:
        # An edition with no explainer is an ordinary edition, and ``teaching``
        # simply does not run on it.  Reported ``not_applicable`` rather than
        # ``required_before_release``, because the latter is a demand no run
        # could ever satisfy: there is no piece to read, so no record can be
        # written, so the checkpoint would sit red for ever and teach an
        # operator to ignore it.  ``produce_graph`` already resolves the node
        # this way; this is the bench agreeing with the graph.
        base["status"] = "not_applicable"
        return base
    if review is None:
        for piece_id in bindings:
            articles[piece_id] = {"status": "unreviewed", "reviewed_at": None}
        return base
    findings = list(review.get("findings", []))
    base.update(
        {
            "reviewer": review.get("reviewer"),
            "reviewed_at": review.get("reviewed_at"),
            "result": review.get("result"),
            "findings": findings,
            "editor_decisions": len(editor_decision_findings(findings)),
        }
    )
    recorded = review.get("articles") or {}
    fallback_reviewed_at = review.get("reviewed_at")
    any_drift = False
    for piece_id in sorted(set(bindings) | set(recorded)):
        row = recorded.get(piece_id)
        current = bindings.get(piece_id)
        if not isinstance(row, dict):
            articles[piece_id] = {"status": "unrecorded", "reviewed_at": None}
            any_drift = True
            continue
        entry: dict[str, Any] = {
            "reviewed_at": row.get("reviewed_at") or fallback_reviewed_at
        }
        # Scores travel out because status is how the CLI and ``mag scores``
        # see a record; they are reported and never read.
        if isinstance(row.get("scores"), dict) and row["scores"]:
            entry["scores"] = dict(row["scores"])
        if current is None:
            entry["status"] = "removed"
            any_drift = True
        else:
            drift = article_drift(spec, row, current)
            if drift:
                entry["status"] = "drifted"
                entry["drift"] = drift
                any_drift = True
            else:
                entry["status"] = "current"
        articles[piece_id] = entry
    if review.get("edition_id") != edition_id or any_drift:
        base["status"] = "stale"
    elif review.get("result") == "approved":
        base["status"] = "approved"
    else:
        base["status"] = "changes_required"
    return base


# ---------------------------------------------------------------------------
# Writing one.


def create_review(
    spec: PieceReviewKind,
    *,
    edition_id: str,
    reviewer: str,
    result: str,
    bindings: Mapping[str, Mapping[str, Any]],
    findings: Iterable[Any] = (),
    scores: Mapping[str, Mapping[str, int]] | None = None,
    notes: str = "",
    reviewed_at: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose one record, refusing anything that would store a false verdict.

    Findings go through :func:`~magazine.review_findings.normalize_findings` at
    the *authored* standard, so a structured finding with no ``disposition`` is
    refused here rather than stored unrouted.  That is the whole point of the
    field: the write path is where it can still be supplied.
    """

    reviewer = reviewer.strip()
    result = result.strip()
    clean_findings = normalize_findings(findings, label=spec.label)
    if not reviewer:
        raise ValidationError(f"{spec.label} requires a reviewer")
    if result not in REVIEW_RESULTS:
        raise ValidationError(
            f"{spec.label} result must be approved or changes_required"
        )
    if result == "changes_required" and not clean_findings:
        raise ValidationError(
            f"A changes_required {spec.label.lower()} needs at least one finding"
        )
    if not bindings:
        raise ValidationError(
            f"{spec.label} requires at least one {spec.subject} to read"
        )
    parsed_scores = normalize_article_scores(
        scores, label=spec.label, article_ids=bindings
    )
    timestamp = (
        reviewed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    )
    # Every row records when *it* was read.  Rows arriving without a stamp were
    # read now (a full record, or the re-bound pieces of a partial one); rows
    # that already carry one are preserved bindings whose reading history must
    # survive the re-record.  See :func:`rebind_articles`.
    articles: dict[str, dict[str, Any]] = {}
    for piece_id, row in bindings.items():
        entry: dict[str, Any] = {"reviewed_at": timestamp, **dict(row)}
        row_scores = parsed_scores.get(piece_id) or entry.get("scores")
        if row_scores:
            entry["scores"] = dict(row_scores)
        else:
            entry.pop("scores", None)
        articles[piece_id] = entry
    record: dict[str, Any] = {
        "schema_version": spec.schema_version,
        "edition_id": edition_id,
        "reviewer": reviewer,
        "reviewed_at": timestamp,
        "result": result,
        "findings": clean_findings,
        "notes": notes.strip(),
        "articles": articles,
    }
    if extra:
        record.update(dict(extra))
    return record


def rebind_articles(
    spec: PieceReviewKind,
    review: Mapping[str, Any] | None,
    *,
    bindings: Mapping[str, Mapping[str, Any]],
    article_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    """Merge a partial re-read into an existing record's bindings.

    ``--articles`` names the pieces that were actually read again; those are
    re-bound from ``bindings`` (current disk state) and will be stamped with the
    new record's timestamp by :func:`create_review`.  Every other piece in the
    edition keeps its recorded binding, its recorded ``reviewed_at`` *and* its
    recorded ``scores``, so an untouched piece's reading survives the re-record
    intact and a drifted-but-unnamed piece stays visibly drifted rather than
    being silently re-blessed by a read that never happened.

    The edition's current piece list is the universe: recorded pieces that left
    the edition simply fall out of the new record, and a piece that is in the
    edition but neither named nor previously recorded is refused -- there is no
    reading, old or new, to carry for it.
    """

    requested = [str(item).strip() for item in article_ids if str(item).strip()]
    if not requested:
        raise ValidationError(
            f"A partial {spec.kind} re-record requires at least one "
            f"{spec.subject} id"
        )
    if review is None:
        raise ValidationError(
            f"A partial {spec.kind} re-record amends an existing record, and "
            f"none exists; record the full {spec.reading} first with "
            f"`mag review record --kind {spec.kind}`"
        )
    unknown = sorted(set(requested) - set(bindings))
    if unknown:
        raise ValidationError(
            f"Cannot re-bind {spec.subject}s the edition does not carry: "
            + ", ".join(unknown)
        )
    recorded = review.get("articles") or {}
    fallback_reviewed_at = review.get("reviewed_at")
    merged: dict[str, dict[str, Any]] = {}
    unbound: list[str] = []
    named = set(requested)
    for piece_id, current in bindings.items():
        if piece_id in named:
            merged[piece_id] = dict(current)
        elif isinstance(recorded.get(piece_id), dict):
            row = recorded[piece_id]
            preserved: dict[str, Any] = {
                "reviewed_at": row.get("reviewed_at") or fallback_reviewed_at
            }
            preserved.update({key: row.get(key) for key in spec.binding_keys})
            if spec.binds_furniture:
                preserved["furniture_sha256"] = row.get("furniture_sha256")
            # An untouched piece's advisory scores are as much recorded history
            # as its timestamp: the lens rated that manuscript, and re-reading
            # a sibling did not change the rating.
            if isinstance(row.get("scores"), dict) and row["scores"]:
                preserved["scores"] = dict(row["scores"])
            merged[piece_id] = preserved
        else:
            unbound.append(piece_id)
    if unbound:
        raise ValidationError(
            f"{spec.subject.capitalize()}s have no recorded {spec.reading} to "
            "preserve: "
            + ", ".join(unbound)
            + f"; name them in --articles or record the full {spec.reading}"
        )
    return merged


def write_review(path: Path, record: Mapping[str, Any]) -> Path:
    """Replace one record atomically.

    The render review's writer is a generic atomic YAML replacement; every kind
    on the bench shares it rather than growing one of its own.
    """

    return write_render_review(path, dict(record))


def require_approved(
    spec: PieceReviewKind,
    review: Mapping[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> None:
    """Refuse a release this lens has not cleared, and say what is in the way.

    Two independent refusals, never folded into one.  The first is the ordinary
    bench question: is there a current approved record?  The second is the one
    ``disposition`` exists for: an ``editor_decision`` finding is a real defect
    the lens was forbidden to route to the writer, so an approving verdict says
    nothing about whether anybody has dealt with it.  Every one of them is named
    in the refusal, at whatever severity it was filed, because a count would let
    an operator clear the gate without reading them.
    """

    status = review_status(spec, review, edition_id=edition_id, bindings=bindings)
    if status["status"] == "not_applicable":
        return
    problems: list[str] = []
    if status["status"] != "approved":
        detail = f"{spec.kind} {spec.reading} is {status['status']}"
        if status["status"] == "stale" and review is not None:
            # The per-piece rows already say exactly what moved; naming them
            # makes the refusal double as the re-read worklist.
            drifted = [
                piece_id
                for piece_id, row in status["articles"].items()
                if row.get("status") != "current"
            ]
            if drifted:
                detail += "; changed since the recorded read: " + ", ".join(drifted)
        problems.append(detail)
    outstanding = editor_decision_findings(status["findings"])
    if outstanding:
        problems.append(
            f"{len(outstanding)} {spec.kind} finding(s) are "
            "`disposition: editor_decision` and are waiting on a human ruling. "
            "They are never the writer's to clear and are never counted clean; "
            "resolve each one -- a silent repair, `[sic]`, leaving it, or not "
            "printing the piece -- and re-record the review."
        )
        problems.extend(f"  {describe_finding(item)}" for item in outstanding)
    if not problems:
        return
    raise ValidationError(
        [
            f"Release requires a current approved {spec.kind} {spec.reading} "
            f"recorded with `mag review record --kind {spec.kind}`.",
            *problems,
        ]
    )
