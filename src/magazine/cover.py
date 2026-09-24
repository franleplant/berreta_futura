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
            f"translate({x:.5f} {baseline:.5f}) {extra_transform} scale({scale_x:.8f} {-scale:.8f})"
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
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.design_path = self.root / "design" / "covers" / "canto-vivo" / "design.toml"
        if self.design_path.is_file():
            self.design = tomllib.loads(self.design_path.read_text(encoding="utf-8"))
        else:
            self.design = {
                "id": "canto-vivo/1",
                "color": {"paper": WHITE, "ink": INK, "violet": VIOLET, "orange": ORANGE},
                "tab": {
                    "width": 21.0,
                    "overdraw": 1.5,
                    "issue_top": 26.5,
                    "identity_top": 433.5,
                    "edge_reveal": 1.4,
                },
                "wordmark": {"x": 38.0, "top": 53.0, "right_reserve": 78.0},
                "headline": {"x": 44.0, "top": 122.0, "width": 302.0},
                "art": {"x": 85.25, "top": 221.85, "width": 249.35, "height": 248.65},
                "deck": {
                    "top": 493.0,
                    "size": 5.5,
                    "wrap_size": 6.7,
                    "leading": 8.4,
                    "horizontal_scale": 108.0,
                    "tracking": 0.35,
                },
                "footer": {"x": 44.0, "bottom": 20.0, "size": 7.0, "tracking": 1.85},
                "back": {
                    "overdraw": 1.5,
                    "rail_width": 42.0,
                    "rail_top": 32.0,
                    "rail_size": 8.0,
                    "rail_tracking": 1.6,
                    "mass_x": 6.0,
                    "mass_top": 38.0,
                    "mass_size": 116.0,
                    "mass_leading": 84.68,
                    "mass_tracking": -12.18,
                    "panel_x": 38.0,
                    "panel_top": 242.0,
                    "panel_right": 62.0,
                    "panel_bottom": 52.0,
                    "panel_padding": 30.0,
                    "statement_max_size": 24.0,
                    "statement_min_size": 18.0,
                    "statement_leading_ratio": 1.05,
                    "slug_x": 38.0,
                    "slug_bottom": 26.0,
                    "slug_size": 7.0,
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

        self.display = _FontOutliner(
            Path(__file__).with_name("assets") / "fonts" / "archivo" / "ArchivoCondensed-Bold.ttf"
        )
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
        if (
            svg_path.is_file()
            and pdf_path.is_file()
            and png_path.is_file()
            and proof_path.is_file()
        ):
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
        tab = self.design["tab"]
        width = float(tab["width"])
        reveal = float(tab.get("edge_reveal", 0.0))
        return PAGE_WIDTH - width, width - reveal

    def _materialize_svg(self, edition: Edition) -> str:
        layout = str(edition.cover.get("layout") or "framed")
        if layout == "footer_caption":
            return self._footer_caption_svg(edition)
        if layout == "honored_plate":
            return self._honored_plate_svg(edition)
        if layout != "framed":
            raise CoverAssetError(
                f"Unknown cover layout {layout!r}: expected framed, footer_caption, or honored_plate"
            )
        tab = self.design["tab"]
        paper = str(self.colors["paper"])
        orange = str(self.colors["orange"])
        band_x, band_width = self._tab_band()
        parts: list[str] = [
            f'<rect data-slot="paper" x="0" y="0" width="{PAGE_WIDTH}" '
            f'height="{PAGE_HEIGHT}" fill="{paper}"/>',
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
            + "</g>"
        )
        parts.extend(self._tab_labels(edition))
        body = "\n    ".join(parts)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_WIDTH}pt" '
            f'height="{PAGE_HEIGHT}pt" viewBox="0 0 {PAGE_WIDTH} {PAGE_HEIGHT}" '
            'overflow="hidden">\n'
            "  <title>Berreta Futura cover</title>\n"
            f'  <g id="cover" data-design="{escape(str(self.design["id"]))}">\n    {body}\n  </g>\n'
            "</svg>\n"
        )

    def _svg_shell(self, body: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_WIDTH}pt" '
            f'height="{PAGE_HEIGHT}pt" viewBox="0 0 {PAGE_WIDTH} {PAGE_HEIGHT}" '
            'overflow="hidden">\n'
            "  <title>Berreta Futura cover</title>\n"
            f'  <g id="cover" data-design="{escape(str(self.design["id"]))}">\n    {body}\n  </g>\n'
            "</svg>\n"
        )

    def _band_x(self) -> float:
        return PAGE_WIDTH - float(self.design["tab"]["width"])

    def _art_zones(self, path: Path) -> tuple[tuple[float, float], tuple[float, float]]:
        try:
            from PIL import Image, ImageStat
        except ImportError as exc:
            raise DependencyError("Cover artwork requires Pillow; run `uv sync --locked`.") from exc
        with Image.open(path) as source:
            image = source.convert("RGB")
        ratio = max(self._band_x() / image.width, PAGE_HEIGHT / image.height)
        width, height = int(self._band_x() / ratio), int(PAGE_HEIGHT / ratio)
        ox, oy = (image.width - width) // 2, (image.height - height) // 2
        image = image.crop((ox, oy, ox + width, oy + height))

        def stat(box):
            grey = image.crop(box).convert("L")
            values = ImageStat.Stat(grey)
            return values.mean[0], values.stddev[0]

        top = stat((0, 0, image.width, int(image.height * 0.24)))
        bottom = stat((0, int(image.height * 0.72), image.width, image.height))
        return top, bottom

    def _full_art(self, edition: Edition, x: float, y: float, w: float, h: float) -> str:
        if not edition.cover_art or not edition.cover_art.is_file():
            raise CoverAssetError(f"Cover art is missing: {edition.cover_art}")
        art_data = base64.b64encode(self._graded_art(edition.cover_art)).decode("ascii")
        return (
            f'<image data-slot="art" x="{x}" y="{y}" width="{w}" height="{h}" '
            f'preserveAspectRatio="xMidYMid slice" href="data:image/png;base64,{art_data}"/>'
        )

    def _scaled_wordmark(
        self, edition: Edition, mode: str, scale: float, dx: float, dy: float
    ) -> str:
        part = self._wordmark(edition.publication_name)[0]
        if mode == "light":
            i = part.find("matrix(")
            j = part.rfind("<g transform=", 0, i)
            part = part[:j].replace(str(self.colors["ink"]), str(self.colors["paper"])) + part[j:]
        return f'<g transform="translate({dx:.4f} {dy:.4f}) scale({scale})">{part}</g>'

    def _margin_locked_wordmark(
        self, edition: Edition, mode: str, scale: float, margin: float, dy: float
    ) -> str:
        dx = margin - (float(self.design["wordmark"]["x"]) + 0.36) * scale
        return self._scaled_wordmark(edition, mode, scale, dx, dy)

    def _fit_display_line(
        self, text: str, max_size: float, width: float, tracking: float = 0.2
    ) -> float:
        size = max_size
        while size >= 12 and self.display.measure(text, size=size, tracking=tracking) > width:
            size -= 0.5
        if size < 12:
            raise CoverOverflowError(f"Cover title cannot fit on one line: {text}")
        return size

    def _justified_line(
        self, text: str, x: float, baseline: float, size: float, fill: str, width: float
    ) -> str:
        base = self.regular.measure(text, size=size, tracking=0)
        tracking = max(0.0, (width - base) / max(1, len(text) - 1))
        return self.regular.outline(
            text, x=x, baseline=baseline, size=size, fill=fill, tracking=tracking
        ).markup

    def _right_line(
        self,
        text: str,
        right_edge: float,
        baseline: float,
        size: float,
        fill: str,
        tracking: float = 1.4,
    ) -> str:
        width = self.bold.measure(text, size=size, tracking=tracking)
        return self.bold.outline(
            text, x=right_edge - width, baseline=baseline, size=size, fill=fill, tracking=tracking
        ).markup

    @staticmethod
    def _gradient(
        gid: str, x: float, y: float, w: float, h: float, color: str, top: float, bottom: float
    ) -> str:
        return (
            f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{color}" stop-opacity="{top}"/>'
            f'<stop offset="1" stop-color="{color}" stop-opacity="{bottom}"/>'
            f"</linearGradient></defs>"
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{gid})"/>'
        )

    def _footer_caption_svg(self, edition: Edition) -> str:
        spec = self.design.get("layout", {}).get("footer_caption", {})
        margin = float(spec.get("margin", 25.0))
        scale = float(spec.get("wordmark_scale", 0.8))
        band = self._band_x()
        right_edge = band - margin
        (top_mean, top_std), (bottom_mean, bottom_std) = self._art_zones(edition.cover_art)
        dark_bottom = bottom_mean < 105
        fill = str(self.colors["paper"] if dark_bottom else self.colors["ink"])
        parts = [self._full_art(edition, 0, 0, band, PAGE_HEIGHT)]
        if dark_bottom and bottom_std > 46:
            parts.append(
                self._gradient(
                    "cap-b", 0, PAGE_HEIGHT - 170, band, 170, str(self.colors["ink"]), 0.0, 0.72
                )
            )
        if not dark_bottom:
            parts.append(
                self._gradient(
                    "cap-b", 0, PAGE_HEIGHT - 170, band, 170, str(self.colors["paper"]), 0.0, 0.7
                )
            )
        if top_std > 52 and top_mean < 150:
            parts.append(
                self._gradient("cap-t", 0, 0, band, 120, str(self.colors["ink"]), 0.42, 0.0)
            )
        mode = "light" if top_mean < 118 else "dark"
        parts.append(
            self._margin_locked_wordmark(
                edition, mode, scale, margin, float(spec.get("wordmark_dy", 6.0))
            )
        )
        title = str(edition.cover.get("headline", edition.title)).upper().strip()
        size = self._fit_display_line(
            title, float(spec.get("title_size", 26.0)), right_edge - margin - 62
        )
        parts.append(
            '<g data-slot="headline">'
            + self.display.outline(
                title, x=margin, baseline=PAGE_HEIGHT - 46, size=size, fill=fill, tracking=0.2
            ).markup
            + "</g>"
        )
        parts.append(
            self._right_line(
                _cover_date(edition.publication_date), right_edge, PAGE_HEIGHT - 46, 7.0, fill
            )
        )
        contributors = _cover_contributors(edition)
        if contributors:
            parts.append(
                '<g data-slot="deck">'
                + self._justified_line(
                    contributors, margin, PAGE_HEIGHT - 24, 4.6, fill, right_edge - margin
                )
                + "</g>"
            )
        parts.append(
            f'<rect data-slot="edge-tab" x="{band + 0 - 0:.5f}" y="-1.5" width="{PAGE_WIDTH - band - float(self.design["tab"]["edge_reveal"]):.5f}" '
            f'height="{PAGE_HEIGHT + 3}" fill="{self.colors["orange"]}"/>'
        )
        parts.extend(self._tab_labels(edition))
        return self._svg_shell("\n    ".join(parts))

    def _honored_plate_svg(self, edition: Edition) -> str:
        spec = self.design.get("layout", {}).get("honored_plate", {})
        margin = float(spec.get("margin", 17.0))
        footer = float(spec.get("footer", 64.0))
        band = self._band_x()
        right_edge = band - margin - 8
        ink = str(self.colors["ink"])
        parts = [
            f'<rect data-slot="paper" x="0" y="0" width="{PAGE_WIDTH}" height="{PAGE_HEIGHT}" fill="{self.colors["paper"]}"/>',
            self._full_art(
                edition, margin, margin, band - 2 * margin, PAGE_HEIGHT - 2 * margin - footer
            ),
            f'<rect data-slot="art-border" x="{margin}" y="{margin}" width="{band - 2 * margin}" '
            f'height="{PAGE_HEIGHT - 2 * margin - footer}" fill="none" stroke="{ink}" stroke-width=".7"/>',
            self._scaled_wordmark(
                edition,
                "dark",
                float(spec.get("wordmark_scale", 0.5)),
                6.0,
                PAGE_HEIGHT - footer - 22 - 14,
            ),
        ]
        title = str(edition.cover.get("headline", edition.title)).upper().strip()
        size = self._fit_display_line(title, float(spec.get("title_size", 19.0)), 190)
        width = self.display.measure(title, size=size, tracking=0.2)
        parts.append(
            '<g data-slot="headline">'
            + self.display.outline(
                title,
                x=right_edge - width,
                baseline=PAGE_HEIGHT - footer + 22,
                size=size,
                fill=ink,
                tracking=0.2,
            ).markup
            + "</g>"
        )
        contributors = _cover_contributors(edition)
        if contributors:
            parts.append(
                '<g data-slot="deck">'
                + self._justified_line(
                    contributors, margin + 8, PAGE_HEIGHT - 24, 4.4, ink, right_edge - margin - 68
                )
                + "</g>"
            )
        parts.append(
            self._right_line(
                _cover_date(edition.publication_date), right_edge, PAGE_HEIGHT - 13, 4.4, ink
            )
        )
        parts.append(
            f'<rect data-slot="edge-tab" x="{band:.5f}" y="-1.5" width="{PAGE_WIDTH - band - float(self.design["tab"]["edge_reveal"]):.5f}" '
            f'height="{PAGE_HEIGHT + 3}" fill="{self.colors["orange"]}"/>'
        )
        parts.extend(self._tab_labels(edition))
        return self._svg_shell("\n    ".join(parts))

    def _materialize_back_svg(self, edition: Edition) -> str:
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
            mass_size -= 0.5
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

        panel_max_height = PAGE_HEIGHT - panel_top - float(back["panel_bottom"])
        panel_padding = float(back["panel_padding"])
        statement = str(
            edition.cover.get("back_text", _back_cover_copy(edition, "back_text_default"))
        ).strip()
        statement_size, statement_lines, statement_rise, statement_block = self._fit_back_statement(
            statement,
            panel_width - panel_padding * 2,
            panel_max_height - panel_padding * 2,
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
                tracking=-0.12,
            ).markup
            for index, line in enumerate(statement_lines)
        ]

        slug = f"{_back_cover_copy(edition, 'end')} / {_cover_date(edition.publication_date)}"
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
            )
            > rail_max_length
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
        rail_x = PAGE_WIDTH - rail_width / 2 - (rail.ascent - rail.descent) / 2
        rail_path = (
            f'<g transform="translate({rail_x:.5f} {float(back["rail_top"]):.5f}) rotate(90)">'
            f"{rail.markup}</g>"
        )

        parts = [
            f'<rect data-slot="field" x="{-overdraw}" y="{-overdraw}" '
            f'width="{PAGE_WIDTH + overdraw * 2}" height="{PAGE_HEIGHT + overdraw * 2}" '
            f'fill="{orange}"/>',
            f'<defs><clipPath id="mass-safe" clipPathUnits="userSpaceOnUse">'
            f'<rect x="0" y="0" width="{PAGE_WIDTH - rail_width}" height="{PAGE_HEIGHT}"/>'
            f"</clipPath></defs>",
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
            "  <title>Berreta Futura back cover</title>\n"
            f'  <g id="back-cover" data-design="{escape(str(self.design["id"]))}">\n'
            f"    {body}\n  </g>\n"
            "</svg>\n"
        )

    def _fit_back_statement(
        self,
        text: str,
        width: float,
        height: float,
    ) -> tuple[float, list[str], float, float]:
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
            size -= 0.5
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
        max_width = (
            PAGE_WIDTH - float(self.design["tab"]["width"]) - float(wordmark["right_reserve"])
        )
        while size >= 25:
            head_width = self.bold.measure(
                head, size=size, tracking=tracking, horizontal_scale=head_scale
            )
            tail_width = (
                self.bold.measure(tail, size=size, tracking=tracking, horizontal_scale=105.1)
                if tail
                else 0
            )
            tail_offset = size * (97 / 42)
            box_width = tail_width + (13 if tail else 0)
            if max(head_width, tail_offset + box_width) <= max_width:
                break
            size -= 0.5
        if size < 25:
            raise CoverOverflowError(f"Publication wordmark cannot fit: {publication_name}")
        head_path = self.bold.outline(
            head,
            x=x + 0.36,
            baseline=baseline,
            size=size,
            fill=str(self.colors["ink"]),
            tracking=tracking,
            horizontal_scale=head_scale,
            stroke=str(self.colors["ink"]),
            stroke_width=0.30,
        ).markup
        if not tail:
            return [f'<g data-slot="wordmark">{head_path}</g>']

        tail_x = x + tail_offset

        tail_origin_y = PAGE_HEIGHT - (pdf_baseline - size * 0.91)
        box_x, box_y = -7.0, -7.0
        box_height = size * 1.04 - 1
        box_width = tail_width + 13
        slug_y = box_y - 1
        center_x = box_x + box_width / 2
        center_y = box_y + box_height / 2
        skew = math.tan(math.radians(-10))
        group = (
            f"translate({tail_x:.5f} {tail_origin_y:.5f}) "
            f"translate({center_x:.5f} {-center_y:.5f}) matrix(1 0 {skew:.8f} 1 0 0) "
            f"translate({-center_x:.5f} {center_y:.5f})"
        )
        slug = (
            f'<path d="M {box_x} {-slug_y} H {box_x + box_width} '
            f'V {-slug_y - (box_height + 0.65)} H {box_x} Z" fill="{self.colors["ink"]}"/>'
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
            stroke_width=0.15,
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
            stroke_width=0.30,
        ).markup
        return [
            f'<g data-slot="wordmark">{head_path}<g transform="{group}">{slug}{orange}{white}</g></g>'
        ]

    def _headline_layout(
        self, value: str, *, described_as: str | None = None
    ) -> tuple[list[str], float]:

        size = 29.0
        headline = self.design["headline"]
        width = float(headline["width"])
        words = value.split()
        while size >= 20:
            candidates: list[tuple[float, tuple[str, str]]] = []
            if len(words) >= 2:
                for split in range(1, len(words)):
                    pair = (" ".join(words[:split]), " ".join(words[split:]))
                    widths = tuple(self.display.measure(line, size=size) for line in pair)
                    if max(widths) <= width:
                        candidates.append((abs(widths[0] - widths[1]), pair))
            if candidates:
                lines = list(min(candidates, key=lambda item: item[0])[1])
            else:
                lines = self._wrap(value, self.display, size, width)
            if len(lines) <= 3:
                break
            size -= 0.5
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
        leading = size * 0.78
        colors = (str(self.colors["ink"]), str(self.colors["violet"]), str(self.colors["ink"]))
        paths = []
        for index, line in enumerate(lines):
            line_size = 28.0 if index % 2 else size
            paths.append(
                self.display.outline(
                    line,
                    x=float(headline["x"]) + (23 if index % 2 else -0.65),
                    baseline=baseline + (1 if index % 2 else 0),
                    size=line_size,
                    fill=colors[index],
                    tracking=-1.35,
                    stroke=colors[index] if index % 2 == 0 else None,
                    stroke_width=0.09 if index % 2 == 0 else 0,
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
                x=x - (0.65 if index == 0 else 0),
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

            cross = band_x + band_width / 2 - (outlined.ascent - outlined.descent) / 2
            return (
                f'<g transform="translate({cross:.5f} {top:.5f}) rotate(90)">{outlined.markup}</g>'
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
        try:
            from PIL import Image
        except ImportError as exc:
            raise DependencyError("Cover artwork requires Pillow; run `uv sync --locked`.") from exc
        with Image.open(path) as source:
            image = source.convert("RGB")
        graded = []
        for red, green, blue in image.get_flattened_data():
            if blue > 120 and blue > red * 1.7 and blue > green * 1.7:
                graded.append(
                    (round(red * 0.96), min(255, round(green * 1.12)), round(blue * 0.953))
                )
            elif red > 170 and red > green * 1.8 and green > blue * 1.5:
                graded.append(
                    (round(red * 0.916), min(255, round(green * 1.146)), min(255, blue + 45))
                )
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
            f"{_back_cover_copy(edition, 'end')} / {_cover_date(edition.publication_date)}",
            38.0,
            26.0,
            7.0,
        )
        invisible_line(
            f"{edition.publication_name.upper()} / {_back_cover_copy(edition, 'issue')} "
            f"{str(edition.issue_number).zfill(3)} / BUENOS AIRES",
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
            raise DependencyError(
                "Cover validation requires pypdf; run `uv sync --locked`."
            ) from exc
        reader = PdfReader(path)
        if len(reader.pages) != 1:
            raise CoverPdfError(f"Cover PDF must contain exactly one page: {path}")
        box = reader.pages[0].mediabox
        width, height = float(box.width), float(box.height)
        if abs(width - PAGE_WIDTH) > 0.02 or abs(height - PAGE_HEIGHT) > 0.02:
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
                [
                    executable,
                    "-f",
                    "1",
                    "-singlefile",
                    "-png",
                    "-r",
                    str(self.proof_dpi),
                    str(pdf),
                    str(prefix),
                ],
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
        mean = sum(index * count for index, count in enumerate(histogram)) / max(
            1, actual.width * actual.height
        )
        overlay = Image.blend(expected, actual, 0.5)
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
        if abs(float(box.width) - PAGE_WIDTH) > 0.02 or abs(float(box.height) - PAGE_HEIGHT) > 0.02:
            raise CoverPdfError(f"{name.title()} cover PDF must be A5")
    writer = PdfWriter(clone_from=source)
    writer.pdf_header = max(reader.pdf_header for reader in (source, front, back))
    for page, cover in ((writer.pages[0], front), (writer.pages[-1], back)):
        face = cover.pages[0].clone(writer)
        for key in [key for key in page if key != "/Parent"]:
            del page[key]
        page.update({key: value for key, value in face.items() if key != "/Parent"})
    writer.compress_identical_objects(remove_identicals=False, remove_orphans=True)
    writer.add_metadata({"/Creator": "magazine-compiler", "/Producer": "magazine-compiler"})
    temporary = target.with_suffix(target.suffix + ".cover-tmp")
    with temporary.open("wb") as stream:
        writer.write(stream)
    temporary.replace(target)
    return target


def replace_first_page(reader_pdf: Path, cover_pdf: Path, output: Path | None = None) -> Path:
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

    value = publication_name.upper().strip()
    markup, frame, _ = _wordmark_frames(
        CoverCompiler(root if root is not None else Path(".")), value
    )
    return _framed_svg(markup, frame, value)


def materialize_favicon_svg(publication_name: str, root: Path | None = None) -> str:

    value = publication_name.upper().strip()
    markup, frame, slug_frame = _wordmark_frames(
        CoverCompiler(root if root is not None else Path(".")), value
    )
    return _framed_svg(markup, slug_frame or frame, value)


def cover_headline_lines(text: str, root: Path | None = None) -> tuple[str, ...]:

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

    label = "ISSUE" if edition.language.split("-", 1)[0] == "en" else "NÚMERO"
    return f"{label} {str(edition.issue_number).zfill(3)}"


def cover_tab_identity(edition: Edition) -> str:

    return f"{edition.publication_name.upper()} / BUENOS AIRES"


def _wordmark_frames(
    compiler: CoverCompiler, value: str
) -> tuple[str, tuple[float, float, float, float], tuple[float, float, float, float] | None]:

    head, separator, tail = value.rpartition(" ")
    if not separator:
        head, tail = value, ""
    wordmark = compiler.design["wordmark"]
    x, top = float(wordmark["x"]), float(wordmark["top"])

    baseline = top + 1.65
    max_width = (
        PAGE_WIDTH - float(compiler.design["tab"]["width"]) - float(wordmark["right_reserve"])
    )
    size, tracking, head_scale = 42.0, -3.6, 89.9
    while size >= 25:
        head_width = compiler.bold.measure(
            head, size=size, tracking=tracking, horizontal_scale=head_scale
        )
        tail_width = (
            compiler.bold.measure(tail, size=size, tracking=tracking, horizontal_scale=105.1)
            if tail
            else 0.0
        )
        tail_offset = size * (97 / 42)
        box_width = tail_width + (13 if tail else 0)
        if max(head_width, tail_offset + box_width) <= max_width:
            break
        size -= 0.5
    if size < 25:
        raise CoverOverflowError(f"Publication wordmark cannot fit: {value}")

    try:
        cap_units = float(compiler.bold.font["OS/2"].sCapHeight)
    except (KeyError, AttributeError):
        cap_units = compiler.bold.ascent_units
    cap = cap_units / compiler.bold.units * size
    left = x - 1.0
    top_edge = baseline - cap - 1.0
    right = x + 0.36 + head_width + 1.0
    bottom = baseline + 2.0
    slug_frame: tuple[float, float, float, float] | None = None
    if tail:
        box_height = size * 1.04 - 1
        tail_origin_y = top + size * 0.91
        reach = math.tan(math.radians(10)) * (box_height + 0.65) / 2 + 1.0
        slug_frame = (
            x + tail_offset - 13 - reach - 1.0,
            tail_origin_y + 8 - box_height - 0.65 - 1.0,
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
