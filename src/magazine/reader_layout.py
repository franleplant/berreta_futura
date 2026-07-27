"""The layout facts a reader renderer reports, neutral to which engine ran.

Both A5 reader engines -- ``render.render_a5`` (ReportLab) and
``weasyprint_adapter.render_a5_weasyprint`` -- return the same value shapes so
the compiler, the packaging step and the render review can consume either
engine's build without knowing which one produced it.  The shapes therefore
live here, owned by neither engine: importing the production adapter must not
drag the 2400-line legacy typesetter into the process (see
``render_engine.py``'s isolation contract), and deleting either renderer
leaves the other, and these facts, intact.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError


def declared_editorial_page_cap(raw: Mapping[str, Any], ceiling: int) -> int:
    """How many reader pages *this* edition's opening editorial may occupy.

    ``ceiling`` is the publication's hard maximum -- each engine's own
    ``MAX_EDITORIAL_PAGES`` -- and no edition may raise it.  An edition may
    however hold itself to something tighter through
    ``format.max_editorial_pages``, and the house standard is one page: the
    editorial is the reader's front door and a door that turns is not one.  The
    field is per-edition rather than global because edition 001 shipped a
    two-page editorial and its frozen artifact must keep rebuilding.

    Resolution lives here, beside the layout facts, because the cap is a rule of
    the publication and not of a typesetter: both engines enforce the same
    number against the same manifest key, without importing each other.
    """

    format_data = raw.get("format") or {}
    declared = format_data.get("max_editorial_pages", ceiling)
    try:
        cap = int(declared)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f"format.max_editorial_pages must be an integer from 1 to {ceiling}"
        ) from exc
    if cap > ceiling:
        raise ValidationError(
            f"format.max_editorial_pages is a hard publication rule and must not "
            f"exceed {ceiling}"
        )
    if cap < 1:
        raise ValidationError("format.max_editorial_pages must be at least 1")
    return cap


@dataclass(frozen=True)
class FrameUsage:
    """How much of one text frame an article actually filled.

    Only the ReportLab engine measures frames; the WeasyPrint path reports an
    empty mapping because CSS owns its own fragmentation.
    """

    relative_page: int
    frame_index: int
    used: float
    capacity: float


@dataclass(frozen=True)
class FigurePlacement:
    """One curated figure as it landed on a reader page.

    A placement records a *curated figure* and nothing else -- never a tail
    motif or a closing plate -- because preflight raises low-resolution and
    print-contrast findings per placement.
    """

    figure_id: str
    article_id: str
    page: int
    path: Path
    pixel_dimensions: tuple[int, int]
    box_points: tuple[float, float, float, float]
    effective_ppi: float
    caption: str
    credit: str
    rights_status: str


@dataclass(frozen=True)
class RenderLayout:
    """What one reader render established: folios, spans, and placements.

    ``article_terminal_balance`` is a legacy field and is always empty.  The
    terminal-page balancer that once shortened an article's last two frames
    was retired -- genuine tail space is handled by the article-end ornament
    instead -- and no engine plans a balance any more.  The field (and the
    ``layout.article_terminal_balance`` key ``compiler.py`` writes from it)
    stays because ``edition-manifest.json`` is a packaged artifact: every
    manifest written since the balancer was pinned off carries the key as
    ``{}``, edition 001's frozen released artifact retains its historical
    non-empty values, and dropping the key would change the bytes of
    otherwise identical rebuilds.
    """

    toc: dict[str, int]
    article_pages: dict[str, int]
    editorial_pages: int | None
    design: str
    cover_art_size_points: tuple[float, float] | None
    article_frame_usage: dict[str, tuple[FrameUsage, ...]]
    article_terminal_balance: dict[str, float]
    figure_placements: tuple[FigurePlacement, ...] = ()
