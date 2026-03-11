# ReinforceSpec Go SDK

Official Go SDK for the [ReinforceSpec API](https://docs.reinforce-spec.dev) - LLM output evaluation and selection using multi-judge scoring and reinforcement learning.

## Installation

```bash
go get github.com/reinforce-spec/sdk-go
```

## Project Structure

```
├── doc.go                  # Package documentation
├── client.go               # Client struct + API methods
├── option.go               # ClientOption + With* + hooks
├── selector.go             # Selector interface
├── errors.go               # Error types + hierarchy
├── types.go                # Public domain types
├── types_wire.go           # Internal wire format types + converters
├── version.go              # Version constant
├── internal/
│   └── transport/
│       ├── transport.go    # HTTP transport with retry + backoff
│       └── transport_test.go
├── reinforcespectest/      # Test utilities sub-package
│   ├── doc.go              #   Package documentation
│   ├── mock.go             #   MockClient (implements Selector)
│   └── factory.go          #   Factory functions for test data
├── examples/               # Runnable example programs
│   ├── basic/main.go       #   Core selection workflow
│   ├── feedback/main.go    #   Selection + feedback loop
│   └── hooks/main.go       #   Request/response hooks
├── *_test.go               # Tests (client, errors, types, wire, option, example)
├── go.mod
├── Makefile
├── .golangci.yml
├── LICENSE
├── CHANGELOG.md
└── README.md
```

## Quick Start

```go
package main

import (
    "context"
    "fmt"
    "log"

    reinforce "github.com/reinforce-spec/sdk-go"
)

func main() {
    // Create client
    client := reinforce.NewClient(
        reinforce.WithBaseURL("https://api.reinforce-spec.dev"),
        reinforce.WithAPIKey("your-api-key"),
    )

    // Evaluate and select best spec
    response, err := client.Select(context.Background(), &reinforce.SelectRequest{
        Candidates: []reinforce.SpecInput{
            {Content: "First LLM output..."},
            {Content: "Second LLM output..."},
        },
        SelectionMethod: reinforce.SelectionMethodHybrid,
    })
    if err != nil {
        log.Fatal(err)
    }

    fmt.Printf("Selected: %d\n", response.Selected.Index)
    fmt.Printf("Score: %.2f\n", response.Selected.CompositeScore)
    fmt.Printf("Confidence: %.2f\n", response.SelectionConfidence)
}
```

## Configuration

### Environment Variables

```bash
export REINFORCE_SPEC_BASE_URL="https://api.reinforce-spec.dev"
export REINFORCE_SPEC_API_KEY="your-api-key"
```

```go
// Create client from environment
client, err := reinforce.NewClientFromEnv()
if err != nil {
    log.Fatal(err)
}
```

### Client Options

```go
client := reinforce.NewClient(
    reinforce.WithBaseURL("https://api.reinforce-spec.dev"),
    reinforce.WithAPIKey("your-api-key"),
    reinforce.WithTimeout(30 * time.Second),
    reinforce.WithMaxRetries(3),
    reinforce.WithRetryDelay(time.Second),
    reinforce.WithHTTPClient(customHTTPClient),
)
```

## API Reference

### `client.Select()`

Evaluate candidates and select the best one.

```go
response, err := client.Select(ctx, &reinforce.SelectRequest{
    Candidates: []reinforce.SpecInput{
        {Content: "...", SourceModel: "gpt-4", Metadata: map[string]interface{}{}},
        {Content: "...", SourceModel: "claude-3"},
    },
    SelectionMethod: reinforce.SelectionMethodHybrid,
    RequestID:       "unique-id",      // Idempotency key (optional)
    Description:     "API spec...",    // Context for scoring
})
```

**Returns:** `*SelectionResponse, error`

### `client.SubmitFeedback()`

Submit human feedback for reinforcement learning.

```go
feedbackID, err := client.SubmitFeedback(ctx, &reinforce.FeedbackRequest{
    RequestID: "original-request-id",
    Rating:    4.5,                    // 1.0-5.0
    Comment:   "Good structure",
    SpecID:    "selected-spec-id",
})
```

**Returns:** `string, error`

### `client.GetPolicyStatus()`

Get the current RL policy status.

```go
status, err := client.GetPolicyStatus(ctx)
fmt.Printf("Version: %s\n", status.Version)
fmt.Printf("Stage: %s\n", status.Stage)
fmt.Printf("Mean Reward: %.3f\n", status.MeanReward)
```

**Returns:** `*PolicyStatus, error`

### `client.Health()`

Check API health.

```go
health, err := client.Health(ctx)
fmt.Printf("Status: %s\n", health.Status)
```

**Returns:** `*HealthResponse, error`

## Error Handling

```go
import (
    "errors"
    reinforce "github.com/reinforce-spec/sdk-go"
)

response, err := client.Select(ctx, request)
if err != nil {
    var validationErr *reinforce.ValidationError
    var rateLimitErr *reinforce.RateLimitError
    var serverErr *reinforce.ServerError

    switch {
    case errors.As(err, &validationErr):
        fmt.Printf("Invalid input: %s\n", validationErr.Message)
        fmt.Printf("Details: %v\n", validationErr.Details)
    case errors.As(err, &rateLimitErr):
        fmt.Printf("Rate limited. Retry after: %v\n", rateLimitErr.RetryAfter)
    case errors.As(err, &serverErr):
        fmt.Printf("Server error: %d\n", serverErr.StatusCode)
    default:
        fmt.Printf("Error: %v\n", err)
    }
}
```

## Types

All request and response types are fully typed:

```go
import reinforce "github.com/reinforce-spec/sdk-go"

// Enums
reinforce.SelectionMethodHybrid
reinforce.SelectionMethodScoringOnly
reinforce.SelectionMethodRLOnly

reinforce.SpecFormatText
reinforce.SpecFormatJSON
reinforce.SpecFormatYAML

reinforce.PolicyStageProduction
reinforce.PolicyStageCanary

// Request types
reinforce.SpecInput{}
reinforce.SelectRequest{}
reinforce.FeedbackRequest{}

// Response types
reinforce.SelectionResponse{}
reinforce.CandidateSpec{}
reinforce.DimensionScore{}
reinforce.PolicyStatus{}
reinforce.HealthResponse{}
```

## Context Support

All methods accept a `context.Context` for cancellation and timeouts:

```go
// With timeout
ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
defer cancel()

response, err := client.Select(ctx, request)
if errors.Is(err, context.DeadlineExceeded) {
    fmt.Println("Request timed out")
}

// With cancellation
ctx, cancel := context.WithCancel(context.Background())
go func() {
    time.Sleep(5 * time.Second)
    cancel()
}()

response, err := client.Select(ctx, request)
if errors.Is(err, context.Canceled) {
    fmt.Println("Request cancelled")
}
```

## Testing

The `reinforcespectest` sub-package provides a mock client and factory functions:

```go
import (
    "context"
    "testing"

    reinforce "github.com/reinforce-spec/sdk-go"
    "github.com/reinforce-spec/sdk-go/reinforcespectest"
)

// Accept the Selector interface in your code for testability
func evaluate(ctx context.Context, sel reinforce.Selector) error {
    resp, err := sel.Select(ctx, &reinforce.SelectRequest{...})
    // ...
}

func TestEvaluate(t *testing.T) {
    // Create mock with canned response
    mock := reinforcespectest.NewMockClient(
        reinforcespectest.WithSelectResponse(&reinforce.SelectionResponse{
            RequestID: "test-123",
            Selected:  reinforcespectest.NewCandidateSpec(),
        }),
    )

    err := evaluate(context.Background(), mock)
    if err != nil {
        t.Fatal(err)
    }

    // Assert the mock was called
    if len(mock.SelectCalls) != 1 {
        t.Errorf("expected 1 call, got %d", len(mock.SelectCalls))
    }
}
```

Factory functions create valid test data with sensible defaults:

```go
spec := reinforcespectest.NewCandidateSpec()
resp := reinforcespectest.NewSelectionResponse()
req := reinforcespectest.NewSelectRequest()
status := reinforcespectest.NewPolicyStatus()
```

## Development

```bash
make test           # Run all tests
make test-race      # Run with race detector
make test-cov       # Coverage report
make lint           # golangci-lint
make vet            # go vet
make fmt            # gofmt
make build-examples # Verify examples compile
```

## License

MIT License - see [LICENSE](LICENSE) for details.
