# Financial LLM Analysis - Implementation Tickets

Generated from PRD: Financial Markets LLM Analysis System

---

## Ticket 8: Multi-Format Report Generation

**type**: story  
**layer**: generate  
**complexity**: medium  
**dependencies**: [Ticket 4, Ticket 6, Ticket 7]  

**title**: Generate end-of-day reports in text, JSON, and HTML formats

**description**:  
Create report generation for all 10 configured tickers, producing analysis in plain text (human-readable), JSON (structured), and HTML (self-contained table). Each format includes the same data: per-ticker trading signals with confidence, sentiment, market return, and rationale. If validation warnings were produced during preprocessing, they are included in all formats.

---

### acceptance_criteria

- AC-01: Given 10 TradingSignal objects (buy/sell/hold mix), When ReportGenerator.generate() is called, Then returns ReportResult whose text report contains all 10 ticker symbols from `src.generate.config.TICKERS`, json is a valid parseable JSON string, and html contains `<table>` and `</html>` tags
- AC-02: Given 10 TradingSignal objects with known tickers, When text report is inspected, Then each ticker symbol, signal label, and confidence value appears in the output
- AC-03: Given 10 TradingSignal objects, When JSON report is parsed, Then it is valid JSON with a `signals` array containing entries that each have all 6 TradingSignal fields: `ticker`, `signal`, `confidence`, `sentiment_score`, `market_return`, and `rationale`
- AC-04: Given 3 ValidationWarning objects with varying categories, When ReportGenerator.generate() is called with warnings included, Then all three formats contain warning content: text has a "Warnings" section, JSON has a `warnings` key with 3 entries, HTML has warning content in a styled warning section below the table
- AC-05: Given an empty list of TradingSignal objects, When ReportGenerator.generate() is called, Then ValueError is raised with a descriptive message
- AC-06: Given None as ReportInput, When ReportGenerator.generate() is called, Then TypeError is raised with a descriptive message
- AC-07: Given TradingSignal objects where some have market_return=None, When the text and HTML reports are inspected, Then those entries show "N/A" for the market return
- AC-08: Given a ReportResult, When report_id is inspected, Then it is an 8-character hex string matching `^[0-9a-f]{8}$`
- AC-09: Given a generated HTML report, When parsed by Python's html.parser, Then it is well-formed HTML (no unclosed tags, parseable without error)
- AC-10: Given 10 TradingSignal objects, When all three formats are inspected, Then the number of data lines in the text format (excluding the preamble: Report header, blank line, column headers, and separator line) equals the length of the `signals` array in JSON and equals the number of `<tr>` rows in HTML (excluding the header row)
- AC-11: Given an empty string or malformed string as date (e.g., "" or "not-a-date"), When run_report_generation() is called, Then ValueError is raised with a descriptive message

---

### format_specs

#### Text Format

```
Report: {date}
Report ID: {report_id}
============================================================

Ticker     Signal        Confidence   Sentiment    Market Return  Rationale
---------------------------------------------------------------------
AAPL       buy               0.65      +0.7000        +5.00%     Sentiment positive (0.70) with...
MSFT       hold              0.25      +0.0500        +0.20%     Sentiment neutral (0.05) with...
JPM        sell              0.55      -0.6000        -3.00%     Sentiment negative (-0.60) with...

============================================================
Warnings:
- Market data warning: open price is 0.0 for AAPL (daily_return defaulted to 0.0)
```

- Header with date and report_id
- Column spec (fixed-width, right-aligned numbers):

  | Column | Width | Format | Alignment |
  |--------|-------|--------|-----------|
  | Ticker | 10 | `{:<10}` | left |
  | Signal | 12 | `{:>12}` | right |
  | Confidence | 12 | `{:>10.2f}` | right |
  | Sentiment | 12 | `{:>+10.4f}` | right |
  | Market Return | 13 | `{:>12}` (`+5.00%` or `N/A`) | right |
  | Rationale | remaining | first 60 chars + `...` if longer | left |

- Separator line: `"-" * 69`
- Footer divider: `"=" * 60`
- Warnings section (if any) below footer, one `"- "` bullet per warning using `warning.message`

#### JSON Format

```json
{
  "report_id": "a1b2c3d4",
  "date": "2026-05-28",
  "signals": [
    {
      "ticker": "AAPL",
      "signal": "buy",
      "confidence": 0.65,
      "sentiment_score": 0.70,
      "market_return": 0.05,
      "rationale": "Sentiment positive (0.70)..."
    }
  ],
  "warnings": [
    {
      "category": "market_data",
      "field": "open",
      "message": "open price is 0.0, daily_return defaulted to 0.0",
      "value": "0.0"
    }
  ]
}
```

- Top-level keys: `report_id`, `date`, `signals`, `warnings` (omit warnings if empty)
- Each signal entry mirrors TradingSignal fields (ticker, signal, confidence, sentiment_score, market_return, rationale)
- `market_return`: number if present, `null` if the signal had no market data (market_return=None on TradingSignal)
- Warning entries are serialized ValidationWarning objects (category, field, message, value)

#### HTML Format

Self-contained HTML with inline CSS (no external dependencies):

```html
<!DOCTYPE html>
<html>
<head><title>Report: {date}</title>
<style>
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
  th { background: #f5f5f5; }
  .buy  { color: green; font-weight: bold; }
  .sell { color: red; font-weight: bold; }
  .hold { color: #888; }
  .warning { background: #fff3cd; }
</style>
</head>
<body>
<h1>End-of-Day Report</h1>
<p>Date: {date} | Report ID: {report_id}</p>
<table>
  <tr><th>Ticker</th><th>Signal</th><th>Confidence</th>
      <th>Sentiment</th><th>Market Return</th><th>Rationale</th></tr>
  {rows}
</table>
{warnings_section}
</body></html>
```

- Signal cells use CSS class: `buy`, `sell`, or `hold` for color-coding
- Warnings appear in a styled `<div class="warning">` below the table

**Testing note for AC-09:** Python's `html.parser.HTMLParser` is a lenient streaming parser — it does not validate tag balance by default. To verify well-formedness, the test helper should subclass `HTMLParser` with a tag stack that tracks open/close pairs with void-element awareness (`<br>`, `<hr>`, `<img>`, `<meta>`, `<link>`, etc.). Example approach:
```python
_VOID_ELEMENTS = {"br", "hr", "img", "input", "meta", "link"}

class _WellFormednessChecker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tag_stack: list[str] = []
    def handle_starttag(self, tag, attrs):
        if tag not in _VOID_ELEMENTS:
            self.tag_stack.append(tag)
    def handle_endtag(self, tag):
        if tag in _VOID_ELEMENTS:
            return  # ignore void elements
        if not self.tag_stack:
            raise ValueError(f"unexpected </{tag}>")
        self.tag_stack.pop()  # assumes correct ordering
```

---

### api_spec

#### Data Models

```python
# src/generate/models.py

from dataclasses import dataclass
from src.model.pretrained.signals import TradingSignal
from src.preprocess.validator import ValidationWarning


@dataclass
class ReportInput:
    ticker_signals: list[TradingSignal]
    date: str
    warnings: list[ValidationWarning] | None = None


@dataclass
class ReportResult:
    report_id: str       # uuid4().hex[:8]
    text: str            # plain text report
    json: str            # JSON string (serialized)
    html: str            # self-contained HTML string
```

#### Ticker Configuration

```python
# src/generate/config.py

TICKERS: list[str] = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",
    "TSLA", "NVDA", "JPM", "V", "JNJ",
]
```

#### Generator Class

```python
# src/generate/reporter.py

import uuid


class ReportGenerator:
    def generate(self, input: ReportInput) -> ReportResult:
        """Generate multi-format report from trading signals.

        Args:
            input: ReportInput containing ticker_signals, date, and optional warnings.

        Returns:
            ReportResult with report_id, text, json, and html strings.

        Raises:
            TypeError: If input is None.
            ValueError: If ticker_signals is empty.
        """
        ...

    def _format_text(self, input: ReportInput) -> str: ...
    def _format_json(self, input: ReportInput) -> str: ...
    def _format_html(self, input: ReportInput) -> str: ...
```

---

### orchestration

The report generator is a **separate orchestration step** — not a new pipeline stage. The existing per-ticker pipeline is unchanged.

**Workflow:**

```
Step 1:  uv run python -m src.pipeline --ticker AAPL  --date 2026-05-28   (per ticker, existing)
         ... repeat for each of 10 configured tickers ...
         Each run writes FusedRecord to data/processed/fused/{TICKER}_{DATE}.json

Step 2:  uv run python -m src.generate --date 2026-05-28                  (new, this ticket)
```

The CLI entry point (`src/generate/__main__.py`) delegates to `src/generate/orchestrate.py`:

```python
# src/generate/orchestrate.py

from src.generate.config import TICKERS


def run_report_generation(date: str) -> ReportResult:
    """Run end-to-end report generation for all configured tickers.

    Instantiates FinBertSentiment once (not per ticker) to avoid 10×
    model downloads. For each ticker in TICKERS:
      1. Load FusedRecord from disk via load_fused_record()
      2. Run FinBertSentiment.analyze(fused) → SentimentResult
      3. Run TradingSignalGenerator.generate() → TradingSignal
      4. Collect fused.warnings as list[ValidationWarning]

    Bundles all signals + warnings into ReportInput and calls ReportGenerator.

    Raises:
        FileNotFoundError: If a FusedRecord file is missing for any ticker.
        ValueError: If date is empty or invalid (validated by _validate_date).
    """
    ...


def load_fused_record(ticker: str, date: str) -> FusedRecord:
    """Load a FusedRecord from disk at data/processed/fused/{ticker}_{date}.json.

    Deserializes the JSON file using _decode_fused_record() to reconstruct
    FusedRecord, MarketData, and ValidationWarning dataclasses from their
    serialized dict forms.
    """
    ...


def _decode_fused_record(data: dict) -> FusedRecord:
    """Deserialize a FusedRecord from its JSON dict representation.

    Reconstructs MarketData from its __dict__, wraps ValidationWarning
    dicts into ValidationWarning instances, and returns a fully typed
    FusedRecord.
    """
    ...


def _validate_date(date: str) -> None:
    """Raise ValueError if date is empty or not in YYYY-MM-DD format."""
    if not date:
        raise ValueError("date must not be empty")
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"date must be in YYYY-MM-DD format, got {date!r}")
```

**Warning propagation:**

Warnings are extracted from each loaded `FusedRecord.warnings` and accumulated into a single list, then passed to `ReportInput.warnings`. The report generator itself does not need to know about `FusedRecord` — it only receives `list[TradingSignal]` and `list[ValidationWarning]` through `ReportInput`.

**File output (optional):**

After generating the report, the orchestrator saves the three formats to disk as a side effect of `run_report_generation()`:

```
data/processed/reports/{report_id}.txt
data/processed/reports/{report_id}.json
data/processed/reports/{report_id}.html
```

The output directory is created at the top of `run_report_generation()` via `os.makedirs("data/processed/reports", exist_ok=True)`. The `ReportResult` is always returned in-memory as the primary contract — file output is a secondary side effect for the CLI workflow. The write logic lives in `orchestrate.py` so that `__main__.py` stays thin (call, print confirmation, exit).

---

### __main__ entry point

```python
# src/generate/__main__.py

import argparse
from datetime import date

from src.generate.orchestrate import run_report_generation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate multi-format end-of-day reports from cached FusedRecords"
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Target date in YYYY-MM-DD format (default: today)",
    )
    args = parser.parse_args()

    result = run_report_generation(args.date)
    print(f"Report generated: {result.report_id}")
    print(f"  Text: data/processed/reports/{result.report_id}.txt")
    print(f"  JSON: data/processed/reports/{result.report_id}.json")
    print(f"  HTML: data/processed/reports/{result.report_id}.html")


if __name__ == "__main__":
    main()
```

---

### files_summary

| File | Action |
|------|--------|
| `src/generate/__init__.py` | **Update** — Add `ReportInput`, `ReportResult`, `ReportGenerator`, `run_report_generation` to `__all__` |
| `src/generate/__main__.py` | **Rewrite** — CLI entry point delegating to `orchestrate.py` |
| `src/generate/config.py` | **Create** — `TICKERS` list |
| `src/generate/models.py` | **Create** — `ReportInput`, `ReportResult` dataclasses |
| `src/generate/reporter.py` | **Create** — `ReportGenerator` class with `_format_text`, `_format_json`, `_format_html` |
| `src/generate/orchestrate.py` | **Create** — `run_report_generation()`, `load_fused_record()`, `_validate_date()` |
| `tests/fixtures/report_data.py` | **Create** — 8 fixtures: buy/sell/hold/no-market signals, mixed list of 10, empty list, warnings list, full ReportInput |
| `tests/conftest.py` | **Update** — Add `"tests.fixtures.report_data"` to `pytest_plugins` |
| `tests/test_report.py` | **Create** — ~15 tests covering all 11 ACs |

### smoke_tests

The 30-second completion guarantee from the original ticket is moved here — it is a benchmark/smoke test, not an acceptance criterion:

- **Smoke Test**: Given 10 TradingSignal objects with real-world data sizes, When ReportGenerator.generate() is called, Then it completes within 30 seconds on a local development machine (not enforced in CI)
