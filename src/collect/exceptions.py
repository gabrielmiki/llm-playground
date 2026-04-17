"""Custom exceptions for market data and news data collection."""


class MarketDataError(Exception):
    """Base exception for all market data errors."""

    pass


class MarketDataParseError(MarketDataError):
    """Raised when response parsing fails (missing fields, wrong types, invalid JSON)."""

    pass


class MarketDataAPIError(MarketDataError):
    """Raised when API returns error code in response body."""

    pass


class MarketDataUnavailableError(MarketDataError):
    """Raised when all data sources fail (after exhausting all fallback providers)."""

    pass


class NewsDataError(Exception):
    """Base exception for all news data errors."""

    pass


class NewsDataParseError(NewsDataError):
    """Raised when response parsing fails (missing fields, wrong types, invalid JSON)."""

    pass


class NewsDataAPIError(NewsDataError):
    """Raised when API returns error code in response body."""

    pass


class NewsDataUnavailableError(NewsDataError):
    """Raised when all data sources fail (after exhausting all fallback providers)."""

    pass
