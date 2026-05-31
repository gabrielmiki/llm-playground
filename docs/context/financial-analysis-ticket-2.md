# Financial LLM Analysis - Implementation Tickets

Generated from PRD: Financial Markets LLM Analysis System

---

## Ticket 2: Market Data Collection

**type**: story  
**layer**: collect  
**complexity**: medium  
**dependencies**: [Ticket 1]  
**status**: ✅ COMPLETE  

**title**: Collect market data from free-tier financial APIs

**implementation**:
- `src/collect/exceptions.py` — Custom exception hierarchy (`MarketDataError`, `MarketDataParseError`, `MarketDataAPIError`, `MarketDataUnavailableError`)
- `src/collect/market_data.py` — Market data collector with fallback chain
- `src/collect/transformers.py` — API-specific response normalizers (Yahoo, AlphaVantage, Finnhub)
- `tests/fixtures/market_data.py` — Mock API responses for all providers
- `tests/test_market_data.py` — Test cases
- `.env.example` — Template for API keys

**description**:  
Implement data collection for stock prices, volume, and basic metrics. Primary source is Yahoo Finance, with Alpha Vantage as secondary and Finnhub as tertiary fallback. All API responses are normalized to a unified OHLCV schema.

**api_priority**: Yahoo Finance → Alpha Vantage → Finnhub

**api_key_env_vars**:
- Yahoo Finance: `YAHOO_API_KEY` (optional - uses public endpoint by default)
- Alpha Vantage: `ALPHAVANTAGE_API_KEY` (required)
- Finnhub: `FINNHUB_API_KEY` (required)

**api_responses** (raw formats before normalization):

```
Yahoo Finance: GET /v8/finance/chart/{ticker}?period1={unix_ts}&period2={unix_ts}&interval=1d
Response:
{
  "chart": {
    "result": [{
      "meta": {"symbol": "AAPL", "regularMarketTime": 1705276800, ...},
      "timestamp": [1705276800, 1705363200, ...],
      "indicators": {
        "quote": [{
          "open": [185.50, 186.20, ...],
          "high": [187.20, 188.10, ...],
          "low": [184.80, 185.50, ...],
          "close": [185.50, 186.75, ...],
          "volume": [45000000, 42000000, ...]
        }],
        "adjclose": [{ "adjclose": [185.25, 186.50, ...] }]
      }
    }]
  }
}

Alpha Vantage: GET /query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={key}
Response:
{
  "Meta Data": {"2. Symbol": "AAPL", "3. Last Refreshed": "2024-01-15"},
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
Note: Uses "5. adjusted close" for adjusted_close field when available.

Finnhub: GET /stock/candle?symbol={ticker}&resolution=D&from={unix_ts}&to={unix_ts}&token={key}
Response:
{
  "c": [185.50, 186.75],   // Close prices
  "h": [187.20, 188.10],   // High prices
  "l": [184.80, 185.50],   // Low prices
  "o": [185.00, 186.20],   // Open prices
  "v": [45000000, 42000000], // Volumes
  "t": [1705276800, 1705363200], // Timestamps (Unix)
  "s": "ok"  // Status: "ok" | "no_data"
}
```

**fallback_conditions**:
- **Trigger**: HTTP 429/4xx/5xx OR `MarketDataAPIError` OR `MarketDataParseError`
- **Per-source retry**: 3 attempts with exponential backoff (handled by `RetryableHTTPClient`)
- **Fallback sequence**: Yahoo Finance → Alpha Vantage → Finnhub → `MarketDataUnavailableError`
- **Rate limit handling**: On HTTP 429, skip remaining retries for that provider and fallback immediately

**weekend_holiday_handling**: Auto-roll to previous trading day if requested date is weekend/holiday

**custom_exceptions** (in `src/collect/exceptions.py`):
```python
class MarketDataError(Exception):  # Base exception
class MarketDataParseError(MarketDataError):  # Missing fields, wrong types, invalid JSON
class MarketDataAPIError(MarketDataError):     # HTTP 200 with error code in response body
class MarketDataUnavailableError(MarketDataError):  # All providers exhausted
```

**acceptance_criteria**:
- Given ticker "AAPL" and date, When `fetch_market_data("AAPL", date)` is called, Then returns `{open: float, high: float, low: float, close: float, volume: int, adjusted_close: float, timestamp: str}` where timestamp is ISO8601 format
- Given rate limiter at capacity (0 tokens), When a request is made, Then the client blocks until a token is available (via `TokenBucketRateLimiter.acquire()`), then proceeds with the request
- Given response missing required field 'close', When response is parsed, Then `MarketDataParseError` is raised with message "Missing required field: close" and error is logged at ERROR level with response snippet
- Given HTTP 200 with API error code in body, When response is parsed, Then `MarketDataAPIError` is raised with the error message from API
- Given Yahoo Finance returns HTTP 429 (rate limit), When after 3 retries, Then fallback to Alpha Vantage automatically
- Given Yahoo Finance + Alpha Vantage both fail (3 retries each), When exhausted, Then fallback to Finnhub
- Given all three providers fail, When `fetch_market_data` is called, Then `MarketDataUnavailableError` is raised after exhausting all fallbacks
- Given weekend date (Saturday), When `fetch_market_data` is called, Then auto-rolls to previous Friday and returns valid data
- Given holiday date, When `fetch_market_data` is called, Then auto-rolls to previous trading day and returns valid data

**api_spec** (internal):
```
Query: ticker: string, date: date
Returns: { open: float, high: float, low: float, close: float, volume: int, adjusted_close: float, timestamp: str }
```
