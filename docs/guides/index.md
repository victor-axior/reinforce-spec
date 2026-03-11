# Guides & Tutorials

Practical guides for getting the most out of ReinforceSpec.

---

## Getting Started

<div class="grid cards" markdown>

-   :material-rocket-launch: **[Quickstart](../getting-started/quickstart.md)**
    
    Get running in 5 minutes

-   :material-download: **[Installation](../getting-started/installation.md)**
    
    All installation options

-   :material-key: **[Authentication](../getting-started/authentication.md)**
    
    API key setup

</div>

---

## Core Workflows

<div class="grid cards" markdown>

-   :material-file-document-check: **[Scoring Specifications](scoring-specs.md)**
    
    Evaluate and score specs effectively

-   :material-sync: **[Feedback Loop](feedback-loop.md)**
    
    Train your model with feedback

</div>

---

## Production Guides

<div class="grid cards" markdown>

-   :material-shield-check: **[Best Practices](best-practices.md)**
    
    Production-ready patterns

-   :material-alert-circle: **[Error Handling](error-handling.md)**
    
    Robust error handling

-   :material-chart-line: **[Observability](observability.md)**
    
    Monitoring and alerting

</div>

---

## Tutorials by Use Case

### API Specification Evaluation

Compare and select the best API specification from multiple candidates:

```python
from reinforce_spec_sdk import ReinforceSpecClient

client = ReinforceSpecClient()

result = await client.select(
    candidates=[
        {"content": api_spec_v1, "spec_type": "api"},
        {"content": api_spec_v2, "spec_type": "api"},
    ],
    description="Payment API specification comparison",
    customer_type="fintech",
)

print(f"Selected: Spec {result.selected.index + 1}")
print(f"Score: {result.selected.composite_score:.2f}")
```

[Full API Scoring Tutorial →](scoring-specs.md#api-specifications)

### Architecture Document Selection

Choose the best architecture proposal:

```python
result = await client.select(
    candidates=[
        {"content": microservices_arch, "spec_type": "architecture"},
        {"content": serverless_arch, "spec_type": "architecture"},
        {"content": hybrid_arch, "spec_type": "architecture"},
    ],
    description="E-commerce platform architecture",
)
```

[Full Architecture Tutorial →](scoring-specs.md#architecture-documents)

### Continuous Improvement

Set up a feedback loop for ongoing model improvement:

```python
# Step 1: Evaluate
result = await client.select(candidates=[...])

# Step 2: Use the selection
selected_spec = result.selected.content
# ... use in your application ...

# Step 3: Submit feedback after review
await client.submit_feedback(
    request_id=result.request_id,
    selected_index=result.selected.index,
    reward=0.8,  # Good but not perfect
    comment="Needed minor security adjustments",
)
```

[Full Feedback Loop Tutorial →](feedback-loop.md)

---

## Integration Patterns

### CI/CD Pipeline Integration

Automatically evaluate specs in your pipeline:

```yaml
# .github/workflows/spec-review.yml
- name: Evaluate Spec Changes
  run: |
    python scripts/evaluate_specs.py \
      --before ${{ github.event.before }} \
      --after ${{ github.sha }}
```

[CI/CD Integration Guide →](best-practices.md#cicd-integration)

### Async Processing

Handle high-volume evaluation with async patterns:

```python
import asyncio

async def evaluate_batch(specs_batch):
    tasks = [
        client.select(candidates=specs)
        for specs in specs_batch
    ]
    return await asyncio.gather(*tasks)
```

[Async Patterns Guide →](best-practices.md#async-processing)

### Webhook Integration

Receive evaluation results via webhooks:

```python
@app.post("/webhook/spec-evaluated")
async def handle_evaluation(payload: EvaluationResult):
    # Process completed evaluation
    await notify_team(payload.selected)
    await update_dashboard(payload.metrics)
```

[Webhook Integration Guide →](best-practices.md#webhooks)

---

## Quick Reference

| Task | Guide |
|------|-------|
| Evaluate specs | [Scoring Specs](scoring-specs.md) |
| Set up feedback | [Feedback Loop](feedback-loop.md) |
| Handle errors | [Error Handling](error-handling.md) |
| Monitor production | [Observability](observability.md) |
| Optimize costs | [Best Practices](best-practices.md#cost-optimization) |
| Scale up | [Best Practices](best-practices.md#scaling) |
