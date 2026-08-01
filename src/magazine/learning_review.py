"""Learning-review records: three readers, one verdict on the teaching material.

The render review binds a visual decision to the exact PDFs; the evidence review
binds a per-article audit to the manuscripts and extractions it compared; the
edition review binds one issue verdict to every byte of the assembled object.
This is the fourth kind, and the one with the *narrowest* subject of the four.
Nadia, Marcus and Priya (see ``prompts/learning-review.md``) do not read the
issue and they do not read the features.  They read the editor-authored
furniture -- the deck, the key ideas box, the glossary, the fifteen-minute
exercise, the cheat sheet, the editors' diagram captions -- and the explainer,
the in-a-nutshell piece written to stand alone.  The article bodies' truth
belongs to the fact-checker, and the personas are explicitly told not to judge
it.

**What the record binds, and why it is not the edition review's binding.**
Exactly two things: the SHA-256 of a canonical *furniture projection* (below),
and, per explainer, the SHA-256 of that explainer's manuscript.  Nothing else.
In particular it does **not** bind every article manuscript, which is what the
edition review does and what the obvious copy-paste would have produced here.

That difference is the whole reason this kind exists as its own module.  The
edition verdict is a judgement about all the manuscripts *at once* -- whether
two pieces make the same point, whether the strongest one opens -- so any
manuscript moving genuinely invalidates it.  A learning verdict is a judgement
about a specific, small set of bytes that three readers actually had in front of
them.  A typo fixed in some feature's third paragraph moves nothing any persona
read: Nadia was shown the explainer and its furniture, Marcus run A was shown
the furniture with the body deliberately withheld, Priya was shown the furniture
against the pinned source.  Staling their verdict on that edit would teach the
bench that staleness is noise, and a staleness signal people learn to ignore is
worse than none.  So the binding is narrow on purpose, and it is narrow in a way
that is *auditable*: the projection is an explicit list of strings, not a
"hash whatever seems relevant" heuristic.

**The furniture projection.**  Most of the furniture the prompt names has no
data model.  There is no key-ideas, glossary, cheat-sheet or exercise field
anywhere in ``edition.yaml`` or ``schemas/edition.schema.json`` today.  The
prompt already anticipates this and says "Judge only the furniture that
exists", so the binding covers the editor-authored strings the manifest can
currently express, and nothing else:

* the edition ``title`` and ``subtitle``;
* the ``cover`` headline, deck, back text and edition label;
* per article, in id order: ``title``, ``short_title``, ``display_emphasis``,
  ``author_note``, its ``key_ideas`` lines, and each figure's ``id``,
  ``caption``, ``alt_text`` and ``anchor`` -- the key-ideas box and the diagram
  captions the prompt names, plus the display copy that frames them;
* the closing plate titles.

Those are read out of :attr:`Edition.raw`, the parsed manifest mapping, so this
module needs no change to ``manifest.py`` to see them.  An absent key is simply
absent from the projection rather than defaulted to ``""``, so a field that is
added and then removed hashes back to the value it had before -- a projection
that invented empty strings would make "this manifest never had a deck" and
"this manifest has an empty deck" hash differently, and only one of those is a
change to what a reader saw.  A present-but-blank value is treated as absent for
the same reason.  The projection is canonicalized and hashed by
:func:`magazine.render_review.projection_sha256`, the bench's shared mechanism,
so the hash is a function of the *values*, not of YAML key order, indentation or
quoting style.  The edition record uses the same mechanism over a very
different projection -- broad where this one is narrow, and subtractive where
this one is an explicit list -- because the canonicalization is common and the
choice of what to bind is per kind.

Hashing ``edition.yaml`` whole was considered and rejected.  The manifest also
carries source ids and ``source_body_sha256`` pins, manuscript paths, figure
``asset_id`` and ``source_caption_sha256`` values, opener art credits, rights
blocks and the release ``status`` -- none of which any persona read.  Re-pinning
a source after a re-extraction would spuriously stale a verdict about whether a
glossary entry is wrong.  The projection costs an explicit key list; the
whole-file hash would have cost the signal.

**This projection is the furniture as the data model can currently express it.**
``key_ideas`` is the first of the prompt's named furniture to acquire a real
manifest field, and it is bound here.  When the manifest grows a ``glossary``,
``cheat_sheet`` or ``try_it`` field -- and it should; the personas are judging
furniture that today lives only inside manuscripts -- extending the
``_FURNITURE_*`` tuples here is mandatory.  Once a learning record has actually
shipped, each such extension must also bump
:data:`LEARNING_REVIEW_SCHEMA_VERSION`, because a record written before the
extension bound strictly less than one written after and the two must not be
read as the same claim.  ``key_ideas`` was folded in before the first record was
written anywhere, so it needed no bump: there is no earlier record to disagree
with.

**Explainer detection reads the manifest's own marker.**  An article declares
``content_mode: in_a_nutshell`` -- the mode registered in
:data:`magazine.manifest.CONTENT_MODES` for the teaching explainer, and one of
the two :data:`magazine.manifest.EDITOR_VOICE_CONTENT_MODES` -- and that
declaration is what this module reads.  It replaces an earlier id heuristic
(exactly ``in-a-nutshell``, or any id ending ``-in-a-nutshell``) written while
the mode was still being added: the heuristic silently missed an explainer named
for its subject rather than for the section, and a missed explainer under-binds
the verdict without saying so.  The caller may still override the detection with
an explicit list, which is the escape hatch for an edition whose explainer is
mis-declared; the default is the declaration.  An edition with no explainer is
an ordinary state, not a failure: ``explainers`` is simply empty and the
furniture still binds.
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

LEARNING_REVIEW_SCHEMA_VERSION = 1

# Only one shape has ever been written.  Older versions will be listed here when
# there are any -- and there will be, the first time the manifest grows a real
# furniture field (see the module docstring).
_SUPPORTED_SCHEMA_VERSIONS = (1,)

_LABEL = "Learning review"

# The manifest's marker for the teaching explainer.  Named here rather than
# imported so this module keeps its manifest dependency to TYPE_CHECKING; the
# test suite asserts the string is still a registered content mode.
EXPLAINER_CONTENT_MODE = "in_a_nutshell"

LEARNING_PERSONAS = ("nadia", "marcus", "priya")

# Every structured finding must say which reader filed it: the same sentence
# means different things from Nadia (the piece never says this) and from Priya
# (the piece says this and the source disagrees), and triage needs to know
# which.  A plain-string ``--finding`` typed by a human stays exempt.
_REQUIRED_FINDING_KEYS = ("severity", "note", "persona")

_TAKEAWAY_VERDICTS = ("supported", "unsupported", "contradicted")

# --- The furniture projection ------------------------------------------------
#
# Extending any of these tuples changes what an approved record claims to have
# covered, so it must come with a LEARNING_REVIEW_SCHEMA_VERSION bump.

_FURNITURE_EDITION_KEYS = ("title", "subtitle")
_FURNITURE_COVER_KEYS = ("headline", "deck", "back_text", "edition_label")
_FURNITURE_ARTICLE_KEYS = ("title", "short_title", "display_emphasis", "author_note")
_FURNITURE_FIGURE_KEYS = ("id", "caption", "alt_text", "anchor")
# Furniture the manifest holds as a list of lines rather than one string.  The
# key-ideas box is the first of these to acquire a real field, and it is the
# furniture the personas read hardest -- it is Marcus's entire run-A input and
# the box Nadia answers from -- so leaving it out of the binding would let the
# one thing they read most be rewritten under an approved verdict.
_FURNITURE_ARTICLE_LIST_KEYS = ("key_ideas",)

# The keys a comprehension row and a manager-takeaways row are written in.  The
# prompt lists them in a deliberate reading order and a record should read the
# way the judge wrote it; anything else the judge said is preserved after these.
_COMPREHENSION_KEYS = ("persona", "language", "correct", "of", "questions")
_QUESTION_KEYS = ("question", "answer", "cite", "correct")
_TAKEAWAY_KEYS = ("article", "decision", "claims", "adjudication")
_ADJUDICATION_KEYS = ("item", "verdict", "cite")


def learning_review_path(editions_dir: Path, edition_id: str) -> Path:
    return editions_dir / edition_id / "reviews" / "learning.yaml"


def explainer_article_ids(edition: "Edition") -> tuple[str, ...]:
    """The edition's in-a-nutshell pieces, in running order.

    Detection by declaration: an explainer is an article whose ``content_mode``
    is :data:`EXPLAINER_CONTENT_MODE`, whatever it is called.  An edition with
    no explainer returns ``()``, which is an ordinary answer: the personas still
    have furniture to judge.
    """

    return tuple(
        article.id
        for article in edition.articles
        if article.content_mode == EXPLAINER_CONTENT_MODE
    )


def furniture_projection(edition: "Edition") -> dict[str, Any]:
    """The editor-authored strings the personas read, as the manifest holds them.

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


def current_learning_bindings(
    edition: "Edition", *, explainer_ids: Iterable[str] | None = None
) -> dict[str, Any]:
    """Everything a learning verdict depends on, hashed as of right now.

    ``explainer_ids=None`` detects the explainers from their declared
    ``content_mode``.  An explicit iterable overrides the detection entirely --
    that is the escape hatch for an edition whose explainer is mis-declared --
    and refuses ids the edition does not carry, because binding a manuscript
    that does not exist would record a verdict over nothing.
    """

    if explainer_ids is None:
        selected: tuple[str, ...] = explainer_article_ids(edition)
    else:
        requested = [str(item).strip() for item in explainer_ids if str(item).strip()]
        known = {article.id for article in edition.articles}
        unknown = sorted(set(requested) - known)
        if unknown:
            raise ValidationError(
                f"{_LABEL} cannot bind explainers the edition does not carry: "
                + ", ".join(unknown)
            )
        selected = tuple(dict.fromkeys(requested))
    manuscripts = {article.id: article.manuscript for article in edition.articles}
    return {
        "furniture_sha256": furniture_sha256(edition),
        "explainers": {
            article_id: {"manuscript_sha256": sha256(manuscripts[article_id])}
            for article_id in sorted(selected)
        },
    }


def load_learning_review(path: Path, *, edition_id: str) -> dict[str, Any] | None:
    """Read a recorded verdict, accumulating every complaint before refusing.

    A record with a bad persona, an out-of-range score and a broken hash should
    report all three, so this collects errors and raises once -- the same
    contract every other record loader in the package keeps.
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
    errors.extend(finding_errors(findings, label=_LABEL, required=_REQUIRED_FINDING_KEYS))
    errors.extend(_finding_persona_errors(findings))
    if data.get("result") == "changes_required" and not findings:
        errors.append(f"A changes_required {_LABEL.lower()} needs at least one finding")
    # Scores are read and validated, never consulted.  Nothing below compares
    # them and nothing in this module lets one reach a gate.
    errors.extend(score_errors(data.get("scores"), label=_LABEL))
    if not _is_sha256(data.get("furniture_sha256")):
        errors.append(f"{_LABEL} has invalid furniture_sha256")
    explainers = data.get("explainers")
    if explainers is None:
        explainers = {}
    if not isinstance(explainers, Mapping):
        # An empty mapping is legal -- an edition need not carry an explainer --
        # but a non-mapping is a record whose explainer bindings cannot be read.
        errors.append(f"{_LABEL} explainers must be a mapping")
        explainers = {}
    for article_id, row in explainers.items():
        if not isinstance(row, Mapping):
            errors.append(f"{_LABEL} explainer {article_id} must be a mapping")
            continue
        if not _is_sha256(row.get("manuscript_sha256")):
            errors.append(f"{_LABEL} explainer {article_id} has invalid manuscript_sha256")
    # ``comprehension`` and ``manager_takeaways`` are absent-legal: a record can
    # be written from a human's reading rather than from a full three-persona
    # run.  Present-but-malformed is not.
    _, comprehension_errors = _normalize_comprehension(data.get("comprehension") or ())
    errors.extend(comprehension_errors)
    _, takeaway_errors = _normalize_takeaways(data.get("manager_takeaways") or ())
    errors.extend(takeaway_errors)
    if errors:
        raise ValidationError(errors)
    return dict(data)


def _is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and set(text) <= _HEX_DIGITS


def _finding_persona_errors(findings: Any) -> list[str]:
    """Check the persona *vocabulary*, which the shared helper cannot know.

    ``review_findings`` enforces that a required key is present and non-empty;
    only this kind knows that the value must be one of three named readers.  A
    finding filed by "the editor" is not a persona finding, and storing it as
    one would make the persona field unqueryable.
    """

    if not isinstance(findings, list):
        return []
    errors: list[str] = []
    for index, item in enumerate(findings, start=1):
        if not isinstance(item, Mapping):
            continue
        persona = str(item.get("persona") or "").strip()
        if persona and persona not in LEARNING_PERSONAS:
            errors.append(
                f"{_LABEL} finding {index} persona must be "
                + ", ".join(LEARNING_PERSONAS)
            )
    return errors


def _normalize_comprehension(entries: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate Nadia's runs structurally, and store them as she wrote them.

    Structure and vocabulary are checked; *counts* deliberately are not.  The
    prompt asks for six questions and one run per language, but a recorder that
    refused a five-question run would lose the whole record -- including the
    findings, which are the part that gates -- over a shortfall the findings
    already describe.  Storing a short run and letting the reader see it is
    short is strictly more informative than refusing to store it.

    ``answer`` and ``cite`` may be null and are preserved as such: the prompt
    writes ``answer: null`` for a question the piece never answers, and that
    null is the evidence of the failure.
    """

    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    if isinstance(entries, Mapping) or not isinstance(entries, (list, tuple)):
        return [], [f"{_LABEL} comprehension must be a list of runs"]
    for index, entry in enumerate(entries, start=1):
        label = f"{_LABEL} comprehension {index}"
        if not isinstance(entry, Mapping):
            errors.append(f"{label} must be a mapping")
            continue
        persona = str(entry.get("persona") or "").strip()
        if not persona:
            errors.append(f"{label} requires a persona")
        elif persona not in LEARNING_PERSONAS:
            errors.append(f"{label} persona must be " + ", ".join(LEARNING_PERSONAS))
        if not str(entry.get("language") or "").strip():
            errors.append(f"{label} requires a language")
        correct = entry.get("correct")
        of = entry.get("of")
        counts_valid = True
        for key, value in (("correct", correct), ("of", of)):
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"{label} {key} must be an integer")
                counts_valid = False
        if counts_valid and not 0 <= int(correct) <= int(of):
            errors.append(f"{label} correct must be between 0 and of")
        questions = entry.get("questions")
        if not isinstance(questions, (list, tuple)):
            errors.append(f"{label} questions must be a list")
            questions = ()
        for position, question in enumerate(questions, start=1):
            if not isinstance(question, Mapping):
                errors.append(f"{label} question {position} must be a mapping")
                continue
            if not str(question.get("question") or "").strip():
                errors.append(f"{label} question {position} requires a question")
            if not isinstance(question.get("correct"), bool):
                errors.append(f"{label} question {position} correct must be true or false")
        rows.append(
            _ordered(
                entry,
                _COMPREHENSION_KEYS,
                questions=[
                    _ordered(question, _QUESTION_KEYS)
                    for question in questions
                    if isinstance(question, Mapping)
                ],
            )
        )
    return rows, errors


def _normalize_takeaways(entries: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate Marcus's two runs as stored: run A verbatim, run B's verdicts.

    The prompt's boundary between the runs is a fact about how the judge was
    driven, not something a recorder can verify after the event; what the record
    can hold is the shape -- the decision and claims he wrote without the body,
    and one adjudicated verdict per item once he had it.  As with comprehension,
    the count of claims and verdicts is not enforced: an adjudication that
    resolved three of four items is a real, storable, visibly incomplete run.
    """

    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    if isinstance(entries, Mapping) or not isinstance(entries, (list, tuple)):
        return [], [f"{_LABEL} manager_takeaways must be a list"]
    for index, entry in enumerate(entries, start=1):
        label = f"{_LABEL} manager_takeaways {index}"
        if not isinstance(entry, Mapping):
            errors.append(f"{label} must be a mapping")
            continue
        for key in ("article", "decision"):
            if not str(entry.get(key) or "").strip():
                errors.append(f"{label} requires a non-empty {key}")
        claims = entry.get("claims")
        if not isinstance(claims, (list, tuple)):
            errors.append(f"{label} claims must be a list")
            claims = ()
        elif any(not str(claim or "").strip() for claim in claims):
            errors.append(f"{label} claims must be non-empty strings")
        adjudication = entry.get("adjudication")
        if not isinstance(adjudication, (list, tuple)):
            errors.append(f"{label} adjudication must be a list")
            adjudication = ()
        for position, item in enumerate(adjudication, start=1):
            if not isinstance(item, Mapping):
                errors.append(f"{label} adjudication {position} must be a mapping")
                continue
            if not str(item.get("item") or "").strip():
                errors.append(f"{label} adjudication {position} requires an item")
            verdict = str(item.get("verdict") or "").strip()
            if verdict not in _TAKEAWAY_VERDICTS:
                errors.append(
                    f"{label} adjudication {position} verdict must be "
                    + ", ".join(_TAKEAWAY_VERDICTS)
                )
        rows.append(
            _ordered(
                entry,
                _TAKEAWAY_KEYS,
                claims=[claim for claim in claims],
                adjudication=[
                    _ordered(item, _ADJUDICATION_KEYS)
                    for item in adjudication
                    if isinstance(item, Mapping)
                ],
            )
        )
    return rows, errors


def _ordered(
    source: Mapping[str, Any], keys: tuple[str, ...], **replacements: Any
) -> dict[str, Any]:
    """One row with its known keys in a fixed order and everything else kept.

    Values are stored exactly as authored -- no stripping, no stringifying --
    because a stored run has to read back as the judge emitted it, ``null``
    answers included.  Unknown keys follow the known ones, sorted: the recorder
    is not the right place to decide a judge said too much.
    """

    row = {key: source[key] for key in keys if key in source}
    row.update({key: value for key, value in replacements.items() if key in row})
    for key in sorted(source):
        if key not in row:
            row[key] = source[key]
    return row


def learning_drift(recorded: Mapping[str, Any], current: Mapping[str, Any]) -> list[str]:
    """Name exactly what moved since the three readers read it.

    Two names only: ``furniture`` when the projection hash moved, and
    ``explainer:<id>`` for any explainer whose manuscript moved -- or that
    appeared or vanished, since either changes which pieces the verdict covered.
    The order is fixed (furniture first, then explainers sorted by id) so the
    same drift always renders the same way in a status table or a refusal.

    Note what is *not* here: no feature manuscript, no source pin, no figure
    asset.  That is the point of the kind (see the module docstring).
    """

    drift: list[str] = []
    if recorded.get("furniture_sha256") != current.get("furniture_sha256"):
        drift.append("furniture")
    recorded_explainers = recorded.get("explainers") or {}
    current_explainers = current.get("explainers") or {}
    for article_id in sorted(set(recorded_explainers) | set(current_explainers)):
        recorded_row = recorded_explainers.get(article_id) or {}
        current_row = current_explainers.get(article_id) or {}
        if recorded_row.get("manuscript_sha256") != current_row.get("manuscript_sha256"):
            drift.append(f"explainer:{article_id}")
    return drift


def learning_review_status(
    review: dict[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Any],
) -> dict[str, Any]:
    """The record's standing against the furniture and explainers on disk now.

    There is one verdict for the whole issue's teaching material, so ``drift``
    is a flat list and any entry in it makes that verdict stale.  Everything the
    record carries travels out -- findings, scores, both persona blocks --
    because status is how the CLI exposes a record: someone asking why the issue
    is not releasable wants Nadia's five-of-six in the same breath as the word
    ``changes_required``.

    Scores are reported and never consulted.  A record whose scores changed but
    whose bound bytes did not is *not* stale; see the drift function.
    """

    base: dict[str, Any] = {
        "status": "required_before_release",
        "reviewer": None,
        "reviewed_at": None,
        "result": None,
        "findings": [],
        "scores": {},
        "comprehension": [],
        "manager_takeaways": [],
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
            "comprehension": list(review.get("comprehension") or []),
            "manager_takeaways": list(review.get("manager_takeaways") or []),
        }
    )
    drift = learning_drift(review, bindings)
    base["drift"] = drift
    if review.get("edition_id") != edition_id or drift:
        base["status"] = "stale"
    elif review.get("result") == "approved":
        base["status"] = "approved"
    else:
        base["status"] = "changes_required"
    return base


def create_learning_review(
    *,
    edition_id: str,
    reviewer: str,
    result: str,
    bindings: Mapping[str, Any],
    findings: Iterable[Any] = (),
    scores: Mapping[str, Any] | None = None,
    comprehension: Iterable[Any] = (),
    manager_takeaways: Iterable[Any] = (),
    notes: str = "",
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    """Compose the record, refusing anything that would store a false verdict.

    The refusals mirror the bench's -- an unnamed reviewer, an unrecognised
    result, a ``changes_required`` with nothing to act on -- plus the two this
    kind needs of its own: a finding must name the persona who filed it, and the
    bindings must carry a furniture hash, since a record that binds no furniture
    is not a verdict on teaching material at all.

    ``scores`` is record-level here, unlike the line and fact records, because
    there is one verdict for the whole issue's teaching material rather than one
    per piece.  It is stored as authored and never looked at again by this
    module.
    """

    reviewer = reviewer.strip()
    result = result.strip()
    clean_findings = normalize_findings(
        findings, label=_LABEL, required=_REQUIRED_FINDING_KEYS
    )
    persona_errors = _finding_persona_errors(clean_findings)
    if persona_errors:
        raise ValidationError(persona_errors)
    clean_scores = normalize_scores(scores, label=_LABEL)
    clean_comprehension, comprehension_errors = _normalize_comprehension(
        list(comprehension)
    )
    if comprehension_errors:
        raise ValidationError(comprehension_errors)
    clean_takeaways, takeaway_errors = _normalize_takeaways(list(manager_takeaways))
    if takeaway_errors:
        raise ValidationError(takeaway_errors)
    if not reviewer:
        raise ValidationError(f"{_LABEL} requires a reviewer")
    if result not in REVIEW_RESULTS:
        raise ValidationError(f"{_LABEL} result must be approved or changes_required")
    if result == "changes_required" and not clean_findings:
        raise ValidationError(f"A changes_required {_LABEL.lower()} needs at least one finding")
    if not _is_sha256(bindings.get("furniture_sha256")):
        raise ValidationError(
            f"{_LABEL} requires the furniture the readers read "
            "(bindings are missing furniture_sha256)"
        )
    timestamp = reviewed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    explainers = {
        article_id: {"manuscript_sha256": row.get("manuscript_sha256")}
        for article_id, row in (bindings.get("explainers") or {}).items()
    }
    return {
        "schema_version": LEARNING_REVIEW_SCHEMA_VERSION,
        "edition_id": edition_id,
        "reviewer": reviewer,
        "reviewed_at": timestamp,
        "result": result,
        "findings": clean_findings,
        "scores": clean_scores,
        "comprehension": clean_comprehension,
        "manager_takeaways": clean_takeaways,
        "notes": notes.strip(),
        "furniture_sha256": bindings.get("furniture_sha256"),
        "explainers": explainers,
    }


def write_learning_review(path: Path, record: dict[str, Any]) -> Path:
    # The render review's writer is a generic atomic YAML replacement; every
    # review kind shares it rather than growing one of its own.
    return write_render_review(path, record)


def require_approved_learning_review(
    review: dict[str, Any] | None,
    *,
    edition_id: str,
    bindings: Mapping[str, Any],
) -> None:
    """Refuse a release whose learning verdict is missing, stale, or negative.

    Deliberately NOT wired into the release path yet: the personas' thresholds
    are still being calibrated against edition 004, and gating releases on a
    judgement the bench does not yet trust would block work over a measurement
    problem.  The function is written, tested, and unreferenced by ``release``
    on purpose; flipping it on is a follow-up, and keeping it here means that
    follow-up is a one-line call rather than a new gate.
    """

    status = learning_review_status(review, edition_id=edition_id, bindings=bindings)
    if status["status"] == "approved":
        return
    detail = f"learning review is {status['status']}"
    if status["status"] == "stale" and review is not None and status["drift"]:
        # The drift list is already the re-read worklist; naming it in the
        # refusal saves the operator a second command.
        detail += "; changed since the recorded read: " + ", ".join(status["drift"])
    raise ValidationError(
        [
            "Release requires a current approved learning review recorded with "
            "`mag review record --kind learning`.",
            detail,
        ]
    )
