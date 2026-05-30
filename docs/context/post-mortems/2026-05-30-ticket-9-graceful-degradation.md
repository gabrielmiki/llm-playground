# Post-Mortem: Ticket 9 — Graceful Degradation & Error Handling

**Date:** May 30, 2026  
**Status:** ✅ COMPLETE  
**Review Status:** APPROVE (after 4 TDD review rounds + 2 code review rounds)

---

## 1. Overview

### Original Ticket
**Title:** Implement graceful degradation when data sources fail

**Original Acceptance Criteria (3 ACs, minimal detail):**
```markdown
- Given market data unavailable, When processing ticker, Then historical data is used as fallback
- Given all data sources fail for ticker, When processing, Then "insufficient_data" status is set
- Given any degradation, When report is generated, Then warnings section clearly lists all issues
```

**Original api_spec:**
```
Input: pipeline state (market_data, news_articles)
Output: FusedRecord with warnings + substituted data
```

### Refined Acceptance Criteria (8 ACs after 4 TDD review rounds)

```
AC-01:  Market data fails (all 3 providers), historical cache exists within 5-day lookback
        → historical market_data substituted, degraded_market warning appended
AC-02:  News fails (both providers), historical cache exists within 5-day lookback
        → historical news_articles substituted, degraded_news warning appended
AC-03:  Market data fails, no historical cache within 5-day lookback
        → market_data stays None, fallback_failed warning, pipeline continues
AC-04:  Both market AND news fail, fallback unavailable
        → insufficient_data warning, pipeline completes with None/empty values
AC-05:  Market fails but news succeeds
        → market uses fallback, news normal, both reflected in warnings/output
AC-06:  News fails but market succeeds
        → news uses fallback, market normal, both reflected in warnings/output
AC-07:  Multiple tickers with mixed failure modes in batch pipeline
        → each ticker independently handles degradation, aggregated warnings in report
AC-08:  Any degradation occurred, report generated via existing ReportGenerator
        → warnings present in all 3 formats (text: "- {message}", HTML: <div class="warning">,
          JSON: category/field/message/value)
```

---

## 2. Problems Identified

### TDD Review Round 1 — NEEDS REVISION (3 blocking + 5 moderate issues)

The initial ticket had only 3 vague ACs, an undefined fallback mechanism, and no specification for how degradation would be represented in the existing data model:

#### Blocking Issues

| Issue | Severity | Problem |
|-------|----------|---------|
| "Historical data" undefined | **Blocking** | No source, format, or selection strategy specified. Current pipeline crashes hard on `MarketDataUnavailableError` and `NewsDataUnavailableError` — no fallback mechanism exists anywhere |
| "insufficient_data status" does not exist | **Blocking** | No `status` field exists on `FusedRecord`, `MarketData`, or any dataclass. Adding one would require changes across multiple files. "All data sources" ambiguous (market? news? both?) |
| Zero edge case coverage | **Blocking** | 3 ACs cover only idealized paths. Missing: partial degradation, historical data also unavailable, first-run behavior, multi-ticker mixed failures, consecutive-day degradation |

#### Moderate Issues

| Issue | Severity | Problem |
|-------|----------|---------|
| Layer ambiguity | **Moderate** | Ticket says `layer: generate` but fallback logic must live where collection exceptions are caught (`pipeline.py`, which orchestrates the collect/preprocess stages) |
| Missing dependency | **Moderate** | Requires Ticket 8 for `load_fused_record()` and the existing warning rendering pipeline |
| Degradation warning format unspecified | **Moderate** | No category conventions defined for what degradation warnings should look like in the existing `ValidationWarning` format |
| Pipeline already has silent failure handling | **Moderate** | `pipeline.py` already catches `MarketDataUnavailableError` and `NewsDataUnavailableError` but generates NO warnings — degradation is invisible today |
| No test structure guidance | **Moderate** | Prior tickets specified exact files, test counts, and fixtures — this ticket provided none |

---

### TDD Review Round 2 — READY (5 green findings)

After fixing all Round 1 issues, the re-review found no blocking or moderate issues. Five non-blocking (green) findings remained:

| Issue | Severity | Problem |
|-------|----------|---------|
| Warning handoff not explicit | **Green** | Pseudocode showed `warnings.append(...)` but didn't show how degradation warnings get into `FusedRecord.warnings` |
| Pre-existing bug exposure | **Green** | Pipeline crashes if `market_data is None` reaches `MarketDataValidator` (pre-existing, now exposed by AC-03/04) |
| Historical "validity" undefined | **Green** | "Use the first valid FusedRecord" — no definition of what counts as valid |
| AC-01/02 wording vague | **Green** | "recent trading day" should cross-reference the exact 5-day lookback definition |
| AC-08 rendering format ambiguous | **Green** | Text/HTML format rendering unspecified — could conflict with existing `reporter.py` behavior |

---

### TDD Review Round 3 — NEEDS REVISION (1 new blocking + 3 non-blocking issues)

After fixing all Round 2 green findings, one new blocking issue was introduced by the AC-08 clarity fix:

| Issue | Severity | Problem | Fix |
|-------|----------|---------|-----|
| AC-08 contradicts "Files Not Modified" | **Blocking** | AC-08 demanded `- {category}: {message}` in text format but existing `reporter.py` renders `- {message}`. Ticket claimed reporter.py is not modified. Three-way conflict: AC-08 text requirement ≠ current code ≠ "no changes" claim | Relax AC-08 to match existing reporter behavior |
| Missing `value=None` in pseudocode | **Moderate** | `ValidationWarning` dataclass has 4 required fields (`category`, `field`, `message`, `value`). All 6 pseudocode invocations passed only 3 args — would crash at runtime | Add `value=None` to all calls |
| Trading-day divergence | **Low** | Two different implementations exist: `market_data.py` uses holiday-aware instance method; `news_collector.py` uses weekends-only module function. Ticket said "same logic" but there are two diverging implementations | Specify weekends-only from `news_collector.py` |
| AC-07 mock strategy unspecified | **Low** | Multi-ticker batch test requires per-ticker mock configuration — could be complex without guidance | Add monkeypatch/dependency-injection note |

---

### TDD Review Round 4 — APPROVE (0 blocking, 0 moderate issues)

After fixing all Round 3 issues, the final verification confirmed:
- All 3 Round 1 blocking issues resolved
- All 5 Round 2 green findings resolved
- All 1 Round 3 blocking issue and 3 non-blocking issues resolved
- All 8 ACs independently testable
- No contradictions with existing infrastructure

---

### Code Review Round 1 — 6 Issues Found (C.L.E.A.R. Framework)

After implementation, the code review identified several quality issues:

| Severity | Finding | Location | Fix |
|----------|---------|----------|-----|
| **Medium** | `build_degradation_warning()` accepts `ticker` and `target_date` params but never uses them in messages — misleading API contract | `src/generate/degradation.py:23-28` | Include ticker/date in fallback_failed messages (e.g., `"Market data unavailable for AAPL on 2026-05-22 and no historical fallback found"`) |
| **Medium** | `WARNING_FIELDS` constant defined but never referenced — dead code | `src/preprocess/fusion.py:11` | Remove the unused constant |
| **Low** | `_get_weekday_adjustment = get_weekday_adjustment` alias adds unnecessary indirection after extracting to `date_utils.py` | `src/collect/news_collector.py:38` | Replace alias with direct import; update call sites |
| **Low** | `test_per_ticker_independent_market_lookback` tests per-ticker lookup via separate directories (not realistic shared-dir layout like real `data/processed/fused/`) | `tests/test_degradation.py:382` | Add `test_per_ticker_in_shared_directory` with both tickers in the same tmp_path |
| **Low** | No integration test for `pipeline.py` exception handler flow (try→fallback→warn→continue) | `src/pipeline.py:82-112` | Add `TestPipelineIntegration` with 4 tests composing fallback + warning + fusion |
| **Low** | Docstring still references old `news_collector._get_weekday_adjustment()` | `src/generate/degradation.py:125` | Update to `date_utils.get_weekday_adjustment()` |

### Code Review Round 1 Re-check — 1 Regression

After applying fixes, the re-review found:

| Severity | Finding | Location | Fix |
|----------|---------|----------|-----|
| **High** | Test import fix dropped `fetch_news` from imports — `TestFetchNews.test_creates_and_closes_client` fails with NameError | `tests/test_news_collector.py:11` | Add `fetch_news` back; remove duplicate `transform_finnhub_news`/`transform_newsapi` imports (already imported from `news_transformers`) |
| **Low** | PEP 8: 3 blank lines before class definition (was 2 + removed alias line) | `src/collect/news_collector.py:36-39` | Trim to 2 blank lines |

All issues resolved, verdict **APPROVE**.

---

## 3. Fixes Applied

### A. Defined Historical Fallback (v1 B1)

**Before (undefined):**
```text
"Use historical data as fallback"
```

**After (FIXED):**
- **Source**: `data/processed/fused/` directory (same as `load_fused_record()`)
- **Scan strategy**: Look back up to 5 previous trading days, using weekends-only adjustment (Saturday → Friday, Sunday → Friday) matching `news_collector.py`'s `_get_weekday_adjustment()`
- **Validity**: File must exist, parse as valid JSON, and contain non-`None` value for the field being substituted
- **Selective substitution**: If market data failed, substitute only `market_data`. If news failed, substitute only `news_articles`. If both failed, substitute both
- **First run**: Issue `fallback_failed` warning and proceed with `None`

### B. Replaced "insufficient_data status" with ValidationWarning Categories (v1 B2)

**Before:** AC referenced a non-existent `status` field — would have required new dataclass field on `FusedRecord`

**After (FIXED):** No new fields. Four `ValidationWarning` categories:

| Category | Meaning |
|----------|---------|
| `degraded_market` | Market data failed, historical fallback used successfully |
| `degraded_news` | News data failed, historical fallback used successfully |
| `fallback_failed` | Fallback attempted but no cached data found |
| `insufficient_data` | Both market AND news unavailable with no fallback |

Flow: `FusedRecord.warnings → ReportInput.warnings → ReportGenerator` — all existing infrastructure.

### C. Expanded AC Coverage from 3 → 8 (v1 B3)

**Before (3 ACs):** Idealized scenarios only — no partial failures, no first-run, no edge cases

**After (8 ACs):** Complete coverage:
- AC-01/02: Happy path (fallback succeeds for market/news)
- AC-03/04: Error path (fallback fails, insufficient data)
- AC-05/06: Mixed/partial (one source fails, other succeeds)
- AC-07: Batch (multi-ticker mixed failures)
- AC-08: Report rendering (warnings appear in all 3 formats)

### D. Scoped to Generate Layer + pipeline.py (v1 M1)

**Before:** `layer: generate` — ambiguous whether fallback logic lives entirely in `src/generate/`

**After (FIXED):**
- `src/generate/degradation.py` — fallback coordinator (`find_historical_fallback()`, `build_degradation_warnings()`)
- `src/pipeline.py` — modified catch blocks to call fallback, build warnings, continue

### E. Added Ticket 8 to Dependencies (v1 M2)

**Before:** `dependencies: [Ticket 2, Ticket 3, Ticket 4]`

**After (FIXED):** `dependencies: [Ticket 2, Ticket 3, Ticket 4, Ticket 8]`

Ticket 8 provides:
- `load_fused_record()` for reading historical data from `data/processed/fused/`
- `ReportInput.warnings` and `ReportGenerator` for warning rendering in reports

### F. Defined Degradation Warning Category Conventions (v1 M3)

**Before:** No specification of what degradation warnings look like

**After (FIXED):** Four categories defined (see Section B), each with convention for `category`, `field`, and `message` fields in `ValidationWarning`.

### G. Specified Pipeline Catch → Fallback → Warn → Continue Flow (v1 M4)

**Before:** `pipeline.py` catches exceptions silently and halts

**After (FIXED):** Explicit pseudocode:
```
Stage 1 (market_data.fetch):
  try: market_data = await collector.fetch(ticker)
  except MarketDataUnavailableError:
      historical = find_historical_fallback(ticker, date, "market")
      if historical and historical.market_data is not None:
          market_data = historical.market_data + degraded_market warning
      else:
          market_data = None + fallback_failed warning

Stage 2 (news.fetch):
  same pattern with NewsDataUnavailableError and "news" target

Post-both:
  if market_data is None and not news_articles:
      insufficient_data warning

→ Skip MarketDataValidator when market_data is None (guard)
→ Merge degradation_warnings into FusedRecord.warnings
→ Continue to fusion / sentiment / signal / report as normal
```

### H. Made Warning Handoff Explicit (v2 G1)

**Before:** `warnings.append(...)` in pseudocode but no merge point shown

**After (FIXED):** Pseudocode shows `degradation_warnings` list accumulated in stages 1-2, then merged into `fused_record.warnings = degradation_warnings` at `FusedRecord` construction time.

### I. Added None Validation Guard (v2 G2)

**Before:** No guard — `market_data = None` reaching `MarketDataValidator` would crash

**After (FIXED):** `→ Proceed to validation stage with guards: market_data = None → skip MarketDataValidator`

### J. Added Historical Validity Criteria (v2 G3)

**Before:** "Use the first valid FusedRecord" — undefined

**After (FIXED):** Three conditions: (1) file exists, (2) parses as valid JSON, (3) contains non-`None` value for the field being substituted.

### K. Cross-Referenced 5-Day Lookback in ACs (v2 G4)

**Before:** Both AC-01 and AC-02 said "recent trading day" — ambiguous

**After (FIXED):** Both cross-reference "(see Historical Fallback Definition)" which specifies the 5-day lookback window.

### L. Matched AC-08 to Existing reporter.py Behavior (v3 B1)

**Before:** AC-08 demanded `- {category}: {message}` in text format — but existing `reporter.py` renders `- {message}`. Ticket claimed `reporter.py` is not modified.

**After (FIXED):**
```
text:  "- {message}"   (matches existing reporter.py:73)
HTML:  "<div class=\"warning\">" with message (matches existing reporter.py:129)
JSON:  category, field, message, value fields (matches existing reporter.py:95-102)
```
No changes to `reporter.py` needed.

### M. Added `value=None` to Pseudocode (v3 M1)

**Before:** All 6 `ValidationWarning(...)` calls used 3 positional args — would crash at runtime

**After (FIXED):** Every call includes `value=None` as 4th argument, matching the `ValidationWarning(category, field, message, value)` signature.

### N. Specified Weekends-Only Adjustment (v3 M2)

**Before:** "(using the same trading-day adjustment logic from `market_data.py` / `news_collector.py`)" — ambiguous, two diverging implementations exist

**After (FIXED):** Explicit: "using weekends-only adjustment: Saturday → Friday, Sunday → Friday — matching `news_collector.py`'s `_get_weekday_adjustment()`"

### O. Added AC-07 Mock Strategy Note (v3 M3)

**Before:** No guidance on how to test multi-ticker batch pipeline with per-ticker mock configuration

**After (FIXED):** Appended: "(note: test implementation should use monkeypatch or dependency injection to simulate per-ticker collector failures)"

### P. Used `ticker`/`target_date` in Warning Messages (Code Review R1)

**Before:** Fallback_failed messages were generic — `"Market data unavailable and no historical fallback found"`
**After (FIXED):** Messages include ticker and date — `"Market data unavailable for AAPL on 2026-05-22 and no historical fallback found"`

### Q. Removed Dead `WARNING_FIELDS` Constant (Code Review R1)

**Before:** `WARNING_FIELDS = ("category", "field", "message", "value")` defined but never referenced
**After (FIXED):** Deleted the unused constant.

### R. Replaced `_get_weekday_adjustment` Alias with Direct Import (Code Review R1)

**Before:** `_get_weekday_adjustment = get_weekday_adjustment` alias in `news_collector.py`
**After (FIXED):** Alias removed; call site uses `get_weekday_adjustment` directly.

### S. Extracted Shared `date_utils.py` (Implementation)

**Before:** Weekend-adjustment logic was private inside `news_collector.py` — not importable from `src/generate/degradation.py`
**After (FIXED):** Extracted `get_weekday_adjustment()` to `src/collect/date_utils.py` — public, reusable, imported by both `news_collector.py` and `degradation.py`.

### T. Extracted Public `decode_fused_record()` (Implementation)

**Before:** Privately defined in `src/generate/orchestrate.py` — duplicated JSON→FusedRecord conversion logic
**After (FIXED):** Moved to `src/preprocess/fusion.py` — shared public function used by both `orchestrate.py` and `degradation.py`.

---

## 4. Technical Issues Found During Implementation

### Dependency Analysis Discoveries (Pre-Implementation)

A detailed cross-reference of the ticket against existing code revealed several gaps:

1. **ValidationWarning signature mismatch** — The pseudocode created `ValidationWarning("category", "field", "message")` with 3 positional args. The actual `ValidationWarning` dataclass has 4 required fields: `category`, `field`, `message`, `value` (no defaults). All 6 invocations would raise `TypeError` at runtime. This was caught in Round 3 review by verifying the dataclass definition directly.

2. **reporter.py rendering conflict** — AC-08 demanded `- {category}: {message}` text format, but the actual `reporter.py` (lines 70-75) renders `- {w.message}` without category. The HTML format similarly only showed `{w.message}` inside the warning div. The JSON format was correct (includes all 4 fields). This was caught only when the infrastructure verification in Round 3 cross-referenced AC-08 against the actual code.

3. **Trading-day implementation divergence** — `market_data.py` uses a holiday-aware `_adjust_to_trading_day()` instance method (considers holidays via calendar logic), while `news_collector.py` uses a weekends-only `_get_weekday_adjustment()` module function. The ticket initially referenced both, but neither is importable from `src/generate/degradation.py` without refactoring. Specifying weekends-only removed the ambiguity.

4. **Pipeline silence** — Reading `src/pipeline.py:71-81` revealed that `MarketDataUnavailableError` and `NewsDataUnavailableError` are already caught, but the catch blocks set data to `None`/`[]` without generating any warnings. The existing behavior is effectively silent degradation — the ticket's real work is making it visible.

### Source of Discovery (Pre-Implementation)

| Finding | Discovery Method |
|---------|-----------------|
| ValidationWarning has 4 required fields | Reading `src/preprocess/validator.py:14` |
| reporter.py renders `- {w.message}` not `- {category}: {message}` | Reading `src/generate/reporter.py:73` |
| Two diverging trading-day implementations | Reading `market_data.py:90` vs `news_collector.py:37` |
| Pipeline catch blocks are silent | Reading `src/pipeline.py:71-81` |

### Implementation Discoveries

During implementation, two refactoring needs emerged beyond the ticket scope:

| Issue | Severity | Problem | Fix |
|-------|----------|---------|-----|
| `_get_weekday_adjustment()` not importable from `src/generate/` | **Medium** | `degradation.py` needed weekend adjustment logic but `news_collector.py`'s function was private to the `collect` layer | Extracted `get_weekday_adjustment()` to new `src/collect/date_utils.py` — public, importable from any layer |
| Private `_decode_fused_record` duplicated in `orchestrate.py` | **Medium** | Both `orchestrate.py` and future `degradation.py` needed JSON→FusedRecord deserialization — would require duplicating or sharing a private function | Extracted `decode_fused_record()` to `src/preprocess/fusion.py` — natural home alongside the `FusedRecord` dataclass |

### Code Review Discoveries (Post-Implementation)

| Finding | Discovery Method |
|---------|-----------------|
| Unused `ticker`/`target_date` params in `build_degradation_warning()` | Reading `src/generate/degradation.py:23-28` |
| Dead `WARNING_FIELDS` constant | Reading `src/preprocess/fusion.py:11` |
| Unnecessary `_get_weekday_adjustment` alias | Reading `src/collect/news_collector.py:38` |
| Per-ticker test uses separate directories (unrealistic) | Reading `tests/test_degradation.py:382` |
| No integration test for pipeline.py handlers | Reviewing test coverage gaps |
| Stale docstring referencing old location | Reading `src/generate/degradation.py:125` |

### Spec-Phase Only Achievement

Ticket 9 is the first ticket in the series to have all structural issues found during the spec-review phase (no code changes needed to fix spec bugs). The implementation phase only introduced:
- One code quality regression (dropped `fetch_news` import)
- Two design improvements (extracting `date_utils.py` and `decode_fused_record()`)

---

## 5. Final Implementation

### Files Created

```
src/generate/degradation.py        # Fallback coordinator: find_historical_fallback(),
                                    #   build_degradation_warning(), build_insufficient_data_warning(),
                                    #   _load_fused_file(), _field_is_valid()
src/collect/date_utils.py          # get_weekday_adjustment() — weekends-only adjustment

tests/test_degradation.py          # 33 tests covering all 8 ACs + integration composition
tests/fixtures/degradation_data.py # 5 fixtures + write_fused_records() + _fused_to_dict()
```

### Files Modified

```
src/pipeline.py                    # Stage 1/2 exception handlers: catch → fallback → warn → continue
src/preprocess/fusion.py           # Added public decode_fused_record()
src/collect/news_collector.py      # Replaced private _get_weekday_adjustment with import from date_utils
src/generate/orchestrate.py        # Replaced private _decode_fused_record with import from fusion.py
tests/conftest.py                  # Added tests.fixtures.degradation_data to pytest_plugins
tests/test_news_collector.py       # Fixed import: _get_weekday_adjustment → get_weekday_adjustment
```

### Files Not Modified (verified)

- `src/generate/reporter.py` — existing warning rendering unchanged
- `src/generate/models.py` — `ReportInput.warnings` reused as-is
- `src/generate/config.py` — no changes
- `src/preprocess/validator.py` — `ValidationWarning` reused as-is
- `src/preprocess/output_writer.py` — `_fused_record_to_dict` serializes `record.warnings` unchanged
- `src/collect/exceptions.py` — exceptions used as catch targets, unchanged
- `src/model/` — entirely untouched
- `src/collect/market_data.py` — no changes
- `src/collect/transformers.py` — no changes

### Key Architecture

```python
# ── Core fallback function ──────────────────────────────────────────────
def find_historical_fallback(
    ticker: str, target_date: str, field_type: str,
    fused_dir: str = "data/processed/fused",
) -> FusedRecord | None:
    # Parse target_date, iterate offset 1..5 calendar days
    # Apply weekends-only adjustment (Sat→Fri, Sun→Fri)
    # Deduplicate adjusted dates via set[str]
    # For each adjusted date:
    #   1. Load {ticker}_{date}.json from fused_dir
    #   2. Skip if file missing / invalid JSON / decode error
    #   3. Check _field_is_valid(record, field_type)
    #   4. Return first valid record found
    # Return None if all 5 offsets exhausted

# ── Warning builders ─────────────────────────────────────────────────────
def build_degradation_warning(
    field_type: str, fallback_record: FusedRecord | None,
    ticker: str, target_date: str,
) -> ValidationWarning:
    # field_type="market" → category degraded_market or fallback_failed
    # field_type="news"   → category degraded_news or fallback_failed
    # Messages include ticker/date context

def build_insufficient_data_warning(ticker: str, target_date: str) -> ValidationWarning:
    # category="insufficient_data", field="combined"

# ── Pipeline integration ─────────────────────────────────────────────────
# src/pipeline.py (lines 69-165):
#
# degradation_warnings: list[ValidationWarning] = []
#
# try:                              # Stage 1: Market data
#     market_data = await fetch(...)
# except MarketDataUnavailableError:
#     historical = find_historical_fallback(ticker, target_date, "market")
#     market_data = historical.market_data if ... else None
#     degradation_warnings.append(build_degradation_warning("market", historical, ...))
#
# try:                              # Stage 2: News
#     news_articles = await fetch_news(...)
# except NewsDataUnavailableError:
#     historical = find_historical_fallback(ticker, target_date, "news")
#     news_articles = historical.news_articles if ... else []
#     degradation_warnings.append(build_degradation_warning("news", historical, ...))
#
# if not market_data and not news_articles:     # Post-both
#     degradation_warnings.append(build_insufficient_data_warning(...))
#
# if market_data is not None:         # Validation guard (was: crash on None)
#     md_result = md_validator.validate(market_data)
#
# fused = engine.fuse(...)            # Stage 3: Fusion
# fused.warnings.extend(degradation_warnings)  # Merge warnings
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| `set[str]` dedup for weekend dates | Both Saturday and Sunday map to Friday — without dedup, the same file would be checked twice, wasting one of the 5 lookback slots |
| `fused_dir` parameter with default | Allows tests to inject `tmp_path` without filesystem mocking; production uses default `data/processed/fused/` |
| Full `FusedRecord` returned (not per-field) | Simpler API — caller extracts the needed field; avoids tuple return or parallel return functions |
| `value=None` for all degradation warnings | Degradation warnings describe a process event (fallback occurred/failed), not a data quality issue — no specific value to report |
| Warnings merged after fusion (not inside) | `DataFusionEngine.fuse()` creates its own warnings (missing_market_data); degradation warnings are appended via `fused.warnings.extend()` to keep the engine unaware of degradation |
| `get_weekday_adjustment()` as independent function | Public, importable from any layer; eliminates the private-function barrier and the two-diverging-implementations problem |

---

## 6. Test Coverage

| Category | Tests | Covers ACs | Status |
|----------|-------|------------|--------|
| Market Fallback Success (valid record, closest first, weekend adjustment) | 3 | AC-01 | ✅ |
| News Fallback Success (valid record, closest first) | 2 | AC-02 | ✅ |
| Market Fallback Failure (no files, null field, invalid date, non-existent dir, 5-day exhaust) | 5 | AC-03 | ✅ |
| Both Fallback Failure (news empty field) | 1 | AC-04 | ✅ |
| Mixed: Market Fail, News Success (skips invalid, finds older valid) | 1 | AC-05 | ✅ |
| Mixed: News Fail, Market Success | 1 | AC-06 | ✅ |
| Batch Multi-Ticker (independent directories, mixed failure modes, shared directory) | 3 | AC-07 | ✅ |
| Warning Rendering (text/JSON/HTML presence + absence) | 4 | AC-08 | ✅ |
| Warning Builder (all 4 categories, value=None) | 8 | — | ✅ |
| Fallback Edge Cases (corrupt JSON, wrong ticker, missing key) | 3 | — | ✅ |
| Integration Composition (market/news/both/None guard) | 2 | — | ✅ |
| **Total** | **33** | **8 ACs** | ✅ |

### Fixtures (5 total)

- `fused_record_today` — Valid FusedRecord (2026-05-22) with market data + 2 news articles + 1 warning
- `fused_record_yesterday` — Valid FusedRecord (2026-05-21) — fallback candidate
- `fused_record_two_days_ago` — Valid FusedRecord (2026-05-20) — deeper fallback
- `fused_record_no_market` — FusedRecord with `market_data=None` — invalid for market fallback
- `fused_record_no_news` — FusedRecord with `news_articles=[]` — invalid for news fallback

### Test Infrastructure

**Simpler than Ticket 8** — no HTML parsing, no cross-format consistency counting:
- Direct `FusedRecord` construction (no mocking needed)
- `tmp_path` for filesystem isolation (no monkeypatch for I/O)
- `set[str]` dedup verified implicitly by weekend-adjustment tests
- No torch mocking, no async mocking, no HTTP mocking
- Helper functions `_make_record()` and `write_fused_records()` for test data setup

### Test Classes (5)

| Class | Tests | Focus |
|-------|-------|-------|
| `TestFindHistoricalFallback` | 11 | Core fallback function behavior and edge cases |
| `TestBuildDegradationWarning` | 8 | Warning category/message/value construction |
| `TestDegradationWarningRendering` | 4 | AC-08: warnings in all 3 report formats |
| `TestFallbackFileEdgeCases` | 6 | File-level edge cases + AC-07 multi-ticker |
| `TestPipelineIntegration` | 4 | Composition: fallback+warn+fuse as in pipeline.py |

---

## 7. Outstanding Issues

### Non-Blocking

- [ ] LOW: No end-to-end integration test for `pipeline.py` exception handlers with real mocked collectors — the 4 `TestPipelineIntegration` tests verify the fallback+warn+fusion composition in isolation but not the actual try→except flow
- [ ] LOW: `find_historical_fallback()` is stateless file-scanner — if `fused_dir` files are partially written during concurrent batch processing, fallback silently skips the candidate (caught by JSON decode handler but no retry)
- [ ] LOW: Triple-warning on complete failure: 2× `fallback_failed` + `insufficient_data` — matches spec but produces noisy reports
- [ ] LOW: No shared constant for fused filename pattern (`{ticker}_{date}.json`) — fallback and `FusedRecordWriter` are manually kept in sync
- [ ] LOW: Smoke test (multi-ticker batch with mixed failures) not implemented as automated test — requires orchestrator-level mocking

### Resolved During Review

- [x] "Historical data" undefined → defined with source, 5-day lookback, selective substitution, first-run fallback
- [x] "insufficient_data status" doesn't exist → replaced with ValidationWarning categories, no new fields
- [x] Zero edge case coverage → expanded from 3 to 8 ACs
- [x] Layer ambiguity → scoped to `src/generate/degradation.py` + `src/pipeline.py`
- [x] Missing Ticket 8 dependency → added to dependencies
- [x] Warning format undefined → 4 categories with conventions
- [x] Pipeline already silent → explicit catch → fallback → warn → continue flow
- [x] No test structure → named files with test/fixture counts
- [x] Warning handoff not explicit → pseudocode shows merge into FusedRecord.warnings
- [x] None validation guard → explicit skip of MarketDataValidator
- [x] Historical validity undefined → 3-part check (file + JSON + non-None field)
- [x] AC-01/02 vague → cross-reference 5-day lookback definition
- [x] AC-08 text/HTML rendering conflict → relaxed to match existing reporter.py behavior
- [x] Pseudocode missing `value=None` → added to all 6 ValidationWarning calls
- [x] Trading-day ambiguity → specified weekends-only from news_collector.py
- [x] AC-07 test complexity → added monkeypatch/dependency-injection note
- [x] Duplicate `_get_weekday_adjustment` and `_decode_fused_record` → extracted shared utilities
- [x] `build_degradation_warning` unused params → included ticker/date in messages
- [x] Dead `WARNING_FIELDS` constant → removed
- [x] `_get_weekday_adjustment` alias → replaced with direct import
- [x] Per-ticker test uses separate directories → added shared-directory test
- [x] No pipeline integration test → added 4 composition tests
- [x] Stale docstring → updated to `date_utils.get_weekday_adjustment()`
- [x] `fetch_news` dropped from imports → restored with duplicate removal
- [x] PEP 8 blank line → trimmed from 3 to 2

---

## 8. Lessons Learned

### What Went Well

1. **Incremental review rounds caught different depth levels** — Round 1 caught structural gaps (undefined fallback, AC sparsity). Round 2 caught polish issues (warning handoff, validity criteria). Round 3 caught a spec-vs-implementation contradiction that the earlier rounds had actually introduced (AC-08 vs reporter.py). Each round surfaced a different category of issue, validating the multi-pass approach even for a single spec refinement cycle.

2. **Infrastructure verification prevented runtime crashes** — The `ValidationWarning` signature discovery (4 required args, not 3) and the `reporter.py` rendering verification were both found by reading actual source files, not by abstract reasoning. This confirms that spec review must include direct codebase verification, not just logical analysis.

3. **Reusing existing warning infrastructure saved complexity** — By choosing `ValidationWarning` categories instead of a new `status` field, the ticket avoided touching 5+ files across `src/preprocess/`, `src/generate/`, and `tests/`. The existing `FusedRecord.warnings → ReportInput.warnings → ReportGenerator` pipeline was already proven by Ticket 8's 34 tests.

4. **First ticket to achieve READY without implementation** — All prior tickets required code review rounds after implementation to catch spec-code mismatches. Ticket 9 achieved READY status entirely during the spec phase, with all issues found by cross-referencing against existing code before any implementation. This is the ideal TDD workflow.

5. **Dependency analysis before implementation is standardizing** — Following the pattern established in Ticket 7's post-mortem and reinforced in Ticket 8's, Ticket 9's review included systematic cross-referencing of every referenced type, function, and file against the actual codebase. This found 4 issues that abstract spec review alone would have missed.

6. **Two code review rounds added value despite READY spec** — Even though the spec was thoroughly validated pre-implementation, code review found 6 quality issues (dead code, unused params, stale docs, missing tests) that no spec review could detect. Code review prevented one regression (dropped `fetch_news` import) from reaching main.

7. **DRY refactoring was discovered during implementation, not spec** — The need to extract `date_utils.py` and `decode_fused_record()` emerged when writing the actual code that needed those functions. These are design improvements that spec review could not anticipate — they are implementation concerns.

8. **33 tests exceeded the 12-15 planned target** — The discrepancy came from: (a) edge case tests for file-level failures (corrupt JSON, wrong ticker, missing key), (b) warning builder unit tests (8 tests for the 4 category variants), (c) rendering tests (4 for AC-08 across 3 formats + absence), and (d) pipeline integration composition tests (4). All tests are meaningful and cover distinct behaviors.

### What Could Improve

1. **Verify pseudocode against actual dataclass signatures** — The `ValidationWarning(category, field, message)` calls with 3 args would have been caught immediately if the pseudocode had been validated against `src/preprocess/validator.py`. A simple "for each dataclass instantiation in pseudocode, check the actual signature" step would catch this class of bug.

2. **Cross-validate AC format requirements against actual rendering code** — The AC-08 vs `reporter.py` conflict was introduced in Round 2's fix (the clarity improvement added format details that didn't match the code). Any AC that references existing rendering behavior should be verified against the actual rendering code.

3. **Single source of truth for trading-day logic** — The existence of two diverging implementations (`market_data.py` holiday-aware, `news_collector.py` weekends-only) is a latent bug in the codebase. One future ticket should unify these or extract a shared utility. Ticket 9 extracted `date_utils.py` as a shared home but only covers the weekends-only variant.

4. **Pipeline integration check earlier** — The pipeline catch block behavior (silent `except` with no warnings) was discovered in Round 1 by reading `pipeline.py:71-81`, not in the initial spec. Adding a "read the pipeline code" step at the very start of each review would surface these integration points earlier.

5. **AC-08 format conflict was self-inflicted** — The Round 2 fix for "AC-08 ambiguous rendering" added explicit format details that were never verified against the actual code. Any AC wording change that describes existing behavior should include a verification step: "does this match what the code actually does?"

6. **Test import surgery is fragile** — The fix in `test_news_collector.py` (replacing one import, adding another, removing duplicates) introduces risk of accidentally dropping needed imports. A safer pattern is to make the full diff visible before/after rather than surgical edits.

7. **Integration test design needs thought** — The `TestPipelineIntegration` class tests the composition of `find_historical_fallback()` + `build_degradation_warning()` + `DataFusionEngine.fuse()` without mocking the actual pipeline. This is a good compromise between coverage and complexity, but it doesn't verify the actual `pipeline.py` exception handlers. For future tickets, consider whether a lightweight integration test framework (e.g., pytest-asyncio + monkeypatch for async context managers) is worth the investment.

### Key Metrics

| Metric | Value |
|--------|-------|
| Original ACs | 3 |
| Refined ACs | 8 |
| TDD review rounds | 4 |
| Code review rounds | 2 |
| Implementation issues found by dependency analysis | 4 |
| Files created | 3 (source) + 2 (test) |
| Files modified | 5 |
| Total tests | 33 |
| Test fixtures | 5 |
| Issues found by TDD review | 3 blocking + 5 moderate (R1) → 5 green (R2) → 1 blocking + 3 non-blocking (R3) → 0 (R4) |
| Issues found by dependency analysis | 4 (all pre-implementation) |
| Issues found by code review | 6 (R1) + 2 (R1 re-check), all resolved |
| Mock complexity | None (pure Python, no torch, no HTTP mocking needed) |
| New dependencies | 0 |

---

## 9. Acceptance Criteria Verification

| AC | Test(s) | Verification Method | Status |
|----|---------|---------------------|--------|
| AC-01 | `test_fallback_returns_valid_market_record`, `test_fallback_returns_closest_valid_first`, `test_degraded_market_warning` | Structural: fallback returns record with non-None market_data; warning category = `degraded_market`; closest date used | ✅ |
| AC-02 | `test_fallback_returns_valid_news_record`, `test_degraded_news_warning` | Structural: fallback returns record with non-empty news_articles; warning category = `degraded_news` | ✅ |
| AC-03 | `test_fallback_returns_none_when_no_files`, `test_fallback_returns_none_when_market_field_null`, `test_fallback_failed_market_warning`, `test_fallback_exhausts_all_offsets` | Structural: None returned when no files / null field / exhausted; warning category = `fallback_failed` | ✅ |
| AC-04 | `test_fallback_returns_none_when_news_field_empty`, `test_insufficient_data_warning`, `test_fallback_failed_and_insufficient_data_compose` | Structural: fallback returns None; insufficient_data warning produced; pipeline continues with None/[] | ✅ |
| AC-05 | `test_fallback_skips_invalid_and_finds_valid`, `test_fallback_and_warning_compose_for_market_failure` | Structural: market fallback used, news runs normal; `degraded_market` + normal news in fused record | ✅ |
| AC-06 | `test_fallback_and_warning_compose_for_news_failure` | Structural: news fallback used, market runs normal; `degraded_news` + normal market in fused record | ✅ |
| AC-07 | `test_per_ticker_independent_market_lookback`, `test_per_ticker_mixed_failure_modes`, `test_per_ticker_in_shared_directory` | Structural: each ticker independently finds/skips fallback; shared directory correctly scoped per ticker | ✅ |
| AC-08 | `test_warnings_in_text`, `test_warnings_in_json`, `test_warnings_in_html`, `test_warnings_section_absent_when_none` | Structural: text has "- {message}"; JSON has category/field/message/value; HTML has `<div class="warning">`; absent when no warnings | ✅ |

---

## 10. Timeline

| Date | Activity |
|------|----------|
| May 30, 2026 | Original ticket loaded (3 vague ACs, undefined fallback, missing dependency) |
| May 30, 2026 | TDD review round 1 (NEEDS REVISION — 3 blocking + 5 moderate issues) |
| May 30, 2026 | Design discussion: historical fallback source, scan strategy, selective substitution, first-run behavior |
| May 30, 2026 | Design decision: ValidationWarning categories instead of new status field (no dataclass changes) |
| May 30, 2026 | Fixed v1: defined historical fallback, added ValidationWarning categories, expanded to 8 ACs, corrected dependencies, added file/test structure |
| May 30, 2026 | TDD review round 2 (READY — 5 green findings) |
| May 30, 2026 | Fixed v2: warning handoff in pseudocode, None validation guard, historical validity criteria, AC cross-references, AC-08 format clarity |
| May 30, 2026 | TDD review round 3 (NEEDS REVISION — 1 blocking: AC-08 vs reporter.py conflict) |
| May 30, 2026 | Fixed v3: relaxed AC-08 to match existing reporter behavior, added value=None to all calls, specified weekends-only adjustment, AC-07 mock note |
| May 30, 2026 | TDD review round 4 (APPROVE — 0 blocking, 0 moderate) |
| May 30, 2026 | **Implementation**: `src/generate/degradation.py`, `src/pipeline.py` modifications, `src/preprocess/fusion.py` decode_fused_record, `src/collect/date_utils.py` extraction |
| May 30, 2026 | **DRY refactoring**: `src/collect/news_collector.py` replaced alias with direct import; `src/generate/orchestrate.py` switched to shared `decode_fused_record` |
| May 30, 2026 | **Test implementation**: `tests/fixtures/degradation_data.py`, `tests/test_degradation.py` (28 tests), `tests/conftest.py` plugin registration |
| May 30, 2026 | **Code review round 1**: 6 issues (unused params, dead code, unnecessary alias, stale docstring, test gaps) |
| May 30, 2026 | **Fixed**: all 6 issues; added 5 new tests (shared-directory + 4 integration composition) → 33 tests |
| May 30, 2026 | **Code review round 1 re-check**: 2 issues (import regression in test_news_collector, PEP 8 blank lines) |
| May 30, 2026 | **Fixed**: restored `fetch_news` import, removed duplicate imports, fixed blank lines |
| May 30, 2026 | **Verification**: ruff ✅, 33/33 degradation tests ✅, 254/260 full suite ✅ (6 pre-existing), mypy 18 pre-existing errors ✅ |
| May 30, 2026 | Post-mortem updated |

---

## 11. Next Steps

1. Mark Ticket 9 as ✅ COMPLETE in tickets index document
2. Consider unifying trading-day adjustment: `market_data.py` holiday-aware vs `news_collector.py`/`date_utils.py` weekends-only — extract shared holiday calendar
3. Consider adding a shared constant for fused filename pattern (`{ticker}_{date}.json`) to prevent silent coupling between `output_writer.py` and `degradation.py`
4. Consider a lightweight integration test framework for `pipeline.py` exception handlers (async context manager monkeypatching) — would benefit future tickets that modify pipeline logic
5. Codify the "pseudocode signature verification" step in the TDD review checklist — verify every dataclass instantiation against its actual constructor
6. Codify the "cross-reference AC format requirements against existing rendering code" step — any AC referencing existing behavior should be verified against the actual code
