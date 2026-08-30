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


@dataclass(frozen=True)
class ReaderRenderer:
    engine: str
    design: str
    design_direction: str
    shaping_scaffolds: tuple[str, ...]
    write_reader: Callable[..., "RenderLayout"]

    def render(self, edition: "Edition", output: Path) -> "RenderLayout":
        return self.write_reader(edition, output, design=self.design)


def _weasyprint(design: str | None) -> ReaderRenderer:

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
    return _ENGINES[engine_name(configured)](design)
