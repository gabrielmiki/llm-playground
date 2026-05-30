"""Test fixtures for graceful degradation tests.

All fixtures construct FusedRecord objects directly — no mocking needed.
Fixtures provide pre-built records for multiple dates and a helper to
write them to a temporary directory for testing find_historical_fallback().
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta

import pytest

from src.collect.market_data import MarketData
from src.preprocess.fusion import FusedRecord
from src.preprocess.validator import ValidationWarning

_TODAY = date(2026, 5, 22)  # Friday


@pytest.fixture
def fused_record_today() -> FusedRecord:
    """Valid FusedRecord for 2026-05-22 with market data + news articles."""
    return FusedRecord(
        ticker="AAPL",
        date=_TODAY.isoformat(),
        market_data=MarketData(
            open=306.12,
            high=311.40,
            low=305.84,
            close=308.82,
            volume=43670223,
            adjusted_close=None,
            timestamp="2026-05-22T00:00:00+00:00",
        ),
        news_articles=[
            {"title": "Test Article 1", "source": "TestSource",
             "published_at": "2026-05-22T10:00:00+00:00",
             "url": "https://example.com/1", "summary": "Summary 1"},
            {"title": "Test Article 2", "source": "TestSource",
             "published_at": "2026-05-22T11:00:00+00:00",
             "url": "https://example.com/2", "summary": "Summary 2"},
        ],
        warnings=[
            ValidationWarning("info", "test", "Test warning", value="test"),
        ],
    )


@pytest.fixture
def fused_record_yesterday() -> FusedRecord:
    """Valid FusedRecord for 2026-05-21 (Thursday) — fallback candidate."""
    return FusedRecord(
        ticker="AAPL",
        date=(_TODAY - timedelta(days=1)).isoformat(),
        market_data=MarketData(
            open=305.00,
            high=310.00,
            low=304.00,
            close=306.50,
            volume=40000000,
            adjusted_close=None,
            timestamp="2026-05-21T00:00:00+00:00",
        ),
        news_articles=[
            {"title": "Yesterday News", "source": "TestSource",
             "published_at": "2026-05-21T10:00:00+00:00",
             "url": "https://example.com/y", "summary": "Older summary"},
        ],
        warnings=[],
    )


@pytest.fixture
def fused_record_two_days_ago() -> FusedRecord:
    """Valid FusedRecord for 2026-05-20 (Wednesday) — deeper fallback."""
    return FusedRecord(
        ticker="AAPL",
        date=(_TODAY - timedelta(days=2)).isoformat(),
        market_data=MarketData(
            open=304.00,
            high=308.00,
            low=302.00,
            close=305.00,
            volume=38000000,
            adjusted_close=None,
            timestamp="2026-05-20T00:00:00+00:00",
        ),
        news_articles=[
            {"title": "Older News", "source": "TestSource",
             "published_at": "2026-05-20T10:00:00+00:00",
             "url": "https://example.com/o", "summary": "Older summary"},
        ],
        warnings=[],
    )


@pytest.fixture
def fused_record_no_market() -> FusedRecord:
    """FusedRecord with market_data=None — invalid fallback for market."""
    return FusedRecord(
        ticker="AAPL",
        date=(_TODAY - timedelta(days=1)).isoformat(),
        market_data=None,
        news_articles=[
            {"title": "News with no market data", "source": "TestSource",
             "published_at": "2026-05-21T10:00:00+00:00",
             "url": "https://example.com/nm", "summary": "No market summary"},
        ],
        warnings=[],
    )


@pytest.fixture
def fused_record_no_news() -> FusedRecord:
    """FusedRecord with empty news_articles — invalid fallback for news."""
    return FusedRecord(
        ticker="AAPL",
        date=(_TODAY - timedelta(days=1)).isoformat(),
        market_data=MarketData(
            open=305.00,
            high=310.00,
            low=304.00,
            close=306.50,
            volume=40000000,
            adjusted_close=None,
            timestamp="2026-05-21T00:00:00+00:00",
        ),
        news_articles=[],
        warnings=[],
    )


def _fused_to_dict(record: FusedRecord) -> dict:
    """Serialize a FusedRecord to a dict matching FusedRecordWriter's format."""
    md = None
    if record.market_data is not None:
        md = {
            "open": record.market_data.open,
            "high": record.market_data.high,
            "low": record.market_data.low,
            "close": record.market_data.close,
            "volume": record.market_data.volume,
            "adjusted_close": record.market_data.adjusted_close,
            "timestamp": record.market_data.timestamp,
        }
    return {
        "ticker": record.ticker,
        "date": record.date,
        "market_data": md,
        "news_articles": record.news_articles,
        "warnings": [
            {"category": w.category, "field": w.field,
             "message": w.message, "value": w.value}
            for w in record.warnings
        ],
    }


def write_fused_records(
    records: dict[str, FusedRecord],
    directory: str,
) -> None:
    """Write multiple FusedRecords to a directory as JSON files.

    Args:
        records: Mapping of ``{date_str: FusedRecord}``.
        directory: Target directory (will be created if missing).
    """
    os.makedirs(directory, exist_ok=True)
    for date_str, record in records.items():
        path = os.path.join(directory, f"{record.ticker}_{date_str}.json")
        with open(path, "w") as f:
            json.dump(_fused_to_dict(record), f, indent=2)
