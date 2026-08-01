"""Source-side extraction artifacts and the article rows that pin them.

``library/sources/<source-id>/extracted.md`` is the durable, human-readable
faithful extraction of a source's substantive text.  Its YAML frontmatter names
the source, the committed raw bundle (the content-addressed directory under
``raw/``) the text was transcribed from, and the extraction method.  The body
is the extraction itself.

The body convention is byte-exact: the file is read as raw bytes, decoded as
strict UTF-8, must open with a ``---`` line, and the body is every byte after
the first ``\\n---\\n`` that closes the frontmatter.  A BOM or any carriage
return anywhere in the file is rejected outright -- silent newline
normalization would make the pinned hashes irreproducible with ``shasum``.  An
article row's ``source_body_sha256`` in ``edition.yaml`` pins the SHA-256 of
the UTF-8 encoding of exactly those body bytes, so the article, the
extraction, and the raw bundle form one verifiable chain from manuscript back
to captured evidence.

The pin lives beside the ``source_ids`` it covers, in the same article row, so
the two declarations cannot drift apart: an article that adds a source without
pinning it is a single row that fails to validate, not two files that quietly
disagree.  An article over a single source declares ``source_body_sha256`` as
one hex digest; an article over several declares a mapping from source id to
hex digest, so no source can hide behind another's hash.  Released editions
predate committed extractions, so their pins are recorded but unverifiable and
are skipped; the open (collecting) edition is held to the full requirement.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .errors import ValidationError

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


@dataclass(frozen=True)
class SourcePin:
    """One article source and the extraction body digest the article pins it to.

    ``body_sha256`` is ``None`` when the article declares the source but no
    digest for it.  That is the released-edition shape -- those editions
    predate committed extractions and have nothing to pin -- and an ordinary
    intermediate state while an author is adding a source.  The open edition
    refuses it; every other caller treats it as "nothing to compare".
    """

    source_id: str
    body_sha256: str | None


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


def normalize_source_pins(
    label: str, source_ids: tuple[str, ...], declared: object
) -> tuple[SourcePin, ...]:
    """Read one article row's ``source_body_sha256`` as one pin per source.

    A bare hex digest is the single-source shape; an article over several
    sources must key each pin by source id, because a lone digest could only
    ever prove one of them.  A missing key yields an unpinned row -- legal for
    a released edition, refused for the open one by
    :func:`verify_source_extractions`.  A *present* but mistyped declaration is
    always an error: an article must never verify vacuously because its pin was
    spelled wrongly.
    """

    if declared is None:
        return tuple(SourcePin(source_id, None) for source_id in source_ids)
    if isinstance(declared, str):
        if len(source_ids) != 1:
            raise ValidationError(
                f"{label}: source_body_sha256 must be a mapping keyed by source id "
                f"when the article covers {len(source_ids)} sources"
            )
        _require_hex(label, source_ids[0], declared)
        return (SourcePin(source_ids[0], declared),)
    if isinstance(declared, dict):
        unknown = sorted(set(str(key) for key in declared) - set(source_ids))
        if unknown:
            raise ValidationError(
                f"{label}: source_body_sha256 names sources the article does not "
                "declare in source_ids: " + ", ".join(unknown)
            )
        for source_id, value in declared.items():
            _require_hex(label, str(source_id), str(value or ""))
        return tuple(
            SourcePin(source_id, str(declared[source_id]) if source_id in declared else None)
            for source_id in source_ids
        )
    raise ValidationError(
        f"{label}: source_body_sha256 must be a hex digest or a mapping keyed by source id"
    )


def _require_hex(label: str, source_id: str, value: str) -> None:
    if not _HEX_SHA256.match(value):
        raise ValidationError(
            f"{label}: source_body_sha256 for {source_id} must be a 64-character "
            f"lowercase hex SHA-256, got {value!r}"
        )


def verify_source_extractions(
    label: str,
    pins: tuple[SourcePin, ...],
    sources_dir: Path,
    *,
    require_extractions: bool,
) -> tuple[Extraction, ...]:
    """Verify an article's source pins against the committed extractions.

    Whenever a source has both an extraction and a declared pin, the pin must
    match the extraction body -- that rule is unconditional, and it is the one
    that detects republishing a source whose text moved underneath the
    manuscript.  When ``require_extractions`` is true (the article belongs to
    the open, collecting edition) every declared source must additionally have
    an extraction *and* a matching pin.  Released editions predate committed
    extractions; their recorded pins have nothing to verify against and are
    skipped, keeping their validation exactly as it was.

    Returns every extraction that was found, in the article's declared source
    order, so a caller that needs the source text (the code-fence check) does
    not load it a second time.  A found-but-unpinned extraction is included:
    the open edition has already refused that state by the time this returns,
    and for a released edition the text is still the committed source text,
    which is worth handing to a caller that only wants to read it.
    """

    errors: list[str] = []
    found: list[Extraction] = []
    if require_extractions and not pins:
        raise ValidationError(
            f"{label}: the open edition requires the article to declare the "
            "source_ids it is written from"
        )
    for pin in pins:
        try:
            extraction = load_extraction(sources_dir, pin.source_id)
        except ValidationError as exc:
            errors.extend(exc.errors)
            continue
        if extraction is None:
            if require_extractions:
                errors.append(
                    f"{label}: source {pin.source_id} has no committed extraction; the "
                    f"open edition requires library/sources/{pin.source_id}/"
                    f"{EXTRACTION_FILENAME} so the article's source side is verifiable"
                )
            continue
        found.append(extraction)
        if pin.body_sha256 is None:
            if require_extractions:
                errors.append(
                    f"{label}: declares no source_body_sha256 for {pin.source_id}; pin "
                    f"the extraction body hash {extraction.body_sha256}"
                )
            continue
        if pin.body_sha256 != extraction.body_sha256:
            errors.append(
                f"{label}: source_body_sha256 for {pin.source_id} is {pin.body_sha256}, "
                f"but the extraction body of {extraction.path} hashes to "
                f"{extraction.body_sha256}; the article no longer matches the "
                "committed extraction"
            )
    if errors:
        raise ValidationError(errors)
    return tuple(found)
