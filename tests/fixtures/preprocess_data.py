"""Test fixtures for preprocessing data quality and fusion."""

from __future__ import annotations

import pytest

from src.collect.market_data import MarketData


@pytest.fixture
def clean_text() -> str:
    """Clean English text with no encoding or whitespace issues."""
    return (
        "Apple Inc. reported record quarterly earnings, "
        "driven by strong iPhone sales and services growth."
    )


@pytest.fixture
def dirty_text() -> str:
    """Text with mojibake encoding issues (em-dash and right single quote)."""
    return "Appleâ€™s new iPhoneâ€”released last weekâ€”is selling well."


@pytest.fixture
def mixed_language_text() -> str:
    """Mixed English and Portuguese text."""
    return (
        "The company reported strong results. "
        "A empresa reportou resultados fortes. "
        "Investors are optimistic about the future."
    )


@pytest.fixture
def garbled_text() -> str:
    """Text with >50% non-alphabetic characters (garbled)."""
    return "!!! 123 $$$ %% 456 @@@ ###"


@pytest.fixture
def valid_market_data() -> MarketData:
    """Valid MarketData for a trading day."""
    return MarketData(
        open=150.0,
        high=155.0,
        low=148.0,
        close=153.0,
        volume=50000000,
        adjusted_close=152.5,
        timestamp="2024-01-15",
    )


@pytest.fixture
def invalid_market_data_open_zero() -> MarketData:
    """Invalid MarketData with open=0.0."""
    return MarketData(
        open=0.0,
        high=155.0,
        low=148.0,
        close=153.0,
        volume=50000000,
        adjusted_close=152.5,
        timestamp="2024-01-15",
    )


@pytest.fixture
def invalid_market_data_inverted() -> MarketData:
    """Invalid MarketData with high < low (inverted range)."""
    return MarketData(
        open=150.0,
        high=140.0,
        low=155.0,
        close=153.0,
        volume=50000000,
        adjusted_close=152.5,
        timestamp="2024-01-15",
    )


@pytest.fixture
def invalid_market_data_negative_volume() -> MarketData:
    """Invalid MarketData with negative volume."""
    return MarketData(
        open=150.0,
        high=155.0,
        low=148.0,
        close=153.0,
        volume=-500,
        adjusted_close=152.5,
        timestamp="2024-01-15",
    )


@pytest.fixture
def valid_news_article() -> dict:
    """Valid news article dict with all required fields."""
    return {
        "title": "Apple Reports Record Quarterly Earnings",
        "source": "Reuters",
        "published_at": "2024-01-15T10:30:00+00:00",
        "url": "https://example.com/article",
        "summary": "Apple Inc. announced record quarterly earnings with strong iPhone sales.",
    }


@pytest.fixture
def invalid_news_article_empty_title() -> dict:
    """Invalid news article with empty title."""
    return {
        "title": "",
        "source": "Reuters",
        "published_at": "2024-01-15T10:30:00+00:00",
        "url": "https://example.com/article",
        "summary": "Apple Inc. announced record quarterly earnings.",
    }


@pytest.fixture
def texts_for_stopword() -> list[str]:
    """Texts for testing stopword removal."""
    return [
        "The quick brown fox jumps over the lazy dog",
        "A quick brown fox jumps over a lazy dog",
        "Quick brown fox jumps lazy dog",
    ]


@pytest.fixture
def texts_for_nltk() -> list[str]:
    """Texts for testing NLTK sentence tokenization."""
    return [
        "Hello world. This is a test sentence. And another one.",
        "Short text.",
    ]
