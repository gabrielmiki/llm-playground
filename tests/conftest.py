"""Test configuration and fixtures for the llm-playground project."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_httpx_response() -> MagicMock:
    """Create a mock httpx.Response object."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.headers = {"content-type": "application/json"}
    response.json.return_value = {"data": "test"}
    response.text = '{"data": "test"}'
    response.is_success = True
    response.is_error = False
    return response


@pytest.fixture
def mock_httpx_client(mock_httpx_response: MagicMock) -> AsyncMock:
    """Create a mock httpx.AsyncClient that returns predefined responses."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=mock_httpx_response)
    client.post = AsyncMock(return_value=mock_httpx_response)
    client.request = AsyncMock(return_value=mock_httpx_response)
    client.aclose = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock()
    return client


@pytest.fixture
def async_session_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide a session-scoped async HTTP client with connection pooling."""
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
    client = httpx.AsyncClient(
        limits=limits,
        timeout=httpx.Timeout(30.0, connect=10.0),
    )
    yield client
    try:
        asyncio.run(client.aclose())
    except RuntimeError:
        pass


class SlowResponseTransport(httpx.BaseTransport):
    """Transport that delays response to trigger timeout."""

    def __init__(self, delay: float) -> None:
        self.delay = delay

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(self.delay)
        return httpx.Response(
            status_code=200,
            content=b'{"data": "ok"}',
            request=request,
        )


@pytest.fixture
def timeout_config() -> httpx.Timeout:
    """Timeout configuration matching AC-004: connect 10s, total 30s."""
    return httpx.Timeout(30.0, connect=10.0)


@pytest.fixture
def slow_response_client(timeout_config: httpx.Timeout) -> httpx.AsyncClient:
    """Client configured to trigger timeout (60s delay > 30s total)."""
    transport = SlowResponseTransport(delay=60.0)
    return httpx.AsyncClient(
        timeout=timeout_config,
        transport=transport,
    )


@pytest.fixture
def connect_timeout_client() -> httpx.AsyncClient:
    """Client configured to trigger connect timeout (1ms delay > 0ms connect)."""
    transport = SlowResponseTransport(delay=0.1)
    timeout = httpx.Timeout(1.0, connect=0.001)
    return httpx.AsyncClient(
        timeout=timeout,
        transport=transport,
    )


@pytest.fixture
def mock_timeout_response() -> MagicMock:
    """Create a mock response that simulates timeout behavior."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 0
    response.is_success = False
    response.is_error = True
    return response
