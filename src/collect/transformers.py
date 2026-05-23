"""API-specific response transformers for market data normalization."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.collect.exceptions import MarketDataAPIError, MarketDataParseError

logger = logging.getLogger(__name__)


def _validate_required_fields(
    data: dict[str, Any],
    required_fields: list[str],
    provider: str,
) -> None:
    """Validate that all required fields are present in the data."""
    missing = [f for f in required_fields if f not in data or data[f] is None]
    if missing:
        error_msg = f"Missing required field(s): {', '.join(missing)}"
        logger.error(f"[{provider}] {error_msg} | Response snippet: {str(data)[:200]}")
        raise MarketDataParseError(error_msg)


def _unix_to_iso8601(timestamp: int | float) -> str:
    """Convert Unix timestamp to ISO8601 UTC string."""
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.isoformat()


def transform_yahoo_finance(
    response: dict[str, Any],
    target_date: str,
) -> dict[str, Any]:
    """
    Transform Yahoo Finance API response to unified OHLCV schema.

    Yahoo Finance v8 chart response structure:
    {
        "chart": {
            "result": [{
                "meta": {...},
                "timestamp": [1705276800, ...],
                "indicators": {
                    "quote": [{
                        "open": [185.50, ...],
                        "high": [187.20, ...],
                        "low": [184.80, ...],
                        "close": [185.50, ...],
                        "volume": [45000000, ...]
                    }],
                    "adjclose": [{ "adjclose": [185.25, ...] }]
                }
            }]
        }
    }
    """
    if "chart" not in response or "result" not in response["chart"]:
        error_msg = "Invalid Yahoo Finance response: missing 'chart.result'"
        logger.error(f"{error_msg} | Response: {str(response)[:200]}")
        raise MarketDataParseError(error_msg)

    results = response["chart"]["result"]
    if not results:
        error_msg = "Yahoo Finance returned empty result set"
        logger.error(error_msg)
        raise MarketDataParseError(error_msg)

    result = results[0]
    timestamps = result.get("timestamp", [])
    quote = result.get("indicators", {}).get("quote", [{}])[0]
    adjclose_data = result.get("indicators", {}).get("adjclose", [{}])
    adjclose = adjclose_data[0].get("adjclose", []) if adjclose_data else []

    if not timestamps:
        error_msg = "Yahoo Finance response contains no timestamp data"
        logger.error(error_msg)
        raise MarketDataParseError(error_msg)

    target_ts = _parse_date_to_timestamp(target_date)

    idx = None
    for i, ts in enumerate(timestamps):
        if _is_same_trading_day(ts, target_ts):
            idx = i
            break

    if idx is None:
        closest_idx = 0
        min_diff = abs(timestamps[0] - target_ts)
        for i, ts in enumerate(timestamps):
            diff = abs(ts - target_ts)
            if diff < min_diff:
                min_diff = diff
                closest_idx = i
        idx = closest_idx

    ohlcv = {
        "open": quote.get("open", [None])[idx] if quote.get("open") else None,
        "high": quote.get("high", [None])[idx] if quote.get("high") else None,
        "low": quote.get("low", [None])[idx] if quote.get("low") else None,
        "close": quote.get("close", [None])[idx] if quote.get("close") else None,
        "volume": int(quote.get("volume", [0])[idx]) if quote.get("volume") else 0,
        "adjusted_close": (adjclose[idx] if adjclose and idx < len(adjclose) else None),
        "timestamp": _unix_to_iso8601(timestamps[idx]),
    }

    _validate_required_fields(ohlcv, ["open", "high", "low", "close"], "Yahoo Finance")

    return ohlcv


def transform_alpha_vantage(
    response: dict[str, Any],
    target_date: str,
) -> dict[str, Any]:
    """
    Transform Alpha Vantage API response to unified OHLCV schema.

    Alpha Vantage TIME_SERIES_DAILY response structure:
    {
        "Meta Data": {...},
        "Time Series (Daily)": {
            "2024-01-15": {
                "1. open": "185.50",
                "2. high": "187.20",
                "3. low": "184.80",
                "4. close": "185.50",
                "5. volume": "45000000",
                "6. adjusted close": "185.25"  // optional
            }
        }
    }
    """
    if "Error Message" in response:
        error_msg = response["Error Message"]
        logger.error(f"[AlphaVantage] API error: {error_msg}")
        raise MarketDataAPIError(error_msg)

    if "Note" in response or "Information" in response:
        error_msg = response.get("Note") or response.get("Information")
        logger.error(f"[AlphaVantage] API error: {error_msg}")
        raise MarketDataAPIError(error_msg)

    time_series = response.get("Time Series (Daily)")
    if not time_series:
        error_msg = "Alpha Vantage response missing 'Time Series (Daily)'"
        logger.error(f"{error_msg} | Response: {str(response)[:200]}")
        raise MarketDataParseError(error_msg)

    if target_date not in time_series:
        available_dates = sorted(time_series.keys(), reverse=True)
        if not available_dates:
            error_msg = "Alpha Vantage time series is empty"
            raise MarketDataParseError(error_msg)
        original_target_date = target_date
        target_date = available_dates[0]
        logger.warning(
            f"[AlphaVantage] Date {original_target_date} not found, using {target_date}"
        )

    day_data = time_series[target_date]

    def _safe_float(value: str | None) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except ValueError, TypeError:
            return None

    def _safe_int(value: str | None) -> int:
        if value is None:
            return 0
        try:
            return int(float(value))
        except ValueError, TypeError:
            return 0

    ohlcv = {
        "open": _safe_float(day_data.get("1. open")),
        "high": _safe_float(day_data.get("2. high")),
        "low": _safe_float(day_data.get("3. low")),
        "close": _safe_float(day_data.get("4. close")),
        "volume": _safe_int(day_data.get("5. volume")),
        "adjusted_close": _safe_float(day_data.get("6. adjusted close")),
        "timestamp": f"{target_date}T00:00:00+00:00",
    }

    _validate_required_fields(ohlcv, ["open", "high", "low", "close"], "AlphaVantage")

    return ohlcv


def transform_finnhub(
    response: dict[str, Any],
    target_date: str,
) -> dict[str, Any]:
    """
    Transform Finnhub API response to unified OHLCV schema.

    Finnhub stock/candle response structure:
    {
        "c": [185.50, 186.75],   // Close prices
        "h": [187.20, 188.10],   // High prices
        "l": [184.80, 185.50],   // Low prices
        "o": [185.00, 186.20],   // Open prices
        "v": [45000000, 42000000], // Volumes
        "t": [1705276800, 1705363200], // Timestamps (Unix)
        "s": "ok"  // Status: "ok" | "no_data"
    }
    """
    if response.get("s") == "no_data":
        error_msg = "Finnhub returned no data for the requested period"
        logger.error(f"[Finnhub] {error_msg}")
        raise MarketDataParseError(error_msg)

    required = ["c", "h", "l", "o", "v", "t"]
    missing = [f for f in required if f not in response or response[f] is None]
    if missing:
        error_msg = f"Finnhub missing required field(s): {', '.join(missing)}"
        logger.error(f"{error_msg} | Response: {str(response)[:200]}")
        raise MarketDataParseError(error_msg)

    target_ts = _parse_date_to_timestamp(target_date)

    timestamps = response["t"]
    idx = None
    for i, ts in enumerate(timestamps):
        if _is_same_trading_day(ts, target_ts):
            idx = i
            break

    if idx is None:
        closest_idx = 0
        min_diff = abs(timestamps[0] - target_ts)
        for i, ts in enumerate(timestamps):
            diff = abs(ts - target_ts)
            if diff < min_diff:
                min_diff = diff
                closest_idx = i
        idx = closest_idx

    ohlcv = {
        "open": response["o"][idx] if idx < len(response["o"]) else None,
        "high": response["h"][idx] if idx < len(response["h"]) else None,
        "low": response["l"][idx] if idx < len(response["l"]) else None,
        "close": response["c"][idx] if idx < len(response["c"]) else None,
        "volume": int(response["v"][idx]) if idx < len(response["v"]) else 0,
        "adjusted_close": None,
        "timestamp": _unix_to_iso8601(timestamps[idx]),
    }

    _validate_required_fields(ohlcv, ["open", "high", "low", "close"], "Finnhub")

    return ohlcv


def _parse_date_to_timestamp(date_str: str) -> int:
    """Parse date string to Unix timestamp."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _is_same_trading_day(ts1: int, ts2: int) -> bool:
    """Check if two Unix timestamps are the same trading day (UTC)."""
    dt1 = datetime.fromtimestamp(ts1, tz=timezone.utc).date()
    dt2 = datetime.fromtimestamp(ts2, tz=timezone.utc).date()
    return dt1 == dt2
