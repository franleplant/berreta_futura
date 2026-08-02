"""What the machine did, per piece, made durable and greppable.

The review bench records a *verdict*: who approved which bytes.  Nothing in the
repository recorded the other half -- which prompt revision, which backend,
which argv, and which round produced the bytes in the first place.  The
edition-4 audit was much harder than it should have been for exactly that
reason: given a shipped manuscript there was no way back to the synthesis
prompt that wrote it, because the prompts had been revised since and nothing
had pinned which revision was in force.

So every produce run leaves one record per piece:

``editions/<edition-id>/production/articles/<piece-id>.yaml``
    one file per drafted piece, including ``editorial``;
``editions/<edition-id>/production/issue/{learning,edition}.yaml``
    the two whole-issue judgments, which belong to no single piece.

The shape follows the review bench's idioms deliberately -- ``schema_version``,
``edition_id``, per-round SHA-256 bindings, the same atomic writer -- so a
reader who knows one knows the other.  It is *not* a review record: it never
gates a release and nothing in the release path reads it.  It answers "how did
this text get here", and the grep that answers it is a plain one::

    grep -rn prompt_sha256 editions/*/production/

Two things in here are load-bearing rather than decorative.

**Drafting notes are stored.**  A round's ``notes`` field holds the writer's
concept graph or claim ladder, taken from below the scratch marker.  It is
stored because the next round needs it -- a finding names where a contradiction
surfaces, not where it originates -- and because a resumed run must be able to
hand round three the notes that round two wrote in a process that has since
exited.  It is stored *here* and never in the manuscript.

**Inputs are fingerprinted.**  ``inputs_sha256`` covers the prompt file's
digest, the piece's manifest row, and every source extraction body.  A piece
whose fingerprint is unchanged, whose manuscript on disk still hashes to the
recorded one, and whose judges approved is not re-drafted: model calls are slow
and cost money, and a resumed run that redrafts settled work is a resumed run
nobody uses.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .io import load_structured
from .render_review import write_render_review

PRODUCTION_RECORD_SCHEMA_VERSION = 1

PRODUCTION_DIRNAME = "production"

AGENT_DIRNAME = "agent"
"""Where the cooperative backend keeps its work queue, beside the records.

Named here rather than in :mod:`magazine.produce_agent` so that a reader of the
production directory finds both halves in one place, and so that the workflow
report can look for an outstanding ready set without importing the pipeline.
"""

# Terminal and non-terminal states one piece's record may sit in.  ``drafting``
# is what a crashed or interrupted run leaves behind, and it is deliberately
# distinguishable from ``escalated``: one means "nobody decided", the other
# means "the pipeline decided it cannot".
PIECE_STATUSES = ("drafting", "passed", "escalated")


def production_dir(editions_dir: Path, edition_id: str) -> Path:
    return editions_dir / edition_id / PRODUCTION_DIRNAME


def piece_record_path(editions_dir: Path, edition_id: str, piece_id: str) -> Path:
    return production_dir(editions_dir, edition_id) / "articles" / f"{piece_id}.yaml"


def issue_record_path(editions_dir: Path, edition_id: str, kind: str) -> Path:
    return production_dir(editions_dir, edition_id) / "issue" / f"{kind}.yaml"


@dataclass(frozen=True)
class ModelCall:
    """One completed model invocation, as an execution record names it.

    Everything here except ``role`` comes straight off the runner's
    :class:`~magazine.runner.GenerationResult` and the prompt file it was
    composed from.  ``argv`` is stored whole: the model name, the sandbox mode
    and the capture-file path are all in it, and a summary of them would be the
    thing that is wrong when the audit needs it.
    """

    role: str
    prompt_path: str
    prompt_sha256: str
    backend: str
    model: str | None
    argv: tuple[str, ...]
    duration_seconds: float
    output_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "prompt_path": self.prompt_path,
            "prompt_sha256": self.prompt_sha256,
            "backend": self.backend,
            "model": self.model,
            "argv": list(self.argv),
            "duration_seconds": round(self.duration_seconds, 3),
            "output_sha256": self.output_sha256,
        }


@dataclass
class RoundRecord:
    """One writer pass and everything that judged it."""

    round_number: int
    writer: ModelCall
    manuscript_sha256: str
    notes: str = ""
    gate_failures: tuple[str, ...] = ()
    anchors_reconciled: tuple[str, ...] = ()
    judges: dict[str, dict[str, Any]] = field(default_factory=dict)
    result: str = "changes_required"

    def to_dict(self) -> dict[str, Any]:
        return {
            "round": self.round_number,
            "result": self.result,
            "manuscript_sha256": self.manuscript_sha256,
            "writer": self.writer.to_dict(),
            "gate_failures": list(self.gate_failures),
            "anchors_reconciled": list(self.anchors_reconciled),
            "judges": self.judges,
            # Last, and always present even when empty: a reader scrolling a
            # record wants the provenance header before the prose, and a
            # reviser reading it programmatically wants the key to exist.
            "notes": self.notes,
        }


@dataclass
class PieceRecord:
    """The whole production history of one piece, across every round."""

    edition_id: str
    piece_id: str
    content_mode: str
    inputs_sha256: str
    status: str = "drafting"
    manuscript_sha256: str | None = None
    rounds: list[RoundRecord] = field(default_factory=list)
    escalation: dict[str, Any] | None = None
    produced_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "schema_version": PRODUCTION_RECORD_SCHEMA_VERSION,
            # The id as it was at production time.  ``mag finish`` renames an
            # edition and rewrites the review bench's identity files; it does
            # not rewrite history, and a production record is history.
            "edition_id": self.edition_id,
            "piece_id": self.piece_id,
            "content_mode": self.content_mode,
            "status": self.status,
            "produced_at": self.produced_at,
            "inputs_sha256": self.inputs_sha256,
            "manuscript_sha256": self.manuscript_sha256,
            "rounds": [entry.to_dict() for entry in self.rounds],
        }
        if self.escalation is not None:
            record["escalation"] = self.escalation
        return record

    @property
    def rounds_run(self) -> int:
        return len(self.rounds)


def write_piece_record(
    editions_dir: Path, record: PieceRecord
) -> Path:
    return write_render_review(
        piece_record_path(editions_dir, record.edition_id, record.piece_id),
        record.to_dict(),
    )


def load_piece_record(
    editions_dir: Path, edition_id: str, piece_id: str
) -> dict[str, Any] | None:
    """Read a piece's record, or ``None`` when it has never been produced.

    A record that cannot be parsed is reported as absent rather than raised on.
    This file is provenance, not a gate: a corrupted one must cost a re-draft,
    never a refusal to run at all.
    """

    path = piece_record_path(editions_dir, edition_id, piece_id)
    if not path.is_file():
        return None
    try:
        data = load_structured(path)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def write_issue_record(
    editions_dir: Path, edition_id: str, kind: str, record: Mapping[str, Any]
) -> Path:
    payload = {
        "schema_version": PRODUCTION_RECORD_SCHEMA_VERSION,
        "edition_id": edition_id,
        "kind": kind,
        **dict(record),
    }
    return write_render_review(
        issue_record_path(editions_dir, edition_id, kind), payload
    )


# ---------------------------------------------------------------------------
# Findings filed from outside the loop.


FILED_FINDINGS_FILENAME = "findings.yaml"

FILED_STATUSES = ("open", "addressed")


def filed_findings_path(editions_dir: Path, edition_id: str) -> Path:
    return production_dir(editions_dir, edition_id) / FILED_FINDINGS_FILENAME


def load_filed_findings(editions_dir: Path, edition_id: str) -> list[dict[str, Any]]:
    """Every finding filed against this edition, in the order they were filed.

    Unreadable or malformed files yield nothing, for the same reason a corrupt
    piece record does: this is a queue of instructions, and a queue that cannot
    be parsed must cost a lost instruction rather than a refusal to produce.
    """

    path = filed_findings_path(editions_dir, edition_id)
    if not path.is_file():
        return []
    try:
        data = load_structured(path)
    except Exception:
        return []
    if not isinstance(data, Mapping):
        return []
    rows = data.get("findings")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def open_filed_findings(
    editions_dir: Path, edition_id: str, piece_id: str
) -> list[dict[str, Any]]:
    """The findings this piece still owes a drafting round.

    Stripped of their bookkeeping keys, so what comes back is a finding in the
    shape every judge already emits and every brief already renders.  ``judge``
    is set to who filed it, because a reviser reading "from the edition review"
    treats it differently from "from the craft lens", and should.
    """

    open_rows: list[dict[str, Any]] = []
    for row in load_filed_findings(editions_dir, edition_id):
        if str(row.get("piece") or "") != piece_id:
            continue
        if str(row.get("status") or "open") != "open":
            continue
        finding = {
            key: value
            for key, value in row.items()
            if key not in {"piece", "status", "filed_at", "filed_by", "addressed_in_round"}
        }
        finding["judge"] = str(row.get("filed_by") or "filed finding")
        open_rows.append(finding)
    return open_rows


def pieces_with_open_findings(editions_dir: Path, edition_id: str) -> dict[str, int]:
    """How many open filed findings each piece is carrying."""

    counts: dict[str, int] = {}
    for row in load_filed_findings(editions_dir, edition_id):
        if str(row.get("status") or "open") != "open":
            continue
        piece = str(row.get("piece") or "")
        if piece:
            counts[piece] = counts.get(piece, 0) + 1
    return counts


def write_filed_findings(
    editions_dir: Path, edition_id: str, rows: Sequence[Mapping[str, Any]]
) -> Path:
    return write_render_review(
        filed_findings_path(editions_dir, edition_id),
        {
            "schema_version": PRODUCTION_RECORD_SCHEMA_VERSION,
            "edition_id": edition_id,
            "findings": [dict(row) for row in rows],
        },
    )


def file_finding(
    editions_dir: Path,
    edition_id: str,
    piece_id: str,
    finding: Mapping[str, Any],
    *,
    filed_by: str,
    filed_at: str,
) -> Path:
    """Append one finding a human wants the piece's next brief to carry.

    The loop's findings all come from inside it: a judge reads a draft and the
    next round is handed what it said.  Real editions also produce findings
    from outside -- an edition-level review, a reader, the owner noticing a
    wrong claim -- and until now there was nowhere to put one.  They were
    pasted into an agent prompt by hand, which is precisely the improvised
    orchestration the pipeline exists to replace, and which leaves no record
    that the instruction was ever given.

    A filed finding is stored in the same shape a judge's is, so the brief
    renders it through the same code and a reviser cannot tell the difference
    in kind.  Two keys are added: ``piece``, because a filed finding is
    addressed rather than discovered, and ``status``, because it has to
    survive until a round has actually seen it.
    """

    rows = load_filed_findings(editions_dir, edition_id)
    rows.append(
        {
            "piece": piece_id,
            "status": "open",
            "filed_by": filed_by,
            "filed_at": filed_at,
            **{key: value for key, value in finding.items()},
        }
    )
    return write_filed_findings(editions_dir, edition_id, rows)


def close_filed_findings(
    editions_dir: Path, edition_id: str, piece_id: str, *, round_number: int
) -> None:
    """Mark this piece's open findings as addressed by a round that passed.

    "Addressed" is the honest word.  It records that the finding was in front
    of the writer for a round whose judges then approved the result; it does
    not claim that a judge verified this particular defect, because no judge
    was told to look for it.  A filer who wants proof re-reads the piece and
    files again -- which now costs one command rather than an improvised prompt.
    """

    rows = load_filed_findings(editions_dir, edition_id)
    changed = False
    for row in rows:
        if str(row.get("piece") or "") != piece_id:
            continue
        if str(row.get("status") or "open") != "open":
            continue
        row["status"] = "addressed"
        row["addressed_in_round"] = round_number
        changed = True
    if changed:
        write_filed_findings(editions_dir, edition_id, rows)


def inputs_fingerprint(
    *,
    content_mode: str,
    prompt_sha256: str,
    manifest_row: Any,
    extraction_body_sha256: Mapping[str, str],
    peer_manuscript_sha256: Mapping[str, str] | None = None,
) -> str:
    """Hash everything a re-draft of this piece would be a function of.

    Canonical JSON with sorted keys, so the digest depends on the values and
    not on how a YAML loader happened to order a mapping.  ``peer_manuscript``
    hashes exist for the editorial, whose inputs are the other pieces: an
    editorial that was approved against a set of articles is stale the moment
    one of them is rewritten, and only this makes that visible.
    """

    payload = {
        "content_mode": content_mode,
        "prompt_sha256": prompt_sha256,
        "manifest_row": manifest_row,
        "extractions": dict(sorted(extraction_body_sha256.items())),
        "peers": dict(sorted((peer_manuscript_sha256 or {}).items())),
    }
    encoded = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def is_settled(
    record: Mapping[str, Any] | None,
    *,
    inputs_sha256: str,
    manuscript_sha256: str | None,
) -> bool:
    """Whether this piece can be skipped: same inputs, same bytes, approved.

    All three have to hold.  Same inputs alone is not enough, because a human
    may have edited the manuscript by hand since; same bytes alone is not
    enough, because the source may have moved underneath it; and neither means
    anything if the last round did not actually pass.
    """

    if not isinstance(record, Mapping):
        return False
    if record.get("status") != "passed":
        return False
    if record.get("inputs_sha256") != inputs_sha256:
        return False
    if manuscript_sha256 is None:
        return False
    return record.get("manuscript_sha256") == manuscript_sha256


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def accumulated_findings(record: Mapping[str, Any] | None) -> list[Any]:
    """Every finding a piece's rounds have collected, oldest first.

    An escalation hands a human the whole history rather than the last round's
    list: three rounds that each failed differently is a different problem than
    one finding that three rounds could not clear, and only the accumulation
    tells them apart.
    """

    if not isinstance(record, Mapping):
        return []
    findings: list[Any] = []
    rounds = record.get("rounds")
    if not isinstance(rounds, Sequence):
        return findings
    for entry in rounds:
        if not isinstance(entry, Mapping):
            continue
        for failure in entry.get("gate_failures") or ():
            findings.append({"severity": "blocking", "category": "gate", "note": failure})
        judges = entry.get("judges")
        if not isinstance(judges, Mapping):
            continue
        for judge, verdict in judges.items():
            if not isinstance(verdict, Mapping):
                continue
            for finding in verdict.get("findings") or ():
                if isinstance(finding, Mapping):
                    findings.append({**finding, "judge": judge})
                else:
                    findings.append({"note": str(finding), "judge": judge})
    return findings
