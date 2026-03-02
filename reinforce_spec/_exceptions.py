"""Exception hierarchy for reinforce-spec.

All exceptions inherit from ReinforceSpecError so callers can catch broadly
or narrowly as needed.
"""

from __future__ import annotations


class ReinforceSpecError(Exception):
    """Base exception for all reinforce-spec errors."""

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


# ── Input Validation Errors ───────────────────────────────────────────────────


class InputValidationError(ReinforceSpecError):
    """Raised when user-provided input (specs, parameters) is invalid."""


class InsufficientCandidatesError(InputValidationError):
    """Raised when fewer than the minimum required candidates are provided."""

    def __init__(
        self,
        message: str = "At least 2 specification candidates are required",
        *,
        required: int = 2,
        received: int = 0,
    ) -> None:
        super().__init__(message, details={"required": required, "received": received})
        self.required = required
        self.received = received


# ── Scoring Errors ────────────────────────────────────────────────────────────


class ScoringError(ReinforceSpecError):
    """Raised when spec scoring fails."""


class CalibrationError(ScoringError):
    """Raised when score calibration fails or calibration data is invalid."""


class RubricError(ScoringError):
    """Raised when the rubric definition is invalid or incomplete."""


# ── Policy / RL Errors ────────────────────────────────────────────────────────


class PolicyError(ReinforceSpecError):
    """Raised when RL policy operations fail."""


class PolicyNotFoundError(PolicyError):
    """Raised when a requested policy version does not exist."""


class PolicyTrainingError(PolicyError):
    """Raised when policy training fails."""


class ReplayBufferError(PolicyError):
    """Raised when replay buffer operations fail."""


# ── Upstream / External Service Errors ────────────────────────────────────────


class UpstreamError(ReinforceSpecError):
    """Raised when an upstream service (OpenRouter, etc.) fails."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "unknown",
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(
            message,
            details={
                "provider": provider,
                "status_code": status_code,
                "retry_after": retry_after,
            },
        )
        self.provider = provider
        self.status_code = status_code
        self.retry_after = retry_after


class CircuitBreakerOpenError(UpstreamError):
    """Raised when the circuit breaker is open and requests are rejected."""

    def __init__(
        self,
        message: str = "Circuit breaker is open",
        *,
        provider: str = "unknown",
        cooldown_remaining: float = 0.0,
    ) -> None:
        super().__init__(message, provider=provider)
        self.cooldown_remaining = cooldown_remaining


class RateLimitError(UpstreamError):
    """Raised when rate-limited by the upstream provider."""


# ── Configuration Errors ──────────────────────────────────────────────────────


class ConfigurationError(ReinforceSpecError):
    """Raised when configuration is invalid or missing.

    Follows the 'day-zero safe by default' principle: if a configuration
    is missing or ambiguous, the system fails closed, not open.
    """


# ── Storage Errors ────────────────────────────────────────────────────────────


class StorageError(ReinforceSpecError):
    """Raised when persistence / storage operations fail."""


class IdempotencyConflictError(StorageError):
    """Raised when an idempotency key is reused with a different request body."""
