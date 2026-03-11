# ReinforceSpec Python SDK

Official Python SDK for the [ReinforceSpec API](https://docs.reinforce-spec.dev) - LLM output evaluation and selection using multi-judge scoring and reinforcement learning.

## Installation

### From AWS CodeArtifact (Private)

```bash
# Login to CodeArtifact
aws codeartifact login --tool pip --domain reinforce-spec --repository python-packages

# Install
pip install reinforce-spec-sdk
```

### From Source

```bash
git clone https://github.com/reinforce-spec/sdk-python.git
cd sdk-python
pip install -e .
```

## Quick Start

```python
import asyncio
from reinforce_spec_sdk import ReinforceSpecClient

async def main():
    # Initialize client
    async with ReinforceSpecClient(
        base_url="https://api.reinforce-spec.dev",
        api_key="your-api-key"
    ) as client:
        # Evaluate and select best spec
        response = await client.select(
            candidates=[
                {"content": "First LLM output..."},
                {"content": "Second LLM output..."},
            ],
            selection_method="hybrid"
        )
        
        print(f"Selected: {response.selected.index}")
        print(f"Score: {response.selected.composite_score}")
        print(f"Confidence: {response.selection_confidence}")

asyncio.run(main())
```

## Synchronous Usage

```python
from reinforce_spec_sdk import ReinforceSpecClient

# Sync context manager
with ReinforceSpecClient.sync(
    base_url="https://api.reinforce-spec.dev",
    api_key="your-api-key"
) as client:
    response = client.select_sync(
        candidates=[
            {"content": "First output"},
            {"content": "Second output"},
        ]
    )
```

## Configuration

### Environment Variables

```bash
export REINFORCE_SPEC_BASE_URL="https://api.reinforce-spec.dev"
export REINFORCE_SPEC_API_KEY="your-api-key"
export REINFORCE_SPEC_TIMEOUT="30"
```

```python
from reinforce_spec_sdk import ReinforceSpecClient

# Loads from environment
client = ReinforceSpecClient.from_env()
```

### Client Options

```python
client = ReinforceSpecClient(
    base_url="https://api.reinforce-spec.dev",
    api_key="your-api-key",
    timeout=30.0,                    # Request timeout in seconds
    max_retries=3,                   # Max retry attempts
    retry_delay=1.0,                 # Initial retry delay
    retry_max_delay=30.0,            # Max retry delay
    retry_jitter=5.0,                # Random jitter for retries
)
```

## API Reference

### `client.select()`

Evaluate candidates and select the best one.

```python
response = await client.select(
    candidates=[
        {"content": "...", "source_model": "gpt-4", "metadata": {}},
        {"content": "...", "source_model": "claude-3"},
    ],
    selection_method="hybrid",       # "hybrid" | "scoring_only" | "rl_only"
    request_id="unique-id",          # Idempotency key
    description="API spec for...",   # Context for scoring
)
```

**Returns:** `SelectionResponse`

### `client.submit_feedback()`

Submit human feedback for reinforcement learning.

```python
feedback_id = await client.submit_feedback(
    request_id="original-request-id",
    rating=4.5,                      # 1.0-5.0
    comment="Good structure",
    spec_id="selected-spec-id",
)
```

**Returns:** `str` (feedback ID)

### `client.get_policy_status()`

Get the current RL policy status.

```python
status = await client.get_policy_status()
print(f"Version: {status.version}")
print(f"Stage: {status.stage}")
print(f"Mean Reward: {status.mean_reward}")
```

**Returns:** `PolicyStatus`

### `client.health()`

Check API health.

```python
health = await client.health()
print(f"Status: {health.status}")
```

**Returns:** `HealthResponse`

## Error Handling

```python
from reinforce_spec_sdk import ReinforceSpecClient
from reinforce_spec_sdk.exceptions import (
    ReinforceSpecError,
    ValidationError,
    RateLimitError,
    ServerError,
)

async with ReinforceSpecClient.from_env() as client:
    try:
        response = await client.select(candidates=[...])
    except ValidationError as e:
        print(f"Invalid input: {e.message}")
        print(f"Details: {e.details}")
    except RateLimitError as e:
        print(f"Rate limited. Retry after: {e.retry_after}s")
    except ServerError as e:
        print(f"Server error: {e.status_code}")
    except ReinforceSpecError as e:
        print(f"API error: {e}")
```

## Types

All request and response types are fully typed with Pydantic models:

```python
from reinforce_spec_sdk.types import (
    # Enums
    SelectionMethod,
    SpecFormat,
    PolicyStage,
    
    # Request types
    SpecInput,
    
    # Response types
    SelectionResponse,
    CandidateSpec,
    DimensionScore,
    PolicyStatus,
    HealthResponse,
)
```

## Testing

```python
from reinforce_spec_sdk import ReinforceSpecClient
from reinforce_spec_sdk.testing import MockClient

# Use mock client in tests
client = MockClient(
    select_response=SelectionResponse(...),
)

response = await client.select(candidates=[...])
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/

# Linting
ruff check src/
```

## License

MIT License - see [LICENSE](LICENSE) for details.
