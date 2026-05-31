# Architectural Decisions — Ticket 8: Multi-Format Report Generation

**Date:** May 29, 2026

## Decision Log

| # | Decision | Rationale | Locked In |
|---|----------|-----------|-----------|
| 1 | **Option B (separate orchestration)** — Pipeline stays single-ticker (`--ticker TICKER`); report is separate `uv run python -m src.generate --date YYYY-MM-DD` step | Avoids rewriting pipeline CLI contract; respects existing `--ticker` convention | Round 2 |
| 2 | **ReportInput wrapper** — New dataclass wrapping `ticker_signals: list[TradingSignal]`, `date: str`, `warnings: list[ValidationWarning] \| None` | Warnings live on `FusedRecord`, not `TradingSignal`; need separate container | Round 1 |
| 3 | **f-strings over Jinja2** — No template library | Zero new dependencies; report template is simple enough | Round 1 |
| 4 | **In-memory ReportResult as primary contract** — `ReportResult(text, json, html)` returned; file output is CLI side effect | Testable without file I/O; keeps generators pure | Round 1 |
| 5 | **UUID4 hex[:8] for report_id** — 8-char hex string | Clock-independent; 4B namespace sufficient for project scale | Round 1 |
| 6 | **config.TICKERS constant** — `list[str]` in `src/generate/config.py` | Importable, single source of truth, testable | Round 1 |
| 7 | **Date validation in orchestration layer** — `_validate_date()` in `orchestrate.py`, called at top of `run_report_generation()` | Fail fast before model loading (FinBertSentiment is expensive) | Round 3 |
| 8 | **FinBertSentiment instantiated once** — Created before ticker loop, not inside it | Avoid 10× HuggingFace model downloads (~500MB each) | Round 3 |
| 9 | **`_ext_to_attr` mapping** — `{"txt": "text", "json": "json", "html": "html"}` | Bridges file extension `.txt` to `ReportResult.text` attribute name | Code Review R2 |
| 10 | **Full HTML rationale (no truncation)** — HTML shows full `s.rationale` text | HTML has wrapping; truncation only needed in fixed-width text format | Round 1 |
| 11 | **html.escape() on all content fields** — ticker, signal, rationale, warnings | XSS prevention for potential web dashboard display | Code Review R1 |
| 12 | **Full HTML5 void elements (14)** in `_WellFormednessChecker` | Prevents false negatives from self-closing tags | Implementation |
| 13 | **`_decode_fused_record()` in orchestrate** — keeps reporter.py pure (no FusedRecord/MarketData awareness) | Separation of concerns: reporter formats strings, orchestrator handles data loading | Round 3 |
| 14 | **Warnings omitted from JSON when empty** — conditional key insertion | Matches spec: "omit warnings if empty" — `json.dumps` would produce `"warnings": []` | Implementation |

## Rejected Alternatives

| Alternative | Rejected Because |
|-------------|-----------------|
| **Option A (pipeline rewrite)** — `run_pipeline()` loops over 10 tickers internally | Changes CLI contract; requires testing existing pipeline consumers; higher risk |
| **Jinja2/HTML templates** — Template engine for HTML | Zero new dependency policy; f-strings sufficient for one template |
| **File-as-primary-contract** — Generator writes to disk directly | Cannot unit test without I/O; side effects mixed with logic |
| **File extension → attribute via dict** — `ReportResult` as `dict[str, str]` | Loses named field benefits; mypy/IDE autocomplete; `_ext_to_attr` is lower-friction fix |
| **`result.txt` attribute name** — Match file extension `.txt` | `result.txt` was briefly considered but `result.text` is more idiomatic |
