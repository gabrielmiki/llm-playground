"""Test fixtures for trading signal generation tests.

All fixtures use direct dataclass construction — no mocking needed.
"""

from __future__ import annotations

import pytest

from src.collect.market_data import MarketData
from src.model.pretrained.sentiment import SentimentResult


@pytest.fixture
def sample_sentiment_result_positive() -> SentimentResult:
    """SentimentResult with moderate positive score and high confidence."""
    return SentimentResult(
        sentiment_score=+0.7,
        confidence=0.8,
        breakdown=[],
    )


@pytest.fixture
def sample_sentiment_result_strong_positive() -> SentimentResult:
    """SentimentResult with strong positive score and high confidence."""
    return SentimentResult(
        sentiment_score=+0.9,
        confidence=0.8,
        breakdown=[],
    )


@pytest.fixture
def sample_sentiment_result_negative() -> SentimentResult:
    """SentimentResult with strong negative score and high confidence."""
    return SentimentResult(
        sentiment_score=-0.6,
        confidence=0.8,
        breakdown=[],
    )


@pytest.fixture
def sample_sentiment_result_neutral() -> SentimentResult:
    """SentimentResult with near-neutral score and low confidence."""
    return SentimentResult(
        sentiment_score=+0.05,
        confidence=0.4,
        breakdown=[],
    )


@pytest.fixture
def sample_sentiment_result_low_confidence() -> SentimentResult:
    """SentimentResult with high score but low confidence."""
    return SentimentResult(
        sentiment_score=+0.8,
        confidence=0.2,
        breakdown=[],
    )


@pytest.fixture
def sample_sentiment_result_very_low_confidence() -> SentimentResult:
    """SentimentResult with score but confidence below threshold (0.25 < 0.3)."""
    return SentimentResult(
        sentiment_score=+0.7,
        confidence=0.25,
        breakdown=[],
    )


@pytest.fixture
def sample_market_data_up() -> MarketData:
    """MarketData with +5% daily return (close > open)."""
    return MarketData(
        open=100.0,
        high=107.0,
        low=99.0,
        close=105.0,
        volume=1000000,
        adjusted_close=105.0,
        timestamp="2024-01-15T00:00:00+00:00",
    )


@pytest.fixture
def sample_market_data_down() -> MarketData:
    """MarketData with -3% daily return (close < open)."""
    return MarketData(
        open=100.0,
        high=101.0,
        low=96.0,
        close=97.0,
        volume=1000000,
        adjusted_close=97.0,
        timestamp="2024-01-15T00:00:00+00:00",
    )


@pytest.fixture
def sample_market_data_down_five() -> MarketData:
    """MarketData with -5% daily return for disagreement test."""
    return MarketData(
        open=100.0,
        high=101.0,
        low=94.0,
        close=95.0,
        volume=1000000,
        adjusted_close=95.0,
        timestamp="2024-01-15T00:00:00+00:00",
    )


@pytest.fixture
def sample_market_data_flat() -> MarketData:
    """MarketData with 0% daily return (close == open)."""
    return MarketData(
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1000000,
        adjusted_close=100.0,
        timestamp="2024-01-15T00:00:00+00:00",
    )


@pytest.fixture
def sample_market_data_zero_open() -> MarketData:
    """MarketData with open=0.0 to test division-by-zero guard."""
    return MarketData(
        open=0.0,
        high=1.0,
        low=0.0,
        close=1.0,
        volume=1000000,
        adjusted_close=1.0,
        timestamp="2024-01-15T00:00:00+00:00",
    )
