# Financial LLM Analysis - Implementation Tickets

Generated from PRD: Financial Markets LLM Analysis System

---

## Ticket 1: API Client Infrastructure

**type**: task  
**layer**: collect  
**complexity**: medium  
**dependencies**: []  
**status**: ✅ IMPLEMENTED

**title**: Set up async HTTP client infrastructure for financial APIs

**description**:  
Create the base infrastructure for making async HTTP requests to financial data providers. Implement rate limiting, retry logic with exponential backoff, and connection pooling.

**implementation**:
- `src/collect/rate_limiter.py` — TokenBucketRateLimiter with configurable rate
- `src/collect/client.py` — RetryableHTTPClient with retry/backoff
- `src/collect/__init__.py` — Package exports

**tests**:
- `tests/test_rate_limiter.py` — 10 tests
- `tests/test_client.py` — 13 tests

**acceptance_criteria**:
- Given a list of API endpoints, When requests exceed 60 req/min, Then requests are automatically delayed using token bucket algorithm (1 req/sec rate) to stay within limits, verified by measuring timestamps between requests
- Given a transient failure (5xx or 429 status), When a request fails, Then the system retries up to 3 times with exponential backoff starting at 1s (2^n ± 0.5s jitter, max 10s)
- Given concurrent requests, When all complete or timeout, Then active connection count returns to 0 and no sockets remain in TIME_WAIT state (verified via resource tracking)
- Given a request timeout (connect: 10s, total: 30s), When exceeded, Then httpx.TimeoutException is raised

---

## Ticket 2: Market Data Collection

**type**: story  
**layer**: collect  
**complexity**: medium  
**dependencies**: [Ticket 1]  

**title**: Collect market data from free-tier financial APIs

**description**:  
Implement data collection for stock prices, volume, and basic metrics from Finnhub and Alpha Vantage. Support Yahoo Finance as fallback for historical data.

**acceptance_criteria**:
- Given a ticker symbol, When data is fetched, Then OHLCV data is returned with timestamp
- Given rate limit exhaustion, When data is requested, Then request is queued and processed when limits reset
- Given malformed response, When data is received, Then appropriate error is logged and exception raised

**api_spec** (internal):
```
Query: ticker: string, date: date
Returns: { open, high, low, close, volume, adjusted_close }
```

---

## Ticket 3: News Data Collection

**type**: story  
**layer**: collect  
**complexity**: medium  
**dependencies**: [Ticket 1]  

**title**: Collect financial news articles from API sources

**description**:  
Implement news collection from Finnhub News API and NewsAPI. Filter for relevance to specified tickers and date ranges.

**acceptance_criteria**:
- Given a ticker and date, When news is fetched, Then articles from that date are returned
- Given no articles for a ticker, When fetching, Then empty list is returned (not an error)
- Given articles older than 1 year, When processing, Then they are excluded with warning logged

**api_spec** (internal):
```
Query: ticker: string, date: date, max_results: int (default 50)
Returns: [{ title, source, published_at, url, summary }]
```

---

## Ticket 4: Data Quality & Fusion

**type**: story  
**layer**: preprocess  
**complexity**: medium  
**dependencies**: [Ticket 2, Ticket 3]  

**title**: Build preprocessing pipeline for data quality and fusion

**description**:  
Implement text cleaning for financial articles, language detection, and fusion of market data with news. Handle edge cases like missing data, foreign language content, and data validation.

**acceptance_criteria**:
- Given non-English content, When processing, Then it is flagged and excluded from analysis
- Given garbled or malformed text, When cleaning, Then it is normalized or removed
- Given market data and news for same ticker, When fused, Then they are correlated by date/time

**api_spec** (internal):
```
Input: { market_data: MarketData, news: [NewsArticle] }
Output: { validated_market: MarketData, filtered_news: [NewsArticle], warnings: [Warning] }
```

---

## Ticket 5: Sentiment Analysis with Pretrained Model

**type**: story  
**layer**: model  
**complexity**: medium  
**dependencies**: [Ticket 4]  

**title**: Implement financial sentiment analysis using FinBERT

**description**:  
Fine-tune or use FinBERT for financial sentiment classification. Process news articles and return sentiment scores per article and aggregated per ticker.

**acceptance_criteria**:
- Given a financial news article, When analyzed, Then sentiment score (-1 to 1) is returned
- Given multiple articles for a ticker, When aggregated, Then weighted average sentiment is calculated
- Given empty article list, When analyzed, Then neutral sentiment with confidence 0.0 is returned

**api_spec** (internal):
```
Input: [NewsArticle]
Output: { sentiment_score: float, confidence: float, breakdown: [{article, score}] }
```

---

## Ticket 6: Trading Signal Generation

**type**: story  
**layer**: model  
**complexity**: complex  
**dependencies**: [Ticket 5]  

**title**: Generate buy/sell/hold signals from sentiment and market data

**description**:  
Combine sentiment analysis with market data (price trends, volume) to generate actionable trading signals with confidence scores and rationale.

**acceptance_criteria**:
- Given sentiment score and market data, When signal is generated, Then result is buy, sell, or hold
- Given signal, When generated, Then confidence score (0-1) is provided
- Given signal, When generated, Then human-readable rationale is included

**api_spec** (internal):
```
Input: { ticker: string, sentiment: SentimentResult, market_data: MarketData }
Output: { ticker, signal: enum(buy|sell|hold), confidence: float, rationale: string }
```

---

## Ticket 7: Multi-Format Report Generation

**type**: story  
**layer**: generate  
**complexity**: medium  
**dependencies**: [Ticket 6]  

**title**: Generate end-of-day reports in text, JSON, and HTML formats

**description**:  
Create report generation for all 10 tickers, producing analysis in plain text (readable), JSON (structured), and HTML (dashboard-ready).

**acceptance_criteria**:
- Given 10 tickers analyzed, When report is generated, Then all formats are produced
- Given analysis complete, When report is generated, Then it completes within 30 seconds (ASSUMPTION: local generation)
- Given warnings during analysis, When report is generated, Then warnings are included in all formats

**api_spec** (internal):
```
Input: { analyses: [TickerAnalysis], date: date }
Output: { report_id, text: string, json: object, html: string }
```

---

## Ticket 8: Graceful Degradation & Error Handling

**type**: task  
**layer**: generate  
**complexity**: medium  
**dependencies**: [Ticket 2, Ticket 3, Ticket 4]  

**title**: Implement graceful degradation when data sources fail

**description**:  
Ensure the system handles partial failures gracefully. Use historical data as fallback, mark incomplete analyses, and provide clear warnings without crashing.

**acceptance_criteria**:
- Given market data unavailable, When processing ticker, Then historical data is used as fallback
- Given all data sources fail for ticker, When processing, Then "insufficient_data" status is set
- Given any degradation, When report is generated, Then warnings section clearly lists all issues

---

## Ticket 9: Async Job Processing

**type**: task  
**layer**: generate  
**complexity**: medium  
**dependencies**: [Ticket 7]  

**title**: Implement async/background job processing for full analysis

**description**:  
Allow full analysis of up to 10 tickers to run in background, returning a job ID for status checks. Support queuing and status polling.

**acceptance_criteria**:
- Given up to 10 tickers, When analysis is submitted, Then job ID is returned immediately
- Given job ID, When status is checked, Then current state (queued/processing/complete/failed) is returned
- Given job complete, When report is retrieved, Then full analysis is available in all formats

**api_spec** (internal):
```
POST /analyze
Body: { tickers: [string], date: date }
Returns: { job_id: string, status: string }

GET /report/{job_id}
Returns: { status, report: Report | null }
```

---

## Ticket 10: Integration & End-to-End Test

**type**: task  
**layer**: generate  
**complexity**: medium  
**dependencies**: [Ticket 8, Ticket 9]  

**title**: Create integration test for full analysis pipeline

**description**:  
Write end-to-end test that verifies complete pipeline: submit tickers → collect data → analyze → generate report. Mock external APIs for deterministic testing.

**acceptance_criteria**:
- Given 3 test tickers with mocked data, When full pipeline runs, Then report contains signals for all tickers
- Given mocked API failures, When pipeline runs, Then graceful degradation is verified
- Given successful run, When output is validated, Then all formats are valid and complete

---

## Implementation Order

```
Phase 1: Foundation
├── Ticket 1: API Client Infrastructure
├── Ticket 2: Market Data Collection
└── Ticket 3: News Data Collection

Phase 2: Processing
├── Ticket 4: Data Quality & Fusion
└── Ticket 8: Graceful Degradation & Error Handling (parallel with Ticket 4)

Phase 3: Model
├── Ticket 5: Sentiment Analysis with FinBERT
└── Ticket 6: Trading Signal Generation

Phase 4: Output
├── Ticket 7: Multi-Format Report Generation
├── Ticket 9: Async Job Processing
└── Ticket 10: Integration & End-to-End Test
```

---

## Assumptions

- ASSUMPTION: Free-tier API limits are sufficient for < 10 tickers/day analysis
- ASSUMPTION: Local LLM inference (or cloud API) for sentiment analysis
- ASSUMPTION: Reports stored locally in `data/processed/reports/` directory
- ASSUMPTION: Async processing uses background threads/tasks (not separate worker service)
