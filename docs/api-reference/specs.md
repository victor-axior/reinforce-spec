# POST /v1/specs

Evaluate multiple specification candidates and select the best one using multi-judge LLM scoring and reinforcement learning.

---

## Endpoint

```http
POST /v1/specs
```

---

## Description

This is the core endpoint of ReinforceSpec. It:

1. **Scores** each candidate spec across 12 enterprise dimensions using a multi-judge LLM ensemble
2. **Selects** the best spec using a hybrid algorithm combining scores with an RL-trained policy
3. **Returns** the selected spec with detailed scoring breakdown

---

## Request

### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | `Bearer <api-key>` |
| `Content-Type` | Yes | `application/json` |
| `Idempotency-Key` | No | Unique key for safe retries |

### Body Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `candidates` | array | **Yes** | 2+ specification candidates to evaluate |
| `description` | string | No | Context about what these specs are for (max 2000 chars) |
| `customer_type` | string | No | Customer segment for scoring adjustment |
| `selection_method` | string | No | `scoring_only`, `hybrid` (default), or `rl_only` |
| `request_id` | string | No | Custom request ID (auto-generated if not provided) |

### Candidate Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | **Yes** | The specification content (any format) |
| `spec_type` | string | No | Type hint: `api`, `architecture`, `srs`, `prd`, etc. |
| `source_model` | string | No | LLM that generated this spec |
| `metadata` | object | No | Arbitrary metadata to pass through |

---

## Request Examples

=== "Minimal"

    ```json
    {
      "candidates": [
        {"content": "# Spec A\nOAuth2 with mTLS, PCI-DSS Level 1"},
        {"content": "# Spec B\nBasic auth, no encryption"}
      ]
    }
    ```

=== "Full"

    ```json
    {
      "candidates": [
        {
          "content": "# Payment API v2\n\n## Security\n- OAuth 2.0 with PKCE\n- mTLS for service-to-service\n- AES-256 encryption at rest\n\n## Compliance\n- PCI DSS Level 1\n- SOC 2 Type II",
          "spec_type": "api",
          "source_model": "claude-3-opus",
          "metadata": {"version": "2.0", "author": "team-payments"}
        },
        {
          "content": "# Payment API v1\n\n## Security\n- API key authentication\n- HTTPS only",
          "spec_type": "api",
          "source_model": "gpt-4",
          "metadata": {"version": "1.0"}
        }
      ],
      "description": "Comparing payment API security specifications",
      "customer_type": "bank",
      "selection_method": "hybrid",
      "request_id": "eval-payment-api-2024-001"
    }
    ```

=== "curl"

    ```bash
    curl -X POST https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/v1/specs \
      -H "Authorization: Bearer $RS_API_KEY" \
      -H "Content-Type: application/json" \
      -H "Idempotency-Key: $(uuidgen)" \
      -d '{
        "candidates": [
          {"content": "# Spec A\nOAuth2 + mTLS"},
          {"content": "# Spec B\nBasic auth"}
        ],
        "description": "Security comparison"
      }'
    ```

=== "Python"

    ```python
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/v1/specs",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Idempotency-Key": "unique-request-id",
            },
            json={
                "candidates": [
                    {"content": "# Spec A\nOAuth2 + mTLS"},
                    {"content": "# Spec B\nBasic auth"},
                ],
                "description": "Security comparison",
            },
        )
        result = response.json()
    ```

---

## Response

### Success (200 OK)

```json
{
  "request_id": "req_01HQXYZ123ABC",
  "selected": {
    "index": 0,
    "spec_id": "spec_01HQXYZ456DEF",
    "content": "# Payment API v2\n\n## Security...",
    "spec_type": "api",
    "composite_score": 0.847,
    "dimension_scores": {
      "security": 0.95,
      "compliance": 0.92,
      "scalability": 0.78,
      "maintainability": 0.85,
      "testability": 0.82,
      "observability": 0.80,
      "reliability": 0.88,
      "performance": 0.75,
      "cost_efficiency": 0.70,
      "interoperability": 0.83,
      "documentation": 0.90,
      "risk_mitigation": 0.87
    },
    "metadata": {"version": "2.0", "author": "team-payments"}
  },
  "all_candidates": [
    {
      "index": 0,
      "spec_id": "spec_01HQXYZ456DEF",
      "composite_score": 0.847,
      "is_selected": true
    },
    {
      "index": 1,
      "spec_id": "spec_01HQXYZ789GHI",
      "composite_score": 0.523,
      "is_selected": false
    }
  ],
  "rankings": [
    {"index": 0, "composite_score": 0.847, "rank": 1},
    {"index": 1, "composite_score": 0.523, "rank": 2}
  ],
  "selection_method": "hybrid",
  "policy_version": "v001",
  "latency_ms": 2847,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Unique request identifier |
| `selected` | object | The selected specification with full details |
| `selected.index` | integer | Index in the original candidates array |
| `selected.composite_score` | number | Weighted aggregate score (0-1) |
| `selected.dimension_scores` | object | Scores per dimension (0-1 each) |
| `all_candidates` | array | Summary of all evaluated candidates |
| `rankings` | array | Candidates sorted by score |
| `selection_method` | string | Method used for selection |
| `policy_version` | string | RL policy version used |
| `latency_ms` | integer | Total processing time |
| `created_at` | string | ISO 8601 timestamp |

---

## Errors

| Status | Error Code | Description |
|--------|------------|-------------|
| `400` | `bad_request` | Malformed JSON |
| `401` | `unauthorized` | Missing or invalid API key |
| `422` | `validation_failed` | Invalid request body |
| `429` | `rate_limited` | Too many requests |
| `502` | `scoring_failed` | LLM provider error |
| `503` | `service_unavailable` | Circuit breaker open |

### Validation Error Example

```json
{
  "error": "validation_failed",
  "message": "At least 2 candidates are required",
  "details": {
    "field": "candidates",
    "constraint": "minItems",
    "value": 1,
    "required": 2
  }
}
```

---

## Selection Methods

| Method | Description | When to Use |
|--------|-------------|-------------|
| `scoring_only` | Pure LLM-based scoring | Deterministic results needed |
| `hybrid` | Scoring + RL policy (default) | Best overall selection |
| `rl_only` | RL policy without scoring | After sufficient training |

See [Selection Methods](../concepts/selection-methods.md) for details.

---

## Idempotency

Include an `Idempotency-Key` header to safely retry requests:

```http
Idempotency-Key: eval-payment-api-2024-001
```

- Keys expire after 24 hours
- Same key returns cached response
- Different request body with same key returns error

See [Idempotency](../concepts/idempotency.md) for details.

---

## Rate Limits

This endpoint consumes 1 rate limit token per request.

Typical response times:

| Candidates | Avg Latency |
|------------|-------------|
| 2 | ~2-3 seconds |
| 5 | ~4-6 seconds |
| 10 | ~8-12 seconds |

---

## Related

- [Submit Feedback](feedback.md) — Improve the RL model
- [Scoring Dimensions](../concepts/scoring-dimensions.md) — What's being evaluated
- [Python SDK](../sdks/python.md) — Native Python client
