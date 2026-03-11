# API Reference

Complete reference documentation for the ReinforceSpec REST API.

---

## Base URL

| Environment | Base URL |
|-------------|----------|
| Production | `https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com` |
| Self-hosted | `https://your-domain.com` |
| Local | `http://localhost:8000` |

All endpoints are prefixed with `/v1`.

---

## Authentication

Include your API key in the `Authorization` header:

```http
Authorization: Bearer your-api-key
```

See [Authentication](../getting-started/authentication.md) for details.

---

## Content Type

All requests must include:

```http
Content-Type: application/json
```

---

## Endpoints

### Core

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | [`/v1/specs`](specs.md) | Evaluate and select the best specification |
| `POST` | [`/v1/specs/feedback`](feedback.md) | Submit feedback on a selection |

### Policy Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | [`/v1/policy/status`](policy.md) | Get RL policy status |
| `POST` | [`/v1/policy/train`](policy.md#train-policy) | Trigger policy training |

### Health & Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | [`/v1/health`](health.md) | Liveness probe |
| `GET` | [`/v1/health/ready`](health.md#readiness) | Readiness probe |

---

## Request Format

### Standard Request

```json
{
  "candidates": [
    {"content": "Spec A content..."},
    {"content": "Spec B content..."}
  ],
  "description": "What these specs are for",
  "selection_method": "hybrid"
}
```

### With Idempotency

Include an idempotency key to safely retry requests:

```http
Idempotency-Key: unique-request-id-12345
```

If a request with the same key was already processed, the cached response is returned.

---

## Response Format

### Successful Response

```json
{
  "request_id": "req_01HQXYZ123ABC",
  "selected": {
    "index": 0,
    "composite_score": 0.847,
    "dimension_scores": {...}
  },
  "all_candidates": [...],
  "selection_method": "hybrid",
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
  }
}
```

See [Error Codes](errors.md) for all error types.

---

## Rate Limits

| Tier | Requests/min | Burst |
|------|-------------|-------|
| Free | 10 | 20 |
| Pro | 60 | 120 |
| Enterprise | Custom | Custom |

Rate limit headers are included in responses:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640995200
Retry-After: 60
```

See [Rate Limits](../resources/rate-limits.md) for details.

---

## Pagination

For endpoints returning lists:

```http
GET /v1/jobs?limit=20&offset=40
```

Response includes pagination metadata:

```json
{
  "data": [...],
  "pagination": {
    "total": 100,
    "limit": 20,
    "offset": 40,
    "has_more": true
  }
}
```

---

## Versioning

The API is versioned via URL path (`/v1/`). Breaking changes will increment the version number.

| Version | Status | End of Life |
|---------|--------|-------------|
| `v1` | Current | — |

---

## OpenAPI Specification

Download the complete OpenAPI 3.1 specification:

- **JSON**: [`/openapi.json`](https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/openapi.json)
- **YAML**: [GitHub](https://github.com/reinforce-spec/reinforce-spec/blob/main/openapi.yml)

Interactive documentation available at:

- **Swagger UI**: [`/docs`](https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/docs)
- **ReDoc**: [`/redoc`](https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/redoc)

---

## SDKs

| Language | Package | Documentation |
|----------|---------|---------------|
| Python | `reinforce-spec` | [Python SDK](../sdks/python.md) |
| HTTP | curl, httpx | [HTTP Examples](../sdks/http.md) |

---

## Quick Links

<div class="grid cards" markdown>

-   **[POST /v1/specs](specs.md)**
    
    The main endpoint for spec evaluation

-   **[Error Codes](errors.md)**
    
    Complete error reference

-   **[Rate Limits](../resources/rate-limits.md)**
    
    Quotas and throttling

-   **[Idempotency](../concepts/idempotency.md)**
    
    Safe request retries

</div>
