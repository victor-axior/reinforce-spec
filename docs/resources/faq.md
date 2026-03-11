# Frequently Asked Questions

Common questions about ReinforceSpec.

---

## General

### What is ReinforceSpec?

ReinforceSpec is an API service that evaluates and selects the best software specification from multiple candidates using:

1. **Multi-judge LLM scoring** across 12 enterprise dimensions
2. **Reinforcement learning** that improves from your feedback
3. **Hybrid selection** combining both approaches

### What types of specifications can I evaluate?

Any text-based specifications:

- API specifications (OpenAPI, GraphQL schemas)
- Architecture documents
- Software Requirements Specifications (SRS)
- Product Requirements Documents (PRD)
- Design documents
- RFCs

### How accurate is the selection?

Accuracy depends on:

- **Scoring only**: 80-85% agreement with expert reviewers
- **Hybrid (with feedback)**: 85-90%+ accuracy
- **Mature RL model**: 90%+ accuracy after 5000+ feedback samples

---

## Pricing & Limits

### Is there a free tier?

Yes. The free tier includes:

- 10 requests/minute
- 500 requests/day
- Access to all features

### How much does it cost?

| Tier | Price | Requests/min |
|------|-------|-------------|
| Free | $0 | 10 |
| Pro | $49/month | 60 |
| Enterprise | Custom | Custom |

### What counts as a request?

Each API call to `/v1/specs` counts as one request, regardless of the number of candidates (2-10).

---

## Technical

### Which LLMs are used for scoring?

By default:

- Claude 3.5 Sonnet (Anthropic)
- GPT-4o (OpenAI)
- Gemini 1.5 Pro (Google)

All accessed through OpenRouter for unified billing and management.

### How long does evaluation take?

| Candidates | Typical Latency |
|------------|----------------|
| 2 | 2-3 seconds |
| 5 | 4-6 seconds |
| 10 | 8-12 seconds |

Using `rl_only` (after training): 50-100ms

### Can I use my own LLM API keys?

Yes, if self-hosting. When using the hosted API, scoring uses shared infrastructure.

### Is my data stored?

- **Specification content**: Not stored after evaluation
- **Scores and selections**: Stored for feedback/training
- **Feedback**: Stored for model improvement

See our [Privacy Policy](https://reinforce-spec.dev/privacy) for details.

---

## Setup

### Do I need to train the model?

No! ReinforceSpec works out of the box with `scoring_only` or `hybrid` mode. The RL component trains automatically from feedback you submit.

### What's the minimum to get started?

```python
from reinforce_spec_sdk import ReinforceSpecClient

client = ReinforceSpecClient()  # Uses RS_API_KEY env var

result = await client.select(
    candidates=[
        {"content": "Spec A..."},
        {"content": "Spec B..."},
    ]
)
```

### How do I set up authentication?

1. Get an API key from [dashboard.reinforce-spec.dev](https://dashboard.reinforce-spec.dev)
2. Set `RS_API_KEY` environment variable
3. (Optional) Set `OPENROUTER_API_KEY` for self-hosted deployments

---

## Features

### What are the 12 scoring dimensions?

1. Security
2. Compliance
3. Scalability
4. Maintainability
5. Testability
6. Observability
7. Reliability
8. Performance
9. Cost Efficiency
10. Interoperability
11. Documentation
12. Risk Mitigation

See [Scoring Dimensions](../concepts/scoring-dimensions.md) for details.

### Can I customize dimension weights?

Yes:

```python
client = ReinforceSpecClient(
    dimension_weights={
        "security": 0.25,
        "compliance": 0.20,
        # Others get remaining weight
    }
)
```

### What's the difference between selection methods?

| Method | Description | When to Use |
|--------|-------------|-------------|
| `scoring_only` | Pure LLM scoring | Deterministic, explainable |
| `hybrid` | Scoring + RL (default) | Best overall quality |
| `rl_only` | RL prediction only | After 5000+ feedback |

---

## Troubleshooting

### Why am I getting rate limited?

Check your tier limits and implement backoff:

```python
try:
    result = await client.select(...)
except RateLimitError as e:
    await asyncio.sleep(e.retry_after)
    result = await client.select(...)
```

### Why is scoring slow?

Possible causes:

1. **Many candidates**: Each candidate is scored by multiple LLMs
2. **Long specifications**: More tokens = more time
3. **LLM provider latency**: OpenRouter routes to multiple providers

Solutions:

- Reduce candidate count
- Truncate very long specs
- Use `rl_only` after training

### Why did the "wrong" spec get selected?

Possible reasons:

1. **Different priorities**: Your priorities may differ from default weights
2. **Context missing**: Add `description` for better context
3. **Model needs training**: Submit feedback to improve

```python
# Customize for your needs
client = ReinforceSpecClient(
    dimension_weights={"security": 0.30},
)

# Add context
result = await client.select(
    candidates=[...],
    description="Financial API requiring PCI compliance",
)

# Submit feedback to improve
await client.submit_feedback(
    request_id=result.request_id,
    selected_index=0,
    reward=-0.5,  # Was not a good selection
    comment="Needed stronger compliance coverage",
)
```

---

## Integration

### Can I use ReinforceSpec in CI/CD?

Yes! Common patterns:

- Evaluate spec changes in PRs
- Gate merges on minimum scores
- Compare before/after specs

See [CI/CD Integration](../guides/best-practices.md#cicd-integration).

### Is there a webhook for async results?

Webhooks are planned for a future release. Currently, use polling or async processing:

```python
# Async processing
result = await client.select(candidates=candidates)
# Process result immediately
```

### Can I integrate with LangChain?

Yes, ReinforceSpecClient works well as a spec evaluation step in LangChain pipelines:

```python
from langchain.chains import LLMChain

# Generate specs with LangChain
specs = [chain.run(prompt) for prompt in prompts]

# Evaluate with ReinforceSpec
result = await client.select(
    candidates=[{"content": s} for s in specs]
)
```

---

## Still Have Questions?

- **Discord**: [discord.gg/reinforce-spec](https://discord.gg/reinforce-spec)
- **GitHub**: [github.com/reinforce-spec/reinforce-spec/discussions](https://github.com/reinforce-spec/reinforce-spec/discussions)
- **Email**: [support@reinforce-spec.dev](mailto:support@reinforce-spec.dev)
