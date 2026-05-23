# Post-Mortem: Ticket 2 — Market Data Collection

**Date:** April 16, 2026  
**Status:** ✅ IMPLEMENTED  
**Review Status:** APPROVE (after fixes)

---

## 1. Overview

### Original Ticket
**Title:** Collect market data from free-tier financial APIs

**Original Acceptance Criteria (ambiguous):**
```markdown
- Given a ticker symbol, When data is fetched, Then OHLCV data is returned with timestamp
- Given rate limit exhaustion, When data is requested, Then request is queued and processed when limits reset
- Given malformed response, When data is received, Then appropriate error is logged and exception raised
```

### Refined Acceptance Criteria (after TDD review)

```markdown
- Given ticker "AAPL" and date, When fetch_market_data("AAPL", date) is called,
  Then returns {open, high, low, close, volume, adjusted_close, timestamp} where timestamp is ISO8601

- Given rate limiter at capacity (0 tokens), When a request is made,
  Then client blocks until token available (via TokenBucketRateLimiter.acquire())

- Given response missing required field 'close', When response is parsed,
  Then MarketDataParseError is raised with message "Missing required field: close"
  and error is logged at ERROR level with response snippet

- Given HTTP 200 with API error code in body, When response is parsed,
  Then MarketDataAPIError is raised with the error message from API

- Given Yahoo Finance returns HTTP 429, When 3 retries exhausted, Then fallback to Alpha Vantage

- Given Yahoo + Alpha Vantage fail, When 3 retries each, Then fallback to Finnhub

- Given all 3 providers fail, When fetch_market_data is called,
  Then MarketDataUnavailableError is raised after exhausting all fallbacks

- Given weekend date (Saturday), When fetch_market_data is called,
  Then auto-rolls to previous Friday

- Given holiday date, When fetch_market_data is called,
  Then auto-rolls to previous trading day
```

---

## 2. Problems Identified

### TDD Review Round 1 — NEEDS REVISION

| Issue | Severity | Problem |
|-------|----------|---------|
| AC-002 "queued" ambiguous | **Blocking** | Implies async queue, but TokenBucketRateLimiter uses blocking |
| AC-003 exceptions undefined | **Blocking** | No exception types specified |
| API schema inconsistent | **Blocking** | No unified schema for OHLCV transformation |
| Fallback conditions undefined | **Blocking** | Cannot write tests without knowing trigger conditions |
| API response formats missing | **Blocking** | Tests cannot mock without knowing provider formats |

### TDD Review Round 2 — READY FOR IMPLEMENTATION

After adding:
- API response schemas for Yahoo, Alpha Vantage, Finnhub
- Explicit fallback conditions (429/4xx/5xx → next provider)
- Custom exception definitions
- Weekend/holiday handling specification

---

## 3. Technical Issues Found During Review

### Code Review Round 1 — NEEDS_WORK

| Severity | Finding | Location |
|----------|---------|----------|
| **Critical** | Python 2 syntax: `except A, B:` (invalid in Python 3) | `market_data.py:169` |
| **Critical** | Python 2 syntax in transformers | `transformers.py:170, 178` |
| Low | Ruff didn't catch Python 2 exception syntax | N/A |

---

## 4. Fixes Applied

### A. Refined Acceptance Criteria

**Before (ambiguous):**
```markdown
- request is queued and processed when limits reset
```

**After (clear):**
```markdown
- client blocks until token available (via TokenBucketRateLimiter.acquire())
```

### B. Added API Response Formats

```python
# Yahoo Finance v8
{
  "chart": {
    "result": [{
      "timestamp": [1705276800, ...],
      "indicators": {
        "quote": [{
          "open": [185.50, ...],
          "high": [187.20, ...],
          "low": [184.80, ...],
          "close": [185.50, ...],
          "volume": [45000000, ...]
        }]
      }
    }]
  }
}

# Alpha Vantage TIME_SERIES_DAILY
{
  "Time Series (Daily)": {
    "2024-01-15": {
      "1. open": "185.50",
      "2. high": "187.20",
      "3. low": "184.80",
      "4. close": "185.50",
      "5. volume": "45000000"
    }
  }
}

# Finnhub stock/candle
{
  "c": [185.50, 186.75],   // Close
  "h": [187.20, 188.10],   // High
  "l": [184.80, 185.50],   // Low
  "o": [185.00, 186.20],   // Open
  "v": [45000000, ...],     // Volume
  "t": [1705276800, ...],   // Timestamps
  "s": "ok"                 // Status
}
```

### C. Bug Fix: Python 2 Exception Syntax

**Before (INVALID in Python 3):**
```python
except MarketDataParseError, MarketDataAPIError:
    return None
```

**After (FIXED):**
```python
except (MarketDataParseError, MarketDataAPIError):
    return None
```

### D. Added Fallback Conditions

```python
FALLBACK_TRIGGERS:
  - HTTP 429 (rate limit exceeded)
  - HTTP 4xx/5xx errors
  - MarketDataAPIError (API error code in response body)
  - MarketDataParseError (malformed response)

FALLBACK_SEQUENCE:
  Yahoo Finance → Alpha Vantage → Finnhub → MarketDataUnavailableError
```

---

## 5. Final Implementation

### Files Created

```text
src/collect/
├── __init__.py              # Updated with market data exports
├── exceptions.py            # Custom exception hierarchy (4 classes)
├── transformers.py          # API-specific normalizers (271 lines)
└── market_data.py           # Collector with fallback (284 lines)

tests/
├── conftest.py              # Updated to import market_data fixtures
├── test_market_data.py      # Collector tests (11 tests)
├── test_transformers.py     # Transformer tests (13 tests)
└── fixtures/
    └── market_data.py       # Mock API responses (11 fixtures)

.env.example                 # API key template
.gitignore                  # Updated to exclude .env files
```

### Key Code: Exception Hierarchy

```python
class MarketDataError(Exception):
    """Base exception for all market data errors."""
    pass

class MarketDataParseError(MarketDataError):
    """Raised when response parsing fails (missing fields, wrong types)."""
    pass

class MarketDataAPIError(MarketDataError):
    """Raised when API returns error code in response body."""
    pass

class MarketDataUnavailableError(MarketDataError):
    """Raised when all data sources fail."""
    pass
```

### Key Code: Collector with Fallback

```python
class MarketDataCollector:
    async def fetch(self, ticker: str, target_date: date | None = None) -> MarketData:
        adjusted_date = self._adjust_to_trading_day(target_date or date.today())
        
        providers = [
            ("Yahoo Finance", self._fetch_from_yahoo),
            ("Alpha Vantage", self._fetch_from_alpha_vantage),
            ("Finnhub", self._fetch_from_finnhub),
        ]
        
        errors: list[str] = []
        for provider_name, fetch_func in providers:
            try:
                result = await fetch_func(ticker, adjusted_date)
                if result is not None:
                    return result
            except MarketDataError as exc:
                errors.append(f"{provider_name}: {exc}")
        
        raise MarketDataUnavailableError(
            f"All providers failed. Errors: {errors}"
        )
```

### Key Code: Transformers

```python
def transform_yahoo_finance(response: dict, target_date: str) -> dict:
    # Parse Yahoo v8 chart format
    # Extract OHLCV arrays
    # Find closest trading day to target_date
    # Return normalized dict

def transform_alpha_vantage(response: dict, target_date: str) -> dict:
    # Parse TIME_SERIES_DAILY format
    # Handle "1. open" → "open" field mapping
    # Return normalized dict

def transform_finnhub(response: dict, target_date: str) -> dict:
    # Parse candle format [c, h, l, o, v, t]
    # Return normalized dict
```

---

## 6. Test Coverage

| Category | Tests | Status |
|----------|-------|--------|
| Date Adjustment | 4 | ✅ |
| Market Data Collector | 6 | ✅ |
| Market Data Schema | 1 | ✅ |
| Yahoo Transformer | 5 | ✅ |
| Alpha Vantage Transformer | 5 | ✅ |
| Finnhub Transformer | 3 | ✅ |
| **Total** | **24** | ✅ |

**Total Test Results:** 49 passed (24 new + 25 from Ticket 1)

---

## 7. Outstanding Issues

### None (all resolved)

- [x] Python 2 exception syntax fixed
- [x] All acceptance criteria covered
- [x] API response formats documented

---

## 8. Lessons Learned

### What Went Well

1. **API research upfront** — Searching for actual provider formats prevented guesswork
2. **Incremental TDD reviews** — Multiple review rounds caught ambiguities early
3. **Comprehensive fixtures** — 11 mock fixtures enabled thorough testing
4. **Clear fallback logic** — Sequential provider list made behavior predictable

### What Could Improve

1. **Fixture auto-discovery** — Had to manually add imports to conftest.py
2. **Ruff Python 2 syntax detection** — Linter didn't catch `except A, B:` pattern
3. **Type hints in fixtures** — Fixtures typed as `dict` instead of `dict[str, Any]`

---

## 9. Acceptance Criteria Verification

| AC | Verification Method | Status |
|----|---------------------|--------|
| AC-001 | `test_fetch_yahoo_success` validates all 7 fields | ✅ |
| AC-002 | Reuses TokenBucketRateLimiter from Ticket 1 | ✅ |
| AC-003 | `test_transform_*_missing_close` | ✅ |
| AC-004 | `test_transform_alpha_vantage_api_error` | ✅ |
| AC-005 | `test_fallback_to_alpha_vantage` | ✅ |
| AC-006 | `test_fallback_to_finnhub` | ✅ |
| AC-007 | `test_all_providers_fail` | ✅ |
| AC-008 | `test_adjust_saturday_to_friday` | ✅ |
| AC-009 | `test_adjust_holiday_to_previous_day` | ✅ |

---

## 10. Timeline

| Date | Activity |
|------|----------|
| Apr 16, 2026 | Ticket created from PRD |
| Apr 16, 2026 | TDD review round 1 (NEEDS REVISION) |
| Apr 16, 2026 | Clarified: blocking behavior, exceptions, fallback order |
| Apr 16, 2026 | TDD review round 2 (READY) |
| Apr 16, 2026 | Implementation: exceptions, transformers, collector |
| Apr 16, 2026 | Tests: fixtures, test_market_data.py, test_transformers.py |
| Apr 16, 2026 | First test run: 4 failures (fixtures not discovered) |
| Apr 16, 2026 | Fixed: added fixture imports to conftest.py |
| Apr 16, 2026 | Second test run: 4 failures (Python 2 syntax) |
| Apr 16, 2026 | Fixed: `except A, B:` → `except (A, B):` |
| Apr 16, 2026 | Final test run: 49 passed |
| Apr 16, 2026 | Code review: APPROVE |
| Apr 16, 2026 | Post-mortem created |

---

## 11. Next Steps

1. Update `docs/context/financial-analysis-tickets.md` to mark Ticket 2 as ✅ IMPLEMENTED
2. Proceed to Ticket 3: News Data Collection
3. Consider adding fixture auto-discovery to test framework
