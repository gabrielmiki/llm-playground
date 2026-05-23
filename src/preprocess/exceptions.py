"""Custom exceptions for the preprocessing pipeline."""


class PreprocessingError(Exception):
    """Base exception for all preprocessing errors."""

    pass


class LanguageFilterError(PreprocessingError):
    """Raised when language detection fails."""

    pass


class FusionError(PreprocessingError):
    """Raised when data fusion correlation fails."""

    pass
