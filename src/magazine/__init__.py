"""Public seam for the magazine compiler."""

from .compiler import BuildResult, Magazine
from .errors import MagazineError, ValidationError
from .records import SourceRecord

__all__ = ["BuildResult", "Magazine", "MagazineError", "SourceRecord", "ValidationError"]

