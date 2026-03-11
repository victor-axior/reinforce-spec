# SDKs & Libraries

Official clients for ReinforceSpec in Python, TypeScript, and Go.

---

## Official SDKs

<div class="grid cards" markdown>

-   :material-language-python: **[Python SDK](python.md)**
    
    Full-featured async client for Python 3.9+
    
    ```bash
    pip install reinforce-spec-sdk
    ```

-   :material-language-typescript: **[TypeScript SDK](typescript.md)**
    
    Type-safe client for Node.js & browsers
    
    ```bash
    npm install @reinforce-spec/sdk
    ```

-   :material-language-go: **[Go SDK](go.md)**
    
    Idiomatic Go client with context support
    
    ```bash
    go get github.com/reinforce-spec/reinforce-spec/sdks/go
    ```

-   :material-api: **[HTTP / REST](http.md)**
    
    Direct API access with any HTTP client
    
    curl, httpx, requests, fetch

</div>

---

## Quick Comparison

| Feature | Python | TypeScript | Go | HTTP |
|---------|--------|------------|-----|------|
| Async support | ✅ Native | ✅ Promise | ✅ Context | ✅ Manual |
| Type safety | ✅ Full | ✅ Full | ✅ Structs | ❌ N/A |
| Auto-retry | ✅ Built-in | ✅ Built-in | ✅ Built-in | ❌ Manual |
| Rate limiting | ✅ Automatic | ✅ Automatic | ✅ Automatic | ❌ Manual |
| Auth handling | ✅ Automatic | ✅ Automatic | ✅ Automatic | ❌ Manual |
| Sync methods | ✅ `_sync()` | ❌ | ❌ | ✅ |

---

## Python Example

```python
from reinforce_spec_sdk import ReinforceSpecClient

async with ReinforceSpecClient.from_env() as client:
    response = await client.select(
        candidates=[
            {"content": "# API Spec A\n..."},
            {"content": "# API Spec B\n..."},
        ],
        description="Payment API comparison",
    )
    
    print(f"Selected: {response.selected.index}")
    print(f"Score: {response.selected.composite_score:.2f}")
    
    # Submit feedback
    await client.submit_feedback(
        request_id=response.request_id,
        rating=4.5,
    )
```

[Full Python SDK Documentation →](python.md)

---

## TypeScript Example

```typescript
import { ReinforceSpecClient } from '@reinforce-spec/sdk';

const client = new ReinforceSpecClient({
  baseUrl: process.env.REINFORCE_SPEC_BASE_URL!,
  apiKey: process.env.REINFORCE_SPEC_API_KEY,
});

const response = await client.select({
  candidates: [
    { content: '# API Spec A\n...' },
    { content: '# API Spec B\n...' },
  ],
  description: 'Payment API comparison',
});

console.log(`Selected: ${response.selected.index}`);
console.log(`Score: ${response.selected.compositeScore.toFixed(2)}`);
```

[Full TypeScript SDK Documentation →](typescript.md)

---

## Go Example

```go
package main

import (
    "context"
    "fmt"
    "log"
    
    reinforce "github.com/reinforce-spec/reinforce-spec/sdks/go"
)

func main() {
    client := reinforce.NewClient(
        reinforce.WithBaseURL(os.Getenv("REINFORCE_SPEC_BASE_URL")),
        reinforce.WithAPIKey(os.Getenv("REINFORCE_SPEC_API_KEY")),
    )
    
    resp, err := client.Select(context.Background(), &reinforce.SelectRequest{
        Candidates: []reinforce.Candidate{
            {Content: "# API Spec A\n..."},
            {Content: "# API Spec B\n..."},
        },
        Description: "Payment API comparison",
    })
    if err != nil {
        log.Fatal(err)
    }
    
    fmt.Printf("Selected: %d\n", resp.Selected.Index)
    fmt.Printf("Score: %.2f\n", resp.Selected.CompositeScore)
}
```

[Full Go SDK Documentation →](go.md)

---

## HTTP API Example

=== "curl"

    ```bash
    curl -X POST https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/v1/specs \
      -H "Authorization: Bearer $REINFORCE_SPEC_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "candidates": [
          {"content": "# Spec A"},
          {"content": "# Spec B"}
        ]
      }'
    ```

=== "Python httpx"

    ```python
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/v1/specs",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"candidates": [...]},
        )
        result = response.json()
    ```

=== "JavaScript fetch"

    ```javascript
    const response = await fetch('https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/v1/specs', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        candidates: [
          { content: '# Spec A' },
          { content: '# Spec B' },
        ],
      }),
    });
    
    const result = await response.json();
    ```

[Full HTTP Examples →](http.md)

---

## Installation Requirements

### Python SDK

| Requirement | Version |
|-------------|---------|
| Python | 3.10+ |
| httpx | 0.24+ |
| pydantic | 2.0+ |

### HTTP API

Any HTTP client supporting:

- POST requests
- JSON body
- Custom headers
- TLS 1.2+

---

## Community Libraries

!!! note "Coming Soon"
    Community libraries for other languages are in development. Join our [Discord](https://discord.gg/reinforce-spec) to contribute.

| Language | Status | Maintainer |
|----------|--------|------------|
| Node.js / TypeScript | Planned | — |
| Go | Planned | — |
| Rust | Planned | — |
| Java | Planned | — |

---

## Contributing

Want to build an SDK for your language?

1. Review the [OpenAPI spec](https://github.com/reinforce-spec/reinforce-spec/blob/main/openapi.yml)
2. Check our [SDK guidelines](https://github.com/reinforce-spec/reinforce-spec/blob/main/CONTRIBUTING.md)
3. Open an issue to discuss

We'll help with:
- API design review
- Testing infrastructure
- Documentation hosting
- Promotion
