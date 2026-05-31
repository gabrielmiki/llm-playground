# Impact & Dependency Chain Analysis: Ticket 8 — Multi-Format Report Generation

**Date:** May 29, 2026  
**Author:** AI Assistant (implementation planning)  
**Status:** Pre-implementation analysis  

---

## 1. Dependency Chain

### Direct Dependencies
```
Ticket 4 (Data Quality & Fusion) ──┐
Ticket 6 (Sentiment Analysis) ─────┤──→ Ticket 8 (Multi-Format Report)
Ticket 7 (Trading Signals) ────────┘
```

### What Each Dependency Provides

| Ticket | Module | Provides to Ticket 8 | Used By |
|--------|--------|----------------------|---------|
| Ticket 4 | `src/preprocess/fusion.py` | `FusedRecord` dataclass — loaded from disk, `warnings` field extracted for `ReportInput.warnings` | `load_fused_record()` in `orchestrate.py` |
| Ticket 4 | `src/preprocess/validator.py` | `ValidationWarning` dataclass — accumulated across all loaded FusedRecords | `ReportInput.warnings`, `reporter.py` format methods |
| Ticket 4 | `src/preprocess/output_writer.py` | `_fused_record_to_dict()` serialization format — determines `_decode_fused_record()` inverse | `orchestrate.py` deserialization |
| Ticket 6 | `src/model/pretrained/sentiment.py` | `FinBertSentiment` — called by orchestrator for each loaded FusedRecord; `SentimentResult` for scoring | `run_report_generation()` |
| Ticket 7 | `src/model/pretrained/signals.py` | `TradingSignal` dataclass — input to `ReportInput.ticker_signals`; `TradingSignalGenerator` for generation | `ReportInput`, `reporter.py` format methods; `run_report_generation()` |

### Import Chain (runtime)
```
__main__.py
  └── orchestrate.py
        ├── config.py                  (TICKERS list)
        ├── models.py                  (ReportInput, ReportResult)
        ├── reporter.py                (ReportGenerator)
        ├── src.preprocess.fusion      (FusedRecord)
        ├── src.preprocess.validator   (ValidationWarning)
        ├── src.model.pretrained.sentiment (FinBertSentiment)
        └── src.model.pretrained.signals   (TradingSignal, TradingSignalGenerator)
```

---

## 2. Impacted Files — Existing Codebase

### ✅ Zero modifications required
These files are read-only dependencies and are NOT modified by Ticket 8:

| File | Role | Rationale |
|------|------|-----------|
| `src/preprocess/fusion.py` | `FusedRecord` definition | Read-only dependency; deserialized in `orchestrate.py` |
| `src/preprocess/validator.py` | `ValidationWarning` definition | Read-only dependency; passed through `ReportInput` |
| `src/preprocess/output_writer.py` | Serialization format | Read-only reference for `_decode_fused_record()` |
| `src/model/pretrained/sentiment.py` | `FinBertSentiment`, `SentimentResult` | Read-only dependency; called by orchestrator |
| `src/model/pretrained/signals.py` | `TradingSignal`, `TradingSignalGenerator` | Read-only dependency; called by orchestrator |
| `src/model/pretrained/config.py` | — | Not referenced |
| `src/collect/market_data.py` | `MarketData` | Read-only dependency; deserialized in `_decode_fused_record()` |
| `src/pipeline.py` | Per-ticker pipeline | Untouched by design (Option B preserves existing CLI contract) |
| `tests/test_signals.py` | Ticket 7 tests | Untouched; new tests go in `test_report.py` |
| `tests/fixtures/signal_data.py` | Ticket 7 fixtures | Untouched; new fixtures in `report_data.py` |

### ✅ Modified files (minimal changes)

| File | Change | Risk Level |
|------|--------|------------|
| `src/generate/__init__.py` | Replace placeholder docstring; add `__all__` with exports | **None** — pure metadata |
| `src/generate/__main__.py` | Full rewrite: CLI argparser delegating to `run_report_generation()` | **Low** — match ticket spec |
| `tests/conftest.py` | Append `"tests.fixtures.report_data"` to `pytest_plugins` list | **None** — one-line additive change |

### ✅ New files created

| File | Lines (est.) | Complexity |
|------|--------------|------------|
| `src/generate/config.py` | ~15 | **Trivial** — constant list |
| `src/generate/models.py` | ~30 | **Low** — two dataclasses |
| `src/generate/reporter.py` | ~120 | **Medium** — three format methods, guard logic |
| `src/generate/orchestrate.py` | ~120 | **Medium** — orchestration, deserialization, file I/O |
| `tests/fixtures/report_data.py` | ~100 | **Medium** — 8 fixtures with TradingSignal construction |
| `tests/test_report.py` | ~250 | **Medium** — ~15 tests covering 11 ACs |

---

## 3. Delicate Points & Risks

### 🔴 High Risk

#### 3.1 FusedRecord Deserialization (`_decode_fused_record()`)

**Problem:** `output_writer.py` serializes `MarketData` using `dataclasses.fields()` → `dict`. `_decode_fused_record()` must reverse this exactly. There is no `from_dict()` on `MarketData`.

**Risks:**
- **Type coercion**: `json.load()` returns all numbers as `float`, but `MarketData.volume` is `int`. A `FusedRecord` loaded from disk would have `volume: float(N)` instead of `int(N)`. This may cause `MarketDataValidator` issues downstream (the validator checks `isinstance(data.volume, int)`).
- **`adjusted_close`**: Field is `float | None` in `MarketData`, but `json.load()` represents None as `null` → `None` in Python. This should work correctly, but any missing field would produce `KeyError`.
- **Field drift risk**: If `MarketData` gains new fields (e.g., support/resistance levels), `_decode_fused_record()` silently drops them because it uses explicit field assignment. A future Ticket adding fields would silently break deserialization.

**Recommendation:**
```python
def _decode_fused_record(data: dict) -> FusedRecord:
    md_data = data.get("market_data")
    market_data = None
    if md_data is not None:
        md_data["volume"] = int(md_data["volume"])  # JSON→int coercion
        market_data = MarketData(**md_data)
    warnings = [ValidationWarning(**w) for w in data.get("warnings", [])]
    return FusedRecord(
        ticker=data["ticker"],
        date=data["date"],
        market_data=market_data,
        news_articles=data.get("news_articles", []),
        warnings=warnings,
    )
```

**Mitigation:** Add explicit `volume: int` coercion in `_decode_fused_record()`. Document the field mapping clearly so future developers know what's happening.

---

#### 3.2 Orchestrator Mock Complexity (FinBertSentiment)

**Problem:** `FinBertSentiment.__init__()` downloads model weights from HuggingFace. Tests for `run_report_generation()` must mock `FinBertSentiment` to avoid actual model loading (~1.5s per download).

**Risks:**
- **Mock chain is deep**: `FinBertSentiment.__init__` calls `AutoTokenizer.from_pretrained`, `AutoModelForSequenceClassification.from_pretrained`, `AutoConfig.from_pretrained` — three HuggingFace calls that each require mocking.
- **`analyze()` returns `SentimentResult`**: The mock must return typed dataclasses, not plain dicts, or the downstream `TradingSignalGenerator.generate()` will fail.
- **`TradingSignalGenerator` is pure Python** — no mocking needed for it, but the orchestrator pipeline `FinBertSentiment → SentimentResult → TradingSignalGenerator → TradingSignal` must work end-to-end with mocked sentiment.

**Recommendation:**
```python
# In test_orchestrate.py
@pytest.fixture
def mock_finbert(mocker):
    mock = mocker.patch("src.generate.orchestrate.FinBertSentiment")
    instance = mock.return_value
    instance.analyze.return_value = SentimentResult(
        sentiment_score=0.7, confidence=0.8, breakdown=[]
    )
    return instance
```

**Mitigation:** Use `pytest-mock` (already available via `uv run pytest` with `mocker` fixture). Mock `FinBertSentiment` at the class level in `orchestrate.py`, not at the HuggingFace import level.

---

#### 3.3 Text Format Column Alignment

**Problem:** The text format has fixed-width columns with precise alignment spec:
```
| Column | Width | Format | Alignment |
|--------|-------|--------|-----------|
| Ticker | 10 | {:<10} | left |
| Signal | 12 | {:>12} | right |
| Confidence | 12 | {:>10.2f} | right |
| Sentiment | 12 | {:>+10.4f} | right |
| Market Return | 13 | {:>12} | right |
| Rationale | remaining | first 60 chars + ... | left |
```

**Risks:**
- **Width mismatch**: `Confidence` is 12 chars wide but format uses `{:>10.2f}` (10 chars) — the extra 2 chars must be pad to reach `12`. Similarly `Sentiment` uses `{:>+10.4f}` (11 chars) in a 12-char field. A simple `f"{value:>10.2f}  "` (2 trailing spaces) works but looks fragile.
- **Rationale truncation**: The rationale field takes "remaining width" — but the spec doesn't define total line width. From the example, the separator line is `"-" * 69` = 69 chars. After 10+12+12+12+13 = 59 fixed-width columns, that leaves 69-59 = 10 chars for rationale. But the example shows rationale content like `"Sentiment positive (0.70) with..."` — much more than 10 chars. Resolution: each data line exceeds the format spec width; the rationale flows into the remaining line space.
- **Market Return padding**: `"{:>12}"` with value `+5.00%` (6 chars) or `N/A` (3 chars) — the 12-char field needs explicit `f"{value:>12}"` to work.

**Recommendation:** Build each row using concatenated f-string segments with explicit width, then verify against test expectations derived from the spec's example output. The test is the source of truth.

**Mitigation:** Test-driven — write test fixtures with known TradingSignal values, compute expected text output manually from the spec, then compare. If the example in the ticket spec and the test expectations match, the format is correct.

---

#### 3.4 HTML Well-Formedness (AC-09)

**Problem:** Python's `html.parser.HTMLParser` is lenient — it does not validate tag balance by default. AC-09 requires a custom `_WellFormednessChecker` with tag-stack tracking and void-element awareness.

**Risks:**
- **Void element list**: Must include all HTML5 void elements: `area`, `base`, `br`, `col`, `embed`, `hr`, `img`, `input`, `link`, `meta`, `param`, `source`, `track`, `wbr`. The spec example only lists 6 — missing elements won't cause false positives (they'll just be tracked on the stack), but could cause false negatives if we add void elements.
- **Self-closing tags**: `<table />` or `<div />` — these are valid HTML5 and should be treated as void. The `_WellFormednessChecker` in the spec doesn't handle `/>`.
- **Void element mismatch**: The `parser.py` vs the test helper — two separate implementations could diverge.

**Recommendation:** Include the `_WellFormednessChecker` as a test helper in `test_report.py` (not in production code), with the full HTML5 void elements list.

**Mitigation:** Test-driven — write the checker first, then generate HTML, then verify. The checker is ~20 lines of portable Python.

---

### 🟡 Medium Risk

#### 3.5 `report_id` Collision Probability

**Risk:** `uuid.uuid4().hex[:8]` produces 8 hex chars = 4 billion possible values. Birthday paradox gives 50% collision probability at ~77k reports. For a personal project this is irrelevant, but worth logging a `warnings.warn` if someone wants to scale.

**Recommendation:** No action needed — 4B namespace is sufficient for this project's scale. Accept the risk.

---

#### 3.6 JSON `market_return: null` Serialization

**Risk:** `TradingSignal.market_return` is `float | None`. When `market_return=None` (no market data), JSON spec requires `null`. Python's `json.dumps()` handles this correctly by default (`json.dumps({"x": None})` → `'{"x": null}'`). However, `sentiment_score` is `float` (never None), so no special handling needed there.

**Recommendation:** Standard `json.dumps()` with `indent=2`. Verify in AC-03 test.

---

#### 3.7 Warning Propagation — Empty Warnings

**Risk:** `ReportInput.warnings` is `list[ValidationWarning] | None = None`. The JSON format spec says "omit warnings if empty" — but `json.dumps` will serialize the empty list as `"warnings": []`. To omit when empty, must explicitly check `if input.warnings` before adding to the dict.

**Recommendation:** In `_format_json()`:
```python
result: dict[str, Any] = {
    "report_id": ...,
    "date": ...,
    "signals": [...],
}
if input.warnings:
    result["warnings": [...serialized warnings...]]
```

---

#### 3.8 Load FusedRecord Path Construction

**Risk:** The spec says `data/processed/fused/{ticker}_{date}.json`. This must match the path format used by `FusedRecordWriter` in `output_writer.py`. Looking at `output_writer.py:46`:
```python
file_path = os.path.join(self.output_dir, f"{record.ticker}_{record.date}.json")
```
Where `output_dir = "data/processed/fused"`. The load path in `orchestrate.py` must be identical.

**Recommendation:** Use `os.path.join("data/processed/fused", f"{ticker}_{date}.json")` in `load_fused_record()`. If the output directory changes in a future ticket, both files must be updated. Consider a shared constant, but the ticket spec explicitly avoids modifying existing files, so duplicate the path in `orchestrate.py`.

---

#### 3.9 `_validate_date()` Location Boundary

**Risk:** AC-11 requires `run_report_generation()` to raise `ValueError` for empty/invalid dates. The spec places `_validate_date()` in `orchestrate.py`, called at the top of `run_report_generation()`. This is correct — fail fast before loading FinBertSentiment or any ticker data.

**Recommendation:** Implement `_validate_date()` as specified: check empty first, then try `datetime.strptime(date, "%Y-%m-%d")`.

---

#### 3.10 AC-01 TICKERS Reference — Index vs Content

**Risk:** AC-01 says "text contains all 10 ticker symbols from `src.generate.config.TICKERS`". The test must:
1. Build `ReportInput` with TradingSignal objects for all 10 configured tickers
2. Verify each ticker symbol appears in the text output

But the text format uses `{:<10}` (left-aligned) — searching for `"AAPL"` substring could match ticker prefix of a longer word (impossible at 10 chars, but theoretically). Use a stricter check like `in text` with right-padded ticker `f"{s.ticker:<10}"`.

**Recommendation:** In tests, check `f"{ticker:<10}" in result.text` rather than raw `ticker in result.text` to ensure the ticker appears in the expected column position.

---

### 🟢 Low Risk (Accept)

| Item | Risk | Mitigation |
|------|------|------------|
| AC-10 preamble counting off-by-one | **Low** — clarified in Round 5 to count data lines between `-` separator and `=` footer | Use regex `r"---.*\n(.*\n)*?===.*"` to extract data block |
| FinBertSentiment instantiated once | **Low** — spec explicitly calls out singleton pattern | Create sentiment instance before ticker loop in `run_report_generation()` |
| File output directory creation | **Low** — `os.makedirs` with `exist_ok=True` | Simple one-liner at top of `run_report_generation()` |
| `ReportGenerator.generate(None)` flagged by type checker | **Low** — `# type: ignore[arg-type]` in test | Acceptable; runtime guard catches it |

---

## 4. Implementation Order & Dependencies

```
Step 1: config.py                     (no dependencies)
Step 2: models.py                     (depends on TradingSignal, ValidationWarning)
Step 3: reporter.py                   (depends on models.py, config.py)
Step 4: orchestrate.py                (depends on models.py, reporter.py, FusedRecord, etc.)
Step 5: __init__.py, __main__.py      (depends on orchestrate.py)
--- (test infrastructure) ---
Step 6: tests/fixtures/report_data.py (depends on models.py, TradingSignal)
Step 7: tests/test_report.py          (depends on reporter.py, fixtures)
Step 8: tests/conftest.py             (one-line change)
--- (verification) ---
Step 9: uv run ruff check .
Step 10: uv run mypy src/
```

**Why this order:**
1. **config.py** first — zero dependencies, trivial constant
2. **models.py** second — depends only on external types (TradingSignal, ValidationWarning), not on other new code
3. **reporter.py** third — depends on models + config, but not on orchestration
4. **orchestrate.py** fourth — depends on all of the above + external modules (FinBertSentiment, FusedRecord)
5. **__main__.py** last — thin CLI wrapper around orchestrate.py
6. **Tests last** — fixtures depend on models.py; tests depend on reporter.py + fixtures

---

## 5. Key Architectural Decisions That Are Now Locked

| Decision | Locked In | Rationale |
|----------|-----------|-----------|
| **Option B** (separate orchestration) | Round 2 | Pipeline stays single-ticker; report is separate step |
| **ReportInput wrapper** (not modifying TradingSignal) | Round 1 | Warnings live on FusedRecord, not TradingSignal |
| **f-strings over jinja2** | Round 1 | Zero new dependencies for a single report template |
| **In-memory ReportResult as primary contract** | Round 1 | File output is side effect, not contract |
| **UUID4 hex[:8] for report_id** | Round 1 | Collision-free, clock-independent |
| **config.TICKERS constant** | Round 1 | Importable, single source of truth |
| **Date validation in orchestration** | Round 3 | Fail fast before model loading |
| **FinBertSentiment instantiated once** | Round 3 | Avoid 10× model downloads |

---

## 6. Test Strategy

### Unit Tests (Reporter)
- Direct `ReportInput` construction → `ReportGenerator.generate()` → assert `ReportResult` fields
- No mocking needed (pure Python string formatting)
- Each AC has 1-2 dedicated tests

### Unit Tests (Orchestrator)
- `_validate_date()`: empty string, malformed format, valid format
- `load_fused_record()`: actual JSON file read + deserialization (temp file fixture)
- `_decode_fused_record()`: dict → typed dataclasses, with `volume: int` coercion

### Integration Tests (Orchestrator)
- `run_report_generation()` with mocked `FinBertSentiment` + temp fused record files
- Verify `ReportResult` returned and files written to disk

### What NOT to Test
- **No end-to-end smoke test in CI** — the 30s benchmark is documented but not CI-enforced
- **No real model loading** — `FinBertSentiment` always mocked in unit tests
- **No HTTP tests** — report generation is purely local (no API calls)

---

## 7. Summary

| Metric | Value |
|--------|-------|
| Files created (source) | 4 (`config.py`, `models.py`, `reporter.py`, `orchestrate.py`) |
| Files created (test) | 2 (`report_data.py`, `test_report.py`) |
| Files modified | 3 (`__init__.py`, `__main__.py`, `conftest.py`) |
| Files read-only referenced | 7 (`fusion.py`, `validator.py`, `output_writer.py`, `sentiment.py`, `signals.py`, `market_data.py`, `pipeline.py`) |
| New dependencies | **0** (f-strings only) |
| High-risk items | 4 (deserialization, orchestrator mocks, text alignment, HTML well-formedness) |
| Medium-risk items | 6 (warnings omission, JSON null, path duplication, date validation, ticker content check, preamble counting) |
| Test count (planned) | ~15 |
| Mock complexity | LOW (reporter) / MEDIUM (orchestrator — FinBertSentiment mock needed) |
