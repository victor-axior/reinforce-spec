# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-01

### Added

- `ReinforceSpecClient` with async/sync support
- `select()` for multi-judge LLM output evaluation and selection
- `submit_feedback()` for reinforcement learning feedback loop
- `get_policy_status()` for RL policy monitoring
- `train_policy()` for triggering policy training
- `health()` and `ready()` health check endpoints
- `TimeoutConfig` for granular timeout control (connect, read, write, pool)
- `PoolLimits` for connection pool configuration
- Request/response hooks for logging and debugging
- Full error hierarchy: `ValidationError`, `AuthenticationError`, `RateLimitError`, etc.
- Automatic retries with exponential backoff and jitter
- Idempotency key support for POST/PUT/PATCH requests
- `MockClient` and factory functions for testing
- Type-safe Pydantic models for all request/response types
- `py.typed` marker for PEP 561 compliance
