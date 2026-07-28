"""Materialize a validated edition as a self-contained, paged web directory.

The public seam is :func:`write_web_edition`: callers supply an already
validated :class:`~magazine.manifest.Edition` and a destination directory, and
receive that directory filled with everything a browser needs, structured the
way a reader arrives: ``index.html`` is the cover page -- composed natively
for the medium from the edition's own facts (the Corte bruto wordmark when the
caller supplies it, the cover headline, the artwork, the contributor register,
the date, and a canto-vivo edge) above a contents whose entries link onward --
one ``<piece>.html`` per editorial, article and section,
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
* Closing plates are dropped the same way, page and bytes both.  They are
  filler art -- decorative furniture that gives a printed object a back to
  close on -- and a website has no back cover.  The line is editorial, not
  aesthetic: evidence figures, the cover artwork and the wordmark are
  content and identity and always ship; art that exists to fill is what
  goes.

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

# Cover-module facts, imported rather than mirrored: the web cover must state
# the same contributor register, the same spaced date, and the same canto-tab
# words the printed cover states, and importing the one derivation each is
# what makes drift impossible.  All are pure functions of edition data --
# importing them pulls in no font or rasterizer machinery.
from .cover import _cover_contributors, _cover_date, cover_tab_identity, cover_tab_issue

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
# Print-only elements, dropped whole: each is emitted as a single line, and
# their reasons to exist -- a tail ornament closing a printed page, a QR
# destination for a reader who cannot click, a closing plate giving a printed
# object a back to close on -- have no screen equivalent (see the module
# docstring).
_PRINT_ONLY_LINE = re.compile(
    r'^\s*(?:<figure class="article-tail" '
    r'|<a class="source-link" '
    r'|<figure class="closing-plate" )'
)
_PROVENANCE_SPAN = re.compile(r'<span data-source-id="([^"]*)">(.*?)</span>')
# An evidence figure's image line, for the full-size escape hatch: the screen
# shows the figure at the reading measure, so the image itself must link to
# the shipped bytes a reader can open at native size.
_FIGURE_IMAGE = re.compile(r'(<img src="([^"]*)"[^>]*>)')
_PIECE_OPENING = re.compile(r'^    <(article|section) id="([^"]*)"')
_HEADING_LINE = re.compile(r"^\s*<h1>(.*)</h1>$")
_CONTENTS_HEADING = re.compile(r"^\s*<h2>(.*)</h2>$")
_TITLE_LINE = re.compile(r"^  <title>(.*)</title>$")
_SHORT_TITLE = re.compile(r'data-short-title="([^"]*)"')
_CONTENTS_HREF = re.compile(r'href="#([^"]*)"')
# Filenames the directory itself owns; a piece may not claim them.
_RESERVED_NAMES = frozenset({"index.html", "edition.html", "edition.css"})
# Asset roles whose markup _PRINT_ONLY_LINE drops; their bytes never ship
# either -- an unreferenced file in assets/ is dead weight a deploy would
# faithfully serve.
_FILLER_ROLES = frozenset({"article_tail", "closing_plate"})


@dataclass(frozen=True, slots=True)
class WebAsset:
    """One materialized asset: the semantic inventory entry and its web URL.

    ``href`` is relative to the web directory root (``assets/...``), which is
    what keeps the output servable from any path and openable straight from
    the filesystem.
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
    contents_label: str
    header: tuple[str, ...]
    contents: tuple[str, ...]
    pieces: tuple[_Piece, ...]


def write_web_edition(
    edition: Edition,
    destination: Path,
    *,
    wordmark: Path | None = None,
    favicon: Path | None = None,
    source_urls: Mapping[str, str] | None = None,
    headline_lines: tuple[str, ...] | None = None,
    alternates: Mapping[str, str] | None = None,
) -> WebEdition:
    """Write a validated edition as a browsable, paged directory.

    ``wordmark`` is the publication's standalone lockup as an SVG file (see
    :func:`magazine.cover.materialize_wordmark_svg`); when given it ships as
    ``assets/wordmark.svg``, leads the cover page large, and heads every
    piece page's masthead -- the logo is publication identity, so it appears
    wherever the publication's name would.  Without it the mastheads fall
    back to the name set as text, and the cover page opens on the edition
    header the semantic layer already carries.  ``favicon`` ships the same
    way as ``assets/favicon.svg`` and is linked from every page's head (see
    :func:`magazine.cover.materialize_favicon_svg`); without it browsers ask
    for an icon nothing ships.  ``source_urls`` maps source ids to the
    addresses their provenance mentions should link to; ids without an entry
    stay inspectable text rather than becoming broken links.
    ``headline_lines`` is the cover headline pre-broken into the printed
    face's own lines (:func:`magazine.cover.cover_headline_lines`); without
    it the headline sets as one run.  ``alternates`` maps sibling language
    codes to relative directory prefixes (``{"es": "../es/"}``) and becomes
    the colophon's way across languages.

    The output is deterministic -- two runs over the same inputs produce
    byte-identical trees -- and self-contained.  The caller owns the
    destination; existing files with the same names are overwritten,
    unrelated files are left alone.
    """

    semantic = render_html_edition(edition)
    destination.mkdir(parents=True, exist_ok=True)

    web_assets, chrome = _materialize_assets(semantic.assets, destination, wordmark, favicon)
    html = _drop_print_only_lines(semantic.html)
    html = _number_provenance(html, source_urls or {})
    html = _rewrite_sources(html, web_assets)
    html = _link_figures(html)

    document = _parse_document(html)
    cover = _cover_lines(edition, document, web_assets, chrome.wordmark, headline_lines)
    masthead = _masthead_line(edition, document, chrome.wordmark)
    colophon_index = _colophon_lines(edition, document, alternates or {}, sibling="edition.html")
    colophon_edition = _colophon_lines(edition, document, alternates or {}, sibling="index.html")

    pages = tuple(
        _write_page(
            destination / piece.filename,
            _piece_page(
                document,
                piece,
                document.pieces[position - 1] if position > 0 else None,
                document.pieces[position + 1] if position + 1 < len(document.pieces) else None,
                masthead,
                chrome.favicon,
            ),
        )
        for position, piece in enumerate(document.pieces)
    )
    index = _write_page(
        destination / "index.html",
        _index_page(document, cover, colophon_index, chrome.favicon),
    )
    edition_document = _write_page(
        destination / "edition.html",
        _close_with_colophon(
            _insert_cover_block(_inject_head(html, chrome.favicon), cover.standalone),
            colophon_edition,
        ),
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


@dataclass(frozen=True, slots=True)
class _Chrome:
    """The publication chrome's shipped URLs: lockup and favicon, or None."""

    wordmark: str | None
    favicon: str | None


def _materialize_assets(
    assets: tuple[HtmlAsset, ...],
    destination: Path,
    wordmark: Path | None,
    favicon: Path | None = None,
) -> tuple[tuple[WebAsset, ...], _Chrome]:
    """Copy every shipping asset under ``assets/`` with a filesystem-safe name.

    The name is the asset's own id -- already unique and deterministic per
    edition -- with every character outside ``[A-Za-z0-9._-]`` folded to ``-``,
    plus the copied file's suffix so browsers and servers can type the bytes.
    Tail art and closing plates do not ship at all (module docstring: filler
    art has no page to fill here).  The wordmark and favicon, when supplied,
    ship as ``assets/wordmark.svg`` and ``assets/favicon.svg`` -- publication
    chrome rather than edition content, so they claim their names first and an
    edition asset that would collide with either is refused like any other
    collision.

    Names are claimed casefolded, though written as-is: on a case-insensitive
    filesystem (APFS, the default here) ``Fig1.png`` and ``fig1.png`` are one
    file, and the second copy would silently replace the first while the HTML
    references both.  Refusing the pair everywhere keeps the verdict a property
    of the edition, not of whichever filesystem happened to build it.
    """

    directory = destination / "assets"
    directory.mkdir(parents=True, exist_ok=True)
    claimed: dict[str, str] = {}
    wordmark_href: str | None = None
    favicon_href: str | None = None
    if wordmark is not None:
        claimed["wordmark.svg"] = "the publication wordmark"
        shutil.copyfile(wordmark, directory / "wordmark.svg")
        wordmark_href = "assets/wordmark.svg"
    if favicon is not None:
        claimed["favicon.svg"] = "the publication favicon"
        shutil.copyfile(favicon, directory / "favicon.svg")
        favicon_href = "assets/favicon.svg"
    materialized: list[WebAsset] = []
    for asset in assets:
        if asset.role in _FILLER_ROLES:
            continue
        source = asset.path
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
    return tuple(materialized), _Chrome(wordmark=wordmark_href, favicon=favicon_href)


def _sanitize(value: str) -> str:
    return _UNSAFE_NAME_CHARACTERS.sub("-", value)


def _drop_print_only_lines(html: str) -> str:
    return "\n".join(
        line for line in html.split("\n") if not _PRINT_ONLY_LINE.match(line)
    )


def _number_provenance(html: str, source_urls: Mapping[str, str]) -> str:
    """Set each provenance mention as a numbered reference, linked when known.

    A source id is an internal name -- content hash and all -- and internal
    names are not reader typography: set as running text they wrap mid-slug
    and read as a build artifact leaked onto the page.  So each mention
    becomes a two-digit reference in the opener's own label grammar, numbered
    in the order the piece names its sources; the id stays inspectable in
    ``title`` and ``aria-label``, and a mention whose address is known links
    there.  The needle keys are the ids exactly as the semantic layer wrote
    them into ``data-source-id`` -- folded, then escaped -- so the lookup
    happens in the document's own encoding.  Only lines carrying the
    provenance class are touched: the same ``data-source-id`` attribute also
    rides on figures, where it is a fact about the image, not a mention.
    """

    addresses = {_attr(source_id): _attr(url) for source_id, url in source_urls.items()}

    def _numbered_line(line: str) -> str:
        counter = 0

        def _reference(match: re.Match[str]) -> str:
            nonlocal counter
            counter += 1
            number = f"{counter:02d}"
            identity = f'data-source-id="{match.group(1)}" title="{match.group(1)}" aria-label="{match.group(1)}"'
            address = addresses.get(match.group(1))
            if address is None:
                return f'<span class="provenance-source" {identity}>{number}</span>'
            return f'<a class="provenance-source" {identity} href="{address}">{number}</a>'

        return _PROVENANCE_SPAN.sub(_reference, line)

    return "\n".join(
        _numbered_line(line) if '<p class="provenance"' in line else line
        for line in html.split("\n")
    )


def _link_figures(html: str) -> str:
    """Give every evidence figure's image a link to its own shipped bytes.

    At the reading measure a dense diagram can be furniture; the full-size
    file is one click away, and the link target is the same ``assets/`` copy
    the page already shows, so nothing new ships.  Runs after source
    rewriting, which is what makes the captured ``src`` the shippable href.
    Only figure lines are touched -- the cover art and the wordmark are
    identity, not evidence, and open nothing.
    """

    return "\n".join(
        _FIGURE_IMAGE.sub(r'<a class="figure-link" href="\2">\1</a>', line)
        if line.lstrip().startswith("<figure data-figure-id=")
        else line
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
    contents_label = next(
        (match.group(1) for line in contents if (match := _CONTENTS_HEADING.match(line))),
        None,
    )
    if contents_label is None:
        raise ValidationError(
            "web edition expected an <h2> heading inside the contents "
            "navigation; the cover cue and the page turns name it"
        )
    return _Document(
        html_open=html_open,
        main_open=lines[start],
        title=titles[0],
        publication=publication,
        issue=issue,
        contents_label=contents_label,
        header=header,
        contents=contents,
        pieces=tuple(pieces),
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


@dataclass(frozen=True, slots=True)
class _Cover:
    """What the cover pages open with.

    ``index_lines`` is the whole top of ``index.html`` -- the native cover
    block when the wordmark exists, the semantic edition header otherwise --
    and ``standalone`` is what ``edition.html`` gets inserted after its
    ``<main>`` opening, where the semantic header already stands on its own.
    """

    index_lines: tuple[str, ...]
    standalone: tuple[str, ...]


def _cover_lines(
    edition: Edition,
    document: _Document,
    web_assets: tuple[WebAsset, ...],
    wordmark_href: str | None,
    headline_lines: tuple[str, ...] | None,
) -> _Cover:
    """Compose the cover for this medium from the edition's own facts.

    The printed cover is a fixed A5 sheet; pasting its raster onto a scrolling
    page shows a picture of a cover, not a cover.  So the web cover restates
    the same facts natively: the lockup large, the localized cover headline
    (the edition title when none was authored) broken into the printed face's
    own lines when the caller derived them, the framed artwork, the
    contributor register the printed deck derives from the article records,
    the date the printed footer spaces, and a canto-vivo edge strip carrying
    the printed tab's exact words (:func:`~.cover.cover_tab_issue`,
    :func:`~.cover.cover_tab_identity`).  Every string is edition data, an
    imported cover derivation, or already-parsed document text; the block
    invents no language.  The index variant closes on a cue down to the
    contents -- the first screen must say where the reading starts -- and the
    cue's label is the contents' own heading.

    Without a wordmark there is no lockup to anchor that composition, so the
    cover page falls back to the semantic edition header, led by the raw
    artwork when the edition authored one.
    """

    art = next((web for web in web_assets if web.asset.role == "cover_art"), None)
    art_lines = () if art is None else (
        '    <figure class="cover-art" data-asset-role="cover_art">'
        f'<img src="{_attr(art.href)}" alt="{_attr(art.asset.alt_text)}">'
        "</figure>",
    )
    if wordmark_href is None:
        return _Cover(index_lines=art_lines + document.header, standalone=art_lines)

    headline_text = str(edition.cover.get("headline") or edition.title)
    if headline_lines and " ".join(headline_lines).split() == headline_text.split():
        headline = "".join(
            f'<span class="cover-headline-line">{_text(line)}</span>'
            for line in headline_lines
        )
    else:
        # No derived break, or a break for some other text: one run of the
        # edition's own words beats a construction that silently mismatches.
        headline = _text(headline_text)
    roster = _text(_cover_contributors(edition))
    date = str(edition.publication_date)
    block = (
        '    <header class="cover" data-web-chrome="cover">',
        f'      <p class="canto"><span class="canto-issue">{_text(cover_tab_issue(edition))}</span>'
        f'<span class="canto-identity">{_text(cover_tab_identity(edition))}</span></p>',
        f'      <img class="cover-wordmark" src="{_attr(wordmark_href)}" '
        f'alt="{_attr(edition.publication_name)}">',
        f'      <h1 class="cover-headline">{headline}</h1>',
        *(f"  {line}" for line in art_lines),
        *((f'      <p class="cover-roster">{roster}</p>',) if roster else ()),
        f'      <time class="cover-date" datetime="{_attr(date)}">{_text(_cover_date(date))}</time>',
        "    </header>",
    )
    cue = f'      <a class="cover-cue" href="#contents">{document.contents_label}</a>'
    # The cue is first-screen information scent, so it stands directly under
    # the headline -- after the artwork it would only be read by a reader who
    # already scrolled, which is no cue at all.
    after_headline = next(
        index for index, line in enumerate(block) if 'class="cover-headline"' in line
    ) + 1
    return _Cover(
        index_lines=block[:after_headline] + (cue,) + block[after_headline:],
        standalone=block,
    )


def _masthead_line(edition: Edition, document: _Document, wordmark_href: str | None) -> str:
    """The piece pages' running head: the lockup when it exists, text when not.

    The logo is the publication's name in its own hand, so it stands wherever
    the name would; the issue number stays text beside it either way, and the
    whole head is one link back to the cover.
    """

    if wordmark_href is None:
        identity = (
            f'<span class="publication-name">{document.publication}</span>'
        )
    else:
        identity = (
            f'<img class="masthead-wordmark" src="{_attr(wordmark_href)}" '
            f'alt="{_attr(edition.publication_name)}">'
        )
    return (
        '    <nav class="masthead" data-web-chrome="masthead"><a href="index.html">'
        f'{identity}<span class="issue-number">{document.issue}</span></a></nav>'
    )


def _colophon_lines(
    edition: Edition,
    document: _Document,
    alternates: Mapping[str, str],
    *,
    sibling: str,
) -> tuple[str, ...]:
    """The quiet foot the cover page and the one-scroll document close on.

    A page that simply stops strands the reader; the printed book closes on
    the Signal fold, and this is the screen's own small version of the same
    gesture: the publication identity line the canto tab carries, the way to
    the sibling document (the one-scroll edition from the cover, the cover
    from the one-scroll edition), the same document in every sibling
    language, and the spaced publication date.  The sibling link's label is
    the issue string when it leads to the whole edition -- ``edition.html``
    IS the issue as one document -- and the contents' own heading when it
    leads back to the cover page, where the contents live.  Language links
    are labelled by their codes: a code is vocabulary-neutral chrome, like a
    folio, where a language *name* would be a word this module refuses to
    invent.
    """

    sibling_label = (
        _text(cover_tab_issue(edition)) if sibling == "edition.html" else document.contents_label
    )
    links = [f'<a class="colophon-sibling" href="{_attr(sibling)}">{sibling_label}</a>']
    here = "index.html" if sibling == "edition.html" else "edition.html"
    links.extend(
        f'<a class="colophon-language" href="{_attr(prefix + here)}" '
        f'hreflang="{_attr(code)}" lang="{_attr(code)}">{_text(code.upper())}</a>'
        for code, prefix in alternates.items()
    )
    date = str(edition.publication_date)
    return (
        '    <footer class="colophon" data-web-chrome="colophon">',
        f'      <p class="colophon-identity">{_text(cover_tab_identity(edition))}</p>',
        f'      <nav class="colophon-links">{"".join(links)}</nav>',
        f'      <time class="colophon-date" datetime="{_attr(date)}">{_text(_cover_date(date))}</time>',
        "    </footer>",
    )


def _shared_head(document: _Document, title: str, favicon_href: str | None) -> tuple[str, ...]:
    return (
        "<!doctype html>",
        document.html_open,
        "<head>",
        _CHARSET_LINE,
        "  " + _VIEWPORT,
        "  " + _STYLESHEET_LINK,
        *(("  " + _favicon_link(favicon_href),) if favicon_href else ()),
        f"  <title>{title}</title>",
        "</head>",
        "<body>",
        document.main_open,
    )


def _favicon_link(favicon_href: str) -> str:
    return f'<link rel="icon" type="image/svg+xml" href="{_attr(favicon_href)}">'


_PAGE_CLOSE = (_MAIN_CLOSING, "</body>", "</html>", "")


def _index_page(
    document: _Document,
    cover: _Cover,
    colophon: tuple[str, ...],
    favicon_href: str | None,
) -> str:
    """The cover page: cover block, contents linking onward, colophon foot.

    The contents entries point at the piece pages instead of the in-document
    anchors ``render_html_edition`` wrote (``edition.html`` keeps those), and
    the navigation gains ``id="contents"`` so the cover block's cue has a
    destination.  Closing plates used to land here; they are filler art now
    dropped with the rest of the print furniture (module docstring).
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
    if not contents[0].lstrip().startswith("<nav "):
        raise ValidationError(
            "web edition expected the contents block to open on its <nav> "
            "line; the semantic body has changed shape"
        )
    contents = (contents[0].replace("<nav ", '<nav id="contents" ', 1),) + contents[1:]
    lines = (
        *_shared_head(document, document.title, favicon_href),
        *cover.index_lines,
        *contents,
        *colophon,
        *_PAGE_CLOSE,
    )
    return "\n".join(lines)


def _piece_page(
    document: _Document,
    piece: _Piece,
    previous: _Piece | None,
    following: _Piece | None,
    masthead: str,
    favicon_href: str | None,
) -> str:
    """One piece on its own page, between a masthead and its page turns.

    Every string on the chrome lines is one the document or the edition
    already carries -- the lockup or publication name and issue in the
    masthead, the neighbours' short titles from their own openings, the
    contents' own heading on the centre turn -- so the pages introduce no
    language of their own, in any language.  The centre turn exists because a
    reader at the end of a long piece has exactly three places to go --
    back, onward, home -- and the masthead answering "home" is a full scroll
    away.
    """

    turns = []
    if previous is not None:
        turns.append(
            f'<a class="page-turn-previous" rel="prev" '
            f'href="{_attr(previous.filename)}">{previous.short_title}</a>'
        )
    turns.append(
        f'<a class="page-turn-contents" href="index.html">{document.contents_label}</a>'
    )
    if following is not None:
        turns.append(
            f'<a class="page-turn-next" rel="next" '
            f'href="{_attr(following.filename)}">{following.short_title}</a>'
        )
    page_turn = (
        '    <nav class="page-turn" data-web-chrome="page-turn">' + "".join(turns) + "</nav>",
    )
    lines = (
        *_shared_head(document, f"{document.publication} — {piece.heading}", favicon_href),
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


def _inject_head(html: str, favicon_href: str | None = None) -> str:
    """Add the viewport, stylesheet and icon links a screen needs and print
    ignores.

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
    injected = ["  " + _VIEWPORT, "  " + _STYLESHEET_LINK]
    if favicon_href:
        injected.append("  " + _favicon_link(favicon_href))
    lines[anchor + 1 : anchor + 1] = injected
    return "\n".join(lines)


def _close_with_colophon(html: str, colophon: tuple[str, ...]) -> str:
    """Close the one-scroll document on the colophon foot.

    Anchored to the one ``  </main>`` closing line -- authored text is always
    escaped, so only the renderer can write it -- and a document without
    exactly one is a shape change and a refusal.
    """

    lines = html.split("\n")
    if lines.count(_MAIN_CLOSING) != 1:
        raise ValidationError(
            "web edition expected exactly one '  </main>' line to anchor the "
            "colophon; the semantic body has changed shape"
        )
    anchor = lines.index(_MAIN_CLOSING)
    lines[anchor:anchor] = list(colophon)
    return "\n".join(lines)


def _insert_cover_block(html: str, block: tuple[str, ...]) -> str:
    """Lead the one-scroll document with the cover, when there is one to lead."""

    if not block:
        return html
    openings = _MAIN_OPENING.findall(html)
    if len(openings) != 1:
        raise ValidationError(
            "web edition expected exactly one '<main>' opening to anchor the "
            "cover block; the semantic body has changed shape"
        )
    return html.replace(openings[0], openings[0] + "\n" + "\n".join(block), 1)


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


def _text(value: object) -> str:
    # Element text for the cover block's own facts: folded into the reader
    # repertoire, then escaped.  No quote education -- the printed cover sets
    # these strings exactly as authored, and the web cover states the same.
    return escape(fold_reader_characters(str(value)), quote=False)
