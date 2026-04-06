# Post-Mortem: Ticket 1 — API Client Infrastructure

**Date:** April 6, 2026  
**Status:** ✅ IMPLEMENTED  
**Review Status:** NEEDS_WORK (1 critical, 3 medium/low findings)

---

## 1. Overview

### Original Ticket
**Title:** Set up async HTTP client infrastructure for financial APIs

**Original Acceptance Criteria (ambiguous):**
```markdown
- Given a list of API endpoints, When requests are made, Then rate limits are respected (max 60 req/min for Finnhub)
- Given a transient failure, When a request fails, Then the system retries with exponential backoff up to 3 times
- Given concurrent ticker requests, When all complete, Then resources are properly released
```

---

## 2. Problems Identified

### TDD Review Round 1 — RED Status

| Issue | Severity | Problem |
|-------|----------|---------|
| Missing dependencies | **Blocking** | `pytest-asyncio`, `httpx` not declared |
| Ambiguous rate limiting | **Blocking** | "respected" undefined — hard throttle vs soft delay? |
| Ambiguous retry logic | **Blocking** | Which status codes trigger retry? |
| Missing backoff formula | **Blocking** | No concrete values for exponential backoff |
| Non-measurable cleanup | **Blocking** | "properly released" has no assertion |
| Missing timeout AC | **Blocking** | No timeout acceptance criterion |

### TDD Review Round 2 — YELLOW Status

After infrastructure created, still had:
- Missing resource tracking fixture for AC-003
- Missing timeout test fixture for AC-004

### Technical Bug Fixes (Discovered During Review)

1. **Rate limiter placement** — Initially placed outside retry loop, causing retries to bypass rate limiting
2. **Deprecated API** — Used `asyncio.get_event_loop().time()` instead of `time.perf_counter()`

### Code Review Findings — NEEDS_WORK

| Severity | Finding | Location |
|----------|---------|----------|
| **Critical** | Metrics accumulation across requests | client.py:120, 194 |
| Medium | Connection errors not retried | client.py:182-185 |
| Low | Unused `TimeoutError` class | client.py:73-77 |
| Low | `get_wait_time()` reads state without lock | rate_limiter.py:140-149 |

---

## 3. Fixes Applied

### A. Dependencies (`pyproject.toml`)

```toml
[project]
dependencies = [
    "pypdf>=6.9.2",
    "httpx>=0.28.0",  # Added
]

[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.25.0",  # Added
    "pytest-mock>=3.14.0",
    "ruff>=0.9.0",
    "mypy>=1.14.0",
]
```

### B. Refined Acceptance Criteria

```markdown
- Given a list of API endpoints, When requests exceed 60 req/min, Then requests 
  are automatically delayed using token bucket algorithm (1 req/sec rate) to stay 
  within limits, verified by measuring timestamps between requests

- Given a transient failure (5xx or 429 status), When a request fails, Then the 
  system retries up to 3 times with exponential backoff starting at 1s 
  (2^n ± 0.5s jitter, max 10s)

- Given concurrent requests, When all complete or timeout, Then active connection 
  count returns to 0 and no sockets remain in TIME_WAIT state (verified via 
  resource tracking)

- Given a request timeout (connect: 10s, total: 30s), When exceeded, Then 
  httpx.TimeoutException is raised
```

### C. Bug Fix: Rate Limiter Inside Retry Loop

**Before (BUG):**
```python
async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
    await self.rate_limiter.acquire()  # Outside loop - retries bypass rate limit!
    
    for attempt in range(self.retry_config.max_attempts):
        response = await self._attempt_request(method, url, **kwargs)
        # ...
```

**After (FIXED):**
```python
async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
    for attempt in range(self.retry_config.max_attempts):
        await self.rate_limiter.acquire()  # Inside loop - every attempt consumes token
        response = await self._attempt_request(method, url, **kwargs)
        # ...
```

### D. Bug Fix: Use `time.perf_counter()`

**Before (DEPRECATED):**
```python
async def _attempt_request(self, ...):
    start = asyncio.get_event_loop().time()  # Deprecated!
    response = await self.client.request(method, url, **kwargs)
    duration = asyncio.get_event_loop().time() - start
```

**After (FIXED):**
```python
async def _attempt_request(self, ...):
    start = time.perf_counter()  # Stable cross-platform API
    response = await self.client.request(method, url, **kwargs)
    duration = time.perf_counter() - start
```

---

## 4. Final Implementation

### Files Created

```
src/collect/
├── __init__.py       # Package exports
├── rate_limiter.py   # TokenBucketRateLimiter, RateLimitConfig (158 lines)
└── client.py         # RetryableHTTPClient, RetryConfig (344 lines)

tests/
├── conftest.py                    # Base fixtures, SlowResponseTransport
├── test_rate_limiter.py           # 10 tests (100 lines)
├── test_client.py                # 13 tests (199 lines)
└── fixtures/
    ├── __init__.py
    ├── rate_limiter.py            # TokenBucketRateLimiter fixture
    ├── http_client.py             # RetryableHTTPClient fixture
    └── resource_tracker.py         # SocketInspector, ResourceTracker
```

### `src/collect/rate_limiter.py` (Key Code)

```python
@dataclass
class RateLimitConfig:
    requests_per_minute: int = 60
    burst_size: int | None = None
    
    @property
    def requests_per_second(self) -> float:
        return self.requests_per_minute / 60.0

class TokenBucketRateLimiter:
    __slots__ = ("config", "state", "_lock", "_last_update")
    
    async def acquire(self) -> None:
        async with self._lock:
            self._refill()
            if self.state.tokens_available < 1.0:
                wait_time = (1.0 - self.state.tokens_available) / self.config.requests_per_second
                self.state.delays_encountered.append(wait_time)
                await asyncio.sleep(wait_time)
                self._refill()
            self.state.tokens_available -= 1.0
            self.state.requests_made.append(time.monotonic())
```

### `src/collect/client.py` (Key Code)

```python
@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 10.0
    jitter: float = 0.5
    retryable_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)

class RetryableHTTPClient:
    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        for attempt in range(self.retry_config.max_attempts):
            await self._rate_limiter.acquire()  # Every attempt consumes token
            response = await self._attempt_request(client, method, url, **kwargs)
            
            if response.is_success:
                return response
            if not self._is_retryable(response.status_code):
                raise RetryableHTTPError(self.metrics.attempts)
            
            delay = self._calculate_delay(attempt)  # 2^n ± jitter, capped
            await asyncio.sleep(delay)
        
        raise RetryableHTTPError(self.metrics.attempts)
```

---

## 5. Test Coverage

| Category | Tests | Status |
|----------|-------|--------|
| Rate Limiter Config | 4 | ✅ |
| Token Bucket Behavior | 5 | ✅ |
| Retry Config | 2 | ✅ |
| Retry Logic | 6 | ✅ |
| HTTP Client | 3 | ✅ |
| **Total** | **20** | ✅ |

**Test Results:** 23 passed in 1.29s

---

## 6. Outstanding Issues

### Critical (Must Fix Before Merge)

- [ ] **Metrics accumulation**: `self.metrics.attempts` never resets, causing unbounded growth

### Medium Priority

- [ ] **Connection errors**: Network failures (DNS, connection refused) not retried

### Low Priority

- [ ] **Unused code**: `TimeoutError` class defined but never used
- [ ] **Thread safety**: `get_wait_time()` reads state without lock (low risk - diagnostic method)

---

## 7. Lessons Learned

### What Went Well

1. **TDD workflow** — Multiple review rounds caught ambiguities before implementation
2. **Infrastructure first** — Building test fixtures before code ensured testability
3. **Clear ACs** — Refining acceptance criteria with measurable assertions prevented scope creep

### What Could Improve

1. **Code review earlier** — Should have done code review in parallel with TDD review
2. **Metrics reset strategy** — Should have decided upfront: per-request vs cumulative metrics
3. **Connection error handling** — Should have explicitly defined retry behavior for network errors

---

## 8. Acceptance Criteria Verification

| AC | Verification Method | Status |
|----|---------------------|--------|
| AC-001 | `state.requests_made` timestamps ≥ 1s apart after burst | ✅ |
| AC-002 | `RequestMetrics.attempts` count = 3, delay pattern verified | ✅ |
| AC-003 | `ResourceTracker.assert_clean()` checks connection count | ✅ |
| AC-004 | `pytest.raises(httpx.TimeoutException)` with slow transport | ✅ |

---

## 9. Timeline

| Date | Activity |
|------|----------|
| Apr 6, 2026 | Ticket created, TDD review round 1 (RED) |
| Apr 6, 2026 | Dependencies added, fixtures created |
| Apr 6, 2026 | TDD review round 2 (YELLOW) |
| Apr 6, 2026 | Resource tracker and timeout fixtures added |
| Apr 6, 2026 | TDD review round 3 (GREEN) |
| Apr 6, 2026 | Implementation started |
| Apr 6, 2026 | Implementation completed (20 tests passing) |
| Apr 6, 2026 | Code review (NEEDS_WORK - 1 critical, 3 low) |

---

## 10. Next Steps

1. Fix critical metrics accumulation issue
2. Consider adding connection error retry handling
3. Remove or use `TimeoutError` class
4. Proceed to Ticket 2: Market Data Collection
