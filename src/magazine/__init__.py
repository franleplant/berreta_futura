"""Public seam for the magazine compiler."""

from .compiler import (
    ArticleWorkflowReport,
    BuildResult,
    LanguageBuildResult,
    Magazine,
)
from .errors import MagazineError, ValidationError
from .records import AuthorProfile, SourceRecord
from .release import ReleaseTransition

__all__ = [
    "BuildResult",
    "ArticleWorkflowReport",
    "AuthorProfile",
    "LanguageBuildResult",
    "Magazine",
    "MagazineError",
    "ReleaseTransition",
    "SourceRecord",
    "ValidationError",
]
