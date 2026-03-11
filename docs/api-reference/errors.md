# Error Codes Reference

Complete reference of all error codes returned by the ReinforceSpec API.

---

## Error Response Format

All errors follow a consistent structure:

```json
{
  "error": "error_code",
  "message": "Human-readable description",
  "details": {
    "field": "specific_field",
    "constraint": "what_was_violated",
    "value": "provided_value"
  },
  "request_id": "req_01HQXYZ123ABC",
  "documentation_url": "https://docs.reinforce-spec.dev/errors#error_code"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `error` | string | Machine-readable error code |
| `message` | string | Human-readable description |
| `details` | object | Additional context (varies by error) |
| `request_id` | string | Request ID for support |
| `documentation_url` | string | Link to relevant documentation |

---

## HTTP Status Codes

| Status | Category | Description |
|--------|----------|-------------|
| `400` | Client Error | Bad request syntax |
| `401` | Authentication | Missing or invalid credentials |
| `403` | Authorization | Valid credentials but insufficient permissions |
| `404` | Not Found | Resource doesn't exist |
| `409` | Conflict | Resource state conflict |
| `422` | Validation | Request body validation failed |
| `429` | Rate Limit | Too many requests |
| `500` | Server Error | Internal server error |
| `502` | Bad Gateway | Upstream service error |
| `503` | Unavailable | Service temporarily unavailable |
| `504` | Timeout | Request timeout |

---

## Authentication Errors (401)

### unauthorized

Missing or invalid API key.

```json
{
  "error": "unauthorized",
  "message": "Invalid or missing API key",
  "details": {
    "header": "Authorization",
    "expected_format": "Bearer <api-key>"
  }
}
```

**Resolution:**
- Verify API key is correct
- Check `Authorization: Bearer <key>` header format
- Ensure key hasn't been revoked

### token_expired

API key has expired.

```json
{
  "error": "token_expired",
  "message": "API key has expired",
  "details": {
    "expired_at": "2024-01-01T00:00:00Z"
  }
}
```

**Resolution:**
- Generate a new API key
- Implement key rotation before expiry

---

## Authorization Errors (403)

### forbidden

Valid credentials but insufficient permissions.

```json
{
  "error": "forbidden",
  "message": "Insufficient permissions for this operation",
  "details": {
    "required_scope": "admin",
    "current_scopes": ["read", "write"]
  }
}
```

**Resolution:**
- Request elevated permissions
- Use appropriate key for the operation

### rate_limit_exceeded_permanently

Account suspended due to abuse.

```json
{
  "error": "rate_limit_exceeded_permanently",
  "message": "Account suspended due to excessive rate limit violations",
  "details": {
    "violations": 50,
    "suspended_until": "2024-01-20T00:00:00Z"
  }
}
```

**Resolution:**
- Contact support
- Review rate limiting documentation

---

## Validation Errors (422)

### validation_failed

Request body doesn't match schema.

```json
{
  "error": "validation_failed",
  "message": "Request validation failed",
  "details": {
    "errors": [
      {
        "field": "candidates",
        "constraint": "minItems",
        "message": "At least 2 candidates are required",
        "value": 1,
        "required": 2
      }
    ]
  }
}
```

**Common Validation Errors:**

| Field | Constraint | Message |
|-------|------------|---------|
| `candidates` | `minItems` | At least 2 candidates required |
| `candidates` | `maxItems` | Maximum 10 candidates allowed |
| `candidates[].content` | `required` | Content is required |
| `candidates[].content` | `maxLength` | Content exceeds 100,000 characters |
| `reward` | `minimum` | Reward must be >= -1.0 |
| `reward` | `maximum` | Reward must be <= 1.0 |
| `description` | `maxLength` | Description exceeds 2,000 characters |

### invalid_content_type

Wrong Content-Type header.

```json
{
  "error": "invalid_content_type",
  "message": "Content-Type must be application/json",
  "details": {
    "received": "text/plain",
    "expected": "application/json"
  }
}
```

---

## Request Errors (400)

### bad_request

Malformed request syntax.

```json
{
  "error": "bad_request",
  "message": "Invalid JSON syntax",
  "details": {
    "parse_error": "Unexpected token at position 45"
  }
}
```

### idempotency_mismatch

Same idempotency key with different request body.

```json
{
  "error": "idempotency_mismatch",
  "message": "Request body doesn't match previous request with same idempotency key",
  "details": {
    "idempotency_key": "my-key-123",
    "original_hash": "abc123",
    "new_hash": "def456"
  }
}
```

**Resolution:**
- Use a unique idempotency key for each unique request
- To retry the same request, use the exact same body

---

## Resource Errors (404, 409)

### request_not_found

Referenced request doesn't exist.

```json
{
  "error": "request_not_found",
  "message": "No selection found for request_id",
  "details": {
    "request_id": "req_invalid123"
  }
}
```

**Resolution:**
- Verify request_id from original `/v1/specs` response
- Request IDs expire after 30 days

### duplicate_feedback

Feedback already submitted.

```json
{
  "error": "duplicate_feedback",
  "message": "Feedback already submitted for this request",
  "details": {
    "existing_feedback_id": "fb_01HQXYZ789GHI",
    "submitted_at": "2024-01-15T10:45:00Z"
  }
}
```

**Resolution:**
- Each request_id can only receive one feedback
- Use idempotency keys to safely retry feedback submissions

### training_in_progress

Training job already running.

```json
{
  "error": "training_in_progress",
  "message": "A training job is already running",
  "details": {
    "current_job_id": "train_01HQXYZ888JKL",
    "started_at": "2024-01-15T11:58:00Z"
  }
}
```

---

## Rate Limiting Errors (429)

### rate_limited

Too many requests.

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

**Headers included:**

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1705320060
Retry-After: 45
```

**Resolution:**
- Wait for `Retry-After` seconds
- Implement exponential backoff
- Consider upgrading your plan

---

## Server Errors (5xx)

### internal_error

Unexpected server error.

```json
{
  "error": "internal_error",
  "message": "An unexpected error occurred",
  "details": {
    "request_id": "req_01HQXYZ123ABC"
  }
}
```

**Resolution:**
- Retry with exponential backoff
- Contact support with request_id if persistent

### scoring_failed

LLM provider error.

```json
{
  "error": "scoring_failed",
  "message": "Failed to score candidates",
  "details": {
    "provider": "openrouter",
    "upstream_error": "rate_limited",
    "models_affected": ["claude-3-opus"]
  }
}
```

**Resolution:**
- The system will attempt fallback models
- Retry after a short delay
- Check OpenRouter status page

### service_unavailable

Circuit breaker open.

```json
{
  "error": "service_unavailable",
  "message": "Service temporarily unavailable",
  "details": {
    "reason": "circuit_breaker_open",
    "component": "llm_scorer",
    "retry_after_seconds": 30
  }
}
```

**Resolution:**
- Wait for retry_after_seconds
- System is protecting itself from cascading failures
- Check status page for incidents

### timeout

Request took too long.

```json
{
  "error": "timeout",
  "message": "Request processing timed out",
  "details": {
    "timeout_seconds": 30,
    "stage": "llm_scoring"
  }
}
```

**Resolution:**
- Retry with fewer candidates
- Reduce spec content size
- Try during off-peak hours

---

## Error Handling Best Practices

### Python SDK

```python
from reinforce_spec_sdk import ReinforceSpecClient, ReinforceSpecError
from reinforce_spec_sdk.exceptions import (
    ValidationError,
    RateLimitError,
    ScoringError,
)

client = ReinforceSpecClient()

try:
    result = await client.select(candidates=[...])
except ValidationError as e:
    # Fix request and retry
    logger.error(f"Validation failed: {e.details}")
except RateLimitError as e:
    # Wait and retry
    await asyncio.sleep(e.retry_after)
    result = await client.select(candidates=[...])
except ScoringError as e:
    # LLM provider issue - retry with backoff
    logger.warning(f"Scoring failed: {e.message}")
    # Implement backoff logic
except ReinforceSpecError as e:
    # Catch-all for other API errors
    logger.error(f"API error: {e.error} - {e.message}")
```

### Retry Strategy

```python
import asyncio
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type((ScoringError, TimeoutError)),
)
async def evaluate_with_retry(candidates):
    return await client.select(candidates=candidates)
```

### HTTP Client

```python
import httpx

async def handle_response(response: httpx.Response):
    if response.status_code == 200:
        return response.json()
    
    error = response.json()
    
    match response.status_code:
        case 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            raise RateLimitError(retry_after=retry_after)
        case 422:
            raise ValidationError(details=error["details"])
        case 502 | 503:
            raise RetryableError(error["message"])
        case _:
            raise APIError(error["error"], error["message"])
```

---

## Getting Help

If you encounter persistent errors:

1. **Check status page**: [status.reinforce-spec.dev](https://status.reinforce-spec.dev)
2. **Search documentation**: Use the search above
3. **Include request_id**: Always include in support requests
4. **Contact support**: [support@reinforce-spec.dev](mailto:support@reinforce-spec.dev)

---

## Related

- [API Reference](index.md) — Full endpoint documentation
- [Rate Limits](../resources/rate-limits.md) — Quotas and limits
- [Error Handling Guide](../guides/error-handling.md) — Implementation patterns
