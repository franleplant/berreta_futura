#!/usr/bin/env python3
"""Objective equivalence harness: WeasyPrint candidate vs frozen ReportLab baseline.

The contract lives in ``EQUIVALENCE.md``.  This module renders the candidate A5
reader with :func:`magazine.weasyprint_adapter.render_a5_weasyprint`, splices the
*same* canonical cover PDFs the baseline build used, imposes the A4 home booklet
with :func:`magazine.booklet.impose_a5_on_a4`, and then reports six gates per
language:

* **G1** geometry -- page counts and every declared page box (media, crop, trim,
  bleed, art, ``/Rotate``) of the reader *and* of the imposed booklet.
* **G2** imposition -- the (left, right) reader-page mapping *measured from the
  booklet PDF*: every word of every imposed side must sit at the position the
  reader page it carries puts it, offset by the slot origin.
* **G3** content placement -- per-page position-canonical extracted text,
  article/editorial spans, contents folios, and absence of ``signature-pad``
  filler pages both on the page and in the adapter's source.  Its summary always
  states two numbers -- how many clauses fail *and* how many reader pages differ --
  because a retiring clause shrinks the first without touching the second.
* **G4** ink geometry -- per-page and per-booklet-side ink coverage ratio and ink
  bounding box.
* **G5** visual -- per-page and per-booklet-side differing-pixel fraction and
  mean absolute difference.
* **G6** colour -- per-page and per-booklet-side *per-channel* RGB raster
  difference, plus an exact comparison of the chromatic ink each pipeline sets in
  its content streams.  G1--G5 are all greyscale or geometric: a hue error on an
  accent token reaches paper without moving any of their numbers.

G1--G3 are hard gates and decide the exit code.  G4/G5/G6 are reported against
tolerances exposed as CLI flags so they can be tightened without editing code.

**What the hard gates do and do not prove** is stated verbatim in the report; see
:data:`GATE_STRENGTH_NOTES`.  Read it before treating a PASS as convergence.

Write safety: the harness mints *every* path it writes through :class:`WorkDir`,
which proves the target lives under ``--work-dir``; ``--work-dir`` itself must be
disjoint -- in both directions -- from the frozen baseline tree and from
``<root>/output``.  It also hashes the whole baseline tree before and after the
run and fails loudly if a single byte moved.

Nothing here is imported by ``magazine``.

**This harness is a measuring instrument, not a gate, and it no longer passes.**
It exists to answer "how far did the output move, and where?".  The three
shaping scaffolds that held WeasyPrint's line breaking down to ReportLab's were
removed after cutover, so the candidate deliberately no longer reproduces the
frozen baseline: G3 reports 11 of 36 differing reader pages in English and 2 of
36 in Spanish, with every article's start page and span unchanged.  Editions 001
and 002 are archived as printed; 003 onward is set by WeasyPrint.  Do not tune
anything, and do not reinstate a scaffold, to make this exit zero again -- see
``docs/RENDERER_MIGRATION.md``.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime
import difflib
import hashlib
import html
import inspect
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:  # Allow `python tools/compare_pipelines.py`.
    sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageChops, ImageOps  # noqa: E402
from pypdf import PdfReader  # noqa: E402
from pypdf.generic import ContentStream, IndirectObject  # noqa: E402

from magazine import render_critic  # noqa: E402
from magazine.booklet import booklet_spreads, impose_a5_on_a4  # noqa: E402
from magazine.cover import CoverCompiler, replace_outer_pages  # noqa: E402
from magazine.render import (  # noqa: E402
    COOL_GRAY,
    COVER_INK,
    COVER_VIOLET,
    INK,
    PALE_VIOLET,
    SIGNAL_ORANGE,
    SLATE,
    VIOLET,
    WHITE,
)
from magazine.render_critic import _booklet_spread_checks, _inspect_page, _render_pages  # noqa: E402


SCRATCH = Path(
    "/private/tmp/claude-501/-Users-franguijarro-code-magazine"
    "/fdda322b-f078-45de-beca-f8cd9c8bac25/scratchpad"
)
DEFAULT_BASELINE = SCRATCH / "baseline"
DEFAULT_WORK_DIR = SCRATCH / "candidate"

A5_MEDIABOX = (419.5276, 595.2756)
A4_LANDSCAPE_MEDIABOX = (841.8898, 595.2756)
A5_PAGE_BOX = (0.0, 0.0, A5_MEDIABOX[0], A5_MEDIABOX[1])
A4_LANDSCAPE_PAGE_BOX = (0.0, 0.0, A4_LANDSCAPE_MEDIABOX[0], A4_LANDSCAPE_MEDIABOX[1])
BOX_NAMES = ("mediabox", "cropbox", "trimbox", "bleedbox", "artbox")
MEDIABOX_TOLERANCE = 0.01

REFERENCE_DPI = 144
"""Every pixel-denominated default below is stated at this DPI and scaled from it."""

# ``impose_a5_on_a4`` scales each A5 page by min(420.9449/419.5276, 1.0) == 1.0 and
# translates the right-hand slot by half an A4 sheet, so an imposed word must land
# on exactly the reader coordinate it came from, offset by the slot origin.  0.05pt
# is two orders of magnitude below a hairline and absorbs only float noise.
IMPOSITION_SLOT_ORIGINS = (0.0, A4_LANDSCAPE_MEDIABOX[0] / 2)
IMPOSITION_POSITION_TOLERANCE = 0.05

# Position-canonical text extraction (G3).  Words are grouped into horizontal
# bands by their vertical centre and read band-by-band, left to right, so reading
# order comes from geometry instead of from content-stream order: ReportLab draws
# the page furniture first, WeasyPrint's @page margin boxes emit it last.
#
# Measured on this edition: intra-line vertical jitter reaches 2.06pt (baseline
# en p6); the tightest *genuine* line separation is 4.93pt (baseline en contents
# grid) and 8.40pt in the candidate; body leading is 12.55pt.  Band counts are
# identical for tolerances 3.0-4.0pt on both baselines and for 2.0-8.0pt on both
# candidates, so 4.0pt sits at the top of a measured plateau.  Banding is derived
# per page from the words' own coordinates, so the ~3-5pt whole-band offset
# between the two pipelines (top furniture 45.41 vs 48.58pt, folio 569.19 vs
# 564.91pt) cannot change the derived order.
DEFAULT_TEXT_BAND_TOLERANCE = 4.0

# A structural entry's title is printed at the top of its opening page.  Measured
# offsets into the canonical page text: 14-56 characters on every opener, both
# pipelines, both languages; the earliest *in-body* quotation of a title sits at
# 165 characters (en candidate p12) and the rest at 177-714.  A 120-character
# window therefore separates an opener from a quotation with better than a
# two-fold margin on each side, which is what keeps a quoted title from
# poisoning a span.
TITLE_PREFIX_CHARS = 120

# A structural plate (closing plate, signature pad) carries a short line of
# display copy.  Measured with this harness's canonical extraction: the sparsest
# *genuine* body page in the frozen baseline holds 295 characters (en p8; 345 on
# es p8), so a 60-character threshold has 4.9x of headroom -- not the order of
# magnitude an earlier comment here claimed.  More importantly the candidate has
# a 2-character interior page (en/es p19, inside loop-engineering's span) and a
# 262-character body page (en p28), so the threshold is *only* ever applied to
# the document's contiguous trailing plate run (see ``spans_from_texts``) and
# never to an interior page.  It is applied symmetrically to both pipelines.
PLATE_TEXT_MAX_CHARS = 60

# A signature pad prints the coda and may also carry a running head and a folio.
# Measured: pad pages hold 39 (en) to 44 (es) characters and the coda itself is
# 39/44 of them; the sparsest genuine body page holds 262.  48 characters of
# furniture slack therefore leaves a 200+ character margin against a body page
# that merely quotes the coda.
PAD_FURNITURE_SLACK = 48

# The coda a signature pad printed, frozen here as a *historical* literal.  The
# adapter no longer emits pads at all: the structural package replaced the padding
# loop with signature arithmetic, so nothing in either pipeline can produce this
# string on a page of its own today.  It is kept because G3's filler-page clause is
# now a **reintroduction** guard -- if pads ever come back, they come back printing
# this, and :func:`find_signature_pads` must still recognise them.  It is
# deliberately *not* bound to the adapter's source: an earlier version of this
# harness asserted the adapter still contained the expression that built it, which
# stopped protecting anything the moment the padding loop was deleted and survived
# only on a leftover local feeding an error message.
SIGNATURE_PAD_CODA_TEMPLATE = "{publication_name} — {title}"

# The invariant the structural package actually established, and the one worth
# asserting: the adapter carries no signature-pad machinery at all.  A regression
# that reintroduces it would silently put back the filler pages gate G3 bans, so
# every source line mentioning this token is reported as a G3 failure.  It is a
# gate failure rather than a hard stop so the rest of the report is still produced
# alongside it.
ADAPTER_PAD_MARKER = "signature-pad"

# --- G6 colour ------------------------------------------------------------- #
#
# The declared palette, imported from the production renderer rather than copied,
# so a token that is retuned in ``magazine.render`` cannot leave a stale literal
# behind here.  It names the colours G6 finds; it is never the *expectation* --
# the frozen baseline is, and an ink absent from this table is still compared.
REFERENCE_PALETTE: dict[str, tuple[float, ...]] = {
    "INK": tuple(INK),
    "VIOLET": tuple(VIOLET),
    "SLATE": tuple(SLATE),
    "COOL_GRAY": tuple(COOL_GRAY),
    "PALE_VIOLET": tuple(PALE_VIOLET),
    "SIGNAL_ORANGE": tuple(SIGNAL_ORANGE),
    "COVER_INK": tuple(COVER_INK),
    "COVER_VIOLET": tuple(COVER_VIOLET),
    "WHITE": tuple(WHITE),
}

# Two producers write the same ink with their own float formatting.  One 8-bit
# level -- the finest distinction any printer or raster can carry -- is
# 1/255 == 0.003922, so this tolerance is a *quarter* of one level: it cannot
# absorb a difference that could ever reach paper, and exists only so decimal
# noise is not reported as a hue error.  Measured on this edition it is never
# exercised: every chromatic value agrees to all six decimals on both pipelines,
# both languages, both surfaces.  The same figure decides whether a colour counts
# as chromatic at all, so COOL_GRAY (.88 .89 .90, a 0.02 spread) is compared as a
# tinted grey and a true neutral is not.
COLOR_VALUE_TOLERANCE = 0.0005

# The colour-setting operators this extractor models, and what they paint with.
# DeviceRGB and DeviceGray only, on purpose: see UNMODELLED_COLOR_OPERATORS.
MODELLED_COLOR_OPERATORS: dict[bytes, tuple[str, str]] = {
    b"rg": ("fill", "DeviceRGB"),
    b"RG": ("stroke", "DeviceRGB"),
    b"g": ("fill", "DeviceGray"),
    b"G": ("stroke", "DeviceGray"),
}

# Every other way a content stream can set colour.  Neither pipeline emits one
# today.  If one ever does, the chromatic-ink clause would go blind -- it would
# see *fewer* colours and report agreement -- so an occurrence is reported as a
# refusal instead, in the same spirit as G3's unparsed clauses.
UNMODELLED_COLOR_OPERATORS: tuple[bytes, ...] = (
    b"k", b"K", b"cs", b"CS", b"sc", b"SC", b"scn", b"SCN",
)

# G6's raster clause, in 0-255 units of per-pixel channel spread.  Measured worst
# residual on this edition at 144 DPI: 0.1339 (en reader page 28), 0.0690 (en
# booklet side 9), 0.0131 (es reader page 25), 0.0065 (es booklet side 4).  The
# default is *not* derived from those numbers: it is a quarter of G5's 2.0
# greyscale mean-absolute-difference allowance, i.e. "a hue residual must stay
# well inside a quarter of the greyscale residual we already accept".  That
# leaves 3.7x of headroom over today's worst surface, which is stated here so the
# default's honesty is checkable rather than asserted.
#
# What this number is worth, measured rather than assumed.  Swapping the red and
# blue channels of VIOLET *and* of SIGNAL_ORANGE in the candidate's content
# streams -- a grossly wrong hue on every accent, on 32 of the 36 reader pages --
# moves the worst page's ink ratio by 0.000013 (G4 tol 0.002), its differing-pixel
# fraction to 0.43% (G5 tol 1%), its greyscale mean absolute difference to 0.0495
# (G5 tol 2.0) and this metric to 0.2573.  So a raster metric *cannot* be the
# thing that catches a hue error on this magazine: the accents are hairlines,
# rules and small display type, and their coverage is too low to move any average
# by the margin a tolerance needs.  Tightening this default to 0.2 to catch that
# case would be fitting it to one injected fault while leaving only 1.5x over the
# honest residual.  The clause that catches it is the chromatic-ink comparison,
# which has no tolerance at all; this raster number is the corroborator that also
# sees hue inside embedded images, where no colour operator exists.
DEFAULT_MAX_CHROMA_MEAN_ABS_DIFFERENCE = 0.5

_TEXT_DIFF_MAX_LINES = 40
_TEXT_DIFF_WRAP = 88
_FAILURE_DISPLAY_LIMIT = 12
# Hard gates decide the exit code, so their failure list is printed in full up to a
# much higher bound: truncating G3 at 12 lines hid "candidate contains
# signature-pad filler pages", one of the divergences the report exists to show.
_HARD_FAILURE_DISPLAY_LIMIT = 40
_INTEGRITY_IGNORED_NAMES = frozenset({".DS_Store"})

GATE_STRENGTH_NOTES = (
    "What the hard gates prove:",
    "  G1 every reader page and booklet side declares the same media/crop/trim/",
    "     bleed/art box and /Rotate as the baseline, at the same origin.",
    "  G2 every word of every imposed booklet side sits at the exact position the",
    "     reader page that side should carry puts it, so the imposition and the",
    "     left/right mapping are measured from the booklet PDF, not from a plan.",
    "  G3 per reader page, the position-canonical extracted text (words ordered by",
    "     geometric band then x) is character-identical to the baseline's, and the",
    "     spans, starts and contents folios agree with a refusal reported as a",
    "     failure rather than as agreement.",
    "What the hard gates do NOT prove:",
    "  Extracted text erases line breaks, hyphenation points, paragraph",
    "  boundaries, NBSP and thin spaces, font, size, leading, measure, rules,",
    "  tints and figure scale.  A candidate with identical words per page but a",
    "  different typographic treatment passes every hard gate and fails only the",
    "  soft ones.  'All hard gates pass' therefore does NOT by itself mean the",
    "  contract's content-placement intent is met: read G4/G5/G6 residuals too.",
    "  G4/G5/G6 tolerances are aspirational, not fitted; they are far below the",
    "  current residual on purpose.",
    "What G6 adds, and what it still does not prove:",
    "  G1-G5 are entirely greyscale or geometric, so a token emitted with the",
    "  wrong hue passes all five.  G6's chromatic-ink clause compares, page by",
    "  page, the exact set of non-neutral colours each pipeline sets in its",
    "  content streams, so a wrong token is caught however few pixels it covers.",
    "  Its raster clause bounds per-channel RGB difference, which is the only one",
    "  of the two that sees hue inside an embedded image.  Neither sees a colour",
    "  a viewer applies (an /ExtGState blend, a soft mask, an ICC output intent),",
    "  and neither judges whether the palette is *right* -- only that the",
    "  candidate lays down the same inks the frozen baseline does.",
)


# --------------------------------------------------------------------------- #
# Path safety -- write guards and frozen-baseline integrity.
# --------------------------------------------------------------------------- #


def resolve_path(path: Path | str) -> Path:
    """Absolute, symlink-free path, whether or not the target exists yet."""
    return Path(path).expanduser().resolve()


def is_within(child: Path, parent: Path) -> bool:
    """True when ``child`` *is* ``parent`` or lives underneath it."""
    return child == parent or parent in child.parents


def protected_trees(*, root: Path, baseline_root: Path) -> dict[str, Path]:
    """The two trees this harness must never write a byte into."""
    return {
        "frozen baseline": resolve_path(baseline_root),
        "repository output tree": resolve_path(root / "output"),
    }


def overlap_reason(label: str, tree: Path, work_dir: Path) -> str | None:
    """Why ``work_dir`` may not be used, in either containment direction."""
    if work_dir == tree:
        return f"--work-dir {work_dir} *is* the {label}"
    if is_within(work_dir, tree):
        return f"--work-dir {work_dir} lives inside the {label} at {tree}"
    if is_within(tree, work_dir):
        return f"--work-dir {work_dir} contains the {label} at {tree}"
    return None


def assert_work_dir_disjoint(work_dir: Path, protected: Mapping[str, Path]) -> None:
    """Positive assertion: the work dir is disjoint from every protected tree.

    Both directions matter.  A work dir *above* a protected tree is the dangerous
    case: ``--work-dir <baseline-root>`` made the harness write its candidate over
    ``<baseline-root>/<language>/reader.pdf`` and then compare that file with
    itself, which reports a perfect score on a destroyed baseline.
    """
    for label, tree in protected.items():
        reason = overlap_reason(label, tree, work_dir)
        if reason is not None:
            raise SystemExit(
                f"Refusing to run: {reason}. Candidate artifacts must live in a tree "
                "that neither contains nor is contained by the frozen baseline or "
                "the repository output tree."
            )


class WorkDir:
    """Mints every path the harness writes and proves it lives under the work dir.

    Nothing in the harness may open a file for writing without asking this object
    for the path first, so "all artifacts land under --work-dir" is an assertion
    rather than a claim in a docstring.
    """

    def __init__(self, root: Path, protected: Mapping[str, Path]) -> None:
        self.root = resolve_path(root)
        self.protected = dict(protected)
        assert_work_dir_disjoint(self.root, self.protected)

    def path(self, *parts: str | Path) -> Path:
        target = resolve_path(self.root.joinpath(*[str(part) for part in parts]))
        if not is_within(target, self.root):
            raise SystemExit(
                f"Refusing to write {target}: it escapes --work-dir {self.root}"
            )
        for label, tree in self.protected.items():
            if is_within(target, tree):
                raise SystemExit(
                    f"Refusing to write {target}: it lands inside the {label} at {tree}"
                )
        return target

    def directory(self, *parts: str | Path) -> Path:
        target = self.path(*parts)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def relative(self, path: Path) -> str:
        return str(resolve_path(path).relative_to(self.root))


def assert_outside_protected(label: str, path: Path, protected: Mapping[str, Path]) -> None:
    """Refuse to write an out-of-work-dir artifact (the JSON report) into a tree."""
    target = resolve_path(path)
    for tree_label, tree in protected.items():
        if is_within(target, tree):
            raise SystemExit(
                f"Refusing to write {label} {target}: it lands inside the {tree_label} at {tree}"
            )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_hashes(root: Path) -> dict[str, str]:
    """``relative path -> sha256`` for every file in ``root``.

    ``.DS_Store`` is skipped: macOS Finder rewrites it spontaneously and it is not
    part of the frozen artifact set.  Everything else -- PDFs, manifests, rasters,
    ``SHA256SUMS`` -- is fingerprinted.
    """
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        if path.name in _INTEGRITY_IGNORED_NAMES:
            continue
        hashes[str(path.relative_to(root))] = sha256(path)
    return hashes


def integrity_failures(before: Mapping[str, str], after: Mapping[str, str]) -> list[str]:
    """Human-readable description of every baseline file that moved during a run."""
    failures: list[str] = []
    for name in sorted(set(before) - set(after)):
        failures.append(f"baseline file was deleted during the run: {name}")
    for name in sorted(set(after) - set(before)):
        failures.append(f"baseline file appeared during the run: {name}")
    for name in sorted(set(before) & set(after)):
        if before[name] != after[name]:
            failures.append(
                f"baseline file was modified during the run: {name} "
                f"({before[name][:12]} -> {after[name][:12]})"
            )
    return failures


def git_revision(root: Path) -> dict[str, Any]:
    """Best-effort git provenance for the candidate renderer."""
    def run(*args: str) -> str | None:
        executable = shutil.which("git")
        if not executable:
            return None
        completed = subprocess.run(
            [executable, "-C", str(root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode:
            return None
        return completed.stdout.strip()

    revision = run("rev-parse", "HEAD")
    status = run("status", "--porcelain")
    return {
        "revision": revision or "unknown",
        "dirty": bool(status) if status is not None else None,
        "dirty_paths": sorted(
            line[3:] for line in (status or "").splitlines() if line[3:]
        )[:20],
    }


# --------------------------------------------------------------------------- #
# Pure helpers -- everything below this line is unit-testable without a render.
# --------------------------------------------------------------------------- #


@dataclasses.dataclass(frozen=True)
class Gate:
    """One machine-checked gate for one language.

    ``failures`` is complete: truncation happens at print time only, so the JSON
    report never loses a failure line.
    """

    name: str
    title: str
    hard: bool
    passed: bool
    summary: str
    failures: tuple[str, ...] = ()
    details: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def as_json(self) -> dict[str, Any]:
        return {
            "gate": self.name,
            "title": self.title,
            "hard": self.hard,
            "result": "pass" if self.passed else "fail",
            "summary": self.summary,
            "failure_count": len(self.failures),
            "failures": list(self.failures),
            "details": dict(self.details),
        }


def merge_surface_gates(parts: Mapping[str, Gate]) -> Gate:
    """Fold the reader-surface and booklet-surface halves of a gate into one.

    Both surfaces are reported; the gate passes only if both do.  Failure lines
    are already surface-labelled by the comparison that produced them.
    """
    surfaces = list(parts)
    first = parts[surfaces[0]]
    return Gate(
        name=first.name,
        title=first.title,
        hard=first.hard,
        passed=all(gate.passed for gate in parts.values()),
        summary=" || ".join(f"{surface}: {parts[surface].summary}" for surface in surfaces),
        failures=tuple(line for surface in surfaces for line in parts[surface].failures),
        details={surface: dict(parts[surface].details) for surface in surfaces},
    )


def normalize_text(value: str | None) -> str:
    """Collapse every whitespace run to a single space and strip the result."""
    return " ".join((value or "").split())


def stream_page_texts(pdf: Path) -> list[str]:
    """Content-stream-order extracted text, kept only as a corroborator.

    This is what ``pypdf`` returns, i.e. the order the producer emitted text in.
    G3 does not use it: the two pipelines emit page furniture at opposite ends of
    the stream, which is a producer artifact and not a placement fact.
    """
    reader = PdfReader(str(pdf))
    return [normalize_text(page.extract_text()) for page in reader.pages]


# --------------------------------------------------------------------------- #
# Position-canonical text extraction.
# --------------------------------------------------------------------------- #


@dataclasses.dataclass(frozen=True)
class PlacedWord:
    """One extracted word with its box, in PDF points from the page's top-left."""

    x0: float
    y0: float
    x1: float
    y1: float
    text: str

    @property
    def x_center(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def y_center(self) -> float:
        return (self.y0 + self.y1) / 2


_BBOX_PAGE = re.compile(r'<page width="([0-9.eE+-]+)" height="([0-9.eE+-]+)">(.*?)</page>', re.S)
_BBOX_WORD = re.compile(
    r'<word xMin="([0-9.eE+-]+)" yMin="([0-9.eE+-]+)" '
    r'xMax="([0-9.eE+-]+)" yMax="([0-9.eE+-]+)">(.*?)</word>',
    re.S,
)


def parse_bbox_xml(xml: str) -> list[list[PlacedWord]]:
    """Parse ``pdftotext -bbox`` output into per-page word boxes."""
    pages: list[list[PlacedWord]] = []
    for page in _BBOX_PAGE.finditer(xml):
        pages.append(
            [
                PlacedWord(
                    float(x0), float(y0), float(x1), float(y1), html.unescape(text)
                )
                for x0, y0, x1, y1, text in _BBOX_WORD.findall(page.group(3))
            ]
        )
    return pages


def word_pages(pdf: Path) -> list[list[PlacedWord]]:
    """Every page's words with coordinates, via Poppler's ``pdftotext -bbox``."""
    executable = shutil.which("pdftotext")
    if not executable:
        raise SystemExit(
            "Position-canonical text extraction requires Poppler's pdftotext "
            "executable (brew install poppler)."
        )
    completed = subprocess.run(
        [executable, "-bbox", str(pdf), "-"], capture_output=True, text=True, check=False
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        raise SystemExit(f"pdftotext could not read {pdf}: {detail}")
    return parse_bbox_xml(completed.stdout)


def band_rows(words: Sequence[PlacedWord], *, tolerance: float) -> list[list[PlacedWord]]:
    """Group words into horizontal bands top-to-bottom, each sorted left-to-right.

    A word joins the open band when its vertical centre is within ``tolerance``
    points of the band's first word; otherwise it opens a new band.  See
    :data:`DEFAULT_TEXT_BAND_TOLERANCE` for the measured rationale.
    """
    bands: list[list[PlacedWord]] = []
    anchors: list[float] = []
    for word in sorted(words, key=lambda item: (item.y_center, item.x0, item.text)):
        if bands and word.y_center - anchors[-1] <= tolerance:
            bands[-1].append(word)
        else:
            bands.append([word])
            anchors.append(word.y_center)
    return [sorted(band, key=lambda item: (item.x0, item.text)) for band in bands]


def canonical_page_text(words: Sequence[PlacedWord], *, tolerance: float) -> str:
    """Whitespace-collapsed page text in geometric reading order."""
    return normalize_text(
        " ".join(word.text for band in band_rows(words, tolerance=tolerance) for word in band)
    )


def canonical_page_texts(
    pages: Sequence[Sequence[PlacedWord]], *, tolerance: float
) -> list[str]:
    return [canonical_page_text(page, tolerance=tolerance) for page in pages]


def text_unified_diff(
    baseline: str,
    candidate: str,
    *,
    max_lines: int = _TEXT_DIFF_MAX_LINES,
    wrap: int = _TEXT_DIFF_WRAP,
) -> list[str]:
    """A readable, truncated unified diff of two normalized page texts."""

    def wrapped(text: str) -> list[str]:
        words = text.split(" ")
        lines: list[str] = []
        current = ""
        for word in words:
            if not current:
                current = word
            elif len(current) + 1 + len(word) <= wrap:
                current = f"{current} {word}"
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [""]

    diff = list(
        difflib.unified_diff(
            wrapped(baseline),
            wrapped(candidate),
            fromfile="baseline",
            tofile="candidate",
            lineterm="",
            n=1,
        )
    )
    if len(diff) > max_lines:
        omitted = len(diff) - max_lines
        diff = diff[:max_lines] + [f"... ({omitted} more diff lines omitted)"]
    return diff


def compare_page_texts(
    baseline: Sequence[str], candidate: Sequence[str]
) -> dict[str, Any]:
    """Compare normalized page text pairwise and locate the first divergence."""
    shared = min(len(baseline), len(candidate))
    differing = [index + 1 for index in range(shared) if baseline[index] != candidate[index]]
    if len(baseline) != len(candidate):
        differing.extend(range(shared + 1, max(len(baseline), len(candidate)) + 1))
    first = differing[0] if differing else None
    diff: list[str] = []
    if first is not None:
        diff = text_unified_diff(
            baseline[first - 1] if first <= len(baseline) else "",
            candidate[first - 1] if first <= len(candidate) else "",
        )
    return {
        "baseline_pages": len(baseline),
        "candidate_pages": len(candidate),
        "compared_pages": max(len(baseline), len(candidate)),
        "matching_pages": shared - len([p for p in differing if p <= shared]),
        "differing_pages": differing,
        # The scalar residual, next to the list, so no reader of the JSON has to
        # count a list to learn how many pages actually differ.
        "differing_page_count": len(differing),
        "first_differing_page": first,
        "first_difference_diff": diff,
        "page_word_counts": [
            {
                "page": page,
                "baseline_words": _word_count(baseline, page),
                "candidate_words": _word_count(candidate, page),
                "delta": _word_count(candidate, page) - _word_count(baseline, page),
            }
            for page in range(1, max(len(baseline), len(candidate)) + 1)
        ],
    }


def _word_count(texts: Sequence[str], page: int) -> int:
    """Words on ``page`` (1-based) of a canonical text list; 0 if it has no page."""
    if not 0 < page <= len(texts):
        return 0
    return len(texts[page - 1].split())


# --------------------------------------------------------------------------- #
# G1 geometry.
# --------------------------------------------------------------------------- #


def page_boxes(pdf: Path) -> list[dict[str, Any]]:
    """Every page's declared boxes and rotation.

    Width and height alone are not geometry: ``impose_a5_on_a4`` merges by
    ``mediabox.width``/``height`` and ignores the box *origin*, so a reader whose
    mediabox is ``[20 20 439.53 615.28]`` rasterizes identically (Poppler crops to
    the box) while every imposed booklet side is 20pt out of position.  The origin,
    ``/CropBox``, ``/TrimBox``, ``/BleedBox``, ``/ArtBox`` and ``/Rotate`` are
    therefore all recorded.  An absent ``/Rotate`` is normalized to 0, which is
    what it means.
    """
    reader = PdfReader(str(pdf))
    rows: list[dict[str, Any]] = []
    for page in reader.pages:
        row: dict[str, Any] = {}
        for name in BOX_NAMES:
            box = getattr(page, name)
            row[name] = tuple(round(float(value), 4) for value in box)
        try:
            rotate = int(page.get("/Rotate", 0) or 0)
        except (TypeError, ValueError):
            rotate = 0
        row["rotate"] = rotate % 360
        row["declared_boxes"] = tuple(sorted(key for key in page.keys() if "Box" in str(key)))
        rows.append(row)
    return rows


def compare_geometry(
    *,
    baseline_reader: Sequence[Mapping[str, Any]],
    candidate_reader: Sequence[Mapping[str, Any]],
    baseline_booklet: Sequence[Mapping[str, Any]],
    candidate_booklet: Sequence[Mapping[str, Any]],
    tolerance: float = MEDIABOX_TOLERANCE,
) -> Gate:
    """Page counts, every declared box (with its origin) and /Rotate, both surfaces."""
    failures: list[str] = []

    def check_expected(
        label: str, rows: Sequence[Mapping[str, Any]], expected: tuple[float, ...]
    ) -> None:
        for index, row in enumerate(rows, 1):
            for name in BOX_NAMES:
                box = tuple(row.get(name) or ())
                if len(box) != 4 or any(
                    abs(box[edge] - expected[edge]) > tolerance for edge in range(4)
                ):
                    failures.append(
                        f"{label} page {index} {name} is {_fmt_box(box)}, "
                        f"expected {_fmt_box(expected)}"
                    )
            if int(row.get("rotate", 0)) != 0:
                failures.append(f"{label} page {index} /Rotate is {row.get('rotate')}, expected 0")

    def check_pairwise(
        label: str,
        baseline_rows: Sequence[Mapping[str, Any]],
        candidate_rows: Sequence[Mapping[str, Any]],
    ) -> None:
        for index in range(min(len(baseline_rows), len(candidate_rows))):
            want, got = baseline_rows[index], candidate_rows[index]
            for name in (*BOX_NAMES, "rotate"):
                left, right = want.get(name), got.get(name)
                if name == "rotate":
                    if int(left or 0) != int(right or 0):
                        failures.append(
                            f"{label} page {index + 1} /Rotate is {right}, baseline {left}"
                        )
                    continue
                left_box, right_box = tuple(left or ()), tuple(right or ())
                if len(left_box) != len(right_box) or any(
                    abs(a - b) > tolerance for a, b in zip(left_box, right_box)
                ):
                    failures.append(
                        f"{label} page {index + 1} {name} is {_fmt_box(right_box)}, "
                        f"baseline {_fmt_box(left_box)}"
                    )

    if len(baseline_reader) != len(candidate_reader):
        failures.append(
            f"reader page count {len(candidate_reader)} != baseline {len(baseline_reader)}"
        )
    if len(baseline_booklet) != len(candidate_booklet):
        failures.append(
            f"booklet page count {len(candidate_booklet)} != baseline {len(baseline_booklet)}"
        )
    check_expected("candidate reader", candidate_reader, A5_PAGE_BOX)
    check_expected("baseline reader", baseline_reader, A5_PAGE_BOX)
    check_expected("candidate booklet", candidate_booklet, A4_LANDSCAPE_PAGE_BOX)
    check_expected("baseline booklet", baseline_booklet, A4_LANDSCAPE_PAGE_BOX)
    check_pairwise("reader", baseline_reader, candidate_reader)
    check_pairwise("booklet", baseline_booklet, candidate_booklet)

    summary = (
        f"reader {len(candidate_reader)}/{len(baseline_reader)} pages, "
        f"booklet {len(candidate_booklet)}/{len(baseline_booklet)} sides "
        f"(candidate/baseline); every media/crop/trim/bleed/art box and /Rotate "
        f"identical to baseline and to the canonical box within {tolerance}pt; "
        f"{len(failures)} geometry problem(s)"
    )
    return Gate(
        name="G1",
        title="Geometry",
        hard=True,
        passed=not failures,
        summary=summary,
        failures=tuple(failures),
        details={
            "baseline_reader_pages": len(baseline_reader),
            "candidate_reader_pages": len(candidate_reader),
            "baseline_booklet_pages": len(baseline_booklet),
            "candidate_booklet_pages": len(candidate_booklet),
            "boxes_compared": list(BOX_NAMES) + ["rotate"],
            "distinct_candidate_reader_boxes": _distinct_boxes(candidate_reader),
            "distinct_candidate_booklet_boxes": _distinct_boxes(candidate_booklet),
            "distinct_baseline_reader_boxes": _distinct_boxes(baseline_reader),
            "distinct_baseline_booklet_boxes": _distinct_boxes(baseline_booklet),
            "box_tolerance_points": tolerance,
        },
    )


def _fmt_box(box: Sequence[float]) -> str:
    if not box:
        return "absent"
    return "[" + " ".join(f"{value:.4f}" for value in box) + "]"


def _distinct_boxes(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
    for index, row in enumerate(rows, 1):
        key = tuple(tuple(row.get(name) or ()) for name in BOX_NAMES) + (
            int(row.get("rotate", 0) or 0),
            tuple(row.get("declared_boxes") or ()),
        )
        entry = seen.setdefault(
            key,
            {
                **{name: list(row.get(name) or ()) for name in BOX_NAMES},
                "rotate": int(row.get("rotate", 0) or 0),
                "declared_boxes": [str(name) for name in row.get("declared_boxes") or ()],
                "pages": [],
            },
        )
        entry["pages"].append(index)
    return list(seen.values())


# --------------------------------------------------------------------------- #
# G2 imposition, measured from the booklet PDF.
# --------------------------------------------------------------------------- #


def imposition_mapping(page_count: int) -> list[tuple[int, int]]:
    """The (left, right) reader-page plan for each booklet side.

    This is a pure function of the page count on *both* sides, so comparing two
    plans is tautological once G1 passes.  It is used as the *expectation* the
    measured mapping is held against, never as evidence in itself.
    """
    return [tuple(pair) for pair in booklet_spreads(page_count)]


def slot_words(
    words: Sequence[PlacedWord], *, slot: int, sheet_width: float
) -> list[PlacedWord]:
    """The words of one imposed A5 slot of a landscape A4 side."""
    half = sheet_width / 2
    if slot == 0:
        return [word for word in words if word.x_center < half]
    return [word for word in words if word.x_center >= half]


def _placement_key(word: PlacedWord) -> tuple[float, float, str]:
    return (round(word.y0, 3), round(word.x0, 3), word.text)


def placement_mismatches(
    imposed: Sequence[PlacedWord],
    source: Sequence[PlacedWord],
    *,
    x_offset: float,
    tolerance: float = IMPOSITION_POSITION_TOLERANCE,
    limit: int = 3,
) -> list[str]:
    """Why an imposed slot is not the source reader page, positionally.

    Both sequences are read in geometric order and compared word by word: same
    word, same y, same x once the slot origin is removed.  A uniform shift -- the
    exact symptom of a reader mediabox whose origin is not (0, 0) -- shows up here
    as every word being off by the same amount, which no text-order check can see.
    """
    return _placement_problems(
        sorted(imposed, key=_placement_key),
        sorted(source, key=_placement_key),
        x_offset=x_offset,
        tolerance=tolerance,
        limit=limit,
    )


def _placement_problems(
    left: Sequence[PlacedWord],
    right: Sequence[PlacedWord],
    *,
    x_offset: float,
    tolerance: float,
    limit: int,
) -> list[str]:
    """``placement_mismatches`` on sequences already in geometric order."""
    problems: list[str] = []
    if len(left) != len(right):
        problems.append(f"carries {len(left)} words, the reader page has {len(right)}")
    for imposed_word, source_word in zip(left, right):
        if len(problems) >= limit:
            break
        want_x = source_word.x0 + x_offset
        if imposed_word.text != source_word.text:
            problems.append(
                f"word {imposed_word.text!r} where the reader page has {source_word.text!r}"
            )
        elif (
            abs(imposed_word.x0 - want_x) > tolerance
            or abs(imposed_word.y0 - source_word.y0) > tolerance
        ):
            problems.append(
                f"{imposed_word.text!r} at ({imposed_word.x0:.3f}, {imposed_word.y0:.3f}) "
                f"instead of ({want_x:.3f}, {source_word.y0:.3f}) "
                f"[dx {imposed_word.x0 - want_x:+.3f}, dy {imposed_word.y0 - source_word.y0:+.3f}]"
            )
    return problems[:limit]


def measured_imposition(
    *,
    booklet_words: Sequence[Sequence[PlacedWord]],
    reader_words: Sequence[Sequence[PlacedWord]],
    plan: Sequence[tuple[int, int]],
    sheet_width: float = A4_LANDSCAPE_MEDIABOX[0],
    tolerance: float = IMPOSITION_POSITION_TOLERANCE,
) -> list[dict[str, Any]]:
    """Derive, per booklet side, which reader page each slot actually carries.

    For each slot the words are matched positionally against every reader page.
    Truly blank pages are indistinguishable from each other by text, so when the
    expected page is among the matches it is reported and the ambiguity recorded;
    the blank inside-cover side is additionally required to be an ink-free raster.
    """
    ordered_reader = [sorted(page, key=_placement_key) for page in reader_words]
    rows: list[dict[str, Any]] = []
    for side_index in range(len(booklet_words)):
        expected = plan[side_index] if side_index < len(plan) else (None, None)
        side = booklet_words[side_index]
        row: dict[str, Any] = {"side": side_index + 1, "slots": []}
        for slot, origin in enumerate(IMPOSITION_SLOT_ORIGINS):
            words = sorted(
                slot_words(side, slot=slot, sheet_width=sheet_width), key=_placement_key
            )
            want = expected[slot] if slot < len(expected) else None
            matches = [
                page
                for page in range(1, len(ordered_reader) + 1)
                if len(ordered_reader[page - 1]) == len(words)
                and not _placement_problems(
                    words,
                    ordered_reader[page - 1],
                    x_offset=origin,
                    tolerance=tolerance,
                    limit=1,
                )
            ]
            if want is not None and want in matches:
                observed: int | None = want
            elif len(matches) == 1:
                observed = matches[0]
            else:
                observed = None
            mismatch: list[str] = []
            if want is not None and want <= len(ordered_reader) and observed != want:
                mismatch = _placement_problems(
                    words,
                    ordered_reader[want - 1],
                    x_offset=origin,
                    tolerance=tolerance,
                    limit=3,
                )
            row["slots"].append(
                {
                    "slot": "left" if slot == 0 else "right",
                    "x_offset": origin,
                    "expected_reader_page": want,
                    "observed_reader_page": observed,
                    "matching_reader_pages": matches,
                    "ambiguous": len(matches) > 1,
                    "word_count": len(words),
                    "mismatches": mismatch,
                }
            )
        row["observed_mapping"] = [slot["observed_reader_page"] for slot in row["slots"]]
        row["expected_mapping"] = list(expected)
        rows.append(row)
    return rows


def compare_imposition(
    *,
    baseline_reader_pages: int,
    candidate_reader_pages: int,
    baseline_measured: Sequence[Mapping[str, Any]],
    candidate_measured: Sequence[Mapping[str, Any]],
    baseline_spreads: Sequence[Mapping[str, Any]],
    candidate_spreads: Sequence[Mapping[str, Any]],
    baseline_inside_covers: Mapping[str, Any],
    candidate_inside_covers: Mapping[str, Any],
) -> Gate:
    """Compare the *measured* booklet imposition of both pipelines.

    ``*_measured`` comes from :func:`measured_imposition`, i.e. from the booklet
    PDFs themselves.  ``*_spreads`` are :func:`render_critic._booklet_spread_checks`
    rows, kept only as a concatenated-text corroborator; they take their left/right
    numbers from the plan they were handed, so they cannot evidence the mapping.
    ``*_inside_covers`` comes from :func:`inside_cover_report`.
    """
    failures: list[str] = []
    baseline_plan = imposition_mapping(baseline_reader_pages)
    candidate_plan = imposition_mapping(candidate_reader_pages)
    if len(baseline_plan) != len(candidate_plan):
        failures.append(
            f"booklet plans {len(candidate_plan)} sides, baseline plans {len(baseline_plan)}"
        )
    for side, (want, got) in enumerate(zip(baseline_plan, candidate_plan), 1):
        if want != got:
            failures.append(f"side {side} plan is {got}, baseline plans {want}")
            break

    def check_measured(label: str, rows: Sequence[Mapping[str, Any]]) -> None:
        for row in rows:
            side = row["side"]
            for slot in row["slots"]:
                want = slot["expected_reader_page"]
                got = slot["observed_reader_page"]
                if want == got:
                    continue
                detail = "; ".join(slot["mismatches"]) or (
                    f"matching reader pages {slot['matching_reader_pages']}"
                )
                failures.append(
                    f"{label} booklet side {side} {slot['slot']} slot carries reader page "
                    f"{got} where the plan puts {want}: {detail}"
                )

    check_measured("baseline", baseline_measured)
    check_measured("candidate", candidate_measured)

    def mapping_of(rows: Sequence[Mapping[str, Any]]) -> list[list[Any]]:
        return [list(row["observed_mapping"]) for row in rows]

    if mapping_of(baseline_measured) != mapping_of(candidate_measured):
        for side, (want, got) in enumerate(
            zip(mapping_of(baseline_measured), mapping_of(candidate_measured)), 1
        ):
            if want != got:
                failures.append(
                    f"measured left/right mapping on side {side} is {got}, baseline {want}"
                )
        if len(baseline_measured) != len(candidate_measured):
            failures.append(
                f"measured {len(candidate_measured)} candidate sides against "
                f"{len(baseline_measured)} baseline sides"
            )

    for label, rows in (("baseline", baseline_spreads), ("candidate", candidate_spreads)):
        broken = [int(row["side"]) for row in rows if not row["text_order_matches"]]
        if broken:
            failures.append(
                f"{label} booklet sides {broken[:6]} do not contain the expected reader page pair"
            )
    for label, report in (
        ("baseline", baseline_inside_covers),
        ("candidate", candidate_inside_covers),
    ):
        for line in report.get("failures", ()):
            failures.append(f"{label} {line}")

    ambiguous = sum(
        1 for row in candidate_measured for slot in row["slots"] if slot["ambiguous"]
    )
    return Gate(
        name="G2",
        title="Imposition",
        hard=True,
        passed=not failures,
        summary=(
            f"{len(candidate_measured)} booklet sides; every slot's words measured at the "
            f"reader page's own coordinates ({ambiguous} blank slot(s) text-ambiguous); "
            "inside-cover side ink-free in both"
            if not failures
            else f"{len(failures)} imposition problem(s)"
        ),
        failures=tuple(failures),
        details={
            "baseline_plan": [list(pair) for pair in baseline_plan],
            "candidate_plan": [list(pair) for pair in candidate_plan],
            "baseline_measured": [dict(row) for row in baseline_measured],
            "candidate_measured": [dict(row) for row in candidate_measured],
            "position_tolerance_points": IMPOSITION_POSITION_TOLERANCE,
            "candidate_sides_matching_reader_text": sum(
                1 for row in candidate_spreads if row["text_order_matches"]
            ),
            "baseline_sides_matching_reader_text": sum(
                1 for row in baseline_spreads if row["text_order_matches"]
            ),
            "inside_covers": {
                "baseline": dict(baseline_inside_covers),
                "candidate": dict(candidate_inside_covers),
            },
        },
    )


# --------------------------------------------------------------------------- #
# G3 content placement.
# --------------------------------------------------------------------------- #


def _fold(text: str) -> str:
    """Normalize whitespace and fold case, so display transforms still match."""
    return normalize_text(text).casefold()


def signature_coda(edition: Any) -> str:
    """The coda a signature pad would print, from the frozen historical template.

    See :data:`SIGNATURE_PAD_CODA_TEMPLATE`: the adapter no longer emits pads, so
    this is what a *reintroduced* one would carry, not what either pipeline prints
    today.  :func:`find_signature_pads` searches both pipelines' pages for it.
    """
    return SIGNATURE_PAD_CODA_TEMPLATE.format(
        publication_name=edition.publication_name, title=edition.title
    )


def adapter_source() -> str:
    from magazine import weasyprint_adapter

    return inspect.getsource(weasyprint_adapter)


def pad_marker_lines(source: str, *, marker: str = ADAPTER_PAD_MARKER) -> list[int]:
    """Source lines of the adapter that reintroduce signature-pad machinery.

    Empty on the structural adapter, which closes its signature with plates.  A
    non-empty result means the padding loop -- or something naming itself after it
    -- is back, which is the regression G3's filler-page clause exists to catch
    before the pages themselves reach a reader.
    """
    return [
        number
        for number, line in enumerate(source.splitlines(), 1)
        if marker in line
    ]


def find_signature_pads(
    texts: Sequence[str], coda: str, *, furniture_slack: int = PAD_FURNITURE_SLACK
) -> list[int]:
    """Reader pages that are a signature pad: the coda plus at most page furniture.

    Matching is by containment, not equality, so a pad that also carries a running
    head, a folio in either position, or both is still recognised; the length bound
    keeps a body page that merely quotes the coda from being mistaken for a pad.
    """
    needle = _fold(coda)
    if not needle:
        return []
    hits: list[int] = []
    for index, text in enumerate(texts, 1):
        folded = _fold(text)
        if needle in folded and len(folded) - len(needle) <= furniture_slack:
            hits.append(index)
    return hits


def longest_increasing_run(values: Sequence[int]) -> tuple[list[int], int]:
    """Return one longest strictly increasing subsequence and how many exist.

    A count above one means the input is ambiguous, which callers use to refuse
    to guess rather than report a plausible-looking wrong answer.
    """
    total = len(values)
    if not total:
        return [], 0
    length = [1] * total
    ways = [1] * total
    for index in range(total):
        for earlier in range(index):
            if values[earlier] >= values[index]:
                continue
            if length[earlier] + 1 > length[index]:
                length[index] = length[earlier] + 1
                ways[index] = ways[earlier]
            elif length[earlier] + 1 == length[index]:
                ways[index] += ways[earlier]
    best = max(length)
    count = sum(ways[index] for index in range(total) if length[index] == best)
    chosen: list[int] = []
    wanted = best
    limit: int | None = None
    for index in range(total - 1, -1, -1):
        if length[index] == wanted and (limit is None or values[index] < limit):
            chosen.append(values[index])
            limit = values[index]
            wanted -= 1
    return list(reversed(chosen)), count


def contents_folios(
    contents_text: str,
    entry_order: Sequence[str],
    *,
    first_body_page: int,
    page_count: int,
) -> dict[str, int | None]:
    """Folio numbers printed on the contents page, in contents order.

    Both pipelines print one folio per entry in reading order, but they disagree
    about where the number sits relative to its title: ReportLab interleaves
    ``"05 FEATURE 01 <title>"`` while WeasyPrint's grid emits every folio before
    every title, so position-relative parsing cannot work for both.  Instead the
    integers inside the body page range are read in document order and reduced to
    their longest strictly increasing subsequence, which discards label numbering
    such as the ``04`` of ``"FEATURE 04"``.  If that subsequence is the wrong
    length or is not unique, every folio is reported as ``None``: callers must
    treat that refusal as a failure, never as agreement.
    """
    numbers = [
        int(match)
        for match in re.findall(r"\d{1,4}", contents_text)
        if first_body_page <= int(match) <= page_count
    ]
    folios, ways = longest_increasing_run(numbers)
    if len(folios) != len(entry_order) or ways != 1:
        return {key: None for key in entry_order}
    return dict(zip(entry_order, folios))


def structural_starts(
    texts: Sequence[str],
    titles: Mapping[str, str],
    *,
    first_body_page: int,
    title_prefix_chars: int = TITLE_PREFIX_CHARS,
) -> dict[str, int | None]:
    """First reader page at or after ``first_body_page`` that *opens* with a title.

    A page opens an entry when its title appears within the first
    ``title_prefix_chars`` of the page's canonical text -- i.e. in the opening
    bands, after the page furniture.  A plain first-substring search would happily
    return a page that merely quotes the title inside a paragraph, which poisons
    the span and the folio corroboration; measured offsets separate the two cases
    by better than 2x (see :data:`TITLE_PREFIX_CHARS`).  Matching is case-folded so
    a stylesheet that uppercases display titles does not silently lose the entry.
    """
    starts: dict[str, int | None] = {}
    for key, title in titles.items():
        needle = _fold(title)
        found: int | None = None
        if needle:
            for page, text in enumerate(texts, 1):
                if page < first_body_page:
                    continue
                if needle in _fold(text)[:title_prefix_chars]:
                    found = page
                    break
        starts[key] = found
    return starts


def title_occurrences(
    texts: Sequence[str], titles: Mapping[str, str], *, first_body_page: int
) -> dict[str, list[int]]:
    """Every body page whose text contains each title, for report visibility."""
    return {
        key: [
            page
            for page, text in enumerate(texts, 1)
            if page >= first_body_page and _fold(title) and _fold(title) in _fold(text)
        ]
        for key, title in titles.items()
    }


def structural_tail_start(
    texts: Sequence[str],
    *,
    plate_text_max_chars: int = PLATE_TEXT_MAX_CHARS,
    pad_pages: Sequence[int] = (),
    trailing_cover_pages: int = 2,
) -> int:
    """First page of the document's contiguous trailing non-body run.

    The tail is the two trailing cover slots (inside back cover and back cover --
    the back cover carries real cover copy, so a character threshold alone cannot
    recognise it), any signature pad, and the run of plate-like pages immediately
    before them.  Scanning *backwards* from the end is what makes span derivation
    robust: a near-empty page in the middle of an article (the candidate's p19
    holds 2 characters) can no longer truncate a span and point the next fixer at
    a defect that does not exist.
    """
    total = len(texts)
    pads = {int(page) for page in pad_pages}
    boundary = total + 1
    for page in range(total, 0, -1):
        text = texts[page - 1]
        is_tail = (
            page > total - trailing_cover_pages
            or page in pads
            or len(text) < plate_text_max_chars
        )
        if not is_tail:
            break
        boundary = page
    return boundary


def spans_from_texts(
    texts: Sequence[str],
    starts: Mapping[str, int | None],
    *,
    plate_text_max_chars: int = PLATE_TEXT_MAX_CHARS,
    pad_pages: Sequence[int] = (),
    trailing_cover_pages: int = 2,
) -> dict[str, int | None]:
    """Derive the page span of each structural entry from the PDF text alone.

    An entry runs from its own start page up to the page before the next start.
    The final entry runs up to the start of the document's trailing structural
    tail (see :func:`structural_tail_start`).  A start that is itself inside the
    tail yields ``None``, which callers report as a refusal.
    """
    ordered = sorted(
        ((key, page) for key, page in starts.items() if page is not None),
        key=lambda item: item[1],
    )
    spans: dict[str, int | None] = {key: None for key in starts}
    tail = structural_tail_start(
        texts,
        plate_text_max_chars=plate_text_max_chars,
        pad_pages=pad_pages,
        trailing_cover_pages=trailing_cover_pages,
    )
    for index, (key, start) in enumerate(ordered):
        if index + 1 < len(ordered):
            spans[key] = ordered[index + 1][1] - start
            continue
        spans[key] = (tail - start) if tail > start else None
    return spans


def redistribution_report(
    *,
    baseline_texts: Sequence[str],
    candidate_texts: Sequence[str],
    baseline_starts: Mapping[str, int | None],
    candidate_starts: Mapping[str, int | None],
    baseline_spans: Mapping[str, int | None],
    candidate_spans: Mapping[str, int | None],
) -> list[dict[str, Any]]:
    """Per-entry word-count deltas for entries whose start *and* span already agree.

    "Same spans, different content distribution" is a distinct state from "wrong
    spans", and it is the one that tells whoever converges the remaining text where
    the body copy is actually breaking differently: an entry can open on the right
    page, occupy the right number of pages, and still hold 184 words on page 17
    where the baseline holds 124.  Nothing here decides pass or fail -- G3's
    per-page text-equality clause already fails on those pages -- it only names
    them, which today is only visible by diffing page text by hand.
    """
    rows: list[dict[str, Any]] = []
    for key in sorted(
        set(baseline_starts) | set(candidate_starts),
        key=lambda name: (baseline_starts.get(name) or 0, name),
    ):
        start = baseline_starts.get(key)
        span = baseline_spans.get(key)
        aligned = (
            start is not None
            and span is not None
            and start == candidate_starts.get(key)
            and span == candidate_spans.get(key)
        )
        pages: list[dict[str, int]] = []
        if aligned:
            assert start is not None and span is not None  # narrowed by ``aligned``
            for page in range(start, start + span):
                want = _word_count(baseline_texts, page)
                got = _word_count(candidate_texts, page)
                pages.append(
                    {
                        "page": page,
                        "baseline_words": want,
                        "candidate_words": got,
                        "delta": got - want,
                    }
                )
        rows.append(
            {
                "entry": key,
                "start": start,
                "span": span,
                "start_and_span_match": aligned,
                "redistributes": aligned and any(page["delta"] for page in pages),
                "worst_page_delta": max((abs(page["delta"]) for page in pages), default=0),
                "total_word_delta": sum(page["delta"] for page in pages),
                "page_word_counts": pages,
            }
        )
    return rows


def redistribution_note(rows: Sequence[Mapping[str, Any]], *, limit: int = 3) -> str:
    """One line naming the aligned entries that still redistribute their body copy."""
    moved = [row for row in rows if row.get("redistributes")]
    if not moved:
        return ""
    aligned = sum(1 for row in rows if row.get("start_and_span_match"))
    shown = sorted(moved, key=lambda row: -int(row["worst_page_delta"]))[:limit]
    detail = "; ".join(
        f"{row['entry']} "
        + ", ".join(
            f"p{page['page']} {page['baseline_words']}->{page['candidate_words']}"
            for page in sorted(
                row["page_word_counts"], key=lambda page: -abs(int(page["delta"]))
            )[:2]
            if page["delta"]
        )
        for row in shown
    )
    more = len(moved) - len(shown)
    return (
        f"{len(moved)} of {aligned} entries with matching start and span still "
        f"redistribute body copy: {detail}" + (f"; +{more} more" if more > 0 else "")
    )


def compare_content(
    *,
    text_comparison: Mapping[str, Any],
    baseline_layout_spans: Mapping[str, int],
    candidate_layout_spans: Mapping[str, int],
    baseline_editorial_pages: int | None,
    candidate_editorial_pages: int | None,
    baseline_pdf_starts: Mapping[str, int | None],
    candidate_pdf_starts: Mapping[str, int | None],
    baseline_pdf_spans: Mapping[str, int | None],
    candidate_pdf_spans: Mapping[str, int | None],
    baseline_folios: Mapping[str, int | None],
    candidate_folios: Mapping[str, int | None],
    candidate_layout_toc: Mapping[str, int],
    signature_pad_pages: Sequence[int],
    adapter_pad_marker_lines: Sequence[int] = (),
    redistribution: Sequence[Mapping[str, Any]] = (),
    baseline_title_occurrences: Mapping[str, Sequence[int]] | None = None,
    candidate_title_occurrences: Mapping[str, Sequence[int]] | None = None,
) -> Gate:
    """Every content clause of G3, with refusals reported as failures.

    ``None`` never counts as agreement.  ``contents_folios`` returns ``None`` when
    the contents page is ambiguous, ``structural_starts`` when no page opens with
    the title, and ``spans_from_texts`` propagates both -- so a clause that could
    not be parsed on *either* side is a loud failure with an ``unparsed`` reason,
    not a silent match.  This matters because the frozen manifest carries no
    ``layout.toc``: the text parse is the only baseline source for folios.
    """
    failures: list[str] = []
    unparsed: list[dict[str, Any]] = []

    def compare_mapping(
        clause: str,
        baseline: Mapping[str, int | None],
        candidate: Mapping[str, int | None],
        *,
        unit: str = "",
    ) -> None:
        suffix = f" {unit}" if unit else ""
        for key in sorted(set(baseline) | set(candidate)):
            want = baseline.get(key)
            got = candidate.get(key)
            missing = [side for side, value in (("baseline", want), ("candidate", got)) if value is None]
            if missing:
                unparsed.append({"clause": clause, "key": key, "unparsed_sides": missing})
                failures.append(
                    f"{clause} for {key} could not be parsed on {' and '.join(missing)} "
                    f"(baseline {want}, candidate {got}); a refusal is not agreement"
                )
                continue
            if want != got:
                failures.append(f"{clause} for {key}: candidate {got}{suffix}, baseline {want}")

    first = text_comparison["first_differing_page"]
    if first is not None:
        failures.append(
            f"first differing reader page is {first} "
            f"({len(text_comparison['differing_pages'])} of "
            f"{text_comparison['baseline_pages']} pages differ)"
        )

    for key in sorted(set(baseline_layout_spans) | set(candidate_layout_spans)):
        want = baseline_layout_spans.get(key)
        got = candidate_layout_spans.get(key)
        if want != got:
            failures.append(f"layout span for {key}: candidate {got} pages, baseline {want}")
    if baseline_editorial_pages != candidate_editorial_pages:
        failures.append(
            f"layout editorial span: candidate {candidate_editorial_pages} pages, "
            f"baseline {baseline_editorial_pages}"
        )

    compare_mapping("PDF start page", baseline_pdf_starts, candidate_pdf_starts)
    compare_mapping("PDF span", baseline_pdf_spans, candidate_pdf_spans, unit="pages")
    compare_mapping("contents folio", baseline_folios, candidate_folios)

    # Corroborator: the folio a contents entry prints must be the page its title
    # actually opens on.  True on both pipelines today, and it catches a contents
    # parse that happens to agree across pipelines while disagreeing with the PDF.
    for label, folios, starts in (
        ("baseline", baseline_folios, baseline_pdf_starts),
        ("candidate", candidate_folios, candidate_pdf_starts),
    ):
        for key in sorted(set(folios) | set(starts)):
            folio, start = folios.get(key), starts.get(key)
            if folio is None or start is None:
                continue  # already reported as unparsed above
            if folio != start:
                failures.append(
                    f"{label} contents folio for {key} is {folio} but its title opens "
                    f"reader page {start}"
                )

    for key, page in sorted(candidate_layout_toc.items()):
        expected = candidate_folios.get(key)
        if expected is not None and expected != page:
            failures.append(
                f"candidate RenderLayout toc puts {key} on page {page} but its "
                f"contents page prints folio {expected}"
            )

    if signature_pad_pages:
        failures.append(
            "candidate contains signature-pad filler pages at "
            + ", ".join(str(page) for page in signature_pad_pages)
        )
    if adapter_pad_marker_lines:
        failures.append(
            "magazine.weasyprint_adapter reintroduces signature-pad machinery at source "
            "line(s) "
            + ", ".join(str(line) for line in adapter_pad_marker_lines)
            + f" (contains {ADAPTER_PAD_MARKER!r}); the structural package replaced the "
            "padding loop with signature arithmetic and G3 bans filler pages"
        )

    # Both numbers, always, in the order they are easiest to confuse: how many
    # clauses fail, and how many pages actually differ.  Seventeen span/start/folio/
    # filler clauses retiring took G3 from 18 failures to 1 while the surviving
    # aggregate clause still reported 32 of 36 pages differing -- unchanged.  A
    # shrinking clause count must never read as a shrinking residual.
    differing = int(text_comparison.get("differing_page_count", 0) or 0)
    compared = int(
        text_comparison.get("compared_pages")
        or max(
            int(text_comparison.get("baseline_pages", 0) or 0),
            int(text_comparison.get("candidate_pages", 0) or 0),
        )
    )
    first_differing = text_comparison["first_differing_page"]
    residual = {
        "clause_failures": len(failures),
        "reader_pages_differing": differing,
        "reader_pages_compared": compared,
        "first_differing_page": first_differing,
    }
    summary = (
        f"{len(failures)} clause(s) failing; "
        f"{differing} of {compared} reader pages differ"
    )
    if first_differing is not None:
        summary += f" (first {first_differing})"
    if not failures:
        summary += "; every span, every folio identical; no filler pages; nothing unparsed"

    return Gate(
        name="G3",
        title="Content placement",
        hard=True,
        passed=not failures,
        summary=summary,
        failures=tuple(failures),
        details={
            "residual": residual,
            "text": dict(text_comparison),
            "adapter_pad_marker_lines": list(adapter_pad_marker_lines),
            "adapter_pad_marker": ADAPTER_PAD_MARKER,
            "redistribution": [dict(row) for row in redistribution],
            "layout_spans": {
                "baseline": dict(baseline_layout_spans),
                "candidate": dict(candidate_layout_spans),
                "baseline_editorial": baseline_editorial_pages,
                "candidate_editorial": candidate_editorial_pages,
            },
            "pdf_starts": {"baseline": dict(baseline_pdf_starts), "candidate": dict(candidate_pdf_starts)},
            "pdf_spans": {"baseline": dict(baseline_pdf_spans), "candidate": dict(candidate_pdf_spans)},
            "contents_folios": {"baseline": dict(baseline_folios), "candidate": dict(candidate_folios)},
            "candidate_layout_toc": dict(candidate_layout_toc),
            "signature_pad_pages": list(signature_pad_pages),
            "unparsed": unparsed,
            "title_occurrences": {
                "baseline": {k: list(v) for k, v in (baseline_title_occurrences or {}).items()},
                "candidate": {k: list(v) for k, v in (candidate_title_occurrences or {}).items()},
            },
        },
    )


# --------------------------------------------------------------------------- #
# G4 ink geometry and G5 visual.
# --------------------------------------------------------------------------- #


def compare_ink(
    *,
    baseline_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
    ratio_tolerance: float,
    bbox_tolerance: int,
    surface: str = "reader page",
) -> Gate:
    """Compare per-page ink coverage ratio and ink bounding box (G4).

    ``surface`` is ``"reader page"`` or ``"booklet side"``; both are compared and
    reported identically, because the A4 booklet is the acceptance surface.
    """
    failures: list[str] = []
    pages: list[dict[str, Any]] = []
    shared = min(len(baseline_rows), len(candidate_rows))
    if len(baseline_rows) != len(candidate_rows):
        failures.append(
            f"rasterized {len(candidate_rows)} candidate {surface}s against "
            f"{len(baseline_rows)} baseline {surface}s"
        )
    for index in range(shared):
        want, got = baseline_rows[index], candidate_rows[index]
        page = index + 1
        ratio_delta = abs(float(got["ink_ratio"]) - float(want["ink_ratio"]))
        want_box = want["ink_bbox"]
        got_box = got["ink_bbox"]
        if want_box is None or got_box is None:
            bbox_delta: list[int] | None = None
            bbox_worst = 0 if want_box == got_box else None
        else:
            bbox_delta = [int(g) - int(w) for w, g in zip(want_box, got_box)]
            bbox_worst = max(abs(value) for value in bbox_delta)
        within = ratio_delta <= ratio_tolerance and bbox_worst is not None and bbox_worst <= bbox_tolerance
        pages.append(
            {
                "surface": surface,
                "page": page,
                "baseline_ink_ratio": want["ink_ratio"],
                "candidate_ink_ratio": got["ink_ratio"],
                "ink_ratio_delta": round(ratio_delta, 6),
                "baseline_ink_bbox": want_box,
                "candidate_ink_bbox": got_box,
                "ink_bbox_delta": bbox_delta,
                "ink_bbox_worst_edge_delta": bbox_worst,
                "within_tolerance": bool(within),
            }
        )
        if not within:
            bbox_note = (
                f"{bbox_worst} px (tol {bbox_tolerance})"
                if bbox_worst is not None
                else f"n/a (baseline bbox {want_box}, candidate bbox {got_box})"
            )
            failures.append(
                f"{surface} {page}: ink ratio candidate {got['ink_ratio']:.6f} vs baseline "
                f"{want['ink_ratio']:.6f} (delta {ratio_delta:.6f}, tol {ratio_tolerance}); "
                f"bbox worst edge delta {bbox_note}"
            )
    worst_ratio = max((row["ink_ratio_delta"] for row in pages), default=0.0)
    worst_bbox = max((row["ink_bbox_worst_edge_delta"] or 0 for row in pages), default=0)
    # Same treatment as G3: the count of out-of-tolerance surfaces is stated against
    # the number compared, so it can never read as a residual on its own.
    out_of_tolerance = sum(1 for row in pages if not row["within_tolerance"])
    return Gate(
        name="G4",
        title="Ink geometry",
        hard=False,
        passed=not failures,
        summary=(
            f"worst ink-ratio delta {worst_ratio:.6f} (tol {ratio_tolerance}), "
            f"worst bbox edge delta {worst_bbox} px (tol {bbox_tolerance}); "
            f"{out_of_tolerance} of {shared} {surface}(s) out of tolerance"
        ),
        failures=tuple(failures),
        details={
            "surface": surface,
            "ink_ratio_tolerance": ratio_tolerance,
            "ink_bbox_tolerance_px": bbox_tolerance,
            "worst_ink_ratio_delta": round(worst_ratio, 6),
            "worst_ink_bbox_edge_delta": worst_bbox,
            "out_of_tolerance": out_of_tolerance,
            "compared": shared,
            "baseline_count": len(baseline_rows),
            "candidate_count": len(candidate_rows),
            "pages": pages,
        },
    )


def raster_page_metrics(
    baseline: Image.Image, candidate: Image.Image, *, channel_threshold: int
) -> dict[str, Any]:
    """Differing-pixel fraction and mean absolute difference between two rasters.

    A pixel counts as differing when its grayscale absolute difference *exceeds*
    ``channel_threshold`` -- a delta equal to the threshold does not count -- which
    absorbs the unavoidable antialiasing noise of two different rasterized
    typesetters.  ``mean_abs_difference`` is reported in 0--255 grayscale units and
    is threshold-free.
    """
    left = baseline.convert("L")
    right = candidate.convert("L")
    if left.size != right.size:
        return {
            "comparable": False,
            "baseline_size": list(left.size),
            "candidate_size": list(right.size),
            "diff_fraction": 1.0,
            "mean_abs_difference": 255.0,
        }
    difference = ImageChops.difference(left, right)
    histogram = difference.histogram()
    total = left.width * left.height
    differing = sum(histogram[channel_threshold + 1 :])
    weighted = sum(value * count for value, count in enumerate(histogram))
    return {
        "comparable": True,
        "baseline_size": list(left.size),
        "candidate_size": list(right.size),
        "diff_fraction": (differing / total) if total else 0.0,
        "mean_abs_difference": (weighted / total) if total else 0.0,
    }


def compare_visual(
    *,
    page_metrics: Sequence[Mapping[str, Any]],
    max_diff_fraction: float,
    max_mean_abs_difference: float,
    baseline_count: int,
    candidate_count: int,
    surface: str = "reader page",
) -> Gate:
    """Aggregate per-page raster metrics into gate G5.

    ``baseline_count``/``candidate_count`` are required: comparing only the shared
    prefix would let a 40-side candidate report a green G5 over 36 sides.
    """
    failures: list[str] = []
    pages: list[dict[str, Any]] = []
    if baseline_count != candidate_count:
        failures.append(
            f"compared {len(page_metrics)} {surface}s: candidate has {candidate_count}, "
            f"baseline {baseline_count}"
        )
    for row in page_metrics:
        page = int(row["page"])
        fraction = float(row["diff_fraction"])
        mean = float(row["mean_abs_difference"])
        within = (
            bool(row.get("comparable", True))
            and fraction <= max_diff_fraction
            and mean <= max_mean_abs_difference
        )
        pages.append(
            {
                "surface": surface,
                "page": page,
                "diff_fraction": round(fraction, 6),
                "mean_abs_difference": round(mean, 4),
                "comparable": bool(row.get("comparable", True)),
                "within_tolerance": within,
                "diff_image": row.get("diff_image"),
            }
        )
        if not within:
            failures.append(
                f"{surface} {page}: {fraction * 100:.2f}% differing pixels "
                f"(tol {max_diff_fraction * 100:.2f}%), mean abs diff {mean:.2f}/255 "
                f"(tol {max_mean_abs_difference})"
            )
    worst = sorted(pages, key=lambda row: row["diff_fraction"], reverse=True)[:5]
    out_of_tolerance = sum(1 for row in pages if not row["within_tolerance"])
    worst_fraction = max((row["diff_fraction"] for row in pages), default=0.0)
    worst_mean = max((row["mean_abs_difference"] for row in pages), default=0.0)
    return Gate(
        name="G5",
        title="Visual",
        hard=False,
        passed=not failures,
        summary=(
            "worst "
            + ", ".join(f"{row['page']} {row['diff_fraction'] * 100:.1f}%" for row in worst)
            + f"; {out_of_tolerance} of {len(pages)} {surface}(s) out of tolerance"
            if pages
            else f"no {surface}s compared"
        ),
        failures=tuple(failures),
        details={
            "surface": surface,
            "max_diff_fraction": max_diff_fraction,
            "max_mean_abs_difference": max_mean_abs_difference,
            "baseline_count": baseline_count,
            "candidate_count": candidate_count,
            "out_of_tolerance": out_of_tolerance,
            "worst_diff_fraction": round(worst_fraction, 6),
            "worst_mean_abs_difference": round(worst_mean, 4),
            "compared": len(pages),
            "worst_pages": [row["page"] for row in worst],
            "pages": pages,
        },
    )


# --------------------------------------------------------------------------- #
# G6 colour.
# --------------------------------------------------------------------------- #
#
# Everything G1-G5 measure is greyscale or geometric.  ``raster_page_metrics``
# converts to ``"L"`` before differencing, ``render_critic``'s ink ratio
# thresholds a grayscale, and G1-G3 never look at a pixel.  A token emitted with
# the wrong hue therefore passes all five -- it is the same shape, in the same
# place, at nearly the same luminance -- and shows up only on paper.  G6 closes
# that with two clauses of deliberately different kinds:
#
#   1. the *chromatic ink* each pipeline sets in its content streams, compared
#      exactly, page by page.  This sees a wrong token however few pixels it
#      covers, which is the case a raster metric structurally cannot bound.
#   2. per-channel RGB raster difference, which sees hue in *images* and in
#      anti-aliased compositing, where no operator appears at all.
#
# Neither subsumes the other, which is why both are here.


def format_color(rgb: Sequence[float]) -> str:
    """Canonical, sortable, JSON-safe spelling of one device colour."""
    return " ".join(f"{float(value):.6f}" for value in rgb)


def is_chromatic(rgb: Sequence[float], *, tolerance: float = COLOR_VALUE_TOLERANCE) -> bool:
    """True when the three channels are not all the same value.

    A neutral -- black text, white paper, a 50% grey rule -- carries no hue and is
    already bounded by G4/G5.  Everything else is an accent that a printer will
    reproduce as a colour, so it is what G6's exact clause compares.
    """
    values = [float(value) for value in rgb]
    return (max(values) - min(values)) > tolerance


def colors_match(
    left: Sequence[float], right: Sequence[float], *, tolerance: float = COLOR_VALUE_TOLERANCE
) -> bool:
    """True when two device colours are the same ink, per channel."""
    return len(left) == len(right) and all(
        abs(float(a) - float(b)) <= tolerance for a, b in zip(left, right)
    )


def name_color(
    rgb: Sequence[float],
    *,
    palette: Mapping[str, Sequence[float]] | None = None,
    tolerance: float = COLOR_VALUE_TOLERANCE,
) -> str | None:
    """The declared palette token this colour is, or ``None`` if it is not one.

    Naming is for the failure message, never for the verdict: an unnamed colour is
    not a failure, and a named one is not a pass.  What decides G6 is whether the
    candidate lays down the same chromatic inks the frozen baseline does.
    """
    for key, value in sorted((palette if palette is not None else REFERENCE_PALETTE).items()):
        if colors_match(rgb, value, tolerance=tolerance):
            return key
    return None


def describe_color(rgb: Sequence[float], **kwargs: Any) -> str:
    """``"0.250000 0.100000 0.430000 (VIOLET)"`` -- readable in a failure line."""
    token = name_color(rgb, **kwargs)
    return format_color(rgb) + (f" ({token})" if token else " (unnamed)")


def color_operations(operations: Sequence[tuple[Any, Any]]) -> dict[str, Any]:
    """Fold a tokenised content stream's operations into the colours it sets.

    ``operations`` is what :class:`pypdf.generic.ContentStream` produces: operands
    already parsed, string literals and inline images already consumed.  Scanning
    the raw bytes with a regex instead is *not* equivalent -- ``rg``/``g`` occur
    inside ``gs`` and inside show-text strings, and a first attempt at this check
    miscounted 259 ``gs`` operators as grey fills before it was tokenised.
    """
    colors: dict[str, dict[str, Any]] = {}
    unmodelled: dict[str, int] = {}
    for operands, operator in operations:
        name = bytes(operator) if isinstance(operator, (bytes, bytearray)) else str(operator).encode()
        if name in UNMODELLED_COLOR_OPERATORS:
            unmodelled[name.decode("latin-1")] = unmodelled.get(name.decode("latin-1"), 0) + 1
            continue
        painted = MODELLED_COLOR_OPERATORS.get(name)
        if painted is None:
            continue
        role, space = painted
        spelling = f"{role} ({name.decode('latin-1')})"
        try:
            values = [float(value) for value in operands]
        except (TypeError, ValueError):
            # An operand that is not a number is a malformed stream, not a colour.
            unmodelled[name.decode("latin-1")] = unmodelled.get(name.decode("latin-1"), 0) + 1
            continue
        if space == "DeviceGray":
            if len(values) != 1:
                unmodelled[name.decode("latin-1")] = unmodelled.get(name.decode("latin-1"), 0) + 1
                continue
            values = values * 3
        elif len(values) != 3:
            unmodelled[name.decode("latin-1")] = unmodelled.get(name.decode("latin-1"), 0) + 1
            continue
        key = format_color(values)
        entry = colors.setdefault(
            key,
            {
                "rgb": [round(value, 6) for value in values],
                "chromatic": is_chromatic(values),
                "name": name_color(values),
                "operators": {},
                "count": 0,
            },
        )
        entry["operators"][spelling] = entry["operators"].get(spelling, 0) + 1
        entry["count"] += 1
    return {
        "colors": {key: colors[key] for key in sorted(colors)},
        "unmodelled_operators": {key: unmodelled[key] for key in sorted(unmodelled)},
    }


def _form_streams(resources: Any, seen: set[int]) -> Iterator[Any]:
    """Every Form XObject reachable from ``resources``, each visited once."""
    if resources is None:
        return
    xobjects = resources.get("/XObject") if hasattr(resources, "get") else None
    if xobjects is None:
        return
    xobjects = xobjects.get_object()
    for key in sorted(str(name) for name in xobjects):
        raw = xobjects[key]
        marker = raw.idnum if isinstance(raw, IndirectObject) else id(raw)
        if marker in seen:
            continue
        seen.add(marker)
        obj = raw.get_object()
        if str(obj.get("/Subtype")) != "/Form":
            continue  # An image carries no colour *operator*; the raster clause sees it.
        yield obj
        yield from _form_streams(obj.get("/Resources"), seen)


def page_color_operators(page: Any, reader: PdfReader) -> dict[str, Any]:
    """Colours set by one page's content stream and every Form XObject it uses.

    ReportLab draws directly on the page; the spliced cover pages and WeasyPrint's
    output both route through Form XObjects, so a page-only scan would miss them.
    A stream that cannot be tokenised is counted rather than skipped -- G6 reports
    that as a refusal, because an unread stream is not an agreeing one.
    """
    operations: list[tuple[Any, Any]] = []
    unreadable = 0
    streams: list[Any] = []
    contents = page.get_contents()
    if contents is not None:
        streams.append(contents)
    streams.extend(_form_streams(page.get("/Resources"), set()))
    for stream in streams:
        try:
            operations.extend(ContentStream(stream, reader).operations)
        except Exception:  # noqa: BLE001 - any parse failure must surface, not vanish
            unreadable += 1
    folded = color_operations(operations)
    folded["unreadable_streams"] = unreadable
    folded["chromatic"] = sorted(
        key for key, entry in folded["colors"].items() if entry["chromatic"]
    )
    return folded


def pdf_color_operators(pdf: Path) -> list[dict[str, Any]]:
    """:func:`page_color_operators` for every page of ``pdf``, in page order."""
    reader = PdfReader(str(pdf))
    return [
        {"page": index, **page_color_operators(page, reader)}
        for index, page in enumerate(reader.pages, 1)
    ]


def color_operator_failures(
    *,
    baseline_pages: Sequence[Mapping[str, Any]],
    candidate_pages: Sequence[Mapping[str, Any]],
    surface: str = "reader page",
    tolerance: float = COLOR_VALUE_TOLERANCE,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Per surface, the chromatic inks the candidate sets versus the baseline's.

    The compared identity is the colour *value*.  The paint operator is recorded
    beside it but deliberately excluded from the identity: ReportLab strokes the
    hairline rules that WeasyPrint fills, which makes 22 of 36 en reader pages
    differ on ``RG`` versus ``rg`` while every one of them lays down the same ink.
    Gating on the operator would report a paint-method difference -- already
    bounded geometrically by G4 and G5 -- as a colour defect, and burying the real
    signal is exactly how a hue error survives.
    """
    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    if len(baseline_pages) != len(candidate_pages):
        failures.append(
            f"read colour operators from {len(candidate_pages)} candidate {surface}s "
            f"against {len(baseline_pages)} baseline {surface}s"
        )
    for index in range(min(len(baseline_pages), len(candidate_pages))):
        page = index + 1
        want, got = baseline_pages[index], candidate_pages[index]
        want_colors = [
            entry for entry in want["colors"].values() if entry["chromatic"]
        ]
        got_colors = [entry for entry in got["colors"].values() if entry["chromatic"]]
        unmatched_candidate = [
            entry
            for entry in got_colors
            if not any(colors_match(entry["rgb"], other["rgb"], tolerance=tolerance) for other in want_colors)
        ]
        unmatched_baseline = [
            entry
            for entry in want_colors
            if not any(colors_match(entry["rgb"], other["rgb"], tolerance=tolerance) for other in got_colors)
        ]
        refusals: list[str] = []
        for label, side in (("baseline", want), ("candidate", got)):
            for operator, count in sorted(side.get("unmodelled_operators", {}).items()):
                refusals.append(
                    f"{label} sets colour {count}x with {operator!r}, a colour space this "
                    "check does not model; that is a refusal, not agreement"
                )
            if side.get("unreadable_streams"):
                refusals.append(
                    f"{label} has {side['unreadable_streams']} content stream(s) that could "
                    "not be tokenised; that is a refusal, not agreement"
                )
        matched = len(got_colors) - len(unmatched_candidate)
        rows.append(
            {
                "surface": surface,
                "page": page,
                "baseline_chromatic": [describe_color(e["rgb"]) for e in want_colors],
                "candidate_chromatic": [describe_color(e["rgb"]) for e in got_colors],
                "candidate_only": [describe_color(e["rgb"]) for e in unmatched_candidate],
                "baseline_only": [describe_color(e["rgb"]) for e in unmatched_baseline],
                "matching_chromatic_inks": matched,
                "refusals": refusals,
                "candidate_paint_operators": {
                    format_color(e["rgb"]): dict(sorted(e["operators"].items()))
                    for e in got_colors
                },
                "baseline_paint_operators": {
                    format_color(e["rgb"]): dict(sorted(e["operators"].items()))
                    for e in want_colors
                },
                "identical": not (unmatched_candidate or unmatched_baseline or refusals),
            }
        )
        for entry in unmatched_candidate:
            failures.append(
                f"{surface} {page}: candidate sets chromatic ink {describe_color(entry['rgb'])} "
                f"{entry['count']}x, which the baseline never sets on this page "
                f"(baseline sets {', '.join(describe_color(e['rgb']) for e in want_colors) or 'none'})"
            )
        for entry in unmatched_baseline:
            failures.append(
                f"{surface} {page}: baseline sets chromatic ink {describe_color(entry['rgb'])} "
                f"{entry['count']}x, which the candidate never sets on this page"
            )
        for line in refusals:
            failures.append(f"{surface} {page}: {line}")
    return failures, rows


def channel_raster_metrics(
    baseline: Image.Image, candidate: Image.Image, *, channel_threshold: int
) -> dict[str, Any]:
    """Per-channel RGB difference between two rasters, plus the hue-only residual.

    ``pdftoppm -png`` already emits RGB, so this reads the *same* cached PNGs G4
    and G5 read -- no second rasterisation and no colour conversion.  G5 throws the
    hue away by converting to ``"L"``; nothing here does.

    Three per-channel mean absolute differences are reported and never averaged
    together.  The gated number is ``chroma_mean_abs_difference``: the mean over
    pixels of ``max_c |delta_c| - min_c |delta_c|``.  That per-pixel spread is
    exactly zero wherever the divergence is achromatic -- a grey rasterises with
    three equal channels, so a shifted glyph edge moves R, G and B by the same
    amount -- which makes it a residual that is *only* hue, unlike a difference of
    channel means, which can cancel a too-red accent against a too-blue one
    elsewhere on the page.  It also dominates that difference: since
    ``mean(max - min) >= mean(d_i) - mean(d_j)`` for any pair of channels,
    bounding it bounds the spread of the three per-channel means too.
    """
    left = baseline.convert("RGB")
    right = candidate.convert("RGB")
    if left.size != right.size:
        return {
            "comparable": False,
            "baseline_size": list(left.size),
            "candidate_size": list(right.size),
            "channel_mean_abs_difference": [255.0, 255.0, 255.0],
            "channel_mean_abs_difference_spread": 0.0,
            "chroma_mean_abs_difference": 255.0,
            "chroma_diff_fraction": 1.0,
        }
    total = left.width * left.height
    differences = [
        ImageChops.difference(a, b) for a, b in zip(left.split(), right.split())
    ]

    def histogram_mean(image: Image.Image) -> float:
        histogram = image.histogram()
        return (
            sum(value * count for value, count in enumerate(histogram)) / total
        ) if total else 0.0

    channel_means = [histogram_mean(image) for image in differences]
    widest = ImageChops.lighter(ImageChops.lighter(differences[0], differences[1]), differences[2])
    narrowest = ImageChops.darker(ImageChops.darker(differences[0], differences[1]), differences[2])
    spread = ImageChops.difference(widest, narrowest)
    spread_histogram = spread.histogram()
    return {
        "comparable": True,
        "baseline_size": list(left.size),
        "candidate_size": list(right.size),
        "channel_mean_abs_difference": channel_means,
        "channel_mean_abs_difference_spread": max(channel_means) - min(channel_means),
        "chroma_mean_abs_difference": histogram_mean(spread),
        "chroma_diff_fraction": (
            sum(spread_histogram[channel_threshold + 1 :]) / total
        ) if total else 0.0,
    }


def colour_rows_for(
    *,
    baseline_rasters: Sequence[Path],
    candidate_rasters: Sequence[Path],
    channel_threshold: int,
) -> list[dict[str, Any]]:
    """Per-page channel metrics, with pages only one side has marked incomparable."""
    rows: list[dict[str, Any]] = []
    for index in range(max(len(baseline_rasters), len(candidate_rasters))):
        if index >= len(baseline_rasters) or index >= len(candidate_rasters):
            rows.append(
                {
                    "page": index + 1,
                    "comparable": False,
                    "channel_mean_abs_difference": [255.0, 255.0, 255.0],
                    "channel_mean_abs_difference_spread": 0.0,
                    "chroma_mean_abs_difference": 255.0,
                    "chroma_diff_fraction": 1.0,
                    "baseline_size": None,
                    "candidate_size": None,
                }
            )
            continue
        with Image.open(baseline_rasters[index]) as left, Image.open(
            candidate_rasters[index]
        ) as right:
            metrics = channel_raster_metrics(left, right, channel_threshold=channel_threshold)
        rows.append({"page": index + 1, **metrics})
    return rows


def compare_colour(
    *,
    page_metrics: Sequence[Mapping[str, Any]],
    baseline_operators: Sequence[Mapping[str, Any]],
    candidate_operators: Sequence[Mapping[str, Any]],
    max_chroma_mean_abs_difference: float,
    baseline_count: int,
    candidate_count: int,
    surface: str = "reader page",
    color_value_tolerance: float = COLOR_VALUE_TOLERANCE,
) -> Gate:
    """Gate G6 for one surface: exact chromatic ink, then per-channel raster.

    Reported per page, never as an average: one badly-hued element on one page has
    to be visible in the output, which is the whole reason this gate exists.
    """
    failures, operator_rows = color_operator_failures(
        baseline_pages=baseline_operators,
        candidate_pages=candidate_operators,
        surface=surface,
        tolerance=color_value_tolerance,
    )
    operator_failure_count = len(failures)
    if baseline_count != candidate_count:
        failures.append(
            f"compared {len(page_metrics)} {surface}s in colour: candidate has "
            f"{candidate_count}, baseline {baseline_count}"
        )
    pages: list[dict[str, Any]] = []
    for row in page_metrics:
        page = int(row["page"])
        channels = [float(value) for value in row["channel_mean_abs_difference"]]
        chroma = float(row["chroma_mean_abs_difference"])
        comparable = bool(row.get("comparable", True))
        within = comparable and chroma <= max_chroma_mean_abs_difference
        pages.append(
            {
                "surface": surface,
                "page": page,
                "channel_mean_abs_difference": {
                    "r": round(channels[0], 6),
                    "g": round(channels[1], 6),
                    "b": round(channels[2], 6),
                },
                "channel_mean_abs_difference_spread": round(
                    float(row.get("channel_mean_abs_difference_spread", 0.0)), 6
                ),
                "chroma_mean_abs_difference": round(chroma, 6),
                "chroma_diff_fraction": round(float(row.get("chroma_diff_fraction", 0.0)), 6),
                "comparable": comparable,
                "within_tolerance": within,
            }
        )
        if not within:
            failures.append(
                f"{surface} {page}: chroma mean abs difference {chroma:.6f}/255 "
                f"(tol {max_chroma_mean_abs_difference}); per-channel mean abs difference "
                f"R {channels[0]:.6f} G {channels[1]:.6f} B {channels[2]:.6f}"
                + ("" if comparable else "; rasters are not the same size")
            )

    worst_page = max(
        pages, key=lambda row: (row["chroma_mean_abs_difference"], row["page"]), default=None
    )
    worst_chroma = worst_page["chroma_mean_abs_difference"] if worst_page else 0.0
    worst_channels = max(
        (
            max(row["channel_mean_abs_difference"].values())
            for row in pages
        ),
        default=0.0,
    )
    out_of_tolerance = sum(1 for row in pages if not row["within_tolerance"])
    identical_ink = sum(1 for row in operator_rows if row["identical"])
    summary = (
        f"chromatic ink identical on {identical_ink} of {len(operator_rows)} {surface}(s); "
        f"worst chroma mean abs difference {worst_chroma:.6f}/255 "
        + (f"on {surface} {worst_page['page']} " if worst_page else "")
        + f"(tol {max_chroma_mean_abs_difference}), worst per-channel mean abs difference "
        f"{worst_channels:.6f}/255; {out_of_tolerance} of {len(pages)} {surface}(s) "
        "out of tolerance"
    )
    return Gate(
        name="G6",
        title="Colour",
        hard=False,
        passed=not failures,
        summary=summary,
        failures=tuple(failures),
        details={
            "surface": surface,
            "max_chroma_mean_abs_difference": max_chroma_mean_abs_difference,
            "color_value_tolerance": color_value_tolerance,
            "baseline_count": baseline_count,
            "candidate_count": candidate_count,
            "compared": len(pages),
            "out_of_tolerance": out_of_tolerance,
            "worst_chroma_mean_abs_difference": round(worst_chroma, 6),
            "worst_chroma_page": worst_page["page"] if worst_page else None,
            "worst_channel_mean_abs_difference": round(worst_channels, 6),
            "worst_chroma_diff_fraction": round(
                max((row["chroma_diff_fraction"] for row in pages), default=0.0), 6
            ),
            "chromatic_ink_identical_pages": identical_ink,
            "chromatic_ink_compared_pages": len(operator_rows),
            "chromatic_ink_failures": operator_failure_count,
            "reference_palette": {
                key: format_color(value) for key, value in sorted(REFERENCE_PALETTE.items())
            },
            "pages": pages,
            "chromatic_ink": operator_rows,
        },
    )


def aggregate_gates(
    gates_by_language: Mapping[str, Sequence[Gate]],
    extra_hard_failures: Sequence[str] = (),
) -> dict[str, Any]:
    """Roll gates up into an overall verdict; only hard gates set the exit code.

    ``extra_hard_failures`` carries run-level blockers that are not per-language
    gates -- today, a frozen baseline that changed during the run.
    """
    hard_failures = [
        f"{language}/{gate.name}"
        for language, gates in sorted(gates_by_language.items())
        for gate in gates
        if gate.hard and not gate.passed
    ] + list(extra_hard_failures)
    soft_failures = [
        f"{language}/{gate.name}"
        for language, gates in sorted(gates_by_language.items())
        for gate in gates
        if not gate.hard and not gate.passed
    ]
    return {
        "result": "pass" if not hard_failures else "fail",
        "hard_gate_failures": hard_failures,
        "soft_gate_failures": soft_failures,
        "exit_code": 0 if not hard_failures else 1,
    }


def _surface_details(gate: Gate) -> dict[str, Mapping[str, Any]]:
    """The reader/booklet halves of a gate folded by :func:`merge_surface_gates`."""
    return {
        name: value
        for name, value in gate.details.items()
        if name in ("reader", "booklet") and isinstance(value, Mapping)
    }


def gate_residuals(gates: Sequence[Gate]) -> dict[str, Any]:
    """The per-language numbers that a failing-clause count can hide.

    Every gate whose headline is a count of *clauses* also carries the residual the
    clauses are measuring, so the two can never be conflated -- and it is produced
    for every language, not only the one quoted first.
    """
    by_name = {gate.name: gate for gate in gates}
    residuals: dict[str, Any] = {}
    gate3 = by_name.get("G3")
    if gate3 is not None:
        residuals["G3"] = dict(gate3.details.get("residual") or {})
    gate4 = by_name.get("G4")
    if gate4 is not None:
        residuals["G4"] = {
            surface: {
                "worst_ink_ratio_delta": detail.get("worst_ink_ratio_delta"),
                "worst_ink_bbox_edge_delta": detail.get("worst_ink_bbox_edge_delta"),
                "out_of_tolerance": detail.get("out_of_tolerance"),
                "compared": detail.get("compared"),
            }
            for surface, detail in _surface_details(gate4).items()
        }
    gate5 = by_name.get("G5")
    if gate5 is not None:
        residuals["G5"] = {
            surface: {
                "worst_diff_fraction": detail.get("worst_diff_fraction"),
                "worst_mean_abs_difference": detail.get("worst_mean_abs_difference"),
                "out_of_tolerance": detail.get("out_of_tolerance"),
                "compared": detail.get("compared"),
            }
            for surface, detail in _surface_details(gate5).items()
        }
    gate6 = by_name.get("G6")
    if gate6 is not None:
        residuals["G6"] = {
            surface: {
                "worst_chroma_mean_abs_difference": detail.get(
                    "worst_chroma_mean_abs_difference"
                ),
                "worst_channel_mean_abs_difference": detail.get(
                    "worst_channel_mean_abs_difference"
                ),
                "worst_chroma_page": detail.get("worst_chroma_page"),
                "chromatic_ink_identical_pages": detail.get("chromatic_ink_identical_pages"),
                "chromatic_ink_compared_pages": detail.get("chromatic_ink_compared_pages"),
                "out_of_tolerance": detail.get("out_of_tolerance"),
                "compared": detail.get("compared"),
            }
            for surface, detail in _surface_details(gate6).items()
        }
    return residuals


def residual_line(language: str, residuals: Mapping[str, Any]) -> str:
    """One compact, quotable line of residuals for one language."""
    parts: list[str] = []
    gate3 = residuals.get("G3") or {}
    if gate3:
        parts.append(
            f"G3 {gate3.get('clause_failures')} clause(s) failing, "
            f"{gate3.get('reader_pages_differing')} of "
            f"{gate3.get('reader_pages_compared')} reader pages differ"
        )
    gate4 = residuals.get("G4") or {}
    if gate4:
        parts.append(
            "G4 worst ink delta "
            + ", ".join(
                f"{float(detail['worst_ink_ratio_delta'] or 0.0):.6f} {surface}"
                for surface, detail in gate4.items()
            )
        )
    gate5 = residuals.get("G5") or {}
    if gate5:
        parts.append(
            "G5 worst differing pixels "
            + ", ".join(
                f"{float(detail['worst_diff_fraction'] or 0.0) * 100:.2f}% {surface}"
                for surface, detail in gate5.items()
            )
        )
    gate6 = residuals.get("G6") or {}
    if gate6:
        parts.append(
            "G6 worst chroma "
            + ", ".join(
                f"{float(detail['worst_chroma_mean_abs_difference'] or 0.0):.6f}/255 "
                f"on {surface} {detail.get('worst_chroma_page')}"
                for surface, detail in gate6.items()
            )
            + ", chromatic ink identical on "
            + ", ".join(
                f"{detail.get('chromatic_ink_identical_pages')} of "
                f"{detail.get('chromatic_ink_compared_pages')} {surface}"
                for surface, detail in gate6.items()
            )
        )
    return f"{language}: " + (" | ".join(parts) or "no residuals recorded")


# --------------------------------------------------------------------------- #
# Rendering, rasterizing, and reporting.
# --------------------------------------------------------------------------- #


@contextlib.contextmanager
def raster_dpi(dpi: int) -> Iterator[None]:
    """Temporarily retarget ``render_critic``'s rasterizer.

    ``render_critic._render_pages`` reads the module-level ``RASTER_DPI``
    constant rather than taking a parameter.  Reusing that helper verbatim is
    worth more than a private copy of the Poppler invocation, so ``--dpi`` is
    applied by rebinding the constant for the duration of the call.
    """
    previous = render_critic.RASTER_DPI
    render_critic.RASTER_DPI = dpi
    try:
        yield
    finally:
        render_critic.RASTER_DPI = previous


def rasterize_cached(pdf: Path, destination: Path, *, dpi: int) -> list[Path]:
    """Rasterize ``pdf`` at ``dpi``, reusing a previous run's PNGs when valid."""
    destination.mkdir(parents=True, exist_ok=True)
    stamp_path = destination / "stamp.json"
    fingerprint = {"sha256": sha256(pdf), "dpi": dpi}
    if stamp_path.is_file():
        try:
            stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            stamp = {}
        existing = sorted(destination.glob("page-*.png"))
        if (
            stamp.get("sha256") == fingerprint["sha256"]
            and stamp.get("dpi") == dpi
            and existing
            and stamp.get("pages") == len(existing)
        ):
            return existing
    for stale in destination.glob("page-*.png"):
        stale.unlink()
    with raster_dpi(dpi):
        pages = _render_pages(pdf, destination)
    stamp_path.write_text(
        json.dumps({**fingerprint, "pages": len(pages)}, indent=2) + "\n", encoding="utf-8"
    )
    return pages


def inspect_pages(pdf: Path, rasters: Sequence[Path]) -> list[dict[str, Any]]:
    reader = PdfReader(str(pdf))
    return [
        _inspect_page(path, reader.pages[index], index + 1)
        for index, path in enumerate(rasters)
        if index < len(reader.pages)
    ]


def raster_is_pure_white(path: Path) -> bool:
    """True only when every pixel is pure white.

    ``render_critic``'s ink ratio counts a pixel as ink below
    ``WHITE_THRESHOLD`` (245), so a light tint or a hairline that rasterizes to
    246-254 has an ink ratio of exactly 0.0 and would pass an "ink_ratio == 0"
    test.  A genuinely empty page rasterizes to pure white, so this is the
    stricter and correct test for "carries no ink at all".
    """
    with Image.open(path) as opened:
        return ImageOps.grayscale(opened).getextrema() == (255, 255)


def inside_cover_report(
    rows: Sequence[Mapping[str, Any]],
    rasters: Sequence[Path],
    *,
    page_count: int,
) -> dict[str, Any]:
    """Whether reader pages 2 and ``page_count - 1`` carry no ink at all.

    Pages are looked up by their recorded page number rather than by list
    position, so a short or reordered raster list can no longer make this check
    silently inspect the wrong pages -- it reports the gap instead.
    """
    pages = [2, page_count - 1]
    by_page = {int(row["page"]): row for row in rows}
    failures: list[str] = []
    detail: dict[str, Any] = {}
    if page_count < 4:
        failures.append(f"reader has {page_count} pages, too few to have inside covers")
    for page in pages:
        row = by_page.get(page)
        raster = rasters[page - 1] if 0 < page <= len(rasters) else None
        entry: dict[str, Any] = {"inspected": row is not None, "rasterized": raster is not None}
        if row is None or raster is None:
            failures.append(
                f"inside-cover reader page {page} was not inspected "
                f"({len(rows)} inspected rows, {len(rasters)} rasters)"
            )
            detail[str(page)] = entry
            continue
        white = raster_is_pure_white(raster)
        characters = int(row.get("text_characters", 0) or 0)
        entry.update(
            {
                "ink_ratio": row.get("ink_ratio"),
                "pure_white_raster": white,
                "text_characters": characters,
            }
        )
        if not white:
            failures.append(f"inside-cover reader page {page} raster is not pure white")
        if characters:
            failures.append(
                f"inside-cover reader page {page} carries {characters} extracted characters"
            )
        detail[str(page)] = entry
    return {"pages": pages, "ink_free": not failures, "failures": failures, "detail": detail}


def blank_booklet_side_failures(
    *,
    measured: Sequence[Mapping[str, Any]],
    rasters: Sequence[Path],
    inside_cover_pages: Sequence[int],
    label: str,
) -> list[str]:
    """The imposed side carrying both inside covers must be an ink-free raster."""
    wanted = set(int(page) for page in inside_cover_pages)
    failures: list[str] = []
    for row in measured:
        planned = {page for page in row["expected_mapping"] if page is not None}
        if planned != wanted:
            continue
        side = int(row["side"])
        if side > len(rasters):
            failures.append(f"{label} booklet side {side} (both inside covers) was not rasterized")
        elif not raster_is_pure_white(rasters[side - 1]):
            failures.append(
                f"{label} booklet side {side} carries both inside covers but is not pure white"
            )
    return failures


def cover_pdfs(
    *,
    root: Path,
    edition_id: str,
    language: str,
    edition: Any,
    work: WorkDir,
) -> tuple[Path, Path, str]:
    """Locate (or regenerate) the canonical cover PDFs the baseline build used.

    ``Magazine.build`` compiles both faces into ``output/.build/covers/<edition>/
    <language>`` and ``output/.build/back-covers/...`` and splices them with
    ``replace_outer_pages``.  Reusing those exact files makes reader page 1 and the
    last page identical by construction instead of a source of noise -- but they
    are read *only*: a cache miss compiles fresh covers under ``--work-dir``, never
    into ``output/``, so the harness cannot write outside its work dir and a
    drifted cache cannot be repaired silently.  The caller records their hashes.
    """
    front = root / "output" / ".build" / "covers" / edition_id / language / "cover.pdf"
    back = root / "output" / ".build" / "back-covers" / edition_id / language / "cover.pdf"
    if front.is_file() and back.is_file():
        return front, back, "output/.build cache (read-only)"
    compiler = CoverCompiler(root)
    front_dir = work.directory(edition_id, language, "covers", "front")
    back_dir = work.directory(edition_id, language, "covers", "back")
    return (
        compiler.compile(edition, front_dir).pdf,
        compiler.compile_back(edition, back_dir).pdf,
        "compiled into --work-dir",
    )


def render_candidate(
    *,
    root: Path,
    edition: Any,
    edition_id: str,
    language: str,
    work: WorkDir,
    reuse: bool,
) -> tuple[Path, Path, dict[str, Any], dict[str, Any]]:
    """Render, splice, and impose the candidate.

    Returns ``(reader, booklet, layout, provenance)``.  The provenance dict records
    the artifact hashes, their mtimes, the cover PDFs used and whether this run
    actually rendered anything, because a reused work-dir PDF is otherwise
    indistinguishable from a fresh one in every gate readout.
    """
    from magazine.weasyprint_adapter import render_a5_weasyprint

    language_work = work.directory(edition_id, language)
    interior = work.path(edition_id, language, "reader-interior.pdf")
    reader = work.path(edition_id, language, "reader.pdf")
    booklet = work.path(edition_id, language, "booklet-a4.pdf")
    layout_path = work.path(edition_id, language, "layout.json")
    assert language_work == reader.parent

    reused = bool(reuse and reader.is_file() and booklet.is_file() and layout_path.is_file())
    if reused:
        layout_json = json.loads(layout_path.read_text(encoding="utf-8"))
        cover_note = str(layout_json.get("cover_source", "unknown (reused layout.json)"))
        front = Path(layout_json.get("front_cover_pdf", ""))
        back = Path(layout_json.get("back_cover_pdf", ""))
    else:
        layout = render_a5_weasyprint(edition, interior)
        front, back, cover_note = cover_pdfs(
            root=root, edition_id=edition_id, language=language, edition=edition, work=work
        )
        replace_outer_pages(interior, front, back, reader)
        impose_a5_on_a4(reader, booklet)
        layout_json = {
            "toc": dict(layout.toc),
            "article_pages": dict(layout.article_pages),
            "editorial_pages": layout.editorial_pages,
            "design": layout.design,
            "front_cover_pdf": str(front),
            "back_cover_pdf": str(back),
            "cover_source": cover_note,
        }
        layout_path.write_text(
            json.dumps(layout_json, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    provenance = {
        "reused_existing_candidate": reused,
        "reader_pdf": str(reader),
        "reader_sha256": sha256(reader),
        "reader_mtime": _mtime(reader),
        "booklet_pdf": str(booklet),
        "booklet_sha256": sha256(booklet),
        "booklet_mtime": _mtime(booklet),
        "cover_source": cover_note,
        "front_cover_pdf": str(front),
        "front_cover_sha256": sha256(front) if front.is_file() else None,
        "back_cover_pdf": str(back),
        "back_cover_sha256": sha256(back) if back.is_file() else None,
    }
    return reader, booklet, layout_json, provenance


def _mtime(path: Path) -> str | None:
    if not path.is_file():
        return None
    return (
        datetime.datetime.fromtimestamp(path.stat().st_mtime, tz=datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def entry_titles(edition: Any) -> dict[str, str]:
    """Stable id -> printed title for the editorial and every article."""
    titles: dict[str, str] = {}
    if edition.editorial is not None:
        titles["editorial"] = edition.editorial.title
    for article in edition.articles:
        titles[article.id] = article.title
    return titles


def write_diff_images(
    *,
    baseline_rasters: Sequence[Path],
    candidate_rasters: Sequence[Path],
    metrics: Sequence[Mapping[str, Any]],
    destination: Path,
    count: int,
    prefix: str = "page",
) -> dict[int, str]:
    """Save amplified difference images for the worst ``count`` pages or sides."""
    destination.mkdir(parents=True, exist_ok=True)
    for stale in destination.glob(f"{prefix}-*-diff.png"):
        stale.unlink()
    worst = sorted(metrics, key=lambda row: float(row["diff_fraction"]), reverse=True)[:count]
    written: dict[int, str] = {}
    for row in worst:
        page = int(row["page"])
        if page > len(baseline_rasters) or page > len(candidate_rasters):
            continue
        with Image.open(baseline_rasters[page - 1]) as left, Image.open(
            candidate_rasters[page - 1]
        ) as right:
            if left.size != right.size:
                continue
            difference = ImageChops.difference(left.convert("L"), right.convert("L"))
            # Invert so untouched areas stay white on screen and paper.
            amplified = difference.point(lambda value: 255 - min(255, value * 4))
            target = destination / f"{prefix}-{page:03d}-diff.png"
            amplified.save(target, format="PNG", optimize=True)
        written[page] = str(target)
    return written


def visual_rows_for(
    *,
    baseline_rasters: Sequence[Path],
    candidate_rasters: Sequence[Path],
    channel_threshold: int,
) -> list[dict[str, Any]]:
    """Per-page raster metrics for every page either side has.

    Pages only one side has are recorded as incomparable rather than skipped, so a
    page-count mismatch can never be averaged away by iterating the shorter list.
    """
    rows: list[dict[str, Any]] = []
    for index in range(max(len(baseline_rasters), len(candidate_rasters))):
        if index >= len(baseline_rasters) or index >= len(candidate_rasters):
            rows.append(
                {
                    "page": index + 1,
                    "comparable": False,
                    "diff_fraction": 1.0,
                    "mean_abs_difference": 255.0,
                    "baseline_size": None,
                    "candidate_size": None,
                }
            )
            continue
        with Image.open(baseline_rasters[index]) as left, Image.open(
            candidate_rasters[index]
        ) as right:
            metrics = raster_page_metrics(left, right, channel_threshold=channel_threshold)
        rows.append({"page": index + 1, **metrics})
    return rows


def compare_language(
    *,
    root: Path,
    edition_id: str,
    language: str,
    edition: Any,
    baseline_dir: Path,
    work: WorkDir,
    options: argparse.Namespace,
) -> tuple[list[Gate], dict[str, Any]]:
    baseline_reader = baseline_dir / ("reader.pdf" if language == options.primary_language else f"{language}/reader.pdf")
    baseline_booklet = baseline_dir / (
        "home/booklet-a4.pdf" if language == options.primary_language else f"{language}/home/booklet-a4.pdf"
    )
    baseline_manifest = baseline_dir / (
        "edition-manifest.json" if language == options.primary_language else f"{language}/edition-manifest.json"
    )
    for path in (baseline_reader, baseline_booklet, baseline_manifest):
        if not path.is_file():
            raise SystemExit(f"Frozen baseline artifact is missing: {path}")

    candidate_reader, candidate_booklet, candidate_layout, provenance = render_candidate(
        root=root,
        edition=edition,
        edition_id=edition_id,
        language=language,
        work=work,
        reuse=options.reuse_candidate,
    )

    band = options.text_band_tolerance
    baseline_reader_words = word_pages(baseline_reader)
    candidate_reader_words = word_pages(candidate_reader)
    baseline_booklet_words = word_pages(baseline_booklet)
    candidate_booklet_words = word_pages(candidate_booklet)
    baseline_texts = canonical_page_texts(baseline_reader_words, tolerance=band)
    candidate_texts = canonical_page_texts(candidate_reader_words, tolerance=band)
    text_comparison = compare_page_texts(baseline_texts, candidate_texts)
    stream_comparison = compare_page_texts(
        stream_page_texts(baseline_reader), stream_page_texts(candidate_reader)
    )

    gate1 = compare_geometry(
        baseline_reader=page_boxes(baseline_reader),
        candidate_reader=page_boxes(candidate_reader),
        baseline_booklet=page_boxes(baseline_booklet),
        candidate_booklet=page_boxes(candidate_booklet),
    )

    baseline_rasters = rasterize_cached(
        baseline_reader, work.directory(edition_id, language, "raster", "baseline"), dpi=options.dpi
    )
    candidate_rasters = rasterize_cached(
        candidate_reader,
        work.directory(edition_id, language, "raster", "candidate"),
        dpi=options.dpi,
    )
    baseline_side_rasters = rasterize_cached(
        baseline_booklet,
        work.directory(edition_id, language, "raster", "baseline-booklet"),
        dpi=options.dpi,
    )
    candidate_side_rasters = rasterize_cached(
        candidate_booklet,
        work.directory(edition_id, language, "raster", "candidate-booklet"),
        dpi=options.dpi,
    )
    baseline_rows = inspect_pages(baseline_reader, baseline_rasters)
    candidate_rows = inspect_pages(candidate_reader, candidate_rasters)
    baseline_side_rows = inspect_pages(baseline_booklet, baseline_side_rasters)
    candidate_side_rows = inspect_pages(candidate_booklet, candidate_side_rasters)

    baseline_measured = measured_imposition(
        booklet_words=baseline_booklet_words,
        reader_words=baseline_reader_words,
        plan=imposition_mapping(len(baseline_texts)),
    )
    candidate_measured = measured_imposition(
        booklet_words=candidate_booklet_words,
        reader_words=candidate_reader_words,
        plan=imposition_mapping(len(candidate_texts)),
    )
    baseline_inside = inside_cover_report(
        baseline_rows, baseline_rasters, page_count=len(baseline_texts)
    )
    candidate_inside = inside_cover_report(
        candidate_rows, candidate_rasters, page_count=len(candidate_texts)
    )
    baseline_inside["failures"] = list(baseline_inside["failures"]) + blank_booklet_side_failures(
        measured=baseline_measured,
        rasters=baseline_side_rasters,
        inside_cover_pages=baseline_inside["pages"],
        label="baseline",
    )
    candidate_inside["failures"] = list(candidate_inside["failures"]) + blank_booklet_side_failures(
        measured=candidate_measured,
        rasters=candidate_side_rasters,
        inside_cover_pages=candidate_inside["pages"],
        label="candidate",
    )
    baseline_inside["ink_free"] = not baseline_inside["failures"]
    candidate_inside["ink_free"] = not candidate_inside["failures"]

    gate2 = compare_imposition(
        baseline_reader_pages=len(baseline_texts),
        candidate_reader_pages=len(candidate_texts),
        baseline_measured=baseline_measured,
        candidate_measured=candidate_measured,
        baseline_spreads=_booklet_spread_checks(
            PdfReader(str(baseline_reader)),
            PdfReader(str(baseline_booklet)),
            booklet_spreads(len(baseline_texts)),
        ),
        candidate_spreads=_booklet_spread_checks(
            PdfReader(str(candidate_reader)),
            PdfReader(str(candidate_booklet)),
            booklet_spreads(len(candidate_texts)),
        ),
        baseline_inside_covers=baseline_inside,
        candidate_inside_covers=candidate_inside,
    )

    titles = entry_titles(edition)
    manifest = json.loads(baseline_manifest.read_text(encoding="utf-8"))
    baseline_layout = manifest.get("layout", {})
    # The contents page follows the two front-cover slots in both pipelines.
    contents_page = 3
    first_body_page = contents_page + 1
    baseline_contents = baseline_texts[contents_page - 1] if len(baseline_texts) >= contents_page else ""
    candidate_contents = candidate_texts[contents_page - 1] if len(candidate_texts) >= contents_page else ""
    # ``titles`` is insertion-ordered: editorial first, then articles in edition
    # order, which is the order both pipelines print the contents list in.
    entry_order = list(titles)
    baseline_folios = contents_folios(
        baseline_contents,
        entry_order,
        first_body_page=first_body_page,
        page_count=len(baseline_texts),
    )
    candidate_folios = contents_folios(
        candidate_contents,
        entry_order,
        first_body_page=first_body_page,
        page_count=len(candidate_texts),
    )
    baseline_starts = structural_starts(baseline_texts, titles, first_body_page=first_body_page)
    candidate_starts = structural_starts(candidate_texts, titles, first_body_page=first_body_page)
    coda = signature_coda(edition)
    baseline_pads = find_signature_pads(baseline_texts, coda)
    candidate_pads = find_signature_pads(candidate_texts, coda)
    adapter_pad_lines = pad_marker_lines(adapter_source())
    baseline_pdf_spans = spans_from_texts(baseline_texts, baseline_starts, pad_pages=baseline_pads)
    candidate_pdf_spans = spans_from_texts(
        candidate_texts, candidate_starts, pad_pages=candidate_pads
    )

    gate3 = compare_content(
        text_comparison=text_comparison,
        baseline_layout_spans=baseline_layout.get("article_pages", {}),
        candidate_layout_spans=candidate_layout.get("article_pages", {}),
        baseline_editorial_pages=baseline_layout.get("editorial_pages"),
        candidate_editorial_pages=candidate_layout.get("editorial_pages"),
        baseline_pdf_starts=baseline_starts,
        candidate_pdf_starts=candidate_starts,
        baseline_pdf_spans=baseline_pdf_spans,
        candidate_pdf_spans=candidate_pdf_spans,
        baseline_folios=baseline_folios,
        candidate_folios=candidate_folios,
        candidate_layout_toc={
            key: value
            for key, value in candidate_layout.get("toc", {}).items()
            if key in titles
        },
        signature_pad_pages=candidate_pads,
        adapter_pad_marker_lines=adapter_pad_lines,
        redistribution=redistribution_report(
            baseline_texts=baseline_texts,
            candidate_texts=candidate_texts,
            baseline_starts=baseline_starts,
            candidate_starts=candidate_starts,
            baseline_spans=baseline_pdf_spans,
            candidate_spans=candidate_pdf_spans,
        ),
        baseline_title_occurrences=title_occurrences(
            baseline_texts, titles, first_body_page=first_body_page
        ),
        candidate_title_occurrences=title_occurrences(
            candidate_texts, titles, first_body_page=first_body_page
        ),
    )
    gate3.details["text"]["extraction"] = {
        "mode": "position-canonical (pdftotext -bbox, banded by geometry)",
        "band_tolerance_points": band,
        "content_stream_order_differing_pages": len(stream_comparison["differing_pages"]),
        "content_stream_order_first_differing_page": stream_comparison["first_differing_page"],
    }
    if baseline_pads:
        gate3.details["baseline_signature_pad_pages"] = baseline_pads

    gate4 = merge_surface_gates(
        {
            "reader": compare_ink(
                baseline_rows=baseline_rows,
                candidate_rows=candidate_rows,
                ratio_tolerance=options.ink_ratio_tolerance,
                bbox_tolerance=options.effective_ink_bbox_tolerance,
                surface="reader page",
            ),
            "booklet": compare_ink(
                baseline_rows=baseline_side_rows,
                candidate_rows=candidate_side_rows,
                ratio_tolerance=options.ink_ratio_tolerance,
                bbox_tolerance=options.effective_ink_bbox_tolerance,
                surface="booklet side",
            ),
        }
    )

    reader_visual = visual_rows_for(
        baseline_rasters=baseline_rasters,
        candidate_rasters=candidate_rasters,
        channel_threshold=options.pixel_diff_threshold,
    )
    booklet_visual = visual_rows_for(
        baseline_rasters=baseline_side_rasters,
        candidate_rasters=candidate_side_rasters,
        channel_threshold=options.pixel_diff_threshold,
    )
    reader_diffs = write_diff_images(
        baseline_rasters=baseline_rasters,
        candidate_rasters=candidate_rasters,
        metrics=reader_visual,
        destination=work.directory(edition_id, language, "diff", "reader"),
        count=options.worst_diff_images,
    )
    booklet_diffs = write_diff_images(
        baseline_rasters=baseline_side_rasters,
        candidate_rasters=candidate_side_rasters,
        metrics=booklet_visual,
        destination=work.directory(edition_id, language, "diff", "booklet"),
        count=options.worst_diff_images,
        prefix="side",
    )
    for rows, images in ((reader_visual, reader_diffs), (booklet_visual, booklet_diffs)):
        for row in rows:
            image = images.get(int(row["page"]))
            if image:
                row["diff_image"] = work.relative(Path(image))
    gate5 = merge_surface_gates(
        {
            "reader": compare_visual(
                page_metrics=reader_visual,
                max_diff_fraction=options.max_diff_fraction,
                max_mean_abs_difference=options.max_mean_abs_difference,
                baseline_count=len(baseline_rasters),
                candidate_count=len(candidate_rasters),
                surface="reader page",
            ),
            "booklet": compare_visual(
                page_metrics=booklet_visual,
                max_diff_fraction=options.max_diff_fraction,
                max_mean_abs_difference=options.max_mean_abs_difference,
                baseline_count=len(baseline_side_rasters),
                candidate_count=len(candidate_side_rasters),
                surface="booklet side",
            ),
        }
    )

    # G6 reads the *same* cached RGB PNGs G4/G5 read -- ``pdftoppm -png`` emits RGB
    # already, so no extra rasterisation and no conversion is involved.
    reader_colour = colour_rows_for(
        baseline_rasters=baseline_rasters,
        candidate_rasters=candidate_rasters,
        channel_threshold=options.pixel_diff_threshold,
    )
    booklet_colour = colour_rows_for(
        baseline_rasters=baseline_side_rasters,
        candidate_rasters=candidate_side_rasters,
        channel_threshold=options.pixel_diff_threshold,
    )
    gate6 = merge_surface_gates(
        {
            "reader": compare_colour(
                page_metrics=reader_colour,
                baseline_operators=pdf_color_operators(baseline_reader),
                candidate_operators=pdf_color_operators(candidate_reader),
                max_chroma_mean_abs_difference=options.max_chroma_mean_abs_difference,
                baseline_count=len(baseline_rasters),
                candidate_count=len(candidate_rasters),
                surface="reader page",
            ),
            "booklet": compare_colour(
                page_metrics=booklet_colour,
                baseline_operators=pdf_color_operators(baseline_booklet),
                candidate_operators=pdf_color_operators(candidate_booklet),
                max_chroma_mean_abs_difference=options.max_chroma_mean_abs_difference,
                baseline_count=len(baseline_side_rasters),
                candidate_count=len(candidate_side_rasters),
                surface="booklet side",
            ),
        }
    )

    gates = [gate1, gate2, gate3, gate4, gate5, gate6]
    artifacts = {
        "candidate_reader": work.relative(candidate_reader),
        "candidate_booklet": work.relative(candidate_booklet),
        "diff_images": sorted(
            work.relative(Path(path))
            for path in (*reader_diffs.values(), *booklet_diffs.values())
        ),
        "provenance": provenance,
        "baseline_reader": str(baseline_reader),
        "baseline_reader_sha256": sha256(baseline_reader),
        "baseline_booklet": str(baseline_booklet),
        "baseline_booklet_sha256": sha256(baseline_booklet),
    }
    return gates, artifacts


def print_report(
    *,
    edition_id: str,
    languages: Sequence[str],
    all_languages: Sequence[str],
    gates_by_language: Mapping[str, Sequence[Gate]],
    artifacts_by_language: Mapping[str, Mapping[str, Any]],
    verdict: Mapping[str, Any],
    work_dir: Path,
    options: argparse.Namespace,
    revision: Mapping[str, Any],
    baseline_integrity: Mapping[str, Any],
    notes: Sequence[str],
) -> None:
    skipped = [language for language in all_languages if language not in languages]
    reused = sorted(
        language
        for language in languages
        if artifacts_by_language.get(language, {}).get("provenance", {}).get(
            "reused_existing_candidate"
        )
    )
    print(f"Pipeline equivalence — edition {edition_id} — {options.dpi} DPI")
    print(f"work dir: {work_dir}")
    print(
        f"repo revision: {revision['revision']}"
        + ("  (WORKING TREE DIRTY)" if revision.get("dirty") else "")
    )
    print(
        f"languages compared: {', '.join(languages) or 'none'}"
        + (f"  — NOT COMPARED: {', '.join(skipped)}" if skipped else "")
    )
    print(
        "candidate: "
        + (
            f"REUSED from the work dir for {', '.join(reused)} — gates below may "
            "describe an earlier build"
            if reused
            else "freshly rendered this run"
        )
    )
    for note in notes:
        print(f"note: {note}")
    print()
    for language in languages:
        print(f"[{language}]")
        provenance = artifacts_by_language.get(language, {}).get("provenance", {})
        print(
            f"  candidate reader {provenance.get('reader_sha256', '?')[:12]} "
            f"({provenance.get('reader_mtime')}), booklet "
            f"{provenance.get('booklet_sha256', '?')[:12]}, covers "
            f"{(provenance.get('front_cover_sha256') or '?')[:12]}/"
            f"{(provenance.get('back_cover_sha256') or '?')[:12]} "
            f"from {provenance.get('cover_source')}"
            + ("  [REUSED]" if provenance.get("reused_existing_candidate") else "")
        )
        for gate in gates_by_language[language]:
            mark = "PASS" if gate.passed else "FAIL"
            kind = "hard" if gate.hard else "soft"
            print(f"  {gate.name} {gate.title:<18} {mark} ({kind})  {gate.summary}")
        print()
    # Every language, side by side, so a report can no longer be summarised by
    # quoting whichever one happened to be printed first.
    print("Residuals, every language (a clause count is not a residual):")
    for language in all_languages:
        if language not in gates_by_language:
            print(f"  {language}: NOT COMPARED")
            continue
        print("  " + residual_line(language, gate_residuals(gates_by_language[language])))
    print()
    print("First failures:")
    any_failure = False
    for language in languages:
        for gate in gates_by_language[language]:
            if gate.passed:
                continue
            any_failure = True
            limit = _HARD_FAILURE_DISPLAY_LIMIT if gate.hard else _FAILURE_DISPLAY_LIMIT
            for line in gate.failures[:limit]:
                print(f"  {language} {gate.name}: {line}")
            if len(gate.failures) > limit:
                print(
                    f"  {language} {gate.name}: ... "
                    f"({len(gate.failures) - limit} more of "
                    f"{len(gate.failures)} failures, all in the JSON report)"
                )
            if gate.name == "G3":
                note = redistribution_note(gate.details.get("redistribution") or ())
                if note:
                    print(f"  {language} G3: {note}")
            text = gate.details.get("text") if gate.name == "G3" else None
            if text and text.get("first_difference_diff"):
                print(f"  {language} G3: reader page {text['first_differing_page']} text diff")
                for line in text["first_difference_diff"]:
                    print(f"      {line}")
    if not any_failure:
        print("  (none)")
    print()
    print(
        "frozen baseline integrity: "
        + (
            f"VERIFIED — {baseline_integrity['files']} files unchanged"
            if baseline_integrity["ok"]
            else "VIOLATED — " + "; ".join(baseline_integrity["failures"][:5])
        )
    )
    print()
    for line in GATE_STRENGTH_NOTES:
        print(line)
    print()
    print(
        f"VERDICT {verdict['result'].upper()} — hard failures: "
        f"{', '.join(verdict['hard_gate_failures']) or 'none'}; "
        f"soft failures: {', '.join(verdict['soft_gate_failures']) or 'none'}"
        + (f"; CANDIDATE REUSED for {', '.join(reused)}" if reused else "")
        + (f"; {', '.join(skipped)} NOT COMPARED" if skipped else "")
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare the WeasyPrint candidate against the frozen ReportLab baseline.",
    )
    parser.add_argument("--edition", required=True, help="Edition id, e.g. 002-unreleased")
    parser.add_argument(
        "--language",
        default="all",
        help="Language to compare: en, es, or all (default: all)",
    )
    parser.add_argument("--json", type=Path, help="Write the machine-readable report here")
    parser.add_argument(
        "--dpi",
        type=int,
        default=REFERENCE_DPI,
        help=f"Raster DPI for G4 and G5 (default: {REFERENCE_DPI})",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=DEFAULT_WORK_DIR,
        help=f"Where candidate artifacts and rasters are written (default: {DEFAULT_WORK_DIR})",
    )
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=DEFAULT_BASELINE,
        help=f"Frozen baseline root, read-only (default: {DEFAULT_BASELINE})",
    )
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root")
    parser.add_argument(
        "--reuse-candidate",
        action="store_true",
        help=(
            "Reuse a previously rendered candidate in the work dir instead of "
            "re-rendering. A cold run is ~90s; the verdict says REUSED and the "
            "report records the artifact hashes, so a stale result is visible."
        ),
    )
    parser.add_argument(
        "--text-band-tolerance",
        type=float,
        default=DEFAULT_TEXT_BAND_TOLERANCE,
        help=(
            "G3: points of vertical slack when grouping extracted words into "
            "reading-order bands. Must stay below the body leading (12.55pt) and "
            f"above intra-line jitter (2.06pt measured); default: {DEFAULT_TEXT_BAND_TOLERANCE}"
        ),
    )
    tolerances = parser.add_argument_group("G4/G5/G6 tolerances (reported, then compared)")
    tolerances.add_argument(
        "--ink-ratio-tolerance",
        type=float,
        default=0.002,
        help="G4: allowed absolute difference in per-page ink coverage ratio (default: 0.002)",
    )
    tolerances.add_argument(
        "--ink-bbox-tolerance",
        type=int,
        default=None,
        help=(
            "G4: allowed per-edge ink bounding-box shift in raster pixels. "
            f"Unset means 4 px at {REFERENCE_DPI} DPI, scaled with --dpi so the "
            "tolerance stays a fixed physical distance; an explicit value is used "
            "verbatim and warned about when --dpi is not the reference."
        ),
    )
    tolerances.add_argument(
        "--pixel-diff-threshold",
        type=int,
        default=8,
        help="G5: grayscale delta (0-255) a pixel must exceed to count as differing (default: 8)",
    )
    tolerances.add_argument(
        "--max-diff-fraction",
        type=float,
        default=0.01,
        help="G5: allowed fraction of differing pixels per page (default: 0.01)",
    )
    tolerances.add_argument(
        "--max-mean-abs-difference",
        type=float,
        default=2.0,
        help="G5: allowed per-page mean absolute grayscale difference (default: 2.0)",
    )
    tolerances.add_argument(
        "--max-chroma-mean-abs-difference",
        type=float,
        default=DEFAULT_MAX_CHROMA_MEAN_ABS_DIFFERENCE,
        help=(
            "G6: allowed per-page mean of the per-pixel channel spread "
            "max|dR,dG,dB| - min|dR,dG,dB|, in 0-255 units. This is a hue-only "
            "residual: an achromatic difference moves all three channels equally "
            "and scores exactly 0, so it does not consume the budget. Default: "
            f"{DEFAULT_MAX_CHROMA_MEAN_ABS_DIFFERENCE}, a quarter of G5's "
            "--max-mean-abs-difference and 3.7x today's worst surface (0.1339 on "
            "en reader page 28); it is aspirational, not fitted. The chromatic-ink "
            "clause of G6 has no tolerance flag at all -- the inks the two content "
            "streams set must match, and no CLI value can loosen that."
        ),
    )
    tolerances.add_argument(
        "--worst-diff-images",
        type=int,
        default=6,
        help="G5: how many worst-page difference images to save per surface (default: 6)",
    )
    return parser


def resolve_dpi_sensitive_tolerances(options: argparse.Namespace) -> list[str]:
    """Scale pixel tolerances with --dpi, or say plainly that they were not."""
    notes: list[str] = []
    scale = options.dpi / REFERENCE_DPI
    if options.ink_bbox_tolerance is None:
        options.effective_ink_bbox_tolerance = max(1, round(4 * scale))
        if options.dpi != REFERENCE_DPI:
            notes.append(
                f"--ink-bbox-tolerance scaled from 4 px at {REFERENCE_DPI} DPI to "
                f"{options.effective_ink_bbox_tolerance} px at {options.dpi} DPI"
            )
    else:
        options.effective_ink_bbox_tolerance = options.ink_bbox_tolerance
        if options.dpi != REFERENCE_DPI:
            factor = REFERENCE_DPI / options.dpi
            notes.append(
                f"--ink-bbox-tolerance {options.ink_bbox_tolerance} px is used verbatim at "
                f"{options.dpi} DPI; a pixel is {factor:.2f}x its {REFERENCE_DPI} DPI "
                f"physical size, so the tolerance is {factor:.2f}x as "
                f"{'loose' if factor > 1 else 'tight'} as the same number at {REFERENCE_DPI} DPI"
            )
    if options.dpi != REFERENCE_DPI:
        notes.append(
            f"G5 --max-diff-fraction and --pixel-diff-threshold are DPI-sensitive: "
            f"antialiasing edges scale with resolution, so residuals at {options.dpi} DPI "
            f"are not comparable with the {REFERENCE_DPI} DPI numbers recorded elsewhere"
        )
    return notes


def main(argv: Sequence[str] | None = None) -> int:
    options = build_parser().parse_args(argv)
    root = resolve_path(options.root)
    baseline_root = resolve_path(options.baseline_dir)
    baseline_dir = resolve_path(baseline_root / options.edition)
    if not baseline_dir.is_dir():
        raise SystemExit(f"Frozen baseline directory not found: {baseline_dir}")
    protected = protected_trees(root=root, baseline_root=baseline_root)
    work = WorkDir(options.work_dir, protected)
    if options.json:
        assert_outside_protected("--json report", options.json, protected)
    notes = resolve_dpi_sensitive_tolerances(options)

    baseline_before = tree_hashes(baseline_root)

    from magazine.compiler import Magazine

    magazine = Magazine(root)
    editions = magazine._validate_languages(options.edition)
    options.primary_language = magazine.primary_language
    all_languages = [language for language in magazine.languages if language in editions]
    if options.language == "all":
        languages = list(all_languages)
    else:
        if options.language not in editions:
            raise SystemExit(
                f"Unknown language {options.language!r}; edition has {sorted(editions)}"
            )
        languages = [options.language]

    revision = git_revision(root)
    gates_by_language: dict[str, list[Gate]] = {}
    artifacts_by_language: dict[str, dict[str, Any]] = {}
    for language in languages:
        gates, artifacts = compare_language(
            root=root,
            edition_id=options.edition,
            language=language,
            edition=editions[language],
            baseline_dir=baseline_dir,
            work=work,
            options=options,
        )
        gates_by_language[language] = gates
        artifacts_by_language[language] = artifacts

    baseline_after = tree_hashes(baseline_root)
    integrity = integrity_failures(baseline_before, baseline_after)
    baseline_integrity = {
        "root": str(baseline_root),
        "files": len(baseline_before),
        "ok": not integrity,
        "failures": integrity,
        "ignored_names": sorted(_INTEGRITY_IGNORED_NAMES),
    }

    verdict = aggregate_gates(
        gates_by_language,
        extra_hard_failures=["baseline-integrity"] if integrity else [],
    )
    print_report(
        edition_id=options.edition,
        languages=languages,
        all_languages=all_languages,
        gates_by_language=gates_by_language,
        artifacts_by_language=artifacts_by_language,
        verdict=verdict,
        work_dir=work.root,
        options=options,
        revision=revision,
        baseline_integrity=baseline_integrity,
        notes=notes,
    )

    if options.json:
        report = {
            "schema_version": 2,
            "edition": options.edition,
            "languages": languages,
            "languages_not_compared": [
                language for language in all_languages if language not in languages
            ],
            "raster_dpi": options.dpi,
            "repo_revision": dict(revision),
            "baseline_integrity": baseline_integrity,
            "gate_strength_notes": list(GATE_STRENGTH_NOTES),
            "notes": list(notes),
            "tolerances": {
                "page_box_points": MEDIABOX_TOLERANCE,
                "imposition_position_points": IMPOSITION_POSITION_TOLERANCE,
                "text_band_points": options.text_band_tolerance,
                "ink_ratio": options.ink_ratio_tolerance,
                "ink_bbox_px": options.effective_ink_bbox_tolerance,
                "ink_bbox_px_requested": options.ink_bbox_tolerance,
                "pixel_diff_threshold": options.pixel_diff_threshold,
                "max_diff_fraction": options.max_diff_fraction,
                "max_mean_abs_difference": options.max_mean_abs_difference,
                "max_chroma_mean_abs_difference": options.max_chroma_mean_abs_difference,
                "color_value": COLOR_VALUE_TOLERANCE,
            },
            "verdict": dict(verdict),
            "residuals": {
                language: gate_residuals(gates)
                for language, gates in gates_by_language.items()
            },
            "gates": {
                language: [gate.as_json() for gate in gates]
                for language, gates in gates_by_language.items()
            },
            "artifacts": artifacts_by_language,
        }
        options.json.parent.mkdir(parents=True, exist_ok=True)
        options.json.write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
        )
        print(f"JSON report: {options.json}")

    return int(verdict["exit_code"])


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
