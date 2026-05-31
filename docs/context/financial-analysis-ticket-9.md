# Financial LLM Analysis - Implementation Tickets

Generated from PRD: Financial Markets LLM Analysis System

---

## Ticket 9: Graceful Degradation & Error Handling

**type**: task  
**layer**: generate  
**complexity**: medium  
**dependencies**: [Ticket 2, Ticket 3, Ticket 4, Ticket 8]

**title**: Implement graceful degradation when data sources fail

**description**:  
Ensure the system handles partial failures gracefully. When primary data sources (market data and/or news) fail, the pipeline should attempt to substitute historical data from the most recent available trading day, append structured warnings indicating the degradation, and continue processing without crashing. If no fallback data exists, a warning is still emitted and the pipeline continues with `None` values. The existing `ValidationWarning` and report-warning infrastructure from Tickets 4 and 8 is reused — no new dataclass fields are added.

### Historical Fallback Definition

- **Source**: Existing `data/processed/fused/` directory (same directory `load_fused_record()` reads from)
- **Scan strategy**: Look back up to **5 previous trading days** (using weekends-only adjustment: Saturday → Friday, Sunday → Friday — matching `news_collector.py`'s `_get_weekday_adjustment()`). Use the first `FusedRecord` file found where the file exists, parses as valid JSON, and contains a non-`None` value for the field being substituted (e.g., if substituting `market_data`, the historical record must have `market_data` not `None`)
- **Selective substitution**: If market data failed, substitute only `market_data` from the historical record. If news failed, substitute only `news_articles`. If both failed, substitute both
- **No cache**: On first run or when no historical file exists within 5 days, issue a `fallback_failed` warning and proceed without substitution (market_data stays `None`, news stays empty list)

### Degradation Warning Categories

No new dataclass fields. Warnings use `ValidationWarning` (from Ticket 4) with the following category conventions:

| Category | When |
|----------|------|
| `degraded_market` | Market data unavailable, historical fallback used successfully for `market_data` |
| `degraded_news` | News data unavailable, historical fallback used successfully for `news_articles` |
| `fallback_failed` | Historical fallback attempted but no cached data found within 5-day window |
| `insufficient_data` | Both market AND news are unavailable with no fallback available |

These flow through the existing `FusedRecord.warnings → ReportInput.warnings → ReportGenerator` pipeline.

### Files to Create

```
src/generate/degradation.py        # Fallback coordinator: find_historical_fallback(), build_degradation_warnings()

tests/test_degradation.py          # 12-15 tests
tests/fixtures/degradation_data.py # Cached FusedRecords for multiple dates, failure mocks (~5 fixtures)
```

### Files to Modify

```
src/pipeline.py                    # Wrap MarketDataUnavailableError / NewsDataUnavailableError catch blocks:
                                     catch → call fallback → build warnings → append to FusedRecord.warnings → continue
tests/conftest.py                  # Register tests.fixtures.degradation_data in pytest_plugins
```

### Files Not Modified (no changes needed)

- `src/collect/` — exceptions already well-defined (`MarketDataUnavailableError`, `NewsDataUnavailableError`)
- `src/preprocess/` — degradation lives in `generate` layer
- `src/model/` — no changes
- `src/generate/reporter.py`, `orchestrate.py`, `config.py`, `models.py` — existing warning pipeline reused unchanged

### Pipeline Behavior Change

Currently, `pipeline.py` catches `MarketDataUnavailableError` and `NewsDataUnavailableError` silently and halts. The new behavior:

```
Stage 1 (market_data.fetch):
  degradation_warnings = []
  try:
      market_data = await collector.fetch(ticker)
  except MarketDataUnavailableError:
      historical = find_historical_fallback(ticker, date, "market")
      if historical and historical.market_data is not None:
          market_data = historical.market_data
          degradation_warnings.append(
              ValidationWarning("degraded_market", "market_data",
                                "Market data unavailable; used fallback from {historical.date}",
                                value=None))
      else:
          market_data = None
          degradation_warnings.append(
              ValidationWarning("fallback_failed", "market_data",
                                "Market data unavailable and no historical fallback found",
                                value=None))

Stage 2 (news.fetch):
  try:
      news_articles = await news_collector.fetch_news(ticker, date)
  except NewsDataUnavailableError:
      historical = find_historical_fallback(ticker, date, "news")
      if historical and historical.news_articles:
          news_articles = historical.news_articles
          degradation_warnings.append(
              ValidationWarning("degraded_news", "news_articles",
                                "News data unavailable; used fallback from {historical.date}",
                                value=None))
      else:
          news_articles = []
          degradation_warnings.append(
              ValidationWarning("fallback_failed", "news_articles",
                                "News data unavailable and no historical fallback found",
                                value=None))

Post-both-stages:
  if market_data is None and not news_articles:
      degradation_warnings.append(
          ValidationWarning("insufficient_data", "combined",
                            "No market data nor news available for {ticker}",
                            value=None))

→ Proceed to validation stage with guards:
  market_data = None  → skip MarketDataValidator (no crash)
  news_articles = []  → NewsValidator handles empty list normally

→ After validation, merge degradation_warnings into fused_record.warnings:
  fused_record = FusedRecord(ticker, date, market_data, news_articles,
                             warnings=degradation_warnings)

→ Continue to fusion / sentiment / signal / report as normal
```

**acceptance_criteria**:

- **AC-01**: Given market data fails (all 3 providers exhausted) and historical cache exists within the 5-day lookback window (see Historical Fallback Definition), When pipeline processes ticker, Then historical `market_data` is substituted and a `degraded_market` warning is appended to `FusedRecord.warnings`
- **AC-02**: Given news data fails (both providers exhausted) and historical cache exists within the 5-day lookback window, When pipeline processes ticker, Then historical `news_articles` are substituted and a `degraded_news` warning is appended to `FusedRecord.warnings`
- **AC-03**: Given market data fails and no historical cache exists within 5-day lookback, When pipeline processes ticker, Then `market_data` remains `None`, a `fallback_failed` warning is appended, and pipeline continues to next stage
- **AC-04**: Given both market AND news data fail and fallback is unavailable, When pipeline processes ticker, Then `insufficient_data` warning is appended, and pipeline continues to completion with `None`/empty values
- **AC-05**: Given market data fails but news succeeds, When pipeline processes ticker, Then market uses historical fallback, news runs normal, and both `degraded_market` + normal processing reflected in warnings and output
- **AC-06**: Given news data fails but market succeeds, When pipeline processes ticker, Then news uses historical fallback, market runs normal, and both `degraded_news` + normal processing reflected in warnings and output
- **AC-07**: Given multiple tickers with mixed failure modes, When running batch pipeline, Then each ticker independently handles degradation and aggregated warnings appear in final report (note: test implementation should use monkeypatch or dependency injection to simulate per-ticker collector failures)
- **AC-08**: Given any degradation occurred during processing, When report is generated (via existing `ReportGenerator`), Then warnings section is present in all three formats; text format renders each warning as `- {message}`; HTML renders warnings inside a `<div class="warning">` section; JSON includes `category`, `field`, `message`, and `value` fields per warning
