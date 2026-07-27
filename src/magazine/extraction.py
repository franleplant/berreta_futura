"""Source-side extraction artifacts and their fidelity-ledger bindings.

``library/sources/<source-id>/extracted.md`` is the durable, human-readable
faithful extraction of a source's substantive text.  Its YAML frontmatter names
the source, the committed raw bundle (the content-addressed directory under
``raw/``) the text was transcribed from, and the extraction method.  The body
is the extraction itself.

The body convention is byte-exact: the file is read as raw bytes, decoded as
strict UTF-8, must open with a ``---`` line, and the body is every byte after
the first ``\\n---\\n`` that closes the frontmatter.  A BOM or any carriage
return anywhere in the file is rejected outright -- silent newline
normalization would make the pinned hashes irreproducible with ``shasum``.  A
fidelity ledger's ``source_body_sha256`` pins the SHA-256 of the UTF-8
encoding of exactly those body bytes, so the ledger, the extraction, and the
raw bundle form one verifiable chain from manuscript back to captured
evidence.

Ledgers over a single source declare ``source_body_sha256`` as one hex digest
(the shape editions 001 and 002 already use).  A multi-source ledger declares a
mapping from source id to hex digest.  Released editions predate committed
extractions, so their pins are recorded but unverifiable and are skipped; the
open (unreleased) edition is held to the full requirement.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .errors import ValidationError
from .io import load_structured

EXTRACTION_FILENAME = "extracted.md"

_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Extraction:
    """One parsed ``extracted.md``: provenance frontmatter plus exact body."""

    path: Path
    source_id: str
    raw_bundle: str
    method: str
    body: str
    file_sha256: str

    @property
    def body_sha256(self) -> str:
        return hashlib.sha256(self.body.encode("utf-8")).hexdigest()


def extraction_path(sources_dir: Path, source_id: str) -> Path:
    return sources_dir / source_id / EXTRACTION_FILENAME


def load_extraction(sources_dir: Path, source_id: str) -> Extraction | None:
    """Load and validate a source's extraction, or ``None`` when absent.

    Absence is an ordinary state -- released editions have no extractions --
    but a present, malformed extraction is always an error naming the file.
    """

    path = extraction_path(sources_dir, source_id)
    if not path.is_file():
        return None
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValidationError(
            f"{path}: extraction must not begin with a UTF-8 BOM; "
            "hashes pin the exact file bytes"
        )
    if b"\r" in raw:
        raise ValidationError(
            f"{path}: extraction contains a carriage return (CR/CRLF line endings); "
            "extractions are byte-exact and must use LF newlines only"
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"{path}: extraction is not valid UTF-8: {exc}") from exc
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValidationError(
            f"{path}: extraction requires YAML frontmatter opened and closed by --- lines"
        )
    header, _, body = text[4:].partition("\n---\n")
    try:
        metadata = yaml.safe_load(header)
    except yaml.YAMLError as exc:
        raise ValidationError(f"{path}: cannot parse extraction frontmatter: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ValidationError(f"{path}: extraction frontmatter must be a mapping")
    errors: list[str] = []
    if metadata.get("schema_version") != 1:
        errors.append(f"{path}: extraction schema_version must be 1")
    declared_source = str(metadata.get("source_id") or "")
    if declared_source != source_id:
        errors.append(
            f"{path}: extraction source_id {declared_source!r} does not match source {source_id!r}"
        )
    raw_bundle = str(metadata.get("raw_bundle") or "")
    if not raw_bundle:
        errors.append(f"{path}: extraction requires the raw_bundle it was extracted from")
    elif not (sources_dir / source_id / "raw" / raw_bundle / "manifest.json").is_file():
        errors.append(
            f"{path}: raw_bundle {raw_bundle} is not a committed raw bundle of {source_id}"
        )
    method = str(metadata.get("extraction_method") or "").strip()
    if not method:
        errors.append(f"{path}: extraction requires a non-empty extraction_method")
    if not body.strip():
        errors.append(f"{path}: extraction body is empty")
    if errors:
        raise ValidationError(errors)
    return Extraction(
        path, source_id, raw_bundle, method, body, hashlib.sha256(raw).hexdigest()
    )


def ledger_source_ids(ledger_path: Path, data: dict[str, Any]) -> tuple[str, ...]:
    """The sources a fidelity ledger covers, in the ledger's declared order.

    A ledger with neither key is an ordinary released-edition state and yields
    an empty tuple (the open edition catches it against the article's own
    declaration).  A *present* but mistyped or empty declaration is always an
    error: a ledger must never verify vacuously because its coverage was
    spelled wrongly.
    """

    if "source_ids" in data:
        declared = data["source_ids"]
        if (
            not isinstance(declared, list)
            or not declared
            or any(not str(item or "").strip() for item in declared)
        ):
            raise ValidationError(
                f"{ledger_path}: source_ids must be a non-empty list of source ids, "
                f"got {declared!r}"
            )
        return tuple(str(item) for item in declared)
    if "source_id" in data:
        single = data["source_id"]
        if not isinstance(single, str) or not single.strip():
            raise ValidationError(
                f"{ledger_path}: source_id must be a non-empty source id, got {single!r}"
            )
        return (single,)
    return ()


def declared_source_hashes(
    ledger_path: Path, data: dict[str, Any], source_ids: tuple[str, ...]
) -> dict[str, str | None]:
    """Normalize a ledger's ``source_body_sha256`` to one pin per source.

    A bare hex digest is the single-source shape editions 001 and 002 use; a
    multi-source ledger must key each pin by source id so no source can hide
    behind another's hash.
    """

    declared = data.get("source_body_sha256")
    if declared is None:
        return {source_id: None for source_id in source_ids}
    if isinstance(declared, str):
        if len(source_ids) != 1:
            raise ValidationError(
                f"{ledger_path}: source_body_sha256 must be a mapping keyed by source id "
                f"when the ledger covers {len(source_ids)} sources"
            )
        _require_hex(ledger_path, source_ids[0], declared)
        return {source_ids[0]: declared}
    if isinstance(declared, dict):
        unknown = sorted(set(str(key) for key in declared) - set(source_ids))
        if unknown:
            raise ValidationError(
                f"{ledger_path}: source_body_sha256 names sources the ledger does not cover: "
                + ", ".join(unknown)
            )
        for source_id, value in declared.items():
            _require_hex(ledger_path, str(source_id), str(value or ""))
        return {
            source_id: str(declared[source_id]) if source_id in declared else None
            for source_id in source_ids
        }
    raise ValidationError(
        f"{ledger_path}: source_body_sha256 must be a hex digest or a mapping keyed by source id"
    )


def _require_hex(ledger_path: Path, source_id: str, value: str) -> None:
    if not _HEX_SHA256.match(value):
        raise ValidationError(
            f"{ledger_path}: source_body_sha256 for {source_id} must be a 64-character "
            f"lowercase hex SHA-256, got {value!r}"
        )


def verify_ledger_source_extractions(
    ledger_path: Path,
    sources_dir: Path,
    *,
    require_extractions: bool,
    article_source_ids: tuple[str, ...] | None = None,
) -> None:
    """Verify a ledger's source-side pins against committed extractions.

    Whenever a source has both an extraction and a declared pin, the pin must
    match the extraction body -- that rule is unconditional.  When
    ``require_extractions`` is true (the article belongs to the open,
    unreleased edition) every covered source must additionally have an
    extraction and a matching pin, and, when ``article_source_ids`` is given,
    the ledger's declared sources must equal the article's ``source_ids`` in
    ``edition.yaml`` exactly -- neither side may cover a source the other does
    not, or a manuscript could cite evidence its ledger never audits (or vice
    versa).  Released editions predate committed extractions; their recorded
    pins have nothing to verify against and are skipped, keeping their
    validation exactly as it was (edition 001's ``narayanan-what-will-be-left``
    ledger already diverges from its article, so the equality rule is scoped
    to the open edition by design).
    """

    data = load_structured(ledger_path)
    source_ids = ledger_source_ids(ledger_path, data)
    if require_extractions:
        if article_source_ids is not None:
            missing = [item for item in article_source_ids if item not in source_ids]
            extra = [item for item in source_ids if item not in article_source_ids]
            if missing or extra:
                parts = []
                if missing:
                    parts.append(
                        "declared by the article but absent from the ledger: "
                        + ", ".join(missing)
                    )
                if extra:
                    parts.append(
                        "declared by the ledger but absent from the article: "
                        + ", ".join(extra)
                    )
                raise ValidationError(
                    f"{ledger_path}: the open edition requires the ledger's source_ids "
                    "to equal the article's source_ids in edition.yaml; "
                    + "; ".join(parts)
                )
        if not source_ids:
            raise ValidationError(
                f"{ledger_path}: the open edition requires the ledger to declare the "
                "source_ids it covers"
            )
    declared = declared_source_hashes(ledger_path, data, source_ids)
    errors: list[str] = []
    for source_id in source_ids:
        try:
            extraction = load_extraction(sources_dir, source_id)
        except ValidationError as exc:
            errors.extend(exc.errors)
            continue
        pinned = declared.get(source_id)
        if extraction is None:
            if require_extractions:
                errors.append(
                    f"{ledger_path}: source {source_id} has no committed extraction; the open "
                    f"edition requires library/sources/{source_id}/{EXTRACTION_FILENAME} "
                    "so the ledger's source side is verifiable"
                )
            continue
        if pinned is None:
            if require_extractions:
                errors.append(
                    f"{ledger_path}: declares no source_body_sha256 for {source_id}; pin the "
                    f"extraction body hash {extraction.body_sha256}"
                )
            continue
        if pinned != extraction.body_sha256:
            errors.append(
                f"{ledger_path}: source_body_sha256 for {source_id} is {pinned}, but the "
                f"extraction body of {extraction.path} hashes to {extraction.body_sha256}; "
                "the ledger no longer matches the committed extraction"
            )
    if errors:
        raise ValidationError(errors)
