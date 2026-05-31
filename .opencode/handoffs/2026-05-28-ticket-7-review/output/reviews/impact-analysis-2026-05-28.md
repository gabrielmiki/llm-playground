# Impact Analysis: Ticket 7 — Trading Signal Generation

**Date:** May 28, 2026  
**Author:** code-reviewer agent  
**Scope:** Codebase-wide impact of implementing `TradingSignalGenerator`  

---

## 1. Executive Summary

Ticket 7 adds a **TradingSignalGenerator** as a new module (`src/model/pretrained/signals.py`). The impact is **moderate and well-contained** — 4 files modified, 3 new files created, 0 new dependencies, and no breaking changes to existing APIs.

The signal generator is **pure Python math** — no torch, no GPU, no external API calls. This makes it the simplest module in the project to test and integrate. However, there are delicate points around existing fixture usage, pipeline integration, and SentimentResult label derivation that need careful attention.

---

## 2. Files Created

| File | Purpose | Risk Level |
|------|---------|------------|
| `src/model/pretrained/signals.py` | `TradingSignal` dataclass + `TradingSignalGenerator` | **Low** — new file, no existing code affected |
| `tests/fixtures/signal_data.py` | SentimentResult + MarketData factory fixtures | **Low** — follows existing pattern |
| `tests/test_signals.py` | 10+ AC tests for signal generation | **Low** — pure math, no mocking needed |

---

## 3. Files Modified

### 3.1 `src/model/pretrained/__init__.py` — LOW RISK

**Current content:**
```python
from src.model.pretrained.sentiment import ArticleSentiment, FinBertSentiment, SentimentResult
__all__ = ["ArticleSentiment", "FinBertSentiment", "SentimentResult"]
```

**Required change:** Add import from `signals.py`
```python
from src.model.pretrained.sentiment import ArticleSentiment, FinBertSentiment, SentimentResult
from src.model.pretrained.signals import TradingSignal, TradingSignalGenerator
__all__ = ["ArticleSentiment", "FinBertSentiment", "SentimentResult", "TradingSignal", "TradingSignalGenerator"]
```

**Risk:** None. Standard re-export pattern. Follows exact same template as the existing `sentiment.py` import.

### 3.2 `src/model/__init__.py` — LOW RISK

**Current content:**
```python
from src.model.exceptions import ModelLoadError
from src.model.pretrained.sentiment import ArticleSentiment, FinBertSentiment, SentimentResult
__all__ = ["ArticleSentiment", "FinBertSentiment", "ModelLoadError", "SentimentResult"]
```

**Required change:** Re-export new classes
```python
from src.model.exceptions import ModelLoadError
from src.model.pretrained.sentiment import ArticleSentiment, FinBertSentiment, SentimentResult
from src.model.pretrained.signals import TradingSignal, TradingSignalGenerator
__all__ = ["ArticleSentiment", "FinBertSentiment", "ModelLoadError", "SentimentResult", "TradingSignal", "TradingSignalGenerator"]
```

**Risk:** None. Standard re-export propagation.

### 3.3 `tests/conftest.py` — LOW RISK

**Current pytest_plugins:** 9 fixture modules registered.

**Required change:** Add `"tests.fixtures.signal_data"` to the list.

**Risk:** None. Follows exact same pattern as all existing fixture registrations (see `sentiment_data` insertion as precedent).

### 3.4 `src/pipeline.py` — MEDIUM RISK ⚠️

**Current pipeline stages:**
```
Stage 1: Collection (market data + news)
Stage 2: Preprocessing (validation, cleaning, language filter)
Stage 3: Fusion (DataFusionEngine)
Stage 4: Output (FusedRecordWriter)
Stage 5: Sentiment Analysis (FinBertSentiment)
```

**Required change:** Add Stage 6: Signal Generation after the existing Stage 5 try/except block.

**Delicate points:**
- ⚠️ **Stage 5 produces `SentimentResult` inside a try/except** — the `result` variable is scoped within the try block. Stage 6 needs access to both `result` and the `fused` record's `market_data`. This requires restructuring.
- ⚠️ **The pipeline currently degrades gracefully** when sentiment analysis is unavailable (torch not installed) — it logs a warning and continues. Stage 6 must not produce misleading signals when sentiment was skipped.
- ⚠️ **Stage 6 should mirror the conditional import pattern** from Stage 5, but simpler (no torch dependency, so a plain import suffices).

**Recommended restructure in `src/pipeline.py`:**
```python
# Stage 5: Sentiment Analysis
sentiment_result = None
try:
    from src.model.pretrained.sentiment import FinBertSentiment
    sentiment = FinBertSentiment()
    sentiment_result = sentiment.analyze(fused)
    ...log results...
except (ModelLoadError, ImportError) as e:
    logger.warning("Sentiment analysis skipped: %s", e)

# Stage 6: Signal Generation
logger.info("")
logger.info("--- Stage 6: Signal Generation ---")
if sentiment_result is not None and fused.market_data is not None:
    from src.model.pretrained.signals import TradingSignalGenerator
    generator = TradingSignalGenerator()
    signal = generator.generate(fused.ticker, sentiment_result, fused.market_data)
    ...log signal...
else:
    reason = "sentiment unavailable" if sentiment_result is None else "market data unavailable"
    logger.warning("Signal generation skipped: %s", reason)
```

---

## 4. Dependency Chain Analysis

### 4.1 Import Graph

```
signals.py
├── SentimentResult          (from src.model.pretrained.sentiment)  — no circular dependency risk
├── MarketData               (from src.collect.market_data)          — no circular dependency risk
└── TradingSignal            (same file, dataclass)                  — self-contained
```

### 4.2 What signals.py DOES NOT depend on

- ❌ `FusedRecord` — not needed. `TradingSignalGenerator.generate()` accepts `SentimentResult` + `MarketData` directly.
- ❌ `torch` / `transformers` — pure Python math, no conditional imports needed.
- ❌ `ModelLoadError` — not needed (no model loading involved).

### 4.3 What the pipeline needs

The pipeline's Stage 5 already has `fused` (FusedRecord) which contains `fused.ticker`, `fused.market_data`. The sentiment result is already computed. Stage 6 just needs to pipe the `SentimentResult` + `MarketData` into the generator.

### 4.4 No Circular Dependency Risk

The import chain `signals.py ← sentiment.py ← fusion.py ← market_data.py` is acyclic and follows the same direction as all existing imports.

---

## 5. Impact on Existing Tests

### 5.1 No Existing Tests Break

The implementation adds **new code** and imports. No existing function signatures, dataclass fields, or API contracts are changed. All 13 existing sentiment tests and all other test files will continue to pass unchanged.

### 5.2 Existing Fixture Limitation ⚠️

**All 6 existing `sentiment_data.py` fixtures use `market_data=None`:**

```python
# sentiment_data.py — ALL fixtures:
FusedRecord(..., market_data=None, ...)
```

This means **none of the existing fixtures can be reused** for signal tests that require MarketData. The new `tests/fixtures/signal_data.py` must create its own `MarketData` fixtures with real OHLCV values.

**No risk of fixture naming collisions** — signal tests will use separate fixtures (`sample_market_data_up`, `sample_market_data_down`, etc.), not the sentiment fixtures.

### 5.3 Sentiment Fixture Refactoring (Optional, Low Priority)

A future improvement could refactor `sentiment_data.py` to include `market_data` in some fixtures so both sentiment and signal tests can share them. This is **not needed** for Ticket 7 implementation.

---

## 6. Delicate Points — Detailed Attention Required

### 🔴 DP1: Pipeline Stage 5 → Stage 6 Data Flow

**The problem:** Stage 5's `SentimentResult result` is currently scoped inside a `try` block:

```python
# pipeline.py:130-155
try:
    from src.model.pretrained.sentiment import FinBertSentiment
    sentiment = FinBertSentiment()
    result = sentiment.analyze(fused)       # result scoped here
    ...
except (ModelLoadError, ImportError) as e:
    ...
# result is NOT accessible here — NameError
```

**The fix:** Initialize `sentiment_result = None` before the try block, then assign inside it.

**Why it matters:** If this is missed, Stage 6 will crash with `NameError: name 'result' is not defined`. The try/except swallows this error if not placed correctly.

### 🔴 DP2: Handling Missing Sentiment Result in Stage 6

**The scenario:** If Stage 5's imports fail (torch/transformers not installed), `sentiment_result` is `None`. Stage 6 must detect this and gracefully skip:

```python
if sentiment_result is None or fused.market_data is None:
    logger.warning("Signal generation skipped: %s", reason)
    return
```

**Why it matters:** If not guarded, calling `generator.generate(None, ...)` will raise `TypeError` (per AC-08), which could crash the pipeline.

### 🟡 DP3: MarketData Availability

**The problem:** `FusedRecord.market_data` is `MarketData | None`. Collection can fail (API rate limits, market holidays) and produce `None`. The signal generator handles `None` internally (AC-04, AC-09), but the pipeline integration needs to handle it too.

**The nuance:** When `market_data=None`, the signal is derived from sentiment alone. This is valid behavior, not an error. The pipeline log message should say "derived from sentiment only" not "skipped."

### 🟡 DP4: SentimentResult Label Field Doesn't Exist

**Confirmed:** `SentimentResult` has `sentiment_score`, `confidence`, `breakdown` — but no `label` field. The ticket spec's `signal_logic` adds label derivation:
```python
if sentiment.sentiment_score > 0: sentiment_label = "positive"
elif sentiment.sentiment_score < 0: sentiment_label = "negative"
else: sentiment_label = "neutral"
```

**Why it's delicate:** This derivation logic lives ONLY in `signals.py`'s `signal_logic` section. A developer might expect `SentimentResult` to have a `.label` property and try to access it, causing an AttributeError. **Document this decision clearly** in the `generate()` method docstring.

### 🟡 DP5: No New Dependencies Required

The signal generator uses only Python stdlib and the project's existing dataclasses (`MarketData`, `SentimentResult`). No additions needed to `pyproject.toml` under `[project.optional-dependencies]`.

### 🟢 DP6: Test Simplicity

Unlike Ticket 6's sentiment tests (which required `MockTensor`, `sys.modules["torch"]` injection, complex mock `side_effect` patterns), signal tests use:
- Direct `SentimentResult` construction
- Direct `MarketData` construction
- Pure Python `assert` statements

This is the simplest test setup in the project. No mocking infrastructure needed.

---

## 7. Implementation Order

Recommended implementation sequence, from lowest to highest risk:

| Step | File(s) | Risk | Why This Order |
|------|---------|------|----------------|
| 1 | `tests/fixtures/signal_data.py` | Low | Fixtures first so tests can reference them |
| 2 | `src/model/pretrained/signals.py` | Low | Core logic — no dependencies on other new files |
| 3 | `tests/test_signals.py` | Low | Tests can run against `signals.py` immediately |
| 4 | `tests/conftest.py` | Low | Register new fixtures |
| 5 | `src/model/pretrained/__init__.py` | Low | Export from subpackage |
| 6 | `src/model/__init__.py` | Low | Export from top-level package |
| 7 | `src/pipeline.py` | Medium ⚠️ | Pipeline integration — depends on all above being correct |

Steps 1-3 can be done in parallel. Steps 5-6 are trivial one-liners. Step 7 (pipeline) is the most delicate and should be done last after all tests pass.

---

## 8. File-by-File Diff Preview

### 8.1 New: `src/model/pretrained/signals.py`

```python
"""Trading signal generation from sentiment and market data."""
from __future__ import annotations

from dataclasses import dataclass

from src.collect.market_data import MarketData
from src.model.pretrained.sentiment import SentimentResult


@dataclass
class TradingSignal:
    ticker: str
    signal: str
    confidence: float
    rationale: str
    sentiment_score: float
    market_return: float | None


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

### 8.2 Modified: `src/model/pretrained/__init__.py`

```diff
 from src.model.pretrained.sentiment import ArticleSentiment, FinBertSentiment, SentimentResult
+from src.model.pretrained.signals import TradingSignal, TradingSignalGenerator

-__all__ = ["ArticleSentiment", "FinBertSentiment", "SentimentResult"]
+__all__ = ["ArticleSentiment", "FinBertSentiment", "SentimentResult", "TradingSignal", "TradingSignalGenerator"]
```

### 8.3 Modified: `src/model/__init__.py`

```diff
 from src.model.exceptions import ModelLoadError
 from src.model.pretrained.sentiment import ArticleSentiment, FinBertSentiment, SentimentResult
+from src.model.pretrained.signals import TradingSignal, TradingSignalGenerator

-__all__ = ["ArticleSentiment", "FinBertSentiment", "ModelLoadError", "SentimentResult"]
+__all__ = ["ArticleSentiment", "FinBertSentiment", "ModelLoadError", "SentimentResult", "TradingSignal", "TradingSignalGenerator"]
```

### 8.4 Modified: `tests/conftest.py`

```diff
 pytest_plugins = [
     ...
     "tests.fixtures.sentiment_data",
+    "tests.fixtures.signal_data",
 ]
```

### 8.5 Modified: `src/pipeline.py`

```diff
 # Stage 5: Sentiment Analysis
+sentiment_result = None
 try:
     from src.model.pretrained.sentiment import FinBertSentiment
     sentiment = FinBertSentiment()
-    result = sentiment.analyze(fused)
+    sentiment_result = sentiment.analyze(fused)
     ...
 except (ModelLoadError, ImportError) as e:
     logger.warning("Sentiment analysis skipped: %s", e)

+# Stage 6: Signal Generation
+if sentiment_result is not None and fused.market_data is not None:
+    from src.model.pretrained.signals import TradingSignalGenerator
+    generator = TradingSignalGenerator()
+    signal = generator.generate(fused.ticker, sentiment_result, fused.market_data)
+    ...
+elif sentiment_result is not None and fused.market_data is None:
+    from src.model.pretrained.signals import TradingSignalGenerator
+    generator = TradingSignalGenerator()
+    signal = generator.generate(fused.ticker, sentiment_result, fused.market_data)
+    ...
+else:
+    logger.warning("Signal generation skipped: no sentiment result")
```

**Note:** The pipeline code above is illustrative. The actual implementation should deduplicate the `TradingSignalGenerator` import and conditional call.

---

## 9. New Dependencies

**None.** The signal generator requires:
- `dataclasses` (stdlib)
- `src.collect.market_data.MarketData` (existing project code)
- `src.model.pretrained.sentiment.SentimentResult` (existing project code)

No additions to `pyproject.toml` needed.

---

## 10. Delicate Checkpoints — Pre-Implementation Checklist

Before merging, verify these 5 critical points:

- [ ] **DP1 resolved:** `sentiment_result` initialized as `None` BEFORE the Stage 5 try block
- [ ] **DP2 resolved:** Stage 6 guarded against `sentiment_result is None`
- [ ] **DP3 resolved:** Pipeline handles `market_data=None` gracefully (sentiment-only signal, not skipped)
- [ ] **DP4 resolved:** `SentimentResult` label derivation is documented in `signals.py` (no field on the dataclass itself)
- [ ] **DP6 resolved:** All tests use direct construction, no mocking infrastructure

---

## 11. Rollback Plan

Reverting Ticket 7 if issues are discovered post-implementation:

1. **Revert** `src/pipeline.py` changes (remove Stage 6 block)
2. **Delete** `src/model/pretrained/signals.py`
3. **Delete** `tests/fixtures/signal_data.py`
4. **Delete** `tests/test_signals.py`
5. **Revert** `src/model/pretrained/__init__.py` (remove import line)
6. **Revert** `src/model/__init__.py` (remove import line)
7. **Revert** `tests/conftest.py` (remove pytest_plugins entry)

No existing tests or functionality are affected during the rollback.

---

## 12. Summary Table

| Dimension | Impact | Risk Level | Mitigation |
|-----------|--------|------------|------------|
| New files | 3 | Low | No existing code touched |
| Modified files | 4 | Low–Medium | Simple one-line additions (init files, conftest); pipeline restructure is the only medium-risk change |
| Existing tests broken | 0 | None | No API changes |
| New dependencies | 0 | None | Pure Python stdlib |
| Circular imports | 0 | None | Acyclic dependency graph |
| Pipeline integration | 1 file | ⚠️ Medium | Sentiment result scoping + None guards + graceful skip |
| Test infrastructure | Simple | Low | Direct construction, no mocks |
| Breaking changes | None | None | Additive change only |
