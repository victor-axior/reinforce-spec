"""Exception hierarchy for the ReinforceSpec SDK."""

from __future__ import annotations

from typing import Any


class ReinforceSpecError(Exception):
    """Base exception for all ReinforceSpec SDK errors.

    Attributes:
        message: Human-readable error message.
        details: Structured error details from the API.
        status_code: HTTP status code if from API response.
    """

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.status_code = status_code

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, status_code={self.status_code})"


# =============================================================================
# Client-Side Errors (4xx)
# =============================================================================


class ValidationError(ReinforceSpecError):
    """Request validation failed.

    Raised when the request payload is invalid (e.g., missing required fields,
    invalid values, fewer than 2 candidates).

    Attributes:
        field: The field that failed validation (if available).
        value: The invalid value (if available).
    """

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        field: str | None = None,
        value: Any = None,
    ) -> None:
        super().__init__(message, details, status_code=400)
        self.field = field
        self.value = value


class AuthenticationError(ReinforceSpecError):
    """Authentication failed.

    Raised when API key is missing, invalid, or expired.
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details, status_code=401)


class AuthorizationError(ReinforceSpecError):
    """Authorization failed.

    Raised when the authenticated user doesn't have permission
    for the requested operation.
    """

    def __init__(
        self,
        message: str = "Not authorized for this operation",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details, status_code=403)


class NotFoundError(ReinforceSpecError):
    """Resource not found.

    Raised when a requested resource (e.g., request_id, policy) doesn't exist.
    """

    def __init__(
        self,
        message: str = "Resource not found",
        details: dict[str, Any] | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> None:
        super().__init__(message, details, status_code=404)
        self.resource_type = resource_type
        self.resource_id = resource_id


class ConflictError(ReinforceSpecError):
    """Resource conflict.

    Raised when there's a conflict with the current state (e.g., idempotency
    key already used with different parameters).
    """

    def __init__(
        self,
        message: str = "Request conflicts with existing state",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details, status_code=409)


class RateLimitError(ReinforceSpecError):
    """Rate limit exceeded.

    Raised when too many requests have been made. Check `retry_after`
    for when to retry.

    Attributes:
        retry_after: Seconds to wait before retrying.
        limit: The rate limit that was exceeded.
        remaining: Requests remaining (usually 0).
        reset_at: Unix timestamp when the limit resets.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        details: dict[str, Any] | None = None,
        retry_after: float | None = None,
        limit: int | None = None,
        remaining: int | None = None,
        reset_at: float | None = None,
    ) -> None:
        super().__init__(message, details, status_code=429)
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining
        self.reset_at = reset_at


class PayloadTooLargeError(ReinforceSpecError):
    """Request payload too large.

    Raised when the request body exceeds the maximum allowed size.
    """

    def __init__(
        self,
        message: str = "Request payload too large",
        details: dict[str, Any] | None = None,
        max_size: int | None = None,
    ) -> None:
        super().__init__(message, details, status_code=413)
        self.max_size = max_size


# =============================================================================
# Server-Side Errors (5xx)
# =============================================================================


class ServerError(ReinforceSpecError):
    """Server error.

    Raised when the server encounters an internal error. These are typically
    transient and can be retried.
    """

    def __init__(
        self,
        message: str = "Internal server error",
        details: dict[str, Any] | None = None,
        status_code: int = 500,
    ) -> None:
        super().__init__(message, details, status_code)


class ServiceUnavailableError(ReinforceSpecError):
    """Service temporarily unavailable.

    Raised when the service is overloaded or under maintenance.
    Check `retry_after` for when to retry.
    """

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        details: dict[str, Any] | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, details, status_code=503)
        self.retry_after = retry_after


# =============================================================================
# Network/Transport Errors
# =============================================================================


class NetworkError(ReinforceSpecError):
    """Network connectivity error.

    Raised when unable to connect to the API server.
    """

    def __init__(
        self,
        message: str = "Failed to connect to API",
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, details)
        self.cause = cause


class TimeoutError(ReinforceSpecError):
    """Request timeout.

    Raised when the request takes longer than the configured timeout.
    """

    def __init__(
        self,
        message: str = "Request timed out",
        details: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> None:
        super().__init__(message, details)
        self.timeout = timeout


# =============================================================================
# Exception Mapping
# =============================================================================


def exception_from_response(
    status_code: int,
    message: str,
    details: dict[str, Any] | None = None,
) -> ReinforceSpecError:
    """Create the appropriate exception from an API response.

    Args:
        status_code: HTTP status code.
        message: Error message from the response.
        details: Error details from the response body.

    Returns:
        The appropriate ReinforceSpecError subclass.
    """
    error_map: dict[int, type[ReinforceSpecError]] = {
        400: ValidationError,
        401: AuthenticationError,
        403: AuthorizationError,
        404: NotFoundError,
        409: ConflictError,
        413: PayloadTooLargeError,
        429: RateLimitError,
        500: ServerError,
        502: ServerError,
        503: ServiceUnavailableError,
        504: ServerError,
    }

    error_class = error_map.get(status_code, ReinforceSpecError)

    # Handle special cases with extra attributes
    if status_code == 429 and details:
        return RateLimitError(
            message=message,
            details=details,
            retry_after=details.get("retry_after"),
            limit=details.get("limit"),
            remaining=details.get("remaining"),
            reset_at=details.get("reset_at"),
        )

    if status_code == 503 and details:
        return ServiceUnavailableError(
            message=message,
            details=details,
            retry_after=details.get("retry_after"),
        )

    return error_class(message=message, details=details)
