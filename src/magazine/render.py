from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Iterable

from .errors import DependencyError
from .manifest import Edition


def _reportlab():
    try:
        from reportlab.lib.pagesizes import A5
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise DependencyError("PDF rendering requires ReportLab; run `uv sync --locked`.") from exc
    return A5, pdfmetrics, canvas


def _plain(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    replacements = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "--", "\u2026": "...", "\u00a0": " "}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("cp1252", errors="replace").decode("cp1252")


def _markdown_blocks(text: str) -> Iterable[tuple[str, str]]:
    if text.startswith("---\n"):
        _, _, text = text.partition("\n---\n")
    buffer: list[str] = []
    def flush():
        if buffer:
            value = " ".join(line.strip() for line in buffer).strip()
            buffer.clear()
            if value:
                return ("body", value)
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            block = flush()
            if block:
                yield block
        elif stripped.startswith("### "):
            block = flush()
            if block:
                yield block
            yield "h3", stripped[4:]
        elif stripped.startswith("## "):
            block = flush()
            if block:
                yield block
            yield "h2", stripped[3:]
        elif stripped.startswith("# "):
            block = flush()
            if block:
                yield block
            yield "h1", stripped[2:]
        elif re.match(r"^[-*] ", stripped):
            block = flush()
            if block:
                yield block
            yield "bullet", stripped[2:]
        elif stripped.startswith("> "):
            block = flush()
            if block:
                yield block
            yield "quote", stripped[2:]
        else:
            buffer.append(stripped)
    block = flush()
    if block:
        yield block


class _Typesetter:
    def __init__(self, pdf, edition: Edition, pagesize, metrics):
        self.pdf, self.edition, self.width, self.height, self.metrics = pdf, edition, *pagesize, metrics
        self.left, self.right, self.top, self.bottom = 43, 39, 49, 43
        self.page = 0
        self.y = self.height - self.top
        self.section = ""
        self.toc: dict[str, int] = {}

    def new_page(self, section: str = "", *, blank_header: bool = False):
        if self.page:
            self.pdf.showPage()
        self.page += 1
        self.section = section or self.section
        self.y = self.height - self.top
        if self.page > 2 and not blank_header:
            self.pdf.setFillColorRGB(.25, .25, .25)
            self.pdf.setFont("Helvetica", 7)
            self.pdf.drawString(self.left, self.height - 27, _plain(self.section.upper())[:64])
            self.pdf.drawRightString(self.width - self.right, 25, str(self.page))
            self.pdf.setStrokeColorRGB(.75, .75, .75)
            self.pdf.line(self.left, self.height - 34, self.width - self.right, self.height - 34)

    def lines(self, text: str, font: str, size: float, width: float) -> list[str]:
        words: list[str] = []
        for word in _plain(re.sub(r"[*_`]", "", text)).split():
            if self.metrics.stringWidth(word, font, size) <= width:
                words.append(word)
                continue
            chunk = ""
            for character in word:
                proposed = chunk + character
                if chunk and self.metrics.stringWidth(proposed, font, size) > width:
                    words.append(chunk)
                    chunk = character
                else:
                    chunk = proposed
            if chunk:
                words.append(chunk)
        result: list[str] = []
        current = ""
        for word in words:
            proposed = f"{current} {word}".strip()
            if current and self.metrics.stringWidth(proposed, font, size) > width:
                result.append(current)
                current = word
            else:
                current = proposed
        if current:
            result.append(current)
        return result or [""]

    def block(self, kind: str, text: str):
        styles = {
            "h1": ("Helvetica-Bold", 20, 24, 13), "h2": ("Helvetica-Bold", 14, 18, 9),
            "h3": ("Helvetica-Bold", 11, 15, 7), "body": ("Times-Roman", 10.25, 13.4, 7),
            "bullet": ("Times-Roman", 10.25, 13.4, 5), "quote": ("Times-Italic", 9.75, 13, 8),
        }
        font, size, leading, after = styles[kind]
        prefix = "- " if kind == "bullet" else ""
        indent = 13 if kind in {"bullet", "quote"} else 0
        lines = self.lines(prefix + text, font, size, self.width - self.left - self.right - indent)
        needed = len(lines) * leading + after
        if self.y - needed < self.bottom:
            self.new_page()
        self.pdf.setFillColorRGB(.08, .08, .08)
        self.pdf.setFont(font, size)
        for line in lines:
            self.pdf.drawString(self.left + indent, self.y, line)
            self.y -= leading
        self.y -= after

    def markdown(self, path: Path):
        for kind, value in _markdown_blocks(path.read_text(encoding="utf-8")):
            self.block(kind, value)

    def cover(self):
        self.new_page(blank_header=True)
        if self.edition.cover_art:
            from reportlab.lib.utils import ImageReader
            image = ImageReader(str(self.edition.cover_art))
            image_width, image_height = image.getSize()
            scale = max(self.width / image_width, self.height / image_height)
            draw_width, draw_height = image_width * scale, image_height * scale
            self.pdf.drawImage(image, (self.width - draw_width) / 2, (self.height - draw_height) / 2,
                               draw_width, draw_height, preserveAspectRatio=True, mask="auto")
            self.pdf.setFillColorRGB(.98, .95, .86, alpha=.91)
            self.pdf.rect(0, self.height - 188, self.width, 188, fill=1, stroke=0)
        else:
            self.pdf.setFillColorRGB(.07, .08, .09)
            self.pdf.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        ink = (.08, .13, .17) if self.edition.cover_art else (.94, .89, .76)
        self.pdf.setFillColorRGB(*ink)
        self.pdf.setFont("Helvetica-Bold", 10)
        self.pdf.drawString(36, self.height - 35, _plain(str(self.edition.cover.get("masthead", "COMMONPLACE"))).upper())
        self.pdf.setFont("Helvetica-Bold", 29)
        title_lines = self.lines(str(self.edition.cover.get("headline", self.edition.title)), "Helvetica-Bold", 29, self.width - 72)
        y = self.height - 78
        for line in title_lines:
            self.pdf.drawString(36, y, line)
            y -= 33
        deck = str(self.edition.cover.get("deck", "")).strip()
        if deck:
            y -= 2
            self.pdf.setFont("Helvetica", 9.25)
            for line in self.lines(deck, "Helvetica", 9.25, self.width - 72):
                self.pdf.drawString(36, y, line)
                y -= 12
        self.pdf.setFillColorRGB(.08, .13, .17)
        self.pdf.setFont("Helvetica-Bold", 7.5)
        self.pdf.drawString(36, 27, f"ISSUE {self.edition.issue_number}  /  {self.edition.publication_date}  /  PRIVATE PROTOTYPE")

    def contents(self, toc_pages: dict[str, int]):
        self.new_page("Contents", blank_header=True)
        self.block("h1", "Contents")
        entries = []
        if self.edition.articles:
            if self.edition.editorial:
                entries.append(("Editorial", toc_pages.get("editorial", 0)))
            entries.extend((article.title, toc_pages.get(article.id, 0)) for article in self.edition.articles)
            entries.extend((section.title, toc_pages.get(f"section-{index}", 0)) for index, section in enumerate(self.edition.sections))
        elif self.edition.sections:
            entries.extend((section.title, toc_pages.get(f"section-{index}", 0)) for index, section in enumerate(self.edition.sections))
        self.pdf.setFont("Times-Roman", 10.5)
        for title, page in entries:
            if self.y < self.bottom + 18:
                self.new_page("Contents")
            self.pdf.drawString(self.left, self.y, _plain(title)[:56])
            self.pdf.drawRightString(self.width - self.right, self.y, str(page) if page else "")
            self.y -= 18

    def body(self):
        if self.edition.articles:
            if self.edition.editorial:
                self.new_page("Editorial")
                self.toc["editorial"] = self.page
                self.markdown(self.edition.editorial)
            for article in self.edition.articles:
                self.new_page(article.title)
                self.toc[article.id] = self.page
                self.block("h1", article.title)
                self.block("body", f"By {article.author}")
                self.markdown(article.manuscript)
            for index, section in enumerate(self.edition.sections):
                self._section(index, section)
            return
        if self.edition.sections:
            for index, section in enumerate(self.edition.sections):
                self._section(index, section)
            return

    def _section(self, index, section):
        self.new_page(section.title)
        self.toc[f"section-{index}"] = self.page
        label = {
            "original_editorial": "ORIGINAL EDITORIAL",
            "source_introduction": "THE SOURCE",
            "original_synthesis": "READING MAP",
            "source_record": "SOURCE RECORD",
            "production_note": "PRODUCTION NOTE",
            "colophon": "COLOPHON",
        }.get(section.kind, section.kind.replace("_", " ").upper())
        self.pdf.setFillColorRGB(.52, .11, .11)
        self.pdf.setFont("Helvetica-Bold", 7.5)
        self.pdf.drawString(self.left, self.y, _plain(label))
        self.y -= 17
        self.block("h1", section.title)
        self.markdown(section.path)

    def back_cover(self):
        configured = self.edition.raw.get("format", {}).get("target_pages")
        minimum_total = self.page + 1
        target = int(configured) if configured else ((minimum_total + 3) // 4) * 4
        target = max(target, minimum_total)
        target = ((target + 3) // 4) * 4
        while self.page < target - 1:
            self.new_page(blank_header=True)
        self.new_page(blank_header=True)
        self.pdf.setFillColorRGB(.94, .89, .76)
        self.pdf.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        self.pdf.setFillColorRGB(.07, .08, .09)
        text = str(self.edition.cover.get("back_text", "A private anthology of writing worth keeping."))
        y = self.height * .58
        self.pdf.setFont("Helvetica-Bold", 16)
        for line in self.lines(text, "Helvetica-Bold", 16, self.width - 90):
            self.pdf.drawString(45, y, line)
            y -= 21
        self.pdf.setFont("Helvetica", 8)
        self.pdf.drawString(45, 40, _plain(self.edition.title))


def _render_pass(target, edition: Edition, toc: dict[str, int] | None = None) -> dict[str, int]:
    A5, metrics, canvas = _reportlab()
    pdf = canvas.Canvas(target, pagesize=A5, pageCompression=1, invariant=1)
    pdf.setTitle(_plain(edition.title))
    pdf.setAuthor("Magazine Compiler")
    pdf.setCreator("magazine-compiler")
    typesetter = _Typesetter(pdf, edition, A5, metrics)
    typesetter.cover()
    typesetter.contents(toc or {})
    typesetter.body()
    typesetter.back_cover()
    pdf.save()
    return typesetter.toc


def render_a5(edition: Edition, output: Path) -> Path:
    """Render an edition twice so the deterministic contents page has folios."""
    output.parent.mkdir(parents=True, exist_ok=True)
    toc = _render_pass(io.BytesIO(), edition)
    _render_pass(str(output), edition, toc)
    return output
