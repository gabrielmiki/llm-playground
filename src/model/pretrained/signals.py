from __future__ import annotations

from dataclasses import dataclass

from src.collect.market_data import MarketData
from src.model.pretrained.sentiment import SentimentResult


@dataclass
class TradingSignal:
    """Output of trading signal generation.

    Attributes:
        ticker: Stock ticker symbol.
        signal: Trading recommendation ("buy", "sell", or "hold").
        confidence: Confidence in the signal [0.0, 1.0].
        rationale: Human-readable explanation of the signal.
        sentiment_score: Pass-through from SentimentResult.
        market_return: Daily return (close - open) / open, or None if no market data.
    """

    ticker: str
    signal: str
    confidence: float
    rationale: str
    sentiment_score: float
    market_return: float | None


def _clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value to [lo, hi] range."""
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


class TradingSignalGenerator:
    """Generates buy/sell/hold signals from sentiment and market data.

    Combines SentimentResult scores with single-day market data features
    using a weighted formula. Supports configurable thresholds and weights.

    Attributes:
        confidence_threshold: Minimum combined confidence for non-hold signals.
        sentiment_weight: Weight assigned to sentiment in the combined score.
        market_weight: Weight assigned to market signal in the combined score.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.3,
        sentiment_weight: float = 0.5,
        market_weight: float = 0.5,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.sentiment_weight = sentiment_weight
        self.market_weight = market_weight

    def generate(
        self,
        ticker: str,
        sentiment: SentimentResult,
        market_data: MarketData | None,
    ) -> TradingSignal:
        if sentiment is None:
            raise TypeError(
                "sentiment must be a SentimentResult, got None"
            )

        daily_return = 0.0

        if market_data is None:
            combined_score = sentiment.sentiment_score
            combined_confidence = sentiment.confidence
        else:
            if market_data.open == 0:
                daily_return = 0.0
            else:
                daily_return = (
                    market_data.close - market_data.open
                ) / market_data.open

            market_signal = _clamp(daily_return * 10, -1, 1)

            combined_score = (
                self.sentiment_weight * sentiment.sentiment_score
                + self.market_weight * market_signal
            )

            market_confidence = _clamp(abs(daily_return) * 10, 0, 1)
            combined_confidence = (
                self.sentiment_weight * sentiment.confidence
                + self.market_weight * market_confidence
            )

            if sentiment.sentiment_score * market_signal < 0:
                combined_confidence *= 0.5

        if combined_confidence < self.confidence_threshold:
            signal = "hold"
        elif combined_score > self.confidence_threshold:
            signal = "buy"
        elif combined_score < -self.confidence_threshold:
            signal = "sell"
        else:
            signal = "hold"

        if sentiment.sentiment_score > 0:
            sentiment_label = "positive"
        elif sentiment.sentiment_score < 0:
            sentiment_label = "negative"
        else:
            sentiment_label = "neutral"

        disagreement_note = (
            " Sentiment and market disagree — confidence halved."
            if market_data is not None
            and sentiment.sentiment_score * market_signal < 0
            else ""
        )
        market_return_str = (
            f"{daily_return:+.2%}" if market_data else "N/A"
        )
        rationale = (
            f"Sentiment {sentiment_label} ({sentiment.sentiment_score:.2f}) "
            f"with confidence {sentiment.confidence:.2f}. "
            f"Market return: {market_return_str}. "
            f"Combined score: {combined_score:.2f}."
            f"{disagreement_note}"
            f" Signal: {signal}."
        )

        return TradingSignal(
            ticker=ticker,
            signal=signal,
            confidence=combined_confidence,
            rationale=rationale,
            sentiment_score=sentiment.sentiment_score,
            market_return=daily_return if market_data else None,
        )
