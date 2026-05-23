"""Tests for MarketDataValidator and NewsValidator."""

from __future__ import annotations

from datetime import date, timedelta

from src.collect.market_data import MarketData
from src.preprocess.validator import MarketDataValidator, NewsValidator


class TestMarketDataValidator:
    """Tests for MarketDataValidator covering price, volume, and date validation."""

    def test_validate_valid_market_data(self, valid_market_data: MarketData):
        validator = MarketDataValidator()
        result = validator.validate(valid_market_data)
        assert result.is_valid is True
        assert result.warnings == []

    def test_validate_open_zero(self, invalid_market_data_open_zero: MarketData):
        validator = MarketDataValidator()
        result = validator.validate(invalid_market_data_open_zero)
        assert result.is_valid is False
        categories = [w.category for w in result.warnings]
        assert "invalid_price" in categories

    def test_validate_high_low_inverted(self, invalid_market_data_inverted: MarketData):
        validator = MarketDataValidator()
        result = validator.validate(invalid_market_data_inverted)
        assert result.is_valid is False
        categories = [w.category for w in result.warnings]
        assert "invalid_price_range" in categories

    def test_validate_negative_volume(self, invalid_market_data_negative_volume: MarketData):
        validator = MarketDataValidator()
        result = validator.validate(invalid_market_data_negative_volume)
        assert result.is_valid is False
        categories = [w.category for w in result.warnings]
        assert "invalid_volume" in categories

    def test_validate_negative_adjusted_close(self):
        validator = MarketDataValidator()
        data = MarketData(
            open=150.0, high=155.0, low=148.0, close=153.0,
            volume=50000000, adjusted_close=-1.0, timestamp="2024-01-15",
        )
        result = validator.validate(data)
        assert result.is_valid is False
        categories = [w.category for w in result.warnings]
        assert "invalid_adjusted_close" in categories

    def test_validate_adjusted_close_none_is_valid(self):
        validator = MarketDataValidator()
        data = MarketData(
            open=150.0, high=155.0, low=148.0, close=153.0,
            volume=50000000, adjusted_close=None, timestamp="2024-01-15",
        )
        result = validator.validate(data)
        assert result.is_valid is True

    def test_validate_adjusted_close_zero_invalid(self):
        validator = MarketDataValidator()
        data = MarketData(
            open=150.0, high=155.0, low=148.0, close=153.0,
            volume=50000000, adjusted_close=0.0, timestamp="2024-01-15",
        )
        result = validator.validate(data)
        assert result.is_valid is False
        categories = [w.category for w in result.warnings]
        assert "invalid_adjusted_close" in categories

    def test_validate_future_timestamp(self):
        validator = MarketDataValidator()
        future = (date.today() + timedelta(days=365 * 10)).isoformat()
        data = MarketData(
            open=150.0, high=155.0, low=148.0, close=153.0,
            volume=50000000, adjusted_close=152.5, timestamp=future,
        )
        result = validator.validate(data)
        assert result.is_valid is False
        categories = [w.category for w in result.warnings]
        assert "future_timestamp" in categories

    def test_validate_many_yields_results(self, valid_market_data: MarketData):
        validator = MarketDataValidator()
        invalid = MarketData(
            open=0.0, high=155.0, low=148.0, close=153.0,
            volume=50000000, adjusted_close=152.5, timestamp="2024-01-15",
        )
        results = list(validator.validate_many([valid_market_data, invalid]))
        assert len(results) == 2
        assert results[0].is_valid is True
        assert results[1].is_valid is False

    def test_validate_many_lazy_evaluation(self, valid_market_data, tracking_iterable):
        validator = MarketDataValidator()
        TrackingIterable = tracking_iterable
        records = TrackingIterable([valid_market_data, valid_market_data, valid_market_data])
        gen = validator.validate_many(records)
        assert records.call_count == 0
        next(gen)
        assert records.call_count == 1
        list(gen)
        assert records.call_count == 3


class TestNewsValidator:
    """Tests for NewsValidator covering title, URL, and date validation."""

    def test_validate_valid_article(self, valid_news_article: dict):
        validator = NewsValidator()
        result = validator.validate(valid_news_article)
        assert result.is_valid is True
        assert result.warnings == []

    def test_validate_empty_title(self, invalid_news_article_empty_title: dict):
        validator = NewsValidator()
        result = validator.validate(invalid_news_article_empty_title)
        assert result.is_valid is False
        categories = [w.category for w in result.warnings]
        assert "missing_field" in categories

    def test_validate_title_too_short(self):
        validator = NewsValidator()
        article = {
            "title": "AB",
            "source": "Reuters",
            "published_at": "2024-01-15T10:30:00+00:00",
            "url": "https://example.com/article",
            "summary": "Some summary text here.",
        }
        result = validator.validate(article)
        assert result.is_valid is False
        categories = [w.category for w in result.warnings]
        assert "title_too_short" in categories

    def test_validate_invalid_url(self):
        validator = NewsValidator()
        article = {
            "title": "Valid Title Here",
            "source": "Reuters",
            "published_at": "2024-01-15T10:30:00+00:00",
            "url": "not-a-url",
            "summary": "Some summary text here.",
        }
        result = validator.validate(article)
        assert result.is_valid is False
        categories = [w.category for w in result.warnings]
        assert "invalid_url" in categories

    def test_validate_invalid_date(self):
        validator = NewsValidator()
        article = {
            "title": "Valid Title Here",
            "source": "Reuters",
            "published_at": "not-a-date",
            "url": "https://example.com/article",
            "summary": "Some summary text here.",
        }
        result = validator.validate(article)
        assert result.is_valid is False
        categories = [w.category for w in result.warnings]
        assert "invalid_date" in categories

    def test_validate_many_yields_results(self, valid_news_article: dict):
        validator = NewsValidator()
        invalid = {"title": "", "source": "", "published_at": "", "url": "", "summary": ""}
        results = list(validator.validate_many([valid_news_article, invalid]))
        assert len(results) == 2
        assert results[0].is_valid is True
        assert results[1].is_valid is False

    def test_validate_many_lazy_evaluation(self, valid_news_article, tracking_iterable):
        validator = NewsValidator()
        TrackingIterable = tracking_iterable
        records = TrackingIterable([valid_news_article, valid_news_article])
        gen = validator.validate_many(records)
        assert records.call_count == 0
        next(gen)
        assert records.call_count == 1
        list(gen)
        assert records.call_count == 2
