# Rate Limits

API rate limits, quotas, and best practices for staying within limits.

---

## Limits by Tier

| Tier | Requests/min | Daily Limit | Burst |
|------|-------------|-------------|-------|
| Free | 10 | 500 | 20 |
| Pro | 60 | 10,000 | 120 |
| Enterprise | Custom | Custom | Custom |

---

## Rate Limit Headers

Every response includes rate limit information:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640995200
```

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Max requests per minute |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Reset` | Unix timestamp when window resets |

When rate limited (429 response):

```http
Retry-After: 45
```

---

## Rate Limit Response

```json
{
  "error": "rate_limited",
  "message": "Rate limit exceeded",
  "details": {
    "limit": 60,
    "remaining": 0,
    "reset_at": "2024-01-15T12:01:00Z",
    "retry_after_seconds": 45
  }
}
```

---

## Endpoint-Specific Limits

| Endpoint | Cost | Notes |
|----------|------|-------|
| `POST /v1/specs` | 1 | Main evaluation endpoint |
| `POST /v1/specs/feedback` | 0.5 | Feedback is encouraged |
| `GET /v1/policy/status` | 0.1 | Low-cost read |
| `POST /v1/policy/train` | 10 | Admin only, expensive |
| `GET /v1/health/*` | 0 | No rate limit |

---

## Best Practices

### Monitor Remaining Quota

```python
async def evaluate_with_quota_check(candidates):
    response = await client.request(
        "POST", "/v1/specs",
        json={"candidates": candidates},
    )
    
    remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
    
    if remaining < 10:
        logger.warning(f"Rate limit low: {remaining} remaining")
    
    return response.json()
```

### Implement Backoff

```python
import asyncio
from tenacity import retry, wait_exponential, retry_if_exception_type

@retry(
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type(RateLimitError),
)
async def evaluate_with_backoff(candidates):
    try:
        return await client.select(candidates=candidates)
    except RateLimitError as e:
        logger.warning(f"Rate limited, waiting {e.retry_after}s")
        await asyncio.sleep(e.retry_after)
        raise
```

### Batch Requests Efficiently

```python
async def evaluate_batch(all_candidates, batch_size=5, delay=1.0):
    """Process in batches with delay to avoid rate limiting."""
    results = []
    
    for i in range(0, len(all_candidates), batch_size):
        batch = all_candidates[i:i + batch_size]
        
        batch_results = await asyncio.gather(*[
            client.select(candidates=c) for c in batch
        ])
        results.extend(batch_results)
        
        # Delay between batches
        if i + batch_size < len(all_candidates):
            await asyncio.sleep(delay)
    
    return results
```

### Use Caching

```python
from functools import lru_cache
import hashlib

def content_hash(candidates):
    """Create deterministic hash for caching."""
    content = json.dumps(
        [c["content"] for c in candidates],
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()[:16]

@lru_cache(maxsize=1000)
async def cached_evaluate(content_hash: str, candidates_json: str):
    candidates = json.loads(candidates_json)
    return await client.select(candidates=candidates)
```

### Queue During High Load

```python
import asyncio
from collections import deque

class RateLimitedQueue:
    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.interval = 60 / requests_per_minute
        self.queue = deque()
        self.last_request = 0
    
    async def evaluate(self, candidates):
        now = time.time()
        wait_time = max(0, self.last_request + self.interval - now)
        
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        self.last_request = time.time()
        return await client.select(candidates=candidates)

queue = RateLimitedQueue(requests_per_minute=50)  # Leave headroom
```

---

## Upgrading Your Tier

### Pro Tier

Best for production applications:

- 60 requests/minute
- Priority support
- Higher burst limits

### Enterprise Tier

For high-volume applications:

- Custom rate limits
- Dedicated infrastructure
- SLA guarantees
- Direct support channel

Contact [sales@reinforce-spec.dev](mailto:sales@reinforce-spec.dev) for Enterprise pricing.

---

## Monitoring Rate Limits

### Prometheus Metrics

```promql
# Rate limit remaining
reinforce_spec_ratelimit_remaining

# Rate limit utilization
1 - (reinforce_spec_ratelimit_remaining / reinforce_spec_ratelimit_limit)

# Rate limit hits
rate(reinforce_spec_ratelimit_exceeded_total[5m])
```

### Alerting

```yaml
# prometheus-alerts.yml
groups:
  - name: rate-limits
    rules:
      - alert: RateLimitNearExhaustion
        expr: reinforce_spec_ratelimit_remaining < 10
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Rate limit nearly exhausted"
          
      - alert: RateLimitExceeded
        expr: rate(reinforce_spec_ratelimit_exceeded_total[5m]) > 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Hitting rate limits consistently"
```

---

## FAQ

### Why am I being rate limited?

Common causes:

1. **Burst traffic**: Too many requests at once
2. **Missing backoff**: Not respecting `Retry-After`
3. **Shared limits**: Multiple services using same key
4. **Inefficient patterns**: Not batching or caching

### How do limits reset?

Rate limits use a sliding window. The limit resets continuously, not at fixed intervals.

### Can I get higher limits?

Yes. Contact [sales@reinforce-spec.dev](mailto:sales@reinforce-spec.dev) for Enterprise tier with custom limits.

---

## Related

- [Error Codes](../api-reference/errors.md#rate_limited) — Rate limit errors
- [Best Practices](../guides/best-practices.md) — Optimization patterns
- [Error Handling](../guides/error-handling.md) — Retry strategies
