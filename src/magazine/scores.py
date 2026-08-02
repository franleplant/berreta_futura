"""The cross-edition score rollup: what the review bench has been saying, over time.

Every lens on the bench carries advisory 1-5 scores: the six per-piece lenses
score each piece they read, the whole-issue ``edition`` lens scores the issue,
and ``render`` -- which is a decision about artifacts rather than a lens -- carries
none.

**Nothing reads a score to decide anything, and that is the load-bearing fact
about this file.**  ``prompts/README.md`` is explicit: "Scores never reach the
writer.  They are advisory telemetry, and the failed edition scored fives, so a
number a writer can see is a number a writer can optimise."  It is equally
explicit that they never gate -- "Scores are integers 1 to 5, advisory, and never
gate a release.  No finding is ever softened or dropped to protect one" -- and
that they do not appear in the revision brief at all.  The bench that failed
scored 5/4/5/5/5 on a piece that was a paraphrase of its source with every
identifier removed, which is the whole case for making a rating telemetry
instead of a verdict.  ``review_findings`` refuses to let a score become
anything more; this module is the consequence.  So the scores have to be looked
at *somewhere*, by an editor and never by a writer, and
``editions/scores.yaml`` is that somewhere: one flat table of every score every
lens has recorded, across every edition, regenerated from the records and never
hand-edited.

Three properties follow from "derived artifact", and each one is a deliberate
departure from how the per-kind loaders behave:

* **It reads records as raw data, not through their loaders.**  Importing them
  would make a reporting command depend on seven validators and inherit all
  seven of their opinions -- and the count rises with the bench, which is
  exactly what it did when four kinds became seven.  What this module imports is
  the *list of kinds*, from the lens declaration in
  :mod:`magazine.produce_graph`, so a new lens is rolled up without this file
  being edited.  The rollup wants one thing from a record -- its scores -- and
  can read that off a plain mapping.

* **A bad record degrades the report; it never breaks the command.**  An
  unparseable file, a record that is not a mapping, a non-mapping ``scores``, a
  score that is a string or a ``0`` or a ``6``: each contributes no rows and is
  skipped in silence.  The authoritative validation lives in each kind's own
  loader, which raises properly and names the file; ``scores.py`` is
  deliberately not a second validator, and a broken record must not be able to
  take ``mag scores`` down with it.

* **The edition id comes from the directory, not from the record.**  A record
  whose ``edition_id`` disagrees with the directory it sits in is a real fault,
  and the per-kind loader catches it.  The rollup still files the row under the
  directory, because that is where a reader will go looking for it.

Rounds are the interesting part.  A review record file holds only the *latest*
verdict -- a re-record overwrites it -- so the history of a judge changing its
mind is visible only in git.  :func:`collect_score_rows` walks each record's
commit history to recover it, and degrades to a single round whenever it cannot
(see :func:`_record_rounds`).
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import mkstemp
from typing import Any, Iterable, Mapping

import yaml

from .io import dump_yaml
from .produce_graph import BENCH_REVIEW_KINDS, PIECE_JUDGE_KINDS
from .review_findings import SCORE_RANGE


SCORES_SCHEMA_VERSION = 1

# Every kind the bench requires before an edition ships, in repair order.
# Derived rather than written out: this tuple named ``evidence``, ``line``,
# ``edition`` and ``learning`` for as long as those were the kinds, and a literal
# here is a rollup that silently stops reporting the day a lens is added or
# retired -- silently, because a missing kind produces no rows rather than an
# error.  ``render`` is deliberately absent and always was: it is a decision
# about built artifacts rather than a lens, it carries no scores at all, and
# listing it would make every edition look like it is missing a record it never
# had.
SCORED_REVIEW_KINDS = BENCH_REVIEW_KINDS

# The kinds whose lens reads one piece at a time, and whose scores therefore
# hang off a piece row rather than off the record.  The complement is
# ``edition``, which has no per-article rows to hang anything off: it reads the
# assembled issue and scores it once.  That record-level path is the one the
# retired ``learning`` kind used, inherited unchanged.
PER_ARTICLE_KINDS = PIECE_JUDGE_KINDS

# The ``article`` value a whole-issue row carries.  The rollup is one flat table
# with one shape of row, so an issue-level score needs *some* article key; using
# a reserved literal keeps the table sortable and joinable without a null.
WHOLE_ISSUE_ARTICLE_ID = "edition"

# Enough for a git invocation on a repository of this size, short enough that a
# hung or prompting git degrades the report instead of hanging the command.
_GIT_TIMEOUT_SECONDS = 15

_BANNER_LINES = (
    "# Generated by `mag scores` from the committed review records under",
    "# editions/*/reviews/. Do not edit by hand.",
)

# The row key order, fixed so the generated file diffs cleanly when a single
# score moves.  ``ScoreRow.to_dict`` is the only thing that should build a row
# mapping, precisely so this order lives in one place.
_ROW_KEYS = (
    "edition",
    "kind",
    "article",
    "round",
    "dimension",
    "score",
    "result",
    "reviewed_at",
    "rounds_to_approval",
)


@dataclass(frozen=True)
class ScoreRow:
    """One score, fully qualified: who scored what, when, and on which round.

    Flat and denormalized on purpose.  ``result`` and ``rounds_to_approval``
    are properties of the ``(edition, kind, round)`` verdict rather than of the
    dimension, and copying them onto every row costs a few bytes and saves
    every reader of the file a join.
    """

    edition: str
    kind: str
    article: str
    round: int
    dimension: str
    score: int
    result: str | None
    reviewed_at: str | None
    rounds_to_approval: int | None

    def to_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in _ROW_KEYS}


def scores_path(editions_dir: Path) -> Path:
    return editions_dir / "scores.yaml"


def collect_score_rows(
    editions_dir: Path, *, root: Path | None = None
) -> tuple[ScoreRow, ...]:
    """Every score in every committed review record, one row per dimension.

    Scans ``<editions_dir>/*/reviews/<kind>.yaml`` for each kind in
    :data:`SCORED_REVIEW_KINDS`, in sorted edition order, and walks each
    record's history so a judge's earlier rounds survive the re-record that
    overwrote them.  ``root`` is the git working tree that history walk runs in
    and defaults to ``editions_dir.parent``.

    This function does not raise.  Anything it cannot make sense of -- a file
    that will not parse, a record that is not a mapping, a ``scores`` that is
    not a mapping, a dimension whose value is not an integer in
    :data:`~magazine.review_findings.SCORE_RANGE` -- contributes no rows and is
    passed over without comment.  The rollup is a reporting surface derived
    from records that already have a validator each; its job when it meets a
    broken one is to keep reporting every other lens and every other edition.

    Rows come back sorted by ``(edition, kind, article, round, dimension)``, so
    the generated file is stable under regeneration.
    """

    editions_root = Path(editions_dir)
    working_tree = Path(root) if root is not None else editions_root.parent
    rows: list[ScoreRow] = []
    if not editions_root.is_dir():
        return ()
    for edition_dir in sorted(path for path in editions_root.iterdir() if path.is_dir()):
        edition_id = edition_dir.name
        for kind in SCORED_REVIEW_KINDS:
            record_path = edition_dir / "reviews" / f"{kind}.yaml"
            if not record_path.is_file():
                continue
            records = [_parse_record(text) for text in _record_rounds(record_path, working_tree)]
            rounds_to_approval = _rounds_to_approval(records)
            for number, record in enumerate(records, start=1):
                if record is None:
                    continue
                rows.extend(
                    _rows_for_record(
                        record,
                        edition_id=edition_id,
                        kind=kind,
                        round_number=number,
                        rounds_to_approval=rounds_to_approval,
                    )
                )
    rows.sort(key=lambda row: (row.edition, row.kind, row.article, row.round, row.dimension))
    return tuple(rows)


def render_scores(rows: Iterable[ScoreRow]) -> str:
    """The ``editions/scores.yaml`` document text, banner included.

    The banner is literal comment lines prepended to the dumped YAML, exactly
    as ``catalog.render_sources`` builds its "Do not edit by hand" header: a
    YAML serializer cannot emit a comment, and the alternative -- a
    ``generated: true`` key -- says the same thing to a parser and nothing at
    all to the person who just opened the file in an editor.
    """

    document: dict[str, Any] = {
        "schema_version": SCORES_SCHEMA_VERSION,
        "generated_from": "editions/*/reviews/{" + ",".join(SCORED_REVIEW_KINDS) + "}.yaml",
        "rows": [row.to_dict() for row in rows],
    }
    return "\n".join(_BANNER_LINES) + "\n" + dump_yaml(document)


def write_scores(editions_dir: Path, *, root: Path | None = None) -> Path:
    path = scores_path(Path(editions_dir))
    _write_atomic(path, render_scores(collect_score_rows(editions_dir, root=root)))
    return path


def scores_are_current(editions_dir: Path, *, root: Path | None = None) -> bool:
    """Whether the file on disk is what regenerating it right now would produce.

    Backs ``mag scores --check``.  A missing file is not current: the check
    exists to catch a rollup that was never regenerated as much as one that
    drifted.
    """

    path = scores_path(Path(editions_dir))
    if not path.is_file():
        return False
    try:
        existing = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return existing == render_scores(collect_score_rows(editions_dir, root=root))


def _rows_for_record(
    record: Mapping[str, Any],
    *,
    edition_id: str,
    kind: str,
    round_number: int,
    rounds_to_approval: int | None,
) -> list[ScoreRow]:
    """Turn one round's record into its rows, dropping whatever does not parse.

    Two record shapes, and the split is the bench's own.  A per-piece lens
    stores its scores on ``articles.<id>.scores``, one row per piece it read; the
    whole-issue lens stores them at the top of the record, because it read the
    issue and there is no piece to attribute them to.  Both land in the same flat
    table, the second under :data:`WHOLE_ISSUE_ARTICLE_ID`.
    """

    result = _text_or_none(record.get("result"))
    record_reviewed_at = _text_or_none(record.get("reviewed_at"))
    rows: list[ScoreRow] = []
    if kind in PER_ARTICLE_KINDS:
        articles = record.get("articles")
        if not isinstance(articles, Mapping):
            return rows
        for article_id, article_row in articles.items():
            article = str(article_id).strip()
            if not article or not isinstance(article_row, Mapping):
                continue
            # A per-article row stamps when *that article* was last reviewed;
            # rows written before those stamps existed fall back to the
            # record's, matching how evidence_review reports the same thing.
            reviewed_at = (
                _text_or_none(article_row.get("reviewed_at")) or record_reviewed_at
            )
            rows.extend(
                _score_rows(
                    article_row.get("scores"),
                    edition=edition_id,
                    kind=kind,
                    article=article,
                    round_number=round_number,
                    result=result,
                    reviewed_at=reviewed_at,
                    rounds_to_approval=rounds_to_approval,
                )
            )
        return rows
    return _score_rows(
        record.get("scores"),
        edition=edition_id,
        kind=kind,
        article=WHOLE_ISSUE_ARTICLE_ID,
        round_number=round_number,
        result=result,
        reviewed_at=record_reviewed_at,
        rounds_to_approval=rounds_to_approval,
    )


def _score_rows(
    scores: Any,
    *,
    edition: str,
    kind: str,
    article: str,
    round_number: int,
    result: str | None,
    reviewed_at: str | None,
    rounds_to_approval: int | None,
) -> list[ScoreRow]:
    if not isinstance(scores, Mapping):
        return []
    low, high = SCORE_RANGE
    rows: list[ScoreRow] = []
    for name, value in scores.items():
        dimension = str(name).strip()
        if not dimension:
            continue
        # ``bool`` is an ``int`` in Python, so ``True`` would otherwise land in
        # the table as a perfectly plausible 1.
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        if not low <= value <= high:
            continue
        rows.append(
            ScoreRow(
                edition=edition,
                kind=kind,
                article=article,
                round=round_number,
                dimension=dimension,
                score=int(value),
                result=result,
                reviewed_at=reviewed_at,
                rounds_to_approval=rounds_to_approval,
            )
        )
    return rows


def _rounds_to_approval(records: list[Mapping[str, Any] | None]) -> int | None:
    """The 1-based round on which this ``(edition, kind)`` pair first approved.

    The verdict is record-level for every kind, including the per-article ones:
    a partial re-record of two articles still produces exactly one issue-level
    ``result``, because the judge is being asked whether the *edition* may
    proceed on this axis, not whether each article may.  So the number belongs
    to the pair, and every row of the pair carries the same one.

    ``None`` means "not derivable from the visible history" -- the kind has not
    approved yet, or its earlier rounds are not in git -- and emphatically not
    "approved in zero rounds".
    """

    for number, record in enumerate(records, start=1):
        if record is not None and _text_or_none(record.get("result")) == "approved":
            return number
    return None


def _parse_record(text: str) -> Mapping[str, Any] | None:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, Mapping) else None


def _record_rounds(path: Path, root: Path) -> list[str]:
    """One string per round of review this record has been through, oldest first.

    The record file is overwritten on every re-record, so the only place the
    earlier rounds still exist is the commit history.  ``git log --reverse``
    over the file's path gives the commits that touched it, and ``git show
    <sha>:<relpath>`` gives what it said at each one -- decoded as UTF-8, which
    is what these YAML records are and what anything else in them being
    replacement characters would honestly represent.

    Two adjustments make the sequence mean "rounds" rather than "commits":

    * consecutive identical contents collapse, because a commit that moved the
      file, or that touched a sibling record in the same tree rewrite, is not a
      judge having another look;
    * the working-tree file is appended as a final round when it differs from
      the last committed one, because an uncommitted re-record is exactly the
      round the operator is staring at while they run ``mag scores``.

    **Every git failure degrades to a single round built from the working-tree
    file.**  Git missing from PATH, a directory that is not a repository, an
    untracked record, a non-zero exit, a timeout: all of them land on the same
    path, and that path is the normal case -- in the test suite, in a fresh
    checkout, in a tarball. It is a first-class answer, not an error.
    """

    working_tree_text = _read_text(path)
    try:
        relative = path.resolve().relative_to(Path(root).resolve()).as_posix()
    except (OSError, ValueError):
        return [working_tree_text] if working_tree_text is not None else []

    contents: list[str] = []
    log = _git(root, "log", "--format=%H", "--reverse", "--", relative)
    if log is not None:
        for commit in log.split():
            revision = _git(root, "show", f"{commit}:{relative}")
            # A commit that deleted or had not yet added the file makes ``git
            # show`` fail; that revision simply is not a round.
            if revision is None:
                continue
            if not contents or contents[-1] != revision:
                contents.append(revision)
    if working_tree_text is not None and (not contents or contents[-1] != working_tree_text):
        contents.append(working_tree_text)
    return contents


def _git(root: Path, *arguments: str) -> str | None:
    """Run one read-only git command, returning ``None`` for any kind of failure.

    No shell, a timeout, and ``errors="replace"`` so a record with a stray byte
    comes back as text rather than as a ``UnicodeDecodeError`` out of a
    reporting command.
    """

    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _text_or_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _write_atomic(path: Path, text: str) -> None:
    """Replace ``path`` with ``text`` in one step, durably.

    This is ``render_review.write_render_review``'s technique rather than a
    call to it: that writer takes a mapping and serializes the YAML itself,
    and this artifact leads with a generated-file banner that no YAML
    serializer can produce.  Sharing it would mean growing it a "and also
    prepend these comment lines" parameter, which is a worse seam than
    repeating eight lines of mkstemp-and-replace.  What must not happen is a
    second *general-purpose* YAML writer, and this is not one -- it takes text.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    content = text.encode("utf-8")
    descriptor, temporary_name = mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
