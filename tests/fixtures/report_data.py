"""Test fixtures for multi-format report generation tests.

All fixtures use direct dataclass construction — no mocking needed.
"""

from __future__ import annotations

import pytest

from src.generate.config import TICKERS
from src.generate.models import ReportInput
from src.model.pretrained.signals import TradingSignal
from src.preprocess.validator import ValidationWarning


@pytest.fixture
def sample_trading_signal_buy() -> TradingSignal:
    return TradingSignal(
        ticker="AAPL",
        signal="buy",
        confidence=0.65,
        rationale="Sentiment positive (0.70) with confidence 0.80. "
        "Market return: +5.00%. Combined score: 0.60. Signal: buy.",
        sentiment_score=0.70,
        market_return=0.05,
    )


@pytest.fixture
def sample_trading_signal_sell() -> TradingSignal:
    return TradingSignal(
        ticker="JPM",
        signal="sell",
        confidence=0.55,
        rationale="Sentiment negative (-0.60) with confidence 0.80. "
        "Market return: -3.00%. Combined score: -0.45. Signal: sell.",
        sentiment_score=-0.60,
        market_return=-0.03,
    )


@pytest.fixture
def sample_trading_signal_hold() -> TradingSignal:
    return TradingSignal(
        ticker="MSFT",
        signal="hold",
        confidence=0.25,
        rationale="Sentiment neutral (0.05) with confidence 0.40. "
        "Market return: +0.20%. Combined score: 0.05. Signal: hold.",
        sentiment_score=0.05,
        market_return=0.002,
    )


@pytest.fixture
def sample_trading_signal_no_market() -> TradingSignal:
    return TradingSignal(
        ticker="TSLA",
        signal="hold",
        confidence=0.20,
        rationale="Sentiment positive (0.30) with confidence 0.20. "
        "Market return: N/A. Combined score: 0.30. Signal: hold.",
        sentiment_score=0.30,
        market_return=None,
    )


@pytest.fixture
def sample_warnings_list() -> list[ValidationWarning]:
    return [
        ValidationWarning(
            category="market_data",
            field="open",
            message="open price is 0.0 for AAPL (daily_return defaulted to 0.0)",
            value="0.0",
        ),
        ValidationWarning(
            category="missing_market_data",
            field="market_data",
            message="No market data available for TSLA on 2026-05-28",
            value=None,
        ),
        ValidationWarning(
            category="invalid_volume",
            field="volume",
            message="volume must be > 0, got 0",
            value="0",
        ),
    ]


@pytest.fixture
def sample_report_input_10() -> ReportInput:
    signals: list[TradingSignal] = []
    for i, ticker in enumerate(TICKERS):
        if i % 3 == 0:
            signal = "buy"
            confidence = 0.65
            sentiment = 0.70
            ret = 0.05
            rationale = (
                "Sentiment positive (0.70) with confidence 0.80. "
                "Market return: +5.00%. Combined score: 0.60. Signal: buy."
            )
        elif i % 3 == 1:
            signal = "sell"
            confidence = 0.55
            sentiment = -0.60
            ret = -0.03
            rationale = (
                "Sentiment negative (-0.60) with confidence 0.80. "
                "Market return: -3.00%. Combined score: -0.45. Signal: sell."
            )
        else:
            signal = "hold"
            confidence = 0.25
            sentiment = 0.05
            ret = 0.002
            rationale = (
                "Sentiment neutral (0.05) with confidence 0.40. "
                "Market return: +0.20%. Combined score: 0.05. Signal: hold."
            )
        signals.append(
            TradingSignal(
                ticker=ticker,
                signal=signal,
                confidence=confidence,
                rationale=rationale,
                sentiment_score=sentiment,
                market_return=ret,
            )
        )
    return ReportInput(
        ticker_signals=signals,
        date="2026-05-28",
    )


@pytest.fixture
def sample_report_input_empty() -> ReportInput:
    return ReportInput(
        ticker_signals=[],
        date="2026-05-28",
    )


@pytest.fixture
def sample_report_input_with_warnings() -> ReportInput:
    signals: list[TradingSignal] = [
        TradingSignal(
            ticker="AAPL",
            signal="buy",
            confidence=0.65,
            rationale="Sentiment positive (0.70). Signal: buy.",
            sentiment_score=0.70,
            market_return=0.05,
        ),
    ]
    warnings = [
        ValidationWarning(
            category="market_data",
            field="open",
            message="open price is 0.0 for AAPL (daily_return defaulted to 0.0)",
            value="0.0",
        ),
        ValidationWarning(
            category="missing_market_data",
            field="market_data",
            message="No market data available for TSLA on 2026-05-28",
            value=None,
        ),
        ValidationWarning(
            category="invalid_volume",
            field="volume",
            message="volume must be > 0, got 0",
            value="0",
        ),
    ]
    return ReportInput(
        ticker_signals=signals,
        date="2026-05-28",
        warnings=warnings,
    )


@pytest.fixture
def sample_report_input_no_market() -> ReportInput:
    return ReportInput(
        ticker_signals=[
            TradingSignal(
                ticker="AAPL",
                signal="buy",
                confidence=0.65,
                rationale="Sentiment positive (0.70). Signal: buy.",
                sentiment_score=0.70,
                market_return=0.05,
            ),
            TradingSignal(
                ticker="TSLA",
                signal="hold",
                confidence=0.20,
                rationale="Sentiment positive (0.30). Signal: hold.",
                sentiment_score=0.30,
                market_return=None,
            ),
        ],
        date="2026-05-28",
    )
