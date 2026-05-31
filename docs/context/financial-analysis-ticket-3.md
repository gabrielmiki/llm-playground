# Financial LLM Analysis - Implementation Tickets

Generated from PRD: Financial Markets LLM Analysis System

---

## Ticket 3: News Data Collection

**type**: story  
**layer**: collect  
**complexity**: medium  
**dependencies**: [Ticket 1]  
**status**: ✅ COMPLETE

**title**: Collect financial news articles from API sources

**implementation**:
- `src/collect/news_collector.py` — News collector with fallback chain
- `src/collect/news_transformers.py` — Normalizers for Finnhub/NewsAPI
- `src/collect/exceptions.py` — Add `NewsDataError` hierarchy
- `tests/fixtures/news_data.py` — Mock API responses
- `tests/test_news_collector.py` — 12 tests
- `.env.example` — Update with `NEWSAPI_KEY`

**description**:  
Implement news collection from Finnhub Company News API and NewsAPI Everything endpoint. Filter for relevance to specified tickers and date ranges with fallback chain.

**api_priority**: Finnhub Company News → NewsAPI Everything → NewsDataUnavailableError

**api_key_env_vars**:
- Finnhub: `FINNHUB_API_KEY` (required)
- NewsAPI: `NEWSAPI_KEY` (required)

**api_responses** (raw formats before normalization):

```
Finnhub Company News: GET https://finnhub.io/api/v1/company-news?symbol={ticker}&from={YYYY-MM-DD}&to={YYYY-MM-DD}&token={key}
Response:
[
  {
    "category": "general",
    "datetime": 1704067200,
    "headline": "Apple Reports Record Q4 Earnings",
    "id": 123456789,
    "image": "https://example.com/image.jpg",
    "related": "AAPL",
    "source": "Reuters",
    "summary": "Apple Inc. announced record quarterly earnings...",
    "url": "https://example.com/article"
  }
]

NewsAPI Everything: GET https://newsapi.org/v2/everything?q={ticker}&from={YYYY-MM-DD}&to={YYYY-MM-DD}&language=en&sortBy=publishedAt&pageSize=50&apiKey={key}
Response:
{
  "status": "ok",
  "totalResults": 1,
  "articles": [
    {
      "source": {"id": "reuters", "name": "Reuters"},
      "author": "John Doe",
      "title": "Apple Reports Record Q4 Earnings",
      "description": "Apple Inc. announced record quarterly earnings...",
      "url": "https://example.com/article",
      "urlToImage": "https://example.com/image.jpg",
      "publishedAt": "2024-01-15T10:30:00Z",
      "content": "Apple Inc. announced record quarterly earnings... (truncated to 200 chars)"
    }
  ]
}
Note: NewsAPI returns HTTP 200 even on error - check "status": "error" in body.
```

**fallback_conditions**:
- **Trigger**: HTTP 429/4xx/5xx OR `NewsDataError` OR `NewsDataParseError` OR HTTP 200 with `"status": "error"`
- **Per-source retry**: 3 attempts with exponential backoff (handled by `RetryableHTTPClient`)
- **Fallback sequence**: Finnhub → NewsAPI → `NewsDataUnavailableError`
- **Rate limit handling**: On HTTP 429, skip remaining retries for that provider and fallback immediately

**age_filter**: Exclude articles older than 365 days from requested date

**custom_exceptions** (in `src/collect/exceptions.py`):
```python
class NewsDataError(Exception):  # Base exception
class NewsDataParseError(NewsDataError):  # Missing fields, wrong types, invalid JSON
class NewsDataAPIError(NewsDataError):     # HTTP 200 with error status in body
class NewsDataUnavailableError(NewsDataError):  # All providers exhausted
```

**normalized_schema**:
```python
{
    "title": str,
    "source": str,
    "published_at": str,  # ISO8601 format
    "url": str,
    "summary": str         # truncated content/description
}
```

**acceptance_criteria**:
- Given ticker "AAPL" and date "2024-01-15", When `fetch_news("AAPL", "2024-01-15")` is called, Then returns list of `{title: str, source: str, published_at: str (ISO8601), url: str, summary: str}` normalized articles
- Given rate limiter at capacity (0 tokens), When a request is made, Then the client blocks until a token is available (via `TokenBucketRateLimiter.acquire()`), then proceeds with the request
- Given response missing required field 'headline' (Finnhub) or 'title' (NewsAPI), When response is parsed, Then `NewsDataParseError` is raised with message "Missing required field: headline/title" and error is logged at ERROR level with response snippet
- Given HTTP 200 with `"status": "error"` in body (NewsAPI), When response is parsed, Then `NewsDataAPIError` is raised with the error message from API
- Given Finnhub returns HTTP 429 (rate limit), When after 3 retries, Then fallback to NewsAPI automatically
- Given Finnhub + NewsAPI both fail (3 retries each), When exhausted, Then fallback to NewsDataUnavailableError
- Given all three providers fail, When `fetch_news` is called, Then `NewsDataUnavailableError` is raised after exhausting all fallbacks
- Given articles older than 365 days from requested date, When processing, Then they are filtered out and WARNING level log entry is emitted with count of excluded articles
- Given no articles for a ticker, When fetching, Then empty list is returned (not an error)
- Given weekend date (Saturday), When `fetch_news` is called, Then adjusts to previous Friday and returns valid articles
- Given holiday date, When `fetch_news` is called, Then adjusts to previous trading day and returns valid articles

**api_spec** (internal):
```
Query: ticker: string, date: string (YYYY-MM-DD), max_results: int (default 50)
Returns: [{ title: str, source: str, published_at: str (ISO8601), url: str, summary: str }]
Error: NewsDataError | NewsDataParseError | NewsDataAPIError | NewsDataUnavailableError
```
