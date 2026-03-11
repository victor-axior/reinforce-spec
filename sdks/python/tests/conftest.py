"""Pytest configuration for SDK tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture
def httpx_mock():
    """Create an httpx mock fixture for testing HTTP interactions."""
    import httpx

    mock_responses: list[dict] = []

    class MockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            for mock in mock_responses:
                if (
                    mock.get("method", "GET").upper() == request.method
                    and mock.get("url") == str(request.url)
                ):
                    return httpx.Response(
                        status_code=mock.get("status_code", 200),
                        headers=mock.get("headers", {}),
                        json=mock.get("json"),
                    )
            raise httpx.ConnectError(f"No mock response for {request.method} {request.url}")

    class MockHelper:
        """Helper class to register mock HTTP responses."""

        def __init__(self, transport: MockTransport):
            self._transport = transport

        def add_response(self, **kwargs: object) -> None:
            mock_responses.append(kwargs)

        @property
        def transport(self) -> MockTransport:
            return self._transport

    transport = MockTransport()
    helper = MockHelper(transport)

    # Patch httpx.AsyncClient to use our mock transport
    original_init = httpx.AsyncClient.__init__

    def patched_init(self_client, *args, **kwargs):
        kwargs["transport"] = transport
        kwargs.pop("http2", None)  # Remove http2 if present, mock doesn't support it
        original_init(self_client, *args, **kwargs)

    with patch.object(httpx.AsyncClient, "__init__", patched_init):
        yield helper
