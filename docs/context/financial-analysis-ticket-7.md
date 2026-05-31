# Financial LLM Analysis - Implementation Tickets

Generated from PRD: Financial Markets LLM Analysis System

---

## Ticket 7: Trading Signal Generation

**type**: story  
**layer**: model  
**complexity**: medium  
**dependencies**: [Ticket 2, Ticket 6]  

**title**: Generate buy/sell/hold signals from sentiment and market data

**description**:  
Combine sentiment analysis with single-day market data features (daily return, direction) to generate actionable trading signals with confidence scores and rationale.

**acceptance_criteria**:

- AC-01: Given sentiment_score=+0.7, sentiment.confidence=0.8, market return=+5%, When generate() is called, Then signal is "buy", confidence > 0.5, and rationale contains both sentiment and market contributions
- AC-02: Given sentiment_score=-0.6, sentiment.confidence=0.8, market return=-3%, When generate() is called, Then signal is "sell", confidence > 0.5
- AC-03: Given sentiment_score=+0.05, sentiment.confidence=0.4, market return=0%, When generate() is called, Then signal is "hold"
- AC-04: Given market_data is None, sentiment_score=+0.7, sentiment.confidence=0.8, When generate() is called, Then signal is derived from sentiment alone and confidence equals sentiment.confidence
- AC-05: Given sentiment_score=+0.8, sentiment.confidence=0.2, market return=0%, When generate() is called, Then signal is "hold" (combined_confidence < confidence_threshold overrides directional score)
- AC-06: Given sentiment_score=+0.9, sentiment.confidence=0.8, market return=-5%, When generate() is called, Then confidence is halved (due to disagreement), combined_score < threshold, signal is "hold", and rationale mentions the disagreement
- AC-07: Given market_data with open=0.0, When generate() is called, Then no division-by-zero error occurs and daily_return safely defaults to 0.0
- AC-08: Given None as SentimentResult, When generate() is called, Then TypeError is raised with descriptive message
- AC-09: Given market_data is None and sentiment.confidence=0.25 (below threshold), When generate() is called, Then signal is "hold" (low-confidence guard applies even with sentiment-only)
- AC-10: Given a generated signal, When rationale is inspected, Then it contains sentiment_label, sentiment_score, confidence, market_return (or "N/A"), combined_score, and the signal label

**api_spec** (internal):

```python
# src/model/pretrained/signals.py

from dataclasses import dataclass
from src.model.pretrained.sentiment import SentimentResult
from src.collect.market_data import MarketData


@dataclass
class TradingSignal:
    ticker: str
    signal: str               # "buy" | "sell" | "hold"
    confidence: float         # [0.0, 1.0]
    rationale: str            # template-based explanation
    sentiment_score: float    # pass-through from SentimentResult
    market_return: float | None  # (close - open) / open if market_data else None


class TradingSignalGenerator:
    def __init__(
        self,
        confidence_threshold: float = 0.3,
        sentiment_weight: float = 0.5,
        market_weight: float = 0.5,
    ) -> None: ...

    def generate(
        self,
        ticker: str,
        sentiment: SentimentResult,
        market_data: MarketData | None,
    ) -> TradingSignal: ...
```

**signal_logic**:

```
daily_return = 0.0  # default, safe for None or zero-open cases

if market_data is None:
    combined_score = sentiment.sentiment_score
    combined_confidence = sentiment.confidence
else:
    # Market features (single-day)
    if market_data.open == 0:
        daily_return = 0.0
    else:
        daily_return = (market_data.close - market_data.open) / market_data.open

    # Normalize market return to [-1, 1]
    market_signal = clamp(daily_return * 10, -1, 1)

    # Combined score
    combined_score = (sentiment_weight * sentiment.sentiment_score
                      + market_weight * market_signal)

    # Confidence
    market_confidence = clamp(abs(daily_return) * 10, 0, 1)
    combined_confidence = (sentiment_weight * sentiment.confidence
                           + market_weight * market_confidence)

    # If sentiment and market disagree in sign, reduce confidence by 50%
    if sentiment.sentiment_score * market_signal < 0:
        combined_confidence *= 0.5

# Low-confidence override: if confidence below threshold, default to hold
if combined_confidence < confidence_threshold:
    signal = "hold"
elif combined_score > confidence_threshold:
    signal = "buy"
elif combined_score < -confidence_threshold:
    signal = "sell"
else:
    signal = "hold"

# Sentiment label derivation (SentimentResult has no label field)
if sentiment.sentiment_score > 0:
    sentiment_label = "positive"
elif sentiment.sentiment_score < 0:
    sentiment_label = "negative"
else:
    sentiment_label = "neutral"

# Rationale template
disagreement_note = (
    " Sentiment and market disagree — confidence halved."
    if market_data is not None and sentiment.sentiment_score * market_signal < 0
    else ""
)
market_return_str = f"{daily_return:+.2%}" if market_data else "N/A"
rationale = (
    f"Sentiment {sentiment_label} ({sentiment.sentiment_score:.2f}) "
    f"with confidence {sentiment.confidence:.2f}. "
    f"Market return: {market_return_str}. "
    f"Combined score: {combined_score:.2f}."
    f"{disagreement_note}"
    f" Signal: {signal}."
)
```
