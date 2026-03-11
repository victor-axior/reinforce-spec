---
title: ReinforceSpec Documentation
description: RL-optimized enterprise specification evaluator and selector
hide:
  - navigation
  - toc
---

<style>
.md-typeset h1 {
  display: none;
}
.hero {
  text-align: center;
  padding: 4rem 1rem;
}
.hero h1 {
  display: block !important;
  font-size: 3rem;
  font-weight: 700;
  margin-bottom: 1rem;
}
.hero .tagline {
  font-size: 1.4rem;
  color: var(--md-default-fg-color--light);
  margin-bottom: 2rem;
}
.hero .buttons {
  display: flex;
  gap: 1rem;
  justify-content: center;
  flex-wrap: wrap;
}
.hero .buttons a {
  padding: 0.75rem 1.5rem;
  border-radius: 0.5rem;
  font-weight: 600;
  text-decoration: none;
}
.hero .buttons .primary {
  background: var(--md-primary-fg-color);
  color: var(--md-primary-bg-color);
}
.hero .buttons .secondary {
  border: 2px solid var(--md-primary-fg-color);
  color: var(--md-primary-fg-color);
}
.features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 2rem;
  padding: 2rem 0;
}
.feature {
  padding: 1.5rem;
  border-radius: 0.5rem;
  background: var(--md-code-bg-color);
}
.feature h3 {
  margin-top: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.code-example {
  margin: 3rem 0;
}
</style>

<div class="hero">
  <h1>ReinforceSpec</h1>
  <p class="tagline">Score, evaluate, and select the best specifications using multi-judge LLMs and reinforcement learning</p>
  <div class="buttons">
    <a href="getting-started/quickstart/" class="primary">Get Started →</a>
    <a href="api-reference/" class="secondary">API Reference</a>
  </div>
</div>

---

## What is ReinforceSpec?

ReinforceSpec is an **enterprise-grade specification evaluation API** that helps engineering teams select the best technical specifications from multiple candidates. It combines:

- **Multi-Judge LLM Evaluation** — Claude, GPT-4, and Gemini score specs across 12 enterprise dimensions
- **Reinforcement Learning** — PPO-trained policy learns from your feedback to improve selection
- **Production-Ready** — Built-in rate limiting, idempotency, circuit breakers, and audit logging

<div class="features">
  <div class="feature">
    <h3>:material-scale-balance: Enterprise Scoring</h3>
    <p>Evaluate specifications across 12 dimensions including security, scalability, compliance, testability, and maintainability.</p>
  </div>
  <div class="feature">
    <h3>:material-robot: RL-Optimized Selection</h3>
    <p>A PPO-trained policy learns from your outcomes to continuously improve spec selection accuracy.</p>
  </div>
  <div class="feature">
    <h3>:material-shield-check: Production Hardened</h3>
    <p>Circuit breakers, retry logic, rate limiting, and comprehensive audit trails built in.</p>
  </div>
  <div class="feature">
    <h3>:material-api: REST & SDK</h3>
    <p>Full REST API with OpenAPI spec, plus native Python SDK for seamless integration.</p>
  </div>
</div>

---

## Quick Example

=== "Python SDK"

    ```python
    from reinforce_spec_sdk import ReinforceSpecClient

    async with ReinforceSpecClient.from_env() as client:
        result = await client.select(
            candidates=[
                {"content": "# API Spec A\n- OAuth2 + mTLS\n- PCI-DSS Level 1"},
                {"content": "# API Spec B\n- Basic auth\n- No encryption"},
            ],
            description="Payment API security comparison",
        )
        
        print(f"Selected: {result.selected.content[:50]}...")
        print(f"Score: {result.selected.composite_score:.2f}")
    ```

=== "REST API"

    ```bash
    curl -X POST https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/v1/specs \
      -H "Authorization: Bearer $RS_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "candidates": [
          {"content": "# API Spec A\n- OAuth2 + mTLS\n- PCI-DSS Level 1"},
          {"content": "# API Spec B\n- Basic auth\n- No encryption"}
        ],
        "description": "Payment API security comparison"
      }'
    ```

=== "Response"

    ```json
    {
      "request_id": "req_01HQXYZ123ABC",
      "selected": {
        "index": 0,
        "composite_score": 0.847,
        "dimension_scores": {
          "security": 0.95,
          "compliance": 0.92,
          "scalability": 0.78
        }
      },
      "selection_method": "hybrid",
      "latency_ms": 2847
    }
    ```

---

## Core Concepts

| Concept | Description |
|---------|-------------|
| **Candidates** | 2+ specification documents in any format (Markdown, JSON, YAML, plain text) |
| **Scoring** | Multi-judge LLM ensemble scores each spec across 12 enterprise dimensions |
| **Selection** | Hybrid algorithm combines scoring with RL policy for final selection |
| **Feedback** | Submit outcomes to continuously improve the RL policy |

[:octicons-arrow-right-24: Learn more about concepts](concepts/index.md)

---

## Why ReinforceSpec?

<div class="grid cards" markdown>

-   :material-clock-fast:{ .lg .middle } **Save Hours of Review**

    ---

    Automated scoring eliminates subjective bias and reduces spec review time from hours to seconds.

-   :material-chart-timeline-variant:{ .lg .middle } **Continuous Improvement**

    ---

    RL policy learns from your feedback. The more you use it, the better it gets at selecting specs your team prefers.

-   :material-security:{ .lg .middle } **Enterprise Ready**

    ---

    SOC 2 compliant architecture with full audit trails, encryption at rest, and configurable data retention.

-   :material-cog-outline:{ .lg .middle } **Flexible Integration**

    ---

    REST API, Python SDK, or embed scoring directly into your CI/CD pipeline.

</div>

---

## Get Started

<div class="grid cards" markdown>

-   **[:material-rocket-launch: Quickstart](getting-started/quickstart.md)**
    
    Get up and running in 5 minutes with the Python SDK

-   **[:material-key-variant: Authentication](getting-started/authentication.md)**
    
    Set up API keys and configure authentication

-   **[:material-book-open-variant: API Reference](api-reference/index.md)**
    
    Complete REST API documentation with examples

-   **[:material-github: Examples](https://github.com/reinforce-spec/reinforce-spec/tree/main/examples)**
    
    Browse working code examples on GitHub

</div>
