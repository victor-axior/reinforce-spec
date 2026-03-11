# HTTP API Examples

Examples for using the ReinforceSpec API directly with various HTTP clients.

---

## Base Configuration

### API Details

| Setting | Value |
|---------|-------|
| Base URL | `https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com` |
| Version | `/v1` |
| Content-Type | `application/json` |
| Auth | `Authorization: Bearer <key>` (optional for local dev) |

### Environment Setup

=== "Bash"

    ```bash
    export RS_API_KEY="your-api-key"
    export RS_BASE_URL="https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com"
    ```

=== "PowerShell"

    ```powershell
    $env:RS_API_KEY = "your-api-key"
    $env:RS_BASE_URL = "https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com"
    ```

---

## curl Examples

### Evaluate Specifications

```bash
curl -X POST "${RS_BASE_URL}/v1/specs" \
  -H "Authorization: Bearer ${RS_API_KEY}" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "candidates": [
      {
        "content": "# API Spec A\nOAuth2 with mTLS",
        "spec_type": "api"
      },
      {
        "content": "# API Spec B\nBasic auth",
        "spec_type": "api"
      }
    ],
    "description": "Payment API comparison"
  }'
```

### Submit Feedback

```bash
curl -X POST "${RS_BASE_URL}/v1/specs/feedback" \
  -H "Authorization: Bearer ${RS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "req_01HQXYZ123ABC",
    "selected_index": 0,
    "reward": 1.0,
    "comment": "Great selection"
  }'
```

### Check Policy Status

```bash
curl -X GET "${RS_BASE_URL}/v1/policy/status" \
  -H "Authorization: Bearer ${RS_API_KEY}"
```

### Health Check

```bash
curl -s "${RS_BASE_URL}/v1/health/ready" | jq .
```

---

## Python httpx

### Async Client

```python
import httpx
import os
import uuid

API_KEY = os.environ["RS_API_KEY"]
BASE_URL = os.environ.get("RS_BASE_URL", "https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com")

async def evaluate(candidates: list[dict]) -> dict:
    """Evaluate specifications."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/v1/specs",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "Idempotency-Key": str(uuid.uuid4()),
            },
            json={"candidates": candidates},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()

async def submit_feedback(
    request_id: str,
    selected_index: int,
    reward: float,
) -> dict:
    """Submit feedback on selection."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/v1/specs/feedback",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "request_id": request_id,
                "selected_index": selected_index,
                "reward": reward,
            },
        )
        response.raise_for_status()
        return response.json()

# Usage
import asyncio

async def main():
    result = await evaluate([
        {"content": "Spec A content"},
        {"content": "Spec B content"},
    ])
    
    print(f"Selected: {result['selected']['index']}")
    
    await submit_feedback(
        request_id=result["request_id"],
        selected_index=result["selected"]["index"],
        reward=1.0,
    )

asyncio.run(main())
```

### With Retry Logic

```python
import httpx
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
)
async def evaluate_with_retry(candidates: list[dict]) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/v1/specs",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"candidates": candidates},
            timeout=30.0,
        )
        
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            await asyncio.sleep(retry_after)
            raise httpx.HTTPStatusError(
                "Rate limited",
                request=response.request,
                response=response,
            )
        
        response.raise_for_status()
        return response.json()
```

---

## Python requests (Sync)

```python
import requests
import os
import uuid

API_KEY = os.environ["RS_API_KEY"]
BASE_URL = os.environ.get("RS_BASE_URL", "https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com")

def evaluate(candidates: list[dict]) -> dict:
    """Evaluate specifications (synchronous)."""
    response = requests.post(
        f"{BASE_URL}/v1/specs",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json={"candidates": candidates},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()

# Usage
result = evaluate([
    {"content": "Spec A"},
    {"content": "Spec B"},
])
print(f"Selected: {result['selected']['index']}")
```

---

## JavaScript / Node.js

### Using fetch

```javascript
const API_KEY = process.env.RS_API_KEY;
const BASE_URL = process.env.RS_BASE_URL || 'https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com';

async function evaluate(candidates) {
  const response = await fetch(`${BASE_URL}/v1/specs`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${API_KEY}`,
      'Content-Type': 'application/json',
      'Idempotency-Key': crypto.randomUUID(),
    },
    body: JSON.stringify({ candidates }),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(`${error.error}: ${error.message}`);
  }
  
  return response.json();
}

async function submitFeedback(requestId, selectedIndex, reward) {
  const response = await fetch(`${BASE_URL}/v1/specs/feedback`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      request_id: requestId,
      selected_index: selectedIndex,
      reward,
    }),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(`${error.error}: ${error.message}`);
  }
  
  return response.json();
}

// Usage
const result = await evaluate([
  { content: '# Spec A\nOAuth2...' },
  { content: '# Spec B\nBasic auth...' },
]);

console.log(`Selected: Spec ${result.selected.index + 1}`);
console.log(`Score: ${result.selected.composite_score}`);

await submitFeedback(
  result.request_id,
  result.selected.index,
  1.0
);
```

### Using axios

```javascript
const axios = require('axios');

const client = axios.create({
  baseURL: process.env.RS_BASE_URL || 'https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com',
  headers: {
    'Authorization': `Bearer ${process.env.RS_API_KEY}`,
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

async function evaluate(candidates) {
  const response = await client.post('/v1/specs', {
    candidates,
  }, {
    headers: {
      'Idempotency-Key': crypto.randomUUID(),
    },
  });
  
  return response.data;
}
```

---

## Go

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
    "os"
    "time"
)

type Candidate struct {
    Content  string `json:"content"`
    SpecType string `json:"spec_type,omitempty"`
}

type EvaluateRequest struct {
    Candidates []Candidate `json:"candidates"`
}

type SelectedSpec struct {
    Index          int                `json:"index"`
    CompositeScore float64            `json:"composite_score"`
    DimensionScores map[string]float64 `json:"dimension_scores"`
}

type EvaluateResponse struct {
    RequestID string       `json:"request_id"`
    Selected  SelectedSpec `json:"selected"`
}

func Evaluate(candidates []Candidate) (*EvaluateResponse, error) {
    apiKey := os.Getenv("RS_API_KEY")
    baseURL := os.Getenv("RS_BASE_URL")
    if baseURL == "" {
        baseURL = "https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com"
    }
    
    reqBody, _ := json.Marshal(EvaluateRequest{Candidates: candidates})
    
    req, _ := http.NewRequest("POST", baseURL+"/v1/specs", bytes.NewBuffer(reqBody))
    req.Header.Set("Authorization", "Bearer "+apiKey)
    req.Header.Set("Content-Type", "application/json")
    
    client := &http.Client{Timeout: 30 * time.Second}
    resp, err := client.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    
    var result EvaluateResponse
    json.NewDecoder(resp.Body).Decode(&result)
    
    return &result, nil
}

func main() {
    result, err := Evaluate([]Candidate{
        {Content: "# Spec A\nOAuth2..."},
        {Content: "# Spec B\nBasic auth..."},
    })
    
    if err != nil {
        panic(err)
    }
    
    fmt.Printf("Selected: Spec %d\n", result.Selected.Index+1)
    fmt.Printf("Score: %.3f\n", result.Selected.CompositeScore)
}
```

---

## Response Handling

### Success Response

```json
{
  "request_id": "req_01HQXYZ123ABC",
  "selected": {
    "index": 0,
    "composite_score": 0.847,
    "dimension_scores": {
      "security": 0.95,
      "compliance": 0.92,
      "scalability": 0.78
    }
  },
  "latency_ms": 2847
}
```

### Error Response

```json
{
  "error": "validation_failed",
  "message": "At least 2 candidates are required",
  "details": {
    "field": "candidates",
    "constraint": "minItems"
  },
  "request_id": "req_01HQXYZ999ZZZ"
}
```

### Error Handling Pattern

```python
async def handle_response(response: httpx.Response):
    if response.status_code == 200:
        return response.json()
    
    error = response.json()
    
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 60))
        raise RateLimitError(
            error["message"],
            retry_after=retry_after,
        )
    
    if response.status_code == 422:
        raise ValidationError(
            error["message"],
            details=error.get("details"),
        )
    
    raise APIError(
        code=error["error"],
        message=error["message"],
        request_id=error.get("request_id"),
    )
```

---

## Rate Limit Handling

### Response Headers

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640995200
Retry-After: 60
```

### Handling in Code

```python
async def evaluate_with_rate_limit(candidates):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/v1/specs",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"candidates": candidates},
        )
        
        # Log rate limit status
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining and int(remaining) < 10:
            logger.warning(f"Rate limit low: {remaining} remaining")
        
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning(f"Rate limited, waiting {retry_after}s")
            await asyncio.sleep(retry_after)
            return await evaluate_with_rate_limit(candidates)
        
        response.raise_for_status()
        return response.json()
```

---

## OpenAPI Client Generation

Generate type-safe clients from the OpenAPI spec:

```bash
# Download spec
curl -o openapi.yml https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/openapi.yaml

# Generate Python client
openapi-generator generate -i openapi.yml -g python -o ./client

# Generate TypeScript client
openapi-generator generate -i openapi.yml -g typescript-fetch -o ./client
```

---

## Related

- [Python SDK](python.md) — Higher-level Python client
- [API Reference](../api-reference/index.md) — Complete API documentation
- [Error Codes](../api-reference/errors.md) — Error reference
