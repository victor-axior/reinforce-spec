# POST /v1/specs/feedback

Submit feedback on a previous selection to improve the reinforcement learning model.

---

## Endpoint

```http
POST /v1/specs/feedback
```

---

## Description

This endpoint closes the feedback loop for reinforcement learning by:

1. **Recording** whether the selected spec was good or bad
2. **Updating** the replay buffer with the experience
3. **Triggering** model improvement when enough data is collected

Every piece of feedback makes the selection algorithm smarter.

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
| `request_id` | string | **Yes** | The request_id from the original `/v1/specs` response |
| `selected_index` | integer | **Yes** | Index of the spec being rated (usually 0) |
| `reward` | number | **Yes** | Reward signal: `-1.0` to `1.0` |
| `feedback_type` | string | No | `thumbs_up`, `thumbs_down`, `rating`, `explicit` |
| `comment` | string | No | Free-form feedback text (max 1000 chars) |
| `actual_outcome` | object | No | Structured outcome data |
| `metadata` | object | No | Additional context |

### Reward Interpretation

| Value | Meaning |
|-------|---------|
| `1.0` | Perfect choice |
| `0.5` | Good choice |
| `0.0` | Neutral / acceptable |
| `-0.5` | Poor choice |
| `-1.0` | Terrible choice |

---

## Request Examples

=== "Simple (Binary)"

    ```json
    {
      "request_id": "req_01HQXYZ123ABC",
      "selected_index": 0,
      "reward": 1.0
    }
    ```

=== "With Comment"

    ```json
    {
      "request_id": "req_01HQXYZ123ABC",
      "selected_index": 0,
      "reward": 0.8,
      "feedback_type": "rating",
      "comment": "Good security recommendations but missing rate limiting details"
    }
    ```

=== "With Outcome Data"

    ```json
    {
      "request_id": "req_01HQXYZ123ABC",
      "selected_index": 0,
      "reward": 1.0,
      "feedback_type": "explicit",
      "actual_outcome": {
        "production_deployed": true,
        "issues_encountered": [],
        "time_to_implement_hours": 8,
        "stakeholder_satisfaction": 5
      },
      "metadata": {
        "reviewer": "tech-lead",
        "environment": "production"
      }
    }
    ```

=== "Negative Feedback"

    ```json
    {
      "request_id": "req_01HQXYZ123ABC",
      "selected_index": 0,
      "reward": -0.5,
      "feedback_type": "thumbs_down",
      "comment": "Selected spec lacked compliance requirements we needed",
      "actual_outcome": {
        "preferred_index": 1,
        "reason": "compliance"
      }
    }
    ```

=== "curl"

    ```bash
    curl -X POST https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/v1/specs/feedback \
      -H "Authorization: Bearer $RS_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "request_id": "req_01HQXYZ123ABC",
        "selected_index": 0,
        "reward": 1.0,
        "comment": "Great selection!"
      }'
    ```

=== "Python"

    ```python
    from reinforce_spec_sdk import ReinforceSpecClient

    client = ReinforceSpecClient()

    await client.submit_feedback(
        request_id="req_01HQXYZ123ABC",
        selected_index=0,
        reward=1.0,
        comment="Perfect for our use case",
    )
    ```

---

## Response

### Success (200 OK)

```json
{
  "feedback_id": "fb_01HQXYZ789GHI",
  "request_id": "req_01HQXYZ123ABC",
  "selected_index": 0,
  "reward": 1.0,
  "status": "recorded",
  "replay_buffer_size": 1247,
  "next_training_at": 1500,
  "created_at": "2024-01-15T11:00:00Z"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `feedback_id` | string | Unique feedback identifier |
| `request_id` | string | Original request this feedback relates to |
| `selected_index` | integer | Index of the rated spec |
| `reward` | number | The reward value submitted |
| `status` | string | `recorded`, `processed`, `training_triggered` |
| `replay_buffer_size` | integer | Current experiences in buffer |
| `next_training_at` | integer | Buffer size that triggers training |
| `created_at` | string | ISO 8601 timestamp |

### Training Triggered Response

When feedback triggers a training run:

```json
{
  "feedback_id": "fb_01HQXYZ789GHI",
  "request_id": "req_01HQXYZ123ABC",
  "selected_index": 0,
  "reward": 1.0,
  "status": "training_triggered",
  "replay_buffer_size": 1500,
  "training_job_id": "train_01HQXYZ999JKL",
  "created_at": "2024-01-15T11:00:00Z"
}
```

---

## Errors

| Status | Error Code | Description |
|--------|------------|-------------|
| `400` | `bad_request` | Malformed JSON |
| `401` | `unauthorized` | Missing or invalid API key |
| `404` | `request_not_found` | Original request_id doesn't exist |
| `409` | `duplicate_feedback` | Feedback already submitted |
| `422` | `validation_failed` | Invalid request body |
| `429` | `rate_limited` | Too many requests |

### Request Not Found Example

```json
{
  "error": "request_not_found",
  "message": "No selection found for request_id",
  "details": {
    "request_id": "req_invalid123",
    "suggestion": "Verify the request_id from the original /v1/specs response"
  }
}
```

### Duplicate Feedback Example

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

---

## Best Practices

### When to Submit Feedback

| Timing | Reward Quality | Example |
|--------|----------------|---------|
| Immediate | Low confidence | Quick thumbs up/down |
| After review | Medium confidence | Technical review complete |
| Post-implementation | High confidence | Spec used in production |

### Reward Signal Quality

Better feedback = better model:

```python
# ❌ Low quality: Binary only
await client.submit_feedback(
    request_id=req_id,
    selected_index=0,
    reward=1.0,  # Was it really perfect?
)

# ✅ High quality: Nuanced with context
await client.submit_feedback(
    request_id=req_id,
    selected_index=0,
    reward=0.7,
    comment="Good overall but security section needed expansion",
    actual_outcome={
        "modifications_required": ["security", "error_handling"],
        "time_saved_vs_manual": 4,  # hours
    },
)
```

### Feedback Loop Patterns

=== "Immediate UI Feedback"

    ```python
    # User clicks thumbs up in UI
    await client.submit_feedback(
        request_id=req_id,
        selected_index=0,
        reward=0.8,
        feedback_type="thumbs_up",
    )
    ```

=== "Delayed Expert Review"

    ```python
    # Tech lead reviews selection later
    await client.submit_feedback(
        request_id=req_id,
        selected_index=0,
        reward=0.6,
        feedback_type="rating",
        comment="Decent but competitor analysis incomplete",
        metadata={"reviewer_role": "tech_lead"},
    )
    ```

=== "Production Outcome"

    ```python
    # Automated feedback from production metrics
    await client.submit_feedback(
        request_id=req_id,
        selected_index=0,
        reward=calculate_reward(production_metrics),
        feedback_type="explicit",
        actual_outcome=production_metrics,
    )
    ```

---

## Idempotency

Include an `Idempotency-Key` header to safely retry:

```http
Idempotency-Key: feedback-req_01HQXYZ123ABC-1
```

Note: Duplicate feedback for the same `request_id` (without idempotency key) returns a `409` error.

---

## Related

- [Evaluate Specs](specs.md) — Get a request_id first
- [Policy Status](policy.md) — Check training progress
- [Feedback Loop Guide](../guides/feedback-loop.md) — Best practices
