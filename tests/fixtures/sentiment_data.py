"""Test fixtures for sentiment analysis tests."""

from __future__ import annotations

import pytest

from src.preprocess.fusion import FusedRecord


@pytest.fixture
def sample_fused_record_single_article() -> FusedRecord:
    """FusedRecord with 1 positive financial news article."""
    return FusedRecord(
        ticker="AAPL",
        date="2024-01-15",
        market_data=None,
        news_articles=[
            {
                "title": "Apple Reports Strong Earnings",
                "summary": "Apple Inc. announced record quarterly revenue exceeding analyst expectations.",
                "source": "Reuters",
                "published_at": "2024-01-15T10:30:00+00:00",
                "url": "https://example.com/article1",
            },
        ],
    )


@pytest.fixture
def sample_fused_record_multi_article() -> FusedRecord:
    """FusedRecord with 3 mixed-sentiment articles."""
    return FusedRecord(
        ticker="AAPL",
        date="2024-01-15",
        market_data=None,
        news_articles=[
            {
                "title": "Apple Reports Strong Earnings",
                "summary": "Record revenue and profit growth driven by iPhone sales.",
                "source": "Reuters",
                "published_at": "2024-01-15T10:30:00+00:00",
                "url": "https://example.com/1",
            },
            {
                "title": "Apple Faces Regulatory Scrutiny",
                "summary": "EU regulators investigating App Store practices.",
                "source": "Bloomberg",
                "published_at": "2024-01-15T11:00:00+00:00",
                "url": "https://example.com/2",
            },
            {
                "title": "Apple Supply Chain Update",
                "summary": "Supplier production targets remain unchanged.",
                "source": "CNBC",
                "published_at": "2024-01-15T12:00:00+00:00",
                "url": "https://example.com/3",
            },
        ],
    )


@pytest.fixture
def sample_fused_record_empty_articles() -> FusedRecord:
    """FusedRecord with no articles (empty list)."""
    return FusedRecord(
        ticker="AAPL",
        date="2024-01-15",
        market_data=None,
        news_articles=[],
    )


@pytest.fixture
def sample_fused_record_blank_article() -> FusedRecord:
    """FusedRecord with an article that has empty title and whitespace summary."""
    return FusedRecord(
        ticker="AAPL",
        date="2024-01-15",
        market_data=None,
        news_articles=[
            {"title": "", "summary": "   "},
        ],
    )


@pytest.fixture
def sample_fused_record_missing_title() -> FusedRecord:
    """FusedRecord with an article missing the 'title' key."""
    return FusedRecord(
        ticker="AAPL",
        date="2024-01-15",
        market_data=None,
        news_articles=[
            {
                "summary": "Apple announced a new product.",
                "source": "Reuters",
                "published_at": "2024-01-15T10:30:00+00:00",
                "url": "https://example.com/1",
            },
        ],
    )


@pytest.fixture
def sample_fused_record_long_text() -> FusedRecord:
    """FusedRecord with article text exceeding BERT's 512-token max_length."""
    return FusedRecord(
        ticker="AAPL",
        date="2024-01-15",
        market_data=None,
        news_articles=[
            {
                "title": "Very Long Article",
                "summary": "word " * 2000,
                "source": "Reuters",
                "published_at": "2024-01-15T10:30:00+00:00",
                "url": "https://example.com/1",
            },
        ],
    )
