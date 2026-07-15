class MagazineError(Exception):
    """Base error for expected compiler failures."""


class ValidationError(MagazineError):
    """Raised when structured input violates compiler invariants."""

    def __init__(self, errors: list[str] | str):
        self.errors = [errors] if isinstance(errors, str) else errors
        super().__init__("\n".join(self.errors))


class DependencyError(MagazineError):
    """Raised when an optional rendering dependency is unavailable."""

