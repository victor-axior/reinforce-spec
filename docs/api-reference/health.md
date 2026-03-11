# Health Check Endpoints

Endpoints for monitoring service health, suitable for load balancers and Kubernetes probes.

---

## GET /v1/health {#liveness}

Basic liveness probe. Returns 200 if the service is running.

### Endpoint

```http
GET /v1/health
```

### Authentication

None required (public endpoint).

### Request Example

```bash
curl -s https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/v1/health
```

### Response (200 OK)

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T12:00:00Z"
}
```

### Response (503 Service Unavailable)

```json
{
  "status": "unhealthy",
  "timestamp": "2024-01-15T12:00:00Z",
  "reason": "shutdown_in_progress"
}
```

---

## GET /v1/health/ready {#readiness}

Readiness probe. Returns 200 only if the service can handle requests.

Checks:
- Database connectivity
- LLM provider reachability  
- Policy model loaded

### Endpoint

```http
GET /v1/health/ready
```

### Authentication

None required (public endpoint).

### Request Example

```bash
curl -s https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/v1/health/ready
```

### Response (200 OK)

```json
{
  "status": "ready",
  "timestamp": "2024-01-15T12:00:00Z",
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 2
    },
    "llm_provider": {
      "status": "healthy",
      "provider": "openrouter",
      "latency_ms": 150
    },
    "policy_model": {
      "status": "healthy",
      "version": "v001",
      "loaded": true
    }
  }
}
```

### Response (503 Service Unavailable)

```json
{
  "status": "not_ready",
  "timestamp": "2024-01-15T12:00:00Z",
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 2
    },
    "llm_provider": {
      "status": "unhealthy",
      "error": "connection_timeout",
      "latency_ms": 5000
    },
    "policy_model": {
      "status": "healthy",
      "version": "v001",
      "loaded": true
    }
  }
}
```

---

## GET /v1/health/live {#kubernetes-liveness}

Kubernetes-style liveness probe. Minimal response for fast checks.

### Endpoint

```http
GET /v1/health/live
```

### Response (200 OK)

```
OK
```

Content-Type: `text/plain`

### Response (503)

```
UNHEALTHY
```

---

## Health Check Matrix

| Endpoint | Purpose | Auth | Checks |
|----------|---------|------|--------|
| `/v1/health` | Liveness | No | Process running |
| `/v1/health/ready` | Readiness | No | All dependencies |
| `/v1/health/live` | K8s liveness | No | Process running |

---

## Kubernetes Configuration

### Deployment Probes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: reinforce-spec
spec:
  template:
    spec:
      containers:
        - name: api
          image: reinforce-spec:latest
          ports:
            - containerPort: 8000
          livenessProbe:
            httpGet:
              path: /v1/health/live
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /v1/health/ready
              port: 8000
            initialDelaySeconds: 20
            periodSeconds: 15
            timeoutSeconds: 10
            failureThreshold: 2
          startupProbe:
            httpGet:
              path: /v1/health/ready
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 10
            failureThreshold: 30
```

### Service Monitor (Prometheus)

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: reinforce-spec
spec:
  selector:
    matchLabels:
      app: reinforce-spec
  endpoints:
    - port: http
      path: /v1/health/ready
      interval: 30s
```

---

## AWS ECS Configuration

### Task Definition Health Check

```json
{
  "healthCheck": {
    "command": [
      "CMD-SHELL",
      "curl -f http://localhost:8000/v1/health/ready || exit 1"
    ],
    "interval": 30,
    "timeout": 10,
    "retries": 3,
    "startPeriod": 60
  }
}
```

### ALB Target Group Health Check

```json
{
  "HealthCheckPath": "/v1/health",
  "HealthCheckIntervalSeconds": 30,
  "HealthCheckTimeoutSeconds": 5,
  "HealthyThresholdCount": 2,
  "UnhealthyThresholdCount": 3,
  "Matcher": {
    "HttpCode": "200"
  }
}
```

---

## Docker Compose

```yaml
services:
  api:
    image: reinforce-spec:latest
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/v1/health/ready"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

---

## Monitoring Integration

### Uptime Monitoring Script

```python
import httpx
import asyncio

async def check_health():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/v1/health/ready",
                timeout=10.0,
            )
            data = response.json()
            
            if response.status_code == 200:
                print(f"✓ Healthy - DB: {data['checks']['database']['latency_ms']}ms")
            else:
                failed = [k for k, v in data['checks'].items() 
                         if v['status'] != 'healthy']
                print(f"✗ Unhealthy - Failed: {', '.join(failed)}")
                
        except httpx.TimeoutException:
            print("✗ Health check timeout")
        except Exception as e:
            print(f"✗ Health check failed: {e}")

asyncio.run(check_health())
```

### Prometheus Metrics

The `/v1/health/ready` endpoint also exposes Prometheus metrics at `/metrics`:

```promql
# Service availability
up{job="reinforce-spec"}

# Database latency
reinforce_spec_db_latency_seconds

# LLM provider latency
reinforce_spec_llm_latency_seconds

# Health check duration
reinforce_spec_health_check_duration_seconds
```

---

## Troubleshooting

### Common Issues

| Symptom | Check | Solution |
|---------|-------|----------|
| `/health` returns 503 | Process crashed | Check logs, restart |
| `/health/ready` returns 503 | Dependency down | Check DB/LLM connectivity |
| High latency on `/health/ready` | Slow dependency | Check network, increase timeouts |
| Intermittent failures | Resource exhaustion | Scale up, check memory |

### Debug Mode

Enable verbose health checks with env var:

```bash
export RS_HEALTH_VERBOSE=true
```

Returns additional diagnostics:

```json
{
  "status": "ready",
  "checks": {...},
  "diagnostics": {
    "memory_mb": 245,
    "cpu_percent": 12.5,
    "open_connections": 15,
    "request_queue_depth": 0
  }
}
```

---

## Related

- [Observability Guide](../guides/observability.md) — Full monitoring setup
- [Deployment](../getting-started/installation.md#docker) — Container configuration
- [Error Codes](errors.md) — Service error reference
