# Post-Mortem: Ticket 7 — Trading Signal Generation

**Date:** May 28, 2026  
**Status:** ✅ COMPLETE  
**Review Status:** APPROVE (after 3 TDD review rounds + 1 code review round)

---

## 1. Overview

### Original Ticket
**Title:** Generate buy/sell/hold signals from sentiment and market data

**Original Acceptance Criteria (3 ACs, minimal detail):**
```markdown
- Given sentiment score and market data, When signal is generated, Then result is buy, sell, or hold
- Given signal, When generated, Then confidence score (0-1) is provided
- Given signal, When generated, Then human-readable rationale is included
```

**Original api_spec:**
```
Input: { ticker: string, sentiment: SentimentResult, market_data: MarketData }
Output: { ticker, signal: enum(buy|sell|hold), confidence: float, rationale: string }
```

### Refined Acceptance Criteria (10 ACs after 3 TDD review rounds)

```
AC-01:  sentiment_score=+0.7, sentiment.confidence=0.8, market return=+5% → "buy", confidence > 0.5
AC-02:  sentiment_score=-0.6, sentiment.confidence=0.8, market return=-3% → "sell", confidence > 0.5
AC-03:  sentiment_score=+0.05, sentiment.confidence=0.4, market return=0% → "hold"
AC-04:  market_data=None, sentiment_score=+0.7, sentiment.confidence=0.8 → signal from sentiment alone, confidence = sentiment.confidence
AC-05:  sentiment_score=+0.8, sentiment.confidence=0.2, market return=0% → "hold" (low-confidence override)
AC-06:  sentiment_score=+0.9, sentiment.confidence=0.8, market return=-5% → confidence halved (disagreement), "hold"
AC-07:  market_data with open=0.0 → no division-by-zero, daily_return defaults to 0.0
AC-08:  None as SentimentResult → TypeError with descriptive message
AC-09:  market_data=None, sentiment.confidence=0.25 → "hold" (low-confidence guard, sentiment-only)
AC-10:  Rationale contains sentiment_label, sentiment_score, confidence, market_return (or "N/A"), combined_score, signal label
```

---

## 2. Problems Identified

### TDD Review Round 1 — NEEDS REVISION (7 blocking + 6 moderate issues)

The initial ticket had only 3 vague ACs, no formula, no concrete types, and wrong dependencies:

#### Blocking Issues

| Issue | Severity | Problem |
|-------|----------|---------|
| Data model mismatch ("price trends") | **Blocking** | Description mentioned "price trends" but `MarketData` is a single OHLCV day — trends require multiple time points. Could not compute trends from a single data point |
| No signal generation formula | **Blocking** | No algorithm specified for combining `sentiment_score` with `MarketData` fields. Any output would trivially pass the ACs |
| No confidence derivation formula | **Blocking** | AC-02 mandated [0,1] confidence but no formula specified. Any float in [0,1] would pass |
| Missing dependency: Ticket 2 | **Blocking** | API spec consumed `MarketData` (defined in Ticket 2) but only declared `dependencies: [Ticket 6]`. Same class of data-flow error as Ticket 6 |
| Dict output violated established pattern | **Blocking** | API spec returned bare `dict`. Every prior ticket used dataclasses: `MarketData`, `FusedRecord`, `SentimentResult` |
| Only 3 ACs, zero edge coverage | **Blocking** | Exactly the same problem as Ticket 6's initial state (which grew from 3 to 11 ACs). Missing: missing market data, zero volume, conflicting signals, absent inputs, low-confidence scenarios |
| Rationale format unspecified | **Blocking** | "human-readable" was ambiguous — any non-empty string would pass. No minimum content or format defined |

#### Moderate Issues

| Issue | Severity | Problem |
|-------|----------|---------|
| No file/class placement | **Moderate** | Where does this live? Class name? |
| Conflicting sentiment vs market undefined | **Moderate** | Strong positive sentiment + negative market return — behavior unspecified |
| Single-day limitations | **Moderate** | Single day doesn't produce "trends" even with daily_return |
| Import guard unspecified | **Moderate** | Signal generation is pure Python (no torch), but should be explicit |
| Input relationship to FinBertSentiment unclear | **Moderate** | Does the generator wrap FinBertSentiment or receive pre-computed SentimentResult? |
| "complex" complexity rating over-scoped | **Moderate** | Rule-based combination is straightforward — "medium" is more appropriate |

---

### TDD Review Round 2 — NEEDS REVISION (3 new blocking issues)

After fixing all 7 v1 blocking issues, 3 new issues emerged:

#### Blocking Issues

| Issue | Severity | Problem |
|-------|----------|---------|
| AC-05 contradicts formula | **Blocking** | AC-05 expected "hold" for sentiment=+0.8 with low confidence (0.2), but formula computed combined_score=0.4 > 0.3 → "buy". No low-confidence override existed in the signal_logic |
| market_data=None path undefined | **Blocking** | Formula started with `daily_return = (close - open) / open` which crashes on None. AC-04 and AC-09 required graceful None handling |
| AC-01/02 underdetermined | **Blocking** | Assertions like `confidence > 0.5` depended on `sentiment.confidence` but the Given clauses didn't specify it. Needed explicit confidence values to be verifiable |

#### Moderate Issues

| Issue | Severity | Problem |
|-------|----------|---------|
| AC-07 tested irrelevant field | **Moderate** | Zero volume was not used in the formula. Real risk was `open=0.0` causing division-by-zero |
| `daily_range` dead code | **Moderate** | Computed but never referenced |
| Market None weight ambiguity | **Moderate** | When market_data=None and sentiment_weight=0.5, scores are halved. Should default to 1.0 |

---

### TDD Review Round 3 — NEEDS REVISION (2 new blocking issues)

After fixing v2 issues, 2 final issues emerged:

#### Blocking Issues

| Issue | Severity | Problem |
|-------|----------|---------|
| `sentiment_label` doesn't exist | **Blocking** | `SentimentResult` has no `label` field — only `sentiment_score`, `confidence`, `breakdown`. Rationale template used `{sentiment_label}` which would crash with AttributeError |
| Disagreement note missing from rationale | **Blocking** | AC-06 required "rationale mentions the disagreement" but the template had no component for it |

#### Moderate Issues

| Issue | Severity | Problem |
|-------|----------|---------|
| `daily_return` unbound variable | **Moderate** | `daily_return` defined only inside `else` branch but referenced by ternary outside it. Linters (ruff, mypy) would flag it as potentially unbound |

---

### Implementation Issues

During implementation, several issues emerged from the dependency analysis that weren't caught by the spec review:

| Issue | Severity | Problem | Fix |
|-------|----------|---------|-----|
| `clamp()` function doesn't exist | **Blocking** | The signal_logic referenced `clamp(daily_return * 10, -1, 1)` but no such utility exists anywhere in the codebase | Added `_clamp()` private helper in `signals.py` |
| AC-08 needs explicit TypeError | **Blocking** | Without a guard, `None.sentiment_score` raises `AttributeError`, not `TypeError` as AC-08 requires | Added explicit `if sentiment is None: raise TypeError(...)` at top of `generate()` |
| Pipeline Stage 5 result scoped inside try | **Blocking** | `result = sentiment.analyze(fused)` was inside the try block — Stage 6 couldn't access it | Initialized `sentiment_result = None` before the try block, assigned inside |
| Pipeline CLI description stale | **Minor** | Description read `"collect -> preprocess -> fuse -> sentiment"` | Updated to include `"-> signal"` |

### Code Review Round 1 — 3 Issues Found (C.L.E.A.R. Framework)

| Severity | Finding | Location | Fix |
|----------|---------|----------|-----|
| **Medium** | AC-07 test only checks `market_return is not None` — does not verify the default value is `0.0` as the AC requires | `test_signals.py:135` | Added `assert result.market_return == pytest.approx(0.0)` |
| **Medium** | 8 fixtures defined in `signal_data.py` but 0 consumed by tests — all data constructed inline | `tests/fixtures/signal_data.py` | Refactored all 25 tests to use fixtures; added 2 new fixtures for AC-06 |
| **Low** | No module/class/method docstrings despite project convention (Google style) | `src/model/pretrained/signals.py` | Added Google-style docstrings to `TradingSignal`, `_clamp()`, `TradingSignalGenerator`, `generate()` |

---

## 3. Fixes Applied

### A. Resolved Data Model: Single-Day Features (v1 B1)

**Before:** "price trends" — impossible with single-day MarketData

**After (FIXED):** Single-day features only:
- `daily_return = (close - open) / open`
- Direction implied by sign of daily_return
- Complexity lowered from "complex" to "medium"

### B. Added Explicit Signal Generation Formula (v1 B2)

**Before:** No algorithm specified

**After (FIXED):**
```python
market_signal = clamp(daily_return * 10, -1, 1)
combined_score = sentiment_weight * sentiment.sentiment_score
                 + market_weight * market_signal
signal = "buy"  if combined_score >  +confidence_threshold
       = "sell" if combined_score <  -confidence_threshold
       = "hold" otherwise
```

### C. Added Confidence Derivation (v1 B3)

**Before:** No confidence formula

**After (FIXED):**
```python
market_confidence = clamp(abs(daily_return) * 10, 0, 1)
combined_confidence = sentiment_weight * sentiment.confidence
                     + market_weight * market_confidence
if sentiment.sentiment_score * market_signal < 0:
    combined_confidence *= 0.5   # disagreement penalty
```

### D. Fixed Dependency Chain (v1 B4)

**Before:** `dependencies: [Ticket 6]`

**After (FIXED):** `dependencies: [Ticket 2, Ticket 6]`

### E. Added Concrete Output Type (v1 B5)

**Before:** `-> dict`

**After (FIXED):**
```python
@dataclass
class TradingSignal:
    ticker: str
    signal: str               # "buy" | "sell" | "hold"
    confidence: float         # [0.0, 1.0]
    rationale: str            # template-based explanation
    sentiment_score: float    # pass-through from SentimentResult
    market_return: float | None  # (close - open) / open if market_data else None
```

### F. Expanded AC Coverage from 3 → 10 (v1 B6)

**Before (3 ACs):** Bare minimum: signal enum, confidence range, rationale exists

**After (10 ACs):**
- AC-01/02: Happy path buy/sell with exact inputs and verifiable outputs
- AC-03: Neutral/hold path
- AC-04/09: market_data=None path (sentiment-only, with and without low-confidence override)
- AC-05: Low-confidence override (confidence < threshold → hold)
- AC-06: Conflicting signal handling (disagreement halving)
- AC-07: Zero-open guard (division-by-zero prevention)
- AC-08: None input error handling
- AC-10: Rationale format verification

### G. Specified Rationale Format (v1 B7)

**Before:** "human-readable rationale" — any non-empty string passes

**After (FIXED):** Template:
```
"Sentiment {label} ({score:.2f}) with confidence {conf:.2f}. "
"Market return: {return:+.2%}. "
"Combined score: {combined:.2f}."
"{disagreement_note}"
" Signal: {signal}."
```

### H. Added Low-Confidence Override (v2 B1)

**Before:** Only `combined_score` thresholds controlled the signal — low confidence didn't prevent trading decisions

**After (FIXED):**
```python
if combined_confidence < confidence_threshold:
    signal = "hold"
elif combined_score > confidence_threshold:
    signal = "buy"
elif combined_score < -confidence_threshold:
    signal = "sell"
else:
    signal = "hold"
```

### I. Added market_data=None Branch (v2 B2)

**Before:** Formula assumed market_data is always present — would crash on None

**After (FIXED):**
```python
daily_return = 0.0  # default, safe for None or zero-open cases
if market_data is None:
    combined_score = sentiment.sentiment_score
    combined_confidence = sentiment.confidence
else:
    # ... market data path ...
```

### J. Fleshed Out AC Inputs (v2 B3)

**Before:** AC-01/02 missing `sentiment.confidence` — `confidence > 0.5` unverifiable

**After (FIXED):** Explicit values: `sentiment.confidence=0.8` in both AC-01 and AC-02, with market returns (+5%, -3%) chosen to produce clean verifiable results

### K. Fixed AC-07: Zero Volume → Zero Open (v2 Moderate)

**Before:** AC-07 tested zero volume — volume is not used in the formula

**After (FIXED):** AC-07 tests `open=0.0` — the actual division-by-zero risk

### L. Removed Dead Code: `daily_range` (v2 Moderate)

**Before:** `daily_range = (high - low) / open` computed but never used

**After (FIXED):** Removed from signal_logic

### M. Added sentiment_label Derivation (v3 B8)

**Before:** `{sentiment_label}` referenced in template but `SentimentResult` has no `label` field

**After (FIXED):**
```python
if sentiment.sentiment_score > 0:
    sentiment_label = "positive"
elif sentiment.sentiment_score < 0:
    sentiment_label = "negative"
else:
    sentiment_label = "neutral"
```

### N. Added Disagreement Note to Rationale (v3 B9)

**Before:** AC-06 required "rationale mentions the disagreement" but template had no component for it

**After (FIXED):**
```python
disagreement_note = (
    " Sentiment and market disagree — confidence halved."
    if market_data is not None and sentiment.sentiment_score * market_signal < 0
    else ""
)
```

### O. Fixed Unbound Variable: `daily_return` (v3 Moderate)

**Before:** `daily_return` defined inside `else` branch, referenced by ternary outside it

**After (FIXED):** `daily_return = 0.0` initialized before the if/else block

### P. Added `_clamp()` Helper (Implementation)

**Before:** `clamp()` referenced in signal_logic but no such function existed in the codebase

**After (FIXED):**
```python
def _clamp(value: float, lo: float, hi: float) -> float:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value
```

### Q. Added Explicit TypeError Guard (Implementation)

**Before:** No guard against `None` sentiment — would raise `AttributeError` from `None.sentiment_score`

**After (FIXED):**
```python
if sentiment is None:
    raise TypeError("sentiment must be a SentimentResult, got None")
```

### R. Fixed Pipeline Stage 5 Scoping (Implementation)

**Before:** `result = sentiment.analyze(fused)` scoped inside try block — Stage 6 couldn't access it

**After (FIXED):** `sentiment_result = None` initialized before the try block, assigned as `sentiment_result = sentiment.analyze(fused)` inside it

### S. Fixed AC-07 Test Depth (Code Review)

**Before:** `assert result.market_return is not None` — didn't verify the default was `0.0`

**After (FIXED):** Added `assert result.market_return == pytest.approx(0.0)`

### T. Refactored Tests to Use Fixtures (Code Review)

**Before:** 8 fixtures defined in `signal_data.py` but tests constructed data inline — fixtures were dead code

**After (FIXED):** All 25 tests refactored to consume fixtures; added 2 new fixtures (`sample_sentiment_result_strong_positive`, `sample_market_data_down_five`) for AC-06

### U. Added Docstrings (Code Review)

**Before:** No module/class/method docstrings in `signals.py`

**After (FIXED):** Added Google-style docstrings to `TradingSignal`, `_clamp()`, `TradingSignalGenerator`, and `generate()` — consistent with `sentiment.py`

---

## 4. Technical Issues Found During Implementation

### Dependency Analysis Discoveries

A detailed dependency analysis was performed before implementation, which surfaced several gaps not caught by the TDD spec review:

1. **Undefined `clamp()`** — The signal_logic formula referenced `clamp(daily_return * 10, -1, 1)` but no such function existed in any module. This is a small utility but shows that spec pseudocode can reference non-existent functions that no reviewer checked.

2. **TypeError vs AttributeError for AC-08** — AC-08 requires `TypeError` when `sentiment=None` is passed, but the natural behavior of `None.sentiment_score` raises `AttributeError`. An explicit guard is required. This is a correctness requirement that the spec states but reviewers didn't verify against Python's actual runtime behavior.

3. **Pipeline result scoping** — Stage 5's `result` variable was inside a `try` block. Stage 6 couldn't access it without a refactor. This demonstrates that pipeline integration data flow must be checked at the file level, not just the spec level.

### Source of Discovery

Unlike Ticket 6 (where implementation issues were found while writing MockTensor code), Ticket 7's implementation issues were all found by reading existing code and cross-referencing with the spec. The `clamp()`, `TypeError`, and scoping issues were all identified as gaps before any code was written, thanks to the dependency analysis.

### Mock Complexity is Lower Than Ticket 6

Signal generation is pure Python math — no torch dependency, no GPU concerns, no external API calls. This means:
- No `MockTensor` infrastructure needed
- No `sys.modules["torch"]` injection
- No `MagicMock.__call__` gotchas
- No complex mock side_effect overrides

Tests use real dataclass construction directly. This made implementation faster and tests more straightforward — the spec review and dependency analysis effort paid off during coding.

### Numerical Verification Prevented False Positives

Manually tracing every AC through the formula caught:
- AC-05 claiming "hold" for (score=0.8, conf=0.2) when formula produced "buy" (combined_score=0.4 > 0.3)
- AC-01/02 missing sentiment.confidence inputs making the `confidence > 0.5` assertion unverifiable

---

## 5. Final Implementation

### Files Created

```
src/model/pretrained/
├── signals.py                   # TradingSignal dataclass + TradingSignalGenerator

tests/
├── test_signals.py              # 25 tests (10 ACs, all using fixtures)
└── fixtures/
    └── signal_data.py           # 10 SentimentResult + MarketData fixtures
```

### Files Modified

```
src/model/pretrained/__init__.py  # Added TradingSignal, TradingSignalGenerator exports
src/model/__init__.py             # Re-exported signal classes at top level
tests/conftest.py                 # Added tests.fixtures.signal_data to pytest_plugins
src/pipeline.py                   # Stage 5 scoping fix + Stage 6 signal generation + CLI description
```

### Key Architecture

```python
class TradingSignalGenerator:
    def __init__(
        self,
        confidence_threshold: float = 0.3,
        sentiment_weight: float = 0.5,
        market_weight: float = 0.5,
    ):
        # Pure Python, no conditional imports needed
        # All parameters tunable

    def generate(
        self,
        ticker: str,
        sentiment: SentimentResult,
        market_data: MarketData | None,
    ) -> TradingSignal:
        # None check → TypeError (explicit guard for AC-08)
        # market_data=None → sentiment-only path
        # Compute daily_return with open=0 guard
        # _clamp() normalizes market return to [-1, 1]
        # Weighted combined score + confidence
        # Low-confidence override → hold
        # Disagreement halving when signs conflict
        # Template-based rationale
```

### Signal Logic Summary

| Aspect | Detail |
|--------|--------|
| Market features | `daily_return = (close - open) / open` |
| Market normalization | `_clamp(daily_return × 10, -1, 1)` |
| Combined score | `w_s × sentiment_score + w_m × market_signal` |
| Decision thresholds | `confidence_threshold` (default ±0.3) |
| Confidence | `w_s × sent.conf + w_m × market_conf` |
| Disagreement penalty | Sign mismatch → confidence halved |
| Low-confidence guard | `combined_confidence < threshold → hold` |
| Rationale | Template with label, score, confidence, return, combined_score, disagreement note |
| Division-by-zero | `open == 0 → daily_return = 0.0` |

---

## 6. Test Coverage

| Category | Tests | Covers ACs | Status |
|----------|-------|------------|--------|
| Buy Happy Path (signal, confidence, rationale) | 3 | AC-01 | ✅ |
| Sell Happy Path (signal, confidence) | 2 | AC-02 | ✅ |
| Hold Neutral | 1 | AC-03 | ✅ |
| Sentiment-Only (signal, confidence, market_return) | 3 | AC-04 | ✅ |
| Low-Confidence Override (signal, confidence) | 2 | AC-05 | ✅ |
| Disagreement Halving (confidence, signal, rationale) | 3 | AC-06 | ✅ |
| Zero Open Guard | 1 | AC-07 | ✅ |
| None Sentiment TypeError | 1 | AC-08 | ✅ |
| Sentiment-Only Low-Confidence (signal, confidence) | 2 | AC-09 | ✅ |
| Rationale Format (label, score, confidence, return, combined_score, signal, N/A) | 7 | AC-10 | ✅ |
| **Total** | **25** | **10 ACs** | ✅ |

### Fixtures (10 total)

- `sample_sentiment_result_positive` — SentimentResult(+0.7, 0.8)
- `sample_sentiment_result_strong_positive` — SentimentResult(+0.9, 0.8)
- `sample_sentiment_result_negative` — SentimentResult(-0.6, 0.8)
- `sample_sentiment_result_neutral` — SentimentResult(+0.05, 0.4)
- `sample_sentiment_result_low_confidence` — SentimentResult(+0.8, 0.2)
- `sample_sentiment_result_very_low_confidence` — SentimentResult(+0.7, 0.25)
- `sample_market_data_up` — MarketData with +5% return
- `sample_market_data_down` — MarketData with -3% return
- `sample_market_data_down_five` — MarketData with -5% return
- `sample_market_data_flat` — MarketData with 0% return
- `sample_market_data_zero_open` — MarketData with open=0.0

### Test Infrastructure

**Simpler than Ticket 6** — no torch mocking needed:
- Direct dataclass construction (no MockTensor)
- Pure Python assertion logic with `pytest.approx`
- Fixture-based test data (all tests consume fixtures from `signal_data.py`)
- No conditional imports required

---

## 7. Outstanding Issues

### Non-Blocking

- [ ] LOW: No integration test with real SentimentResult from FinBertSentiment — requires Ticket 6's module to be importable (needs torch in environment)
- [ ] LOW: `market_weight` unused when `market_data=None` — accepted, simplifies the code path

### Resolved During Review

- [x] Data model mismatch: "price trends" → single-day features
- [x] No signal generation formula → explicit weighted combination
- [x] No confidence derivation → combined_confidence formula with disagreement halving
- [x] Missing dependency (Ticket 2) → corrected to [Ticket 2, Ticket 6]
- [x] Dict output → TradingSignal dataclass
- [x] Only 3 ACs → expanded to 10 ACs
- [x] Rationale unspecified → template with all required fields
- [x] AC-05 vs formula (low-confidence override missing) → added guard
- [x] market_data=None path undefined → conditional branch
- [x] AC-01/02 underdetermined → explicit confidence values
- [x] AC-07 tested wrong risk → zero open instead of zero volume
- [x] dead `daily_range` code → removed
- [x] `sentiment_label` doesn't exist → derived from score
- [x] Disagreement note missing → added to rationale
- [x] `daily_return` unbound → initialized before if/else
- [x] `clamp()` doesn't exist in codebase → added `_clamp` helper
- [x] AC-08 needs explicit TypeError → added guard in `generate()`
- [x] Pipeline Stage 5 result scoping → `sentiment_result` extracted before try block
- [x] AC-07 test too shallow → added value assertion (`== 0.0`)
- [x] Unused fixture file → tests refactored to consume all fixtures
- [x] Missing docstrings → added Google-style docstrings

---

## 8. Lessons Learned

### What Went Well

1. **Iterative TDD review caught layered issues** — Each review round surfaced deeper, subtler problems. Round 1 found structural gaps (no formula, wrong deps). Round 2 found logical gaps (low-confidence override, None path). Round 3 found spec-reality mismatches (field doesn't exist, template component missing). This validates doing multiple review passes rather than trying to fix everything at once.

2. **Dependency analysis caught implementation gaps before coding** — A detailed codebase dependency analysis performed before implementation surfaced three issues that the TDD spec review missed: `clamp()` didn't exist, AC-08 needed explicit `TypeError` (not `AttributeError`), and pipeline result scoping. These were fixed before any code was written, preventing the mid-implementation surprises that plagued Ticket 6.

3. **Numerical verification prevented false ACs** — Manually computing each AC against the formula caught cases where the AC text claimed one thing but the math produced another (AC-05). Without this, those tests would have been written to match the wrong expected values, hiding bugs.

4. **Lower mock complexity than Ticket 6** — Signal generation is pure math with no torch/GPU/external dependencies. This makes implementation faster and tests more straightforward. The spec review and dependency analysis effort will pay off during coding.

5. **Pattern reuse from Ticket 6** — The `TradingSignal` dataclass follows the same pattern as `SentimentResult`/`ArticleSentiment`/`MarketData`. The dependency correction pattern (wrong → right) was applied from Ticket 6's lesson.

6. **Code review caught 3 real issues** — All 3 C.L.E.A.R. framework findings were legitimate: 1 test shallowness bug (AC-07 missing value assertion), 1 dead code issue (unused fixtures), and 1 documentation gap (missing docstrings). Compared to Ticket 6's code review (6 issues), Ticket 7 had fewer issues and lower severity, reflecting the simpler codebase and better spec quality.

### What Could Improve

1. **First-pass review depth** — The v1 reviewer found 7 blocking issues but missed the low-confidence override (found in v2) and the sentiment_label field (found in v3). A checklist of common AC pitfalls (input field existence, runtime crash scenarios, unbound variables) would help surface these in the first pass.

2. **Cross-reference ACs against data types** — The `sentiment_label` bug (referencing a field that doesn't exist on `SentimentResult`) could have been caught by systematically verifying each referenced symbol against its source type's definition. A tool or checklist for this would help.

3. **Template completeness check** — The disagreement note was missing from the rationale even though AC-06 required it. A simple "for each AC, check every component it references exists in the output" would catch this.

4. **Scope creep awareness** — Option B (multi-day trends) was discussed and rejected in favor of single-day features. Documenting the rationale for scope decisions (and their implications) would help future reviewers understand why the simpler path was chosen.

5. **Dependency analysis should be standard pre-implementation step** — The dependency analysis found 3 implementation-level gaps that the TDD spec review didn't catch. Making this a standard step before every implementation would reduce "mid-coding discoveries." This analysis is relatively quick (reading ~5 files, tracing imports, checking function existence) and has high ROI.

6. **Fixture-first test pattern** — The unused fixtures issue (code review finding) was because tests were written first with inline data, then fixtures were created but never integrated. Writing tests to consume fixtures from the start would prevent this. Alternatively, removing fixtures when tests don't use them keeps the codebase clean.

### Key Metrics

| Metric | Value |
|--------|-------|
| Original ACs | 3 |
| Refined ACs | 10 |
| TDD review rounds | 3 |
| Implementation issues found by dependency analysis | 3 |
| Code review rounds | 1 |
| Files created | 3 |
| Files modified | 4 |
| Total tests | 25 |
| Test fixtures | 10 |
| Spec + review effort | 3 TDD rounds + 1 code review |
| Issues found by TDD review | 12 blocking + 9 moderate |
| Issues found by dependency analysis | 3 (3 blocking) |
| Issues found by code review | 3 (2 medium, 1 low) |
| Mock complexity | None (pure Python) |

---

## 9. Acceptance Criteria Verification

| AC | Test(s) | Verification Method | Status |
|----|---------|---------------------|--------|
| AC-01 | `TestAC01BuyHappyPath` (3 tests) | Numerical: combined_score=0.6 > 0.3 → "buy", combined_confidence=0.65 > 0.5 | ✅ |
| AC-02 | `TestAC02SellHappyPath` (2 tests) | Numerical: combined_score=-0.45 < -0.3 → "sell", combined_confidence=0.55 > 0.5 | ✅ |
| AC-03 | `TestAC03HoldNeutral` (1 test) | Numerical: combined_score=0.025 < 0.3 → "hold", combined_confidence=0.2 < 0.3 | ✅ |
| AC-04 | `TestAC04MarketDataNone` (3 tests) | Numerical: market_data=None → combined_confidence=0.8 = sentiment.confidence, combined_score=0.7 > 0.3 → "buy" | ✅ |
| AC-05 | `TestAC05LowConfidenceOverride` (2 tests) | Numerical: combined_confidence=0.1 < 0.3 → "hold" (overrides combined_score=0.4) | ✅ |
| AC-06 | `TestAC06DisagreementHalving` (3 tests) | Numerical: disagreement → conf halved (0.65→0.325), combined_score=0.2 < 0.3 → "hold" | ✅ |
| AC-07 | `TestAC07ZeroOpenGuard` (1 test) | Structural: open=0.0 guard prevents ZeroDivisionError, daily_return=0.0 | ✅ |
| AC-08 | `TestAC08NoneSentiment` (1 test) | Structural: `if sentiment is None: raise TypeError(...)` at top of `generate()` | ✅ |
| AC-09 | `TestAC09MarketDataNoneLowConfidence` (2 tests) | Numerical: market_data=None, combined_confidence=0.25 < 0.3 → "hold" | ✅ |
| AC-10 | `TestAC10RationaleFormat` (7 tests) | Structural: rationale template contains all 6 required fields + "N/A" for no-market-data case | ✅ |

---

## 10. Timeline

| Date | Activity |
|------|----------|
| May 28, 2026 | Original ticket loaded (3 ACs, wrong dependency, no formula, dict output) |
| May 28, 2026 | TDD review round 1 (NEEDS REVISION — 7 blocking + 6 moderate issues) |
| May 28, 2026 | Fixed v1: single-day features, weighted formula, confidence derivation, TradingSignal dataclass, expanded to 10 ACs, rationale template, corrected dependencies |
| May 28, 2026 | TDD review round 2 (NEEDS REVISION — 3 new blocking issues) |
| May 28, 2026 | Fixed v2: low-confidence override, market_data=None branch, explicit AC inputs, zero-open guard, removed dead code |
| May 28, 2026 | TDD review round 3 (NEEDS REVISION — 2 new blocking issues) |
| May 28, 2026 | Fixed v3: sentiment_label derivation, disagreement note in rationale, unbound variable guard |
| May 28, 2026 | TDD review round 4 (APPROVE — 0 blocking issues) |
| May 28, 2026 | Dependency analysis performed — found 3 gaps (clamp missing, TypeError vs AttributeError, pipeline scoping) |
| May 28, 2026 | **Implementation**: signals.py, fixtures/signal_data.py, test_signals.py, conftest, __init__.py files, pipeline.py |
| May 28, 2026 | **Code review round 1**: 3 issues (shallow AC-07 test, unused fixtures, missing docstrings) |
| May 28, 2026 | **Fixed**: AC-07 test deepened, tests refactored to consume fixtures, docstrings added |
| May 28, 2026 | Post-mortem updated |

---

## 11. Next Steps

1. Mark Ticket 7 as ✅ COMPLETE in tickets index document
2. Proceed to downstream generation ticket that consumes TradingSignal
3. Consider adding dependency analysis as a standard pre-implementation step in project workflow documentation
