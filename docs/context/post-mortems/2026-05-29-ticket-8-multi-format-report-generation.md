# Post-Mortem: Ticket 8 — Multi-Format Report Generation

**Date:** May 29, 2026  
**Status:** ✅ COMPLETE  
**Review Status:** APPROVE (after 5 TDD review rounds + 2 code review rounds)

---

## 1. Overview

### Original Ticket
**Title:** Generate end-of-day reports in text, JSON, and HTML formats

**Original Acceptance Criteria (3 ACs, minimal detail):**
```markdown
- Given 10 tickers analyzed, When report is generated, Then all formats are produced
- Given analysis complete, When report is generated, Then it completes within 30 seconds (ASSUMPTION: local generation)
- Given warnings during analysis, When report is generated, Then warnings are included in all formats
```

**Original api_spec:**
```
Input: { analyses: [TickerAnalysis], date: date }
Output: { report_id, text: string, json: object, html: string }
```

### Refined Acceptance Criteria (11 ACs after 5 TDD review rounds)

```
AC-01:  10 TradingSignal objects → ReportResult whose text contains all 10 ticker symbols
        from src.generate.config.TICKERS, json is parseable, html has <table> and </html>
AC-02:  Text report contains each ticker symbol, signal label, and confidence value
AC-03:  JSON has signals array with all 6 TradingSignal fields per entry
AC-04:  3 ValidationWarnings → warning content in all 3 formats
AC-05:  Empty signal list → ValueError
AC-06:  None as ReportInput → TypeError
AC-07:  market_return=None → "N/A" in text and HTML
AC-08:  report_id matches ^[0-9a-f]{8}$
AC-09:  HTML well-formed (parseable by custom HTMLParser subclass)
AC-10:  Cross-format consistency: data line count matches across all 3 formats
AC-11:  Empty or malformed date string → ValueError from run_report_generation()
```

---

## 2. Problems Identified

### TDD Review Round 1 — NEEDS REVISION (12 blocking + 7 moderate issues)

The initial ticket had only 3 vague ACs, an undefined input type, no format specifications, and wrong dependencies:

#### Blocking Issues

| Issue | Severity | Problem |
|-------|----------|---------|
| `TickerAnalysis` type undefined | **Blocking** | API spec input type `TickerAnalysis` does not exist anywhere in the codebase. The output of Ticket 7 is `TradingSignal`, not `TickerAnalysis`. The report generator input must be concretely defined |
| Missing warning data source | **Blocking** | AC-003 requires warnings in all formats, but `TradingSignal` has no `warnings` field. Warnings live on `FusedRecord.warnings` (Ticket 4), which is not in the dependency chain |
| AC-001 not deterministically testable | **Blocking** | "all formats are produced" is ambiguous — returned? written to disk? No output paths or verification criteria specified |
| AC-002 is environment-dependent | **Blocking** | 30-second timeout depends on hardware and I/O — not a valid unit-test pass/fail criterion |
| AC-003 warning source unspecified | **Blocking** | Which warnings? From which stage? What fields? Where in each format? |
| No format specifications | **Blocking** | Text/JSON/HTML formats have no schema, template, or required content. Any output string trivially passes |
| Zero error case ACs | **Blocking** | Empty list, None input, format failures — all uncovered |
| Zero edge case ACs | **Blocking** | 0/1/10 boundary, duplicates, degenerate data — all uncovered |
| "10 tickers" undefined | **Blocking** | No list, config, or sourcing mechanism specified for which tickers |
| No `report_id` scheme | **Blocking** | UUID? Timestamp? Ticker+date hash? Not specified |
| Missing output paths | **Blocking** | Where do reports go? No destination specified |
| "dashboard-ready" HTML undefined | **Blocking** | No spec for what "dashboard-ready" means — any HTML string would pass |

#### Moderate Issues

| Issue | Severity | Problem |
|-------|----------|---------|
| Date type mismatch | **Moderate** | Input spec says `date: date` (Python datetime.date) but FusedRecord.date is `str` |
| No `to_dict()` on TradingSignal | **Moderate** | JSON report generation needs a serialization strategy |
| No template engine decision | **Moderate** | HTML generation needs a templating approach |
| No output validation strategy | **Moderate** | Should text/JSON/HTML be validated for correctness? |
| Mock complexity unclear | **Moderate** | Report generation likely pure Python, but HTML templates could introduce complexity |
| Missing error case coverage | **Moderate** | Empty analyses, None analyses, partially failed generation |
| Format-specific edge cases | **Moderate** | JSON serialization of datetimes/None, HTML injection, text wrapping |

---

### TDD Review Round 2 — NEEDS REVISION (2 new blocking + 8 moderate issues)

After fixing all 12 v1 blocking issues, the pipeline integration analysis revealed gaps not visible in the spec alone:

#### Blocking Issues

| Issue | Severity | Problem |
|-------|----------|---------|
| Single-ticker vs multi-ticker conflict | **Blocking** | Existing `run_pipeline()` processes one ticker (`--ticker AAPL`). Stage 7 requires results from all 10 tickers. No bridge specified |
| FusedRecord.warnings not propagated | **Blocking** | `FusedRecord.warnings` are created in Stage 3, written to disk in Stage 4, but never passed to downstream stages. Stage 7 plan assumes warnings are available but data flow doesn't support it |

#### Moderate Issues

| Issue | Severity | Problem |
|-------|----------|---------|
| JSON `market_return=None` representation unspecified | **Moderate** | Not specified whether None serializes as `null` or is omitted |
| Text format is an example, not locked-down spec | **Moderate** | Column widths, decimal precision, rationale truncation all unspecified |
| AC-03 only checks 3 of 6 TradingSignal fields | **Moderate** | Only checks `ticker`, `signal`, `confidence` — misses `sentiment_score`, `market_return`, `rationale` |
| AC-01 "non-empty text" too weak | **Moderate** | Any `len(x) > 0` string passes — doesn't verify content |
| No AC for invalid/empty date string | **Moderate** | Date validation specified in docstring but no AC tests it |
| AC-10 "same number of entries" ambiguous for text | **Moderate** | No clarification on how to count entries in text format vs JSON/HTML |
| No TradingSignal or ValidationWarning fixtures exist | **Moderate** | signal_data.py has SentimentResult+MarketData fixtures but no combined TradingSignal fixtures |
| Architectural layering for models.py | **Moderate** | Report models in `src/generate/models.py` vs shared model layer — decision needed |

---

### TDD Review Round 3 — APPROVE (0 blocking, 4 moderate issues)

After fixing all v2 issues, 4 moderate implementation details remained:

#### Moderate Issues

| Issue | Severity | Problem | Fix |
|-------|----------|---------|-----|
| Missing `dependencies: [Ticket 6]` | **Moderate** | Orchestration directly calls `FinBertSentiment.analyze()` but only depends on Ticket 4 and Ticket 7 | Added Ticket 6 to dependencies |
| FinBertSentiment per-ticker (10× loads) | **Moderate** | Creating FinBertSentiment inside the loop would download model weights 10 times | Specified instantiate-once pattern |
| AC-11 validation location ambiguous | **Moderate** | Generator or orchestration layer should validate date | Moved to `_validate_date()` in orchestrate.py |
| FusedRecord deserialization path unspecified | **Moderate** | `load_fused_record()` signature exists but JSON→FusedRecord conversion not defined | Added `_decode_fused_record()` with docstring |

---

### TDD Review Round 4 — APPROVE (0 blocking, 4 moderate issues)

#### Moderate Issues

| Issue | Severity | Problem | Fix |
|-------|----------|---------|-----|
| AC-09 HTML well-formedness parser is lenient | **Moderate** | Python's `html.parser.HTMLParser` doesn't validate tag balance — always returns "parseable" | Added `_WellFormednessChecker` subclass example with tag-stack tracking in format specs |
| AC-01 "configured TICKERS list" ambiguous | **Moderate** | Could refer to `config.TICKERS` or the input `ticker_signals` — they could differ | Changed to explicit `` `src.generate.config.TICKERS` `` |
| AC-11 only tests empty date, not invalid format | **Moderate** | `_validate_date()` checks both empty and format but AC only covers empty | Extended AC-11 to cover both `""` and `"not-a-date"` |
| File output directory not created | **Moderate** | `os.makedirs` not mentioned in spec | Added `os.makedirs("data/processed/reports", exist_ok=True)` detail |

---

### TDD Review Round 5 — APPROVE (0 blocking, 4 moderate issues)

#### Moderate Issues

| Issue | Severity | Problem | Fix |
|-------|----------|---------|-----|
| AC-10 preamble description off-by-one | **Moderate** | Lists 4 preamble items but format has 6 lines (missing `=` separator and blank line) | Let test count data lines between `-` separator and `=` footer — robust to format changes |
| Orchestration imports incomplete | **Moderate** | Code snippet only shows `TICKERS` import, but `FinBertSentiment`, `TradingSignalGenerator`, `FusedRecord` also needed | Acceptable as shorthand — context makes them obvious |
| JSON "omit warnings if empty" has no AC | **Moderate** | Format spec says omit warnings if empty, but no AC tests empty-warnings behavior | Addressed in implementation notes — test implicitly covers it |
| HTML `warnings_section` undefined when absent | **Moderate** | Template shows `{warnings_section}` but doesn't define value when no warnings | Clarified: empty string when no warnings |

---

### Implementation Issues

During implementation, four issues emerged from the dependency analysis and coding:

| Issue | Severity | Problem | Fix |
|-------|----------|---------|-----|
| `volume: int` coercion in `_decode_fused_record()` | **Blocking** | `MarketData.volume` is `int` but `json.load()` returns `float` for all numbers. Without coercion, `validator.py:111` `isinstance(data.volume, int)` silently fails | Added explicit `int(md_data["volume"])` in `_decode_fused_record()` before `MarketData(**md_data)` call |
| Text format column alignment ambiguity | **Medium** | Spec's "Format" column (e.g., `{:>10.2f}` for Confidence) showed format width less than column width — implementors must pad to match column width | Code uses column width as format width (e.g., `{:>12.2f}`) which produces correct output. Spec "Format" column has minor typos |
| HTML void elements list incomplete | **Low** | The spec's `_WellFormednessChecker` example listed 6 void elements but HTML5 has 14. Missing elements wouldn't cause incorrect behavior for table-based report but would affect `<br>` usage | Full 14-element set used in the test implementation |
| Warnings omission from JSON when empty checked incorrectly | **Low** | Naively serializing with `json.dumps` would produce `"warnings": []` instead of omitting the key entirely | Explicit `if input.warnings:` check before adding key to dict |

---

### Code Review Round 1 — 2 Issues Found (C.L.E.A.R. Framework)

| Severity | Finding | Location | Fix |
|----------|---------|----------|-----|
| **Low** | 4 fixture functions defined in `report_data.py` (`sample_trading_signal_buy`, `sell`, `hold`, `no_market`) but never referenced by any test — dead code | `tests/fixtures/report_data.py:16-65` | Added 6 tests in `TestSignalFormatting` consuming all 4 fixtures, verifying HTML CSS classes and `N/A`/`null` handling |
| **Low** | `s.ticker` not passed through `html.escape()` in HTML output while `s.signal`, `s.rationale`, and `w.message` all are — inconsistent escaping pattern | `src/generate/reporter.py:114` | Changed to `html.escape(s.ticker)` |

### Code Review Round 2 — 1 Issue Found (C.L.E.A.R. Framework)

| Severity | Finding | Location | Fix |
|----------|---------|----------|-----|
| **Critical** | File-writing loop used `getattr(result, "txt")` but `ReportResult` has field `text`, not `txt` — would crash with `AttributeError` at runtime | `src/generate/orchestrate.py:75` | Added `_ext_to_attr` mapping dict (`{"txt": "text", "json": "json", "html": "html"}`) |

---

## 3. Fixes Applied

### A. Defined Concrete Input Type (v1 B1)

**Before:** `TickerAnalysis` — type doesn't exist
**After (FIXED):**
```python
@dataclass
class ReportInput:
    ticker_signals: list[TradingSignal]
    date: str
    warnings: list[ValidationWarning] | None = None
```

### B. Added Warning Data Source (v1 B2)

**Before:** No way for warnings to enter the report generator
**After (FIXED):** Warnings extracted from `FusedRecord.warnings` (Ticket 4), accumulated by orchestrator, passed via `ReportInput.warnings`. Added Ticket 4 to dependencies.

### C. Rewrote All 3 ACs with Concrete Values (v1 B3, B6, B7, B8, B10, B12)

**Before (3 ACs):** Vague: "all formats are produced", "30 seconds", "warnings included"
**After (11 ACs):** Concrete, testable assertions with exact format specs, error paths, and edge cases.

### D. Moved Performance Guarantee to Smoke Test (v1 B4)

**Before:** `completes within 30 seconds` — an AC
**After (FIXED):** Demoted to smoke test (benchmark, not CI-enforced)

### E. Added Full Format Specifications (v1 B6, B12)

**Before:** No format specs — any output trivially passed
**After (FIXED):** Three complete format specs:
- **Text**: Fixed-width columns with alignment table (Ticker:10, Signal:12, Confidence:12, Sentiment:12, Market Return:13), rationale truncated to 60 chars, preamble/footer separators
- **JSON**: Explicit schema with `report_id`, `date`, `signals` array (all 6 TradingSignal fields), `warnings` array; `market_return: null` when None
- **HTML**: Self-contained inline CSS, table with buy/sell/hold color classes, warning div below table

### F. Added Ticker Configuration (v1 B9)

**Before:** "10 tickers" — undefined constant
**After (FIXED):** `TICKERS` list in `src/generate/config.py`:
```python
TICKERS: list[str] = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",
    "TSLA", "NVDA", "JPM", "V", "JNJ",
]
```

### G. Added report_id Scheme (v1 B10)

**Before:** No generation scheme
**After (FIXED):** `uuid.uuid4().hex[:8]` — 8-character hex string, verified by AC-08 regex `^[0-9a-f]{8}$`

### H. Switched to In-Memory Output (v1 B11)

**Before:** No output path specified — assumption was file-based
**After (FIXED):** Primary contract is `ReportResult` dataclass returned in-memory. File output is secondary side effect in orchestrator.

### I. Standardized Date Type (v1 M1)

**Before:** `date: date` (Python datetime.date)
**After (FIXED):** `date: str` — matches `FusedRecord.date` convention

### J. Resolved Templating Strategy (v1 M3)

**Before:** No template engine decision
**After (FIXED):** Python f-strings — zero new dependencies. HTML template defined inline in format specs.

### K. Added Error and Edge Case ACs (v1 M6)

**Before:** Zero error case coverage
**After (FIXED):**
- AC-05: Empty signal list → `ValueError`
- AC-06: `None` as ReportInput → `TypeError`
- AC-07: `market_return=None` → "N/A" in text/HTML
- AC-08: report_id format validation
- AC-09: HTML well-formedness
- AC-10: Cross-format consistency
- AC-11: Empty/invalid date → `ValueError`

### L. Resolved Pipeline Integration: Option B (v2 B1)

**Before:** Pipeline rewrite with internal loop over 10 tickers — would change CLI contract
**After (FIXED):** Separate orchestration step (two-step workflow):
```
Step 1: uv run python -m src.pipeline --ticker AAPL --date 2026-05-28  (per ticker)
Step 2: uv run python -m src.generate --date 2026-05-28                (report)
```

### M. Fixed Warning Propagation (v2 B2)

**Before:** `FusedRecord.warnings` never passed downstream after Stage 4
**After (FIXED):** `run_report_generation()` loads FusedRecord from disk, extracts `fused.warnings` per ticker, passes via `ReportInput.warnings`.

### N. Locked Text Format Spec (v2 M2)

**Before:** Example format with no fixed widths
**After (FIXED):** Column width table (Ticker:10 left, Signal:12 right, Confidence:12 right `.2f`, Sentiment:12 right `+.4f`, Market Return:13 right, Rationale:60 chars+`...`)

### O. Strengthened AC-03 (v2 M3)

**Before:** Only 3 fields checked: `ticker`, `signal`, `confidence`
**After (FIXED):** All 6 TradingSignal fields: `ticker`, `signal`, `confidence`, `sentiment_score`, `market_return`, `rationale`

### P. Strengthened AC-01 (v2 M4)

**Before:** "non-empty text" — any `len(x) > 0` string passes
**After (FIXED):** "text contains all 10 ticker symbols from `src.generate.config.TICKERS`"

### Q. Added AC-11 for Date Validation (v2 M5)

**Before:** No AC for empty/invalid date
**After (FIXED):** AC-11: empty string or malformed string → `ValueError` from `run_report_generation()`

### R. Clarified AC-10 Counting Rule (v2 M6)

**Before:** "same number of entries" — ambiguous for text format
**After (FIXED):** "number of data lines in text format (excluding preamble) equals length of signals array in JSON equals number of `<tr>` rows in HTML (excluding header)"

### S. Expanded Dependencies (v3 M1)

**Before:** `dependencies: [Ticket 4, Ticket 7]`
**After (FIXED):** `dependencies: [Ticket 4, Ticket 6, Ticket 7]`

### T. Added FinBertSentiment Singleton Pattern (v3 M2)

**Before:** `run_report_generation()` docstring didn't specify instantiation strategy
**After (FIXED):** "Instantiates FinBertSentiment once (not per ticker) to avoid 10× model downloads"

### U. Moved Date Validation to Orchestration Layer (v3 M3)

**Before:** Validation implied inside `ReportGenerator.generate()`
**After (FIXED):** All date validation in `_validate_date()` called by `run_report_generation()` — fail fast before any processing

### V. Added FusedRecord Deserialization Spec (v3 M4)

**Before:** `load_fused_record()` signature without implementation
**After (FIXED):** `_decode_fused_record(data: dict) -> FusedRecord` with docstring explaining MarketData and ValidationWarning reconstruction

### W. Added HTML Well-Formedness Checker (v4 M1)

**Before:** AC-09 relied on lenient `html.parser.HTMLParser`
**After (FIXED):** `_WellFormednessChecker` subclass with tag-stack + void-element tracking added to format specs as test guidance

### X. Clarified AC-01 TICKERS Reference (v4 M2)

**Before:** "configured TICKERS list" — ambiguous between config.TICKERS and input tickers
**After (FIXED):** "ticker symbols from `src.generate.config.TICKERS`"

### Y. Extended AC-11 Coverage (v4 M3)

**Before:** Only `""` tested
**After (FIXED):** Both `""` and `"not-a-date"` covered

### Z. Added Output Directory Creation (v4 M4)

**Before:** No `os.makedirs` — file write would fail with `FileNotFoundError`
**After (FIXED):** `os.makedirs("data/processed/reports", exist_ok=True)` at top of `run_report_generation()`

### AA. Clarified AC-10 Preamble Counting (v5 M1)

**Before:** Preamble list off by one with format
**After (FIXED):** Test counts data lines between `-` separator and `=` footer — robust even if preamble changes

### AB. Clarified HTML Warnings Section When Absent (v5 M4)

**Before:** `{warnings_section}` undefined when no warnings
**After (FIXED):** Warnings section is empty string when warnings list is None or empty

### AC. Added `volume: int` Coercion in `_decode_fused_record()` (Implementation)

**Before:** `MarketData(**md_data)` would receive `volume` as `float` from `json.load()`, silently breaking `validator.py:111` `isinstance(data.volume, int)` check
**After (FIXED):** `md_data["volume"] = int(md_data["volume"])` before dataclass reconstruction

### AD. Fixed HTML Escaping on `s.ticker` (Code Review R1)

**Before:** `<td>{s.ticker}</td>` — no escaping, inconsistent with other fields
**After (FIXED):** `<td>{html.escape(s.ticker)}</td>`

### AE. Wired Up Unused Fixtures to Tests (Code Review R1)

**Before:** 4 fixture functions defined but never referenced — dead code
**After (FIXED):** 6 new tests in `TestSignalFormatting` consume all 4 fixtures, testing HTML CSS class rendering and `N/A`/`null` handling

### AF. Fixed `txt` → `text` Field Mapping (Code Review R2)

**Before:** `getattr(result, "txt")` — crashes because `ReportResult` has `text` field, not `txt`
**After (FIXED):** Added `_ext_to_attr = {"txt": "text", "json": "json", "html": "html"}` mapping

---

## 4. Technical Issues Found During Implementation

### Dependency Analysis Discoveries

A detailed dependency analysis was performed before implementation, which surfaced several gaps not caught by the TDD spec review:

1. **`volume: int` coercion needed** — `MarketData.volume` is `int` in the dataclass definition, but `json.load()` deserializes it as `float`. Without explicit coercion, `validator.py:111` `isinstance(data.volume, int)` would silently fail. This is invisible to the report generator itself (it doesn't run validation) but would corrupt data if the deserialized FusedRecord were re-validated.

2. **Text format "Format" column width mismatch** — The spec table's "Format" column shows `{:>10.2f}` for a 12-character column — the format width (10) is less than the column width (12). The code must pad with extra spaces to reach the column width. This is a spec documentation issue (the "Format" column should show `{:>12.2f}`), but the code correctly uses column width as format width and produces aligned output.

3. **HTML void elements list** — The spec's example `_WellFormednessChecker` only listed 6 void elements. The full HTML5 set is 14. Our HTML only uses table/text tags, so this is low risk, but the full list was used in the test implementation.

4. **Warnings omission must be explicit** — The JSON spec says "omit warnings if empty" but `json.dumps` with `"warnings": []` in the dict would produce `"warnings": []`. The key must be conditionally added only when warnings exist.

### Source of Discovery

All four implementation issues were found by cross-referencing the spec against the actual codebase before writing any code, following the same process established in Ticket 7:

- Issue 1: Reading `market_data.py` and `validator.py` revealed the `int`→`float` type coercion requirement
- Issue 2: Tracing the text format spec column widths and comparing with the format field
- Issue 3: Checking HTML5 void element spec against the example code in the ticket
- Issue 4: Testing the behavior of `json.dumps` with empty lists

### Mock Complexity is Lower Than Ticket 6

Report generation is pure Python string formatting and JSON serialization — no torch dependency, no GPU concerns, no external API calls. This means:
- No `MockTensor` infrastructure needed
- No `sys.modules["torch"]` injection
- No `MagicMock.__call__` gotchas
- No complex mock side_effect overrides

Tests use real dataclass construction directly. Orchestration tests would need `FinBertSentiment` mocking for model loading, but the core `ReportGenerator` and all format methods are tested without any mocking.

### Format Spec Verification Prevented Noisy Bugs

Testing the text format against the spec's example output caught:
- The column width/format mismatch where `{:>10.2f}` in a 12-char column needs padding
- The separator length (69 chars = 59 fixed-width columns + 10 rationale start buffer)
- The preamble counting for AC-10 (which lines to exclude vs include)

The code review process then caught an additional runtime crash (`txt` → `text` field mapping) that the spec-level review couldn't find because it was a pure implementation bug, not a spec deficiency.

---

## 5. Final Implementation

### Files Created

```
src/generate/
├── config.py                    # TICKERS list
├── models.py                    # ReportInput, ReportResult dataclasses
├── reporter.py                  # ReportGenerator with _format_text, _format_json, _format_html
└── orchestrate.py               # run_report_generation(), load_fused_record(), _validate_date()

tests/
├── test_report.py               # 34 tests covering all 11 ACs + signal formatting
└── fixtures/
    └── report_data.py           # 11 fixtures (TradingSignal + ReportInput + ValidationWarning)
```

### Files Modified

```
src/generate/__init__.py          # Added __all__ with all exports
src/generate/__main__.py          # Rewritten: argparse → run_report_generation() → print paths
tests/conftest.py                 # Added tests.fixtures.report_data to pytest_plugins
```

### Key Architecture

```python
class ReportGenerator:
    def generate(self, input: ReportInput) -> ReportResult:
        # TypeError guard for None input
        # ValueError guard for empty ticker_signals
        # uuid4().hex[:8] for report_id
        # Delegate to _format_text, _format_json, _format_html

    def _format_text(self, input: ReportInput) -> str:
        # Fixed-width columns: Ticker(10), Signal(12), Confidence(12), Sentiment(12), Market Return(13)
        # Separator: "-" * 69, Footer: "=" * 60
        # Rationale truncated to 60 chars + "..."
        # Warnings section if present, "- " per warning.message

    def _format_json(self, input: ReportInput) -> str:
        # {"report_id", "date", "signals", "warnings" (conditional)}
        # market_return=None → JSON null
        # warnings omitted when None or empty list

    def _format_html(self, input: ReportInput) -> str:
        # Self-contained HTML with inline CSS
        # Table with buy/sell/hold color classes
        # Rationale: full text (no truncation)
        # Warning <div class="warning"> below table
```

### Orchestration Flow

```python
def run_report_generation(date: str) -> ReportResult:
    _validate_date(date)                           # fail fast
    sentiment_engine = FinBertSentiment()           # once, not per ticker
    signal_generator = TradingSignalGenerator()     # pure Python

    for ticker in TICKERS:
        fused = load_fused_record(ticker, date)     # read from disk
        sentiment_result = sentiment_engine.analyze(fused)
        signal = signal_generator.generate(...)
        all_signals.append(signal)
        all_warnings.extend(fused.warnings)

    result = ReportGenerator().generate(ReportInput(...))
    # File output as side effect
    return result
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| f-strings over Jinja2 | Zero new dependencies; report template is simple enough |
| In-memory ReportResult as primary contract | Testable without file I/O; file output is CLI side effect |
| UUID4 hex[:8] for report_id | Clock-independent; sufficient namespace for project scale |
| _decode_fused_record() in orchestrate | Keeps reporter.py pure (no FusedRecord/MarketData awareness) |
| `_ext_to_attr` mapping | Maps file extensions (.txt) to ReportResult field names (text) |
| Full HTML rationale (no truncation) | HTML can wrap; truncation only in fixed-width text format |
| `html.escape()` on all content fields | XSS prevention for ticker, signal, rationale, warnings |

---

## 6. Test Coverage

| Category | Tests | Covers ACs | Status |
|----------|-------|------------|--------|
| Full Report (all 10 tickers, valid JSON, HTML tags) | 3 | AC-01 | ✅ |
| Text Content (ticker, signal, confidence per entry) | 3 | AC-02 | ✅ |
| JSON Structure (array, all 6 fields) | 2 | AC-03 | ✅ |
| Warnings in All 3 Formats (presence + absence) | 5 | AC-04 | ✅ |
| Empty Signals → ValueError | 1 | AC-05 | ✅ |
| None Input → TypeError | 1 | AC-06 | ✅ |
| N/A for Missing Market Return | 3 | AC-07 | ✅ |
| report_id Format (hex regex + in all 3 formats) | 4 | AC-08 | ✅ |
| HTML Well-Formedness (with/without warnings) | 2 | AC-09 | ✅ |
| Cross-Format Line Count Consistency | 1 | AC-10 | ✅ |
| Invalid Date → ValueError (empty, malformed, valid) | 3 | AC-11 | ✅ |
| Signal Formatting (buy/sell/hold HTML classes, no-market null/NA) | 6 | — | ✅ |
| **Total** | **34** | **11 ACs** | ✅ |

### Fixtures (11 total)

- `sample_trading_signal_buy` — TradingSignal(AAPL, buy, 0.65, +5.00%)
- `sample_trading_signal_sell` — TradingSignal(JPM, sell, 0.55, -3.00%)
- `sample_trading_signal_hold` — TradingSignal(MSFT, hold, 0.25, +0.20%)
- `sample_trading_signal_no_market` — TradingSignal(TSLA, hold, 0.20, None)
- `sample_warnings_list` — 3 ValidationWarnings (market_data, missing, invalid_volume)
- `sample_report_input_10` — 10 mixed TradingSignals for all configured tickers
- `sample_report_input_empty` — Empty signals list
- `sample_report_input_with_warnings` — 1 signal + 3 warnings
- `sample_report_input_no_market` — 2 signals (1 with market, 1 without)

### Test Infrastructure

**Simpler than Ticket 6** — no torch mocking needed:
- Direct dataclass construction (no MockTensor)
- Pure Python assertion logic with `json.loads`, `re.fullmatch`, `html.parser`
- Fixture-based test data (all tests consume fixtures from `report_data.py`)
- No conditional imports required
- Custom `_WellFormednessChecker` with full HTML5 void elements (14) for AC-09

**Slightly more than Ticket 7** — additional infrastructure for:
- HTML parsing: `_WellFormednessChecker` subclass for tag-stack validation
- Text line counting: helper methods for preamble/footer boundary detection
- Cross-format consistency: methods to count data lines across text/JSON/HTML

---

## 7. Outstanding Issues

### Non-Blocking

- [ ] LOW: No integration test with real pipeline output — requires FusedRecord files on disk and torch environment
- [ ] LOW: `_decode_fused_record()` type coercion — `MarketData.volume` is `int` but `json.load()` returns float. Fixed with explicit `int()` call, but no test verifies the coercion (would need a real JSON file loaded from disk)
- [ ] LOW: `ReportGenerator.generate(None)` flagged by type checker — `# type: ignore[arg-type]` in test; runtime guard catches it
- [ ] LOW: Smoke test (30-second benchmark) not implemented as automated test — documented but not CI-enforced
- [ ] LOW: No end-to-end test for `run_report_generation()` — requires mocking FinBertSentiment (model loading) and temporary file fixtures; planned but not implemented

### Resolved During Review

- [x] `TickerAnalysis` type undefined → `ReportInput(ticker_signals: list[TradingSignal])`
- [x] Warning data source missing → Added Ticket 4 dependency; `warnings: list[ValidationWarning]`
- [x] ACs not testable → Rewritten with concrete values and format specs
- [x] 30-second timeout → Moved to smoke test
- [x] Warning source unspecified → ValidationWarning serialized in all 3 formats
- [x] No format specs → Full text/JSON/HTML specs with examples
- [x] No error ACs → AC-05 (empty → ValueError), AC-06 (None → TypeError)
- [x] No edge ACs → AC-07 (N/A for missing market), AC-08 (UUID format), AC-09 (HTML parseable), AC-10 (consistency)
- [x] 10 tickers undefined → `TICKERS` config in `src/generate/config.py`
- [x] No report_id scheme → UUID4 hex[:8] with regex in AC-08
- [x] Output paths missing → In-memory `ReportResult` dataclass
- [x] "dashboard-ready" vague → Concrete HTML table with CSS classes and warning section
- [x] Date type mismatch → `str` matching FusedRecord convention
- [x] No templating strategy → f-strings (zero new dependencies)
- [x] Pipeline integration gap → Two-step workflow (Option B)
- [x] Warning propagation gap → Orchestrator extracts from FusedRecord disk
- [x] Text format example only → Fixed-width column table with alignment spec
- [x] AC-03 too shallow → All 6 TradingSignal fields checked
- [x] AC-01 too weak → Specific: "all 10 ticker symbols from config.TICKERS"
- [x] Missing date validation AC → AC-11 added
- [x] AC-10 ambiguous → Clarified preamble exclusion and counting rules
- [x] Missing Ticket 6 dependency → Corrected to [Ticket 4, Ticket 6, Ticket 7]
- [x] 10× model loads → FinBertSentiment instantiated once
- [x] AC-11 validation location → Moved to _validate_date() in orchestrate
- [x] FusedRecord deserialization → _decode_fused_record() function
- [x] HTML parser leniency → _WellFormednessChecker example in spec
- [x] AC-01 TICKERS ambiguity → Explicit `src.generate.config.TICKERS` reference
- [x] AC-11 only empty → Extended to malformed format too
- [x] Missing output directory → os.makedirs with exist_ok=True
- [x] AC-10 preamble off-by-one → Count data between separators
- [x] HTML warnings_section when absent → Empty string
- [x] `volume: int` coercion → Added `int()` in `_decode_fused_record()`
- [x] `s.ticker` HTML escaping → Added `html.escape(s.ticker)` (Code Review R1)
- [x] Unused fixtures → Added 6 tests consuming all fixtures (Code Review R1)
- [x] `txt`→`text` field mapping → Added `_ext_to_attr` dict (Code Review R2)

---

## 8. Lessons Learned

### What Went Well

1. **Spec reviews caught issues in layers** — Round 1 found structural gaps (undefined types, missing formats). Round 2 found pipeline integration gaps (single vs multi-ticker, data flow). Rounds 3-5 found implementation details (imports, deserialization, lenient parsers). Each round focused on a different depth level, validating the multi-pass approach.

2. **Dependency analysis surfaced pipeline gaps** — Reading `src/pipeline.py` to check the single-ticker vs multi-ticker assumption revealed an architectural conflict that no spec-only review would catch. This matches the Ticket 7 post-mortem finding that dependency analysis should be standard pre-implementation.

3. **Format specs prevented implementation drift** — Having three concrete format specs (text column widths, JSON schema, HTML template) with examples means any implementation can be validated against a fixed target. The spec itself includes test guidance for tricky parts (HTMLParser subclass, preamble counting).

4. **Mock complexity remained LOW throughout** — Pure Python formatting meant no torch mocking, no MockTensor, no sys.modules injection. The only mocking needed is for the orchestrator's FinBertSentiment (model loading) and file I/O — both well-understood patterns.

5. **Smoke test demotion was the right call** — The 30-second performance guarantee from the original ticket was moved to a smoke test early. This prevented a non-deterministic AC from blocking verification while keeping the benchmark visible.

6. **5 rounds of iteration were acceptable** — Despite being more rounds than Ticket 7 (3), rounds 3-5 had zero blocking issues. The extra rounds were about spec polish and test guidance, not fundamental flaws. The ticket quality at round 5 is higher than any prior ticket's pre-implementation state.

7. **Code review caught a critical runtime crash** — The `txt`→`text` field mapping bug was found in round 2 of code review. Both `getattr(result, "txt")` and `result.txt` look obviously wrong once pointed out, but neither the spec review nor the dependency analysis flagged it because the issue was in implementation, not spec. This validates doing at least one code review pass after implementation, even for well-specified tickets.

8. **Fixture-first pattern was followed** — Unlike Ticket 7 (where fixtures were created after tests and stayed unused), Ticket 8's tests were written to consume fixtures from the start. The initial review finding about unused fixtures was a different pattern (individual signal fixtures that no single test consumed).

### What Could Improve

1. **Early pipeline integration check** — The single-ticker vs multi-ticker conflict was discovered in round 2, not round 1. A standard "read the existing pipeline code before reviewing" step in the TDD process would catch this class of issue earlier.

2. **Format spec templates** — Creating format specs from scratch for each new ticket is time-consuming. A library of format spec templates (text column layout, JSON schema examples, HTML boilerplate) would reduce effort and ensure consistency.

3. **Test guidance in spec** — The `_WellFormednessChecker` example in the format specs was added proactively in round 4. Including test infrastructure guidance in the spec itself (even as optional notes) reduces ambiguity for implementors and prevents AC-09 from being tested incorrectly.

4. **Cross-format ACs need extra care** — AC-10 (cross-format consistency) required more clarification than any single-format AC because it bridges three different representations. The preamble counting rule took two iterations to get right. Cross-format ACs might benefit from a standard template phrase.

5. **Early dependency validation** — The missing Ticket 6 dependency (orchestrator calls FinBertSentiment) was caught in round 3 but could have been caught in round 1 by tracing the orchestration flow through the pipeline. A "trace all imports and function calls referenced" step would help.

6. **"Omit if empty" patterns need explicit ACs** — The JSON spec says "omit warnings if empty" but no AC verified this behavior. Any spec-level "omit if" or "default when absent" pattern should have a corresponding AC or explicit test note.

7. **File extension ↔ field name mapping is a design pattern** — The `txt`→`text` bug is a recurring pattern where file extensions don't match attribute names. A convention like `ReportResult` using `.txt`, `.json`, `.html` methods (returning strings) instead of getattr, or storing content in a `dict[str, str]` with extension keys, would prevent this class of bug.

8. **Code review after implementation is essential** — All 3 code review findings (unused fixtures, missing escaping, wrong field mapping) were pure implementation bugs that no spec review could prevent. Without a code review pass, the `txt`→`text` bug would have crashed any orchestration run.

### Key Metrics

| Metric | Value |
|--------|-------|
| Original ACs | 3 |
| Refined ACs | 11 |
| TDD review rounds | 5 |
| Code review rounds | 2 |
| Implementation issues found by dependency analysis | 4 |
| Files created | 6 (source) + 2 (test) |
| Files modified | 3 |
| Total tests | 34 |
| Test fixtures | 11 |
| Issues found by TDD review | 12 blocking + 7 moderate (R1) → 2 blocking + 8 moderate (R2) → 0+4 (R3→R5) |
| Issues found by dependency analysis | 4 (1 blocking, 1 medium, 2 low) |
| Issues found by code review | 3 (1 critical, 2 low) |
| Mock complexity | None for reporter (pure Python); bounded for orchestrator (FinBertSentiment) |
| New dependencies | 0 (f-strings) |

---

## 9. Acceptance Criteria Verification

| AC | Test(s) | Verification Method | Status |
|----|---------|---------------------|--------|
| AC-01 | `test_text_contains_all_tickers`, `test_json_is_valid_parseable`, `test_html_has_table_and_html_tags` | Structural: text contains all 10 ticker symbols from config.TICKERS; json.loads succeeds; html contains `<table>` and `</html>` | ✅ |
| AC-02 | `test_each_ticker_in_text`, `test_each_signal_label_in_text`, `test_each_confidence_in_text` | Structural: each known ticker, signal label (right-aligned), and confidence value appears in text output | ✅ |
| AC-03 | `test_json_has_signals_array`, `test_each_signal_has_six_fields` | Structural: JSON has `signals` array; each entry has all 6 TradingSignal fields | ✅ |
| AC-04 | `test_warnings_in_text`, `test_warnings_in_json`, `test_warnings_in_html`, `test_no_warnings_section_when_none`, `test_no_warnings_section_when_empty_list` | Structural: text has "Warnings" heading; JSON has `warnings` key with 3 entries; HTML has warning section; omitted when None/empty | ✅ |
| AC-05 | `test_value_error_raised` | Error: empty list → `ValueError` with descriptive message | ✅ |
| AC-06 | `test_type_error_raised` | Error: `None` input → `TypeError` with descriptive message | ✅ |
| AC-07 | `test_na_in_text`, `test_na_in_html`, `test_value_present_in_text` | Structural: entries with `market_return=None` show "N/A" in text and HTML; entries with market data show formatted percentage | ✅ |
| AC-08 | `test_8_char_hex`, `test_report_id_in_text/in_json/in_html` | Format: `report_id` matches `^[0-9a-f]{8}$`; appears in all 3 format strings | ✅ |
| AC-09 | `test_html_is_well_formed`, `test_html_with_warnings_is_well_formed` | Structural: HTML parseable by custom `_WellFormednessChecker` (tag stack + 14 void elements) | ✅ |
| AC-10 | `test_counts_match` | Consistency: data line count in text = JSON signals length = HTML `<tr>` count (excl. header row) | ✅ |
| AC-11 | `test_empty_date_raises`, `test_malformed_date_raises`, `test_valid_date_passes` | Error: `""` → `ValueError("date must not be empty")`; `"not-a-date"` → `ValueError("must be in YYYY-MM-DD format")`; `"2026-05-28"` passes | ✅ |

---

## 10. Timeline

| Date | Activity |
|------|----------|
| May 29, 2026 | Original ticket loaded (3 ACs, undefined TickerAnalysis type, no formats, wrong deps) |
| May 29, 2026 | TDD review round 1 (NEEDS REVISION — 12 blocking + 7 moderate issues) |
| May 29, 2026 | Fixed v1: ReportInput dataclass, added Ticket 4 dep, expanded to 10 ACs, full format specs, config.TICKERS, UUID4 report_id, in-memory output |
| May 29, 2026 | TDD review round 2 (NEEDS REVISION — 2 new blocking + 8 moderate issues) |
| May 29, 2026 | Fixed v2: Option B orchestration, warning propagation via FusedRecord, locked text column widths, strengthened AC-01/03/10, added AC-11 for date validation |
| May 29, 2026 | TDD review round 3 (APPROVE — 0 blocking, 4 moderate issues) |
| May 29, 2026 | Fixed v3: Added Ticket 6 dep, FinBertSentiment singleton pattern, AC-11 moved to orchestration, _decode_fused_record() spec |
| May 29, 2026 | TDD review round 4 (APPROVE — 0 blocking, 4 moderate issues) |
| May 29, 2026 | Fixed v4: _WellFormednessChecker example, AC-01 TICKERS reference clarified, AC-11 extended to malformed dates, os.makedirs added |
| May 29, 2026 | TDD review round 5 (APPROVE — 0 blocking, 4 moderate issues) |
| May 29, 2026 | Fixed v5: AC-10 preamble counting clarified, empty warnings behavior defined |
| May 29, 2026 | **Implementation**: config.py, models.py, reporter.py, orchestrate.py, __init__.py, __main__.py |
| May 29, 2026 | **Test implementation**: fixtures/report_data.py, test_report.py (28 tests), conftest.py |
| May 29, 2026 | **Code review round 1**: 2 issues (unused fixtures, missing html.escape on ticker) |
| May 29, 2026 | **Fixed**: 6 new tests consuming fixtures, html.escape added to ticker |
| May 29, 2026 | **Code review round 2**: 1 issue (txt→text field mapping — critical runtime crash) |
| May 29, 2026 | **Fixed**: `_ext_to_attr` mapping added; 34 tests all passing |
| May 29, 2026 | Post-mortem updated |

---

## 11. Next Steps

1. Mark Ticket 8 as ✅ COMPLETE in tickets index document
2. Proceed to downstream tickets that consume ReportResult (if any)
3. Codify the "pipeline dependency analysis" step as standard pre-implementation practice
4. Consider creating format spec templates for reuse in future tickets
5. Consider adding `dict[str, str]` content storage pattern to ReportResult to prevent extension→attribute mapping bugs
