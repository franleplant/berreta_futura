"""Which renderer typesets the A5 reader, and the design vocabulary it owns.

The publication has two independent reader renderers.  ``render.render_a5``
is the original ReportLab typesetter; ``weasyprint_adapter.render_a5_weasyprint``
is the HTML/CSS path.  They were proven equivalent on edition ``002-unreleased``
before WeasyPrint became the default, and ReportLab is retained as the rollback.

Two properties are load-bearing here.

**Neither path depends on the other.**  Each renderer is imported lazily, inside
the factory that builds it, so selecting one engine never imports the other's
module.  Deleting the unselected renderer would leave the selected one working.

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
    from .render import RenderLayout


DEFAULT_ENGINE = "weasyprint"
"""The production reader renderer.  ``[render] engine`` absent means this."""


@dataclass(frozen=True)
class ReaderRenderer:
    """One reader engine: its name, the design it renders, and how to run it."""

    engine: str
    design: str
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
        shaping_scaffolds=SHAPING_SCAFFOLDS,
        write_reader=render_a5_weasyprint,
    )


def _reportlab(design: str | None) -> ReaderRenderer:
    from .render import DESIGN_MONUMENT, render_a5

    # An unsupported direction stays ``render_a5``'s error to raise, so the
    # switch does not become a second place that decides what a design may be.
    return ReaderRenderer(
        engine="reportlab",
        design=design or DESIGN_MONUMENT,
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
