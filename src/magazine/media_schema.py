"""Edition figure references, resolved directly against source media files.

A figure row in ``edition.yaml`` names the source it comes from and the image
file inside that source's directory:

.. code-block:: yaml

    figures:
    - id: campaign-timeline
      source_id: anatomy-of-a-frontier-lab-agent-intrusion-a-tech-8088c1df
      path: media/003.png
      caption: ...
      alt_text: ...
      anchor: From one pod to the network
      layout: evidence_band_prose

``path`` is relative to ``library/sources/<source_id>/``. Validation checks
that the file exists, the anchor names a real ``##`` heading in the
manuscript, and the layout is one the renderer knows.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ValidationError

FIGURE_LAYOUTS = {
    "evidence_band",
    "evidence_band_prose",
    "adaptive_band",
    "compact_band",
    "column_plate",
    "landscape_plate",
    "landscape_plate_after",
}


@dataclass(frozen=True)
class Figure:
    id: str
    source_id: str
    path: Path
    caption: str
    credit: str
    alt_text: str
    anchor: str
    layout: str


def resolve_figures(
    root: Path,
    *,
    article_id: str,
    article_source_ids: tuple[str, ...],
    manuscript: Path,
    rows: Any,
    allow_unanchored: bool = False,
) -> tuple[Figure, ...]:
    """Resolve an article's figure rows to files under ``library/sources``.

    ``allow_unanchored`` keeps a figure whose anchor names a heading the current
    manuscript does not carry. It exists only for the renderer adapter while it
    measures a supplied render manifest and reports a stranded anchor by name;
    every other caller leaves it false.
    """

    if rows in (None, []):
        return ()
    if not isinstance(rows, list):
        raise ValidationError(f"Article {article_id} figures must be a list")
    if len(rows) > 3:
        raise ValidationError(f"Article {article_id} selects {len(rows)} figures; maximum is 3")
    errors: list[str] = []
    figures: list[Figure] = []
    seen: set[str] = set()
    headings = semantic_headings(manuscript)
    for index, row in enumerate(rows):
        label = f"Article {article_id} figure {index + 1}"
        if not isinstance(row, dict):
            errors.append(f"{label} must be a mapping")
            continue
        figure_id = str(row.get("id") or "").strip()
        source_id = str(row.get("source_id") or "").strip()
        rel_path = str(row.get("path") or "").strip()
        caption = str(row.get("caption") or "").strip()
        credit = str(row.get("credit") or "").strip()
        alt_text = str(row.get("alt_text") or "").strip()
        anchor = str(row.get("anchor") or "").strip()
        layout = str(row.get("layout") or "").strip()
        missing = [
            name
            for name, value in (
                ("id", figure_id),
                ("source_id", source_id),
                ("path", rel_path),
                ("caption", caption),
                ("alt_text", alt_text),
                ("anchor", anchor),
                ("layout", layout),
            )
            if not value
        ]
        if missing:
            errors.append(f"{label} missing: {', '.join(missing)}")
            continue
        if figure_id in seen:
            errors.append(f"Article {article_id} has duplicate figure id: {figure_id}")
        seen.add(figure_id)
        if source_id not in article_source_ids:
            errors.append(f"{label} source_id must be one of the article source_ids")
        relative = PurePosixPath(rel_path)
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            errors.append(f"{label} has unsafe path: {rel_path!r}")
            continue
        if layout not in FIGURE_LAYOUTS:
            errors.append(f"{label} has invalid layout: {layout or '<missing>'}")
        if anchor != "__opener__" and anchor not in headings and not allow_unanchored:
            errors.append(f"{label} anchor does not match an article heading: {anchor!r}")
        path = root / "library" / "sources" / source_id / Path(*relative.parts)
        if not path.is_file():
            errors.append(f"{label} image file is missing: {path}")
            continue
        figures.append(
            Figure(figure_id, source_id, path, caption, credit, alt_text, anchor, layout)
        )
    if errors:
        raise ValidationError(errors)
    return tuple(figures)


def localize_figures(
    base: tuple[Figure, ...],
    rows: Any,
    *,
    article_id: str,
    manuscript: Path,
    language: str,
) -> tuple[Figure, ...]:
    """Overlay translated caption, credit, alt text, and anchor on base figures."""

    if not base:
        if rows not in (None, []):
            raise ValidationError(
                f"Translation {language!r} article {article_id} has figures absent from English"
            )
        return ()
    if not isinstance(rows, list):
        raise ValidationError(
            f"Translation {language!r} article {article_id} figures must be a list"
        )
    errors: list[str] = []
    by_id = {
        str(row.get("id")): row
        for row in rows
        if isinstance(row, dict) and row.get("id")
    }
    expected_ids = {figure.id for figure in base}
    if set(by_id) != expected_ids:
        missing = sorted(expected_ids - set(by_id))
        extra = sorted(set(by_id) - expected_ids)
        if missing:
            errors.append(
                f"Translation {language!r} article {article_id} is missing figures: {', '.join(missing)}"
            )
        if extra:
            errors.append(
                f"Translation {language!r} article {article_id} has unknown figures: {', '.join(extra)}"
            )
    headings = semantic_headings(manuscript)
    localized: list[Figure] = []
    for figure in base:
        row = by_id.get(figure.id)
        if not row:
            continue
        caption = str(row.get("caption") or "").strip()
        credit = str(row.get("credit") or "").strip() or figure.credit
        alt_text = str(row.get("alt_text") or "").strip()
        anchor = str(row.get("anchor") or "").strip()
        if not caption or not alt_text or not anchor:
            errors.append(
                f"Translation {language!r} figure {figure.id} requires caption, alt_text, and anchor"
            )
        if anchor != "__opener__" and anchor not in headings:
            errors.append(
                f"Translation {language!r} figure {figure.id} anchor does not match a translated heading"
            )
        localized.append(
            replace(figure, caption=caption, credit=credit, alt_text=alt_text, anchor=anchor)
        )
    if errors:
        raise ValidationError(errors)
    return tuple(localized)


EXTRACT_STYLES = {"code", "quote"}


@dataclass(frozen=True)
class Extract:
    """A verbatim run of source text the edition MUST print, as a panel.

    The figure pattern applied to text: the editor names the run in
    ``edition.yaml`` and the renderer places it beside the manuscript, pulled
    from the captured source at load time.  The writer is never asked for it,
    so the run cannot be misquoted -- ``text`` is byte-identical to the source
    by construction, located by ``begin``/``end`` markers that must each pin a
    single position.  ``text`` is never localized; a verbatim run has one
    language, its source's, exactly as a code block does.
    """

    id: str
    source_id: str
    text: str
    style: str
    caption: str
    anchor: str


def resolve_extracts(
    root: Path,
    *,
    article_id: str,
    article_source_ids: tuple[str, ...],
    manuscript: Path,
    rows: Any,
    allow_unanchored: bool = False,
) -> tuple[Extract, ...]:
    """Resolve an article's extract rows to verbatim runs of captured sources.

    Every check is a string check.  ``begin`` must occur exactly once in the
    source's ``article.md``; ``end`` must occur exactly once at or after it;
    the run is the contiguous span from ``begin`` through the end of ``end``.
    A run the manuscript already contains verbatim is an error, not a warning:
    the piece would print it twice, and the editor must drop one copy.
    """

    if rows in (None, []):
        return ()
    if not isinstance(rows, list):
        raise ValidationError(f"Article {article_id} extracts must be a list")
    if len(rows) > 2:
        raise ValidationError(f"Article {article_id} selects {len(rows)} extracts; maximum is 2")
    errors: list[str] = []
    extracts: list[Extract] = []
    seen: set[str] = set()
    manuscript_text = manuscript.read_text(encoding="utf-8")
    headings = semantic_headings(manuscript)
    for index, row in enumerate(rows):
        label = f"Article {article_id} extract {index + 1}"
        if not isinstance(row, dict):
            errors.append(f"{label} must be a mapping")
            continue
        extract_id = str(row.get("id") or "").strip()
        source_id = str(row.get("source_id") or "").strip()
        begin = str(row.get("begin") or "")
        end = str(row.get("end") or "")
        style = str(row.get("style") or "").strip()
        caption = str(row.get("caption") or "").strip()
        anchor = str(row.get("anchor") or "").strip()
        missing = [
            name
            for name, value in (
                ("id", extract_id),
                ("source_id", source_id),
                ("begin", begin),
                ("end", end),
                ("style", style),
                ("caption", caption),
                ("anchor", anchor),
            )
            if not value
        ]
        if missing:
            errors.append(f"{label} missing: {', '.join(missing)}")
            continue
        if extract_id in seen:
            errors.append(f"Article {article_id} has duplicate extract id: {extract_id}")
        seen.add(extract_id)
        if source_id not in article_source_ids:
            errors.append(f"{label} source_id must be one of the article source_ids")
            continue
        if style not in EXTRACT_STYLES:
            errors.append(f"{label} has invalid style: {style!r}; known: {sorted(EXTRACT_STYLES)}")
        if anchor != "__opener__" and anchor not in headings and not allow_unanchored:
            errors.append(f"{label} anchor does not match an article heading: {anchor!r}")
        source_path = root / "library" / "sources" / source_id / "article.md"
        if not source_path.is_file():
            errors.append(f"{label} source article is missing: {source_path}")
            continue
        source_text = source_path.read_text(encoding="utf-8")
        if source_text.count(begin) != 1:
            errors.append(
                f"{label} begin marker must occur exactly once in the source "
                f"(found {source_text.count(begin)}): {begin!r}"
            )
            continue
        start = source_text.index(begin)
        if source_text.count(end, start) != 1:
            errors.append(
                f"{label} end marker must occur exactly once at or after begin "
                f"(found {source_text.count(end, start)}): {end!r}"
            )
            continue
        text = source_text[start : source_text.index(end, start) + len(end)]
        if text in manuscript_text:
            errors.append(
                f"{label} run already appears verbatim in the manuscript; "
                "drop the extract row or the manuscript's own copy"
            )
        extracts.append(Extract(extract_id, source_id, text, style, caption, anchor))
    if errors:
        raise ValidationError(errors)
    return tuple(extracts)


def localize_extracts(
    base: tuple[Extract, ...],
    rows: Any,
    *,
    article_id: str,
    manuscript: Path,
    language: str,
) -> tuple[Extract, ...]:
    """Overlay translated caption and anchor on base extracts.

    ``text``, ``style``, and ``source_id`` never change: the run is verbatim
    source material, preserved exactly, in its source's language.
    """

    if not base:
        if rows not in (None, []):
            raise ValidationError(
                f"Translation {language!r} article {article_id} has extracts absent from English"
            )
        return ()
    if not isinstance(rows, list):
        raise ValidationError(
            f"Translation {language!r} article {article_id} extracts must be a list"
        )
    errors: list[str] = []
    by_id = {
        str(row.get("id")): row
        for row in rows
        if isinstance(row, dict) and row.get("id")
    }
    expected_ids = {extract.id for extract in base}
    if set(by_id) != expected_ids:
        missing = sorted(expected_ids - set(by_id))
        extra = sorted(set(by_id) - expected_ids)
        if missing:
            errors.append(
                f"Translation {language!r} article {article_id} is missing extracts: {', '.join(missing)}"
            )
        if extra:
            errors.append(
                f"Translation {language!r} article {article_id} has unknown extracts: {', '.join(extra)}"
            )
    headings = semantic_headings(manuscript)
    localized: list[Extract] = []
    for extract in base:
        row = by_id.get(extract.id)
        if not row:
            continue
        caption = str(row.get("caption") or "").strip()
        anchor = str(row.get("anchor") or "").strip()
        if not caption or not anchor:
            errors.append(
                f"Translation {language!r} extract {extract.id} requires caption and anchor"
            )
        if anchor != "__opener__" and anchor not in headings:
            errors.append(
                f"Translation {language!r} extract {extract.id} anchor does not match a translated heading"
            )
        localized.append(replace(extract, caption=caption, anchor=anchor))
    if errors:
        raise ValidationError(errors)
    return tuple(localized)


def semantic_headings(path: Path) -> set[str]:
    """Every ``##`` heading a figure anchor may name.

    Public because ``produce`` reconciles anchors against a manuscript it has
    just rewritten, and it has to ask the same question this module answers
    when it validates one.
    """

    return {
        line[3:].strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ") and line[3:].strip()
    }
