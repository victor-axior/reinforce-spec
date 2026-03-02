"""Unit tests for exception hierarchy."""

from __future__ import annotations

from reinforce_spec._exceptions import (
    CalibrationError,
    CircuitBreakerOpenError,
    ConfigurationError,
    IdempotencyConflictError,
    InputValidationError,
    InsufficientCandidatesError,
    PolicyError,
    PolicyNotFoundError,
    PolicyTrainingError,
    RateLimitError,
    ReinforceSpecError,
    ReplayBufferError,
    RubricError,
    ScoringError,
    StorageError,
    UpstreamError,
)


class TestExceptionHierarchy:
    """Test exception inheritance and message propagation."""

    def test_all_exceptions_inherit_from_base(self) -> None:
        exceptions = [
            InputValidationError("test"),
            ScoringError("test"),
            ConfigurationError("test"),
            PolicyNotFoundError("test"),
            CircuitBreakerOpenError("test"),
        ]
        for exc in exceptions:
            assert isinstance(exc, ReinforceSpecError)

    def test_exception_messages(self) -> None:
        exc = InputValidationError("Invalid candidate input")
        assert "Invalid candidate" in str(exc)

    def test_exception_details(self) -> None:
        exc = ReinforceSpecError("test", details={"key": "value"})
        assert exc.details == {"key": "value"}

    def test_exception_default_details(self) -> None:
        exc = ReinforceSpecError("test")
        assert exc.details == {}


class TestInsufficientCandidatesError:
    """Test InsufficientCandidatesError custom attributes."""

    def test_default_values(self) -> None:
        exc = InsufficientCandidatesError()
        assert exc.required == 2
        assert exc.received == 0
        assert "2 specification candidates" in str(exc)

    def test_custom_values(self) -> None:
        exc = InsufficientCandidatesError(required=5, received=1)
        assert exc.required == 5
        assert exc.received == 1
        assert exc.details == {"required": 5, "received": 1}

    def test_inherits_from_input_validation(self) -> None:
        exc = InsufficientCandidatesError()
        assert isinstance(exc, InputValidationError)
        assert isinstance(exc, ReinforceSpecError)


class TestScoringExceptions:
    """Test scoring exception subclasses."""

    def test_calibration_error_hierarchy(self) -> None:
        exc = CalibrationError("bad calibration")
        assert isinstance(exc, ScoringError)
        assert isinstance(exc, ReinforceSpecError)
        assert str(exc) == "bad calibration"

    def test_rubric_error_hierarchy(self) -> None:
        exc = RubricError("invalid rubric")
        assert isinstance(exc, ScoringError)
        assert isinstance(exc, ReinforceSpecError)


class TestPolicyExceptions:
    """Test policy exception subclasses."""

    def test_policy_training_error(self) -> None:
        exc = PolicyTrainingError("training failed")
        assert isinstance(exc, PolicyError)
        assert isinstance(exc, ReinforceSpecError)

    def test_replay_buffer_error(self) -> None:
        exc = ReplayBufferError("buffer overflow")
        assert isinstance(exc, PolicyError)
        assert isinstance(exc, ReinforceSpecError)


class TestUpstreamError:
    """Test UpstreamError custom attributes."""

    def test_default_attributes(self) -> None:
        exc = UpstreamError("service unavailable")
        assert exc.provider == "unknown"
        assert exc.status_code is None
        assert exc.retry_after is None

    def test_custom_attributes(self) -> None:
        exc = UpstreamError(
            "rate limited",
            provider="openrouter",
            status_code=429,
            retry_after=30.0,
        )
        assert exc.provider == "openrouter"
        assert exc.status_code == 429
        assert exc.retry_after == 30.0
        assert exc.details["provider"] == "openrouter"
        assert exc.details["status_code"] == 429


class TestCircuitBreakerOpenError:
    """Test CircuitBreakerOpenError custom attributes."""

    def test_default_attributes(self) -> None:
        exc = CircuitBreakerOpenError()
        assert exc.cooldown_remaining == 0.0
        assert exc.provider == "unknown"
        assert "Circuit breaker" in str(exc)

    def test_custom_cooldown(self) -> None:
        exc = CircuitBreakerOpenError(
            cooldown_remaining=42.5, provider="openrouter"
        )
        assert exc.cooldown_remaining == 42.5
        assert exc.provider == "openrouter"


class TestRateLimitError:
    """Test RateLimitError inherits from UpstreamError."""

    def test_hierarchy(self) -> None:
        exc = RateLimitError("too many requests", provider="openrouter")
        assert isinstance(exc, UpstreamError)
        assert isinstance(exc, ReinforceSpecError)


class TestStorageExceptions:
    """Test storage exception subclasses."""

    def test_storage_error(self) -> None:
        exc = StorageError("db write failed")
        assert isinstance(exc, ReinforceSpecError)

    def test_idempotency_conflict(self) -> None:
        exc = IdempotencyConflictError("duplicate key")
        assert isinstance(exc, StorageError)
        assert isinstance(exc, ReinforceSpecError)


class TestConfigurationError:
    """Test ConfigurationError."""

    def test_hierarchy(self) -> None:
        exc = ConfigurationError("missing key")
        assert isinstance(exc, ReinforceSpecError)
        assert str(exc) == "missing key"
