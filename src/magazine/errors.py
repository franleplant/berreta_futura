class MagazineError(Exception):
    pass


class ValidationError(MagazineError):
    def __init__(self, errors: list[str] | str):
        self.errors = [errors] if isinstance(errors, str) else errors
        super().__init__("\n".join(self.errors))


class DependencyError(MagazineError):
    pass


class CoverError(MagazineError):
    pass


class CoverAssetError(CoverError):
    pass


class CoverOverflowError(CoverError):
    pass


class CoverPdfError(CoverError):
    pass


class CoverMismatchError(CoverError):
    pass
