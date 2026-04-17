"""Market data collector with multi-provider fallback support."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import httpx

from src.collect.client import RetryableHTTPClient, RetryableHTTPError
from src.collect.exceptions import (
    MarketDataAPIError,
    MarketDataError,
    MarketDataParseError,
    MarketDataUnavailableError,
)
from src.collect.transformers import (
    transform_alpha_vantage,
    transform_finnhub,
    transform_yahoo_finance,
)

logger = logging.getLogger(__name__)

US_HOLIDAYS_2026 = frozenset(
    [
        "2026-01-01",
        "2026-01-19",
        "2026-02-16",
        "2026-04-03",
        "2026-05-25",
        "2026-07-03",
        "2026-09-07",
        "2026-11-26",
        "2026-12-25",
    ]
)


@dataclass
class MarketData:
    """Normalized market data for a single trading day."""

    open: float
    high: float
    low: float
    close: float
    volume: int
    adjusted_close: float | None
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "adjusted_close": self.adjusted_close,
            "timestamp": self.timestamp,
        }


class MarketDataCollector:
    """Market data collector with fallback across multiple providers.

    Providers are tried in order: Yahoo Finance -> Alpha Vantage -> Finnhub.
    Falls back to previous trading day for weekends/holidays.
    """

    YAHOO_BASE_URL = "https://query1.finance.yahoo.com"
    ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"
    FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

    def __init__(
        self,
        http_client: RetryableHTTPClient | None = None,
        alpha_vantage_key: str | None = None,
        finnhub_key: str | None = None,
        yahoo_key: str | None = None,
    ) -> None:
        self._client = http_client or RetryableHTTPClient()
        self._alpha_vantage_key = alpha_vantage_key or os.getenv("ALPHAVANTAGE_API_KEY")
        self._finnhub_key = finnhub_key or os.getenv("FINNHUB_API_KEY")
        self._yahoo_key = yahoo_key or os.getenv("YAHOO_API_KEY")

    def _adjust_to_trading_day(self, target_date: date) -> date:
        """Adjust date to previous trading day if weekend or holiday."""
        adjusted = target_date
        while True:
            weekday = adjusted.weekday()
            if weekday >= 5:
                adjusted -= timedelta(days=weekday - 4)
                continue
            if adjusted.strftime("%Y-%m-%d") in US_HOLIDAYS_2026:
                adjusted -= timedelta(days=1)
                continue
            break
        if adjusted != target_date:
            logger.info(f"Adjusted {target_date} to trading day {adjusted}")
        return adjusted

    async def _fetch_from_yahoo(
        self, ticker: str, target_date: date
    ) -> MarketData | None:
        """Fetch data from Yahoo Finance."""
        from datetime import datetime

        date_str = target_date.strftime("%Y-%m-%d")
        start_ts = int(datetime.combine(target_date, datetime.min.time()).timestamp())
        end_ts = start_ts + 86400

        url = f"{self.YAHOO_BASE_URL}/v8/finance/chart/{ticker}"
        params: dict[str, str | int] = {
            "period1": start_ts,
            "period2": end_ts,
            "interval": "1d",
        }

        logger.info(f"[Yahoo Finance] Fetching {ticker} for {date_str}")
        headers: dict[str, str] | None = None
        if self._yahoo_key:
            headers = {"X-Yahoo-API-Key": self._yahoo_key}
            logger.info("[Yahoo Finance] Using API key for authenticated request")
        try:
            response = await self._client.get(url, params=params, headers=headers)
            if response.status_code == 429:
                logger.warning("[Yahoo Finance] Rate limited (429)")
                return None
            response.raise_for_status()
            data = response.json()
            ohlcv = transform_yahoo_finance(data, date_str)
            return MarketData(**ohlcv)
        except (httpx.HTTPError, RetryableHTTPError) as exc:
            logger.warning(f"[Yahoo Finance] Request failed: {exc}")
            return None
        except MarketDataParseError:
            return None
        except MarketDataAPIError:
            return None

    async def _fetch_from_alpha_vantage(
        self, ticker: str, target_date: date
    ) -> MarketData | None:
        """Fetch data from Alpha Vantage."""
        if not self._alpha_vantage_key:
            logger.warning("[Alpha Vantage] No API key configured")
            return None

        date_str = target_date.strftime("%Y-%m-%d")
        url = self.ALPHA_VANTAGE_BASE_URL
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": ticker,
            "outputsize": "compact",
            "apikey": self._alpha_vantage_key,
        }

        logger.info(f"[Alpha Vantage] Fetching {ticker} for {date_str}")
        try:
            response = await self._client.get(url, params=params)
            if response.status_code == 429:
                logger.warning("[Alpha Vantage] Rate limited (429)")
                return None
            response.raise_for_status()
            data = response.json()
            ohlcv = transform_alpha_vantage(data, date_str)
            return MarketData(**ohlcv)
        except (httpx.HTTPError, RetryableHTTPError) as exc:
            logger.warning(f"[Alpha Vantage] Request failed: {exc}")
            return None
        except MarketDataParseError, MarketDataAPIError:
            return None

    async def _fetch_from_finnhub(
        self, ticker: str, target_date: date
    ) -> MarketData | None:
        """Fetch data from Finnhub."""
        from datetime import datetime

        if not self._finnhub_key:
            logger.warning("[Finnhub] No API key configured")
            return None

        start_ts = int(datetime.combine(target_date, datetime.min.time()).timestamp())
        end_ts = start_ts + 86400
        url = f"{self.FINNHUB_BASE_URL}/stock/candle"
        params: dict[str, str | int] = {
            "symbol": ticker,
            "resolution": "D",
            "from": start_ts,
            "to": end_ts,
            "token": self._finnhub_key,
        }

        logger.info(f"[Finnhub] Fetching {ticker} for {target_date}")
        try:
            response = await self._client.get(url, params=params)
            if response.status_code == 429:
                logger.warning("[Finnhub] Rate limited (429)")
                return None
            response.raise_for_status()
            data = response.json()
            ohlcv = transform_finnhub(data, target_date.strftime("%Y-%m-%d"))
            return MarketData(**ohlcv)
        except (httpx.HTTPError, RetryableHTTPError) as exc:
            logger.warning(f"[Finnhub] Request failed: {exc}")
            return None
        except MarketDataParseError:
            return None

    async def fetch(
        self,
        ticker: str,
        target_date: date | None = None,
    ) -> MarketData:
        """Fetch market data for a ticker, with fallback across providers.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL").
            target_date: Target date for data. Defaults to today.
                       Auto-adjusts to previous trading day if weekend/holiday.

        Returns:
            MarketData object with OHLCV data.

        Raises:
            MarketDataUnavailableError: If all providers fail.
        """
        if target_date is None:
            target_date = date.today()

        adjusted_date = self._adjust_to_trading_day(target_date)

        providers = [
            ("Yahoo Finance", self._fetch_from_yahoo),
            ("Alpha Vantage", self._fetch_from_alpha_vantage),
            ("Finnhub", self._fetch_from_finnhub),
        ]

        errors: list[str] = []
        for provider_name, fetch_func in providers:
            try:
                result = await fetch_func(ticker, adjusted_date)
                if result is not None:
                    logger.info(f"[{provider_name}] Success for {ticker}")
                    return result
            except MarketDataError as exc:
                errors.append(f"{provider_name}: {exc}")
                logger.warning(f"[{provider_name}] Error: {exc}")

        all_providers = ", ".join([p[0] for p in providers])
        error_summary = "; ".join(errors) if errors else "Unknown error"
        raise MarketDataUnavailableError(
            f"All providers failed for {ticker} on {adjusted_date}. "
            f"Providers tried: {all_providers}. Last errors: {error_summary}"
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.close()

    async def __aenter__(self) -> "MarketDataCollector":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()


async def fetch_market_data(
    ticker: str,
    target_date: date | None = None,
) -> MarketData:
    """Convenience function to fetch market data.

    Args:
        ticker: Stock ticker symbol.
        target_date: Target date, defaults to today.

    Returns:
        MarketData with OHLCV data.

    Raises:
        MarketDataUnavailableError: If all providers fail.
    """
    async with MarketDataCollector() as collector:
        return await collector.fetch(ticker, target_date)
