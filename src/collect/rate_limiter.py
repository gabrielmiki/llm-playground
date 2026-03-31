"""Token bucket rate limiter for API request throttling."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting behavior.

    Attributes:
        requests_per_minute: Maximum requests allowed per minute.
            Defaults to 60 (Finnhub free tier).
        burst_size: Maximum burst size for token bucket.
            Defaults to None (same as requests_per_minute).
    """

    requests_per_minute: int = 60
    burst_size: int | None = None

    @property
    def requests_per_second(self) -> float:
        """Convert requests per minute to requests per second."""
        return self.requests_per_minute / 60.0

    @property
    def capacity(self) -> int:
        """Get burst capacity, defaulting to requests_per_minute."""
        return (
            self.burst_size if self.burst_size is not None else self.requests_per_minute
        )


@dataclass
class RateLimitState:
    """Tracks rate limiter state for monitoring and testing.

    Attributes:
        requests_made: Timestamps of all requests made.
        delays_encountered: Seconds of delay imposed by rate limiting.
        tokens_available: Current token count.
    """

    requests_made: list[float] = field(default_factory=list)
    delays_encountered: list[float] = field(default_factory=list)
    tokens_available: float = 0.0


class TokenBucketRateLimiter:
    """Async token bucket rate limiter for API requests.

    Implements the token bucket algorithm to limit request rates while allowing
    bursts up to the configured capacity. This implementation is async-safe
    and can be shared across multiple concurrent tasks.

    The rate limiter automatically refills tokens at the specified rate.
    When a request is made, a token is consumed if available. If no tokens
    are available, the request waits until a token becomes available.

    Example:
        ```python
        limiter = TokenBucketRateLimiter(
            config=RateLimitConfig(requests_per_minute=60)
        )
        await limiter.acquire()
        # Now safe to make a request
        ```

    Attributes:
        config: Rate limiting configuration.
        state: Mutable state for tracking and testing.
    """

    __slots__ = ("config", "state", "_lock", "_last_update")

    def __init__(
        self,
        config: RateLimitConfig | None = None,
        state: RateLimitState | None = None,
    ) -> None:
        self.config = config or RateLimitConfig()
        self.state = state or RateLimitState()
        self._lock = asyncio.Lock()
        self._last_update: float = time.monotonic()
        self.state.tokens_available = float(self.config.capacity)

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._last_update = now
        self.state.tokens_available = min(
            self.config.capacity,
            self.state.tokens_available + elapsed * self.config.requests_per_second,
        )

    async def acquire(self) -> None:
        """Acquire permission to make a request.

        Waits if necessary until a token is available, then consumes it.
        This method is async-safe and can be called concurrently from
        multiple tasks.
        """
        async with self._lock:
            self._refill()

            if self.state.tokens_available < 1.0:
                wait_time = (
                    1.0 - self.state.tokens_available
                ) / self.config.requests_per_second
                self.state.delays_encountered.append(wait_time)
                await asyncio.sleep(wait_time)
                self._refill()

            self.state.tokens_available -= 1.0
            self.state.requests_made.append(time.monotonic())

    async def try_acquire(self) -> bool:
        """Try to acquire a token without blocking.

        Returns:
            True if a token was acquired, False otherwise.
        """
        async with self._lock:
            self._refill()

            if self.state.tokens_available >= 1.0:
                self.state.tokens_available -= 1.0
                self.state.requests_made.append(time.monotonic())
                return True
            return False

    def get_wait_time(self) -> float:
        """Get estimated wait time until a token is available.

        Returns:
            Seconds to wait for the next available token, or 0.0 if
            a token is immediately available.
        """
        if self.state.tokens_available >= 1.0:
            return 0.0
        return (1.0 - self.state.tokens_available) / self.config.requests_per_second


def create_finnhub_limiter() -> TokenBucketRateLimiter:
    """Create a rate limiter configured for Finnhub free tier (60 req/min).

    Returns:
        TokenBucketRateLimiter configured for Finnhub API limits.
    """
    return TokenBucketRateLimiter(config=RateLimitConfig(requests_per_minute=60))
