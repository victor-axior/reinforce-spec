# Python SDK

The official Python client for ReinforceSpec provides a full-featured async interface with type hints, automatic retries, and built-in rate limiting.

---

## Installation

=== "pip"

    ```bash
    pip install reinforce-spec-sdk
    ```

=== "uv"

    ```bash
    uv add reinforce-spec-sdk
    ```

=== "poetry"

    ```bash
    poetry add reinforce-spec-sdk
    ```

### Requirements

| Requirement | Minimum Version |
|-------------|-----------------|
| Python | 3.9+ |
| httpx | 0.25+ |
| pydantic | 2.0+ |

---

## Quick Start

```python
import asyncio
from reinforce_spec_sdk import ReinforceSpecClient

async def main():
    async with ReinforceSpecClient(
        base_url="https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com",
        api_key="your-api-key",  # Optional for local development
    ) as client:
        response = await client.select(
            candidates=[
                {"content": "# API Spec A\nOAuth2 authentication..."},
                {"content": "# API Spec B\nBasic auth..."},
            ],
        )
        
        print(f"Selected: Spec {response.selected.index + 1}")
        print(f"Score: {response.selected.composite_score:.2f}")

asyncio.run(main())
```

---

## Client Configuration

### Basic Configuration

```python
from reinforce_spec_sdk import ReinforceSpecClient

# Using environment variables
client = ReinforceSpecClient.from_env()

# Explicit configuration
client = ReinforceSpecClient(
    base_url="https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com",
    api_key="your-api-key",
    timeout=30.0,
)
```

### Advanced Configuration

```python
from reinforce_spec_sdk import ReinforceSpecClient
from reinforce_spec_sdk._http import PoolLimits, TimeoutConfig

client = ReinforceSpecClient(
    # Required
    base_url="https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com",
    
    # Authentication
    api_key="your-api-key",
    
    # Timeout configuration
    timeout=30.0,
    # Or granular timeouts:
    # timeout=TimeoutConfig(connect=5.0, read=30.0, write=30.0, pool=10.0),
    
    # Retry settings
    max_retries=3,
    retry_delay=1.0,
    retry_max_delay=30.0,
    retry_jitter=5.0,
    
    # Connection pool limits
    pool_limits=PoolLimits(max_connections=100, max_keepalive=20),
    
    # Hooks for logging/debugging
    on_request=lambda req: print(f"Request: {req.method} {req.url}"),
    on_response=lambda res: print(f"Response: {res.status_code}"),
)
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `REINFORCE_SPEC_BASE_URL` | API base URL (required for `from_env()`) |
| `REINFORCE_SPEC_API_KEY` | API authentication key |
| `REINFORCE_SPEC_TIMEOUT` | Request timeout in seconds (default: 30) |
| `REINFORCE_SPEC_MAX_RETRIES` | Max retry attempts (default: 3) |

---

## Core Methods

### select()

Evaluate candidates and select the best one using multi-judge scoring.

```python
response = await client.select(
    candidates=[
        {
            "content": "spec A content",
            "spec_type": "api",
            "source_model": "claude-3-opus",
            "metadata": {"version": "2.0"},
        },
        {"content": "spec B content", "spec_type": "api"},
    ],
    description="API for payment processing",
    selection_method="hybrid",
    request_id="unique-request-id",  # Optional idempotency key
)

print(response.request_id)
print(response.selected.index)
print(response.selected.composite_score)
print(response.all_candidates)
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `candidates` | `list[dict]` | Yes | Specs to evaluate (min 2) |
| `description` | `str` | No | Context for scoring (max 2000 chars) |
| `selection_method` | `str` | No | `"scoring_only"`, `"hybrid"`, `"rl_only"` |
| `request_id` | `str` | No | Idempotency key (auto-generated if omitted) |

**Returns:** `SelectionResponse`

---

### submit_feedback()

Submit human feedback for RL training.

```python
feedback_id = await client.submit_feedback(
    request_id="prev-request-id",
    rating=4.5,           # 1.0 to 5.0
    comment="Good result",
    spec_id="selected-spec-id",  # Optional
)

print(f"Feedback submitted: {feedback_id}")
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `request_id` | `str` | Yes | From original `select()` response |
| `rating` | `float` | No | Rating from 1.0 to 5.0 |
| `comment` | `str` | No | Free-form text (max 2000 chars) |
| `spec_id` | `str` | No | ID of spec being rated |

**Returns:** `str` (feedback ID)

---

### get_policy_status()

Get RL policy status and metrics.

```python
status = await client.get_policy_status()

print(f"Version: {status.version}")
print(f"Stage: {status.stage}")
print(f"Episode count: {status.episode_count}")
print(f"Explore rate: {status.explore_rate}")
```

**Returns:** `PolicyStatus`

---

### train_policy()

Trigger policy training iteration.

```python
result = await client.train_policy(n_steps=256)

print(f"Job ID: {result['job_id']}")
print(f"Status: {result['status']}")
```

---

### health() / ready()

Health and readiness checks.

```python
health = await client.health()
print(f"Status: {health.status}")
print(f"Version: {health.version}")

ready = await client.ready()
print(f"Ready: {ready.status == 'healthy'}")
```

---

## Synchronous Methods

All async methods have synchronous equivalents with a `_sync` suffix:

```python
from reinforce_spec_sdk import ReinforceSpecClient

# Sync context manager
with ReinforceSpecClient.sync(
    base_url="https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com",
    api_key="your-api-key",
) as client:
    response = client.select_sync(candidates=[...])
    feedback_id = client.submit_feedback_sync(request_id="...", rating=4.5)
    status = client.get_policy_status_sync()
    result = client.train_policy_sync(n_steps=256)
    health = client.health_sync()
    ready = client.ready_sync()
```

---

## Data Models

### SelectionResponse

```python
from reinforce_spec_sdk.types import SelectionResponse, SelectedCandidate

class SelectionResponse(BaseModel):
    request_id: str
    selected: SelectedCandidate
    all_candidates: list[CandidateSummary]
    selection_method: str
    processing_time_seconds: float

class SelectedCandidate(BaseModel):
    index: int
    content: str
    spec_type: str | None
    format: SpecFormat
    composite_score: float
    dimension_scores: dict[str, float]
```

### PolicyStatus

```python
class PolicyStatus(BaseModel):
    version: str
    stage: PolicyStage  # "cold_start", "shadow", "canary", "production"
    episode_count: int
    explore_rate: float
    last_updated: datetime
```

### DimensionScores

```python
scores = response.selected.dimension_scores

# Access individual dimensions
print(f"Security: {scores['security']:.2f}")
print(f"Scalability: {scores['scalability']:.2f}")

# Find weakest dimension
weakest = min(scores, key=scores.get)
print(f"Needs improvement: {weakest} ({scores[weakest]:.2f})")
```

---

## Error Handling

### Exception Hierarchy

```
ReinforceSpecError (base)
├── ValidationError (400)
├── AuthenticationError (401)
├── AuthorizationError (403)
├── NotFoundError (404)
├── ConflictError (409)
├── PayloadTooLargeError (413)
├── RateLimitError (429)
├── ServerError (500, 502, 504)
├── ServiceUnavailableError (503)
├── NetworkError
└── TimeoutError
```

### Error Properties

```python
from reinforce_spec_sdk.exceptions import (
    ReinforceSpecError,
    RateLimitError,
    ValidationError,
)

try:
    response = await client.select(candidates=[...])
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except ValidationError as e:
    print(f"Validation error: {e.message}")
except ReinforceSpecError as e:
    print(f"Error code: {e.status_code}")
    print(f"Message: {e.message}")
```

### Handling Specific Errors

```python
from reinforce_spec_sdk.exceptions import (
    ValidationError,
    RateLimitError,
    ScoringError,
)

try:
    result = await client.select(candidates=candidates)
except ValidationError as e:
    # Fix request
    print(f"Invalid: {e.details}")
except RateLimitError as e:
    # Wait and retry
    await asyncio.sleep(e.retry_after)
    result = await client.select(candidates=candidates)
except ScoringError as e:
    # LLM issue
    if e.retryable:
        result = await client.select(candidates=candidates)
```

---

## Async Patterns

### Concurrent Evaluations

```python
async def evaluate_batch(candidates_list: list[list]):
    tasks = [
        client.select(candidates=candidates)
        for candidates in candidates_list
    ]
    return await asyncio.gather(*tasks)

results = await evaluate_batch([
    [spec_a1, spec_a2],
    [spec_b1, spec_b2],
    [spec_c1, spec_c2],
])
```

### With Semaphore (Rate Limiting)

```python
semaphore = asyncio.Semaphore(10)  # Max 10 concurrent

async def rate_limited_evaluate(candidates):
    async with semaphore:
        return await client.select(candidates=candidates)

results = await asyncio.gather(*[
    rate_limited_evaluate(c) for c in candidates_list
])
```

### Context Manager

```python
async with ReinforceSpecClient() as client:
    result = await client.select(candidates=candidates)
    # Client properly closed after block
```

---

## Configuration Presets

### Enterprise Preset

```python
client = ReinforceSpecClient(weight_preset="enterprise")

# Equivalent to:
client = ReinforceSpecClient(
    dimension_weights={
        "security": 0.20,
        "compliance": 0.18,
        "reliability": 0.12,
        "risk_mitigation": 0.10,
    }
)
```

### Available Presets

| Preset | Focus Areas |
|--------|-------------|
| `enterprise` | Security, Compliance, Reliability |
| `startup` | Performance, Cost, Scalability |
| `platform` | Scalability, Interoperability |
| `regulated` | Compliance, Documentation, Audit |

---

## Logging

### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("reinforce_spec")
logger.setLevel(logging.DEBUG)

client = ReinforceSpecClient()
# Now logs all requests/responses
```

### Custom Logger

```python
import structlog

client = ReinforceSpecClient(
    logger=structlog.get_logger("reinforce_spec"),
)
```

---

## Testing

### Mock Client

```python
from unittest.mock import AsyncMock
from reinforce_spec_sdk import EvaluationResult, SelectedSpec

@pytest.fixture
def mock_client():
    client = AsyncMock(spec=ReinforceSpecClient)
    client.evaluate.return_value = EvaluationResult(
        request_id="test-123",
        selected=SelectedSpec(
            index=0,
            composite_score=0.85,
            dimension_scores={"security": 0.9},
        ),
        # ...
    )
    return client

async def test_evaluation(mock_client):
    result = await mock_client.select(candidates=[...])
    assert result.selected.index == 0
```

### Integration Testing

```python
@pytest.mark.integration
async def test_real_evaluation():
    client = ReinforceSpecClient()
    
    result = await client.select(
        candidates=[
            {"content": "Test spec A"},
            {"content": "Test spec B"},
        ],
    )
    
    assert result.selected.index in [0, 1]
    assert 0 <= result.selected.composite_score <= 1
```

---

## Complete Example

```python
import asyncio
from reinforce_spec_sdk import ReinforceSpecClient

async def main():
    # Initialize client
    client = ReinforceSpecClient(
        selection_method="hybrid",
        dimension_weights={"security": 0.25},
    )
    
    # Define specifications
    spec_a = """
    # Payment API v2
    
    ## Security
    - OAuth 2.0 with PKCE
    - mTLS for service communication
    - AES-256 encryption at rest
    
    ## Compliance
    - PCI DSS Level 1
    - SOC 2 Type II
    """
    
    spec_b = """
    # Payment API v1
    
    ## Security
    - API key authentication
    - HTTPS only
    """
    
    # Evaluate
    result = await client.select(
        candidates=[
            {"content": spec_a, "spec_type": "api"},
            {"content": spec_b, "spec_type": "api"},
        ],
        description="Payment API for enterprise fintech",
    )
    
    # Print results
    print(f"Selected: Spec {result.selected.index + 1}")
    print(f"Score: {result.selected.composite_score:.3f}")
    print(f"Latency: {result.latency_ms}ms")
    
    print("\nDimension Scores:")
    for dim, score in sorted(
        result.selected.dimension_scores.items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        print(f"  {dim}: {score:.3f}")
    
    # Submit feedback
    await client.submit_feedback(
        request_id=result.request_id,
        selected_index=result.selected.index,
        reward=1.0,
        comment="Excellent security coverage",
    )
    
    print("\n✓ Feedback submitted")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Related

- [API Reference](../api-reference/index.md) — REST API documentation
- [HTTP Examples](http.md) — Direct HTTP usage
- [Error Handling Guide](../guides/error-handling.md) — Error patterns
