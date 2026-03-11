# Scoring Specifications

Learn how to effectively evaluate and score specifications using ReinforceSpec's multi-judge LLM ensemble.

---

## Overview

This guide covers:

- Preparing specifications for evaluation
- Choosing the right scoring configuration
- Interpreting score results
- Optimizing for your use case

---

## Basic Scoring

### Minimal Example

```python
from reinforce_spec_sdk import ReinforceSpecClient

client = ReinforceSpecClient()

result = await client.select(
    candidates=[
        {"content": "# Spec A\nDetailed API specification..."},
        {"content": "# Spec B\nAlternative approach..."},
    ]
)

print(f"Winner: Spec {result.selected.index + 1}")
print(f"Score: {result.selected.composite_score:.2f}")
```

### With Context

Adding context improves scoring relevance:

```python
result = await client.select(
    candidates=[
        {"content": spec_a, "spec_type": "api"},
        {"content": spec_b, "spec_type": "api"},
    ],
    description="REST API for payment processing in fintech",
    customer_type="enterprise",
)
```

---

## Preparing Specifications

### Content Guidelines

| Do | Don't |
|-----|-------|
| ✅ Include full specification text | ❌ Send truncated content |
| ✅ Use consistent formatting | ❌ Mix formats (MD + HTML) |
| ✅ Include diagrams as text | ❌ Reference external images |
| ✅ Keep under 100KB per spec | ❌ Send massive documents |

### Recommended Structure

```markdown
# [Specification Title]

## Overview
Brief description of what this spec covers.

## Requirements
- Functional requirements
- Non-functional requirements

## Architecture
System design and components.

## Security
Authentication, authorization, encryption.

## Scalability
How the system handles growth.

## Implementation
Key implementation details.
```

### Spec Types

| Type | Best For |
|------|----------|
| `api` | REST/GraphQL API specifications |
| `architecture` | System architecture documents |
| `srs` | Software Requirements Specifications |
| `prd` | Product Requirements Documents |
| `design` | Design documents |
| `rfc` | Request for Comments |

```python
candidates = [
    {"content": spec, "spec_type": "api"},  # Helps scoring focus
]
```

---

## Scoring Configuration

### Dimension Weights

Customize weights for your domain:

```python
# Security-focused (financial services)
client = ReinforceSpecClient(
    dimension_weights={
        "security": 0.25,
        "compliance": 0.20,
        "reliability": 0.15,
        # Remaining dimensions share rest
    }
)

# Performance-focused (real-time systems)
client = ReinforceSpecClient(
    dimension_weights={
        "performance": 0.25,
        "scalability": 0.20,
        "reliability": 0.15,
    }
)
```

### Selection Method

Choose based on your needs:

```python
# Pure scoring (deterministic)
result = await client.select(
    candidates=candidates,
    selection_method="scoring_only",
)

# Hybrid (recommended)
result = await client.select(
    candidates=candidates,
    selection_method="hybrid",
)

# RL only (after training)
result = await client.select(
    candidates=candidates,
    selection_method="rl_only",
)
```

---

## Use Case Examples

### API Specifications {#api-specifications}

Comparing API design approaches:

```python
openapi_spec = """
openapi: 3.1.0
info:
  title: Payment API
  version: 2.0.0
paths:
  /payments:
    post:
      security:
        - oauth2: [write:payments]
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Payment'
...
"""

graphql_spec = """
type Mutation {
  createPayment(input: PaymentInput!): PaymentResult!
    @auth(requires: WRITE_PAYMENTS)
}

type Payment {
  id: ID!
  amount: Money!
  status: PaymentStatus!
}
...
"""

result = await client.select(
    candidates=[
        {"content": openapi_spec, "spec_type": "api"},
        {"content": graphql_spec, "spec_type": "api"},
    ],
    description="Payment processing API for fintech platform",
    customer_type="bank",
)

# Check why one was selected
print("Dimension breakdown:")
for dim, score in result.selected.dimension_scores.items():
    print(f"  {dim}: {score:.2f}")
```

### Architecture Documents {#architecture-documents}

Comparing system architectures:

```python
microservices = """
# Microservices Architecture

## Services
- API Gateway (Kong)
- Auth Service (OAuth2 + OIDC)
- Payment Service (PCI-DSS compliant)
- Notification Service (async)

## Communication
- Sync: gRPC with mTLS
- Async: Kafka for events

## Data
- PostgreSQL per service
- Redis for caching
- S3 for documents
"""

serverless = """
# Serverless Architecture

## Functions
- API: AWS Lambda + API Gateway
- Auth: Cognito + Lambda authorizers
- Payment: Step Functions workflow
- Notifications: SNS + Lambda

## Data
- DynamoDB (single-table design)
- S3 for storage
- ElastiCache for session
"""

result = await client.select(
    candidates=[
        {"content": microservices, "spec_type": "architecture"},
        {"content": serverless, "spec_type": "architecture"},
    ],
    description="E-commerce platform serving 10M MAU",
)
```

### Requirements Documents {#requirements-documents}

Evaluating PRDs or SRS documents:

```python
result = await client.select(
    candidates=[
        {"content": prd_v1, "spec_type": "prd"},
        {"content": prd_v2, "spec_type": "prd"},
    ],
    description="Mobile banking app requirements",
    customer_type="retail_bank",
)
```

---

## Interpreting Results

### Score Breakdown

```python
result = await client.select(candidates=candidates)

# Overall result
print(f"Selected: Index {result.selected.index}")
print(f"Composite Score: {result.selected.composite_score:.3f}")

# Dimension-by-dimension
print("\nDimension Scores:")
scores = result.selected.dimension_scores
for dim in sorted(scores, key=scores.get, reverse=True):
    print(f"  {dim:20}: {scores[dim]:.3f}")

# Compare all candidates
print("\nAll Candidates:")
for candidate in result.rankings:
    status = "✓" if candidate.index == result.selected.index else " "
    print(f"  [{status}] Index {candidate.index}: {candidate.composite_score:.3f}")
```

### Understanding Scores

| Score | Quality | Action |
|-------|---------|--------|
| 0.9+ | Excellent | Ready for production |
| 0.8-0.9 | Good | Minor improvements suggested |
| 0.7-0.8 | Adequate | Review weak dimensions |
| 0.6-0.7 | Needs work | Significant gaps exist |
| <0.6 | Poor | Major revision needed |

### Identifying Weaknesses

```python
# Find dimensions needing improvement
weak_dimensions = [
    (dim, score) 
    for dim, score in result.selected.dimension_scores.items()
    if score < 0.7
]

if weak_dimensions:
    print("Areas for improvement:")
    for dim, score in sorted(weak_dimensions, key=lambda x: x[1]):
        print(f"  - {dim}: {score:.2f}")
```

---

## Batch Evaluation

### Parallel Processing

```python
import asyncio

async def evaluate_all_specs(spec_pairs):
    """Evaluate multiple spec pairs in parallel."""
    tasks = [
        client.select(
            candidates=pair,
            request_id=f"batch-{i}",
        )
        for i, pair in enumerate(spec_pairs)
    ]
    return await asyncio.gather(*tasks)

# Evaluate many comparisons at once
results = await evaluate_all_specs([
    [spec_a1, spec_a2],
    [spec_b1, spec_b2],
    [spec_c1, spec_c2],
])
```

### Sequential with Progress

```python
from tqdm.asyncio import tqdm

async def evaluate_with_progress(spec_pairs):
    results = []
    async for pair in tqdm(spec_pairs, desc="Evaluating"):
        result = await client.select(candidates=pair)
        results.append(result)
    return results
```

---

## Optimization Tips

### Cost Reduction

```python
# Use fewer judges for non-critical evaluations
client = ReinforceSpecClient(
    judges=[
        Judge(model="google/gemini-1.5-flash"),  # Fast, cheap
    ],
)

# Enable caching for similar specs
client = ReinforceSpecClient(
    enable_score_cache=True,
)
```

### Latency Reduction

```python
# Pre-warm the client
await client.health_check()

# Use RL-only for trained models (much faster)
result = await client.select(
    candidates=candidates,
    selection_method="rl_only",  # ~50ms vs ~3s
)
```

### Quality Improvement

```python
# Use more judges for critical decisions
client = ReinforceSpecClient(
    judges=[
        Judge(model="anthropic/claude-3.5-sonnet", weight=1.2),
        Judge(model="openai/gpt-4o", weight=1.0),
        Judge(model="google/gemini-1.5-pro", weight=1.0),
        Judge(model="anthropic/claude-3-opus", weight=1.3),  # Add opus
    ],
)
```

---

## Next Steps

- [Feedback Loop](feedback-loop.md) — Improve selection over time
- [Best Practices](best-practices.md) — Production patterns
