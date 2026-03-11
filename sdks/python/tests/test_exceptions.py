"""Tests for exception hierarchy and error mapping."""

from __future__ import annotations

import pytest

from reinforce_spec_sdk.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NetworkError,
    NotFoundError,
    PayloadTooLargeError,
    RateLimitError,
    ReinforceSpecError,
    ServerError,
    ServiceUnavailableError,
    TimeoutError,
    ValidationError,
    exception_from_response,
)


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_all_exceptions_inherit_from_base(self):
        """Every SDK error must be a subclass of ReinforceSpecError."""
        subclasses = [
            ValidationError,
            AuthenticationError,
            AuthorizationError,
            NotFoundError,
            ConflictError,
            RateLimitError,
            PayloadTooLargeError,
            ServerError,
            ServiceUnavailableError,
            NetworkError,
            TimeoutError,
        ]
        for cls in subclasses:
            assert issubclass(cls, ReinforceSpecError), f"{cls.__name__} must inherit ReinforceSpecError"

    def test_base_error_str_with_status(self):
        err = ReinforceSpecError("test", status_code=500)
        assert "[500]" in str(err)
        assert "test" in str(err)

    def test_base_error_str_without_status(self):
        err = ReinforceSpecError("test")
        assert str(err) == "test"

    def test_base_error_repr(self):
        err = ReinforceSpecError("test", status_code=400)
        assert "ReinforceSpecError" in repr(err)

    def test_validation_error_fields(self):
        err = ValidationError("bad input", field="name", value="")
        assert err.field == "name"
        assert err.value == ""
        assert err.status_code == 400

    def test_rate_limit_error_fields(self):
        err = RateLimitError(retry_after=30.0, limit=100, remaining=0, reset_at=1700000000.0)
        assert err.retry_after == 30.0
        assert err.limit == 100
        assert err.remaining == 0
        assert err.reset_at == 1700000000.0
        assert err.status_code == 429

    def test_not_found_error_fields(self):
        err = NotFoundError(resource_type="policy", resource_id="v001")
        assert err.resource_type == "policy"
        assert err.resource_id == "v001"

    def test_network_error_cause(self):
        cause = ConnectionError("conn refused")
        err = NetworkError(cause=cause)
        assert err.cause is cause

    def test_timeout_error_timeout(self):
        err = TimeoutError(timeout=30.0)
        assert err.timeout == 30.0


class TestExceptionFromResponse:
    """Tests for the exception_from_response factory."""

    @pytest.mark.parametrize(
        "status_code,expected_type",
        [
            (400, ValidationError),
            (401, AuthenticationError),
            (403, AuthorizationError),
            (404, NotFoundError),
            (409, ConflictError),
            (413, PayloadTooLargeError),
            (429, RateLimitError),
            (500, ServerError),
            (502, ServerError),
            (503, ServiceUnavailableError),
            (504, ServerError),
        ],
    )
    def test_maps_status_to_error_type(self, status_code, expected_type):
        err = exception_from_response(status_code, "error msg")
        assert isinstance(err, expected_type)

    def test_unknown_status_returns_base(self):
        err = exception_from_response(418, "I'm a teapot")
        assert type(err) is ReinforceSpecError

    def test_rate_limit_with_details(self):
        details = {"retry_after": 30.0, "limit": 100, "remaining": 0, "reset_at": 1700000000.0}
        err = exception_from_response(429, "rate limited", details)
        assert isinstance(err, RateLimitError)
        assert err.retry_after == 30.0
        assert err.limit == 100

    def test_503_with_retry_after(self):
        err = exception_from_response(503, "unavailable", {"retry_after": 60.0})
        assert isinstance(err, ServiceUnavailableError)
        assert err.retry_after == 60.0
