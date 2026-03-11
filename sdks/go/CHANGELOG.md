# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-01

### Added

- `Client` with functional options pattern (`NewClient`, `NewClientFromEnv`)
- `Select()` for multi-judge LLM output evaluation and selection
- `SubmitFeedback()` for reinforcement learning feedback loop
- `GetPolicyStatus()` for RL policy monitoring
- `TrainPolicy()` for triggering policy training
- `Health()` and `Ready()` health check endpoints
- `Close()` for resource cleanup
- Request/response hooks (`WithOnRequest`, `WithOnResponse`)
- Full error hierarchy with sentinel errors and typed errors
- Automatic retries with exponential backoff and jitter
- Idempotency key support for POST/PUT/PATCH requests
- Context-based cancellation and timeout
- Custom `http.Client` support via `WithHTTPClient`
