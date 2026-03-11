"""Low-level HTTP client with retry logic and error handling."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

import httpx

from reinforce_spec_sdk.exceptions import (
    NetworkError,
    RateLimitError,
    ReinforceSpecError,
    ServerError,
    TimeoutError,
    exception_from_response,
)

try:
    from reinforce_spec_sdk import __version__
except ImportError:
    __version__ = "1.0.0"

logger = logging.getLogger("reinforce_spec_sdk")

T = TypeVar("T")

# Type aliases for hooks
RequestHook = Callable[[httpx.Request], None]
ResponseHook = Callable[[httpx.Response], None]


@dataclass
class TimeoutConfig:
    """Granular timeout configuration.

    Attributes:
        connect: Timeout for establishing connection (seconds).
        read: Timeout for receiving response (seconds).
        write: Timeout for sending request (seconds).
        pool: Timeout for acquiring connection from pool (seconds).
    """

    connect: float = 5.0
    read: float = 30.0
    write: float = 30.0
    pool: float = 10.0

    def to_httpx(self) -> httpx.Timeout:
        """Convert to httpx.Timeout."""
        return httpx.Timeout(
            connect=self.connect,
            read=self.read,
            write=self.write,
            pool=self.pool,
        )


@dataclass
class PoolLimits:
    """Connection pool configuration.

    Attributes:
        max_connections: Maximum total connections.
        max_keepalive_connections: Maximum keepalive connections.
        keepalive_expiry: Time to keep idle connections alive (seconds).
    """

    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: float = 30.0

    def to_httpx(self) -> httpx.Limits:
        """Convert to httpx.Limits."""
        return httpx.Limits(
            max_connections=self.max_connections,
            max_keepalive_connections=self.max_keepalive_connections,
            keepalive_expiry=self.keepalive_expiry,
        )


class HTTPClient:
    """Low-level HTTP client with retry, timeout, and error handling.

    This class handles all HTTP communication with the ReinforceSpec API,
    including retries with exponential backoff, timeout handling, and
    error response parsing.

    Attributes:
        base_url: Base URL of the API.
        api_key: API key for authentication.
        timeout: Request timeout configuration.
        max_retries: Maximum number of retry attempts.
        retry_delay: Initial delay between retries.
        retry_max_delay: Maximum delay between retries.
        retry_jitter: Random jitter added to retry delays.
        pool_limits: Connection pool configuration.
        on_request: Hook called before each request.
        on_response: Hook called after each response.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float | TimeoutConfig = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        retry_max_delay: float = 30.0,
        retry_jitter: float = 5.0,
        pool_limits: PoolLimits | None = None,
        on_request: RequestHook | None = None,
        on_response: ResponseHook | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_max_delay = retry_max_delay
        self.retry_jitter = retry_jitter

        # Handle timeout configuration
        if isinstance(timeout, TimeoutConfig):
            self._timeout = timeout
        else:
            self._timeout = TimeoutConfig(
                connect=5.0,
                read=timeout,
                write=timeout,
                pool=10.0,
            )

        # Connection pool limits
        self._pool_limits = pool_limits or PoolLimits()

        # Request/response hooks for logging/debugging
        self._on_request = on_request
        self._on_response = on_response

        self._client: httpx.AsyncClient | None = None

    @property
    def _headers(self) -> dict[str, str]:
        """Build request headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"reinforce-spec-sdk-python/{__version__}",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers,
                timeout=self._timeout.to_httpx(),
                limits=self._pool_limits.to_httpx(),
                event_hooks={
                    "request": [self._on_request] if self._on_request else [],
                    "response": [self._on_response] if self._on_response else [],
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _should_retry(self, exc: Exception) -> bool:
        """Determine if an exception should trigger a retry."""
        if isinstance(exc, httpx.TimeoutException):
            return True
        if isinstance(exc, httpx.ConnectError):
            return True
        if isinstance(exc, ServerError) and exc.status_code in (502, 503, 504):
            return True
        return bool(isinstance(exc, RateLimitError))

    def _get_retry_delay(self, attempt: int, exc: Exception | None = None) -> float:
        """Calculate retry delay with exponential backoff and jitter."""
        # Check for Retry-After header in rate limit errors
        if isinstance(exc, RateLimitError) and exc.retry_after:
            return exc.retry_after

        # Exponential backoff: delay * 2^attempt
        delay = self.retry_delay * (2**attempt)
        delay = min(delay, self.retry_max_delay)

        # Add jitter
        jitter = random.uniform(0, self.retry_jitter)  # noqa: S311
        return delay + jitter

    async def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle API response and raise appropriate exceptions.

        Args:
            response: The HTTP response to handle.

        Returns:
            Parsed JSON response body.

        Raises:
            ReinforceSpecError: If the response indicates an error.
        """
        # Success responses
        if 200 <= response.status_code < 300:
            if response.status_code == 204:
                return {}
            return response.json()

        # Error responses
        try:
            error_body = response.json()
            message = error_body.get("detail", error_body.get("message", "Unknown error"))
            details = error_body.get("details", error_body)
        except Exception:
            message = response.text or f"HTTP {response.status_code}"
            details = None

        # Extract rate limit info from headers
        if response.status_code == 429:
            details = details or {}
            if "Retry-After" in response.headers:
                details["retry_after"] = float(response.headers["Retry-After"])
            if "X-RateLimit-Limit" in response.headers:
                details["limit"] = int(response.headers["X-RateLimit-Limit"])
            if "X-RateLimit-Remaining" in response.headers:
                details["remaining"] = int(response.headers["X-RateLimit-Remaining"])
            if "X-RateLimit-Reset" in response.headers:
                details["reset_at"] = float(response.headers["X-RateLimit-Reset"])

        raise exception_from_response(response.status_code, message, details)

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API path (e.g., "/v1/specs").
            json: JSON body for the request.
            params: Query parameters.
            headers: Additional headers.
            idempotency_key: Idempotency key for POST/PUT/PATCH requests.

        Returns:
            Parsed JSON response.

        Raises:
            ReinforceSpecError: On API errors.
            NetworkError: On connection failures.
            TimeoutError: On request timeout.
        """
        client = await self._get_client()

        request_headers = dict(headers or {})
        if idempotency_key and method.upper() in ("POST", "PUT", "PATCH"):
            request_headers["Idempotency-Key"] = idempotency_key

        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(
                    "Request %s %s (attempt %d/%d)",
                    method,
                    path,
                    attempt + 1,
                    self.max_retries + 1,
                )

                response = await client.request(
                    method=method,
                    url=path,
                    json=json,
                    params=params,
                    headers=request_headers,
                )

                return await self._handle_response(response)

            except httpx.TimeoutException as e:
                last_exception = TimeoutError(
                    message=f"Request timed out after {self._timeout.read}s",
                    timeout=self._timeout.read,
                )
                logger.warning("Request timeout (attempt %d): %s", attempt + 1, e)

            except httpx.ConnectError as e:
                last_exception = NetworkError(
                    message=f"Failed to connect to {self.base_url}",
                    cause=e,
                )
                logger.warning("Connection error (attempt %d): %s", attempt + 1, e)

            except (ServerError, RateLimitError) as e:
                last_exception = e
                logger.warning(
                    "Server error %d (attempt %d): %s",
                    e.status_code,
                    attempt + 1,
                    e.message,
                )

            except ReinforceSpecError:
                # Don't retry client errors (4xx except 429)
                raise

            except Exception as e:
                last_exception = NetworkError(
                    message=f"Unexpected error: {e}",
                    cause=e,
                )
                logger.error("Unexpected error (attempt %d): %s", attempt + 1, e)

            # Check if we should retry
            if attempt < self.max_retries and self._should_retry(last_exception):
                delay = self._get_retry_delay(attempt, last_exception)
                logger.info("Retrying in %.2fs...", delay)
                import asyncio

                await asyncio.sleep(delay)
            else:
                break

        # Raise the last exception if all retries failed
        if last_exception:
            raise last_exception

        # Should never reach here, but just in case
        raise NetworkError("Request failed after all retries")

    async def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Make a GET request."""
        return await self.request("GET", path, params=params, headers=headers)

    async def post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Make a POST request."""
        return await self.request(
            "POST",
            path,
            json=json,
            params=params,
            headers=headers,
            idempotency_key=idempotency_key,
        )

    async def put(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Make a PUT request."""
        return await self.request(
            "PUT",
            path,
            json=json,
            headers=headers,
            idempotency_key=idempotency_key,
        )

    async def delete(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Make a DELETE request."""
        return await self.request("DELETE", path, params=params, headers=headers)
