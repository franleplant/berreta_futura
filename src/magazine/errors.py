class MagazineError(Exception):
    """Base error for expected compiler failures."""


class ValidationError(MagazineError):
    """Raised when structured input violates compiler invariants."""

    def __init__(self, errors: list[str] | str):
        self.errors = [errors] if isinstance(errors, str) else errors
        super().__init__("\n".join(self.errors))


class DependencyError(MagazineError):
    """Raised when an optional rendering dependency is unavailable."""


class CoverError(MagazineError):
    """Base error for failures isolated to the cover compilation seam."""


class CoverAssetError(CoverError):
    """Raised when a cover design asset is missing, unsafe, or changed."""


class CoverOverflowError(CoverError):
    """Raised when localized cover copy cannot fit its approved zone."""


class CoverPdfError(CoverError):
    """Raised when a compiled cover PDF violates the one-page A5 contract."""


class CoverMismatchError(CoverError):
    """Raised by checked proofs after diagnostic artifacts have been written."""
