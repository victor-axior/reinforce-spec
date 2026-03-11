# Go SDK

The official Go client for ReinforceSpec with idiomatic error handling, context support, and configurable options.

---

## Installation

```bash
go get github.com/reinforce-spec/reinforce-spec/sdks/go
```

### Requirements

| Requirement | Minimum Version |
|-------------|-----------------|
| Go | 1.21+ |

---

## Quick Start

```go
package main

import (
    "context"
    "fmt"
    "log"

    reinforcespec "github.com/reinforce-spec/reinforce-spec/sdks/go"
)

func main() {
    ctx := context.Background()

    // Create client from environment
    client, err := reinforcespec.NewClientFromEnv()
    if err != nil {
        log.Fatal(err)
    }
    defer client.Close()

    // Select best spec
    resp, err := client.Select(ctx, &reinforcespec.SelectRequest{
        Candidates: []reinforcespec.CandidateInput{
            {Content: "# API Spec A\nOAuth2 authentication..."},
            {Content: "# API Spec B\nBasic auth..."},
        },
    })
    if err != nil {
        log.Fatal(err)
    }

    fmt.Printf("Selected: Spec %d\n", resp.Selected.Index+1)
    fmt.Printf("Score: %.2f\n", resp.Selected.CompositeScore)
}
```

---

## Client Configuration

### Using Options

```go
import reinforcespec "github.com/reinforce-spec/reinforce-spec/sdks/go"

client := reinforcespec.NewClient(
    reinforcespec.WithBaseURL("https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com"),
    reinforcespec.WithAPIKey("your-api-key"),
    reinforcespec.WithTimeout(30 * time.Second),
    reinforcespec.WithMaxRetries(3),
)
defer client.Close()
```

### Available Options

| Option | Description |
|--------|-------------|
| `WithBaseURL(url)` | API base URL (required) |
| `WithAPIKey(key)` | API authentication key |
| `WithTimeout(d)` | Request timeout duration |
| `WithMaxRetries(n)` | Max retry attempts |
| `WithHTTPClient(c)` | Custom `*http.Client` |
| `WithRequestHook(fn)` | Hook called before each request |
| `WithResponseHook(fn)` | Hook called after each response |

### Environment Variables

Create client from environment variables:

```go
client, err := reinforcespec.NewClientFromEnv()
if err != nil {
    log.Fatal(err)
}
```

Required environment variables:

| Variable | Description |
|----------|-------------|
| `REINFORCE_SPEC_BASE_URL` | API base URL (required) |
| `REINFORCE_SPEC_API_KEY` | API authentication key |

---

## Core Methods

### Select

Evaluate and select the best specification from candidates.

```go
resp, err := client.Select(ctx, &reinforcespec.SelectRequest{
    Candidates: []reinforcespec.CandidateInput{
        {
            Content:     "spec A content",
            SpecType:    "api",
            SourceModel: "claude-3-opus",
            Metadata:    map[string]any{"version": "2.0"},
        },
        {Content: "spec B content", SpecType: "api"},
    },
    Description:     "API for payment processing",
    SelectionMethod: "hybrid", // "scoring_only", "hybrid", "rl_only"
    RequestID:       "unique-request-id", // Optional idempotency key
})
if err != nil {
    log.Fatal(err)
}

fmt.Println(resp.RequestID)
fmt.Println(resp.Selected.Index)
fmt.Println(resp.Selected.CompositeScore)
```

### SubmitFeedback

Submit human feedback for RL training.

```go
feedbackID, err := client.SubmitFeedback(ctx, &reinforcespec.FeedbackRequest{
    RequestID: "prev-request-id",
    Rating:    4.5, // 1.0 to 5.0
    Comment:   "Good result",
    SpecID:    "", // Optional
})
if err != nil {
    log.Fatal(err)
}

fmt.Printf("Feedback submitted: %s\n", feedbackID)
```

### GetPolicyStatus

Get RL policy status and metrics.

```go
status, err := client.GetPolicyStatus(ctx)
if err != nil {
    log.Fatal(err)
}

fmt.Printf("Version: %s\n", status.Version)
fmt.Printf("Stage: %s\n", status.Stage)
fmt.Printf("Episodes: %d\n", status.EpisodeCount)
fmt.Printf("Explore Rate: %.4f\n", status.ExploreRate)
```

### TrainPolicy

Trigger policy training iteration.

```go
nSteps := 256
resp, err := client.TrainPolicy(ctx, &nSteps)
if err != nil {
    log.Fatal(err)
}

fmt.Printf("Job ID: %s\n", resp.JobID)
fmt.Printf("Status: %s\n", resp.Status)
```

### Health / Ready

Health and readiness checks.

```go
health, err := client.Health(ctx)
if err != nil {
    log.Fatal(err)
}
fmt.Printf("Status: %s\n", health.Status)
fmt.Printf("Version: %s\n", health.Version)

ready, err := client.Ready(ctx)
if err != nil {
    log.Fatal(err)
}
fmt.Printf("Ready: %v\n", ready.Status == "healthy")
```

---

## Types

### SelectRequest

```go
type SelectRequest struct {
    Candidates      []CandidateInput `json:"candidates"`
    Description     string           `json:"description,omitempty"`
    SelectionMethod string           `json:"selection_method,omitempty"`
    RequestID       string           `json:"request_id,omitempty"`
}

type CandidateInput struct {
    Content     string         `json:"content"`
    SpecType    string         `json:"spec_type,omitempty"`
    SourceModel string         `json:"source_model,omitempty"`
    Metadata    map[string]any `json:"metadata,omitempty"`
}
```

### SelectionResponse

```go
type SelectionResponse struct {
    RequestID       string             `json:"request_id"`
    Selected        SelectedCandidate  `json:"selected"`
    AllCandidates   []CandidateSummary `json:"all_candidates"`
    SelectionMethod string             `json:"selection_method"`
    ProcessingTime  float64            `json:"processing_time_seconds"`
}

type SelectedCandidate struct {
    Index           int                `json:"index"`
    Content         string             `json:"content"`
    SpecType        string             `json:"spec_type,omitempty"`
    Format          string             `json:"format"`
    CompositeScore  float64            `json:"composite_score"`
    DimensionScores map[string]float64 `json:"dimension_scores"`
}
```

---

## Error Handling

```go
import (
    "errors"
    reinforcespec "github.com/reinforce-spec/reinforce-spec/sdks/go"
)

resp, err := client.Select(ctx, req)
if err != nil {
    var rateLimitErr *reinforcespec.RateLimitError
    var validationErr *reinforcespec.ValidationError
    var authErr *reinforcespec.AuthenticationError
    var apiErr *reinforcespec.APIError

    switch {
    case errors.As(err, &rateLimitErr):
        fmt.Printf("Rate limited. Retry after %ds\n", rateLimitErr.RetryAfter)
    case errors.As(err, &validationErr):
        fmt.Printf("Validation error: %s\n", validationErr.Message)
    case errors.As(err, &authErr):
        fmt.Println("Invalid API key")
    case errors.As(err, &apiErr):
        fmt.Printf("API error (%d): %s\n", apiErr.StatusCode, apiErr.Message)
    default:
        fmt.Printf("Unknown error: %v\n", err)
    }
}
```

### Error Types

| Type | Description |
|------|-------------|
| `APIError` | Base API error with status code and message |
| `ValidationError` | Request validation failed (400) |
| `AuthenticationError` | Invalid or missing API key (401) |
| `AuthorizationError` | Insufficient permissions (403) |
| `NotFoundError` | Resource not found (404) |
| `RateLimitError` | Rate limit exceeded (429) |
| `ServerError` | Server-side error (5xx) |

---

## Context and Cancellation

All methods accept a `context.Context` for cancellation and timeouts:

```go
// With timeout
ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
defer cancel()

resp, err := client.Select(ctx, req)
if err != nil {
    if errors.Is(err, context.DeadlineExceeded) {
        fmt.Println("Request timed out")
    }
}

// With cancellation
ctx, cancel := context.WithCancel(context.Background())

go func() {
    time.Sleep(5 * time.Second)
    cancel() // Cancel after 5s
}()

resp, err := client.Select(ctx, req)
```

---

## Custom HTTP Client

```go
httpClient := &http.Client{
    Timeout: 60 * time.Second,
    Transport: &http.Transport{
        MaxIdleConns:        100,
        MaxIdleConnsPerHost: 10,
        IdleConnTimeout:     90 * time.Second,
    },
}

client := reinforcespec.NewClient(
    reinforcespec.WithBaseURL("https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com"),
    reinforcespec.WithHTTPClient(httpClient),
)
```

---

## See Also

- [Python SDK](python.md)
- [TypeScript SDK](typescript.md)
- [HTTP/REST API](http.md)
