"""Which renderer typesets the A5 reader, and the design vocabulary it owns.

The publication has two independent reader renderers.  ``render.render_a5``
is the original ReportLab typesetter; ``weasyprint_adapter.render_a5_weasyprint``
is the HTML/CSS path and the default.

**Selecting ReportLab is no longer a rollback.**  The two were interchangeable
only while three shaping scaffolds held WeasyPrint's line breaking down to
ReportLab's, and those came out after cutover: the reader now kerns, applies
ligatures and takes Pango's own intra-token break opportunities, and ReportLab
does none of the three.  Choosing it therefore *changes the publication* --
66% of English running words shift, worst case 1.87pt on a single word, and line
breaks move -- rather than restoring it.  It remains a working, supported engine
and reproduces the pre-cutover publication byte for byte, so it is still the
escape hatch if the WeasyPrint path ever cannot build an edition at all; but
flipping this key is an editorial decision, not an operational one.  See
"The rollback window is closed" in ``docs/RENDERER_MIGRATION.md``.

Two properties are load-bearing here.

**Neither path depends on the other.**  Each renderer is imported lazily, inside
the factory that builds it, so selecting one engine never imports the other's
module.  Deleting the unselected renderer would leave the selected one working.
The layout facts both engines return (``RenderLayout``, ``FigurePlacement``,
``FrameUsage``) live in the neutral ``reader_layout`` module, owned by neither
engine, precisely so this stays true; ``tests/test_render_engine.py`` probes
both directions in fresh interpreters.

**Neither path is handed the other's design.**  ``design`` is not a shared
vocabulary: ``render_a5`` accepts only ``"monument"`` and
``render_a5_weasyprint`` accepts only ``"WeasyPrint / A5 fold proof"``, and each
*raises* on the other's value.  A renderer therefore carries the design it
renders as part of its identity, taken from a constant in its own module, and
the compiler never forwards a design across the seam.  ``[render] design`` in
``magazine.toml`` is the ReportLab engine's design direction and is read only
when that engine is selected; the WeasyPrint path has exactly one design and
names it itself.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .errors import ValidationError

if TYPE_CHECKING:  # pragma: no cover - typing only, keeps both paths unimported
    from .manifest import Edition
    from .reader_layout import RenderLayout


DEFAULT_ENGINE = "weasyprint"
"""The production reader renderer.  ``[render] engine`` absent means this."""


@dataclass(frozen=True)
class ReaderRenderer:
    """One reader engine: its name, the design it renders, and how to run it."""

    engine: str
    design: str
    design_direction: str
    """The ``layout.design_direction`` label this engine writes into a build's
    ``edition-manifest.json``.  For ReportLab it differs from ``design`` (the
    ``[render] design`` key ``"monument"`` renders as ``"A / Quiet Standard"``);
    the render review record uses it to prove which engine produced the PDFs
    under review."""
    shaping_scaffolds: tuple[str, ...]
    write_reader: Callable[..., "RenderLayout"]

    def render(self, edition: "Edition", output: Path) -> "RenderLayout":
        """Write the A5 reader PDF for ``edition`` and return its layout facts."""
        return self.write_reader(edition, output, design=self.design)


def _weasyprint(design: str | None) -> ReaderRenderer:
    # ``design`` is the ReportLab engine's key and is deliberately not consulted:
    # this renderer owns a single design and would reject any other value.
    from .weasyprint_adapter import (
        SHAPING_SCAFFOLDS,
        WEASYPRINT_DESIGN,
        render_a5_weasyprint,
    )

    return ReaderRenderer(
        engine="weasyprint",
        design=WEASYPRINT_DESIGN,
        design_direction=WEASYPRINT_DESIGN,
        shaping_scaffolds=SHAPING_SCAFFOLDS,
        write_reader=render_a5_weasyprint,
    )


def _reportlab(design: str | None) -> ReaderRenderer:
    from .render import DESIGN_LABEL, DESIGN_MONUMENT, render_a5

    # An unsupported direction stays ``render_a5``'s error to raise, so the
    # switch does not become a second place that decides what a design may be.
    return ReaderRenderer(
        engine="reportlab",
        design=design or DESIGN_MONUMENT,
        design_direction=DESIGN_LABEL,
        shaping_scaffolds=(),
        write_reader=render_a5,
    )


_ENGINES: dict[str, Callable[[str | None], ReaderRenderer]] = {
    "weasyprint": _weasyprint,
    "reportlab": _reportlab,
}

ENGINES: tuple[str, ...] = tuple(sorted(_ENGINES))


def engine_name(configured: object | None) -> str:
    """Return a known engine name, or raise so a typo cannot fall back silently."""
    if configured is None:
        return DEFAULT_ENGINE
    name = str(configured).strip()
    if name not in _ENGINES:
        raise ValidationError(
            f"Unknown render engine {name!r}; expected one of "
            + ", ".join(repr(known) for known in ENGINES)
            + f" (omit [render] engine for the default {DEFAULT_ENGINE!r})"
        )
    return name


def reader_renderer(
    configured: object | None = None, *, design: str | None = None
) -> ReaderRenderer:
    """Select the reader renderer named by ``configured`` (``None`` for default)."""
    return _ENGINES[engine_name(configured)](design)
