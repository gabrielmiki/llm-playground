"""Tests for DataFusionEngine."""

from __future__ import annotations

from src.collect.market_data import MarketData
from src.preprocess.fusion import DataFusionEngine


class TestDataFusionEngine:
    """Tests for DataFusionEngine covering correlation, edge cases, and streaming."""

    def test_fuse_matching_articles_included(self, valid_market_data: MarketData):
        engine = DataFusionEngine()
        articles = [
            {"title": "News 1", "published_at": "2024-01-15T10:00:00+00:00"},
            {"title": "News 2", "published_at": "2024-01-15T14:00:00+00:00"},
        ]
        result = engine.fuse("AAPL", "2024-01-15", valid_market_data, articles)
        assert result.ticker == "AAPL"
        assert result.date == "2024-01-15"
        assert result.market_data == valid_market_data
        assert len(result.news_articles) == 2

    def test_fuse_non_matching_articles_dropped(self, valid_market_data: MarketData):
        engine = DataFusionEngine()
        articles = [
            {"title": "Match", "published_at": "2024-01-15T10:00:00+00:00"},
            {"title": "Different Date", "published_at": "2024-01-16T10:00:00+00:00"},
            {"title": "Another Match", "published_at": "2024-01-15T14:00:00+00:00"},
            {"title": "Far Date", "published_at": "2024-01-20T10:00:00+00:00"},
        ]
        result = engine.fuse("AAPL", "2024-01-15", valid_market_data, articles)
        assert len(result.news_articles) == 2
        assert result.news_articles[0]["title"] == "Match"
        assert result.news_articles[1]["title"] == "Another Match"

    def test_fuse_no_market_data(self):
        engine = DataFusionEngine()
        articles = [
            {"title": "News", "published_at": "2024-01-15T10:00:00+00:00"},
        ]
        result = engine.fuse("AAPL", "2024-01-15", None, articles)
        assert result.market_data is None
        assert len(result.warnings) == 1
        assert result.warnings[0].category == "missing_market_data"

    def test_fuse_empty_articles_valid_market_data(self, valid_market_data: MarketData):
        engine = DataFusionEngine()
        result = engine.fuse("AAPL", "2024-01-15", valid_market_data, [])
        assert result.market_data == valid_market_data
        assert result.news_articles == []

    def test_fuse_article_with_no_date(self, valid_market_data: MarketData):
        engine = DataFusionEngine()
        articles = [
            {"title": "No Date", "published_at": ""},
            {"title": "Valid Date", "published_at": "2024-01-15T10:00:00+00:00"},
        ]
        result = engine.fuse("AAPL", "2024-01-15", valid_market_data, articles)
        assert len(result.news_articles) == 1
        assert result.news_articles[0]["title"] == "Valid Date"

    def test_fuse_non_dict_article_ignored(self, valid_market_data: MarketData):
        engine = DataFusionEngine()
        articles: list = [
            None,
            "string instead of dict",
            {"title": "Valid", "published_at": "2024-01-15T10:00:00+00:00"},
        ]
        result = engine.fuse("AAPL", "2024-01-15", valid_market_data, articles)
        assert len(result.news_articles) == 1
        assert result.news_articles[0]["title"] == "Valid"

    def test_fuse_all_returns_fusion_result(self, valid_market_data: MarketData):
        engine = DataFusionEngine()
        records = [
            ("AAPL", "2024-01-15", valid_market_data, [{"title": "N1", "published_at": "2024-01-15T00:00:00+00:00"}]),
            ("MSFT", "2024-01-15", None, [{"title": "N2", "published_at": "2024-01-15T00:00:00+00:00"}]),
        ]
        result = engine.fuse_all(records)
        assert len(result.records) == 2
        assert len(result.fusion_warnings) == 1
        assert result.fusion_warnings[0].category == "missing_market_data"

    def test_fuse_many_streaming(self, tracking_iterable):
        engine = DataFusionEngine()
        TrackingIterable = tracking_iterable

        records = [
            ("AAPL", "2024-01-15", None, []),
            ("MSFT", "2024-01-15", None, []),
            ("GOOG", "2024-01-15", None, []),
            ("AMZN", "2024-01-15", None, []),
            ("TSLA", "2024-01-15", None, []),
        ]
        tracking = TrackingIterable(records)
        gen = engine.fuse_many(tracking)
        assert tracking.call_count == 0
        next(gen)
        assert tracking.call_count == 1
        all_results = list(gen)
        assert len(all_results) == 4
        assert tracking.call_count == 5
