"""Materialize a validated edition as a self-contained, paged web directory.

The public seam is :func:`write_web_edition`: callers supply an already
validated :class:`~magazine.manifest.Edition` and a destination directory, and
receive that directory filled with everything a browser needs, structured the
way a reader arrives: ``index.html`` is the cover page -- the composed cover
face when the caller supplies one, the edition header, and a contents whose
entries link onward -- one ``<piece>.html`` per editorial, article and section,
each carrying a masthead back to the cover and a previous/next turn between
neighbours, and ``edition.html``, the whole edition in one scroll for reading
straight through.  Shared ``edition.css``, ``assets/`` and ``fonts/`` sit at
the root beside them; every URL is relative and nothing requires a network or
the repository to exist.

The semantic HTML itself comes from
:func:`magazine.html_edition.render_html_edition` unchanged; what this adapter
adds is exactly the screen policy that module deliberately leaves out.  Three
of its verdicts are content decisions this medium reverses mechanically:

* The opener's provenance line names the sources a piece was built from; on
  screen each named id whose address the caller supplies (``source_urls``)
  becomes a working link, because a screen can follow where paper can only
  print.
* The bottom ``source-link`` anchor -- the semantic hook print renders as a QR
  code -- is dropped: the linked provenance line above already answers it, and
  answering twice is clutter.
* Tail art is dropped entirely, page and bytes both: the ornament closes a
  printed page, and a scrolling page is closed by its own end mark.

Like the print adapter, this module never re-folds or re-escapes the assembled
document: character rules applied to finished markup rewrite tag and attribute
syntax, not prose.  Every split and insertion is anchored to a line the
semantic renderer is known to emit, and a missing anchor is a refusal, never a
silent skip -- an unstyled, unviewable or half-paged edition shipped quietly is
the same class of failure as a blank printed one.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from html import escape
from importlib import resources
from pathlib import Path

from .errors import ValidationError
from .html_edition import HtmlAsset, render_html_edition
from .manifest import Edition
from .reader_text import fold_reader_characters

_VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">'
_STYLESHEET_LINK = '<link rel="stylesheet" href="edition.css">'
# The exact charset line render_html_edition writes, indentation included.  It
# is the anchor for the head injection: everything a screen needs and print
# does not goes immediately after it.
_CHARSET_LINE = '  <meta charset="utf-8">'
# The <main> opening is the anchor for the cover plate and the document split:
# the semantic layer indents every top-level piece to column four inside it and
# closes each at column zero, which is what makes line-anchored surgery exact.
_MAIN_OPENING = re.compile(r"(?m)^  <main [^\n]*>$")
_MAIN_CLOSING = "  </main>"
_UNSAFE_NAME_CHARACTERS = re.compile(r"[^A-Za-z0-9._-]")
# Print-only elements, dropped whole: both are emitted as single lines, and
# their reasons to exist -- a tail ornament closing a printed page, a QR
# destination for a reader who cannot click -- have no screen equivalent once
# the provenance line links out (see the module docstring).
_PRINT_ONLY_LINE = re.compile(r'^\s*(?:<figure class="article-tail" |<a class="source-link" )')
_PROVENANCE_SPAN = re.compile(r'<span data-source-id="([^"]*)">(.*?)</span>')
_PIECE_OPENING = re.compile(r'^    <(article|section) id="([^"]*)"')
_HEADING_LINE = re.compile(r"^\s*<h1>(.*)</h1>$")
_TITLE_LINE = re.compile(r"^  <title>(.*)</title>$")
_SHORT_TITLE = re.compile(r'data-short-title="([^"]*)"')
_CONTENTS_HREF = re.compile(r'href="#([^"]*)"')
# Filenames the directory itself owns; a piece may not claim them.
_RESERVED_NAMES = frozenset({"index.html", "edition.html", "edition.css"})


@dataclass(frozen=True, slots=True)
class WebAsset:
    """One materialized asset: the semantic inventory entry and its web URL.

    ``href`` is relative to the web directory root (``assets/...``), which is
    what keeps the output servable from any path and openable straight from
    the filesystem.  When a composed ``cover_face`` was supplied, the cover
    entry's copied bytes are the face's rather than ``asset.path``'s -- the
    inventory records what the edition authored, the face is how this adapter
    presents it.
    """

    asset: HtmlAsset
    href: str


@dataclass(frozen=True, slots=True)
class WebEdition:
    """The written web directory: root, cover page, piece pages, one-scroll
    document, and the materialized assets."""

    root: Path
    index: Path
    pages: tuple[Path, ...]
    edition_document: Path
    assets: tuple[WebAsset, ...]


@dataclass(frozen=True, slots=True)
class _Piece:
    """One top-level piece of the document, verbatim, with its page facts."""

    lines: tuple[str, ...]
    element_id: str
    short_title: str
    heading: str
    filename: str


@dataclass(frozen=True, slots=True)
class _Document:
    """The rendered document, split on the semantic layer's own boundaries."""

    html_open: str
    main_open: str
    title: str
    publication: str
    issue: str
    header: tuple[str, ...]
    contents: tuple[str, ...]
    pieces: tuple[_Piece, ...]
    plates: tuple[str, ...]


def write_web_edition(
    edition: Edition,
    destination: Path,
    *,
    cover_face: Path | None = None,
    source_urls: Mapping[str, str] | None = None,
) -> WebEdition:
    """Write a validated edition as a browsable, paged directory.

    ``cover_face`` is the composed cover -- wordmark, headline, tab -- as an
    image file; when given it is what the cover pages show, and the raw
    artwork the inventory records is not shipped, because the face contains
    it.  Without it the raw artwork stands in, and an edition with neither
    simply opens on its header.  ``source_urls`` maps source ids to the
    addresses their provenance mentions should link to; ids without an entry
    stay plain text rather than becoming broken links.

    The output is deterministic -- two runs over the same inputs produce
    byte-identical trees -- and self-contained.  The caller owns the
    destination; existing files with the same names are overwritten,
    unrelated files are left alone.
    """

    semantic = render_html_edition(edition)
    destination.mkdir(parents=True, exist_ok=True)

    inventory = _inventory_with_cover_face(edition, semantic.assets, cover_face)
    web_assets = _materialize_assets(inventory, destination, cover_face)
    html = _drop_print_only_lines(semantic.html)
    html = _link_provenance(html, source_urls or {})
    html = _rewrite_sources(html, web_assets)

    document = _parse_document(html)
    plate = _cover_plate_line(web_assets)

    pages = tuple(
        _write_page(
            destination / piece.filename,
            _piece_page(
                document,
                piece,
                document.pieces[position - 1] if position > 0 else None,
                document.pieces[position + 1] if position + 1 < len(document.pieces) else None,
            ),
        )
        for position, piece in enumerate(document.pieces)
    )
    index = _write_page(destination / "index.html", _index_page(document, plate))
    edition_document = _write_page(
        destination / "edition.html",
        _insert_cover_plate(_inject_head(html), plate),
    )
    (destination / "edition.css").write_bytes(_read_screen_css())
    _copy_tree(resources.files("magazine").joinpath("assets", "fonts"), destination / "fonts")
    return WebEdition(
        root=destination,
        index=index,
        pages=pages,
        edition_document=edition_document,
        assets=web_assets,
    )


def _inventory_with_cover_face(
    edition: Edition, assets: tuple[HtmlAsset, ...], cover_face: Path | None
) -> tuple[HtmlAsset, ...]:
    """The semantic inventory, plus a cover entry when only the face exists.

    ``render_html_edition`` inventories the cover only when the edition
    authored raw cover art; a caller supplying a composed face for a coverless
    edition still gets a cover page, so the entry is fabricated here with the
    same alt text the semantic layer would have chosen.
    """

    if cover_face is None or any(asset.role == "cover_art" for asset in assets):
        return assets
    return assets + (
        HtmlAsset(
            id="cover-art",
            role="cover_art",
            path=cover_face,
            src=cover_face.as_uri(),
            alt_text=str(edition.cover.get("headline") or edition.title),
        ),
    )


def _materialize_assets(
    assets: tuple[HtmlAsset, ...], destination: Path, cover_face: Path | None
) -> tuple[WebAsset, ...]:
    """Copy every shipping asset under ``assets/`` with a filesystem-safe name.

    The name is the asset's own id -- already unique and deterministic per
    edition -- with every character outside ``[A-Za-z0-9._-]`` folded to ``-``,
    plus the copied file's suffix so browsers and servers can type the bytes.
    Tail art does not ship at all (module docstring), and the cover entry's
    bytes are the composed face's when one was supplied.

    Names are claimed casefolded, though written as-is: on a case-insensitive
    filesystem (APFS, the default here) ``Fig1.png`` and ``fig1.png`` are one
    file, and the second copy would silently replace the first while the HTML
    references both.  Refusing the pair everywhere keeps the verdict a property
    of the edition, not of whichever filesystem happened to build it.
    """

    directory = destination / "assets"
    directory.mkdir(parents=True, exist_ok=True)
    claimed: dict[str, str] = {}
    materialized: list[WebAsset] = []
    for asset in assets:
        if asset.role == "article_tail":
            continue
        source = asset.path
        if asset.role == "cover_art" and cover_face is not None:
            source = cover_face
        name = _sanitize(asset.id) + _sanitize(source.suffix)
        prior = claimed.get(name.casefold())
        if prior is not None:
            raise ValidationError(
                f"web asset filename collision: {asset.id!r} and {prior!r} "
                f"both sanitize to assets/{name}, compared case-insensitively "
                "because a case-insensitive filesystem would store one file "
                "for both"
            )
        claimed[name.casefold()] = asset.id
        shutil.copyfile(source, directory / name)
        materialized.append(WebAsset(asset=asset, href=f"assets/{name}"))
    return tuple(materialized)


def _sanitize(value: str) -> str:
    return _UNSAFE_NAME_CHARACTERS.sub("-", value)


def _drop_print_only_lines(html: str) -> str:
    return "\n".join(
        line for line in html.split("\n") if not _PRINT_ONLY_LINE.match(line)
    )


def _link_provenance(html: str, source_urls: Mapping[str, str]) -> str:
    """Turn each provenance mention with a known address into a working link.

    The needle keys are the ids exactly as the semantic layer wrote them into
    ``data-source-id`` -- folded, then escaped -- so the lookup happens in the
    document's own encoding.  Only lines carrying the provenance class are
    touched: the same ``data-source-id`` attribute also rides on figures,
    where it is a fact about the image, not a mention to link.
    """

    if not source_urls:
        return html
    addresses = {_attr(source_id): _attr(url) for source_id, url in source_urls.items()}

    def _linked(match: re.Match[str]) -> str:
        address = addresses.get(match.group(1))
        if address is None:
            return match.group(0)
        return (
            f'<a data-source-id="{match.group(1)}" href="{address}">{match.group(2)}</a>'
        )

    return "\n".join(
        _PROVENANCE_SPAN.sub(_linked, line) if '<p class="provenance"' in line else line
        for line in html.split("\n")
    )


def _rewrite_sources(html: str, web_assets: tuple[WebAsset, ...]) -> str:
    """Point every rendered ``src`` at the materialized copy of its asset.

    The needle is the ``file:`` URI exactly as the semantic layer wrote it into
    the attribute -- folded, then escaped -- so the replacement can be a plain
    string substitution rather than markup surgery.  Two inventory entries may
    share one source file (the cover and a figure can be the same picture);
    they then share one URI and the first entry's copy answers for both, which
    is harmless because identical source bytes were copied under both names.
    """

    replacements: dict[str, str] = {}
    for web in web_assets:
        replacements.setdefault(
            f'src="{_attr(web.asset.src)}"', f'src="{_attr(web.href)}"'
        )
    for needle, replacement in replacements.items():
        html = html.replace(needle, replacement)
    return html


def _parse_document(html: str) -> _Document:
    """Split the rendered document on the boundaries the renderer guarantees.

    Inside ``<main>`` every top-level element opens at column four and closes
    at column zero (embedded content keeps its own shallower indent, and all
    authored text is escaped, so no authored line can imitate a boundary).
    Anything this walk does not recognize means render_html_edition changed
    shape underneath the adapter, and the answer is a named refusal.
    """

    lines = html.split("\n")
    if len(lines) < 2 or not lines[1].startswith("<html "):
        raise ValidationError(
            "web edition expected the semantic document to open '<html ' on "
            "its second line; the document has changed shape"
        )
    html_open = lines[1]
    titles = [match.group(1) for line in lines if (match := _TITLE_LINE.match(line))]
    if len(titles) != 1:
        raise ValidationError(
            "web edition expected exactly one '  <title>' line in the semantic "
            "head; the document has changed shape"
        )
    openings = [index for index, line in enumerate(lines) if _MAIN_OPENING.match(line)]
    if len(openings) != 1:
        raise ValidationError(
            "web edition expected exactly one '<main>' opening; the semantic "
            "body has changed shape"
        )
    start = openings[0]
    try:
        stop = lines.index(_MAIN_CLOSING, start)
    except ValueError:
        raise ValidationError(
            "web edition expected a '  </main>' closing line; the semantic "
            "body has changed shape"
        ) from None

    header: tuple[str, ...] | None = None
    contents: tuple[str, ...] | None = None
    pieces: list[_Piece] = []
    plates: list[str] = []
    claimed: dict[str, str] = {}
    position = start + 1
    while position < stop:
        line = lines[position]
        if line.startswith('    <header class="edition-header"'):
            closing = _closing_line(lines, position, stop, "</header>")
            header = tuple(lines[position : closing + 1])
            position = closing + 1
        elif line.startswith("    <nav ") and 'data-edition-navigation="contents"' in line:
            closing = _closing_line(lines, position, stop, "</nav>")
            contents = tuple(lines[position : closing + 1])
            position = closing + 1
        elif (opened := _PIECE_OPENING.match(line)) is not None:
            closing = _closing_line(lines, position, stop, f"</{opened.group(1)}>")
            pieces.append(
                _piece(tuple(lines[position : closing + 1]), opened.group(2), claimed)
            )
            position = closing + 1
        elif line.startswith('    <figure class="closing-plate"') and line.endswith("</figure>"):
            plates.append(line)
            position += 1
        else:
            raise ValidationError(
                "web edition met a top-level line it does not recognize while "
                f"paging the document: {line.strip()[:80]!r}; the semantic "
                "body has changed shape"
            )
    if header is None or contents is None:
        raise ValidationError(
            "web edition expected the edition header and the contents "
            "navigation inside <main>; the semantic body has changed shape"
        )
    publication = _header_text(header, "publication-name")
    issue = _header_text(header, "issue-number")
    return _Document(
        html_open=html_open,
        main_open=lines[start],
        title=titles[0],
        publication=publication,
        issue=issue,
        header=header,
        contents=contents,
        pieces=tuple(pieces),
        plates=tuple(plates),
    )


def _closing_line(lines: list[str], start: int, stop: int, closing: str) -> int:
    for position in range(start + 1, stop):
        if lines[position] == closing:
            return position
    raise ValidationError(
        f"web edition expected a {closing!r} line closing the element opened "
        f"at {lines[start].strip()[:80]!r}; the semantic body has changed shape"
    )


def _piece(lines: tuple[str, ...], element_id: str, claimed: dict[str, str]) -> _Piece:
    short_title = _SHORT_TITLE.search(lines[0])
    if short_title is None:
        raise ValidationError(
            "web edition expected a data-short-title attribute on the piece "
            f"opened at {lines[0].strip()[:80]!r}; the page turns have nothing "
            "to say without it"
        )
    heading = next(
        (match.group(1) for line in lines if (match := _HEADING_LINE.match(line))), None
    )
    if heading is None:
        raise ValidationError(
            "web edition expected an <h1> inside the piece opened at "
            f"{lines[0].strip()[:80]!r}; a page needs its own title"
        )
    filename = _sanitize(element_id) + ".html"
    if filename.casefold() in {name.casefold() for name in _RESERVED_NAMES}:
        raise ValidationError(
            f"web page filename collision: piece id {element_id!r} claims "
            f"{filename}, a name the web directory itself owns"
        )
    prior = claimed.get(filename.casefold())
    if prior is not None:
        raise ValidationError(
            f"web page filename collision: piece ids {element_id!r} and "
            f"{prior!r} both claim {filename}, compared case-insensitively "
            "because a case-insensitive filesystem would store one file for "
            "both"
        )
    claimed[filename.casefold()] = element_id
    return _Piece(
        lines=lines,
        element_id=element_id,
        short_title=short_title.group(1),
        heading=heading,
        filename=filename,
    )


def _header_text(header: tuple[str, ...], class_name: str) -> str:
    pattern = re.compile(rf'^\s*<p class="{class_name}"[^>]*>(.*)</p>$')
    for line in header:
        match = pattern.match(line)
        if match:
            return match.group(1)
    raise ValidationError(
        f"web edition expected a '{class_name}' paragraph in the edition "
        "header; the masthead has nothing to say without it"
    )


def _cover_plate_line(web_assets: tuple[WebAsset, ...]) -> str | None:
    """The cover figure, or None when the edition ships no cover at all.

    Print splices the cover PDF into the reader's first page; the screen
    equivalent is an ordinary figure leading the page.  The alt text is the
    inventory's own -- the cover headline, or the edition title when no
    headline was authored -- escaped here because the inventory stores
    authored text, not markup.
    """

    cover = next((web for web in web_assets if web.asset.role == "cover_art"), None)
    if cover is None:
        return None
    return (
        '    <figure class="cover-plate" data-asset-role="cover_art">'
        f'<img src="{_attr(cover.href)}" alt="{_attr(cover.asset.alt_text)}">'
        "</figure>"
    )


def _shared_head(document: _Document, title: str) -> tuple[str, ...]:
    return (
        "<!doctype html>",
        document.html_open,
        "<head>",
        _CHARSET_LINE,
        "  " + _VIEWPORT,
        "  " + _STYLESHEET_LINK,
        f"  <title>{title}</title>",
        "</head>",
        "<body>",
        document.main_open,
    )


_PAGE_CLOSE = (_MAIN_CLOSING, "</body>", "</html>", "")


def _index_page(document: _Document, plate: str | None) -> str:
    """The cover page: face, header, contents linking onward, closing plates.

    The contents entries point at the piece pages instead of the in-document
    anchors ``render_html_edition`` wrote (``edition.html`` keeps those).  The
    closing plates land here too: they close the edition, not any piece, and
    the cover page is the one page that is the edition rather than a piece --
    the shelf a printed reader returns to when the covers close.
    """

    filenames = {piece.element_id: piece.filename for piece in document.pieces}

    def _paged(match: re.Match[str]) -> str:
        filename = filenames.get(match.group(1))
        if filename is None:
            raise ValidationError(
                f"the contents navigation points at #{match.group(1)} but no "
                "piece with that id was paged; the semantic body has changed "
                "shape"
            )
        return f'href="{filename}"'

    contents = tuple(_CONTENTS_HREF.sub(_paged, line) for line in document.contents)
    lines = (
        *_shared_head(document, document.title),
        *(() if plate is None else (plate,)),
        *document.header,
        *contents,
        *document.plates,
        *_PAGE_CLOSE,
    )
    return "\n".join(lines)


def _piece_page(
    document: _Document, piece: _Piece, previous: _Piece | None, following: _Piece | None
) -> str:
    """One piece on its own page, between a masthead and its page turns.

    Every string on the chrome lines is one the document already carries --
    the publication name and issue from the edition header, the neighbours'
    short titles from their own openings -- so the pages introduce no language
    of their own, in any language.
    """

    masthead = (
        '    <nav class="masthead" data-web-chrome="masthead"><a href="index.html">'
        f'<span class="publication-name">{document.publication}</span>'
        f'<span class="issue-number">{document.issue}</span></a></nav>'
    )
    turns = []
    if previous is not None:
        turns.append(
            f'<a class="page-turn-previous" rel="prev" '
            f'href="{_attr(previous.filename)}">{previous.short_title}</a>'
        )
    if following is not None:
        turns.append(
            f'<a class="page-turn-next" rel="next" '
            f'href="{_attr(following.filename)}">{following.short_title}</a>'
        )
    page_turn = (
        ('    <nav class="page-turn" data-web-chrome="page-turn">' + "".join(turns) + "</nav>",)
        if turns
        else ()
    )
    lines = (
        *_shared_head(document, f"{document.publication} — {piece.heading}"),
        masthead,
        *piece.lines,
        *page_turn,
        *_PAGE_CLOSE,
    )
    return "\n".join(lines)


def _write_page(path: Path, html: str) -> Path:
    if 'src="file:' in html:
        raise ValidationError(
            f"web page {path.name} still references a local file: URI after "
            "source rewriting; either an asset was rendered that the "
            "inventory did not declare, or an authored code span contains a "
            'literal src="file: -- code keeps its straight quotes, so this '
            "guard cannot tell the two apart and refuses both"
        )
    path.write_text(html, encoding="utf-8")
    return path


def _inject_head(html: str) -> str:
    """Add the viewport and stylesheet link a screen needs and print ignores.

    Anchored to the one charset line the semantic head is known to contain; a
    head of any other shape means render_html_edition changed underneath this
    adapter, and the right response is a named refusal, not a page that quietly
    ships unstyled and unscaled.
    """

    lines = html.split("\n")
    if lines.count(_CHARSET_LINE) != 1:
        # Counted line by line, not by substring search: two adjacent charset
        # lines share a newline, and a non-overlapping count would see one.
        raise ValidationError(
            "web edition expected exactly one '  <meta charset=\"utf-8\">' line "
            "to anchor the viewport and stylesheet injection; the semantic head "
            "has changed shape"
        )
    anchor = lines.index(_CHARSET_LINE)
    lines[anchor + 1 : anchor + 1] = ["  " + _VIEWPORT, "  " + _STYLESHEET_LINK]
    return "\n".join(lines)


def _insert_cover_plate(html: str, plate: str | None) -> str:
    """Lead the one-scroll document with the cover, when the edition has one."""

    if plate is None:
        return html
    openings = _MAIN_OPENING.findall(html)
    if len(openings) != 1:
        raise ValidationError(
            "web edition expected exactly one '<main>' opening to anchor the "
            "cover plate; the semantic body has changed shape"
        )
    return html.replace(openings[0], openings[0] + "\n" + plate, 1)


def _read_screen_css() -> bytes:
    resource = resources.files("magazine").joinpath("assets", "screen-edition.css")
    try:
        return resource.read_bytes()
    except FileNotFoundError:
        raise ValidationError(
            "the packaged screen stylesheet assets/screen-edition.css is "
            "missing; the web edition ships no page it cannot style"
        ) from None


def _copy_tree(source, target: Path) -> None:
    """Copy a packaged directory tree byte-for-byte, in sorted order.

    Uses the Traversable API rather than assuming the package is a real
    directory on disk, and sorts every level so the copy order -- and with it
    the written tree -- never depends on filesystem enumeration.
    """

    target.mkdir(parents=True, exist_ok=True)
    for entry in sorted(source.iterdir(), key=lambda item: item.name):
        if entry.is_dir():
            _copy_tree(entry, target / entry.name)
        else:
            (target / entry.name).write_bytes(entry.read_bytes())


def _attr(value: object) -> str:
    # Must mirror html_edition._attr exactly -- fold first, escape second --
    # because the rewrite needles are matched against attribute values that
    # function already wrote.
    return escape(fold_reader_characters(str(value)), quote=True)
