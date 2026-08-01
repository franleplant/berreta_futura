"""Recompute the derivable hash pins an edition's authors keep by hand.

An edition's authored files carry a small economy of SHA-256 pins.  A
translation overlay pins the base edition's copy (``base_copy_sha256``), each
translated file's English source (``source_sha256``), and each localized
figure's base caption and credit (``source_caption_sha256`` /
``source_credit_sha256``).  Each article row in ``edition.yaml`` pins the
committed extraction body of every source it is written from
(``source_body_sha256``).  Every one of those digests is a pure function of
files already in the repository, yet until now each was computed by hand --
eighteen shasum invocations per Spanish overlay -- so a routine base-copy edit
meant an afternoon of ritual.

``refresh_pins`` recomputes every such pin for one edition and rewrites the
stale ones in place. Three rules keep it honest:

* **Existing pins are changed surgically.** These files are hand-authored;
  their comments, key order, quoting, and line wrapping are the author's.
  Ordinary refreshes therefore replace exactly the digest. The structural
  collecting-edition repair replaces only the one article row entry it derives,
  leaving that row's other keys, comments and blank lines where they were.

* **It repairs only derivable state.** A collecting edition's article-row pin
  structure is wholly determined by that row's ``source_ids`` and the committed
  extractions, so missing or malformed ``source_body_sha256`` structure is
  repaired by machine. Released editions retain the historical rule that pin
  keys must already exist. Anything under ``editions/<id>/reviews/`` is a
  signed record of what a reviewer actually saw and is refused outright: review
  records are recorded only via ``mag review record``.

* **Verify everything, then write everything.**  A textual match can be a
  mirage -- a comment can carry a pin's digest while the real pin hides in a
  spelling the pattern cannot see -- so after substitution each file's
  rewritten text is re-parsed with the same loader validation uses, and every
  refreshed pin must read back as its new digest.  Only when every file
  verifies does any file reach disk: a raise from this module's own checks,
  anywhere, means the working tree is exactly as the author left it. The
  edition-scoped write lock, compare-and-swap check, and rollback keep the
  complete multi-file refresh atomic under write faults and cooperative
  concurrent refreshes.

The function deliberately reuses the canonical hashers -- ``extraction.py``'s
body hash, ``manifest.py``'s edition-copy hash, ``media_schema.py``'s caption
and credit hashes -- rather than restating them, so a pin refreshed here is by
construction the pin validation expects.
"""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import re
import tomllib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir, mkstemp

import yaml

from .errors import ValidationError
from .extraction import EXTRACTION_FILENAME, load_extraction
from .io import load_structured
from .manifest import Article, Edition, _edition_copy_sha256, load_edition
from .media_schema import caption_sha256, credit_sha256
from .records import load_records
from .release import load_release_state

_LOCK_DIRECTORY = Path(gettempdir()) / "magazine-pin-locks"
_SAFE_EDITION_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class PinChange:
    """One derivable pin value rewritten in one authored file.

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


@dataclass(frozen=True)
class _InputFingerprint:
    path: Path
    content_sha256: str


@dataclass
class _PinnedInstall:
    file: "_PinnedFile"
    backup: Path
    installed_identity: tuple[int, int] | None = None


class _ConcurrentWrite(ValidationError):
    """A target changed during commit and its new bytes were preserved."""


def refresh_pins(
    root: Path, edition_id: str, *, within: Iterable[Path] | None = None
) -> PinReport:
    """Recompute every derivable pin in the edition's authored files.

    Covers, for the named edition: the ``source_body_sha256`` pins of every
    article row in ``edition.yaml`` (recomputed from the committed
    ``library/sources/<id>/extracted.md`` bodies), and, for every non-source
    language overlay under ``translations/``, the ``base_copy_sha256``, the
    editorial's and each article's and section's ``source_sha256``, and each
    figure's caption and credit pins.

    ``within`` narrows the sweep: when given, only pinned files under those
    directories are examined -- everything else is neither read nor required
    to be refreshable, exactly as if it were not there.  That is how a caller
    with authority over one overlay (the translation stage) refreshes it
    without demanding the rest of the edition be consistent first.  The
    default, ``None``, sweeps the whole edition.

    Stale pins are rewritten in place by textual substitution and reported as
    ``PinChange`` rows; correct pins are left byte-for-byte alone. A collecting
    edition's article rows also have missing or malformed ``source_body_sha256``
    structure repaired from committed extractions. Raises ``ValidationError``
    when a released-edition pin key it expects is missing, when a target file
    lives under ``reviews/``, when a rewritten file does not re-parse to its
    new value, or when the base edition itself cannot be loaded. Every such raise
    happens before anything is written: a refresh this module refuses leaves
    the working tree byte-for-byte as it found it. Write faults trigger a
    rollback of every completed replacement.
    """
    _validate_edition_id(edition_id)
    root = root.resolve()
    with _edition_lock(root, edition_id):
        return _refresh_pins_locked(root, edition_id, within=within)


def _refresh_pins_locked(
    root: Path, edition_id: str, *, within: Iterable[Path] | None = None
) -> PinReport:
    """Prepare, verify, compare-and-swap, and commit one locked pin batch."""

    _validate_edition_id(edition_id)
    config = _load_config(root)
    editions_dir = _safe_repo_path(
        root,
        root / config["editions"],
        label="Configured editions directory",
    )
    sources_dir = _safe_repo_path(
        root,
        root / config["sources"],
        label="Configured sources directory",
    )
    edition_dir = _safe_repo_path(
        editions_dir,
        editions_dir / edition_id,
        label=f"Edition {edition_id}",
    )
    if not (edition_dir / "edition.yaml").is_file():
        raise ValidationError(f"Edition manifest not found: {edition_dir / 'edition.yaml'}")
    reviews_dir = edition_dir / "reviews"
    release_state_path = _safe_repo_path(
        root,
        root / config["release_state"],
        label="Configured release state",
    )
    release_state = load_release_state(release_state_path)
    repair_pin_structure = edition_id in release_state.collecting_edition_ids

    dependency_snapshot = _snapshot_pin_dependencies(
        root,
        edition_dir,
        sources_dir,
        release_state_path,
    )
    # The scope test is by directory ancestry, resolved on both sides, so a
    # caller may name the overlay directory and cover whatever lives in it.
    scope = None if within is None else tuple(Path(path).resolve() for path in within)

    def in_scope(path: Path) -> bool:
        return scope is None or any(
            path.resolve().is_relative_to(ancestor) for ancestor in scope
        )

    # Two-phase commit, in miniature: every file's rewritten text is computed
    # and verified first, and only when the whole batch verifies does any file
    # reach disk.  Otherwise a failure in the second file would leave the
    # first one changed while the report explaining the change was discarded.
    files: list[_PinnedFile] = []
    files.extend(
        _refresh_source_pins(
            edition_dir / "edition.yaml",
            sources_dir,
            reviews_dir,
            in_scope,
            repair_derived_structure=repair_pin_structure,
        )
    )
    # The source pins are read from the manifest's raw rows, deliberately, and
    # the fully validated edition is loaded only when an overlay actually needs
    # it.  A malformed ``source_body_sha256`` is exactly the state this refresh
    # exists to repair, and ``load_edition`` refuses it -- so loading the
    # edition first would let a broken pin veto its own repair.  The overlay
    # half has no such tension: it hashes the base edition's copy and files, so
    # it genuinely cannot proceed until the base edition loads.
    overlays = sorted((edition_dir / "translations").glob("*/edition.yaml"))
    if any(in_scope(overlay) for overlay in overlays):
        records = {record.id: record for record in load_records(sources_dir)}
        base = load_edition(
            root,
            edition_id,
            set(records),
            publication_name=config["publication_name"],
            source_records=records,
        )
        files.extend(_refresh_overlays(base, edition_dir, reviews_dir, in_scope))
    for file in files:
        file.verify()
    changed_files = [file for file in files if file.changes]
    if changed_files:
        _replace_pinned_files_atomically(
            changed_files,
            dependencies=dependency_snapshot,
        )
    changes = [
        change
        for file in changed_files
        for change in file.changes
    ]
    return PinReport(edition_id, tuple(changes))


def _load_config(root: Path) -> dict[str, str]:
    """The path and publication facts ``magazine.toml`` contributes.

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
        "release_state": str(
            paths.get("release_state", "library/release-state.yaml")
        ),
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
        self.original_bytes = path.read_bytes()
        try:
            self.text = self.original_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError(f"{path}: pin file is not valid UTF-8: {exc}") from exc
        self.changes: list[PinChange] = []
        self._staged_path: Path | None = None
        self._checks: list[
            tuple[str, object, Callable[[dict], object]]
        ] = []

    def pin(
        self,
        key: str,
        old: object,
        new: str,
        label: str,
        read: Callable[[dict], object],
        *,
        article_id: str | None = None,
    ) -> None:
        """Move one pin from ``old`` to ``new``, or verify it already there.

        ``old`` is whatever the parsed YAML carried; anything that is not a
        non-empty string means the author never wrote the pin, and writing it
        for them would be inserting a key -- which this tool refuses to do.

        ``read`` navigates a re-parsed document back to this pin's value; it
        is how ``verify`` later proves the substitution landed on the parsed
        pin and not on some other text that happened to spell the same bytes.

        ``article_id`` narrows the textual search to that article's row.  Every
        article's source pins now live in one ``edition.yaml``, so two articles
        written from the same source carry the same digest under the same key
        -- and an unscoped search would find both and refuse to move either,
        exactly when a re-extraction makes the refresh necessary.  Uniqueness is
        a property of one row, so the search is too.
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
        if article_id is None:
            begin, end, scope = 0, len(self.text), ""
        else:
            begin, end = _article_row_span(self.path, self.text, article_id)
            scope = f" within article {article_id}"
        segment = self.text[begin:end]
        matches = list(pattern.finditer(segment))
        if not matches:
            raise ValidationError(
                f"{self.path}: cannot find the authored text of {label} "
                f"(key {key!r} with digest {old}){scope}; refresh only rewrites pins "
                "it can locate verbatim"
            )
        if len(matches) > 1:
            raise ValidationError(
                f"{self.path}: {label} (key {key!r} with digest {old}) appears "
                f"{len(matches)} times{scope}; refresh cannot tell which one is meant"
            )
        replaced = pattern.sub(
            lambda m: f"{m.group(0)[: -len(old)]}{new}", segment, count=1
        )
        self.text = self.text[:begin] + replaced + self.text[end:]
        self.changes.append(PinChange(self.path, label, old, new))
        self._checks.append((label, new, read))

    def set_article_entry(
        self,
        article_id: str,
        key: str,
        value: object,
        label: str,
        read: Callable[[dict], object],
    ) -> None:
        """Insert or reshape one fully derivable entry of one article row.

        This is reserved for a collecting edition's ``source_body_sha256``,
        whose shape is wholly determined by the row's ``source_ids`` and the
        committed extractions.  Only the named entry of the named row is
        rewritten: every other key, comment and blank line in ``edition.yaml``
        -- including the rest of that row -- is left exactly as authored.
        """

        try:
            parsed = yaml.safe_load(self.text)
        except yaml.YAMLError as exc:
            raise ValidationError(
                f"{self.path}: cannot parse the edition manifest for {label} repair: {exc}"
            ) from exc
        row = _parsed_row(_parsed_value(parsed, "articles"), article_id)
        if not isinstance(row, dict):
            raise ValidationError(
                f"{self.path}: no article row {article_id!r} to repair"
            )
        old = row.get(key, "<missing>")
        if old == value:
            return
        self.text = _replace_article_yaml_entry(
            self.path,
            self.text,
            article_id,
            key,
            value,
        )
        self.changes.append(
            PinChange(
                self.path,
                label,
                _pin_value_display(old),
                _pin_value_display(value),
            )
        )
        self._checks.append((label, value, read))

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
            data = yaml.safe_load(self.text)
        except yaml.YAMLError as exc:
            raise ValidationError(
                f"{self.path}: the refreshed text no longer parses ({exc}); nothing "
                "was written -- fix the file's spelling by hand and refresh again"
            ) from exc
        if not isinstance(data, dict):
            raise ValidationError(
                f"{self.path}: the refreshed text no longer parses as a mapping; "
                "nothing was written -- fix the file's spelling by hand"
            )
        for label, expected, read in self._checks:
            found = read(data)
            if found != expected:
                raise ValidationError(
                    f"{self.path}: rewriting {label} changed text the parser "
                    f"does not read as that pin (it re-parses to {found!r}, not "
                    f"{expected!r}); the real pin is spelled in a way the refresher "
                    "cannot target -- a folded scalar, or a comment carrying the "
                    "same digest.  Nothing was written; respell the pin as a plain "
                    "`key: digest` line by hand and refresh again"
                )

    @property
    def updated_bytes(self) -> bytes:
        return self.text.encode("utf-8")

    def write(self) -> list[PinChange]:
        """Commit the already-staged replacement.

        Kept as the narrow write seam used by translation staging fault tests.
        """

        if self.changes:
            if self._staged_path is None:
                raise OSError(f"No staged replacement is ready for {self.path}")
            try:
                os.link(
                    self._staged_path,
                    self.path,
                    follow_symlinks=False,
                )
            except FileExistsError as exc:
                raise _ConcurrentWrite(
                    f"Pin destination appeared during commit and was preserved: "
                    f"{self.path}"
                ) from exc
        return self.changes


def _source_pin_shape_matches(
    declared: object,
    source_ids: tuple[str, ...],
) -> bool:
    """Whether a collecting article row already uses its canonical pin shape."""

    if len(source_ids) == 1:
        return isinstance(declared, str) and bool(declared.strip())
    return (
        isinstance(declared, dict)
        and set(str(key) for key in declared) == set(source_ids)
        and all(
            isinstance(declared.get(source_id), str)
            and bool(str(declared[source_id]).strip())
            for source_id in source_ids
        )
    )


# Where a repaired pin is inserted when the row never had one: immediately
# before whichever of these keys comes first.  ``source_body_sha256`` belongs
# beside the ``source_ids`` it pins, so the row reads as one provenance block.
_PIN_INSERTION_ANCHORS = ("manuscript", "figures", "tail_art_path", "opener_art")


def _replace_article_yaml_entry(
    path: Path,
    text: str,
    article_id: str,
    key: str,
    value: object,
) -> str:
    """Replace or insert one key of one article row, retaining unrelated text.

    The row is located through ``yaml.compose`` rather than by pattern, so the
    edit lands on the parsed node and not on some other text that happens to
    spell the same words; the caller's ``verify`` then re-parses the result and
    proves it.  Comments and blank lines inside the replaced entry survive,
    for the same reason the surgical digest substitution exists: these files
    are hand-authored and the author's annotations are not the tool's to drop.
    """

    try:
        root_node = yaml.compose(text)
    except yaml.YAMLError as exc:
        raise ValidationError(
            f"{path}: cannot locate {key} for structural repair: {exc}"
        ) from exc
    row_node = _article_row_node(path, root_node, article_id)
    pairs = list(row_node.value)
    matching = [
        (index, key_node)
        for index, (key_node, _) in enumerate(pairs)
        if getattr(key_node, "value", None) == key
    ]
    if len(matching) > 1:
        raise ValidationError(
            f"{path}: article {article_id} declares {key} more than once; "
            "structural repair is ambiguous"
        )
    indent = " " * pairs[0][0].start_mark.column
    lines = text.splitlines(keepends=True)
    row_end = min(row_node.end_mark.line, len(lines))
    replacement = [
        f"{indent}{line}" if line.strip() else line
        for line in yaml.safe_dump(
            {key: value},
            sort_keys=False,
            allow_unicode=True,
            width=100,
        ).splitlines(keepends=True)
    ]
    if matching:
        index, key_node = matching[0]
        if index == 0:
            raise ValidationError(
                f"{path}: article {article_id} opens with {key}; structural repair "
                "cannot rewrite a row's first key without disturbing the row itself"
            )
        start = key_node.start_mark.line
        end = pairs[index + 1][0].start_mark.line if index + 1 < len(pairs) else row_end
        preserved = [
            line
            for line in lines[start + 1 : end]
            if not line.strip() or line.lstrip().startswith("#")
        ]
        return "".join(lines[:start] + replacement + preserved + lines[end:])
    anchors = {
        getattr(key_node, "value", None): key_node.start_mark.line
        for key_node, _ in pairs[1:]
    }
    insertion = min(
        (anchors[name] for name in _PIN_INSERTION_ANCHORS if name in anchors),
        default=row_end,
    )
    return "".join(lines[:insertion] + replacement + lines[insertion:])


def _article_row_span(path: Path, text: str, article_id: str) -> tuple[int, int]:
    """The character span one article row occupies in the manifest text.

    Derived from the composed node, so it is the parser's idea of where the row
    begins and ends, not a pattern's.  Recomputed per call because each pin
    substitution changes the text beneath it.
    """

    try:
        root_node = yaml.compose(text)
    except yaml.YAMLError as exc:
        raise ValidationError(
            f"{path}: cannot locate article {article_id} to refresh its pins: {exc}"
        ) from exc
    row = _article_row_node(path, root_node, article_id)
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    start = offsets[min(row.start_mark.line, len(lines))]
    end = offsets[min(row.end_mark.line, len(lines))]
    return start, end


def _article_row_node(
    path: Path, root_node: object, article_id: str
) -> yaml.MappingNode:
    """The composed node of one article row, or a refusal naming the file."""

    if not isinstance(root_node, yaml.MappingNode):
        raise ValidationError(f"{path}: edition manifest must be a mapping")
    articles = next(
        (
            value_node
            for key_node, value_node in root_node.value
            if getattr(key_node, "value", None) == "articles"
        ),
        None,
    )
    if not isinstance(articles, yaml.SequenceNode):
        raise ValidationError(f"{path}: edition manifest articles must be a list")
    for item in articles.value:
        if not isinstance(item, yaml.MappingNode) or not item.value:
            continue
        declared = next(
            (
                getattr(value_node, "value", None)
                for key_node, value_node in item.value
                if getattr(key_node, "value", None) == "id"
            ),
            None,
        )
        if declared == article_id:
            return item
    raise ValidationError(
        f"{path}: no article row {article_id!r} to repair"
    )


def _pin_value_display(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _refreshable_row(manifest_path: Path, row: object) -> tuple[str, tuple[str, ...]]:
    """One article row's id and declared sources, or a refusal naming the row.

    The rows are read raw rather than from a loaded ``Edition`` -- see
    ``_refresh_pins_locked`` -- so the two fields the refresh derives from have
    to be checked here.  Anything else wrong with the row is validation's to
    say; this only refuses what would make the recomputation guesswork.
    """

    if not isinstance(row, dict) or not str(row.get("id") or "").strip():
        raise ValidationError(
            f"{manifest_path}: every article row needs an id before its "
            "source_body_sha256 can be refreshed"
        )
    article_id = str(row["id"])
    source_ids = row.get("source_ids")
    if (
        not isinstance(source_ids, list)
        or not source_ids
        or any(not str(item or "").strip() for item in source_ids)
    ):
        raise ValidationError(
            f"{manifest_path}: article {article_id} declares no source_ids, so there "
            "is no source_body_sha256 to refresh"
        )
    return article_id, tuple(str(item) for item in source_ids)


def _refresh_source_pins(
    manifest_path: Path,
    sources_dir: Path,
    reviews_dir: Path,
    in_scope: Callable[[Path], bool],
    *,
    repair_derived_structure: bool,
) -> list[_PinnedFile]:
    """Prepare ``edition.yaml``'s article pins against the extraction bodies.

    The expected digest is ``Extraction.body_sha256`` -- the same byte-exact
    body hash ``extraction.py`` verifies -- never a rehash invented here.  A
    declared source without a committed extraction is an error: there is
    nothing true to pin to.  The manifest outside the caller's scope is skipped
    before it is even read -- out of scope means not this refresh's business,
    stale or not.  Nothing is written here; the caller verifies the whole batch
    and only then commits it to disk.  When ``repair_derived_structure`` is
    true, missing or incorrectly shaped pin structure is repaired from those
    same extractions.

    One file carries every article's pins now, so this returns at most one
    ``_PinnedFile`` -- and a single atomic rewrite moves them all, instead of
    one rewrite per article.  The rows are read raw, not from a loaded
    ``Edition``, so a manifest whose pin is malformed can still have that pin
    repaired rather than being refused by the very validation the repair exists
    to satisfy.
    """
    if not in_scope(manifest_path):
        return []
    data = load_structured(manifest_path)
    file = _PinnedFile(manifest_path, reviews_dir)
    for row in data.get("articles") or []:
        article_id, source_ids = _refreshable_row(manifest_path, row)
        declared = row.get("source_body_sha256")
        if declared is None and not repair_derived_structure:
            raise ValidationError(
                f"{manifest_path}: article {article_id} has no source_body_sha256 key; "
                "add it by hand first -- refresh never inserts keys"
            )
        extractions = {}
        for source_id in source_ids:
            extraction = load_extraction(sources_dir, source_id)
            if extraction is None:
                raise ValidationError(
                    f"{manifest_path}: article {article_id} source {source_id} has no "
                    f"committed extraction at library/sources/{source_id}/"
                    f"{EXTRACTION_FILENAME}, so its source_body_sha256 cannot be "
                    "recomputed"
                )
            extractions[source_id] = extraction
        expected: str | dict[str, str]
        if len(source_ids) == 1:
            expected = extractions[source_ids[0]].body_sha256
        else:
            expected = {
                source_id: extractions[source_id].body_sha256
                for source_id in source_ids
            }
        if repair_derived_structure and not _source_pin_shape_matches(
            declared, source_ids
        ):
            file.set_article_entry(
                article_id,
                "source_body_sha256",
                expected,
                f"articles[{article_id}].source_body_sha256",
                lambda refreshed, aid=article_id: _parsed_value(
                    _parsed_row(refreshed.get("articles"), aid), "source_body_sha256"
                ),
            )
            continue
        for source_id in source_ids:
            extraction = extractions[source_id]
            if isinstance(declared, str):
                # The single-digest shape only ever covers one source; a
                # multi-source article spelled this way is a validation problem,
                # not one a refresh should paper over.
                if len(source_ids) != 1:
                    raise ValidationError(
                        f"{manifest_path}: article {article_id} source_body_sha256 is a "
                        f"single digest but the article covers {len(source_ids)} "
                        "sources; key each pin by source id before refreshing"
                    )
                file.pin(
                    "source_body_sha256",
                    declared,
                    extraction.body_sha256,
                    f"articles[{article_id}].source_body_sha256",
                    lambda refreshed, aid=article_id: _parsed_value(
                        _parsed_row(refreshed.get("articles"), aid),
                        "source_body_sha256",
                    ),
                    article_id=article_id,
                )
            elif isinstance(declared, dict):
                file.pin(
                    source_id,
                    declared.get(source_id),
                    extraction.body_sha256,
                    f"articles[{article_id}].source_body_sha256[{source_id}]",
                    lambda refreshed, aid=article_id, sid=source_id: _parsed_value(
                        _parsed_value(
                            _parsed_row(refreshed.get("articles"), aid),
                            "source_body_sha256",
                        ),
                        sid,
                    ),
                    article_id=article_id,
                )
            else:
                raise ValidationError(
                    f"{manifest_path}: article {article_id} source_body_sha256 must be a "
                    f"hex digest or a mapping keyed by source id, got "
                    f"{type(declared).__name__}"
                )
    return [file]


def _refresh_overlays(
    base: Edition, edition_dir: Path, reviews_dir: Path, in_scope: Callable[[Path], bool]
) -> list[_PinnedFile]:
    """Prepare every on-disk language overlay's re-pin against the base.

    Overlays are found by looking, not by configuration: whatever manifests
    live under ``translations/*/edition.yaml`` are the overlays an author can
    have left stale.  Which languages *must* exist is validation's question,
    and an overlay outside the caller's scope is skipped unread -- a
    half-staged sibling language must not be able to veto this one's refresh.
    Nothing is written here; the caller verifies the whole batch first.
    """
    files: list[_PinnedFile] = []
    translations_dir = edition_dir / "translations"
    if not translations_dir.is_dir():
        return files
    for overlay_path in sorted(translations_dir.glob("*/edition.yaml")):
        if not in_scope(overlay_path):
            continue
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


@contextmanager
def _edition_lock(root: Path, edition_id: str):
    """Serialize pin refreshes for one edition without touching the repo."""

    lock_name = hashlib.sha256(
        f"{root}:{edition_id}".encode("utf-8")
    ).hexdigest()
    lock_path = _LOCK_DIRECTORY / f"{lock_name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _replace_pinned_files_atomically(
    files: list[_PinnedFile],
    *,
    dependencies: tuple[_InputFingerprint, ...],
) -> None:
    """Conditionally commit every pin file without overwriting new bytes."""

    staged: dict[Path, Path] = {}
    installs: list[_PinnedInstall] = []
    active: _PinnedInstall | None = None
    try:
        for file in files:
            staged[file.path] = _stage_bytes(file.path, file.updated_bytes)
            file._staged_path = staged[file.path]
        _assert_pin_dependencies(dependencies, installs)
        for file in files:
            _assert_pin_dependencies(dependencies, installs)
            active = _prepare_pinned_install(file)
            installs.append(active)
            file.write()
            stat = file.path.stat()
            active.installed_identity = (stat.st_dev, stat.st_ino)
            active = None
        _assert_pin_dependencies(dependencies, installs)
    except (ValidationError, OSError) as exc:
        rollback_errors: list[str] = []
        io_fault_active = active if isinstance(exc, OSError) else None
        for install in reversed(installs):
            try:
                _restore_pinned_install(
                    install,
                    discard_partial=install is io_fault_active,
                )
            except OSError as rollback_exc:
                rollback_errors.append(f"{install.file.path}: {rollback_exc}")
        if not rollback_errors:
            raise
        detail = f"Cannot refresh pins atomically: {exc}"
        detail += "; rollback failed: " + "; ".join(rollback_errors)
        raise ValidationError(detail) from exc
    else:
        for install in installs:
            install.backup.unlink(missing_ok=True)
    finally:
        for file in files:
            file._staged_path = None
        for install in installs:
            install.backup.unlink(missing_ok=True)
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def _prepare_pinned_install(file: _PinnedFile) -> _PinnedInstall:
    backup = _reserve_backup(file.path)
    install = _PinnedInstall(file, backup)
    try:
        os.replace(file.path, backup)
    except OSError:
        backup.unlink(missing_ok=True)
        raise
    if backup.read_bytes() != file.original_bytes:
        _restore_pinned_install(install, discard_partial=False)
        raise _ConcurrentWrite(
            f"Pin destination changed during commit and was preserved: {file.path}"
        )
    return install


def _restore_pinned_install(
    install: _PinnedInstall,
    *,
    discard_partial: bool,
) -> None:
    file = install.file
    path = file.path
    if discard_partial and (path.exists() or path.is_symlink()):
        path.unlink()
    elif install.installed_identity is not None and path.exists():
        stat = path.stat()
        if (
            (stat.st_dev, stat.st_ino) == install.installed_identity
            and path.read_bytes() == file.updated_bytes
        ):
            path.unlink()
    if not path.exists() and not path.is_symlink():
        try:
            os.link(install.backup, path, follow_symlinks=False)
        except FileExistsError:
            pass
    install.backup.unlink(missing_ok=True)


def _assert_pin_dependencies(
    dependencies: tuple[_InputFingerprint, ...],
    installs: list[_PinnedInstall],
) -> None:
    committed = {
        install.file.path: install.file.updated_bytes
        for install in installs
        if install.installed_identity is not None
    }
    conflicts: list[str] = []
    for fingerprint in dependencies:
        expected = committed.get(fingerprint.path)
        expected_sha256 = (
            hashlib.sha256(expected).hexdigest()
            if expected is not None
            else fingerprint.content_sha256
        )
        if (
            not fingerprint.path.is_file()
            or fingerprint.path.is_symlink()
            or _file_sha256(fingerprint.path) != expected_sha256
        ):
            conflicts.append(str(fingerprint.path))
    if conflicts:
        raise ValidationError(
            [
                "Pin refresh is stale; no files were written",
                *(f"changed while refreshing: {path}" for path in conflicts),
            ]
        )


def _snapshot_pin_dependencies(
    root: Path,
    edition_dir: Path,
    sources_dir: Path,
    release_state_path: Path,
) -> tuple[_InputFingerprint, ...]:
    paths = {
        root / "magazine.toml",
        release_state_path,
        *edition_dir.rglob("*.md"),
        *edition_dir.rglob("*.yaml"),
        *edition_dir.rglob("*.yml"),
        *edition_dir.rglob("*.json"),
        *sources_dir.glob("*/record.y*ml"),
        *sources_dir.glob("*/extracted.md"),
    }
    return tuple(
        _InputFingerprint(path, _file_sha256(path))
        for path in sorted(paths)
        if path.is_file() and not path.is_symlink()
    )


def _validate_edition_id(edition_id: str) -> None:
    if not isinstance(edition_id, str) or not _SAFE_EDITION_ID.fullmatch(edition_id):
        raise ValidationError(
            "Edition id must use lowercase letters, digits, and hyphens"
        )


def _safe_repo_path(root: Path, path: Path, *, label: str) -> Path:
    root = root.resolve()
    candidate = path if path.is_absolute() else root / path
    try:
        lexical = candidate.relative_to(root)
    except ValueError as exc:
        raise ValidationError(f"{label} escapes its configured root: {candidate}") from exc
    if ".." in lexical.parts:
        raise ValidationError(f"{label} escapes its configured root: {candidate}")
    current = root
    for part in lexical.parts:
        current = current / part
        if current.is_symlink():
            raise ValidationError(f"{label} cannot use symlink path component: {current}")
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ValidationError(f"{label} escapes its configured root: {candidate}")
    return resolved


def _reserve_backup(destination: Path) -> Path:
    descriptor, name = mkstemp(
        prefix=f".{destination.name}.",
        suffix=".rollback",
        dir=destination.parent,
    )
    os.close(descriptor)
    return Path(name)


def _stage_bytes(destination: Path, content: bytes) -> Path:
    descriptor, name = mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, destination.stat().st_mode)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)
