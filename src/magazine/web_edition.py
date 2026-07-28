"""Materialize a validated edition as a self-contained web directory.

The public seam is :func:`write_web_edition`: callers supply an already
validated :class:`~magazine.manifest.Edition` and a destination directory, and
receive that directory filled with everything a browser needs -- ``index.html``,
``edition.css``, every referenced image under ``assets/``, and the bundled
faces under ``fonts/`` -- with no reference back into the repository and no
network fetch.  The semantic HTML itself comes from
:func:`magazine.html_edition.render_html_edition` unchanged; what this adapter
adds is exactly the screen policy that module deliberately leaves out: relative
asset URLs instead of ``file:`` URIs, a viewport, a stylesheet link, and a
visible cover.

Like the print adapter, this module never re-folds or re-escapes the assembled
document: character rules applied to finished markup rewrite tag and attribute
syntax, not prose.  Every insertion is anchored to a line the semantic renderer
is known to emit, and a missing anchor is a refusal, never a silent skip --
an unstyled or unviewable page shipped quietly is the same class of failure as
a blank printed one.
"""

from __future__ import annotations

import re
import shutil
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
# The <main> opening is the anchor for the cover plate: the semantic layer
# records the cover in its asset inventory but paints nothing, because where a
# cover appears is adapter policy -- print splices a PDF, screen leads with it.
_MAIN_OPENING = re.compile(r"(?m)^  <main [^\n]*>$")
_UNSAFE_NAME_CHARACTERS = re.compile(r"[^A-Za-z0-9._-]")


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
    """The written web directory: its root, its entry page, its assets."""

    root: Path
    index: Path
    assets: tuple[WebAsset, ...]


def write_web_edition(edition: Edition, destination: Path) -> WebEdition:
    """Write a validated edition as a browsable directory at ``destination``.

    The output is deterministic -- two runs over the same validated edition
    produce byte-identical trees -- and self-contained: every URL in
    ``index.html`` is relative, every referenced file is under the
    destination, and nothing requires a network or the repository to exist.
    The caller owns the destination; existing files with the same names are
    overwritten, unrelated files are left alone.
    """

    semantic = render_html_edition(edition)
    destination.mkdir(parents=True, exist_ok=True)

    web_assets = _materialize_assets(semantic.assets, destination)
    html = _rewrite_sources(semantic.html, web_assets)
    html = _inject_head(html)
    html = _insert_cover_plate(html, web_assets)
    if 'src="file:' in html:
        raise ValidationError(
            "web edition still references a local file: URI after source "
            "rewriting; either an asset was rendered that the inventory did "
            'not declare, or an authored code span contains a literal src="file: '
            "-- code keeps its straight quotes, so this guard cannot tell the "
            "two apart and refuses both"
        )

    index = destination / "index.html"
    index.write_text(html, encoding="utf-8")
    (destination / "edition.css").write_bytes(_read_screen_css())
    _copy_tree(resources.files("magazine").joinpath("assets", "fonts"), destination / "fonts")
    return WebEdition(root=destination, index=index, assets=web_assets)


def _materialize_assets(
    assets: tuple[HtmlAsset, ...], destination: Path
) -> tuple[WebAsset, ...]:
    """Copy every inventory asset under ``assets/`` with a filesystem-safe name.

    The name is the asset's own id -- already unique and deterministic per
    edition -- with every character outside ``[A-Za-z0-9._-]`` folded to ``-``,
    plus the source file's suffix so browsers and servers can type the bytes.
    Sanitisation cannot merge two distinct ids by construction today, but the
    collision check stays: a silently overwritten image is the kind of failure
    only a reader would catch.

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
        name = _sanitize(asset.id) + _sanitize(asset.path.suffix)
        prior = claimed.get(name.casefold())
        if prior is not None:
            raise ValidationError(
                f"web asset filename collision: {asset.id!r} and {prior!r} "
                f"both sanitize to assets/{name}, compared case-insensitively "
                "because a case-insensitive filesystem would store one file "
                "for both"
            )
        claimed[name.casefold()] = asset.id
        shutil.copyfile(asset.path, directory / name)
        materialized.append(WebAsset(asset=asset, href=f"assets/{name}"))
    return tuple(materialized)


def _sanitize(value: str) -> str:
    return _UNSAFE_NAME_CHARACTERS.sub("-", value)


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


def _insert_cover_plate(html: str, web_assets: tuple[WebAsset, ...]) -> str:
    """Lead the page with the cover, when the edition has one.

    Print splices the cover PDF into the reader's first page; the screen
    equivalent is an ordinary figure at the head of ``<main>``.  The alt text
    is the inventory's own -- the cover headline, or the edition title when no
    headline was authored -- escaped here because the inventory stores authored
    text, not markup.
    """

    cover = next((web for web in web_assets if web.asset.role == "cover_art"), None)
    if cover is None:
        return html
    openings = _MAIN_OPENING.findall(html)
    if len(openings) != 1:
        raise ValidationError(
            "web edition expected exactly one '<main>' opening to anchor the "
            "cover plate; the semantic body has changed shape"
        )
    figure = (
        '    <figure class="cover-plate" data-asset-role="cover_art">'
        f'<img src="{_attr(cover.href)}" alt="{_attr(cover.asset.alt_text)}">'
        "</figure>"
    )
    return html.replace(openings[0], openings[0] + "\n" + figure, 1)


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
