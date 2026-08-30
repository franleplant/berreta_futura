
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import ValidationError


def declared_editorial_page_cap(raw: Mapping[str, Any], ceiling: int) -> int:

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

    relative_page: int
    frame_index: int
    used: float
    capacity: float


@dataclass(frozen=True)
class FigurePlacement:

    figure_id: str
    article_id: str
    page: int
    path: Path
    pixel_dimensions: tuple[int, int]
    box_points: tuple[float, float, float, float]
    effective_ppi: float
    caption: str
    credit: str


@dataclass(frozen=True)
class RenderLayout:

    toc: dict[str, int]
    article_pages: dict[str, int]
    editorial_pages: int | None
    design: str
    cover_art_size_points: tuple[float, float] | None
    article_frame_usage: dict[str, tuple[FrameUsage, ...]]
    article_terminal_balance: dict[str, float]
    figure_placements: tuple[FigurePlacement, ...] = ()
    article_opener_fits: dict[str, bool] = field(default_factory=dict)
