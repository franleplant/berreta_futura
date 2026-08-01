"""Edition-review records: the managing editor's verdict on the whole issue.

The render review binds a visual decision to the exact PDFs it looked at; the
evidence review binds a per-article audit to the manuscripts and extractions it
compared.  This is the third kind, and the one whose subject is not a piece at
all.  The managing editor (see ``prompts/edition-review.md``) reads the
editorial, then every manuscript in running order, and asks whether these
pieces belong between the same covers, in this order, under this cover line:
the through-line, the running order, the cover promise, redundancy across
pieces, the editorial's own argument.  Every one of those questions is about
the issue as an assembled object, so the record stores exactly one verdict for
the whole edition and never a per-article one.

**What the record binds.**  The SHA-256 of the editorial, the SHA-256 of
``edition.yaml``, and the SHA-256 of *every* article manuscript.  Any one of
them moving stales the verdict.  That is correct rather than unfortunate, and
it is the one place this kind deliberately departs from its siblings: coherence
is a function of all of those bytes *at once*.  Whether the strongest piece
opens, whether two pieces make the same point, whether the cover deck promises
what the issue delivers -- none of those survive one manuscript being rewritten
just because the other manuscripts did not change.  A rewritten piece can
introduce the redundancy that was not there before, or blunt the argument the
editorial claimed the issue makes.  So there is **no partial rebind here**.  The
evidence and line records have ``--articles`` because an audit of article A
against its sources is genuinely independent of article B; an issue verdict is
not decomposable that way, and offering a way to re-read one piece and keep the
issue-level verdict would be offering a way to launder a stale judgement.  The
whole issue is re-read, or the verdict stays stale.

``edition.yaml`` is bound for the same reason the manuscripts are.  The running
order, the cover headline and deck, the contents order, and each article's
``content_mode`` all live in the manifest and are all inputs the judge is
explicitly told to read.  A cover-line rewrite changes what the issue promises
without touching a single manuscript, and it must stale an issue verdict just
as a manuscript rewrite does.

**What is bound is the manifest's content, not its bytes.**  The record hashes
a canonical projection of the parsed manifest with the edition's *filesystem
identity* removed: the top-level ``id``, the release ``status``, and the
``editions/<id>/`` and ``output/<id>/`` prefixes inside every path the manifest
carries.  Hashing the file whole was the first implementation and it was wrong
in a way that only showed up at the end of an edition: ``mag finish`` renames a
collecting edition to its stable id and rewrites exactly those things -- the
``id`` line and every path around it -- so an approved issue verdict read as
stale immediately after finish, through no editorial change at all.  Release
then rewrites ``status`` and re-serializes the whole file, so a re-record would
not have survived either.  A verdict that always stales at the moment it
matters teaches the bench to ignore staleness, which is worse than having no
signal; and once this kind gates release, it would have blocked every finish.

The projection is subtractive rather than an allowlist, and that is the
deliberate difference from the learning record's furniture projection (see
``learning_review``).  A learning verdict covers a small, named set of strings
three readers were shown, so listing them is the honest description.  An issue
verdict is a judgement about the assembled object, so *everything the manifest
says about the issue is bound* -- the running order, the cover copy, the
per-article titles and content modes, the sections, the rights block -- and the
projection names only the handful of keys that are about where the edition
lives on disk rather than what the issue is.  Written the other way round, a
field added to the schema later would silently fall out of an approved
verdict's coverage; written this way it is bound the day it exists.  Both
projections share the canonicalization in
:func:`magazine.render_review.projection_sha256` and nothing else, because the
mechanics are common and the policies are opposites.

Canonicalizing also makes the binding indifferent to *how* the manifest is
written: ``mag pin`` and the release transaction both re-serialize the file
through ``dump_yaml``, and a re-wrapped long line is not an editorial change.

The manifest path is still passed in rather than derived from the edition,
because the caller already knows it is ``editions/<id>/edition.yaml`` and path
construction belongs with the caller that owns the layout.

An edition with no editorial binds ``editorial_sha256: None``.  That is an
ordinary state -- a section-shaped edition need not open with one -- not an
error, and it must not read as drift against an edition that still has none.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping

from .errors import ValidationError
from .io import load_structured
from .render_review import (
    REVIEW_RESULTS,
    projection_sha256,
    sha256,
    write_render_review,
)
from .review_findings import (
    finding_errors,
    normalize_findings,
    normalize_scores,
    score_errors,
)

if TYPE_CHECKING:
    from .manifest import Edition

_HEX_DIGITS = set("0123456789abcdef")

EDITION_REVIEW_SCHEMA_VERSION = 1

# Only one shape has ever been written.  Older versions will be listed here
# when there are any -- the tuple exists so that day is a one-line change and
# the refusal message keeps naming every version that still loads.
_SUPPORTED_SCHEMA_VERSIONS = (1,)

_LABEL = "Edition review"

# The manifest keys that name where the edition lives rather than what the
# issue is.  ``mag finish`` rewrites the id when it gives a collection its
# stable identity and the release transaction writes the status; neither is a
# change the managing editor made or would judge.  Everything else the manifest
# carries stays bound -- see the module docstring for why the list is this way
# round.
_IDENTITY_KEYS = ("id", "status")

# What an edition-relative path is normalized to, so ``editions/004-unreleased/
# articles/x.md`` and ``editions/004-the-name/articles/x.md`` project alike.
# The placeholder keeps the rest of the path bound: re-pointing an article at a
# different manuscript file is still an editorial change.
_EDITION_PLACEHOLDER = "<edition>"

# The two prefixes ``rename_collecting_edition`` rewrites inside the edition's
# text files; normalizing the same two is what makes the binding survive the
# rename exactly, and nothing more than the rename.
_IDENTITY_PATH_ROOTS = ("editions", "output")


def edition_review_path(editions_dir: Path, edition_id: str) -> Path:
    return editions_dir / edition_id / "reviews" / "edition.yaml"


def manifest_projection(manifest: Mapping[str, Any], *, edition_id: str) -> dict[str, Any]:
    """The manifest as an editorial statement, with its filesystem identity out.

    Everything the manifest says about the issue survives; the edition's own
    ``id``, its release ``status``, and the ``editions/<id>/`` and
    ``output/<id>/`` prefixes inside its paths do not.  Mapping keys are
    stringified on the way through so a hand-written manifest cannot make the
    canonical dump fail on a key type YAML allows and JSON does not.
    """

    return {
        str(key): _without_identity(value, edition_id)
        for key, value in manifest.items()
        if str(key) not in _IDENTITY_KEYS
    }


def _without_identity(value: Any, edition_id: str) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _without_identity(item, edition_id) for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_without_identity(item, edition_id) for item in value]
    if isinstance(value, str):
        for root in _IDENTITY_PATH_ROOTS:
            value = value.replace(
                f"{root}/{edition_id}/", f"{root}/{_EDITION_PLACEHOLDER}/"
            )
        return value
    return value


def manifest_projection_sha256(manifest_path: Path, *, edition_id: str) -> str:
    """One hash over the manifest's editorial content, read from disk."""

    return projection_sha256(
        manifest_projection(load_structured(manifest_path), edition_id=edition_id)
    )


def current_edition_bindings(edition: "Edition", *, manifest_path: Path) -> dict[str, Any]:
    """Everything an issue verdict depends on, hashed as of right now.

    The editorial, the manifest, and each article's manuscript.  The manifest
    is in here because the judge reads it: the running order it defines, the
    cover headline and deck it carries, and the contents order it fixes are all
    part of what the verdict is a verdict *about*, so rewriting a cover line
    after approval must stale the record exactly as rewriting a manuscript
    does.  It is bound as a projection rather than as bytes so that renaming
    the edition does not read as an editorial change; the module docstring says
    why at length.

    An edition without an editorial binds ``editorial_sha256: None`` rather
    than raising -- the absence is a fact about the edition, and a verdict on
    an issue that opens without an editorial is still a verdict.
    """

    return {
        "editorial_sha256": sha256(edition.editorial.path) if edition.editorial else None,
        "manifest_sha256": manifest_projection_sha256(
            manifest_path, edition_id=edition.id
        ),
        "articles": {
            article.id: {"manuscript_sha256": sha256(article.manuscript)}
            for article in edition.articles
        },
    }


def load_edition_review(path: Path, *, edition_id: str) -> dict[str, Any] | None:
    """Read a recorded verdict, accumulating every complaint before refusing.

    A record with three problems should report three problems; the loader
    therefore collects errors and raises once, the way every other record
    loader in the package does.
    """

    if not path.is_file():
        return None
    data = load_structured(path)
    errors: list[str] = []
    if data.get("schema_version") not in _SUPPORTED_SCHEMA_VERSIONS:
        errors.append(
            f"{_LABEL} schema_version must be "
            + " or ".join(str(version) for version in _SUPPORTED_SCHEMA_VERSIONS)
        )
    if data.get("edition_id") != edition_id:
        errors.append(
            f"{_LABEL} edition_id {data.get('edition_id')!r} does not match {edition_id!r}"
        )
    if str(data.get("result") or "") not in REVIEW_RESULTS:
        errors.append(f"{_LABEL} result must be approved or changes_required")
    for key in ("reviewer", "reviewed_at"):
        if not str(data.get(key) or "").strip():
            errors.append(f"{_LABEL} requires {key}")
    findings = data.get("findings", [])
    errors.extend(finding_errors(findings, label=_LABEL))
    if data.get("result") == "changes_required" and not findings:
        errors.append(f"A changes_required {_LABEL.lower()} needs at least one finding")
    # Scores are read and validated, never consulted.  They are advisory by
    # construction (see review_findings): nothing below compares them, and
    # nothing in this module lets them reach a gate.
    errors.extend(score_errors(data.get("scores"), label=_LABEL))
    if not _is_sha256(data.get("manifest_sha256")):
        errors.append(f"{_LABEL} has invalid manifest_sha256")
    # An absent or null editorial binding is the legal record of an edition
    # that opens without an editorial; a present-but-malformed one is not.
    if data.get("editorial_sha256") is not None and not _is_sha256(data.get("editorial_sha256")):
        errors.append(f"{_LABEL} has invalid editorial_sha256")
    articles = data.get("articles")
    if not isinstance(articles, dict):
        # A one-piece issue is a legal issue, so the mapping may be small; an
        # absent mapping is a record that binds no manuscripts at all, which
        # would let every piece move under an approved verdict.
        errors.append(f"{_LABEL} requires an articles mapping")
        articles = {}
    for article_id, row in articles.items():
        if not isinstance(row, dict):
            errors.append(f"{_LABEL} article {article_id} must be a mapping")
            continue
        if not _is_sha256(row.get("manuscript_sha256")):
            errors.append(f"{_LABEL} article {article_id} has invalid manuscript_sha256")
    if errors:
        raise ValidationError(errors)
    return dict(data)


def _is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and set(text) <= _HEX_DIGITS


def edition_drift(recorded: Mapping[str, Any], current: Mapping[str, Any]) -> list[str]:
    """Name exactly what moved since the issue was read.

    The names are for the human deciding whether to re-read the issue, so they
    are the things a person can go and look at: ``editorial``, ``edition.yaml``,
    and ``manuscript:<article-id>`` for any article whose manuscript hash moved
    -- or that joined or left the bound set, since either changes the issue the
    verdict was about.  The order is fixed (editorial, manifest, then
    manuscripts sorted by id) so the same drift always renders the same way in
    a status table or a refusal message.
    """

    drift: list[str] = []
    if recorded.get("editorial_sha256") != current.get("editorial_sha256"):
        drift.append("editorial")
    if recorded.get("manifest_sha256") != current.get("manifest_sha256"):
        drift.append("edition.yaml")
    recorded_articles = recorded.get("articles") or {}
    current_articles = current.get("articles") or {}
    for article_id in sorted(set(recorded_articles) | set(current_articles)):
        recorded_row = recorded_articles.get(article_id) or {}
        current_row = current_articles.get(article_id) or {}
        if recorded_row.get("manuscript_sha256") != current_row.get("manuscript_sha256"):
            drift.append(f"manuscript:{article_id}")
    return drift


def edition_review_status(
    review: dict[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Any],
) -> dict[str, Any]:
    """The record's standing against the edition as it is on disk right now.

    There are no per-article rows to report, because there is no per-article
    verdict: ``drift`` is a flat list naming what moved, and any entry in it
    makes the single verdict stale.  The findings and the scores travel out
    through the status because status is how the CLI exposes a record -- a
    reader asking why the issue is not releasable wants the findings in the
    same breath as the word ``changes_required``.
    """

    base: dict[str, Any] = {
        "status": "required_before_release",
        "reviewer": None,
        "reviewed_at": None,
        "result": None,
        "findings": [],
        "scores": {},
        "drift": [],
    }
    if review is None:
        return base
    base.update(
        {
            "reviewer": review.get("reviewer"),
            "reviewed_at": review.get("reviewed_at"),
            "result": review.get("result"),
            "findings": list(review.get("findings", [])),
            "scores": dict(review.get("scores") or {}),
        }
    )
    drift = edition_drift(review, bindings)
    base["drift"] = drift
    if review.get("edition_id") != edition_id or drift:
        base["status"] = "stale"
    elif review.get("result") == "approved":
        base["status"] = "approved"
    else:
        base["status"] = "changes_required"
    return base


def create_edition_review(
    *,
    edition_id: str,
    reviewer: str,
    result: str,
    bindings: Mapping[str, Any],
    findings: Iterable[Any] = (),
    scores: Mapping[str, Any] | None = None,
    notes: str = "",
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    """Compose the record, refusing anything that would store a false verdict.

    The refusals mirror the evidence recorder's -- an unnamed reviewer, a
    result the bench does not recognise, a ``changes_required`` with nothing to
    act on -- plus one this kind needs of its own: bindings that carry no
    ``manifest_sha256`` -- the manifest *projection* hash, see the module
    docstring -- describe an issue whose running order and cover line are
    unbound, which is not an issue verdict at all.

    Scores are stored as authored and never looked at again by this module.
    """

    reviewer = reviewer.strip()
    result = result.strip()
    clean_findings = normalize_findings(findings, label=_LABEL)
    clean_scores = normalize_scores(scores, label=_LABEL)
    if not reviewer:
        raise ValidationError(f"{_LABEL} requires a reviewer")
    if result not in REVIEW_RESULTS:
        raise ValidationError(f"{_LABEL} result must be approved or changes_required")
    if result == "changes_required" and not clean_findings:
        raise ValidationError(f"A changes_required {_LABEL.lower()} needs at least one finding")
    if not _is_sha256(bindings.get("manifest_sha256")):
        raise ValidationError(
            f"{_LABEL} requires the edition.yaml the issue was read in "
            "(bindings are missing manifest_sha256)"
        )
    timestamp = reviewed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    articles = {
        article_id: {"manuscript_sha256": row.get("manuscript_sha256")}
        for article_id, row in (bindings.get("articles") or {}).items()
    }
    return {
        "schema_version": EDITION_REVIEW_SCHEMA_VERSION,
        "edition_id": edition_id,
        "reviewer": reviewer,
        "reviewed_at": timestamp,
        "result": result,
        "findings": clean_findings,
        "scores": clean_scores,
        "notes": notes.strip(),
        "editorial_sha256": bindings.get("editorial_sha256"),
        "manifest_sha256": bindings.get("manifest_sha256"),
        "articles": articles,
    }


def write_edition_review(path: Path, record: dict[str, Any]) -> Path:
    # The render review's writer is a generic atomic YAML replacement; every
    # review kind shares it rather than growing one of its own.
    return write_render_review(path, record)


def require_approved_edition_review(
    review: dict[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Any],
) -> None:
    """Refuse a release whose issue verdict is missing, stale, or negative.

    Deliberately NOT wired into the release path yet: the managing editor's
    thresholds are still being calibrated against edition 004, and turning the
    gate on before they settle would block releases on a judgement the bench
    does not yet trust.  The function is written, tested, and unreferenced by
    ``release`` on purpose; flipping it on is a follow-up, and keeping it here
    means that follow-up is a one-line call rather than a new gate.
    """

    status = edition_review_status(review, edition_id=edition_id, bindings=bindings)
    if status["status"] == "approved":
        return
    detail = f"edition review is {status['status']}"
    if status["status"] == "stale" and review is not None and status["drift"]:
        # The drift list is already the re-read worklist; naming it in the
        # refusal saves the operator a second command.
        detail += "; changed since the recorded read: " + ", ".join(status["drift"])
    raise ValidationError(
        [
            "Release requires a current approved edition review recorded with "
            "`mag review record --kind edition`.",
            detail,
        ]
    )
