from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from .errors import (
    CoverAssetError,
    CoverMismatchError,
    CoverOverflowError,
    CoverPdfError,
    DependencyError,
)
from .manifest import Edition


# A5 in PostScript points. The SVG viewBox and PDF MediaBox share this space.
PAGE_WIDTH = 419.527559
PAGE_HEIGHT = 595.275591
PROOF_DPI = 144
PRINT_DPI = 300
COVER_COMPILER_VERSION = "10"
ART_SIZE_POINTS = (249.35, 248.65)

INK = "#0a0b0d"
VIOLET = "#4b21c0"
ORANGE = "#f05738"
WHITE = "#ffffff"


@dataclass(frozen=True)
class CoverArtifact:
    language: str
    svg: Path
    pdf: Path
    png: Path
    proof_json: Path
    input_sha256: str
    pdf_sha256: str
    png_sha256: str
    status: str
    cover_art_size_points: tuple[float, float] | None = ART_SIZE_POINTS
    face: str = "front"


@dataclass(frozen=True)
class _OutlinedText:
    markup: str
    width: float
    ascent: float
    descent: float


class _FontOutliner:
    """Convert bundled-font strings into self-contained SVG path geometry."""

    def __init__(self, path: Path):
        try:
            from fontTools.pens.svgPathPen import SVGPathPen
            from fontTools.ttLib import TTFont
        except ImportError as exc:
            raise DependencyError(
                "Cover outlining requires FontTools; run `uv sync --locked`."
            ) from exc
        if not path.is_file():
            raise CoverAssetError(f"Bundled cover font is missing: {path}")
        self._svg_pen = SVGPathPen
        self._glyph_bounds_cache: dict[str, tuple[float, float, float, float] | None] = {}
        self.font = TTFont(path, lazy=False)
        self.glyph_set = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.hmtx = self.font["hmtx"].metrics
        self.units = float(self.font["head"].unitsPerEm)
        self.ascent_units = float(self.font["hhea"].ascent)
        self.descent_units = abs(float(self.font["hhea"].descent))

    def outline(
        self,
        text: str,
        *,
        x: float,
        baseline: float,
        size: float,
        fill: str,
        tracking: float = 0.0,
        horizontal_scale: float = 100.0,
        stroke: str | None = None,
        stroke_width: float = 0.0,
        extra_transform: str = "",
    ) -> _OutlinedText:
        scale = size / self.units
        scale_x = scale * horizontal_scale / 100.0
        cursor = 0.0
        paths: list[str] = []
        for index, character in enumerate(text):
            glyph_name = self.cmap.get(ord(character))
            if glyph_name is None:
                raise CoverAssetError(
                    f"Bundled cover font has no glyph for U+{ord(character):04X} {character!r}"
                )
            advance = self.hmtx[glyph_name][0] * scale_x
            if character != " ":
                pen = self._svg_pen(self.glyph_set)
                self.glyph_set[glyph_name].draw(pen)
                commands = pen.getCommands()
                if commands:
                    paint = f'fill="{fill}"'
                    if stroke and stroke_width:
                        paint += (
                            f' stroke="{stroke}" stroke-width="{stroke_width / scale:.4f}"'
                            ' paint-order="stroke fill"'
                        )
                    paths.append(
                        f'<path d="{commands}" {paint} '
                        f'transform="translate({cursor / scale_x:.5f} 0)"/>'
                    )
            cursor += advance
            if index < len(text) - 1:
                cursor += tracking * horizontal_scale / 100.0
        transform = (
            f"translate({x:.5f} {baseline:.5f}) {extra_transform} "
            f"scale({scale_x:.8f} {-scale:.8f})"
        ).strip()
        return _OutlinedText(
            f'<g transform="{transform}">{"".join(paths)}</g>',
            cursor,
            self.ascent_units * scale,
            self.descent_units * scale,
        )

    def measure(
        self,
        text: str,
        *,
        size: float,
        tracking: float = 0.0,
        horizontal_scale: float = 100.0,
    ) -> float:
        scale = size / self.units * horizontal_scale / 100.0
        width = 0.0
        for index, character in enumerate(text):
            glyph_name = self.cmap.get(ord(character))
            if glyph_name is None:
                raise CoverAssetError(f"Bundled cover font has no glyph for {character!r}")
            width += self.hmtx[glyph_name][0] * scale
            if index < len(text) - 1:
                width += tracking * horizontal_scale / 100.0
        return width

    def ink_extent(self, text: str, *, size: float) -> tuple[float, float]:
        """Measure the inked rise above and drop below the baseline of a line."""
        rise = 0.0
        drop = 0.0
        for character in text:
            glyph_name = self.cmap.get(ord(character))
            if glyph_name is None:
                raise CoverAssetError(f"Bundled cover font has no glyph for {character!r}")
            bounds = self._glyph_bounds(glyph_name)
            if bounds is None:
                continue
            rise = max(rise, bounds[3])
            drop = max(drop, -bounds[1])
        scale = size / self.units
        return rise * scale, drop * scale

    def _glyph_bounds(self, glyph_name: str) -> tuple[float, float, float, float] | None:
        if glyph_name not in self._glyph_bounds_cache:
            from fontTools.pens.boundsPen import BoundsPen

            pen = BoundsPen(self.glyph_set)
            self.glyph_set[glyph_name].draw(pen)
            self._glyph_bounds_cache[glyph_name] = pen.bounds
        return self._glyph_bounds_cache[glyph_name]


class CoverCompiler:
    """Deep module for the canonical SVG -> PDF -> proof cover pipeline."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.design_path = self.root / "design" / "covers" / "canto-vivo" / "design.toml"
        if self.design_path.is_file():
            self.design = tomllib.loads(self.design_path.read_text(encoding="utf-8"))
        else:
            # Installed-package and minimal test projects keep the same stable
            # defaults without requiring repository design files.
            self.design = {
                "id": "canto-vivo/1",
                "color": {"paper": WHITE, "ink": INK, "violet": VIOLET, "orange": ORANGE},
                "tab": {
                    "width": 21.0, "overdraw": 1.5, "issue_top": 26.5,
                    "identity_top": 433.5, "edge_reveal": 1.4,
                },
                "wordmark": {"x": 38.0, "top": 53.0, "right_reserve": 78.0},
                "headline": {"x": 44.0, "top": 122.0, "width": 302.0},
                "art": {"x": 85.25, "top": 221.85, "width": 249.35, "height": 248.65},
                "deck": {"top": 493.0, "size": 5.5, "wrap_size": 6.7, "leading": 8.4, "horizontal_scale": 108.0, "tracking": .35},
                "footer": {"x": 44.0, "bottom": 20.0, "size": 7.0, "tracking": 1.85},
                "back": {
                    "overdraw": 1.5, "rail_width": 42.0, "rail_top": 32.0,
                    "rail_size": 8.0, "rail_tracking": 1.6, "mass_x": 6.0,
                    "mass_top": 38.0, "mass_size": 116.0, "mass_leading": 84.68,
                    "mass_tracking": -12.18, "panel_x": 38.0, "panel_top": 242.0,
                    "panel_right": 62.0, "panel_bottom": 52.0, "panel_padding": 30.0,
                    "statement_max_size": 24.0,
                    "statement_min_size": 18.0, "statement_leading_ratio": 1.05,
                    "slug_x": 38.0, "slug_bottom": 26.0, "slug_size": 7.0,
                    "slug_tracking": 1.6,
                },
            }
        self.colors = self.design["color"]
        self.proof_dpi = int(self.design.get("proof_dpi", PROOF_DPI))
        self.print_dpi = int(self.design.get("production_dpi", PRINT_DPI))
        art = self.design["art"]
        self.art_size = (float(art["width"]), float(art["height"]))
        fonts = Path(__file__).with_name("assets") / "fonts" / "inter"
        self.regular = _FontOutliner(fonts / "Inter-Regular.ttf")
        self.bold = _FontOutliner(fonts / "Inter-Bold.ttf")
        serif = Path(__file__).with_name("assets") / "fonts" / "source-serif-4"
        self.serif = _FontOutliner(serif / "SourceSerif4SmText-Regular.ttf")

    def compile(
        self,
        edition: Edition,
        destination: Path,
        *,
        reference: Path | None = None,
        check: bool = False,
    ) -> CoverArtifact:
        """Compile one localized edition cover and retain all proof evidence."""
        return self._compile_face(
            edition,
            destination,
            face="front",
            reference=reference,
            check=check,
        )

    def compile_back(
        self,
        edition: Edition,
        destination: Path,
        *,
        reference: Path | None = None,
        check: bool = False,
    ) -> CoverArtifact:
        """Compile the localized back cover through the same proof pipeline."""
        return self._compile_face(
            edition,
            destination,
            face="back",
            reference=reference,
            check=check,
        )

    def _compile_face(
        self,
        edition: Edition,
        destination: Path,
        *,
        face: str,
        reference: Path | None,
        check: bool,
    ) -> CoverArtifact:
        destination = destination.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        svg_path = destination / "cover.svg"
        pdf_path = destination / "cover.pdf"
        png_path = destination / "cover.png"
        proof_path = destination / "proof.json"

        svg = (
            self._materialize_svg(edition)
            if face == "front"
            else self._materialize_back_svg(edition)
        )
        digest = self._input_digest(edition, svg, face=face)
        if svg_path.is_file() and pdf_path.is_file() and png_path.is_file() and proof_path.is_file():
            try:
                previous = json.loads(proof_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                previous = {}
            if (
                previous.get("input_sha256") == digest
                and svg_path.read_text(encoding="utf-8") == svg
            ):
                comparison = self._compare(png_path, reference, destination)
                previous["comparison"] = comparison
                proof_path.write_text(
                    json.dumps(previous, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                status = str(comparison["status"])
                if check and status != "matched":
                    raise CoverMismatchError(
                        f"Cover proof is {status}; inspect {destination / 'diff.png'} and {proof_path}"
                    )
                return CoverArtifact(
                    edition.language,
                    svg_path,
                    pdf_path,
                    png_path,
                    proof_path,
                    digest,
                    _sha256(pdf_path),
                    _sha256(png_path),
                    status,
                    self.art_size if face == "front" else None,
                    face,
                )
        svg_path.write_text(svg, encoding="utf-8")
        self._svg_to_pdf(svg.encode("utf-8"), pdf_path, edition, face=face)
        self._validate_pdf(pdf_path)
        self._rasterize_pdf(pdf_path, png_path)

        comparison = self._compare(png_path, reference, destination)
        status = comparison["status"]
        manifest = {
            "schema_version": 1,
            "edition_id": edition.id,
            "language": edition.language,
            "face": face,
            "design": str(self.design["id"]),
            "input_sha256": digest,
            "pdf_sha256": _sha256(pdf_path),
            "png_sha256": _sha256(png_path),
            "page_points": [PAGE_WIDTH, PAGE_HEIGHT],
            "raster_dpi": self.proof_dpi,
            "production_raster_dpi": self.print_dpi,
            "proof_source": "cover.pdf",
            "production_source": "cover.pdf",
            "cover_art_size_points": list(self.art_size) if face == "front" else None,
            "comparison": comparison,
        }
        proof_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if check and status != "matched":
            raise CoverMismatchError(
                f"Cover proof is {status}; inspect {destination / 'diff.png'} and {proof_path}"
            )
        return CoverArtifact(
            edition.language,
            svg_path,
            pdf_path,
            png_path,
            proof_path,
            digest,
            manifest["pdf_sha256"],
            manifest["png_sha256"],
            status,
            self.art_size if face == "front" else None,
            face,
        )

    def _tab_band(self) -> tuple[float, float]:
        """Return the printed fore-edge band as (x, width) in page points.

        The band's inner edge is fixed by the design grid; `edge_reveal` is
        taken off its outer edge, so the page keeps a hairline of unprinted
        paper between the band and the right trim.
        """
        tab = self.design["tab"]
        width = float(tab["width"])
        reveal = float(tab.get("edge_reveal", 0.0))
        return PAGE_WIDTH - width, width - reveal

    def _materialize_svg(self, edition: Edition) -> str:
        tab = self.design["tab"]
        paper = str(self.colors["paper"])
        orange = str(self.colors["orange"])
        band_x, band_width = self._tab_band()
        parts: list[str] = [
            f'<rect data-slot="paper" x="0" y="0" width="{PAGE_WIDTH}" '
            f'height="{PAGE_HEIGHT}" fill="{paper}"/>',
            # One solid band, bleeding off the head and the foot only: the
            # vertical overdraw is clipped by the SVG viewport and later the PDF
            # MediaBox, while the right edge stops short of the trim so the
            # reserve stays unprinted paper.
            f'<rect data-slot="edge-tab" x="{band_x:.5f}" '
            f'y="{-float(tab["overdraw"]):.5f}" '
            f'width="{band_width:.5f}" '
            f'height="{PAGE_HEIGHT + float(tab["overdraw"]) * 2:.5f}" fill="{orange}"/>',
        ]
        parts.extend(self._wordmark(edition.publication_name))
        parts.extend(self._headline(str(edition.cover.get("headline", edition.title))))

        art_spec = self.design["art"]
        art_x, art_y = float(art_spec["x"]), float(art_spec["top"])
        art_w, art_h = self.art_size
        if edition.cover_art:
            if not edition.cover_art.is_file():
                raise CoverAssetError(f"Cover art is missing: {edition.cover_art}")
            art_bytes = self._graded_art(edition.cover_art)
            art_data = base64.b64encode(art_bytes).decode("ascii")
            parts.append(
                f'<image data-slot="art" x="{art_x}" y="{art_y}" width="{art_w}" '
                f'height="{art_h}" preserveAspectRatio="xMidYMid slice" '
                f'href="data:image/png;base64,{art_data}"/>'
            )
        else:
            # Deterministic fixture/provisional fallback; production editions
            # should supply committed cover art before review.
            parts.append(
                f'<g data-slot="art"><rect x="{art_x}" y="{art_y}" width="{art_w}" '
                f'height="{art_h}" fill="{self.colors["violet"]}"/><circle cx="{art_x + art_w / 2}" '
                f'cy="{art_y + art_h / 2}" r="56" fill="none" stroke="{paper}"/></g>'
            )
        parts.append(
            f'<rect data-slot="art-border" x="{art_x}" y="{art_y}" width="{art_w}" '
            f'height="{art_h}" fill="none" stroke="{self.colors["ink"]}" stroke-width=".7"/>'
        )
        parts.extend(self._deck(_cover_contributors(edition), art_x, art_w))
        footer = self.design["footer"]
        parts.append(
            '<g data-slot="footer">'
            + self.bold.outline(
                _cover_date(edition.publication_date),
                x=float(footer["x"]),
                baseline=PAGE_HEIGHT - float(footer["bottom"]),
                size=float(footer["size"]),
                fill=str(self.colors["ink"]),
                tracking=float(footer["tracking"]),
            ).markup
            + '</g>'
        )
        parts.extend(self._tab_labels(edition))
        body = "\n    ".join(parts)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_WIDTH}pt" '
            f'height="{PAGE_HEIGHT}pt" viewBox="0 0 {PAGE_WIDTH} {PAGE_HEIGHT}" '
            'overflow="hidden">\n'
            '  <title>Berreta Futura cover</title>\n'
            f'  <g id="cover" data-design="{escape(str(self.design["id"]))}">\n    {body}\n  </g>\n'
            '</svg>\n'
        )

    def _materialize_back_svg(self, edition: Edition) -> str:
        """Materialize the selected Signal fold back cover as outlined SVG."""
        back = self.design["back"]
        orange = str(self.colors["orange"])
        ink = str(self.colors["ink"])
        violet = str(self.colors["violet"])
        paper = str(self.colors["paper"])
        overdraw = float(back["overdraw"])
        rail_width = float(back["rail_width"])
        mass_x = float(back["mass_x"])
        mass_size = float(back["mass_size"])
        mass_tracking = float(back["mass_tracking"])
        mass_words = _back_cover_copy(edition, "mass")
        mass_max_width = PAGE_WIDTH - rail_width - mass_x + 4.0
        while mass_size >= 72.0 and any(
            self.bold.measure(word, size=mass_size, tracking=mass_tracking) > mass_max_width
            for word in mass_words
        ):
            mass_size -= .5
        if mass_size < 72.0:
            raise CoverOverflowError(
                f"Back-cover display words cannot fit: {' / '.join(mass_words)}"
            )
        mass_top = float(back["mass_top"])
        mass_leading = float(back["mass_leading"]) * mass_size / float(back["mass_size"])
        mass_paths = []
        for index, word in enumerate(mass_words):
            mass_paths.append(
                self.bold.outline(
                    word,
                    x=mass_x,
                    baseline=mass_top + mass_size + index * mass_leading,
                    size=mass_size,
                    fill=violet if index == 0 else ink,
                    tracking=mass_tracking,
                ).markup
            )

        panel_x = float(back["panel_x"])
        panel_top = float(back["panel_top"])
        panel_width = PAGE_WIDTH - panel_x - float(back["panel_right"])
        # panel_bottom is the floor: the panel may never intrude on the slug
        # zone, but its actual height hugs the measured statement block so the
        # white insert always carries equal, generous padding on every side.
        panel_max_height = PAGE_HEIGHT - panel_top - float(back["panel_bottom"])
        panel_padding = float(back["panel_padding"])
        statement = str(
            edition.cover.get("back_text", _back_cover_copy(edition, "back_text_default"))
        ).strip()
        statement_size, statement_lines, statement_rise, statement_block = (
            self._fit_back_statement(
                statement,
                panel_width - panel_padding * 2,
                panel_max_height - panel_padding * 2,
            )
        )
        panel_height = statement_block + panel_padding * 2
        statement_leading = statement_size * float(back["statement_leading_ratio"])
        statement_paths = [
            self.serif.outline(
                line,
                x=panel_x + panel_padding,
                baseline=panel_top + panel_padding + statement_rise + index * statement_leading,
                size=statement_size,
                fill=ink,
                tracking=-.12,
            ).markup
            for index, line in enumerate(statement_lines)
        ]

        slug = f'{_back_cover_copy(edition, "end")} / {_cover_date(edition.publication_date)}'
        slug_path = self.bold.outline(
            slug,
            x=float(back["slug_x"]),
            baseline=PAGE_HEIGHT - float(back["slug_bottom"]),
            size=float(back["slug_size"]),
            fill=paper,
            tracking=float(back["slug_tracking"]),
        ).markup

        label = _back_cover_copy(edition, "issue")
        identity = (
            f"{edition.publication_name.upper()} / {label} "
            f"{str(edition.issue_number).zfill(3)} / BUENOS AIRES"
        )
        rail_size = float(back["rail_size"])
        rail_tracking = float(back["rail_tracking"])
        rail_scale = 100.0
        rail_max_length = PAGE_HEIGHT - float(back["rail_top"]) - 28.0
        while (
            rail_scale >= 70.0
            and self.bold.measure(
                identity,
                size=rail_size,
                tracking=rail_tracking,
                horizontal_scale=rail_scale,
            ) > rail_max_length
        ):
            rail_scale -= 1.0
        if rail_scale < 70.0:
            raise CoverOverflowError(f"Back-cover identity rail cannot fit: {identity}")
        rail = self.bold.outline(
            identity,
            x=0,
            baseline=0,
            size=rail_size,
            fill=ink,
            tracking=rail_tracking,
            horizontal_scale=rail_scale,
        )
        rail_x = (
            PAGE_WIDTH
            - rail_width / 2
            - (rail.ascent - rail.descent) / 2
        )
        rail_path = (
            f'<g transform="translate({rail_x:.5f} {float(back["rail_top"]):.5f}) rotate(90)">'
            f'{rail.markup}</g>'
        )

        parts = [
            f'<rect data-slot="field" x="{-overdraw}" y="{-overdraw}" '
            f'width="{PAGE_WIDTH + overdraw * 2}" height="{PAGE_HEIGHT + overdraw * 2}" '
            f'fill="{orange}"/>',
            f'<defs><clipPath id="mass-safe" clipPathUnits="userSpaceOnUse">'
            f'<rect x="0" y="0" width="{PAGE_WIDTH - rail_width}" height="{PAGE_HEIGHT}"/>'
            f'</clipPath></defs>',
            f'<g data-slot="mass" clip-path="url(#mass-safe)">{"".join(mass_paths)}</g>',
            f'<rect data-slot="statement-panel" x="{panel_x}" y="{panel_top}" '
            f'width="{panel_width}" height="{panel_height}" fill="{paper}"/>',
            f'<g data-slot="statement">{"".join(statement_paths)}</g>',
            f'<g data-slot="slug">{slug_path}</g>',
            f'<g data-slot="identity-label">{rail_path}</g>',
        ]
        body = "\n    ".join(parts)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_WIDTH}pt" '
            f'height="{PAGE_HEIGHT}pt" viewBox="0 0 {PAGE_WIDTH} {PAGE_HEIGHT}" '
            'overflow="hidden">\n'
            '  <title>Berreta Futura back cover</title>\n'
            f'  <g id="back-cover" data-design="{escape(str(self.design["id"]))}">\n'
            f'    {body}\n  </g>\n'
            '</svg>\n'
        )

    def _fit_back_statement(
        self,
        text: str,
        width: float,
        height: float,
    ) -> tuple[float, list[str], float, float]:
        """Fit the statement, returning size, lines, first-line rise, block height.

        The block height is the measured ink extent — first-line rise above its
        baseline, the baseline-to-baseline run, and the last line's descender
        drop — so the surrounding panel padding is optically true.
        """
        back = self.design["back"]
        size = float(back["statement_max_size"])
        minimum = float(back["statement_min_size"])
        leading_ratio = float(back["statement_leading_ratio"])
        while size >= minimum:
            lines = self._wrap(text, self.serif, size, width)
            if lines:
                rise, _ = self.serif.ink_extent(lines[0], size=size)
                _, drop = self.serif.ink_extent(lines[-1], size=size)
                block = rise + (len(lines) - 1) * size * leading_ratio + drop
                if block <= height:
                    return size, lines, rise, block
            size -= .5
        raise CoverOverflowError(f"Back-cover issue statement cannot fit: {text}")

    def _wordmark(self, publication_name: str) -> list[str]:
        value = publication_name.upper().strip()
        head, separator, tail = value.rpartition(" ")
        if not separator:
            head, tail = value, ""
        wordmark = self.design["wordmark"]
        x, top = float(wordmark["x"]), float(wordmark["top"])
        pdf_baseline = PAGE_HEIGHT - top
        baseline = PAGE_HEIGHT - (pdf_baseline - 1.65)
        size = 42.0
        tracking = -3.6
        head_scale = 89.9
        max_width = PAGE_WIDTH - float(self.design["tab"]["width"]) - float(wordmark["right_reserve"])
        while size >= 25:
            head_width = self.bold.measure(
                head, size=size, tracking=tracking, horizontal_scale=head_scale
            )
            tail_width = self.bold.measure(
                tail, size=size, tracking=tracking, horizontal_scale=105.1
            ) if tail else 0
            tail_offset = size * (97 / 42)
            box_width = tail_width + (13 if tail else 0)
            if max(head_width, tail_offset + box_width) <= max_width:
                break
            size -= .5
        if size < 25:
            raise CoverOverflowError(f"Publication wordmark cannot fit: {publication_name}")
        head_path = self.bold.outline(
            head,
            x=x + .36,
            baseline=baseline,
            size=size,
            fill=str(self.colors["ink"]),
            tracking=tracking,
            horizontal_scale=head_scale,
            stroke=str(self.colors["ink"]),
            stroke_width=.30,
        ).markup
        if not tail:
            return [f'<g data-slot="wordmark">{head_path}</g>']

        tail_x = x + tail_offset
        # Convert the old PDF group origin to SVG top-axis coordinates.
        tail_origin_y = PAGE_HEIGHT - (pdf_baseline - size * .91)
        box_x, box_y = -7.0, -7.0
        box_height = size * 1.04 - 1
        box_width = tail_width + 13
        slug_y = box_y - 1
        center_x = box_x + box_width / 2
        center_y = box_y + box_height / 2
        skew = math.tan(math.radians(-10))
        group = (
            f'translate({tail_x:.5f} {tail_origin_y:.5f}) '
            f'translate({center_x:.5f} {-center_y:.5f}) matrix(1 0 {skew:.8f} 1 0 0) '
            f'translate({-center_x:.5f} {center_y:.5f})'
        )
        slug = (
            f'<path d="M {box_x} {-slug_y} H {box_x + box_width} '
            f'V {-slug_y - (box_height + .65)} H {box_x} Z" fill="{self.colors["ink"]}"/>'
        )
        orange = self.bold.outline(
            tail,
            x=-13,
            baseline=-1.65,
            size=size,
            fill=str(self.colors["orange"]),
            tracking=tracking,
            horizontal_scale=106.6,
            stroke=str(self.colors["orange"]),
            stroke_width=.15,
        ).markup
        white = self.bold.outline(
            tail,
            x=0,
            baseline=-1.65,
            size=size,
            fill=str(self.colors["paper"]),
            tracking=tracking,
            horizontal_scale=105.1,
            stroke=str(self.colors["paper"]),
            stroke_width=.30,
        ).markup
        return [
            f'<g data-slot="wordmark">{head_path}<g transform="{group}">{slug}{orange}{white}</g></g>'
        ]

    def _headline_layout(self, value: str, *, described_as: str | None = None) -> tuple[list[str], float]:
        """The headline's line construction: balanced lines and the fitted size.

        Shared between the printed face (:meth:`_headline`) and the web
        cover's :func:`cover_headline_lines`, so both media break the issue
        title on the same words for the same measured reasons.
        """

        size = 29.0
        headline = self.design["headline"]
        width = float(headline["width"])
        words = value.split()
        while size >= 20:
            candidates: list[tuple[float, tuple[str, str]]] = []
            if len(words) >= 2:
                for split in range(1, len(words)):
                    pair = (" ".join(words[:split]), " ".join(words[split:]))
                    widths = tuple(self.bold.measure(line, size=size) for line in pair)
                    if max(widths) <= width / .795:
                        candidates.append((abs(widths[0] - widths[1]), pair))
            if candidates:
                lines = list(min(candidates, key=lambda item: item[0])[1])
            else:
                lines = self._wrap(value, self.bold, size, width / .795)
            if len(lines) <= 3:
                break
            size -= .5
        if size < 20:
            raise CoverOverflowError(
                f"Cover headline cannot fit: {described_as if described_as is not None else value}"
            )
        return lines, size

    def _headline(self, text: str) -> list[str]:
        value = text.upper().strip()
        headline = self.design["headline"]
        lines, size = self._headline_layout(value, described_as=text)
        baseline = float(headline["top"]) + size
        leading = size * .78
        colors = (str(self.colors["ink"]), str(self.colors["violet"]), str(self.colors["ink"]))
        paths = []
        for index, line in enumerate(lines):
            line_size = 28.0 if index % 2 else size
            paths.append(
                self.bold.outline(
                    line,
                    x=float(headline["x"]) + (23 if index % 2 else -.65),
                    baseline=baseline + (1 if index % 2 else 0),
                    size=line_size,
                    fill=colors[index],
                    horizontal_scale=80.9 if index % 2 else 79.83,
                    tracking=-1.35,
                    stroke=colors[index] if index % 2 == 0 else None,
                    stroke_width=.09 if index % 2 == 0 else 0,
                ).markup
            )
            baseline += leading
        return [f'<g data-slot="headline">{"".join(paths)}</g>']

    def _deck(self, text: str, x: float, width: float) -> list[str]:
        if not text:
            return ['<g data-slot="deck"/>']
        deck = self.design["deck"]
        lines = self._wrap(text, self.regular, float(deck["wrap_size"]), width)
        if len(lines) > 5:
            raise CoverOverflowError(f"Cover deck cannot fit: {text}")
        baseline = float(deck["top"]) + float(deck["size"])
        paths = [
            self.regular.outline(
                line,
                x=x - (.65 if index == 0 else 0),
                baseline=baseline + index * float(deck["leading"]),
                size=float(deck["size"]),
                fill=str(self.colors["ink"]),
                horizontal_scale=float(deck["horizontal_scale"]),
                tracking=float(deck.get("tracking", 0)),
            ).markup
            for index, line in enumerate(lines)
        ]
        return [f'<g data-slot="deck">{"".join(paths)}</g>']

    def _tab_labels(self, edition: Edition) -> list[str]:
        issue = cover_tab_issue(edition)
        identity = cover_tab_identity(edition)
        tab = self.design["tab"]
        band_x, band_width = self._tab_band()

        def vertical(text: str, top: float, size: float, tracking: float, scale: float = 100):
            outlined = self.bold.outline(
                text,
                x=0,
                baseline=0,
                size=size,
                fill=str(self.colors["ink"]),
                tracking=tracking,
                horizontal_scale=scale,
            )
            # Center the glyph body across the printed band, then advance
            # top-to-bottom. Centring on the band and not on the tab's full
            # width keeps the type seated in the orange the reader sees.
            cross = band_x + band_width / 2 - (outlined.ascent - outlined.descent) / 2
            return (
                f'<g transform="translate({cross:.5f} {top:.5f}) rotate(90)">'
                f'{outlined.markup}</g>'
            )

        return [
            f'<g data-slot="issue-label">{vertical(issue, float(tab["issue_top"]), 7.4, 1.6)}</g>',
            f'<g data-slot="identity-label">{vertical(identity, float(tab["identity_top"]), 4.8, 1.6, 103)}</g>',
        ]

    @staticmethod
    def _wrap(text: str, font: _FontOutliner, size: float, width: float) -> list[str]:
        lines: list[str] = []
        current = ""
        for word in text.split():
            candidate = f"{current} {word}".strip()
            if current and font.measure(candidate, size=size) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines

    @staticmethod
    def _graded_art(path: Path) -> bytes:
        """Apply the explicitly versioned Canto vivo two-ink grade."""
        try:
            from PIL import Image
        except ImportError as exc:
            raise DependencyError("Cover artwork requires Pillow; run `uv sync --locked`.") from exc
        with Image.open(path) as source:
            image = source.convert("RGB")
        graded = []
        for red, green, blue in image.get_flattened_data():
            if blue > 120 and blue > red * 1.7 and blue > green * 1.7:
                graded.append((round(red * .96), min(255, round(green * 1.12)), round(blue * .953)))
            elif red > 170 and red > green * 1.8 and green > blue * 1.5:
                graded.append((round(red * .916), min(255, round(green * 1.146)), min(255, blue + 45)))
            else:
                graded.append((red, green, blue))
        image.putdata(graded)
        output = io.BytesIO()
        image.save(output, format="PNG", optimize=False)
        return output.getvalue()

    def _svg_to_pdf(
        self,
        svg: bytes,
        output: Path,
        edition: Edition,
        *,
        face: str = "front",
    ) -> None:
        try:
            import resvg
            from reportlab.lib.colors import HexColor
            from reportlab.lib.pagesizes import A5
            from reportlab.lib.utils import ImageReader
            from reportlab.pdfgen import canvas
        except ImportError as exc:
            raise DependencyError(
                "Cover PDF conversion requires resvg and ReportLab; run `uv sync --locked`."
            ) from exc
        try:
            pixel_width = round(PAGE_WIDTH / 72 * self.print_dpi)
            pixel_height = round(PAGE_HEIGHT / 72 * self.print_dpi)
            raster_svg = re.sub(
                rb'width="[^"]+" height="[^"]+"',
                f'width="{pixel_width}" height="{pixel_height}"'.encode("ascii"),
                svg,
                count=1,
            )
            # The PDF owns the paper as a vector rectangle. Rendering the
            # paper into a scaled full-page bitmap can turn white into periodic
            # 254-gray interpolation lines in Poppler.
            raster_svg = re.sub(
                rb'(<rect data-slot="paper"[^>]*?) fill="[^"]+"',
                rb'\1 fill="none"',
                raster_svg,
                count=1,
            )
            raster_svg = re.sub(
                rb'(<rect data-slot="edge-tab"[^>]*?) fill="[^"]+"',
                rb'\1 fill="none"',
                raster_svg,
                count=1,
            )
            raster_svg = re.sub(
                rb'(<rect data-slot="field"[^>]*?) fill="[^"]+"',
                rb'\1 fill="none"',
                raster_svg,
                count=1,
            )
            options = resvg.usvg.Options.default()
            tree = resvg.usvg.Tree.from_str(raster_svg.decode("utf-8"), options)
            # resvg follows affine.Affine's (a, b, c, d, e, f) ordering;
            # identity is therefore (1, 0, 0, 0, 1, 0), not the PDF matrix order.
            png = resvg.render(tree, (1, 0, 0, 0, 1, 0))
            pdf = canvas.Canvas(
                str(output),
                pagesize=A5,
                pageCompression=1,
                invariant=1,
            )
            pdf.setTitle(f"Berreta Futura {face} cover")
            pdf.setCreator("magazine-compiler cover pipeline")
            if face == "front":
                pdf.setFillColorRGB(1, 1, 1)
                pdf.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
                # One vector band over the vector paper. The reserve at the
                # right trim is the paper rectangle itself showing through, so
                # the hairline is unprinted rather than painted white.
                tab_overdraw = float(self.design["tab"]["overdraw"])
                band_x, band_width = self._tab_band()
                pdf.setFillColor(HexColor(str(self.colors["orange"])))
                pdf.rect(
                    band_x,
                    -tab_overdraw,
                    band_width,
                    PAGE_HEIGHT + tab_overdraw * 2,
                    fill=1,
                    stroke=0,
                )
            else:
                overdraw = float(self.design["back"]["overdraw"])
                pdf.setFillColor(HexColor(str(self.colors["orange"])))
                pdf.rect(
                    -overdraw,
                    -overdraw,
                    PAGE_WIDTH + overdraw * 2,
                    PAGE_HEIGHT + overdraw * 2,
                    fill=1,
                    stroke=0,
                )
            pdf.drawImage(
                ImageReader(io.BytesIO(png)),
                0,
                0,
                PAGE_WIDTH,
                PAGE_HEIGHT,
                preserveAspectRatio=False,
                mask="auto",
            )
            pdf.saveState()
            try:
                if face == "front":
                    self._add_selectable_text_layer(pdf, edition)
                else:
                    self._add_selectable_back_text_layer(pdf, edition)
            finally:
                pdf.restoreState()
            pdf.showPage()
            pdf.save()
        except Exception as exc:
            raise CoverPdfError(f"Could not convert cover SVG to PDF: {exc}") from exc

    def _add_selectable_text_layer(self, pdf, edition: Edition) -> None:
        """Add invisible bundled-font text so outlined cover copy stays selectable."""
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except ImportError as exc:
            raise DependencyError(
                "Selectable cover text requires ReportLab; run `uv sync --locked`."
            ) from exc
        font_path = Path(__file__).with_name("assets") / "fonts" / "inter" / "Inter-Regular.ttf"
        font_name = "CoverSelectableInter"
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))

        def invisible_line(
            value: str,
            x: float,
            y: float,
            size: float,
            *,
            horizontal_scale: float = 100.0,
            tracking: float = 0.0,
        ) -> None:
            text = pdf.beginText()
            text.setTextRenderMode(3)
            text.setTextOrigin(x, y)
            text.setFont(font_name, size)
            text.setHorizScale(horizontal_scale)
            text.setCharSpace(tracking)
            text.textLine(value)
            pdf.drawText(text)

        # Reading order follows the cover's information hierarchy. Geometry is
        # close to the outlined artwork so selection highlights the visible copy.
        invisible_line(edition.publication_name.upper(), 38.0, PAGE_HEIGHT - 55.0, 22.0)
        invisible_line(
            str(edition.cover.get("headline", edition.title)).upper(),
            44.0,
            PAGE_HEIGHT - 151.0,
            16.0,
        )
        deck = self.design["deck"]
        contributors = _cover_contributors(edition)
        lines = self._wrap(
            contributors,
            self.regular,
            float(deck["wrap_size"]),
            self.art_size[0],
        )
        baseline = float(deck["top"]) + float(deck["size"])
        for index, line in enumerate(lines):
            invisible_line(
                line,
                float(self.design["art"]["x"]),
                PAGE_HEIGHT - (baseline + index * float(deck["leading"])),
                float(deck["size"]),
                horizontal_scale=float(deck["horizontal_scale"]),
                tracking=float(deck.get("tracking", 0)),
            )
        footer = self.design["footer"]
        invisible_line(
            _cover_date(edition.publication_date),
            float(footer["x"]),
            float(footer["bottom"]),
            float(footer["size"]),
            tracking=float(footer["tracking"]),
        )

    def _add_selectable_back_text_layer(self, pdf, edition: Edition) -> None:
        """Mirror the outlined Signal fold copy with invisible embedded text."""
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except ImportError as exc:
            raise DependencyError(
                "Selectable back-cover text requires ReportLab; run `uv sync --locked`."
            ) from exc
        font_path = Path(__file__).with_name("assets") / "fonts" / "inter" / "Inter-Regular.ttf"
        font_name = "BackCoverSelectableInter"
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))

        def invisible_line(
            value: str,
            x: float,
            y: float,
            size: float,
            *,
            horizontal_scale: float = 100.0,
        ) -> None:
            text = pdf.beginText()
            text.setTextRenderMode(3)
            text.setTextOrigin(x, y)
            text.setFont(font_name, size)
            text.setHorizScale(horizontal_scale)
            text.textLine(value)
            pdf.drawText(text)

        first, second = _back_cover_copy(edition, "mass")
        invisible_line(first, 6.0, PAGE_HEIGHT - 90.0, 20.0)
        invisible_line(second, 6.0, PAGE_HEIGHT - 170.0, 20.0)
        statement = str(
            edition.cover.get("back_text", _back_cover_copy(edition, "back_text_default"))
        ).strip()
        for index, line in enumerate(self._wrap(statement, self.regular, 10.0, 260.0)):
            invisible_line(line, 68.0, PAGE_HEIGHT - 300.0 - index * 12.0, 10.0)
        invisible_line(
            f'{_back_cover_copy(edition, "end")} / {_cover_date(edition.publication_date)}',
            38.0,
            26.0,
            7.0,
        )
        invisible_line(
            f'{edition.publication_name.upper()} / {_back_cover_copy(edition, "issue")} '
            f'{str(edition.issue_number).zfill(3)} / BUENOS AIRES',
            38.0,
            10.0,
            5.5,
            horizontal_scale=88.0,
        )

    @staticmethod
    def _validate_pdf(path: Path) -> None:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise DependencyError("Cover validation requires pypdf; run `uv sync --locked`.") from exc
        reader = PdfReader(path)
        if len(reader.pages) != 1:
            raise CoverPdfError(f"Cover PDF must contain exactly one page: {path}")
        box = reader.pages[0].mediabox
        width, height = float(box.width), float(box.height)
        if abs(width - PAGE_WIDTH) > .02 or abs(height - PAGE_HEIGHT) > .02:
            raise CoverPdfError(
                f"Cover PDF is {width:.3f} x {height:.3f}pt; expected A5 "
                f"{PAGE_WIDTH:.3f} x {PAGE_HEIGHT:.3f}pt"
            )

    def _rasterize_pdf(self, pdf: Path, png: Path) -> None:
        executable = shutil.which("pdftoppm")
        if not executable:
            raise DependencyError("Cover proofing requires Poppler's pdftoppm executable.")
        with tempfile.TemporaryDirectory(prefix="mag-cover-") as directory:
            prefix = Path(directory) / "cover"
            completed = subprocess.run(
                [executable, "-f", "1", "-singlefile", "-png", "-r", str(self.proof_dpi), str(pdf), str(prefix)],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode:
                detail = completed.stderr.strip() or completed.stdout.strip()
                raise CoverPdfError(f"Could not rasterize cover PDF: {detail}")
            shutil.copyfile(prefix.with_suffix(".png"), png)

    @staticmethod
    def _compare(png: Path, reference: Path | None, destination: Path) -> dict[str, object]:
        if reference is None:
            return {"status": "uncompared", "reference": None}
        if not reference.is_file():
            return {"status": "missing_reference", "reference": str(reference)}
        from PIL import Image, ImageChops, ImageEnhance

        with Image.open(png) as opened:
            actual = opened.convert("RGB")
        with Image.open(reference) as opened:
            expected = opened.convert("RGB")
        if expected.size != actual.size:
            expected = expected.resize(actual.size, Image.Resampling.LANCZOS)
        diff = ImageChops.difference(actual, expected)
        bbox = diff.getbbox()
        histogram = diff.convert("L").histogram()
        changed = sum(histogram[1:])
        mean = sum(index * count for index, count in enumerate(histogram)) / max(1, actual.width * actual.height)
        overlay = Image.blend(expected, actual, .5)
        overlay.save(destination / "overlay.png")
        ImageEnhance.Contrast(diff).enhance(4).save(destination / "diff.png")
        return {
            "status": "matched" if bbox is None else "changed",
            "reference": str(reference.resolve()),
            "reference_sha256": _sha256(reference),
            "changed_pixels": changed,
            "mean_absolute_difference": round(mean, 4),
            "bounds": list(bbox) if bbox else None,
        }

    def _input_digest(self, edition: Edition, svg: str, *, face: str = "front") -> str:
        payload = {
            "edition": edition.id,
            "compiler": COVER_COMPILER_VERSION,
            "face": face,
            "design": self.design,
            "language": edition.language,
            "issue": edition.issue_number,
            "date": edition.publication_date,
            "cover": edition.cover,
            "svg_sha256": hashlib.sha256(svg.encode("utf-8")).hexdigest(),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()


def replace_outer_pages(
    reader_pdf: Path,
    front_cover_pdf: Path,
    back_cover_pdf: Path,
    output: Path | None = None,
) -> Path:
    """Replace both reader outer pages with the exact compiled cover PDFs."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError as exc:
        raise DependencyError("Cover integration requires pypdf; run `uv sync --locked`.") from exc
    target = output or reader_pdf
    source = PdfReader(reader_pdf)
    front = PdfReader(front_cover_pdf)
    back = PdfReader(back_cover_pdf)
    if len(source.pages) < 4 or len(front.pages) != 1 or len(back.pages) != 1:
        raise CoverPdfError(
            "Reader must have at least four pages and each cover PDF exactly one page"
        )
    for name, cover in (("front", front), ("back", back)):
        box = cover.pages[0].mediabox
        if abs(float(box.width) - PAGE_WIDTH) > .02 or abs(float(box.height) - PAGE_HEIGHT) > .02:
            raise CoverPdfError(f"{name.title()} cover PDF must be A5")
    writer = PdfWriter()
    writer.add_page(front.pages[0])
    for page in source.pages[1:-1]:
        writer.add_page(page)
    writer.add_page(back.pages[0])
    writer.add_metadata({"/Creator": "magazine-compiler", "/Producer": "magazine-compiler"})
    temporary = target.with_suffix(target.suffix + ".cover-tmp")
    with temporary.open("wb") as stream:
        writer.write(stream)
    temporary.replace(target)
    return target


def replace_first_page(reader_pdf: Path, cover_pdf: Path, output: Path | None = None) -> Path:
    """Compatibility helper for callers that only replace reader page 1."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError as exc:
        raise DependencyError("Cover integration requires pypdf; run `uv sync --locked`.") from exc
    target = output or reader_pdf
    source = PdfReader(reader_pdf)
    cover = PdfReader(cover_pdf)
    if len(source.pages) < 2 or len(cover.pages) != 1:
        raise CoverPdfError("Reader must have at least two pages and cover PDF exactly one")
    writer = PdfWriter()
    writer.add_page(cover.pages[0])
    for page in source.pages[1:]:
        writer.add_page(page)
    writer.add_metadata({"/Creator": "magazine-compiler", "/Producer": "magazine-compiler"})
    temporary = target.with_suffix(target.suffix + ".cover-tmp")
    with temporary.open("wb") as stream:
        writer.write(stream)
    temporary.replace(target)
    return target


def _cover_date(value: str) -> str:
    parts = str(value).split("-")
    return " ".join(parts) if len(parts) == 3 and all(parts) else str(value)


def _cover_contributors(edition: Edition) -> str:
    """Derive front-cover contributor copy from the rendered article records.

    An author with two pieces in the issue is still one contributor, so the
    roster dedups case-insensitively while keeping first-appearance order.
    """
    authors: list[str] = []
    seen: set[str] = set()
    for article in edition.articles:
        author = article.author.strip()
        if author and author.casefold() not in seen:
            seen.add(author.casefold())
            authors.append(author)
    if authors:
        return " / ".join(authors).upper()
    return str(edition.cover.get("deck", "")).strip()


def materialize_wordmark_svg(publication_name: str, root: Path | None = None) -> str:
    """The Corte bruto lockup alone, as one standalone self-contained SVG.

    The markup is exactly what :meth:`CoverCompiler._wordmark` sets on the
    printed cover -- the compressed near-black head, the skewed slug, the
    misregistered orange under the reversed letters -- outlined from the
    bundled Inter Bold, so no page that shows it ever consults a host font.
    What this function adds is only a frame: a tight ``viewBox`` around the
    lockup's ink and a transparent background, which is what lets a screen
    surface place the mark at any size like the paste-up it is.

    ``root`` is a project root whose authored cover design (inks, wordmark
    slot) should be honoured; without one, or without a design file under it,
    the compiler's built-in canto-vivo defaults apply.  Deterministic: the
    same name and design yield the same bytes.

    The bounds below MIRROR the sizing loop in ``_wordmark``.  Drift between
    the two only loosens or crops the frame's padding -- the lockup itself
    always comes from ``_wordmark`` -- and the mirror is kept rather than
    shared because the print method's loop lives mid-layout, entangled with
    page coordinates this frame deliberately forgets.
    """

    value = publication_name.upper().strip()
    markup, frame, _ = _wordmark_frames(
        CoverCompiler(root if root is not None else Path(".")), value
    )
    return _framed_svg(markup, frame, value)


def materialize_favicon_svg(publication_name: str, root: Path | None = None) -> str:
    """The lockup's slug alone -- the skewed FUTURA bar -- framed as a favicon.

    A favicon is the lockup at sixteen pixels, and at sixteen pixels the whole
    two-story paste-up is noise; the slug -- the black printer's bar with the
    reversed letters over the misregistered orange -- is the piece of the mark
    that still reads.  The markup is the complete lockup exactly as
    :meth:`CoverCompiler._wordmark` sets it, with the ``viewBox`` cropped to
    the slug's own box, so the icon is a crop of the real mark, never new
    artwork.  A single-word publication name has no slug and gets the full
    lockup frame instead.
    """

    value = publication_name.upper().strip()
    markup, frame, slug_frame = _wordmark_frames(
        CoverCompiler(root if root is not None else Path(".")), value
    )
    return _framed_svg(markup, slug_frame or frame, value)


def cover_headline_lines(text: str, root: Path | None = None) -> tuple[str, ...]:
    """The printed cover's own line construction for ``text``.

    The printed face breaks the issue title into width-balanced lines measured
    on the bundled bold (``CoverCompiler._headline_layout``) and alternates
    the ink: odd lines set violet, staggered right.  A screen cover restating
    the headline must break on the same words or it reads as a different
    construction, so this returns that break -- in the text's authored casing,
    since casing is presentation the stylesheet owns.  Raises
    :class:`CoverOverflowError` when no size fits, exactly as the print path
    would; callers with a single-line fallback catch it.
    """

    compiler = CoverCompiler(root if root is not None else Path("."))
    lines, _ = compiler._headline_layout(str(text).upper().strip(), described_as=str(text))
    words = str(text).split()
    authored: list[str] = []
    cursor = 0
    for line in lines:
        count = len(line.split())
        authored.append(" ".join(words[cursor : cursor + count]))
        cursor += count
    return tuple(authored)


def cover_tab_issue(edition: Edition) -> str:
    """The canto-vivo tab's head label, exactly as the printed tab sets it.

    Zero-padded to three digits -- the shelf-navigation grammar -- under the
    localized issue word.  Shared by the printed tab (:meth:`_tab_labels`) and
    the web cover's canto strip, so the two media cannot drift apart.
    """

    label = "ISSUE" if edition.language.split("-", 1)[0] == "en" else "NÚMERO"
    return f"{label} {str(edition.issue_number).zfill(3)}"


def cover_tab_identity(edition: Edition) -> str:
    """The canto-vivo tab's foot: the publication's identity line.

    The city is the foot's whole point -- it is what the tab says when
    editions stand on a shelf -- and it lives here, in the cover module that
    owns cover copy, so every surface that states the identity states the
    same one.
    """

    return f"{edition.publication_name.upper()} / BUENOS AIRES"


def _wordmark_frames(
    compiler: CoverCompiler, value: str
) -> tuple[str, tuple[float, float, float, float], tuple[float, float, float, float] | None]:
    """The lockup markup with its tight frame and, when a slug exists, the
    slug's own frame.

    The bounds MIRROR the sizing loop in ``_wordmark``.  Drift between the two
    only loosens or crops a frame's padding -- the lockup itself always comes
    from ``_wordmark`` -- and the mirror is kept rather than shared because the
    print method's loop lives mid-layout, entangled with page coordinates
    these frames deliberately forget.
    """

    head, separator, tail = value.rpartition(" ")
    if not separator:
        head, tail = value, ""
    wordmark = compiler.design["wordmark"]
    x, top = float(wordmark["x"]), float(wordmark["top"])
    # PAGE_HEIGHT - (pdf_baseline - 1.65) with pdf_baseline = PAGE_HEIGHT - top:
    # the head sits 1.65pt below the slot's nominal top line.
    baseline = top + 1.65
    max_width = (
        PAGE_WIDTH - float(compiler.design["tab"]["width"]) - float(wordmark["right_reserve"])
    )
    size, tracking, head_scale = 42.0, -3.6, 89.9
    while size >= 25:
        head_width = compiler.bold.measure(
            head, size=size, tracking=tracking, horizontal_scale=head_scale
        )
        tail_width = compiler.bold.measure(
            tail, size=size, tracking=tracking, horizontal_scale=105.1
        ) if tail else 0.0
        tail_offset = size * (97 / 42)
        box_width = tail_width + (13 if tail else 0)
        if max(head_width, tail_offset + box_width) <= max_width:
            break
        size -= .5
    if size < 25:
        raise CoverOverflowError(f"Publication wordmark cannot fit: {value}")

    try:
        cap_units = float(compiler.bold.font["OS/2"].sCapHeight)
    except (KeyError, AttributeError):  # A face without OS/2 caps: use ascent.
        cap_units = compiler.bold.ascent_units
    cap = cap_units / compiler.bold.units * size
    left = x - 1.0
    top_edge = baseline - cap - 1.0
    right = x + .36 + head_width + 1.0
    bottom = baseline + 2.0
    slug_frame: tuple[float, float, float, float] | None = None
    if tail:
        # The slug group: translate(tail_x, tail_origin_y), sheared ~10deg
        # about its own centre.  Its ink spans group-y [8 - box_height - .65, 8]
        # and group-x [-13, -7 + box_width]; the shear reaches at most
        # tan(10deg) * half the box height sideways.
        box_height = size * 1.04 - 1
        tail_origin_y = top + size * .91
        reach = math.tan(math.radians(10)) * (box_height + .65) / 2 + 1.0
        slug_frame = (
            x + tail_offset - 13 - reach - 1.0,
            tail_origin_y + 8 - box_height - .65 - 1.0,
            x + tail_offset - 7 + box_width + reach + 1.0,
            tail_origin_y + 8 + 1.0,
        )
        right = max(right, slug_frame[2])
        left = min(left, slug_frame[0])
        bottom = max(bottom, slug_frame[3])
    markup = compiler._wordmark(value)[0]
    return markup, (left, top_edge, right, bottom), slug_frame


def _framed_svg(markup: str, frame: tuple[float, float, float, float], value: str) -> str:
    left, top_edge, right, bottom = frame
    label = escape(value)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{left:.3f} {top_edge:.3f} {right - left:.3f} {bottom - top_edge:.3f}" '
        f'role="img" aria-label="{label}">\n'
        f"  <title>{label}</title>\n"
        f"  {markup}\n"
        "</svg>\n"
    )


def _back_cover_copy(edition: Edition, key: str):
    language = edition.language.split("-", 1)[0]
    copy = {
        "en": {
            "mass": ("LOOP", "CLOSED"),
            "issue": "ISSUE",
            "end": "END",
            "back_text_default": "An independent anthology of writing worth keeping.",
        },
        "es": {
            "mass": ("CICLO", "CERRADO"),
            "issue": "NÚMERO",
            "end": "FIN",
            "back_text_default": "Una antología independiente de textos que vale la pena conservar.",
        },
    }
    return copy.get(language, copy["en"])[key]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
