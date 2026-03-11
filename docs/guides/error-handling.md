# Error Handling Guide

Comprehensive guide to handling errors when using the ReinforceSpec API.

---

## Error Categories

| Category | Status Codes | Retryable | Action |
|----------|--------------|-----------|--------|
| Client Errors | 400, 401, 403, 422 | No | Fix request |
| Rate Limits | 429 | Yes | Wait and retry |
| Server Errors | 500, 502, 503, 504 | Yes | Retry with backoff |

---

## Exception Handling

### Python SDK

```python
from reinforce_spec_sdk import ReinforceSpecClient
from reinforce_spec_sdk.exceptions import (
    ReinforceSpecError,
    ValidationError,
    AuthenticationError,
    RateLimitError,
    ScoringError,
    ServiceUnavailableError,
    TimeoutError,
)

client = ReinforceSpecClient()

try:
    result = await client.select(candidates=[spec_a, spec_b])
    
except ValidationError as e:
    # 422: Invalid request
    print(f"Validation failed: {e.message}")
    print(f"Details: {e.details}")
    # Fix request and retry
    
except AuthenticationError as e:
    # 401: Bad credentials
    print(f"Auth failed: {e.message}")
    # Check API key
    
except RateLimitError as e:
    # 429: Too many requests
    print(f"Rate limited. Retry after {e.retry_after}s")
    await asyncio.sleep(e.retry_after)
    result = await client.select(candidates=[spec_a, spec_b])
    
except ScoringError as e:
    # 502: LLM provider failed
    print(f"Scoring failed: {e.message}")
    if e.retryable:
        await asyncio.sleep(5)
        result = await client.select(candidates=[spec_a, spec_b])
    
except ServiceUnavailableError as e:
    # 503: Service down
    print(f"Service unavailable: {e.message}")
    # Use fallback or retry later
    
except TimeoutError as e:
    # 504: Request timeout
    print(f"Request timed out after {e.timeout}s")
    # Retry with fewer candidates
    
except ReinforceSpecError as e:
    # Catch-all
    print(f"Error {e.error}: {e.message}")
    if e.request_id:
        print(f"Request ID: {e.request_id}")
```

### HTTP Client

```python
import httpx

async def evaluate(candidates):
    async with httpx.AsyncClient() as http:
        response = await http.post(
            "https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/v1/specs",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"candidates": candidates},
            timeout=30.0,
        )
        
        if response.status_code == 200:
            return response.json()
        
        error = response.json()
        
        match response.status_code:
            case 400:
                raise BadRequestError(error["message"])
            case 401:
                raise AuthenticationError(error["message"])
            case 422:
                raise ValidationError(error["message"], error["details"])
            case 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitError(retry_after=retry_after)
            case 500:
                raise ServerError(error["message"])
            case 502:
                raise ScoringError(error["message"])
            case 503:
                raise ServiceUnavailableError(error["message"])
            case 504:
                raise TimeoutError(error["message"])
            case _:
                raise APIError(error["error"], error["message"])
```

---

## Retry Strategies

### Exponential Backoff

```python
import asyncio
import random

async def retry_with_backoff(
    func,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
):
    for attempt in range(max_retries):
        try:
            return await func()
        except (ScoringError, ServiceUnavailableError, TimeoutError) as e:
            if attempt == max_retries - 1:
                raise
            
            delay = min(base_delay * (2 ** attempt), max_delay)
            if jitter:
                delay *= (0.5 + random.random())
            
            logger.warning(
                f"Attempt {attempt + 1} failed: {e}. "
                f"Retrying in {delay:.1f}s"
            )
            await asyncio.sleep(delay)
```

### Tenacity Library

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type((ScoringError, TimeoutError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def evaluate_with_retry(candidates):
    return await client.select(candidates=candidates)
```

### Rate Limit Handling

```python
async def evaluate_respecting_limits(candidates):
    while True:
        try:
            return await client.select(candidates=candidates)
        except RateLimitError as e:
            logger.warning(f"Rate limited, waiting {e.retry_after}s")
            await asyncio.sleep(e.retry_after)
```

---

## Circuit Breaker

Prevent cascading failures:

```python
from circuitbreaker import circuit

class CircuitBreakerConfig:
    FAILURE_THRESHOLD = 5
    RECOVERY_TIMEOUT = 60
    EXPECTED_EXCEPTIONS = (ServiceUnavailableError, TimeoutError)

@circuit(
    failure_threshold=CircuitBreakerConfig.FAILURE_THRESHOLD,
    recovery_timeout=CircuitBreakerConfig.RECOVERY_TIMEOUT,
    expected_exception=CircuitBreakerConfig.EXPECTED_EXCEPTIONS,
)
async def evaluate_with_circuit_breaker(candidates):
    return await client.select(candidates=candidates)

# Usage
try:
    result = await evaluate_with_circuit_breaker(candidates)
except CircuitBreakerError:
    logger.error("Circuit breaker open, using fallback")
    result = fallback_selection(candidates)
```

---

## Fallback Strategies

### Simple Fallback

```python
async def evaluate_with_fallback(candidates):
    try:
        return await client.select(
            candidates=candidates,
            selection_method="hybrid",
        )
    except ServiceUnavailableError:
        logger.warning("Service unavailable, trying scoring only")
        try:
            return await client.select(
                candidates=candidates,
                selection_method="scoring_only",
            )
        except ServiceUnavailableError:
            logger.error("All methods failed, using local fallback")
            return local_selection(candidates)
```

### Graceful Degradation

```python
class EvaluationService:
    def __init__(self, client):
        self.client = client
        self.degraded = False
    
    async def evaluate(self, candidates):
        if self.degraded:
            return await self._degraded_evaluate(candidates)
        
        try:
            result = await self.client.select(
                candidates=candidates,
                selection_method="hybrid",
            )
            return result
        except ServiceUnavailableError:
            self.degraded = True
            asyncio.create_task(self._check_recovery())
            return await self._degraded_evaluate(candidates)
    
    async def _degraded_evaluate(self, candidates):
        """Simpler evaluation when service is degraded."""
        return await self.client.select(
            candidates=candidates,
            selection_method="scoring_only",
            judges=[Judge(model="google/gemini-1.5-flash")],
        )
    
    async def _check_recovery(self):
        while True:
            await asyncio.sleep(60)
            try:
                await self.client.health_check()
                self.degraded = False
                logger.info("Service recovered")
                return
            except Exception:
                continue
```

---

## Error Logging

### Structured Logging

```python
import structlog

logger = structlog.get_logger()

async def evaluate_with_logging(candidates):
    request_id = str(uuid.uuid4())
    
    logger.info(
        "evaluation_started",
        request_id=request_id,
        candidate_count=len(candidates),
    )
    
    try:
        result = await client.select(
            candidates=candidates,
            request_id=request_id,
        )
        
        logger.info(
            "evaluation_completed",
            request_id=request_id,
            rs_request_id=result.request_id,
            selected_index=result.selected.index,
            score=result.selected.composite_score,
            latency_ms=result.latency_ms,
        )
        
        return result
        
    except ReinforceSpecError as e:
        logger.error(
            "evaluation_failed",
            request_id=request_id,
            error_code=e.error,
            error_message=e.message,
            rs_request_id=e.request_id,
        )
        raise
```

### Error Tracking

```python
import sentry_sdk

sentry_sdk.init(dsn="your-sentry-dsn")

async def evaluate_with_tracking(candidates):
    try:
        return await client.select(candidates=candidates)
    except ReinforceSpecError as e:
        sentry_sdk.capture_exception(e)
        sentry_sdk.set_context("reinforce_spec", {
            "error": e.error,
            "request_id": e.request_id,
        })
        raise
```

---

## Error-Specific Handling

### Validation Errors

```python
async def handle_validation_error(candidates, error: ValidationError):
    """Attempt to fix validation errors automatically."""
    
    details = error.details.get("errors", [])
    
    for err in details:
        if err["field"] == "candidates" and err["constraint"] == "maxItems":
            # Too many candidates - split and evaluate
            chunks = chunk_list(candidates, size=10)
            results = []
            for chunk in chunks:
                result = await client.select(candidates=chunk)
                results.append(result)
            return merge_results(results)
        
        if err["field"].startswith("candidates[") and "maxLength" in err["constraint"]:
            # Content too long - truncate
            idx = int(err["field"].split("[")[1].split("]")[0])
            candidates[idx]["content"] = truncate(
                candidates[idx]["content"],
                max_length=100000,
            )
            return await client.select(candidates=candidates)
    
    # Can't fix automatically
    raise error
```

### Scoring Errors

```python
async def handle_scoring_error(candidates, error: ScoringError):
    """Handle LLM provider failures."""
    
    if "rate_limited" in str(error):
        # OpenRouter rate limit - wait and retry
        await asyncio.sleep(60)
        return await client.select(candidates=candidates)
    
    if "model_unavailable" in str(error):
        # Specific model down - use different judges
        return await client.select(
            candidates=candidates,
            judges=[
                Judge(model="google/gemini-1.5-pro"),  # Fallback
            ],
        )
    
    # Unknown scoring error - retry with backoff
    await asyncio.sleep(5)
    return await client.select(candidates=candidates)
```

---

## Testing Error Handling

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_retry_on_rate_limit():
    mock_client = AsyncMock()
    mock_client.evaluate.side_effect = [
        RateLimitError(retry_after=1),
        {"selected": {"index": 0}},
    ]
    
    result = await evaluate_with_retry(
        client=mock_client,
        candidates=[{"content": "a"}, {"content": "b"}],
    )
    
    assert mock_client.evaluate.call_count == 2
    assert result["selected"]["index"] == 0

@pytest.mark.asyncio
async def test_circuit_breaker_opens():
    mock_client = AsyncMock()
    mock_client.evaluate.side_effect = ServiceUnavailableError("Down")
    
    # Should open after 5 failures
    for _ in range(5):
        with pytest.raises(ServiceUnavailableError):
            await evaluate_with_circuit_breaker(
                client=mock_client,
                candidates=[{"content": "a"}, {"content": "b"}],
            )
    
    # Next call should fail immediately
    with pytest.raises(CircuitBreakerError):
        await evaluate_with_circuit_breaker(
            client=mock_client,
            candidates=[{"content": "a"}, {"content": "b"}],
        )
```

---

## Related

- [Error Codes Reference](../api-reference/errors.md) — All error codes
- [Best Practices](best-practices.md) — Production patterns
- [Idempotency](../concepts/idempotency.md) — Safe retries
