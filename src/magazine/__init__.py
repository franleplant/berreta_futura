"""Public seam for the magazine compiler."""

from .compiler import BuildResult, LanguageBuildResult, Magazine
from .errors import MagazineError, ValidationError
from .records import SourceRecord
from .release import ReleaseTransition

__all__ = [
    "BuildResult",
    "LanguageBuildResult",
    "Magazine",
    "MagazineError",
    "ReleaseTransition",
    "SourceRecord",
    "ValidationError",
]
