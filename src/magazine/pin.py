"""Recompute the derivable hash pins an edition's authors keep by hand.

An edition's authored files carry a small economy of SHA-256 pins.  A
translation overlay pins the base edition's copy (``base_copy_sha256``), each
translated file's English source (``source_sha256``), and each localized
figure's base caption and credit (``source_caption_sha256`` /
``source_credit_sha256``).  A fidelity ledger pins the committed extraction
body of every source it covers (``source_body_sha256``).  Every one of those
digests is a pure function of files already in the repository, yet until now
each was computed by hand -- eighteen shasum invocations per Spanish overlay --
so a routine base-copy edit meant an afternoon of ritual.

``refresh_pins`` recomputes every such pin for one edition and rewrites the
stale ones in place.  Two rules keep it honest:

* **The digest is the only thing that changes.**  These files are
  hand-authored; their comments, key order, quoting, and line wrapping are the
  author's.  So the rewrite is a targeted textual substitution -- find the pin
  key with its current digest, replace exactly the digest -- never a YAML
  round-trip, which would launder the whole file through a dumper's taste.

* **It refreshes pins; it never invents them.**  A missing pin key is an
  authoring decision this tool must not make, so it raises instead of
  inserting.  Anything under ``editions/<id>/reviews/`` is a signed record of
  what a reviewer actually saw and is refused outright: review records are
  recorded only via ``mag review record``.

* **Verify everything, then write everything.**  A textual match can be a
  mirage -- a comment can carry a pin's digest while the real pin hides in a
  spelling the pattern cannot see -- so after substitution each file's
  rewritten text is re-parsed with the same loader validation uses, and every
  refreshed pin must read back as its new digest.  Only when every file
  verifies does any file reach disk: a raise, from anywhere, means the
  working tree is exactly as the author left it.

The function deliberately reuses the canonical hashers -- ``extraction.py``'s
body hash, ``manifest.py``'s edition-copy hash, ``media_schema.py``'s caption
and credit hashes -- rather than restating them, so a pin refreshed here is by
construction the pin validation expects.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

from .errors import ValidationError
from .extraction import EXTRACTION_FILENAME, ledger_source_ids, load_extraction
from .io import load_structured
from .manifest import Article, Edition, _edition_copy_sha256, load_edition
from .media_schema import caption_sha256, credit_sha256
from .records import load_records


@dataclass(frozen=True)
class PinChange:
    """One digest rewritten in one authored file.

    ``pin`` is a human-readable locator (``articles[the-id].source_sha256``,
    ``source_body_sha256[source-id]``) rather than a byte offset, because the
    report's audience is the author deciding whether the refresh matched their
    intent, not a machine replaying the edit.
    """

    path: Path
    pin: str
    old: str
    new: str


@dataclass(frozen=True)
class PinReport:
    """What one refresh actually did: every file touched, every pin moved.

    A no-op run -- every pin already correct -- reports zero changes and has
    touched nothing, so running the refresh is always safe to do speculatively.
    """

    edition_id: str
    changes: tuple[PinChange, ...]

    @property
    def files(self) -> tuple[Path, ...]:
        """The rewritten files, in first-touched order, each named once."""
        return tuple(dict.fromkeys(change.path for change in self.changes))


def refresh_pins(root: Path, edition_id: str) -> PinReport:
    """Recompute every derivable pin in the edition's authored files.

    Covers, for the named edition: the ``source_body_sha256`` pins of every
    article's fidelity ledger (recomputed from the committed
    ``library/sources/<id>/extracted.md`` bodies), and, for every non-source
    language overlay under ``translations/``, the ``base_copy_sha256``, the
    editorial's and each article's and section's ``source_sha256``, and each
    figure's caption and credit pins.

    Stale pins are rewritten in place by textual substitution and reported as
    ``PinChange`` rows; correct pins are left byte-for-byte alone.  Raises
    ``ValidationError`` when a pin key it expects is missing (it never inserts
    keys), when a target file lives under ``reviews/``, when a rewritten file
    does not re-parse to its new digests, or when the base edition itself
    cannot be loaded -- a broken base has no truth to pin.  Every raise, from
    any file, happens before anything is written: a failed refresh leaves the
    working tree byte-for-byte as it found it.
    """
    root = root.resolve()
    config = _load_config(root)
    editions_dir = root / config["editions"]
    sources_dir = root / config["sources"]
    edition_dir = editions_dir / edition_id
    if not (edition_dir / "edition.yaml").is_file():
        raise ValidationError(f"Edition manifest not found: {edition_dir / 'edition.yaml'}")
    reviews_dir = edition_dir / "reviews"

    records = {record.id: record for record in load_records(sources_dir)}
    base = load_edition(
        root,
        edition_id,
        set(records),
        publication_name=config["publication_name"],
        source_records=records,
    )

    # Two-phase commit, in miniature: every file's rewritten text is computed
    # and verified first, and only when the whole batch verifies does any file
    # reach disk.  Otherwise a failure in the second file would leave the
    # first one changed while the report explaining the change was discarded.
    files: list[_PinnedFile] = []
    files.extend(_refresh_ledgers(base, sources_dir, reviews_dir))
    files.extend(_refresh_overlays(base, edition_dir, reviews_dir))
    for file in files:
        file.verify()
    changes: list[PinChange] = []
    for file in files:
        changes.extend(file.write())
    return PinReport(edition_id, tuple(changes))


def _load_config(root: Path) -> dict[str, str]:
    """The three facts ``magazine.toml`` contributes, with its own defaults.

    Read directly rather than through the compiler so the pin refresher stays
    importable on its own; the defaults restate the compiler's.
    """
    config_path = root / "magazine.toml"
    data = tomllib.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    paths = data.get("paths", {})
    publication = data.get("publication", {})
    return {
        "publication_name": str(publication.get("name") or "Magazine").strip(),
        "sources": str(paths.get("sources", "library/sources")),
        "editions": str(paths.get("editions", "editions")),
    }


class _PinnedFile:
    """One authored file whose digests are replaced surgically, or not at all.

    The file is held as text; every ``pin`` call substitutes exactly one
    ``key: old-digest`` occurrence (YAML or JSON-in-YAML spelling, quoted or
    not) with the new digest, leaving every other byte alone.  Failure to find
    the pin -- or finding it twice -- is an error, never a guess: a rewrite
    that might land on the wrong line is worse than no rewrite.
    """

    def __init__(self, path: Path, reviews_dir: Path):
        if path.resolve().is_relative_to(reviews_dir.resolve()):
            raise ValidationError(
                f"Refusing to rewrite {path}: review records under {reviews_dir} are "
                "recorded only via `mag review record`, never edited in place"
            )
        self.path = path
        self.text = path.read_text(encoding="utf-8")
        self.changes: list[PinChange] = []
        self._reads: list[Callable[[dict], object]] = []

    def pin(
        self, key: str, old: object, new: str, label: str, read: Callable[[dict], object]
    ) -> None:
        """Move one pin from ``old`` to ``new``, or verify it already there.

        ``old`` is whatever the parsed YAML carried; anything that is not a
        non-empty string means the author never wrote the pin, and writing it
        for them would be inserting a key -- which this tool refuses to do.

        ``read`` navigates a re-parsed document back to this pin's value; it
        is how ``verify`` later proves the substitution landed on the parsed
        pin and not on some other text that happened to spell the same bytes.
        """
        if not isinstance(old, str) or not old.strip():
            raise ValidationError(
                f"{self.path}: expected an existing {label} pin to refresh, found "
                f"{old!r}; add the {key} key by hand first -- refresh never inserts keys"
            )
        if old == new:
            return
        # The key must start a token (not be the tail of a longer key), may be
        # quoted in either style, and must be immediately followed by the old
        # digest -- optionally quoted -- so nothing but that digest can match.
        # The digest itself must end where the old one ends: hex never
        # continues past its own last character, so a digest that is a strict
        # prefix of a sibling's must not count that sibling as a second match.
        pattern = re.compile(
            r"(?<![A-Za-z0-9_-])(['\"]?)"
            + re.escape(key)
            + r"\1(\s*:\s*)(['\"]?)"
            + re.escape(old)
            + r"(?![0-9a-f])"
        )
        matches = list(pattern.finditer(self.text))
        if not matches:
            raise ValidationError(
                f"{self.path}: cannot find the authored text of {label} "
                f"(key {key!r} with digest {old}); refresh only rewrites pins it "
                "can locate verbatim"
            )
        if len(matches) > 1:
            raise ValidationError(
                f"{self.path}: {label} (key {key!r} with digest {old}) appears "
                f"{len(matches)} times; refresh cannot tell which one is meant"
            )
        self.text = pattern.sub(lambda m: f"{m.group(0)[: -len(old)]}{new}", self.text, count=1)
        self.changes.append(PinChange(self.path, label, old, new))
        self._reads.append(read)

    def verify(self) -> None:
        """Prove the rewritten text still parses to every refreshed digest.

        Exactly-one-match shows the old digest was textually unique, not that
        the matched bytes were the parsed pin: a comment can carry the same
        digest while the real pin hides in a spelling the pattern cannot see
        -- a folded scalar, say -- and the substitution would then fix the
        comment and call the stale pin refreshed.  So the rewritten text is
        re-parsed with the same loader the validators use, and every refreshed
        pin must read back as its new digest.  A mismatch raises before
        anything is written: fail closed, and let the author respell the pin.
        """
        if not self.changes:
            return
        try:
            data = (
                json.loads(self.text)
                if self.path.suffix == ".json"
                else yaml.safe_load(self.text)
            )
        except (json.JSONDecodeError, yaml.YAMLError) as exc:
            raise ValidationError(
                f"{self.path}: the refreshed text no longer parses ({exc}); nothing "
                "was written -- fix the file's spelling by hand and refresh again"
            ) from exc
        if not isinstance(data, dict):
            raise ValidationError(
                f"{self.path}: the refreshed text no longer parses as a mapping; "
                "nothing was written -- fix the file's spelling by hand"
            )
        for change, read in zip(self.changes, self._reads):
            found = read(data)
            if found != change.new:
                raise ValidationError(
                    f"{self.path}: rewriting {change.pin} changed text the parser "
                    f"does not read as that pin (it re-parses to {found!r}, not the "
                    "new digest); the real pin is spelled in a way the refresher "
                    "cannot target -- a folded scalar, or a comment carrying the "
                    "same digest.  Nothing was written; respell the pin as a plain "
                    "`key: digest` line by hand and refresh again"
                )

    def write(self) -> list[PinChange]:
        """Persist the substitutions, if there were any, and hand them back."""
        if self.changes:
            self.path.write_text(self.text, encoding="utf-8")
        return self.changes


def _refresh_ledgers(
    base: Edition, sources_dir: Path, reviews_dir: Path
) -> list[_PinnedFile]:
    """Prepare every fidelity ledger's re-pin against the extraction bodies.

    The expected digest is ``Extraction.body_sha256`` -- the same byte-exact
    body hash ``extraction.py`` verifies -- never a rehash invented here.  A
    covered source without a committed extraction is an error: there is
    nothing true to pin to.  Nothing is written here; the caller verifies the
    whole batch and only then commits it to disk.
    """
    files: list[_PinnedFile] = []
    for article in base.articles:
        ledger_path = article.fidelity
        data = load_structured(ledger_path)
        source_ids = ledger_source_ids(ledger_path, data)
        if not source_ids:
            raise ValidationError(
                f"{ledger_path}: the ledger declares no source_ids, so there is no "
                "source_body_sha256 to refresh"
            )
        declared = data.get("source_body_sha256")
        if declared is None:
            raise ValidationError(
                f"{ledger_path}: has no source_body_sha256 key; add it by hand first "
                "-- refresh never inserts keys"
            )
        file = _PinnedFile(ledger_path, reviews_dir)
        for source_id in source_ids:
            extraction = load_extraction(sources_dir, source_id)
            if extraction is None:
                raise ValidationError(
                    f"{ledger_path}: source {source_id} has no committed extraction at "
                    f"library/sources/{source_id}/{EXTRACTION_FILENAME}, so its "
                    "source_body_sha256 cannot be recomputed"
                )
            if isinstance(declared, str):
                # The single-digest shape only ever covers one source; a
                # multi-source ledger spelled this way is a validation problem,
                # not one a refresh should paper over.
                if len(source_ids) != 1:
                    raise ValidationError(
                        f"{ledger_path}: source_body_sha256 is a single digest but the "
                        f"ledger covers {len(source_ids)} sources; key each pin by "
                        "source id before refreshing"
                    )
                file.pin(
                    "source_body_sha256",
                    declared,
                    extraction.body_sha256,
                    "source_body_sha256",
                    lambda data: data.get("source_body_sha256"),
                )
            elif isinstance(declared, dict):
                file.pin(
                    source_id,
                    declared.get(source_id),
                    extraction.body_sha256,
                    f"source_body_sha256[{source_id}]",
                    lambda data, sid=source_id: _parsed_value(
                        data.get("source_body_sha256"), sid
                    ),
                )
            else:
                raise ValidationError(
                    f"{ledger_path}: source_body_sha256 must be a hex digest or a "
                    f"mapping keyed by source id, got {type(declared).__name__}"
                )
        files.append(file)
    return files


def _refresh_overlays(
    base: Edition, edition_dir: Path, reviews_dir: Path
) -> list[_PinnedFile]:
    """Prepare every on-disk language overlay's re-pin against the base.

    Overlays are found by looking, not by configuration: whatever manifests
    live under ``translations/*/edition.yaml`` are the overlays an author can
    have left stale.  Which languages *must* exist is validation's question.
    Nothing is written here; the caller verifies the whole batch first.
    """
    files: list[_PinnedFile] = []
    translations_dir = edition_dir / "translations"
    if not translations_dir.is_dir():
        return files
    for overlay_path in sorted(translations_dir.glob("*/edition.yaml")):
        language = overlay_path.parent.name
        data = load_structured(overlay_path)
        file = _PinnedFile(overlay_path, reviews_dir)
        file.pin(
            "base_copy_sha256",
            data.get("base_copy_sha256"),
            _edition_copy_sha256(base),
            "base_copy_sha256",
            lambda data: data.get("base_copy_sha256"),
        )
        if base.editorial:
            editorial_row = data.get("editorial")
            row = editorial_row if isinstance(editorial_row, dict) else {}
            file.pin(
                "source_sha256",
                row.get("source_sha256"),
                _file_sha256(base.editorial.path),
                "editorial.source_sha256",
                lambda data: _parsed_value(data.get("editorial"), "source_sha256"),
            )
        rows_by_id = {
            str(row.get("id")): row
            for row in data.get("articles") or []
            if isinstance(row, dict) and row.get("id")
        }
        for article in base.articles:
            row = rows_by_id.get(article.id)
            if row is None:
                raise ValidationError(
                    f"{overlay_path}: translation {language!r} has no row for article "
                    f"{article.id}, so its source_sha256 cannot be refreshed"
                )
            file.pin(
                "source_sha256",
                row.get("source_sha256"),
                _file_sha256(article.manuscript),
                f"articles[{article.id}].source_sha256",
                lambda data, aid=article.id: _parsed_value(
                    _parsed_row(data.get("articles"), aid), "source_sha256"
                ),
            )
            _refresh_figure_pins(file, overlay_path, language, article, row)
        section_rows = data.get("sections") or []
        for index, section in enumerate(base.sections):
            row = section_rows[index] if index < len(section_rows) else None
            if not isinstance(row, dict):
                raise ValidationError(
                    f"{overlay_path}: translation {language!r} has no row for section "
                    f"{index + 1} ({section.kind}), so its source_sha256 cannot be "
                    "refreshed"
                )
            file.pin(
                "source_sha256",
                row.get("source_sha256"),
                _file_sha256(section.path),
                f"sections[{index + 1}].source_sha256",
                lambda data, i=index: _parsed_value(
                    _parsed_index(data.get("sections"), i), "source_sha256"
                ),
            )
        files.append(file)
    return files


def _refresh_figure_pins(
    file: _PinnedFile, overlay_path: Path, language: str, article: Article, row: dict
) -> None:
    """Re-pin one article's localized figures to the base caption and credit.

    The expected digests come from ``media_schema``'s canonical hashers over
    the *resolved* base figures -- the caption as authored in ``edition.yaml``
    and the credit as recorded on the curated source asset -- which is exactly
    what ``localize_figures`` will verify against.
    """
    if not article.figures:
        return
    figure_rows = {
        str(item.get("id")): item
        for item in row.get("figures") or []
        if isinstance(item, dict) and item.get("id")
    }
    for figure in article.figures:
        figure_row = figure_rows.get(figure.id)
        if figure_row is None:
            raise ValidationError(
                f"{overlay_path}: translation {language!r} article {article.id} has no "
                f"row for figure {figure.id}, so its caption and credit pins cannot "
                "be refreshed"
            )
        file.pin(
            "source_caption_sha256",
            figure_row.get("source_caption_sha256"),
            caption_sha256(figure.id, figure.caption),
            f"articles[{article.id}].figures[{figure.id}].source_caption_sha256",
            lambda data, aid=article.id, fid=figure.id: _parsed_value(
                _parsed_figure(data, aid, fid), "source_caption_sha256"
            ),
        )
        file.pin(
            "source_credit_sha256",
            figure_row.get("source_credit_sha256"),
            credit_sha256(figure.id, figure.credit),
            f"articles[{article.id}].figures[{figure.id}].source_credit_sha256",
            lambda data, aid=article.id, fid=figure.id: _parsed_value(
                _parsed_figure(data, aid, fid), "source_credit_sha256"
            ),
        )


# The verify() readbacks navigate a *re-parsed* document, which may have any
# shape at all after a bad substitution, so these helpers answer "nothing
# there" with None rather than trusting the structure the original parse had.


def _parsed_value(row: object, key: str) -> object:
    """The key's value, if ``row`` re-parsed as a mapping at all."""
    return row.get(key) if isinstance(row, dict) else None


def _parsed_row(rows: object, row_id: str) -> object:
    """The list entry whose ``id`` is ``row_id``, if ``rows`` is such a list."""
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and str(row.get("id")) == row_id:
                return row
    return None


def _parsed_index(rows: object, index: int) -> object:
    """The list entry at ``index``, if ``rows`` is a list that long."""
    if isinstance(rows, list) and 0 <= index < len(rows):
        return rows[index]
    return None


def _parsed_figure(data: dict, article_id: str, figure_id: str) -> object:
    """One article's figure row, walked fresh from a re-parsed overlay."""
    article_row = _parsed_row(data.get("articles"), article_id)
    return _parsed_row(_parsed_value(article_row, "figures"), figure_id)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
