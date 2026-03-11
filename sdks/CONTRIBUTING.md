# Contributing to ReinforceSpec SDKs

Thank you for your interest in contributing to the ReinforceSpec SDKs.

## Repository Structure

```
sdks/
├── python/       # Python SDK (PyPI: reinforce-spec-sdk)
├── typescript/   # TypeScript/JavaScript SDK (npm: @reinforce-spec/sdk)
└── go/           # Go SDK (github.com/reinforce-spec/sdk-go)
```

Each SDK is an independent package with its own build system, tests, and release cycle.

## Development Setup

### Python

```bash
cd sdks/python
make dev        # Install with dev dependencies
make test       # Run tests
make lint       # Run linting
make typecheck  # Run mypy
make format     # Auto-format code
```

### TypeScript

```bash
cd sdks/typescript
make install    # Install dependencies
make test       # Run tests
make lint       # Run ESLint
make typecheck  # Run tsc --noEmit
make build      # Build CJS/ESM/types
```

### Go

```bash
cd sdks/go
make test       # Run tests
make test-race  # Run tests with race detector
make lint       # Run golangci-lint
make vet        # Run go vet
make fmt        # Format code
```

## Guidelines

### API Consistency

All three SDKs must expose the same API surface:

| Operation        | Python                | TypeScript            | Go                    |
|------------------|-----------------------|-----------------------|-----------------------|
| Select           | `client.select()`     | `client.select()`     | `client.Select()`     |
| Feedback         | `submit_feedback()`   | `submitFeedback()`    | `SubmitFeedback()`    |
| Policy status    | `get_policy_status()` | `getPolicyStatus()`   | `GetPolicyStatus()`   |
| Train policy     | `train_policy()`      | `trainPolicy()`       | `TrainPolicy()`       |
| Health           | `health()`            | `health()`            | `Health()`            |
| Ready            | `ready()`             | `ready()`             | `Ready()`             |

### Naming Conventions

Follow each language's idioms:

- **Python**: `snake_case` for functions and variables, `PascalCase` for classes
- **TypeScript**: `camelCase` for functions and variables, `PascalCase` for classes/interfaces
- **Go**: `PascalCase` for exported symbols, `camelCase` for unexported

### Error Handling

All SDKs must:

1. Map HTTP status codes to typed errors
2. Include retry logic with exponential backoff
3. Support idempotency keys
4. Provide rate limit information in error objects

### Testing

- Every public method must have tests
- Tests should use mock HTTP servers (not real API calls)
- Test files should be organized by module (not one giant test file)
- Aim for >80% code coverage

### Version Management

All SDKs share a version number. When bumping versions:

1. Update the version constant in each SDK
2. Update CHANGELOG.md in each SDK
3. Tag the release as `sdk-v{version}`

## Pull Request Process

1. Create a feature branch from `main`
2. Make changes and add tests
3. Run all checks: `make lint test typecheck` (per SDK)
4. Update CHANGELOG.md under `## [Unreleased]`
5. Open a PR targeting `main`
6. Ensure CI passes for all three SDKs
