# Changelog

All notable changes to ReinforceSpec.

---

## [1.3.0] - 2025-01-15

### Added

- **TypeScript SDK** — Full-featured TypeScript/JavaScript client with type safety
  - Promise-based async API
  - Browser and Node.js support
  - Configurable timeouts and retries
- **Go SDK** — Idiomatic Go client with context support
  - Functional options pattern for configuration
  - Built-in error types with `errors.Is`/`errors.As`
  - Context cancellation and deadline support
- **GitHub Actions workflows** for automated CI/CD
  - `ci.yml` — Lint, type-check, and test on each push
  - `sdk-tests.yml` — SDK integration tests
  - `sdk-publish.yml` — Publish SDKs to package registries
  - `deploy-api.yml` — Deploy API to ECS Fargate
  - `nightly.yml` — Nightly regression tests
- **AWS CodeArtifact** support for private SDK distribution
- **OIDC authentication** for GitHub Actions deployments (no long-lived secrets)

### Changed

- Python SDK package renamed from `reinforce-spec` to `reinforce-spec-sdk`
- Python SDK minimum version lowered from 3.11 to 3.9
- Python SDK method renamed from `evaluate()` to `select()` for consistency
- Environment variables standardized to `REINFORCE_SPEC_*` prefix
- Documentation updated with all three SDK examples

### Fixed

- Fixed 48 ruff lint warnings with `--unsafe-fixes`
- Fixed 11 mypy type errors across multiple files
- Fixed httpx_mock fixture import in Python SDK tests
- Fixed TypeScript ts-node dependency for test execution

---

## [1.2.0] - 2024-01-15

### Added

- Multi-judge LLM ensemble scoring with configurable weights
- Support for GPT-4o, Gemini 1.5 Pro alongside Claude 3.5 Sonnet
- Idempotency key support for safe request retries
- Rate limiting with configurable tiers
- Security headers middleware (HSTS, CSP, X-Content-Type-Options)
- Circuit breaker for LLM provider failures
- Prometheus metrics endpoint at `/metrics`

### Changed

- Default selection method changed from `scoring_only` to `hybrid`
- Improved scoring calibration based on expanded reference set
- Reduced default timeout from 60s to 30s
- Enhanced error messages with more actionable details

### Fixed

- Memory leak in rate limiter middleware
- Race condition in replay buffer during concurrent training
- PostgreSQL connection pool exhaustion under load

### Security

- Added dependency auditing with pip-audit in CI
- Tightened mypy configuration for stricter type checking
- Implemented request signing for webhooks

---

## [1.1.0] - 2024-01-01

### Added

- Reinforcement learning selection method (`rl_only`)
- Hybrid selection combining scoring with RL policy
- Feedback API for model improvement
- Policy status and training endpoints
- Docker Compose configuration with PostgreSQL
- AWS ECS Fargate deployment support

### Changed

- Migrated from SQLite to PostgreSQL for production
- Improved async performance with connection pooling
- Enhanced dimension scoring with 12 enterprise criteria

### Fixed

- Scoring consistency across different spec lengths
- API key validation edge cases
- Health check timeout issues

---

## [1.0.0] - 2023-12-15

### Added

- Initial release
- Multi-judge LLM scoring with Claude 3 Sonnet
- REST API with OpenAPI 3.1 specification
- Python SDK with async support
- 12 enterprise scoring dimensions
- SQLite persistence for development
- Docker container support
- Comprehensive API documentation

---

## Version Policy

ReinforceSpec follows [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking API changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

### API Versioning

The API version is included in the URL path (`/v1/`). Breaking changes will create a new API version while maintaining the previous version for a deprecation period.

| Version | Status | Deprecation |
|---------|--------|-------------|
| v1 | Current | — |

---

## Upgrade Guides

### 1.1.x → 1.2.0

**Breaking Changes:** None

**Recommended Changes:**

1. Update dimension weights if using custom configuration
2. Enable idempotency keys for production requests
3. Monitor new metrics endpoint

```python
# Before
client = ReinforceSpecClient()

# After (recommended)
client = ReinforceSpecClient(
    selection_method="hybrid",  # Now default
)
```

### 1.0.x → 1.1.0

**Breaking Changes:**

- SQLite is no longer recommended for production
- Default database changed to PostgreSQL

**Migration:**

1. Set up PostgreSQL database
2. Run migration script:
   ```bash
   python scripts/migrate_sqlite_to_postgres.py
   ```
3. Update `DATABASE_URL` environment variable

---

## Subscribing to Updates

- **GitHub Releases**: Watch the [repository](https://github.com/reinforce-spec/reinforce-spec)
- **Changelog RSS**: [/changelog.xml](/changelog.xml)
- **Email**: Subscribe at [updates.reinforce-spec.dev](https://updates.reinforce-spec.dev)
