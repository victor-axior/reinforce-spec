# Installation

Multiple ways to install and deploy ReinforceSpec depending on your use case.

---

## Python SDK

The recommended way to use ReinforceSpec is via the Python SDK.

### Requirements

| Requirement | Minimum Version |
|-------------|-----------------|
| Python | 3.9+ |
| OS | Linux, macOS, Windows |

### Install from PyPI

=== "pip"

    ```bash
    pip install reinforce-spec-sdk
    ```

=== "uv (recommended)"

    ```bash
    uv add reinforce-spec-sdk
    ```

=== "poetry"

    ```bash
    poetry add reinforce-spec-sdk
    ```

### Verify Installation

```python
import reinforce_spec_sdk
print(reinforce_spec_sdk.__version__)
# Output: 1.0.0
```

---

## Docker

Run the ReinforceSpec API server as a Docker container.

### Quick Start

```bash
docker run -d \
  -p 8000:8000 \
  -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
  ghcr.io/reinforce-spec/reinforce-spec:latest
```

### Docker Compose

```yaml title="docker-compose.yml"
services:
  api:
    image: ghcr.io/reinforce-spec/reinforce-spec:latest
    ports:
      - "8000:8000"
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - RS_DATABASE_URL=postgresql://postgres:postgres@postgres:5432/reinforce_spec
    depends_on:
      postgres:
        condition: service_healthy

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=reinforce_spec
      - POSTGRES_PASSWORD=postgres
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s

volumes:
  postgres-data:
```

```bash
docker-compose up -d
```

### Build from Source

```bash
git clone https://github.com/reinforce-spec/reinforce-spec.git
cd reinforce-spec
docker build -t reinforce-spec .
```

---

## Self-Hosted Server

Run the ReinforceSpec API server directly without Docker.

### Install Dependencies

```bash
git clone https://github.com/reinforce-spec/reinforce-spec.git
cd reinforce-spec
uv sync --all-extras
```

### Configure Environment

```bash title=".env"
# Required
OPENROUTER_API_KEY=sk-or-v1-your-key

# Database (PostgreSQL recommended for production)
RS_DATABASE_URL=postgresql://user:pass@localhost:5432/reinforce_spec

# Server settings
RS_HOST=0.0.0.0
RS_PORT=8000
RS_WORKERS=4
RS_LOG_LEVEL=info
```

### Run the Server

=== "Development"

    ```bash
    uv run reinforce-spec-server --reload
    ```

=== "Production"

    ```bash
    uv run reinforce-spec-server --workers 4 --host 0.0.0.0
    ```

=== "With Gunicorn"

    ```bash
    gunicorn reinforce_spec.server.app:create_app \
      --worker-class uvicorn.workers.UvicornWorker \
      --workers 4 \
      --bind 0.0.0.0:8000
    ```

---

## Cloud Deployments

### AWS ECS Fargate

We provide a complete CloudFormation template for AWS deployment:

```bash
./scripts/aws/deploy_ecs_fargate.sh \
  --vpc-id vpc-xxxxx \
  --public-subnets subnet-a,subnet-b \
  --private-subnets subnet-c,subnet-d \
  --certificate-arn arn:aws:acm:... \
  --openrouter-secret-arn arn:aws:secretsmanager:...
```

See [infra/aws/ecs-fargate](https://github.com/reinforce-spec/reinforce-spec/tree/main/infra/aws/ecs-fargate) for detailed deployment configuration.

### Kubernetes / Helm

```bash
helm repo add reinforce-spec https://charts.reinforce-spec.dev
helm install reinforce-spec reinforce-spec/reinforce-spec \
  --set secrets.openrouterApiKey=$OPENROUTER_API_KEY
```

---

## REST API Only

If you don't need the Python SDK, you can use the REST API directly:

```bash
# No installation required - just call the API
curl -X POST https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/v1/specs \
  -H "Authorization: Bearer $RS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"candidates": [...]}'
```

See the [API Reference](../api-reference/index.md) for complete documentation.

---

## Version Compatibility

| ReinforceSpec | Python | PostgreSQL | Redis |
|---------------|--------|------------|-------|
| 0.1.x | 3.11+ | 14+ | 6+ |
| 0.2.x (planned) | 3.11+ | 14+ | 6+ |

---

## Next Steps

After installation:

1. [Set up authentication](authentication.md)
2. [Run the quickstart](quickstart.md)
3. [Explore the API](../api-reference/index.md)
