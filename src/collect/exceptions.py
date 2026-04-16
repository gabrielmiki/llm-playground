"""Custom exceptions for market data collection."""


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
