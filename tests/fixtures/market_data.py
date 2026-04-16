"""Mock API responses for market data providers."""

from __future__ import annotations

import pytest


@pytest.fixture
def yahoo_response_valid() -> dict:
    """Valid Yahoo Finance v8 chart response."""
    return {
        "chart": {
            "result": [
                {
                    "meta": {
                        "symbol": "AAPL",
                        "regularMarketTime": 1705276800,
                        "currency": "USD",
                    },
                    "timestamp": [1705276800, 1705363200, 1705449600],
                    "indicators": {
                        "quote": [
                            {
                                "open": [185.50, 186.20, 187.10],
                                "high": [187.20, 188.10, 188.50],
                                "low": [184.80, 185.50, 186.20],
                                "close": [185.50, 186.75, 187.30],
                                "volume": [45000000, 42000000, 38000000],
                            }
                        ],
                        "adjclose": [{"adjclose": [185.25, 186.50, 187.05]}],
                    },
                }
            ]
        }
    }


@pytest.fixture
def yahoo_response_missing_close() -> dict:
    """Yahoo Finance response missing 'close' field in quote."""
    return {
        "chart": {
            "result": [
                {
                    "meta": {"symbol": "AAPL"},
                    "timestamp": [1705276800],
                    "indicators": {
                        "quote": [
                            {
                                "open": [185.50],
                                "high": [187.20],
                                "low": [184.80],
                                "volume": [45000000],
                            }
                        ],
                        "adjclose": [{"adjclose": [185.25]}],
                    },
                }
            ]
        }
    }


@pytest.fixture
def yahoo_response_empty_result() -> dict:
    """Yahoo Finance response with empty result."""
    return {"chart": {"result": []}}


@pytest.fixture
def yahoo_response_no_timestamp() -> dict:
    """Yahoo Finance response with no timestamp data."""
    return {
        "chart": {
            "result": [
                {
                    "meta": {"symbol": "AAPL"},
                    "timestamp": [],
                    "indicators": {
                        "quote": [
                            {
                                "open": [185.50],
                                "high": [187.20],
                                "low": [184.80],
                                "close": [185.50],
                                "volume": [45000000],
                            }
                        ],
                        "adjclose": [{"adjclose": [185.25]}],
                    },
                }
            ]
        }
    }


@pytest.fixture
def alpha_vantage_response_valid() -> dict:
    """Valid Alpha Vantage TIME_SERIES_DAILY response."""
    return {
        "Meta Data": {
            "1. Information": "Daily Prices (open, high, low, close) and Volumes",
            "2. Symbol": "AAPL",
            "3. Last Refreshed": "2024-01-15",
        },
        "Time Series (Daily)": {
            "2024-01-15": {
                "1. open": "185.50",
                "2. high": "187.20",
                "3. low": "184.80",
                "4. close": "185.50",
                "5. volume": "45000000",
            },
            "2024-01-16": {
                "1. open": "186.20",
                "2. high": "188.10",
                "3. low": "185.50",
                "4. close": "186.75",
                "5. volume": "42000000",
            },
        },
    }


@pytest.fixture
def alpha_vantage_response_error() -> dict:
    """Alpha Vantage response with API error."""
    return {
        "Error Message": "Invalid API call. Please retry or visit the documentation."
    }


@pytest.fixture
def alpha_vantage_response_rate_limit() -> dict:
    """Alpha Vantage response indicating rate limit."""
    return {
        "Note": "Thank you for using Alpha Vantage! Our standard API call frequency is 5 requests per minute and 500 requests per day."
    }


@pytest.fixture
def alpha_vantage_response_missing_series() -> dict:
    """Alpha Vantage response missing Time Series."""
    return {"Meta Data": {"1. Information": "Test"}}


@pytest.fixture
def alpha_vantage_response_with_adjusted_close() -> dict:
    """Alpha Vantage response with adjusted close."""
    return {
        "Meta Data": {"2. Symbol": "AAPL"},
        "Time Series (Daily)": {
            "2024-01-15": {
                "1. open": "185.50",
                "2. high": "187.20",
                "3. low": "184.80",
                "4. close": "185.50",
                "5. volume": "45000000",
                "6. adjusted close": "185.25",
            }
        },
    }


@pytest.fixture
def finnhub_response_valid() -> dict:
    """Valid Finnhub stock/candle response."""
    return {
        "c": [185.50, 186.75, 187.30],
        "h": [187.20, 188.10, 188.50],
        "l": [184.80, 185.50, 186.20],
        "o": [185.50, 186.20, 187.10],
        "v": [45000000, 42000000, 38000000],
        "t": [1705276800, 1705363200, 1705449600],
        "s": "ok",
    }


@pytest.fixture
def finnhub_response_no_data() -> dict:
    """Finnhub response indicating no data available."""
    return {
        "c": None,
        "h": None,
        "l": None,
        "o": None,
        "v": None,
        "t": None,
        "s": "no_data",
    }


@pytest.fixture
def finnhub_response_missing_fields() -> dict:
    """Finnhub response missing required fields."""
    return {"c": [185.50], "h": [187.20], "l": [184.80]}


@pytest.fixture
def expected_ohlcv() -> dict:
    """Expected normalized OHLCV data structure."""
    return {
        "open": 185.50,
        "high": 187.20,
        "low": 184.80,
        "close": 185.50,
        "volume": 45000000,
        "adjusted_close": 185.25,
        "timestamp": "2024-01-15T00:00:00+00:00",
    }
