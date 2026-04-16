"""Tests for RetryableHTTPClient implementation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.collect.client import (
    DEFAULT_RETRYABLE_STATUSES,
    DEFAULT_TIMEOUT_CONFIG,
    RetryConfig,
    RetryableHTTPClient,
    RetryableHTTPError,
)
from src.collect.rate_limiter import TokenBucketRateLimiter


class TestRetryConfig:
    def test_default_values(self) -> None:
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 10.0
        assert config.jitter == 0.5
        assert config.retryable_statuses == DEFAULT_RETRYABLE_STATUSES

    def test_custom_retryable_statuses(self) -> None:
        config = RetryConfig(retryable_statuses=(500, 503))
        assert config.retryable_statuses == (500, 503)


class TestRetryableHTTPClient:
    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock(spec=httpx.AsyncClient)
        client.request = AsyncMock()
        client.aclose = AsyncMock()
        return client

    @pytest.fixture
    def rate_limiter(self) -> TokenBucketRateLimiter:
        return TokenBucketRateLimiter()

    @pytest.fixture
    def client(
        self,
        mock_client: AsyncMock,
        rate_limiter: TokenBucketRateLimiter,
    ) -> RetryableHTTPClient:
        http_client = RetryableHTTPClient(
            rate_limiter=rate_limiter,
            retry_config=RetryConfig(max_attempts=3, base_delay=0.01, jitter=0.001),
        )
        http_client._client = mock_client
        return http_client

    def _create_response(self, status_code: int) -> MagicMock:
        response = MagicMock(spec=httpx.Response)
        response.status_code = status_code
        response.is_success = status_code < 400
        response.is_error = status_code >= 400
        return response

    @pytest.mark.asyncio
    async def test_successful_request_first_try(
        self,
        client: RetryableHTTPClient,
        mock_client: AsyncMock,
    ) -> None:
        mock_client.request.return_value = self._create_response(200)

        response = await client.get("https://api.example.com/data")

        assert response.status_code == 200
        assert mock_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_503_then_success(
        self,
        client: RetryableHTTPClient,
        mock_client: AsyncMock,
    ) -> None:
        mock_client.request.side_effect = [
            self._create_response(503),
            self._create_response(200),
        ]

        response = await client.get("https://api.example.com/data")

        assert response.status_code == 200
        assert mock_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_429_then_success(
        self,
        client: RetryableHTTPClient,
        mock_client: AsyncMock,
    ) -> None:
        mock_client.request.side_effect = [
            self._create_response(429),
            self._create_response(200),
        ]

        response = await client.get("https://api.example.com/data")

        assert response.status_code == 200
        assert mock_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exhausted_raises_error(
        self,
        client: RetryableHTTPClient,
        mock_client: AsyncMock,
    ) -> None:
        mock_client.request.side_effect = [self._create_response(503) for _ in range(3)]

        with pytest.raises(RetryableHTTPError) as exc_info:
            await client.get("https://api.example.com/data")

        assert len(exc_info.value.attempts) == 3
        assert mock_client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_status_raises_immediately(
        self,
        client: RetryableHTTPClient,
        mock_client: AsyncMock,
    ) -> None:
        client.retry_config = RetryConfig(retryable_statuses=(500,))
        mock_client.request.return_value = self._create_response(400)

        with pytest.raises(RetryableHTTPError) as exc_info:
            await client.get("https://api.example.com/data")

        assert len(exc_info.value.attempts) == 1
        assert mock_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_connect_error_then_success(
        self,
        client: RetryableHTTPClient,
        mock_client: AsyncMock,
    ) -> None:
        mock_client.request.side_effect = [
            httpx.ConnectError("Connection refused"),
            self._create_response(200),
        ]

        response = await client.get("https://api.example.com/data")

        assert response.status_code == 200
        assert mock_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_network_error_max_attempts(
        self,
        client: RetryableHTTPClient,
        mock_client: AsyncMock,
    ) -> None:
        mock_client.request.side_effect = [
            httpx.NetworkError("Network failure"),
            httpx.ConnectError("Connection refused"),
            httpx.WriteError("Write failed"),
        ]

        with pytest.raises(RetryableHTTPError) as exc_info:
            await client.get("https://api.example.com/data")

        assert mock_client.request.call_count == 3
        assert exc_info.value.__cause__ is not None

    @pytest.mark.asyncio
    async def test_rate_limiter_called_per_attempt(
        self,
        client: RetryableHTTPClient,
        mock_client: AsyncMock,
        rate_limiter: TokenBucketRateLimiter,
    ) -> None:
        mock_client.request.side_effect = [
            self._create_response(503),
            self._create_response(200),
        ]

        await client.get("https://api.example.com/data")

        assert len(rate_limiter.state.requests_made) == 2

    @pytest.mark.asyncio
    async def test_post_request(
        self,
        client: RetryableHTTPClient,
        mock_client: AsyncMock,
    ) -> None:
        mock_client.request.return_value = self._create_response(201)

        response = await client.post(
            "https://api.example.com/data",
            json={"key": "value"},
        )

        assert response.status_code == 201
        mock_client.request.assert_called_once()
        call_kwargs = mock_client.request.call_args.kwargs
        assert call_kwargs.get("json") == {"key": "value"}

    @pytest.mark.asyncio
    async def test_close_client(self, client: RetryableHTTPClient) -> None:
        await client.close()
        assert client._client is None


class TestRetryableHTTPError:
    def test_error_message(self) -> None:
        attempts = [{"url": "test1"}, {"url": "test2"}, {"url": "test3"}]
        error = RetryableHTTPError(attempts)

        assert "3 attempts" in str(error)
        assert error.attempts == attempts


class TestCreateFinnhubClient:
    def test_creates_client_with_default_config(self) -> None:
        client = RetryableHTTPClient()

        assert client.retry_config.max_attempts == 3
        assert client.timeout == DEFAULT_TIMEOUT_CONFIG
        assert client.retry_config.retryable_statuses == DEFAULT_RETRYABLE_STATUSES
