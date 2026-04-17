"""News data collector with fallback chain for Finnhub and NewsAPI."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

import httpx

from src.collect.client import RetryableHTTPClient, RetryConfig
from src.collect.exceptions import (
    NewsDataError,
    NewsDataParseError,
    NewsDataUnavailableError,
)
from src.collect.news_transformers import (
    NewsArticle,
    transform_finnhub_news,
    transform_newsapi,
)

logger = logging.getLogger(__name__)

# Load environment variables before other imports that need them
from dotenv import load_dotenv  # noqa: E402

load_dotenv()  # noqa: E402

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
NEWSAPI_BASE_URL = "https://newsapi.org/v2"

DEFAULT_MAX_AGE_DAYS = 365


def _get_weekday_adjustment(target_date: str) -> str:
    """Adjust date if it falls on weekend or holiday.

    Args:
        target_date: Date string in YYYY-MM-DD format.

    Returns:
        Adjusted date string in YYYY-MM-DD format.
    """
    dt = datetime.strptime(target_date, "%Y-%m-%d")

    if dt.weekday() == 5:
        adjusted = dt - timedelta(days=1)
        logger.info(
            f"Date {target_date} is Saturday, adjusted to {adjusted.strftime('%Y-%m-%d')}"
        )
    elif dt.weekday() == 6:
        adjusted = dt - timedelta(days=2)
        logger.info(
            f"Date {target_date} is Sunday, adjusted to {adjusted.strftime('%Y-%m-%d')}"
        )
    else:
        adjusted = dt

    return adjusted.strftime("%Y-%m-%d")


class NewsCollector:
    """Collects news data from Finnhub and NewsAPI with fallback chain.

    Implements a fallback chain: Finnhub Company News → NewsAPI Everything → NewsDataUnavailableError

    Example:
        ```python
        async with NewsCollector() as collector:
            articles = await collector.fetch_news("AAPL", "2024-01-15")
            for article in articles:
                print(article["title"])
        ```

    Attributes:
        http_client: HTTP client for making requests.
        max_age_days: Maximum age of articles to include (default: 365).
    """

    def __init__(
        self,
        http_client: RetryableHTTPClient | None = None,
        max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    ) -> None:
        self._http_client = http_client
        self._max_age_days = max_age_days
        self._finnhub_api_key = os.getenv("FINNHUB_API_KEY", "")
        self._newsapi_key = os.getenv("NEWSAPI_KEY", "")

    async def _ensure_client(self) -> RetryableHTTPClient:
        """Lazily initialize the HTTP client."""
        if self._http_client is None:
            from src.collect.rate_limiter import create_finnhub_limiter

            limiter = create_finnhub_limiter()
            retry_config = RetryConfig(max_attempts=3)
            self._http_client = RetryableHTTPClient(
                rate_limiter=limiter,
                retry_config=retry_config,
            )
        return self._http_client

    async def _fetch_finnhub(
        self,
        ticker: str,
        target_date: str,
    ) -> list[NewsArticle]:
        """Fetch news from Finnhub Company News API.

        Args:
            ticker: Stock ticker symbol.
            target_date: Target date in YYYY-MM-DD format.

        Returns:
            List of normalized news articles.

        Raises:
            NewsDataError: On parse error or API error.
            httpx.HTTPError: On HTTP error.
        """
        if not self._finnhub_api_key:
            logger.warning("[Finnhub] API key not configured, skipping")
            raise NewsDataError("FINNHUB_API_KEY not set")

        dt = datetime.strptime(target_date, "%Y-%m-%d")
        from_iso = target_date
        to_iso = dt.strftime("%Y-%m-%d")

        url = f"{FINNHUB_BASE_URL}/company-news"
        params = {
            "symbol": ticker,
            "from": from_iso,
            "to": to_iso,
            "token": self._finnhub_api_key,
        }

        client = await self._ensure_client()
        response = await client.get(url, params=params)

        if response.status_code == 429:
            logger.warning("[Finnhub] Rate limited (429)")
            raise NewsDataError("Rate limited")

        if response.status_code >= 400:
            logger.error(f"[Finnhub] HTTP {response.status_code}")
            raise NewsDataError(f"HTTP {response.status_code}")

        try:
            data = response.json()
        except ValueError as e:
            logger.error(f"[Finnhub] Failed to parse JSON: {e}")
            raise NewsDataParseError(f"Invalid JSON response: {e}")

        return transform_finnhub_news(data, target_date, self._max_age_days)

    async def _fetch_newsapi(
        self,
        ticker: str,
        target_date: str,
    ) -> list[NewsArticle]:
        """Fetch news from NewsAPI Everything endpoint.

        Args:
            ticker: Stock ticker symbol.
            target_date: Target date in YYYY-MM-DD format.

        Returns:
            List of normalized news articles.

        Raises:
            NewsDataError: On API error.
            httpx.HTTPError: On HTTP error.
        """
        if not self._newsapi_key:
            logger.warning("[NewsAPI] API key not configured, skipping")
            raise NewsDataError("NEWSAPI_KEY not set")

        dt = datetime.strptime(target_date, "%Y-%m-%d")
        from_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
        to_date = target_date

        url = f"{NEWSAPI_BASE_URL}/everything"
        params = {
            "q": ticker,
            "from": from_date,
            "to": to_date,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 50,
            "apiKey": self._newsapi_key,
        }

        client = await self._ensure_client()
        response = await client.get(url, params=params)

        if response.status_code == 429:
            logger.warning("[NewsAPI] Rate limited (429)")
            raise NewsDataError("Rate limited")

        if response.status_code >= 400:
            logger.error(f"[NewsAPI] HTTP {response.status_code}")
            raise NewsDataError(f"HTTP {response.status_code}")

        try:
            data = response.json()
        except ValueError as e:
            logger.error(f"[NewsAPI] Failed to parse JSON: {e}")
            raise NewsDataParseError(f"Invalid JSON response: {e}")

        return transform_newsapi(data, target_date, self._max_age_days)

    async def fetch_news(
        self,
        ticker: str,
        target_date: str,
    ) -> list[NewsArticle]:
        """Fetch news articles for a ticker with fallback chain.

        Implements the fallback chain: Finnhub → NewsAPI → Error

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL").
            target_date: Target date in YYYY-MM-DD format.

        Returns:
            List of normalized news articles (may be empty).

        Raises:
            NewsDataUnavailableError: When all providers fail.
        """
        adjusted_date = _get_weekday_adjustment(target_date)
        logger.info(f"Fetching news for {ticker} on {adjusted_date}")

        errors: list[str] = []

        try:
            articles = await self._fetch_finnhub(ticker, adjusted_date)
            if articles:
                logger.info(f"[Finnhub] Retrieved {len(articles)} article(s)")
                return articles
        except NewsDataError as e:
            error_msg = f"Finnhub failed: {e}"
            logger.warning(f"[Fallback] {error_msg}")
            errors.append(error_msg)
        except httpx.HTTPError as e:
            error_msg = f"Finnhub HTTP error: {e}"
            logger.warning(f"[Fallback] {error_msg}")
            errors.append(error_msg)

        try:
            articles = await self._fetch_newsapi(ticker, adjusted_date)
            if articles:
                logger.info(f"[NewsAPI] Retrieved {len(articles)} article(s)")
                return articles
        except NewsDataError as e:
            error_msg = f"NewsAPI failed: {e}"
            logger.warning(f"[Fallback] {error_msg}")
            errors.append(error_msg)
        except httpx.HTTPError as e:
            error_msg = f"NewsAPI HTTP error: {e}"
            logger.warning(f"[Fallback] {error_msg}")
            errors.append(error_msg)

        logger.error(f"All providers exhausted for {ticker}")
        raise NewsDataUnavailableError(
            f"News unavailable for {ticker} on {target_date}. "
            f"Errors: {'; '.join(errors) if errors else 'Unknown'}"
        )

    async def close(self) -> None:
        """Close the collector and release resources."""
        if self._http_client is not None:
            await self._http_client.close()
            self._http_client = None

    async def __aenter__(self) -> "NewsCollector":
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager and close collector."""
        await self.close()


async def fetch_news(
    ticker: str,
    target_date: str,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> list[NewsArticle]:
    """Fetch news articles for a ticker.

    Convenience function that creates and manages a NewsCollector.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL").
        target_date: Target date in YYYY-MM-DD format.
        max_age_days: Maximum age of articles in days (default: 365).

    Returns:
        List of normalized news articles (may be empty).

    Raises:
        NewsDataUnavailableError: When all providers fail.

    Example:
        ```python
        articles = await fetch_news("AAPL", "2024-01-15")
        for article in articles:
            print(article["title"])
        ```
    """
    async with NewsCollector(max_age_days=max_age_days) as collector:
        return await collector.fetch_news(ticker, target_date)
