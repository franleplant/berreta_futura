"""Stage a language overlay: scaffold it, reconcile it, and say what's left.

An edition's translation overlay (``editions/<id>/translations/<lang>/``)
mirrors the English manifest one row per article, one key per localized prose
field, one hash pin per derivable fact -- and every English edit used to mean
reconstructing that mirror by hand.  ``stage_translation`` does the clerical
half of that work and refuses, loudly, to do the creative half:

* **A missing overlay is generated whole.**  Every structural row is mirrored
  from the English edition, every derivable pin is computed with the same
  canonical hashers validation uses, and every localized prose field is filled
  with its English text.  The English filler is a *placeholder*, never a
  translation, so the report names each one; nothing English can ship as
  Spanish silently.

* **An existing overlay is reconciled, not regenerated.**  New English
  articles, figures, and plates gain placeholder rows with correct pins; rows
  whose English counterpart vanished are removed -- with their localized prose
  quoted in the report, because deleting a translation someone wrote is a fact
  the author must see, not an implementation detail.  Overlay files are
  hand-authored, so edits are targeted line splices located through the YAML
  parser's own marks; the author's comments, ordering, and wrapping survive.
  Only brand-new files are generated whole.

* **Pins are refreshed through ``pin.refresh_pins``**, the one tool whose
  contract is "whatever validation expects, write that" -- never through a
  second hashing implementation.  Before refreshing, each recorded pin is
  compared against its recomputed value, and every mismatch becomes an
  advisory: a moved manuscript hash means that article needs re-translation, a
  moved caption or credit pin names the figure text to revisit.  When no pin
  disagrees the refresh is skipped entirely -- proven unnecessary by the same
  hashers it would have used.

* **Nothing outside ``translations/<language>/`` is touched.**  The staging
  writes are confined to the overlay directory by construction, and the pin
  refresh is scoped the same way (``refresh_pins``'s ``within``), so a
  fidelity ledger or sibling language is never read for rewriting, never
  required to be refreshable, and never written.  Their staleness is still
  the author's to know: it is recomputed read-only and reported as a note on
  every run, whether or not this overlay needed anything itself.  Review
  records are never staging's to write.

Running the stage twice changes nothing the second time: a staged overlay is
already mirrored, already pinned, and the remaining work -- translation -- is
exactly what the report lists.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .errors import ValidationError
from .extraction import ledger_source_ids, load_extraction
from .io import load_structured
from .manifest import (
    Article,
    Edition,
    _edition_copy_sha256,
    _sha256,
    load_edition,
    load_translation,
)
from .media_schema import caption_sha256, credit_sha256
from .pin import PinChange, refresh_pins
from .records import load_records

# The four cover fields the translation gate demands whenever the base cover
# carries them; see manifest.load_translation.
_COVER_COPY_KEYS = ("headline", "deck", "edition_label", "back_text")


@dataclass(frozen=True)
class UntranslatedField:
    """One localized field still carrying its English text.

    ``path`` is the overlay file the English text lives in (the overlay
    manifest for copy fields, the translated manuscript itself when the whole
    file is an English copy), ``pointer`` locates the field the way pin
    reports do (``articles[the-id].title``), and ``english`` quotes the text
    so the translator can work from the report alone.
    """

    path: Path
    pointer: str
    english: str


@dataclass(frozen=True)
class DroppedContent:
    """Localized prose removed because its English counterpart is gone.

    ``content`` is the parsed YAML fragment exactly as the overlay carried it
    -- the report is the only place this translation work survives, so it is
    quoted whole rather than summarized.
    """

    pointer: str
    content: Any
    note: str = ""


@dataclass(frozen=True)
class Advisory:
    """A judgment call the stage cannot make: likely re-translation work."""

    pointer: str
    reason: str


@dataclass(frozen=True)
class StageReport:
    """Everything one staging run did, and everything it left for a human.

    ``placeholders`` is the untranslated backlog (English text standing in),
    ``dropped`` is removed localized prose quoted in full, ``advisories`` are
    inferred re-translation needs, ``pin_changes`` are the digests
    ``pin.refresh_pins`` moved inside this overlay, and
    ``validation_errors`` is whatever the structural translation gate still
    rejects after staging -- honestly reported rather than papered over.
    """

    edition_id: str
    language: str
    created: tuple[Path, ...] = ()
    updated: tuple[Path, ...] = ()
    placeholders: tuple[UntranslatedField, ...] = ()
    dropped: tuple[DroppedContent, ...] = ()
    advisories: tuple[Advisory, ...] = ()
    pin_changes: tuple[PinChange, ...] = ()
    validation_errors: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        """Whether this run wrote anything; a second run must report False."""
        return bool(self.created or self.updated or self.pin_changes)


def stage_translation(root: Path, edition_id: str, language: str) -> StageReport:
    """Generate or reconcile one language overlay against the English edition.

    A missing overlay is scaffolded whole -- structure mirrored, pins
    computed, prose filled with reported English placeholders.  An existing
    overlay is reconciled: placeholder rows added for new English articles,
    figures, and plates; rows without an English counterpart removed with
    their localized prose quoted in the report; stale pins refreshed through
    ``pin.refresh_pins`` with a re-translation advisory for each one.

    Writes only inside ``editions/<id>/translations/<language>/`` and never
    overwrites a file that already exists there -- an existing manuscript may
    be someone's translation.  Raises ``ValidationError`` when the base
    edition cannot be loaded, when ``language`` *is* the base language, or
    when the overlay is spelled in a way the reconciler cannot edit safely;
    every raise rolls this run's writes back, leaving the tree as it found it.
    """
    root = root.resolve()
    config = _load_config(root)
    records = {record.id: record for record in load_records(root / config["sources"])}
    base = load_edition(
        root,
        edition_id,
        set(records),
        publication_name=config["publication_name"],
        source_records=records,
    )
    if language == base.language:
        raise ValidationError(
            f"Refusing to stage {language!r}: it is the base edition's own language, "
            "and an overlay of the base would shadow the original"
        )
    edition_dir = root / config["editions"] / edition_id
    overlay_dir = edition_dir / "translations" / language
    overlay_path = overlay_dir / "edition.yaml"

    writer = _OverlayWriter(overlay_dir)
    notes: list[str] = []
    try:
        if overlay_path.is_file():
            dropped, advisories = _reconcile(
                root, edition_dir, overlay_dir, base, language, writer, notes
            )
            # Advisories are computed with the refresher's own hashers, so an
            # empty list is proof the refresh would leave this overlay alone
            # -- it is skipped rather than run to discover nothing.
            pin_changes = (
                _refresh_overlay_pins(root, edition_id, overlay_dir)
                if advisories
                else ()
            )
        else:
            _generate_skeleton(root, edition_dir, overlay_dir, base, language, writer, notes)
            dropped, advisories, pin_changes = [], [], ()
    except Exception:
        writer.rollback()
        raise

    placeholders = _untranslated_fields(root, base, overlay_dir)
    validation_errors = _structural_validation(root, base, language)
    # Out-of-scope staleness is state, not an event: it is recomputed
    # read-only and reported on every run, not only when this overlay
    # happened to need a refresh of its own.
    notes.extend(
        _out_of_scope_notes(root / config["sources"], base, edition_dir, overlay_dir)
    )
    if language not in config["languages"]:
        notes.append(
            f"Language {language!r} is not in publication.languages in magazine.toml, "
            "so `mag validate` will not enforce this overlay until it is added"
        )
    updated = tuple(
        dict.fromkeys(list(writer.updated) + [change.path for change in pin_changes])
    )
    return StageReport(
        edition_id,
        language,
        created=tuple(writer.created),
        updated=updated,
        placeholders=tuple(placeholders),
        dropped=tuple(dropped),
        advisories=tuple(advisories),
        pin_changes=pin_changes,
        validation_errors=validation_errors,
        notes=tuple(notes),
    )


def _load_config(root: Path) -> dict[str, Any]:
    """The facts ``magazine.toml`` contributes, with the compiler's defaults.

    Read directly (as ``pin.py`` does) so the stage stays importable on its
    own; the defaults restate the compiler's.
    """
    config_path = root / "magazine.toml"
    data = tomllib.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    paths = data.get("paths", {})
    publication = data.get("publication", {})
    primary = str(publication.get("language") or "en").strip()
    languages = publication.get("languages") or [primary]
    return {
        "publication_name": str(publication.get("name") or "Magazine").strip(),
        "sources": str(paths.get("sources", "library/sources")),
        "editions": str(paths.get("editions", "editions")),
        "languages": tuple(str(item).strip() for item in languages),
    }


# ---------------------------------------------------------------------------
# Writing: everything reaches disk through one guard.


class _OverlayWriter:
    """All disk writes, confined to the overlay directory and reversible.

    The guard is structural rather than disciplinary: a path outside
    ``translations/<language>/`` (or under any ``reviews/``) raises before
    anything happens, existing files are never overwritten (a file that is
    already there may be someone's translation), and every write is snapshot
    so a raise later in the run can put the tree back exactly.
    """

    def __init__(self, overlay_dir: Path):
        self.overlay_dir = overlay_dir.resolve()
        self.created: list[Path] = []
        self.updated: list[Path] = []
        self._before: dict[Path, bytes | None] = {}

    def write(self, path: Path, content: bytes, *, overwrite: bool = False) -> bool:
        """Write ``content``; returns False when an existing file was kept."""
        path = self._guarded(path)
        if path.is_file():
            if not overwrite:
                return False
            if path.read_bytes() == content:
                return True
        self._before.setdefault(path, path.read_bytes() if path.is_file() else None)
        existed = path.is_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        (self.updated if existed else self.created).append(path)
        return True

    def rollback(self) -> None:
        for path, before in self._before.items():
            if before is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(before)
        self.created.clear()
        self.updated.clear()

    def _guarded(self, path: Path) -> Path:
        path = path if path.is_absolute() else self.overlay_dir / path
        resolved = path.parent.resolve() / path.name if not path.exists() else path.resolve()
        if not resolved.is_relative_to(self.overlay_dir):
            raise ValidationError(
                f"Refusing to write outside the overlay directory: {resolved}"
            )
        if "reviews" in resolved.relative_to(self.overlay_dir).parts:
            raise ValidationError(
                f"Refusing to write under a reviews directory: {resolved}"
            )
        return resolved


# ---------------------------------------------------------------------------
# Skeleton: a brand-new overlay, generated whole.


def _generate_skeleton(
    root: Path,
    edition_dir: Path,
    overlay_dir: Path,
    base: Edition,
    language: str,
    writer: _OverlayWriter,
    notes: list[str],
) -> None:
    """Write the full overlay: mirrored structure, computed pins, English prose."""
    data: dict[str, Any] = {
        "schema_version": 1,
        "language": language,
        "source_language": base.language,
        "locale": language,
        "base_copy_sha256": _edition_copy_sha256(base),
        "title": base.title,
    }
    subtitle = str(base.raw.get("subtitle") or "")
    if subtitle:
        data["subtitle"] = subtitle
    cover = {key: base.cover[key] for key in _COVER_COPY_KEYS if base.cover.get(key)}
    if cover:
        data["cover"] = cover
    if base.closing_plates:
        data["closing_plate_titles"] = [plate.title for plate in base.closing_plates]
    if base.editorial:
        rel = _mirrored_rel(edition_dir, base.editorial.path)
        _copy_placeholder(base.editorial.path, overlay_dir / rel, writer, notes)
        data["editorial"] = {
            "path": rel,
            "source_sha256": _sha256(base.editorial.path),
        }
    data["articles"] = [
        _article_row(edition_dir, overlay_dir, article, writer, notes)
        for article in base.articles
    ]
    data["sections"] = [
        _section_row(edition_dir, overlay_dir, section, writer, notes)
        for section in base.sections
    ]
    writer.write(overlay_dir / "edition.yaml", _dump(data).encode("utf-8"))


def _article_row(
    edition_dir: Path,
    overlay_dir: Path,
    article: Article,
    writer: _OverlayWriter,
    notes: list[str],
) -> dict[str, Any]:
    """One placeholder article row: English prose, correct pins, copied file."""
    rel = _mirrored_rel(edition_dir, article.manuscript, prefix="articles")
    _copy_placeholder(article.manuscript, overlay_dir / rel, writer, notes)
    row: dict[str, Any] = {
        "id": article.id,
        "title": article.title,
        "short_title": article.short_title,
    }
    if article.display_emphasis:
        row["display_emphasis"] = article.display_emphasis
    row["author_note"] = article.author_note
    row["manuscript"] = rel
    row["source_sha256"] = _sha256(article.manuscript)
    if article.figures:
        row["figures"] = [_figure_row(figure) for figure in article.figures]
    return row


def _figure_row(figure) -> dict[str, Any]:
    return {
        "id": figure.id,
        "caption": figure.caption,
        "credit": figure.credit,
        "alt_text": figure.alt_text,
        # The English anchor matches the copied English manuscript's headings,
        # so the skeleton validates; translating the manuscript means
        # translating the anchor with it, which the placeholder report flags.
        "anchor": figure.anchor,
        "source_caption_sha256": caption_sha256(figure.id, figure.caption),
        "source_credit_sha256": credit_sha256(figure.id, figure.credit),
    }


def _section_row(
    edition_dir: Path,
    overlay_dir: Path,
    section,
    writer: _OverlayWriter,
    notes: list[str],
) -> dict[str, Any]:
    rel = _mirrored_rel(edition_dir, section.path, prefix="sections")
    _copy_placeholder(section.path, overlay_dir / rel, writer, notes)
    return {
        "kind": section.kind,
        "title": section.title,
        "path": rel,
        "source_sha256": _sha256(section.path),
    }


def _copy_placeholder(
    source: Path, target: Path, writer: _OverlayWriter, notes: list[str]
) -> None:
    """A structure-valid placeholder: the English file, byte for byte.

    An existing target is kept untouched -- it may be a translation already in
    progress -- and noted, because the pins staged around it assume the
    *current* English source and the keeper should verify the survivor.
    """
    if not writer.write(target, source.read_bytes()):
        notes.append(
            f"Kept the existing file {target}: it may already be a translation; "
            f"verify it against {source}"
        )


def _ensure_file(source: Path, target: Path, writer: _OverlayWriter) -> None:
    """Restore a declared file that is missing; an existing one is the point.

    Used for rows that were already in the overlay: their file being present
    (and translated) is the expected state and merits no note, but a dangling
    declaration is repaired with an English placeholder so the overlay loads.
    A target that resolves outside the overlay is left to validation to name.
    """
    try:
        if not target.is_file():
            writer.write(target, source.read_bytes())
    except ValidationError:
        pass


def _mirrored_rel(edition_dir: Path, path: Path, *, prefix: str = "") -> str:
    """The overlay-relative spelling of a base file's path.

    Overlays mirror the base edition's layout (``articles/x.md`` under the
    overlay for ``articles/x.md`` under the edition); a base file living
    outside the edition directory has no mirror position, so it falls back to
    its bare name under ``prefix``.
    """
    try:
        return path.relative_to(edition_dir).as_posix()
    except ValueError:
        return f"{prefix}/{path.name}" if prefix else path.name


def _dump(data: dict[str, Any]) -> str:
    # The house dump: key order as authored, UTF-8 prose unescaped, wrapped at
    # the same width tools/assemble_edition_2.py established for overlays.
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110)


# ---------------------------------------------------------------------------
# Reconcile: targeted edits to a hand-authored overlay.


def _reconcile(
    root: Path,
    edition_dir: Path,
    overlay_dir: Path,
    base: Edition,
    language: str,
    writer: _OverlayWriter,
    notes: list[str],
) -> tuple[list[DroppedContent], list[Advisory]]:
    """Mirror the overlay to the current base, dropping nothing silently.

    Advisories are judged against the overlay *as found* -- a pin that
    disagrees with its recomputed value means the English moved underneath an
    existing translation -- and only then is the structure edited, so a row
    added by this very run can never be mistaken for stale work.
    """
    editor = _OverlayEditor(overlay_dir / "edition.yaml")
    advisories = _pin_advisories(base, editor.data)
    dropped: list[DroppedContent] = []

    _reconcile_cover(base, editor)
    _reconcile_closing_plates(base, editor, dropped)
    _reconcile_editorial(edition_dir, overlay_dir, base, editor, writer, notes, dropped)
    _reconcile_articles(edition_dir, overlay_dir, base, editor, writer, notes, dropped)
    _reconcile_sections(edition_dir, overlay_dir, base, editor, writer, notes, dropped)

    if editor.dirty:
        writer.write(editor.path, editor.text.encode("utf-8"), overwrite=True)
    return dropped, advisories


def _reconcile_cover(base: Edition, editor: _OverlayEditor) -> None:
    required = {key: base.cover[key] for key in _COVER_COPY_KEYS if base.cover.get(key)}
    if not required:
        return
    cover = editor.data.get("cover")
    if not isinstance(cover, dict):
        editor.set_key((), "cover", dict(required))
        return
    for key, english in required.items():
        if key not in cover:
            editor.set_key(("cover",), key, english)


def _reconcile_closing_plates(
    base: Edition, editor: _OverlayEditor, dropped: list[DroppedContent]
) -> None:
    # Plate titles are positional against the base plates, so the reconcile is
    # positional too: extend with English placeholders, trim from the end.
    expected = [plate.title for plate in base.closing_plates]
    titles = editor.data.get("closing_plate_titles")
    if not expected:
        if titles is not None:
            dropped.append(
                DroppedContent("closing_plate_titles", titles, "base edition has no closing plates")
            )
            editor.delete_key((), "closing_plate_titles")
        return
    if not isinstance(titles, list):
        editor.set_key((), "closing_plate_titles", list(expected))
        return
    for index in range(len(titles), len(expected)):
        editor.insert_item((), "closing_plate_titles", index, expected[index])
    while len(editor.data["closing_plate_titles"]) > len(expected):
        index = len(editor.data["closing_plate_titles"]) - 1
        dropped.append(
            DroppedContent(
                f"closing_plate_titles[{index + 1}]",
                editor.data["closing_plate_titles"][index],
                "base edition no longer has this plate",
            )
        )
        editor.delete_item((), "closing_plate_titles", index)


def _reconcile_editorial(
    edition_dir: Path,
    overlay_dir: Path,
    base: Edition,
    editor: _OverlayEditor,
    writer: _OverlayWriter,
    notes: list[str],
    dropped: list[DroppedContent],
) -> None:
    row = editor.data.get("editorial")
    if base.editorial is None:
        if row is not None:
            dropped.append(
                DroppedContent(
                    "editorial",
                    row,
                    "base edition has no editorial; the translated file, if any, was left on disk",
                )
            )
            editor.delete_key((), "editorial")
        return
    expected = _sha256(base.editorial.path)
    if not isinstance(row, dict):
        rel = _mirrored_rel(edition_dir, base.editorial.path)
        _copy_placeholder(base.editorial.path, overlay_dir / rel, writer, notes)
        editor.set_key((), "editorial", {"path": rel, "source_sha256": expected})
        return
    if not row.get("path"):
        editor.set_key(("editorial",), "path", _mirrored_rel(edition_dir, base.editorial.path))
    target = overlay_dir / str(editor.data["editorial"]["path"])
    _ensure_file(base.editorial.path, target, writer)
    if "source_sha256" not in row:
        editor.set_key(("editorial",), "source_sha256", expected)


def _reconcile_articles(
    edition_dir: Path,
    overlay_dir: Path,
    base: Edition,
    editor: _OverlayEditor,
    writer: _OverlayWriter,
    notes: list[str],
    dropped: list[DroppedContent],
) -> None:
    rows = editor.data.get("articles")
    if not isinstance(rows, list):
        editor.set_key(
            (),
            "articles",
            [
                _article_row(edition_dir, overlay_dir, article, writer, notes)
                for article in base.articles
            ],
        )
        return
    base_by_id = {article.id: article for article in base.articles}
    # Additions before removals, so a full turnover of articles never leaves
    # the list empty mid-edit.
    present = {str(row.get("id")) for row in rows if isinstance(row, dict)}
    for article in base.articles:
        if article.id not in present:
            editor.insert_item(
                (),
                "articles",
                len(editor.data["articles"]),
                _article_row(edition_dir, overlay_dir, article, writer, notes),
            )
    for row_id in [
        str(row.get("id"))
        for row in list(editor.data["articles"])
        if isinstance(row, dict) and str(row.get("id")) not in base_by_id
    ]:
        index = next(
            i
            for i, row in enumerate(editor.data["articles"])
            if isinstance(row, dict) and str(row.get("id")) == row_id
        )
        dropped.append(
            DroppedContent(
                f"articles[{row_id}]",
                editor.data["articles"][index],
                "base edition no longer has this article; its translated manuscript, "
                "if any, was left on disk",
            )
        )
        if len(editor.data["articles"]) == 1:
            editor.replace_with_empty_list((), "articles")
        else:
            editor.delete_item((), "articles", index)
    for index, row in enumerate(editor.data["articles"]):
        if not isinstance(row, dict):
            continue
        article = base_by_id.get(str(row.get("id")))
        if article is None:
            continue
        _repair_article_row(
            edition_dir, overlay_dir, article, editor, index, writer, notes
        )
        _reconcile_figures(article, editor, index, dropped)


def _repair_article_row(
    edition_dir: Path,
    overlay_dir: Path,
    article: Article,
    editor: _OverlayEditor,
    index: int,
    writer: _OverlayWriter,
    notes: list[str],
) -> None:
    """Add the keys an existing row is missing; never rewrite ones it has.

    Prose keys get English placeholders (reported by the placeholder scan);
    the pin key gets the correct digest outright, because a missing pin is a
    key ``refresh_pins`` refuses to insert.
    """
    row = editor.data["articles"][index]
    path = ("articles", index)
    placeholders = {
        "title": article.title,
        "short_title": article.short_title,
        "author_note": article.author_note,
    }
    for key, english in placeholders.items():
        if not row.get(key):
            editor.set_key(path, key, english)
    if not row.get("manuscript"):
        editor.set_key(
            path,
            "manuscript",
            _mirrored_rel(edition_dir, article.manuscript, prefix="articles"),
        )
    _ensure_file(
        article.manuscript,
        overlay_dir / str(editor.data["articles"][index]["manuscript"]),
        writer,
    )
    if "source_sha256" not in row:
        editor.set_key(path, "source_sha256", _sha256(article.manuscript))


def _reconcile_figures(
    article: Article,
    editor: _OverlayEditor,
    index: int,
    dropped: list[DroppedContent],
) -> None:
    row = editor.data["articles"][index]
    path = ("articles", index)
    if not article.figures:
        if row.get("figures"):
            dropped.append(
                DroppedContent(
                    f"articles[{article.id}].figures",
                    row["figures"],
                    "base article no longer has figures",
                )
            )
            editor.delete_key(path, "figures")
        return
    if not isinstance(row.get("figures"), list) or not row["figures"]:
        if "figures" in row:
            editor.delete_key(path, "figures")
        editor.set_key(path, "figures", [_figure_row(figure) for figure in article.figures])
        return
    base_ids = {figure.id for figure in article.figures}
    present = {
        str(item.get("id")) for item in row["figures"] if isinstance(item, dict)
    }
    for figure in article.figures:
        if figure.id not in present:
            editor.insert_item(
                path, "figures", len(editor.data["articles"][index]["figures"]), _figure_row(figure)
            )
    for figure_id in [
        str(item.get("id"))
        for item in list(editor.data["articles"][index]["figures"])
        if isinstance(item, dict) and str(item.get("id")) not in base_ids
    ]:
        figures = editor.data["articles"][index]["figures"]
        item_index = next(
            i
            for i, item in enumerate(figures)
            if isinstance(item, dict) and str(item.get("id")) == figure_id
        )
        dropped.append(
            DroppedContent(
                f"articles[{article.id}].figures[{figure_id}]",
                figures[item_index],
                "base article no longer selects this figure",
            )
        )
        editor.delete_item(path, "figures", item_index)
    # An existing row missing its pin keys is repaired the way an article
    # row's source_sha256 is: a missing pin is a key ``refresh_pins`` refuses
    # to insert, so reconcile writes the correct digest outright.  Prose keys
    # are the translator's and are left exactly as found.
    base_by_id = {figure.id: figure for figure in article.figures}
    for item_index, item in enumerate(editor.data["articles"][index]["figures"]):
        if not isinstance(item, dict):
            continue
        figure = base_by_id.get(str(item.get("id")))
        if figure is None:
            continue
        pins = {
            "source_caption_sha256": caption_sha256(figure.id, figure.caption),
            "source_credit_sha256": credit_sha256(figure.id, figure.credit),
        }
        for key, digest in pins.items():
            if key not in item:
                editor.set_key(path + ("figures", item_index), key, digest)


def _reconcile_sections(
    edition_dir: Path,
    overlay_dir: Path,
    base: Edition,
    editor: _OverlayEditor,
    writer: _OverlayWriter,
    notes: list[str],
    dropped: list[DroppedContent],
) -> None:
    # Sections are positional and must preserve the base kinds in order; a row
    # at the wrong kind is replaced whole (its prose quoted), extra rows are
    # trimmed from the end, and missing rows appended as placeholders.
    rows = editor.data.get("sections")
    if not isinstance(rows, list):
        editor.set_key(
            (),
            "sections",
            [
                _section_row(edition_dir, overlay_dir, section, writer, notes)
                for section in base.sections
            ],
        )
        return
    for index, section in enumerate(base.sections):
        current = editor.data["sections"]
        if index < len(current):
            row = current[index]
            if isinstance(row, dict) and row.get("kind") == section.kind:
                continue
            # Replace in two moves -- insert the placeholder, then delete the
            # displaced row -- so the list is never emptied mid-edit.
            dropped.append(
                DroppedContent(
                    f"sections[{index + 1}]",
                    row,
                    f"base section {index + 1} is now kind {section.kind!r}",
                )
            )
            editor.insert_item(
                (), "sections", index,
                _section_row(edition_dir, overlay_dir, section, writer, notes),
            )
            editor.delete_item((), "sections", index + 1)
            continue
        editor.insert_item(
            (), "sections", index, _section_row(edition_dir, overlay_dir, section, writer, notes)
        )
    while len(editor.data["sections"]) > len(base.sections):
        index = len(editor.data["sections"]) - 1
        dropped.append(
            DroppedContent(
                f"sections[{index + 1}]",
                editor.data["sections"][index],
                "base edition no longer has this section",
            )
        )
        if len(editor.data["sections"]) == 1:
            editor.replace_with_empty_list((), "sections")
        else:
            editor.delete_item((), "sections", index)


# ---------------------------------------------------------------------------
# Advisories and the guarded pin refresh.


def _pin_advisories(base: Edition, overlay: dict[str, Any]) -> list[Advisory]:
    """Every recorded pin that disagrees with its recomputed value.

    Computed with the same canonical hashers ``refresh_pins`` uses, so "no
    advisories" *is* the proof that a refresh would leave this overlay alone.
    A disagreeing pin means the English moved under an existing translation;
    the advisory names the localized text to revisit.
    """
    advisories: list[Advisory] = []
    if overlay.get("base_copy_sha256") != _edition_copy_sha256(base):
        advisories.append(
            Advisory(
                "base_copy_sha256",
                "the base edition's display copy changed; review the localized title, "
                "subtitle, cover copy, author notes, and closing plate titles",
            )
        )
    editorial_row = overlay.get("editorial")
    if (
        base.editorial
        and isinstance(editorial_row, dict)
        and editorial_row.get("source_sha256") != _sha256(base.editorial.path)
    ):
        advisories.append(
            Advisory(
                "editorial",
                f"the English editorial {base.editorial.path.name} changed; "
                "re-translate the localized editorial",
            )
        )
    rows_by_id = {
        str(row.get("id")): row
        for row in overlay.get("articles") or []
        if isinstance(row, dict) and row.get("id")
    }
    for article in base.articles:
        row = rows_by_id.get(article.id)
        if row is None:
            continue
        if row.get("source_sha256") != _sha256(article.manuscript):
            advisories.append(
                Advisory(
                    f"articles[{article.id}].manuscript",
                    f"the English manuscript {article.manuscript.name} changed; "
                    "re-translate the localized manuscript against it",
                )
            )
        figure_rows = {
            str(item.get("id")): item
            for item in row.get("figures") or []
            if isinstance(item, dict) and item.get("id")
        }
        for figure in article.figures:
            item = figure_rows.get(figure.id)
            if item is None:
                continue
            if item.get("source_caption_sha256") != caption_sha256(figure.id, figure.caption):
                advisories.append(
                    Advisory(
                        f"articles[{article.id}].figures[{figure.id}].caption",
                        "the English caption changed; re-translate the localized caption",
                    )
                )
            if item.get("source_credit_sha256") != credit_sha256(figure.id, figure.credit):
                advisories.append(
                    Advisory(
                        f"articles[{article.id}].figures[{figure.id}].credit",
                        "the English credit changed; re-translate the localized credit",
                    )
                )
    section_rows = overlay.get("sections") or []
    for index, section in enumerate(base.sections):
        row = section_rows[index] if index < len(section_rows) else None
        if isinstance(row, dict) and row.get("source_sha256") != _sha256(section.path):
            advisories.append(
                Advisory(
                    f"sections[{index + 1}]",
                    f"the English section {section.path.name} changed; re-translate it",
                )
            )
    return advisories


def _refresh_overlay_pins(
    root: Path, edition_id: str, overlay_dir: Path
) -> tuple[PinChange, ...]:
    """Refresh this overlay's pins via ``pin.refresh_pins`` -- and only this one's.

    The refresher is handed the overlay directory as its ``within`` scope, so
    a fidelity ledger or sibling language is never read for rewriting, never
    required to be refreshable, and never written; that is what lets two
    half-staged languages be staged one at a time instead of deadlocking on
    each other's missing rows.  The refresher's verify-then-write contract
    means its own raises wrote nothing, but the write itself belongs to the
    operating system: an I/O fault mid-write could leave the one in-scope
    file partial.  So the manifest is snapshot here and put back on *any*
    raise before it propagates -- the caller then rolls back this run's
    structural writes and the tree is as found.
    """
    manifest_path = overlay_dir / "edition.yaml"
    before = manifest_path.read_bytes()
    try:
        report = refresh_pins(root, edition_id, within=(overlay_dir,))
    except BaseException:
        if manifest_path.read_bytes() != before:
            manifest_path.write_bytes(before)
        raise
    return report.changes


def _out_of_scope_notes(
    sources_dir: Path, base: Edition, edition_dir: Path, overlay_dir: Path
) -> list[str]:
    """Name every stale pin the stage saw but must not fix.

    Staging's writes stop at the overlay boundary, so a stale fidelity
    ledger or sibling overlay is never rewritten here -- but silence would
    let it rot.  Each out-of-scope pin is recomputed with the same canonical
    hashers the refresher uses and compared purely in memory; every
    disagreement becomes a note pointing at the tool allowed to fix it.
    """
    notes: list[str] = []
    overlay_dir = overlay_dir.resolve()
    for article in base.articles:
        notes.extend(_stale_ledger_pins(sources_dir, article))
    for sibling in sorted((edition_dir / "translations").glob("*/edition.yaml")):
        if sibling.resolve().is_relative_to(overlay_dir):
            continue
        notes.extend(_stale_sibling_pins(base, sibling))
    return notes


def _stale_ledger_pins(sources_dir: Path, article: Article) -> list[str]:
    """One ledger's disagreeing body pins, judged without writing anything.

    A ledger without the pin key (the released-edition shape) and a source
    without a committed extraction both have nothing to compare, and a
    malformed ledger or extraction is validation's to reject; none of them
    may turn a staging run into a raise, so every unanswerable case here
    simply yields no note.
    """
    try:
        data = load_structured(article.fidelity)
        source_ids = ledger_source_ids(article.fidelity, data)
    except ValidationError:
        return []
    declared = data.get("source_body_sha256")
    if isinstance(declared, str) and len(source_ids) == 1:
        declared = {source_ids[0]: declared}
    if not isinstance(declared, dict):
        return []
    notes: list[str] = []
    for source_id in source_ids:
        pin = declared.get(source_id)
        if not isinstance(pin, str):
            continue
        try:
            extraction = load_extraction(sources_dir, source_id)
        except ValidationError:
            continue
        if extraction is not None and pin != extraction.body_sha256:
            notes.append(
                f"Out of scope, left stale: {article.fidelity} "
                f"source_body_sha256[{source_id}] no longer matches the committed "
                "extraction; staging touches only its own language -- run "
                "`mag pin` to repair it"
            )
    return notes


def _stale_sibling_pins(base: Edition, overlay_path: Path) -> list[str]:
    """A sibling overlay's stale pins and missing rows, judged read-only.

    Stale pins reuse the advisory scan (the refresher's own hashers); a
    missing article row is named too, because it is the very state that used
    to deadlock the edition-wide refresh and its cure is staging *that*
    language, not this one.
    """
    language = overlay_path.parent.name
    try:
        data = yaml.safe_load(overlay_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(data, dict):
        return []
    notes = [
        f"Out of scope, left stale: {overlay_path} {advisory.pointer} -- "
        f"stage {language!r} to repair its pins and see its backlog"
        for advisory in _pin_advisories(base, data)
    ]
    present = {
        str(row.get("id"))
        for row in data.get("articles") or []
        if isinstance(row, dict)
    }
    notes.extend(
        f"Out of scope, missing: {overlay_path} has no row for article "
        f"{article.id} -- stage {language!r} to scaffold it"
        for article in base.articles
        if article.id not in present
    )
    return notes


# ---------------------------------------------------------------------------
# The report's backlog: what still reads as English.


def _untranslated_fields(
    root: Path, base: Edition, overlay_dir: Path
) -> list[UntranslatedField]:
    """Every localized field whose text equals its English counterpart.

    Equality is the placeholder test: staging fills prose with English, so
    English-equal text is untranslated until proven otherwise.  A proper name
    that legitimately survives translation will be flagged too -- the report
    is a checklist for a human, and a false "check this" is cheap where a
    silent English page in a Spanish edition is not.  A *missing* optional
    field (title, subtitle) is flagged the same way: display falls back to the
    English, which is exactly the outcome this report exists to surface.
    """
    overlay_path = overlay_dir / "edition.yaml"
    data = yaml.safe_load(overlay_path.read_text(encoding="utf-8")) or {}
    found: list[UntranslatedField] = []

    def flag(path: Path, pointer: str, english: str) -> None:
        found.append(UntranslatedField(path, pointer, english))

    if not data.get("title") or data.get("title") == base.title:
        flag(overlay_path, "title", base.title)
    subtitle = str(base.raw.get("subtitle") or "")
    if subtitle and str(data.get("subtitle") or "") in ("", subtitle):
        flag(overlay_path, "subtitle", subtitle)
    cover = data.get("cover") if isinstance(data.get("cover"), dict) else {}
    for key in _COVER_COPY_KEYS:
        english = base.cover.get(key)
        if english and cover.get(key) == english:
            flag(overlay_path, f"cover.{key}", english)
    titles = data.get("closing_plate_titles") or []
    for index, plate in enumerate(base.closing_plates):
        if index < len(titles) and titles[index] == plate.title:
            flag(overlay_path, f"closing_plate_titles[{index + 1}]", plate.title)
    if base.editorial and isinstance(data.get("editorial"), dict):
        path = overlay_dir / str(data["editorial"].get("path") or "")
        if path.is_file() and path.read_bytes() == base.editorial.path.read_bytes():
            flag(path, "editorial.manuscript", f"(untranslated copy of {base.editorial.path.name})")
    rows_by_id = {
        str(row.get("id")): row
        for row in data.get("articles") or []
        if isinstance(row, dict) and row.get("id")
    }
    for article in base.articles:
        row = rows_by_id.get(article.id)
        if row is None:
            continue
        pointer = f"articles[{article.id}]"
        for key, english in (
            ("title", article.title),
            ("short_title", article.short_title),
            ("author_note", article.author_note),
        ):
            if row.get(key) == english:
                flag(overlay_path, f"{pointer}.{key}", english)
        if article.display_emphasis and row.get("display_emphasis") == article.display_emphasis:
            flag(overlay_path, f"{pointer}.display_emphasis", article.display_emphasis)
        manuscript = overlay_dir / str(row.get("manuscript") or "")
        if manuscript.is_file() and manuscript.read_bytes() == article.manuscript.read_bytes():
            flag(
                manuscript,
                f"{pointer}.manuscript",
                f"(untranslated copy of {article.manuscript.name})",
            )
        figure_rows = {
            str(item.get("id")): item
            for item in row.get("figures") or []
            if isinstance(item, dict) and item.get("id")
        }
        for figure in article.figures:
            item = figure_rows.get(figure.id)
            if item is None:
                continue
            figure_pointer = f"{pointer}.figures[{figure.id}]"
            for key, english in (
                ("caption", figure.caption),
                ("credit", figure.credit),
                ("alt_text", figure.alt_text),
            ):
                if item.get(key) == english:
                    flag(overlay_path, f"{figure_pointer}.{key}", english)
            if figure.anchor != "__opener__" and item.get("anchor") == figure.anchor:
                flag(overlay_path, f"{figure_pointer}.anchor", figure.anchor)
    section_rows = data.get("sections") or []
    for index, section in enumerate(base.sections):
        if index >= len(section_rows) or not isinstance(section_rows[index], dict):
            continue
        row = section_rows[index]
        if row.get("title") == section.title:
            flag(overlay_path, f"sections[{index + 1}].title", section.title)
        path = overlay_dir / str(row.get("path") or "")
        if path.is_file() and path.read_bytes() == section.path.read_bytes():
            flag(path, f"sections[{index + 1}].manuscript", f"(untranslated copy of {section.path.name})")
    return found


def _structural_validation(root: Path, base: Edition, language: str) -> tuple[str, ...]:
    """What the translation gate still rejects, reported instead of raised.

    Staging's promise is a structurally valid overlay, but some failures are
    honest leftovers (an orphaned manuscript kept instead of overwritten, an
    anchor awaiting its translated heading); the report states them and the
    stage still counts as done -- fixing prose is the translator's move.
    """
    try:
        load_translation(root, base, language)
    except ValidationError as exc:
        return tuple(exc.errors)
    return ()


# ---------------------------------------------------------------------------
# The textual editor: splices located by the parser's own marks.


class _OverlayEditor:
    """Targeted line edits to a hand-authored overlay manifest.

    The file is held as text; every operation recomposes it with the YAML
    parser and uses the resulting node marks -- the parser's own line numbers
    -- to splice whole lines, so the author's comments, key order, quoting,
    and wrapping survive everywhere an edit does not land.  A parallel parsed
    copy (``data``) receives the same mutation, and after every splice the
    text is re-parsed and compared against it: any disagreement raises before
    the file is ever written, mirroring ``pin.py``'s fail-closed stance.
    """

    def __init__(self, path: Path):
        self.path = path
        self.text = path.read_text(encoding="utf-8")
        if not self.text.endswith("\n"):
            self.text += "\n"
        data = yaml.safe_load(self.text)
        if not isinstance(data, dict):
            raise ValidationError(f"{path} must contain a mapping")
        self.data: dict[str, Any] = data
        self.dirty = False

    # -- operations ---------------------------------------------------------

    def set_key(self, path: tuple, key: str, value: Any) -> None:
        """Append ``key: value`` to the mapping at ``path``; key must be new."""
        container = self._container(path)
        if key in container:
            if container[key] is None:
                # A bare `key:` line parses as null, so to the reconciler the
                # key both exists (cannot be inserted) and carries nothing
                # (cannot be kept).  Naming that spelling is the whole fix;
                # "tried to insert but it exists" reads like an internal bug.
                raise ValidationError(
                    f"{self.path}: {key!r} at {path!r} is spelled with no value "
                    f"(a bare `{key}:` line); respell the empty key -- give it a "
                    "value or delete the line -- and stage again"
                )
            raise ValidationError(
                f"{self.path}: staging tried to insert {key!r} at {path!r} but it exists"
            )
        node = self._node_at(path)
        indent = node.start_mark.column if node.value else self._mapping_indent(path)
        line = _block_end(node)
        self._splice(line, line, _render({key: value}, indent))
        container[key] = value
        self._verify()

    def delete_key(self, path: tuple, key: str) -> None:
        node = self._node_at(path)
        entries = node.value
        for position, (key_node, _) in enumerate(entries):
            if key_node.value == key:
                start = key_node.start_mark.line
                if position + 1 < len(entries):
                    end = entries[position + 1][0].start_mark.line
                else:
                    end = _block_end(node)
                self._splice(start, end, [])
                del self._container(path)[key]
                self._verify()
                return
        raise ValidationError(f"{self.path}: no key {key!r} at {path!r} to delete")

    def insert_item(self, path: tuple, key: str, index: int, item: Any) -> None:
        """Insert ``item`` at ``index`` of the sequence under ``key``."""
        container = self._container(path)[key]
        node = self._node_at(path + (key,))
        if not node.value:
            # An empty list is spelled in flow style (`key: []`); growing it
            # means respelling the whole entry in block style.
            self._replace_entry(path, key, [item])
            container.append(item)
            self._verify()
            return
        dash_column = node.value[0].start_mark.column - 2
        if index < len(node.value):
            line = node.value[index].start_mark.line
        else:
            line = _block_end(node)
        self._splice(line, line, _render([item], dash_column))
        container.insert(index, item)
        self._verify()

    def delete_item(self, path: tuple, key: str, index: int) -> None:
        container = self._container(path)[key]
        if len(container) == 1:
            raise ValidationError(
                f"{self.path}: deleting the last item of {key!r} must respell the "
                "entry; use replace_with_empty_list"
            )
        node = self._node_at(path + (key,))
        start = node.value[index].start_mark.line
        if index + 1 < len(node.value):
            end = node.value[index + 1].start_mark.line
        else:
            end = _block_end(node)
        self._splice(start, end, [])
        del container[index]
        self._verify()

    def replace_with_empty_list(self, path: tuple, key: str) -> None:
        self._replace_entry(path, key, [])
        self._container(path)[key] = []
        self._verify()

    # -- mechanics ----------------------------------------------------------

    def _replace_entry(self, path: tuple, key: str, value: Any) -> None:
        node = self._node_at(path)
        entries = node.value
        for position, (key_node, _) in enumerate(entries):
            if key_node.value == key:
                start = key_node.start_mark.line
                if position + 1 < len(entries):
                    end = entries[position + 1][0].start_mark.line
                else:
                    end = _block_end(node)
                self._splice(start, end, _render({key: value}, key_node.start_mark.column))
                return
        raise ValidationError(f"{self.path}: no key {key!r} at {path!r} to respell")

    def _node_at(self, path: tuple):
        node = yaml.compose(self.text)
        for part in path:
            if isinstance(part, str):
                for key_node, value_node in node.value:
                    if key_node.value == part:
                        node = value_node
                        break
                else:
                    raise ValidationError(
                        f"{self.path}: cannot locate {part!r} along {path!r}"
                    )
            else:
                node = node.value[part]
        return node

    def _mapping_indent(self, path: tuple) -> int:
        # An empty mapping never occurs in these files; the indent of a
        # non-empty ancestor's keys is column 0 at the root and unknown
        # elsewhere, so only the root case is answered without a node.
        if not path:
            return 0
        raise ValidationError(
            f"{self.path}: cannot infer the indent of an empty mapping at {path!r}"
        )

    def _container(self, path: tuple):
        container: Any = self.data
        for part in path:
            container = container[part]
        return container

    def _splice(self, start: int, end: int, new_lines: list[str]) -> None:
        lines = self.text.splitlines(keepends=True)
        lines[start:end] = new_lines
        self.text = "".join(lines)
        self.dirty = True

    def _verify(self) -> None:
        try:
            parsed = yaml.safe_load(self.text)
        except yaml.YAMLError as exc:
            raise ValidationError(
                f"{self.path}: a staged edit produced text that no longer parses "
                f"({exc}); nothing was written"
            ) from exc
        if parsed != self.data:
            raise ValidationError(
                f"{self.path}: a staged edit did not parse back to the intended "
                "value -- the file is spelled in a way the stager cannot edit "
                "safely; nothing was written"
            )


def _block_end(node) -> int:
    """The first line after a node, from the parser's end mark.

    For block collections the end mark sits on the token that terminated the
    block -- the start of whatever comes next -- so its line *is* the first
    line after.  Scalars and flow collections end mid-line instead, so the
    first line after is the following one.
    """
    mark = node.end_mark
    return mark.line if mark.column == 0 else mark.line + 1


def _render(value: Any, indent: int) -> list[str]:
    """House-style YAML for ``value``, re-indented for its insertion point."""
    text = yaml.safe_dump(
        value, sort_keys=False, allow_unicode=True, width=110, default_flow_style=False
    )
    pad = " " * indent
    return [pad + line if line.strip() else line for line in text.splitlines(keepends=True)]
