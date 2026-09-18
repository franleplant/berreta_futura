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
from .manifest import Edition, source_code_payload
from .reader_text import fold_reader_characters


from .cover import _cover_contributors, _cover_date, cover_tab_identity, cover_tab_issue

_VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">'
_STYLESHEET_LINK = '<link rel="stylesheet" href="edition.css">'


_CHARSET_LINE = '  <meta charset="utf-8">'


_MAIN_OPENING = re.compile(r"(?m)^  <main [^\n]*>$")
_MAIN_CLOSING = "  </main>"
_UNSAFE_NAME_CHARACTERS = re.compile(r"[^A-Za-z0-9._-]")


_PRINT_ONLY_LINE = re.compile(
    r'^\s*(?:<figure class="article-tail" '
    r'|<a class="source-link" '
    r'|<figure class="closing-plate" )'
)
_PROVENANCE_SPAN = re.compile(r'<span data-source-id="([^"]*)">(.*?)</span>')


_FIGURE_IMAGE = re.compile(r'(<img src="([^"]*)"[^>]*>)')
_ILLUSTRATED_OPENER_HEADER = re.compile(r'<header\b[^>]*\bclass="article-opener"')
_SOURCE_LINK_LINE = re.compile(
    r'^(?P<indent>\s*)<a class="source-link" '
    r'data-source-link="primary" data-source-id="(?P<source_id>[^"]*)" '
    r'href="(?P<href>[^"]*)">.*</a>$'
)
_PIECE_OPENING = re.compile(r'^    <(article|section) id="([^"]*)"')
_HEADING_LINE = re.compile(r"^\s*<h1>(.*)</h1>$")
_CONTENTS_HEADING = re.compile(r"^\s*<h2>(.*)</h2>$")
_TITLE_LINE = re.compile(r"^  <title>(.*)</title>$")
_SHORT_TITLE = re.compile(r'data-short-title="([^"]*)"')
_CONTENTS_HREF = re.compile(r'href="#([^"]*)"')

_RESERVED_NAMES = frozenset({"index.html", "edition.html", "edition.css"})


_FILLER_ROLES = frozenset({"article_tail", "closing_plate"})


@dataclass(frozen=True, slots=True)
class WebAsset:
    asset: HtmlAsset
    href: str


@dataclass(frozen=True, slots=True)
class WebEdition:
    root: Path
    index: Path
    pages: tuple[Path, ...]
    edition_document: Path
    assets: tuple[WebAsset, ...]


@dataclass(frozen=True, slots=True)
class _Piece:
    lines: tuple[str, ...]
    element_id: str
    short_title: str
    heading: str
    filename: str


@dataclass(frozen=True, slots=True)
class _Document:
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

    semantic = render_html_edition(edition)
    destination.mkdir(parents=True, exist_ok=True)

    web_assets, chrome = _materialize_assets(semantic.assets, destination, wordmark, favicon)
    source_codes = _materialize_source_codes(edition, destination, web_assets)
    html = _install_illustrated_source_codes(semantic.html, source_codes)
    html = _drop_print_only_lines(html)
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
    wordmark: str | None
    favicon: str | None


def _materialize_assets(
    assets: tuple[HtmlAsset, ...],
    destination: Path,
    wordmark: Path | None,
    favicon: Path | None = None,
) -> tuple[tuple[WebAsset, ...], _Chrome]:

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


@dataclass(frozen=True, slots=True)
class CommittedSourceCode:
    directory: Path
    payload: str
    svg: str
    error: str | None
    modules: int | None
    matrix: tuple[str, ...]


def source_code_directory(anchor: Path) -> Path | None:
    for parent in [anchor, *anchor.parents]:
        if (parent / "edition.yaml").is_file():
            return parent / "source-codes"
    return None


def committed_source_codes(directory: Path) -> dict[str, CommittedSourceCode]:
    index = directory / "codes.json"
    if not index.is_file():
        return {}
    import json

    rows = json.loads(index.read_text())["codes"]
    loaded: dict[str, CommittedSourceCode] = {}
    for row in rows:
        printed = row.get("print")
        loaded[row["payload"]] = CommittedSourceCode(
            directory=directory,
            payload=row["payload"],
            svg=row["svg"],
            error=None if printed is None else printed["error"],
            modules=None if printed is None else printed["modules"],
            matrix=() if printed is None else tuple(printed["matrix"]),
        )
    return loaded


def committed_source_code(anchor: Path, payload: str) -> CommittedSourceCode | None:
    directory = source_code_directory(anchor)
    return None if directory is None else committed_source_codes(directory).get(payload)


def _materialize_source_codes(
    edition: Edition,
    destination: Path,
    web_assets: tuple[WebAsset, ...],
) -> dict[str, str]:

    if not any(getattr(article, "opener_art", None) for article in edition.articles):
        return {}
    directory = destination / "assets"
    claimed = {Path(web.href).name.casefold() for web in web_assets}
    result: dict[str, str] = {}
    for article in edition.articles:
        if getattr(article, "opener_art", None) is None or not article.source_url:
            continue
        source_id = article.source_ids[0] if article.source_ids else article.id
        if source_id in result:
            continue
        name = f"source-code-{_sanitize(source_id)}.svg"
        if name.casefold() in claimed:
            raise ValidationError(f"web source-code filename collision at assets/{name}")
        claimed.add(name.casefold())
        asset = committed_source_code(article.manuscript, source_code_payload(article.source_url))
        if asset is None:
            raise ValidationError(
                f"No committed source code for article {article.id}; "
                "regenerate editions/<id>/source-codes"
            )
        (directory / name).write_bytes((asset.directory / asset.svg).read_bytes())
        result[source_id] = f"assets/{name}"
    return result


def _install_illustrated_source_codes(html: str, source_codes: Mapping[str, str]) -> str:

    lines: list[str] = []
    in_illustrated_opener = False
    for line in html.split("\n"):
        if _ILLUSTRATED_OPENER_HEADER.search(line):
            in_illustrated_opener = True
        match = _SOURCE_LINK_LINE.match(line) if in_illustrated_opener else None
        if match is not None:
            source_id = match.group("source_id")
            code = source_codes.get(source_id)
            if code is None:
                raise ValidationError(
                    f"Illustrated opener source link {source_id!r} has no web QR asset"
                )
            line = (
                f'{match.group("indent")}<a class="source-link opener-source-link" '
                f'data-source-link="primary" data-source-id="{source_id}" '
                f'href="{match.group("href")}" aria-label="{match.group("href")}">'
                f'<img class="source-qr" src="{_attr(code)}" alt=""></a>'
            )
        lines.append(line)
        if in_illustrated_opener and line.strip() == "</header>":
            in_illustrated_opener = False
    return "\n".join(lines)


def _drop_print_only_lines(html: str) -> str:
    return "\n".join(line for line in html.split("\n") if not _PRINT_ONLY_LINE.match(line))


def _number_provenance(html: str, source_urls: Mapping[str, str]) -> str:

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

    return "\n".join(
        _FIGURE_IMAGE.sub(r'<a class="figure-link" href="\2">\1</a>', line)
        if line.lstrip().startswith("<figure data-figure-id=")
        else line
        for line in html.split("\n")
    )


def _rewrite_sources(html: str, web_assets: tuple[WebAsset, ...]) -> str:

    replacements: dict[str, str] = {}
    for web in web_assets:
        replacements.setdefault(f'src="{_attr(web.asset.src)}"', f'src="{_attr(web.href)}"')
    for needle, replacement in replacements.items():
        html = html.replace(needle, replacement)
    return html


def _parse_document(html: str) -> _Document:

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
            "web edition expected exactly one '<main>' opening; the semantic body has changed shape"
        )
    start = openings[0]
    try:
        stop = lines.index(_MAIN_CLOSING, start)
    except ValueError:
        raise ValidationError(
            "web edition expected a '  </main>' closing line; the semantic body has changed shape"
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

            sheet = tuple(lines[position : closing + 1])
            contents = sheet if contents is None else contents + sheet
            position = closing + 1
        elif (opened := _PIECE_OPENING.match(line)) is not None:
            closing = _closing_line(lines, position, stop, f"</{opened.group(1)}>")
            pieces.append(_piece(tuple(lines[position : closing + 1]), opened.group(2), claimed))
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
    heading = next((match.group(1) for line in lines if (match := _HEADING_LINE.match(line))), None)
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
    index_lines: tuple[str, ...]
    standalone: tuple[str, ...]


def _cover_lines(
    edition: Edition,
    document: _Document,
    web_assets: tuple[WebAsset, ...],
    wordmark_href: str | None,
    headline_lines: tuple[str, ...] | None,
) -> _Cover:

    art = next((web for web in web_assets if web.asset.role == "cover_art"), None)
    art_lines = (
        ()
        if art is None
        else (
            '    <figure class="cover-art" data-asset-role="cover_art">'
            f'<img src="{_attr(art.href)}" alt="{_attr(art.asset.alt_text)}">'
            "</figure>",
        )
    )
    if wordmark_href is None:
        return _Cover(index_lines=art_lines + document.header, standalone=art_lines)

    headline_text = str(edition.cover.get("headline") or edition.title)
    if headline_lines and " ".join(headline_lines).split() == headline_text.split():
        headline = "".join(
            f'<span class="cover-headline-line">{_text(line)}</span>' for line in headline_lines
        )
    else:
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

    after_headline = (
        next(index for index, line in enumerate(block) if 'class="cover-headline"' in line) + 1
    )
    return _Cover(
        index_lines=block[:after_headline] + (cue,) + block[after_headline:],
        standalone=block,
    )


def _masthead_line(edition: Edition, document: _Document, wordmark_href: str | None) -> str:

    if wordmark_href is None:
        identity = f'<span class="publication-name">{document.publication}</span>'
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

    turns = []
    if previous is not None:
        turns.append(
            f'<a class="page-turn-previous" rel="prev" '
            f'href="{_attr(previous.filename)}">{previous.short_title}</a>'
        )
    turns.append(f'<a class="page-turn-contents" href="index.html">{document.contents_label}</a>')
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

    lines = html.split("\n")
    if lines.count(_CHARSET_LINE) != 1:
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

    target.mkdir(parents=True, exist_ok=True)
    for entry in sorted(source.iterdir(), key=lambda item: item.name):
        if entry.is_dir():
            _copy_tree(entry, target / entry.name)
        else:
            (target / entry.name).write_bytes(entry.read_bytes())


def _attr(value: object) -> str:

    return escape(fold_reader_characters(str(value)), quote=True)


def _text(value: object) -> str:

    return escape(fold_reader_characters(str(value)), quote=False)
