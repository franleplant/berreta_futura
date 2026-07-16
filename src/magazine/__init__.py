"""Public seam for the magazine compiler."""

from .compiler import BuildResult, Magazine
from .errors import MagazineError, ValidationError
from .records import SourceRecord
from .release import ReleaseTransition

__all__ = [
    "BuildResult",
    "Magazine",
    "MagazineError",
    "ReleaseTransition",
    "SourceRecord",
    "ValidationError",
]
