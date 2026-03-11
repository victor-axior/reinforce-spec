# ReinforceSpec

**RL-optimized enterprise specification evaluator and selector.**

ReinforceSpec scores and selects the best enterprise software specification from user-provided candidates using multi-judge LLM evaluation and PPO reinforcement learning.

## Features

- **Bring your own specs** — Submit 2+ spec candidates in any format (text, JSON, YAML, Markdown, etc.) and let ReinforceSpec pick the best one
- **Auto format detection** — Automatically identifies spec format (text, JSON, YAML, Markdown) for optimal feature extraction
- **12-dimension enterprise scoring** — Rigorous evaluation against compliance, security, scalability, observability, data governance, integration, testing, DX, cost, performance, DR/BCP, and vendor independence
- **Multi-judge LLM ensemble** — Chain-of-thought evaluation from multiple models with position-swapped pairwise comparison and bias mitigation
- **PPO reinforcement learning** — Contextual bandit policy with action-dependent rewards, trained via prioritized experience replay with per-candidate composite scores
- **Replay-mode training** — Environment replays real evaluation transitions during PPO training, returning the actual per-candidate reward for the chosen action so the policy learns genuine quality signal
- **Automated data loop** — Built-in script (`scripts/build_replay_buffer.py`) runs diverse evaluation → feedback → train cycles across 20 domain scenarios to bootstrap the replay buffer
- **Customer-type presets** — Weight configurations for bank, system integrator, BPO, and SaaS archetypes
- **Graceful degradation** — 4-level ladder (L0 full → L3 emergency) ensures availability under load
- **Production infrastructure** — Circuit breaker, retry with backoff, idempotency, backpressure, structured logging, Prometheus metrics, drift detection

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     FastAPI Server                       │
│  POST /v1/specs  →  Evaluate → Score → Select → Return  │
│  POST /v1/specs/feedback  →  Shape RL reward             │
│  POST /v1/policy/train    →  PPO training step           │
│  GET  /v1/policy/status   →  Policy version & metrics    │
└──────────────────────────────────────────────────────────┘
                       │                    │
                ┌──────▼──────┐     ┌──────▼──────┐
                │  Scorer     │     │  Selector   │
                │(Multi-Judge)│     │(RL + Score) │
                └──────┬──────┘     └──────┬──────┘
                       │                    │
    ┌──────────────────▼────────────────────▼──────┐
    │              OpenRouter (LLM API)            │
    │         + Gym Environment + PPO Policy       │
    │         + Prioritized Replay Buffer          │
    │         + PostgreSQL Persistence             │
    └──────────────────────────────────────────────┘
```

### RL Training Pipeline

```
select()                      train_policy()
   │                               │
   ▼                               ▼
Score candidates ──────► Transition(obs, reward,    ──► PPO.learn()
   │                      candidate_rewards[])          │
   ▼                               │                    ▼
Record to PER buffer ◄─────────────┘       Env replays transitions
   │                                       reward = candidate_rewards[action]
   ▼                                               │
SelectionResponse                           Policy updated & promoted
```

Each `select()` call records a `Transition` with per-candidate composite scores.
During training, the Gym environment replays these transitions and returns
**action-dependent rewards** — the actual score of whichever candidate the
policy chooses — so PPO receives a genuine gradient signal.

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/reinforce-spec.git
cd reinforce-spec

# Install with uv (recommended)
make install

# Or with pip
pip install -e ".[dev]"
```

### Configuration

```bash
cp .env.example .env
# Edit .env with your OpenRouter API key and RS_DATABASE_URL
```

### Docker Deployment Flow

Use the local deployment flow aligned with production health behavior:

```bash
make docker-build
make docker-up
make docker-smoke
```

To tear down services:

```bash
make docker-down
```

### PostgreSQL (Local)

Docker Compose starts a local Postgres instance and the API uses it via
`RS_DATABASE_URL`.

### SQLite → PostgreSQL Migration

Use the migration script to move existing SQLite data into PostgreSQL:

```bash
python scripts/migrate_sqlite_to_postgres.py \
  --sqlite-path data/reinforce_spec.db \
  --postgres-url postgresql://postgres:postgres@localhost:5432/reinforce_spec
```

### ECS Fargate Deployment

With `RS_AWS_*` values configured in `.env`:

```bash
scripts/aws/deploy_ecs_fargate.sh
```

### Usage

#### Official SDKs

ReinforceSpec provides official SDKs for Python, TypeScript, and Go.

=== "Python"

```python
import asyncio
from reinforce_spec_sdk import ReinforceSpecClient

async def main():
    async with ReinforceSpecClient(
        base_url="https://api.reinforce-spec.dev",
        api_key="your-api-key",
    ) as client:
        response = await client.select(
            candidates=[
                {"content": "# Payment API\n## Auth\n- OAuth 2.0 with mTLS", "spec_type": "api"},
                {"content": '{"openapi":"3.0","info":{"title":"Payments"}}', "spec_type": "api"},
            ],
        )
        print(f"Selected: index {response.selected.index}")
        print(f"Score: {response.selected.composite_score:.2f}")

asyncio.run(main())
```

=== "TypeScript"

```typescript
import { ReinforceSpecClient } from '@reinforce-spec/sdk';

const client = new ReinforceSpecClient({
  baseUrl: process.env.REINFORCE_SPEC_BASE_URL!,
  apiKey: process.env.REINFORCE_SPEC_API_KEY,
});

const response = await client.select({
  candidates: [
    { content: '# Payment API\n- OAuth 2.0', specType: 'api' },
    { content: '{"openapi":"3.0"}', specType: 'api' },
  ],
});

console.log(`Selected: ${response.selected.index}`);
console.log(`Score: ${response.selected.compositeScore.toFixed(2)}`);
```

=== "Go"

```go
package main

import (
    "context"
    "fmt"

    reinforce "github.com/reinforce-spec/reinforce-spec/sdks/go"
)

func main() {
    client := reinforce.NewClient(
        reinforce.WithBaseURL(os.Getenv("REINFORCE_SPEC_BASE_URL")),
        reinforce.WithAPIKey(os.Getenv("REINFORCE_SPEC_API_KEY")),
    )

    resp, err := client.Select(context.Background(), &reinforce.SelectRequest{
        Candidates: []reinforce.Candidate{
            {Content: "# Payment API\n- OAuth 2.0", SpecType: "api"},
            {Content: `{"openapi":"3.0"}`, SpecType: "api"},
        },
    })
    if err != nil {
        panic(err)
    }

    fmt.Printf("Selected: %d\n", resp.Selected.Index)
    fmt.Printf("Score: %.2f\n", resp.Selected.CompositeScore)
}
```

For detailed SDK documentation, see:
- [Python SDK](docs/sdks/python.md)
- [TypeScript SDK](docs/sdks/typescript.md)
- [Go SDK](docs/sdks/go.md)

#### REST API

```bash
# Start the server
make serve

# Evaluate and select the best spec
curl -X POST http://localhost:8000/v1/specs \
  -H "Content-Type: application/json" \
  -d '{
    "candidates": [
      {"content": "# Payment API\n## Auth\n- OAuth 2.0..."},
      {"content": "{\"openapi\":\"3.0\"}"},
      {"content": "title: Payment SRS\nrequirements:\n  - Process cards"},
      {"content": "# Architecture\nEvent-driven CQRS..."},
      {"content": "The payment system shall handle..."}
    ]
  }'
```

### Local RL Quickstart (specs → feedback → train → status)

Use this loop to make RL training stable in local/dev:

```bash
# 0) Start API
make serve

# 1) Select a spec (hybrid mode)
RESP=$(curl -s -X POST http://localhost:8000/v1/specs \
  -H "Content-Type: application/json" \
  -d '{
    "selection_method": "hybrid",
    "candidates": [
      {"content": "Spec A ..."},
      {"content": "Spec B ..."}
    ]
  }')

echo "$RESP"
REQ_ID=$(echo "$RESP" | python -c 'import sys,json; print(json.load(sys.stdin)["request_id"])')
echo "request_id=$REQ_ID"

# 2) Submit feedback (creates reward signal)
curl -s -X POST http://localhost:8000/v1/specs/feedback \
  -H "Content-Type: application/json" \
  -d "{\"request_id\":\"$REQ_ID\",\"rating\":5,\"comment\":\"Worked well\"}"

# 3) Train policy
curl -s -X POST http://localhost:8000/v1/policy/train \
  -H "Content-Type: application/json" \
  -d '{"n_steps": 128}'

# 4) Check status
curl -s http://localhost:8000/v1/policy/status
```

Notes:

- Training can start once there is at least one replay sample.
- Each transition stores **per-candidate composite scores**, so the PPO policy receives action-dependent rewards during training.
- For meaningful RL generalisation, accumulate 10–20+ diverse transitions before relying on `rl_only` selection.

### Automated Data Loop

For faster bootstrapping, use the built-in replay-buffer builder. It runs 20 diverse
evaluation → feedback → train cycles across varied domains (payments, CIAM, K8s,
ML pipelines, CI/CD, caching, DR, and more):

```bash
# Full 20-round run (trains every 5 evals, 256 PPO steps per train)
python scripts/build_replay_buffer.py

# Quick test (2 rounds)
python scripts/build_replay_buffer.py --rounds 2 --train-every 2 --n-steps 128

# Custom settings
python scripts/build_replay_buffer.py --rounds 10 --train-every 3 --n-steps 512
```

Each scenario has 5 candidates of intentionally varied quality so per-candidate
rewards are spread (e.g. 1.7 → 1.2 → 1.1 → 1.0 → 1.0), giving PPO a meaningful
gradient to learn from. Expect ~50 s per round (multi-judge LLM scoring).

### Compare `scoring_only` vs `rl_only`

Use the same candidates to compare deterministic rubric ranking vs policy-only selection:

```bash
PAYLOAD='{
  "candidates": [
    {"content": "Spec A ..."},
    {"content": "Spec B ..."}
  ]
}'

echo "== scoring_only =="
curl -s -X POST http://localhost:8000/v1/specs \
  -H "Content-Type: application/json" \
  -d "$(echo "$PAYLOAD" | python -c 'import sys,json; d=json.load(sys.stdin); d["selection_method"]="scoring_only"; print(json.dumps(d))')"

echo
echo "== rl_only =="
curl -s -X POST http://localhost:8000/v1/specs \
  -H "Content-Type: application/json" \
  -d "$(echo "$PAYLOAD" | python -c 'import sys,json; d=json.load(sys.stdin); d["selection_method"]="rl_only"; print(json.dumps(d))')"
```

Tips:

- `scoring_only` is usually more stable when the replay buffer is still small.
- `rl_only` becomes meaningful after repeated `specs → feedback → train` cycles.

### Common API Errors

#### 422 Unprocessable Entity (`json_invalid` / `JSON decode error`)

This error means the request body is not valid JSON (it is rejected before business validation).

Most common causes:

- Unescaped quotes inside `content` strings (for example embedding JSON directly)
- Trailing commas
- Comments inside JSON

Postman-safe request body example:

```json
{
  "candidates": [
    {
      "content": "## Payment API\n## Auth\nOAuth 2.0 with JWT"
    },
    {
      "content": "{\"openapi\":\"3.0.3\",\"info\":{\"title\":\"Payments\"}}"
    },
    {
      "content": "title: Payment SRS\nrequirements:\n  - Process card payments"
    }
  ],
  "selection_method": "scoring_only"
}
```

Notes:

- `/v1/specs` requires at least 2 candidates.
- In Postman, use **Body → raw → JSON** and click **Beautify** before sending.

## Enterprise Scoring Dimensions

| # | Dimension | Description |
|---|-----------|-------------|
| 1 | Compliance & Regulatory | GDPR, PCI DSS, SOC 2, HIPAA readiness |
| 2 | Security Posture | Defense-in-depth, zero-trust, threat modeling |
| 3 | Scalability & Performance | Horizontal scaling, load patterns, SLOs |
| 4 | Observability & Monitoring | Structured logging, distributed tracing, alerts |
| 5 | Data Governance | Classification, lineage, retention, encryption |
| 6 | Integration & Interop | API contracts, event schemas, backward compat |
| 7 | Testing & Quality | Coverage strategy, contract tests, chaos |
| 8 | Developer Experience | Onboarding, documentation, local dev |
| 9 | Cost & Resource Efficiency | TCO modeling, right-sizing, FinOps |
| 10 | Operational Resilience | Circuit breakers, retry, graceful degradation |
| 11 | DR & Business Continuity | RTO/RPO, multi-region, failover procedures |
| 12 | Vendor Independence | Abstraction layers, multi-cloud portability |

## Development

```bash
make test           # Run tests
make lint           # Run ruff linter
make format         # Format code
make typecheck      # Run mypy + pyright
make test-cov       # Run tests with coverage
make serve          # Start dev server with auto-reload
make serve-prod     # Start production server
```

### Integration Tests (PostgreSQL)

```bash
make docker-up  # starts postgres
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/reinforce_spec_test \
  make test
```

## Deploy on AWS (ECS Fargate)

This repository includes an AWS deployment scaffold for production-style ECS Fargate:

- CloudFormation stack: `infra/aws/ecs-fargate/stack.yaml`
- Deployment script: `scripts/aws/deploy_ecs_fargate.sh`
- Runbook: `infra/aws/ecs-fargate/README.md`

The stack provisions:

- Internet-facing ALB with HTTPS
- ECS Fargate service
- EFS mount at `/app/data` for policy state
- RDS PostgreSQL for persistence
- Secrets Manager injection for `OPENROUTER_API_KEY`
- CPU target-tracking autoscaling

Quick start:

```bash
chmod +x scripts/aws/deploy_ecs_fargate.sh

scripts/aws/deploy_ecs_fargate.sh \
  --region us-east-1 \
  --vpc-id vpc-xxxxxxxx \
  --public-subnets subnet-public-a,subnet-public-b \
  --private-subnets subnet-private-a,subnet-private-b \
  --certificate-arn arn:aws:acm:us-east-1:123456789012:certificate/xxxx \
  --openrouter-secret-arn arn:aws:secretsmanager:us-east-1:123456789012:secret:reinforce-spec/openrouter-xxxx
```

Optional custom domain:

```bash
scripts/aws/deploy_ecs_fargate.sh \
  --region us-east-1 \
  --vpc-id vpc-xxxxxxxx \
  --public-subnets subnet-public-a,subnet-public-b \
  --private-subnets subnet-private-a,subnet-private-b \
  --certificate-arn arn:aws:acm:us-east-1:123456789012:certificate/xxxx \
  --openrouter-secret-arn arn:aws:secretsmanager:us-east-1:123456789012:secret:reinforce-spec/openrouter-xxxx \
  --hosted-zone-id Z1234567890ABCDE \
  --api-domain api.example.com
```

After deployment, smoke check:

```bash
curl -sSf https://<alb-dns>/v1/health
curl -sSf https://<alb-dns>/v1/health/ready
```

If you deploy with `--hosted-zone-id` and `--api-domain`, the stack also outputs
`CustomDomainUrl` and creates a Route 53 alias A-record to the ALB.

## Project Structure

```
reinforce_spec/
├── __init__.py              # Public API with lazy imports
├── client.py                # ReinforceSpec orchestrator (select, feedback, train)
├── types.py                 # Pydantic models and enums
├── version.py               # Version string
├── _exceptions.py           # Exception hierarchy
├── _compat.py               # Optional dependency detection (SB3, etc.)
├── _internal/               # Private implementation
│   ├── _config.py           # Pydantic settings
│   ├── _client.py           # OpenRouter client + circuit breaker
│   ├── _scorer.py           # Multi-judge scoring engine
│   ├── _rubric.py           # 12-dimension rubric definitions
│   ├── _calibration.py      # Score calibration
│   ├── _bias.py             # Bias detection & mitigation
│   ├── _environment.py      # Gym env with replay mode (action-dependent rewards)
│   ├── _replay_buffer.py    # PER buffer + Transition (per-candidate rewards)
│   ├── _policy.py           # PPO policy + manager (train_on_batch with env replay)
│   ├── _ope.py              # Off-policy evaluation
│   ├── _selector.py         # Hybrid RL + scoring selector
│   ├── _drift.py            # Distribution drift detection
│   ├── _persistence.py      # PostgreSQL async storage
│   ├── _metrics.py          # Prometheus metrics
│   ├── _logging.py          # Structured logging config
│   └── _utils.py            # Utility functions
├── scoring/                 # Public scoring interface
│   ├── rubric.py, presets.py, judge.py, calibration.py
├── rl/                      # Public RL interface
│   ├── environment.py, evaluation.py, registry.py, selector.py, trainer.py
├── observability/           # Audit, experiment tracking, metrics export
│   ├── audit.py, experiment.py, metrics.py
└── server/                  # FastAPI server
    ├── app.py               # App factory + exception handlers
    ├── routes/              # specs.py, policy.py, health.py
    └── middleware/          # Request logging, backpressure

scripts/
├── build_replay_buffer.py   # Automated RL data loop (20 diverse scenarios)
├── seed_calibration_set.py  # Calibration seed data

examples/
├── basic_selection.py       # SDK usage (select + feedback)
├── scoring_only.py          # Direct scoring without RL
├── api_client.py            # HTTP API client example

data/
└── policies/                # PPO checkpoint storage
```

## License

MIT