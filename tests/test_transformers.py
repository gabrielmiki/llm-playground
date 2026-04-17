"""Tests for market data transformers."""

from __future__ import annotations

import pytest

from src.collect.exceptions import MarketDataAPIError, MarketDataParseError
from src.collect.transformers import (
    transform_alpha_vantage,
    transform_finnhub,
    transform_yahoo_finance,
)


class TestTransformYahooFinance:
    """Tests for Yahoo Finance response transformation."""

    def test_transform_yahoo_valid_response(
        self,
        yahoo_response_valid: dict,
        expected_ohlcv: dict,
    ) -> None:
        """AC-1: Valid Yahoo Finance response returns normalized OHLCV."""
        result = transform_yahoo_finance(yahoo_response_valid, "2024-01-15")
        assert result["open"] == pytest.approx(expected_ohlcv["open"])
        assert result["high"] == pytest.approx(expected_ohlcv["high"])
        assert result["low"] == pytest.approx(expected_ohlcv["low"])
        assert result["close"] == pytest.approx(expected_ohlcv["close"])
        assert result["volume"] == expected_ohlcv["volume"]
        assert result["timestamp"] == expected_ohlcv["timestamp"]

    def test_transform_yahoo_missing_close(
        self, yahoo_response_missing_close: dict
    ) -> None:
        """AC-3: Missing 'close' field raises MarketDataParseError."""
        with pytest.raises(MarketDataParseError, match="Missing required field"):
            transform_yahoo_finance(yahoo_response_missing_close, "2024-01-15")

    def test_transform_yahoo_empty_result(
        self, yahoo_response_empty_result: dict
    ) -> None:
        """Yahoo Finance empty result raises MarketDataParseError."""
        with pytest.raises(MarketDataParseError, match="empty result"):
            transform_yahoo_finance(yahoo_response_empty_result, "2024-01-15")

    def test_transform_yahoo_no_timestamp(
        self, yahoo_response_no_timestamp: dict
    ) -> None:
        """Yahoo Finance no timestamp raises MarketDataParseError."""
        with pytest.raises(MarketDataParseError, match="no timestamp"):
            transform_yahoo_finance(yahoo_response_no_timestamp, "2024-01-15")

    def test_transform_yahoo_invalid_structure(self) -> None:
        """Yahoo Finance invalid structure raises MarketDataParseError."""
        with pytest.raises(MarketDataParseError, match="missing 'chart.result'"):
            transform_yahoo_finance({"error": "test"}, "2024-01-15")


class TestTransformAlphaVantage:
    """Tests for Alpha Vantage response transformation."""

    def test_transform_alpha_vantage_valid_response(
        self,
        alpha_vantage_response_valid: dict,
    ) -> None:
        """AC-1: Valid Alpha Vantage response returns normalized OHLCV."""
        result = transform_alpha_vantage(alpha_vantage_response_valid, "2024-01-15")
        assert result["open"] == pytest.approx(185.50)
        assert result["high"] == pytest.approx(187.20)
        assert result["low"] == pytest.approx(184.80)
        assert result["close"] == pytest.approx(185.50)
        assert result["volume"] == 45000000
        assert result["timestamp"] == "2024-01-15T00:00:00+00:00"

    def test_transform_alpha_vantage_with_adjusted_close(
        self,
        alpha_vantage_response_with_adjusted_close: dict,
    ) -> None:
        """Alpha Vantage with adjusted close is parsed correctly."""
        result = transform_alpha_vantage(
            alpha_vantage_response_with_adjusted_close, "2024-01-15"
        )
        assert result["adjusted_close"] == pytest.approx(185.25)

    def test_transform_alpha_vantage_api_error(
        self,
        alpha_vantage_response_error: dict,
    ) -> None:
        """AC-4: Alpha Vantage API error raises MarketDataAPIError."""
        with pytest.raises(MarketDataAPIError, match="Invalid API call"):
            transform_alpha_vantage(alpha_vantage_response_error, "2024-01-15")

    def test_transform_alpha_vantage_rate_limit(
        self,
        alpha_vantage_response_rate_limit: dict,
    ) -> None:
        """AC-4: Alpha Vantage rate limit raises MarketDataAPIError."""
        with pytest.raises(
            MarketDataAPIError, match="Thank you for using Alpha Vantage"
        ):
            transform_alpha_vantage(alpha_vantage_response_rate_limit, "2024-01-15")

    def test_transform_alpha_vantage_missing_series(
        self,
        alpha_vantage_response_missing_series: dict,
    ) -> None:
        """Alpha Vantage missing time series raises MarketDataParseError."""
        with pytest.raises(MarketDataParseError, match="missing 'Time Series"):
            transform_alpha_vantage(alpha_vantage_response_missing_series, "2024-01-15")


class TestTransformFinnhub:
    """Tests for Finnhub response transformation."""

    def test_transform_finnhub_valid_response(
        self,
        finnhub_response_valid: dict,
    ) -> None:
        """AC-1: Valid Finnhub response returns normalized OHLCV."""
        result = transform_finnhub(finnhub_response_valid, "2024-01-15")
        assert result["open"] == pytest.approx(185.50)
        assert result["high"] == pytest.approx(187.20)
        assert result["low"] == pytest.approx(184.80)
        assert result["close"] == pytest.approx(185.50)
        assert result["volume"] == 45000000
        assert result["timestamp"] == "2024-01-15T00:00:00+00:00"

    def test_transform_finnhub_no_data(self, finnhub_response_no_data: dict) -> None:
        """Finnhub no data raises MarketDataParseError."""
        with pytest.raises(MarketDataParseError, match="no data"):
            transform_finnhub(finnhub_response_no_data, "2024-01-15")

    def test_transform_finnhub_missing_fields(
        self,
        finnhub_response_missing_fields: dict,
    ) -> None:
        """Finnhub missing required fields raises MarketDataParseError."""
        with pytest.raises(MarketDataParseError, match="missing required field"):
            transform_finnhub(finnhub_response_missing_fields, "2024-01-15")
