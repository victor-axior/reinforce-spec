# Best Practices

Production-ready patterns for deploying and operating ReinforceSpec.

---

## API Usage

### Use Idempotency Keys

Always include idempotency keys for safe retries:

```python
import uuid

async def evaluate_safely(candidates):
    idempotency_key = str(uuid.uuid4())
    
    for attempt in range(3):
        try:
            return await client.select(
                candidates=candidates,
                request_id=idempotency_key,
            )
        except NetworkError:
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)
```

### Handle Rate Limits

Implement exponential backoff:

```python
from reinforce_spec_sdk.exceptions import RateLimitError

async def evaluate_with_backoff(candidates):
    for attempt in range(5):
        try:
            return await client.select(candidates=candidates)
        except RateLimitError as e:
            wait_time = e.retry_after or (2 ** attempt)
            logger.warning(f"Rate limited, waiting {wait_time}s")
            await asyncio.sleep(wait_time)
    
    raise Exception("Max retries exceeded")
```

### Batch Requests Efficiently

```python
# Good: Process in parallel batches
async def evaluate_batch(all_candidates: list[list], batch_size: int = 10):
    results = []
    
    for i in range(0, len(all_candidates), batch_size):
        batch = all_candidates[i:i + batch_size]
        batch_results = await asyncio.gather(*[
            client.select(candidates=c)
            for c in batch
        ])
        results.extend(batch_results)
        
        # Respect rate limits
        await asyncio.sleep(1)
    
    return results
```

---

## Error Handling

### Comprehensive Error Handling

```python
from reinforce_spec_sdk.exceptions import (
    ReinforceSpecError,
    ValidationError,
    RateLimitError,
    ScoringError,
    ServiceUnavailableError,
)

async def robust_evaluate(candidates):
    try:
        return await client.select(candidates=candidates)
    
    except ValidationError as e:
        # Client error - fix request
        logger.error(f"Validation failed: {e.details}")
        raise
    
    except RateLimitError as e:
        # Retry after delay
        await asyncio.sleep(e.retry_after)
        return await client.select(candidates=candidates)
    
    except ScoringError as e:
        # LLM provider issue - maybe retry
        logger.warning(f"Scoring failed: {e.message}")
        if e.retryable:
            await asyncio.sleep(5)
            return await client.select(candidates=candidates)
        raise
    
    except ServiceUnavailableError:
        # Service down - use fallback
        logger.error("Service unavailable, using fallback")
        return fallback_selection(candidates)
    
    except ReinforceSpecError as e:
        # Catch-all for API errors
        logger.error(f"API error: {e.error} - {e.message}")
        raise
```

### Circuit Breaker Pattern

```python
from circuitbreaker import circuit

@circuit(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=ServiceUnavailableError,
)
async def evaluate_with_circuit_breaker(candidates):
    return await client.select(candidates=candidates)
```

---

## Performance Optimization

### Connection Pooling

```python
import httpx

# Reuse client for connection pooling
limits = httpx.Limits(
    max_keepalive_connections=20,
    max_connections=100,
)

async with httpx.AsyncClient(limits=limits) as http_client:
    client = ReinforceSpecClient(http_client=http_client)
    
    # Multiple requests reuse connections
    results = await asyncio.gather(*[
        client.select(candidates=c) for c in candidates_list
    ])
```

### Caching

```python
from functools import lru_cache
import hashlib

def spec_hash(spec: str) -> str:
    return hashlib.sha256(spec.encode()).hexdigest()[:16]

# Cache evaluation results
@lru_cache(maxsize=1000)
async def cached_evaluate(spec_hash_a: str, spec_hash_b: str):
    # Note: actual implementation would need async-compatible cache
    pass

# Use content-based cache keys
async def evaluate_with_cache(spec_a: str, spec_b: str):
    cache_key = f"{spec_hash(spec_a)}-{spec_hash(spec_b)}"
    
    cached = await cache.get(cache_key)
    if cached:
        return cached
    
    result = await client.select(candidates=[
        {"content": spec_a},
        {"content": spec_b},
    ])
    
    await cache.set(cache_key, result, ttl=3600)
    return result
```

### Async Processing

```python
# Process evaluations without blocking
async def async_evaluate(candidates, callback_url: str):
    # Start evaluation
    result = await client.select(
        candidates=candidates,
        request_id=str(uuid.uuid4()),
    )
    
    # Notify via webhook
    async with httpx.AsyncClient() as http:
        await http.post(callback_url, json=result.model_dump())
    
    return result

# Queue-based processing
async def process_evaluation_queue(queue):
    while True:
        request = await queue.get()
        try:
            result = await client.select(
                candidates=request.candidates,
                request_id=request.idempotency_key,
            )
            await notify_completion(request.callback_url, result)
        except Exception as e:
            await notify_failure(request.callback_url, e)
        finally:
            queue.task_done()
```

---

## Cost Optimization {#cost-optimization}

### Use Appropriate Judges

```python
# Development: single cheap judge
dev_client = ReinforceSpecClient(
    judges=[Judge(model="google/gemini-1.5-flash")],
)

# Production: full ensemble
prod_client = ReinforceSpecClient(
    judges=[
        Judge(model="anthropic/claude-3.5-sonnet"),
        Judge(model="openai/gpt-4o"),
        Judge(model="google/gemini-1.5-pro"),
    ],
)
```

### Progressive Evaluation

```python
async def progressive_evaluate(candidates: list):
    """Fast filter, then full evaluation on top candidates."""
    
    # Quick filter with cheap model
    quick_results = await client.select(
        candidates=candidates,
        selection_method="scoring_only",
        judges=[Judge(model="google/gemini-1.5-flash")],
    )
    
    # Full evaluation on top 3
    top_indices = [r.index for r in quick_results.rankings[:3]]
    top_candidates = [candidates[i] for i in top_indices]
    
    return await client.select(
        candidates=top_candidates,
        selection_method="hybrid",
    )
```

### Use RL After Training

```python
async def cost_aware_evaluate(candidates):
    status = await client.get_policy_status()
    
    if status.metrics.total_feedback > 5000:
        # RL is trained - use it (no LLM cost)
        return await client.select(
            candidates=candidates,
            selection_method="rl_only",
        )
    else:
        # Still training - use hybrid
        return await client.select(
            candidates=candidates,
            selection_method="hybrid",
        )
```

---

## Scaling {#scaling}

### Horizontal Scaling

```yaml
# Kubernetes HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: reinforce-spec
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: reinforce-spec
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### Database Scaling

```python
# Use connection pooling
DATABASE_URL = "postgresql://user:pass@host/db?pool_size=20&max_overflow=10"

# Read replicas for status checks
async def get_policy_status():
    # Use read replica
    return await read_replica_client.get_policy_status()
```

### Request Queuing

```python
import asyncio
from collections import deque

class RequestQueue:
    def __init__(self, max_concurrent: int = 50):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.queue = deque()
    
    async def evaluate(self, candidates):
        async with self.semaphore:
            return await client.select(candidates=candidates)

# Limit concurrent evaluations
queue = RequestQueue(max_concurrent=50)
result = await queue.select(candidates)
```

---

## CI/CD Integration {#cicd-integration}

### GitHub Actions

```yaml
name: Spec Evaluation

on:
  pull_request:
    paths:
      - 'specs/**'

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install reinforce-spec
      
      - name: Evaluate Changed Specs
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
        run: |
          python scripts/evaluate_pr_specs.py \
            --before ${{ github.event.before }} \
            --after ${{ github.sha }}
      
      - name: Comment Results
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const results = JSON.parse(fs.readFileSync('evaluation_results.json'));
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## Spec Evaluation Results\n\n${results.summary}`
            });
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: evaluate-specs
        name: Evaluate Specifications
        entry: python scripts/evaluate_specs.py
        language: python
        files: ^specs/.*\.(md|yaml)$
        pass_filenames: true
```

---

## Webhook Integration {#webhooks}

### Receiving Webhooks

```python
from fastapi import FastAPI, Request, HTTPException
import hmac
import hashlib

app = FastAPI()

WEBHOOK_SECRET = os.environ["RS_WEBHOOK_SECRET"]

def verify_signature(payload: bytes, signature: str) -> bool:
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)

@app.post("/webhook/evaluation")
async def handle_evaluation(request: Request):
    payload = await request.body()
    signature = request.headers.get("X-RS-Signature", "")
    
    if not verify_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    data = await request.json()
    
    # Process evaluation result
    await process_evaluation_result(data)
    
    return {"status": "received"}
```

### Configuring Webhooks

```python
# Configure webhook endpoint
await client.configure_webhook(
    url="https://your-app.com/webhook/evaluation",
    events=["evaluation.completed", "training.completed"],
    secret=webhook_secret,
)
```

---

## Security Best Practices

### API Key Management

```python
import os
from cryptography.fernet import Fernet

# Never hardcode keys
api_key = os.environ["RS_API_KEY"]

# Rotate keys regularly
async def rotate_api_key():
    new_key = await client.admin.create_api_key(
        name="production-key",
        scopes=["read", "write"],
        expires_in_days=90,
    )
    
    # Update secrets manager
    await secrets_manager.update("RS_API_KEY", new_key)
    
    # Revoke old key after grace period
    await asyncio.sleep(3600)  # 1 hour
    await client.admin.revoke_api_key(old_key_id)
```

### Request Validation

```python
from pydantic import BaseModel, validator

class EvaluationRequest(BaseModel):
    candidates: list[dict]
    description: str | None = None
    
    @validator("candidates")
    def validate_candidates(cls, v):
        if len(v) < 2:
            raise ValueError("At least 2 candidates required")
        if len(v) > 10:
            raise ValueError("Maximum 10 candidates allowed")
        for c in v:
            if len(c.get("content", "")) > 100_000:
                raise ValueError("Candidate content too long")
        return v
```

---

## Related

- [Error Handling](error-handling.md) — Detailed error handling
- [Observability](observability.md) — Monitoring and alerting
- [Idempotency](../concepts/idempotency.md) — Safe retries
