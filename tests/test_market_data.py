"""Tests for market data collector with fallback support."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.collect.exceptions import MarketDataUnavailableError
from src.collect.market_data import (
    MarketData,
    MarketDataCollector,
)


@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Create a mock HTTP client."""
    return AsyncMock()


@pytest.fixture
def collector(mock_http_client: AsyncMock) -> MarketDataCollector:
    """Create a market data collector with mocked client."""
    return MarketDataCollector(
        http_client=mock_http_client,
        alpha_vantage_key="test_alpha_key",
        finnhub_key="test_finnhub_key",
    )


class TestMarketDataAdjustment:
    """Tests for date adjustment to trading days."""

    def test_adjust_weekday(self) -> None:
        """Weekday dates are not adjusted."""
        collector = MarketDataCollector()
        wed = date(2024, 1, 17)
        assert collector._adjust_to_trading_day(wed) == wed

    def test_adjust_saturday_to_friday(self) -> None:
        """AC-8: Saturday rolls back to Friday."""
        collector = MarketDataCollector()
        saturday = date(2024, 1, 20)
        assert collector._adjust_to_trading_day(saturday) == date(2024, 1, 19)

    def test_adjust_sunday_to_friday(self) -> None:
        """Sunday also rolls back to Friday."""
        collector = MarketDataCollector()
        sunday = date(2024, 1, 21)
        assert collector._adjust_to_trading_day(sunday) == date(2024, 1, 19)

    def test_adjust_holiday_to_previous_day(self) -> None:
        """AC-9: Holiday rolls back to previous trading day."""
        collector = MarketDataCollector()
        holiday = date(2026, 1, 19)
        assert collector._adjust_to_trading_day(holiday) == date(2026, 1, 16)


class TestMarketDataCollector:
    """Tests for MarketDataCollector with provider fallback."""

    @pytest.mark.asyncio
    async def test_fetch_yahoo_success(
        self,
        collector: MarketDataCollector,
        mock_http_client: AsyncMock,
        yahoo_response_valid: dict,
    ) -> None:
        """AC-1: Yahoo Finance success returns market data."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = yahoo_response_valid
        mock_http_client.get = AsyncMock(return_value=mock_response)

        result = await collector.fetch("AAPL", date(2024, 1, 15))

        assert isinstance(result, MarketData)
        assert result.open == pytest.approx(185.50)
        assert result.high == pytest.approx(187.20)
        assert result.close == pytest.approx(185.50)
        assert "timestamp" in result.to_dict()

    @pytest.mark.asyncio
    async def test_fallback_to_alpha_vantage(
        self,
        collector: MarketDataCollector,
        mock_http_client: AsyncMock,
        yahoo_response_valid: dict,
        alpha_vantage_response_valid: dict,
    ) -> None:
        """AC-5: Yahoo 429 triggers fallback to Alpha Vantage."""
        yahoo_429 = MagicMock(spec=httpx.Response)
        yahoo_429.status_code = 429
        yahoo_429.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429", request=MagicMock(), response=yahoo_429
        )

        alpha_response = MagicMock(spec=httpx.Response)
        alpha_response.status_code = 200
        alpha_response.json.return_value = alpha_vantage_response_valid

        mock_http_client.get = AsyncMock(side_effect=[yahoo_429, alpha_response])

        result = await collector.fetch("AAPL", date(2024, 1, 15))

        assert isinstance(result, MarketData)
        assert result.open == pytest.approx(185.50)

    @pytest.mark.asyncio
    async def test_fallback_to_finnhub(
        self,
        collector: MarketDataCollector,
        mock_http_client: AsyncMock,
        alpha_vantage_response_valid: dict,
        finnhub_response_valid: dict,
    ) -> None:
        """AC-6: Yahoo + Alpha Vantage failure triggers fallback to Finnhub."""
        yahoo_429 = MagicMock(spec=httpx.Response)
        yahoo_429.status_code = 429
        yahoo_429.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429", request=MagicMock(), response=yahoo_429
        )

        alpha_error = MagicMock(spec=httpx.Response)
        alpha_error.status_code = 429
        alpha_error.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429", request=MagicMock(), response=alpha_error
        )

        finnhub_response = MagicMock(spec=httpx.Response)
        finnhub_response.status_code = 200
        finnhub_response.json.return_value = finnhub_response_valid

        mock_http_client.get = AsyncMock(
            side_effect=[yahoo_429, alpha_error, finnhub_response]
        )

        result = await collector.fetch("AAPL", date(2024, 1, 15))

        assert isinstance(result, MarketData)
        assert result.close == pytest.approx(185.50)

    @pytest.mark.asyncio
    async def test_all_providers_fail(
        self,
        collector: MarketDataCollector,
        mock_http_client: AsyncMock,
    ) -> None:
        """AC-7: All providers fail raises MarketDataUnavailableError."""
        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 500
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=error_response
        )

        mock_http_client.get = AsyncMock(return_value=error_response)

        with pytest.raises(MarketDataUnavailableError, match="All providers failed"):
            await collector.fetch("AAPL", date(2024, 1, 15))

    @pytest.mark.asyncio
    async def test_parse_error_triggers_fallback(
        self,
        collector: MarketDataCollector,
        mock_http_client: AsyncMock,
        alpha_vantage_response_valid: dict,
    ) -> None:
        """Parse error triggers fallback to next provider."""
        invalid_yahoo = MagicMock(spec=httpx.Response)
        invalid_yahoo.status_code = 200
        invalid_yahoo.json.return_value = {"chart": {"result": []}}

        alpha_response = MagicMock(spec=httpx.Response)
        alpha_response.status_code = 200
        alpha_response.json.return_value = alpha_vantage_response_valid

        mock_http_client.get = AsyncMock(side_effect=[invalid_yahoo, alpha_response])

        result = await collector.fetch("AAPL", date(2024, 1, 15))

        assert isinstance(result, MarketData)

    @pytest.mark.asyncio
    async def test_api_error_triggers_fallback(
        self,
        collector: MarketDataCollector,
        mock_http_client: AsyncMock,
        alpha_vantage_response_valid: dict,
    ) -> None:
        """API error in response body triggers fallback."""
        yahoo_error = MagicMock(spec=httpx.Response)
        yahoo_error.status_code = 200
        yahoo_error.json.return_value = {"Error Message": "Invalid symbol"}

        alpha_response = MagicMock(spec=httpx.Response)
        alpha_response.status_code = 200
        alpha_response.json.return_value = alpha_vantage_response_valid

        mock_http_client.get = AsyncMock(side_effect=[yahoo_error, alpha_response])

        result = await collector.fetch("INVALID", date(2024, 1, 15))

        assert isinstance(result, MarketData)


class TestMarketDataSchema:
    """Tests for MarketData schema."""

    def test_market_data_to_dict(self, expected_ohlcv: dict) -> None:
        """AC-1: MarketData returns correct schema."""
        data = MarketData(**expected_ohlcv)
        result = data.to_dict()

        assert set(result.keys()) == {
            "open",
            "high",
            "low",
            "close",
            "volume",
            "adjusted_close",
            "timestamp",
        }
        assert isinstance(result["open"], float)
        assert isinstance(result["volume"], int)
        assert "T" in result["timestamp"]
