"""Tests for news data collection and transformation."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.collect.news_collector import (
    NewsCollector,
    fetch_news,
    _get_weekday_adjustment,
)
from src.collect.news_transformers import (
    transform_finnhub_news,
    transform_newsapi,
)
from src.collect.exceptions import (
    NewsDataError,
    NewsDataParseError,
    NewsDataAPIError,
    NewsDataUnavailableError,
)


class TestWeekdayAdjustment:
    """Tests for date adjustment logic."""

    def test_saturday_adjusts_to_friday(self):
        """Given Saturday date, When adjusted, Then returns previous Friday."""
        result = _get_weekday_adjustment("2024-01-13")
        assert result == "2024-01-12"

    def test_sunday_adjusts_to_friday(self):
        """Given Sunday date, When adjusted, Then returns previous Friday."""
        result = _get_weekday_adjustment("2024-01-14")
        assert result == "2024-01-12"

    def test_weekday_returns_same(self):
        """Given weekday date, When adjusted, Then returns same date."""
        result = _get_weekday_adjustment("2024-01-15")
        assert result == "2024-01-15"


class TestFinnhubTransformer:
    """Tests for Finnhub news transformation."""

    def test_valid_response(
        self,
        finnhub_response_valid: list[dict],
    ):
        """Given valid Finnhub response, When transformed, Then returns normalized articles."""
        articles = transform_finnhub_news(finnhub_response_valid, "2024-01-15")

        assert len(articles) == 2
        assert articles[0]["title"] == "Apple Reports Record Q4 Earnings"
        assert articles[0]["source"] == "Reuters"
        assert articles[0]["url"] == "https://example.com/article"

    def test_empty_response(
        self,
        finnhub_response_empty: list[dict],
    ):
        """Given empty Finnhub response, When transformed, Then returns empty list."""
        articles = transform_finnhub_news(finnhub_response_empty, "2024-01-15")

        assert articles == []

    def test_invalid_response_format(self):
        """Given invalid format (not list), When transformed, Then raises parse error."""
        with pytest.raises(NewsDataParseError):
            transform_finnhub_news({"error": "invalid"}, "2024-01-15")

    def test_old_articles_filtered(
        self,
        finnhub_response_with_old_articles: list[dict],
    ):
        """Given articles older than 365 days, When transformed, Then filtered out."""
        articles = transform_finnhub_news(
            finnhub_response_with_old_articles,
            "2024-01-15",
            max_age_days=365,
        )

        assert len(articles) == 1
        assert articles[0]["title"] == "Recent Apple News"


class TestNewsAPITransformer:
    """Tests for NewsAPI transformation."""

    def test_valid_response(
        self,
        newsapi_response_valid: dict,
    ):
        """Given valid NewsAPI response, When transformed, Then returns normalized articles."""
        articles = transform_newsapi(newsapi_response_valid, "2024-01-15")

        assert len(articles) == 2
        assert articles[0]["title"] == "Apple Reports Record Q4 Earnings"
        assert articles[0]["source"] == "Reuters"

    def test_empty_response(
        self,
        newsapi_response_empty: dict,
    ):
        """Given empty NewsAPI response, When transformed, Then returns empty list."""
        articles = transform_newsapi(newsapi_response_empty, "2024-01-15")

        assert articles == []

    def test_error_response(
        self,
        newsapi_response_error: dict,
    ):
        """Given error response from NewsAPI, When transformed, Then raises API error."""
        with pytest.raises(NewsDataAPIError):
            transform_newsapi(newsapi_response_error, "2024-01-15")

    def test_old_articles_filtered(
        self,
        newsapi_response_with_old_articles: dict,
    ):
        """Given articles older than 365 days, When transformed, Then filtered out."""
        articles = transform_newsapi(
            newsapi_response_with_old_articles,
            "2024-01-15",
            max_age_days=365,
        )

        assert len(articles) == 1


class TestNewsCollectorIntegration:
    """Integration tests for NewsCollector with mocked HTTP client."""

    @pytest.mark.asyncio
    async def test_finnhub_fallback_to_newsapi(self):
        """Given Finnhub fails but NewsAPI succeeds, When fetched, Then returns from NewsAPI."""
        mock_client = AsyncMock()

        newsapi_response = {
            "status": "ok",
            "articles": [
                {
                    "source": {"name": "Reuters"},
                    "title": "Success",
                    "url": "https://x.com",
                    "publishedAt": "2024-01-15T10:30:00Z",
                    "description": "Test",
                }
            ],
        }

        async def mock_get(url, params=None):
            if "finnhub" in url:
                response = MagicMock()
                response.status_code = 429
                raise Exception("Rate limited")

            response = MagicMock()
            response.status_code = 200
            response.json = lambda: newsapi_response
            return response

        mock_client.get = mock_get
        mock_client.close = AsyncMock()

        collector = NewsCollector(http_client=mock_client)
        articles = await collector.fetch_news("AAPL", "2024-01-15")

        assert len(articles) == 1
        assert articles[0]["title"] == "Success"

    @pytest.mark.asyncio
    async def test_all_providers_fail_raises_unavailable(self):
        """Given all providers fail, When fetched, Then raises unavailable error."""
        mock_client = AsyncMock()

        async def mock_get(url, params=None):
            raise NewsDataError("API failure")

        mock_client.get = mock_get
        mock_client.close = AsyncMock()

        collector = NewsCollector(http_client=mock_client)

        with pytest.raises(NewsDataUnavailableError):
            await collector.fetch_news("AAPL", "2024-01-15")

    @pytest.mark.asyncio
    async def test_empty_result_returns_empty_list(self):
        """Given provider returns empty, When fetched, Then returns empty list not error."""
        mock_client = AsyncMock()

        async def mock_get(url, params=None):
            response = MagicMock()
            response.status_code = 200
            response.json = lambda: []
            return response

        mock_client.get = mock_get
        mock_client.close = AsyncMock()

        collector = NewsCollector(http_client=mock_client)
        articles = await collector.fetch_news("AAPL", "2024-01-15")

        assert articles == []


class TestFetchNews:
    """Tests for convenience fetch_news function."""

    @pytest.mark.asyncio
    async def test_creates_and_closes_client(self):
        """Given call, When completes, Then client is properly closed."""
        with patch("src.collect.news_collector.NewsCollector") as MockCollector:
            mock_collector = AsyncMock()
            mock_collector.fetch_news = AsyncMock(return_value=[])
            mock_collector.close = AsyncMock()
            MockCollector.return_value.__aenter__ = AsyncMock(
                return_value=mock_collector
            )
            MockCollector.return_value.__aexit__ = AsyncMock()

            await fetch_news("AAPL", "2024-01-15")

            mock_collector.close.assert_called_once()
