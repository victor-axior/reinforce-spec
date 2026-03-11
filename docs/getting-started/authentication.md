# Authentication

ReinforceSpec supports multiple authentication methods depending on your deployment model.

---

## Overview

| Method | Use Case | Security Level |
|--------|----------|----------------|
| **API Key** | Server-to-server | High |
| **OpenRouter API Key** | LLM provider access | Required |
| **No Auth** | Local development | Development only |

---

## OpenRouter API Key (Required)

ReinforceSpec uses [OpenRouter](https://openrouter.ai) to access multiple LLM providers (Claude, GPT-4, Gemini) for multi-judge evaluation.

### Get Your Key

1. Sign up at [openrouter.ai](https://openrouter.ai)
2. Navigate to **API Keys** in your dashboard
3. Create a new key with appropriate rate limits

### Configure the Key

=== "Environment Variable"

    ```bash
    export OPENROUTER_API_KEY="sk-or-v1-your-key-here"
    ```

=== ".env File"

    ```bash title=".env"
    OPENROUTER_API_KEY=sk-or-v1-your-key-here
    ```

=== "Python Code"

    ```python
    from reinforce_spec_sdk import ReinforceSpec
    
    # Explicitly pass the key
    rs = ReinforceSpecClient(openrouter_api_key="sk-or-v1-...")
    ```

!!! warning "Never commit API keys"
    Add `.env` to your `.gitignore` and use secrets management in production.

---

## ReinforceSpec API Key

When running your own ReinforceSpec server, you can require API key authentication for incoming requests.

### Server Configuration

```bash title=".env"
# Require API key authentication
RS_API_KEY=your-reinforce-spec-api-key

# Leave empty to disable auth (development only)
# RS_API_KEY=
```

### Client Usage

=== "Python SDK"

    ```python
    from reinforce_spec_sdk import ReinforceSpec
    
    rs = ReinforceSpecClient(
        base_url="https://your-server.com",
        api_key="your-reinforce-spec-api-key",
    )
    ```

=== "curl"

    ```bash
    curl -X POST https://your-server.com/v1/specs \
      -H "Authorization: Bearer your-reinforce-spec-api-key" \
      -H "Content-Type: application/json" \
      -d '{"candidates": [...]}'
    ```

=== "httpx"

    ```python
    import httpx
    
    client = httpx.AsyncClient(
        base_url="https://your-server.com",
        headers={"Authorization": "Bearer your-api-key"},
    )
    ```

### Authentication Header Format

```http
Authorization: Bearer <your-api-key>
```

---

## API Key Best Practices

### Rotation

Rotate API keys regularly:

```bash
# Generate a new key
openssl rand -base64 32

# Update your deployment with zero downtime:
# 1. Add new key to allowed list
# 2. Update clients to use new key
# 3. Remove old key from allowed list
```

### Scoping

Create separate keys for different environments:

| Key Name | Environment | Permissions |
|----------|-------------|------------|
| `rs-prod-api` | Production | Full access |
| `rs-staging-api` | Staging | Full access |
| `rs-readonly` | Monitoring | Read-only |

### Storage

=== "AWS Secrets Manager"

    ```bash
    aws secretsmanager create-secret \
      --name reinforce-spec/api-key \
      --secret-string "your-api-key"
    ```

=== "HashiCorp Vault"

    ```bash
    vault kv put secret/reinforce-spec api_key="your-api-key"
    ```

=== "Kubernetes Secrets"

    ```yaml
    apiVersion: v1
    kind: Secret
    metadata:
      name: reinforce-spec
    type: Opaque
    stringData:
      api-key: "your-api-key"
    ```

---

## Error Responses

### Missing Authentication

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
  "error": "unauthorized",
  "message": "Missing or invalid Authorization header"
}
```

### Invalid Key

```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{
  "error": "forbidden",
  "message": "Invalid API key"
}
```

---

## Development Mode

For local development, you can disable authentication:

```bash title=".env"
# Leave RS_API_KEY empty or unset
RS_API_KEY=
```

!!! danger "Never disable auth in production"
    Always require API key authentication for production deployments.

---

## OAuth 2.0 / JWT (Enterprise)

For enterprise deployments requiring OAuth 2.0 or JWT validation, contact us for custom integration options.

---

## Next Steps

- [Run the Quickstart](quickstart.md)
- [View API Reference](../api-reference/index.md)
- [Production Best Practices](../guides/best-practices.md)
