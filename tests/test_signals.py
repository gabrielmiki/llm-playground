"""Tests for trading signal generation (Ticket 7).

All 10 acceptance criteria verified. Uses fixtures from
tests/fixtures/signal_data.py for test data.
"""

from __future__ import annotations

import pytest

from src.collect.market_data import MarketData
from src.model.pretrained.sentiment import SentimentResult
from src.model.pretrained.signals import TradingSignalGenerator


@pytest.fixture
def generator() -> TradingSignalGenerator:
    return TradingSignalGenerator()


class TestAC01BuyHappyPath:
    """AC-01: Strong positive sentiment + positive return → buy."""

    def test_signal_is_buy(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_positive: SentimentResult,
        sample_market_data_up: MarketData,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_positive, sample_market_data_up)
        assert result.signal == "buy"

    def test_confidence_above_05(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_positive: SentimentResult,
        sample_market_data_up: MarketData,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_positive, sample_market_data_up)
        assert result.confidence > 0.5

    def test_rationale_contains_both_contributions(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_positive: SentimentResult,
        sample_market_data_up: MarketData,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_positive, sample_market_data_up)
        assert "Sentiment" in result.rationale
        assert "Market return" in result.rationale


class TestAC02SellHappyPath:
    """AC-02: Negative sentiment + negative return → sell."""

    def test_signal_is_sell(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_negative: SentimentResult,
        sample_market_data_down: MarketData,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_negative, sample_market_data_down)
        assert result.signal == "sell"

    def test_confidence_above_05(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_negative: SentimentResult,
        sample_market_data_down: MarketData,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_negative, sample_market_data_down)
        assert result.confidence > 0.5


class TestAC03HoldNeutral:
    """AC-03: Neutral sentiment + flat return → hold."""

    def test_signal_is_hold(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_neutral: SentimentResult,
        sample_market_data_flat: MarketData,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_neutral, sample_market_data_flat)
        assert result.signal == "hold"


class TestAC04MarketDataNone:
    """AC-04: No market data → signal derived from sentiment alone."""

    def test_signal_derived_from_sentiment_only(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_positive: SentimentResult,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_positive, market_data=None)
        assert result.signal == "buy"

    def test_confidence_equals_sentiment_confidence(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_positive: SentimentResult,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_positive, market_data=None)
        assert result.confidence == pytest.approx(0.8)

    def test_market_return_is_none(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_positive: SentimentResult,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_positive, market_data=None)
        assert result.market_return is None


class TestAC05LowConfidenceOverride:
    """AC-05: Low confidence overrides directional score → hold."""

    def test_signal_is_hold(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_low_confidence: SentimentResult,
        sample_market_data_flat: MarketData,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_low_confidence, sample_market_data_flat)
        assert result.signal == "hold"

    def test_combined_confidence_below_threshold(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_low_confidence: SentimentResult,
        sample_market_data_flat: MarketData,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_low_confidence, sample_market_data_flat)
        assert result.confidence < 0.3


class TestAC06DisagreementHalving:
    """AC-06: Conflicting signals → confidence halved, hold, rationale mentions disagreement."""

    def test_confidence_is_halved(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_strong_positive: SentimentResult,
        sample_market_data_down_five: MarketData,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_strong_positive, sample_market_data_down_five)
        expected_full = 0.5 * 0.8 + 0.5 * 0.5
        assert result.confidence == pytest.approx(expected_full * 0.5)

    def test_signal_is_hold(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_strong_positive: SentimentResult,
        sample_market_data_down_five: MarketData,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_strong_positive, sample_market_data_down_five)
        assert result.signal == "hold"

    def test_rationale_mentions_disagreement(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_strong_positive: SentimentResult,
        sample_market_data_down_five: MarketData,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_strong_positive, sample_market_data_down_five)
        assert "disagree" in result.rationale.lower()


class TestAC07ZeroOpenGuard:
    """AC-07: open=0.0 → no division-by-zero, daily_return defaults to 0.0."""

    def test_no_zero_division_error(
        self,
        generator: TradingSignalGenerator,
        sample_market_data_zero_open: MarketData,
    ) -> None:
        sentiment = SentimentResult(sentiment_score=+0.5, confidence=0.6, breakdown=[])
        result = generator.generate("AAPL", sentiment, sample_market_data_zero_open)
        assert result.market_return is not None
        assert result.market_return == pytest.approx(0.0)


class TestAC08NoneSentiment:
    """AC-08: None as SentimentResult → TypeError."""

    def test_type_error_raised(self, generator: TradingSignalGenerator) -> None:
        with pytest.raises(TypeError, match="sentiment must be a SentimentResult"):
            generator.generate("AAPL", None, market_data=None)  # type: ignore[arg-type]


class TestAC09MarketDataNoneLowConfidence:
    """AC-09: No market data + low confidence → hold."""

    def test_signal_is_hold(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_very_low_confidence: SentimentResult,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_very_low_confidence, market_data=None)
        assert result.signal == "hold"

    def test_confidence_below_threshold(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_very_low_confidence: SentimentResult,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_very_low_confidence, market_data=None)
        assert result.confidence < 0.3


class TestAC10RationaleFormat:
    """AC-10: Rationale contains all required fields."""

    def test_rationale_contains_sentiment_label(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_positive: SentimentResult,
        sample_market_data_up: MarketData,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_positive, sample_market_data_up)
        assert "positive" in result.rationale

    def test_rationale_contains_sentiment_score(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_positive: SentimentResult,
        sample_market_data_up: MarketData,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_positive, sample_market_data_up)
        assert "0.70" in result.rationale

    def test_rationale_contains_confidence(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_positive: SentimentResult,
        sample_market_data_up: MarketData,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_positive, sample_market_data_up)
        assert "0.80" in result.rationale

    def test_rationale_contains_market_return(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_positive: SentimentResult,
        sample_market_data_up: MarketData,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_positive, sample_market_data_up)
        assert "+5.00%" in result.rationale

    def test_rationale_contains_combined_score(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_positive: SentimentResult,
        sample_market_data_up: MarketData,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_positive, sample_market_data_up)
        assert "0.60" in result.rationale

    def test_rationale_contains_signal(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_positive: SentimentResult,
        sample_market_data_up: MarketData,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_positive, sample_market_data_up)
        assert "Signal: buy" in result.rationale

    def test_rationale_uses_na_when_no_market_data(
        self,
        generator: TradingSignalGenerator,
        sample_sentiment_result_positive: SentimentResult,
    ) -> None:
        result = generator.generate("AAPL", sample_sentiment_result_positive, market_data=None)
        assert "N/A" in result.rationale
