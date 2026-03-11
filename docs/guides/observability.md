# Observability Guide

Set up comprehensive monitoring, logging, and alerting for ReinforceSpec.

---

## Overview

A well-instrumented ReinforceSpec deployment tracks:

- **Metrics**: Request rates, latencies, error rates, policy performance
- **Logs**: Structured application logs with correlation
- **Traces**: Distributed tracing across services
- **Alerts**: Proactive notification of issues

---

## Metrics

### Key Metrics to Track

| Metric | Type | Description |
|--------|------|-------------|
| `reinforce_spec_requests_total` | Counter | Total API requests |
| `reinforce_spec_request_duration_seconds` | Histogram | Request latency |
| `reinforce_spec_errors_total` | Counter | Error count by type |
| `reinforce_spec_selection_score` | Histogram | Selected spec scores |
| `reinforce_spec_policy_accuracy` | Gauge | Current policy accuracy |
| `reinforce_spec_feedback_total` | Counter | Feedback submissions |
| `reinforce_spec_replay_buffer_size` | Gauge | RL training buffer |

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'reinforce-spec'
    static_configs:
      - targets: ['reinforce-spec:8000']
    metrics_path: '/metrics'
```

### Custom Metrics in Code

```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
REQUESTS = Counter(
    'reinforce_spec_client_requests_total',
    'Total requests made',
    ['endpoint', 'status']
)

LATENCY = Histogram(
    'reinforce_spec_client_latency_seconds',
    'Request latency',
    ['endpoint'],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30]
)

SCORE = Histogram(
    'reinforce_spec_selection_score',
    'Selected spec composite score',
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# Instrument calls
async def evaluate_with_metrics(candidates):
    start = time.time()
    
    try:
        result = await client.select(candidates=candidates)
        REQUESTS.labels(endpoint='specs', status='success').inc()
        SCORE.observe(result.selected.composite_score)
        return result
    except ReinforceSpecError as e:
        REQUESTS.labels(endpoint='specs', status='error').inc()
        raise
    finally:
        LATENCY.labels(endpoint='specs').observe(time.time() - start)
```

---

## Grafana Dashboards

### Overview Dashboard

```json
{
  "title": "ReinforceSpec Overview",
  "panels": [
    {
      "title": "Request Rate",
      "type": "graph",
      "targets": [
        {
          "expr": "rate(reinforce_spec_requests_total[5m])",
          "legendFormat": "{{status}}"
        }
      ]
    },
    {
      "title": "P95 Latency",
      "type": "graph",
      "targets": [
        {
          "expr": "histogram_quantile(0.95, rate(reinforce_spec_request_duration_seconds_bucket[5m]))",
          "legendFormat": "P95"
        }
      ]
    },
    {
      "title": "Error Rate",
      "type": "graph",
      "targets": [
        {
          "expr": "rate(reinforce_spec_errors_total[5m]) / rate(reinforce_spec_requests_total[5m])",
          "legendFormat": "Error %"
        }
      ]
    },
    {
      "title": "Selection Score Distribution",
      "type": "heatmap",
      "targets": [
        {
          "expr": "rate(reinforce_spec_selection_score_bucket[5m])"
        }
      ]
    }
  ]
}
```

### Policy Performance Dashboard

```json
{
  "title": "Policy Performance",
  "panels": [
    {
      "title": "Selection Accuracy",
      "type": "stat",
      "targets": [
        {
          "expr": "reinforce_spec_policy_accuracy"
        }
      ],
      "thresholds": [
        {"value": 0.7, "color": "red"},
        {"value": 0.8, "color": "yellow"},
        {"value": 0.9, "color": "green"}
      ]
    },
    {
      "title": "Feedback Rate",
      "type": "stat",
      "targets": [
        {
          "expr": "rate(reinforce_spec_feedback_total[24h]) / rate(reinforce_spec_requests_total[24h])"
        }
      ]
    },
    {
      "title": "Replay Buffer Size",
      "type": "gauge",
      "targets": [
        {
          "expr": "reinforce_spec_replay_buffer_size"
        }
      ],
      "max": 5000
    }
  ]
}
```

---

## Logging

### Structured Logging Setup

```python
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()
```

### Log Correlation

```python
import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar('request_id', default='')

async def evaluate_with_correlation(candidates):
    request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    
    logger.info(
        "evaluation_started",
        request_id=request_id,
        candidates_count=len(candidates),
    )
    
    try:
        result = await client.select(
            candidates=candidates,
            request_id=request_id,
        )
        
        logger.info(
            "evaluation_completed",
            request_id=request_id,
            rs_request_id=result.request_id,
            selected_index=result.selected.index,
            composite_score=result.selected.composite_score,
            latency_ms=result.latency_ms,
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "evaluation_failed",
            request_id=request_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise
```

### Log Aggregation (ELK Stack)

```yaml
# filebeat.yml
filebeat.inputs:
  - type: container
    paths:
      - '/var/lib/docker/containers/*/*.log'
    processors:
      - add_docker_metadata: ~
      - decode_json_fields:
          fields: ["message"]
          target: ""
          overwrite_keys: true

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  index: "reinforce-spec-%{+yyyy.MM.dd}"
```

---

## Distributed Tracing

### OpenTelemetry Setup

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentation

# Configure tracing
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(endpoint="otel-collector:4317")
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(otlp_exporter)
)

# Auto-instrument HTTP client
HTTPXClientInstrumentation().instrument()
```

### Manual Instrumentation

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def evaluate_with_tracing(candidates):
    with tracer.start_as_current_span("evaluate_specs") as span:
        span.set_attribute("candidates.count", len(candidates))
        
        result = await client.select(candidates=candidates)
        
        span.set_attribute("selected.index", result.selected.index)
        span.set_attribute("selected.score", result.selected.composite_score)
        span.set_attribute("latency_ms", result.latency_ms)
        
        return result
```

### Jaeger Configuration

```yaml
# docker-compose.yml
services:
  jaeger:
    image: jaegertracing/all-in-one:1.51
    ports:
      - "16686:16686"  # UI
      - "4317:4317"    # OTLP gRPC
    environment:
      - COLLECTOR_OTLP_ENABLED=true
```

---

## Alerting

### Prometheus Alerting Rules

```yaml
# alerts.yml
groups:
  - name: reinforce-spec
    rules:
      - alert: HighErrorRate
        expr: |
          rate(reinforce_spec_errors_total[5m]) 
          / rate(reinforce_spec_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate in ReinforceSpec"
          description: "Error rate is {{ $value | humanizePercentage }}"
      
      - alert: HighLatency
        expr: |
          histogram_quantile(0.95, 
            rate(reinforce_spec_request_duration_seconds_bucket[5m])
          ) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency in ReinforceSpec"
          description: "P95 latency is {{ $value }}s"
      
      - alert: PolicyAccuracyDrop
        expr: reinforce_spec_policy_accuracy < 0.7
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Policy accuracy below threshold"
          description: "Current accuracy: {{ $value | humanizePercentage }}"
      
      - alert: LowFeedbackRate
        expr: |
          rate(reinforce_spec_feedback_total[24h]) 
          / rate(reinforce_spec_requests_total[24h]) < 0.1
        for: 1h
        labels:
          severity: info
        annotations:
          summary: "Low feedback rate"
          description: "Feedback rate is {{ $value | humanizePercentage }}"
```

### PagerDuty Integration

```yaml
# alertmanager.yml
receivers:
  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: 'your-pagerduty-key'
        severity: '{{ .Labels.severity }}'

route:
  receiver: 'pagerduty'
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty'
      continue: true
```

### Slack Notifications

```yaml
# alertmanager.yml
receivers:
  - name: 'slack'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/xxx'
        channel: '#reinforce-spec-alerts'
        title: '{{ .Status | toUpper }}: {{ .CommonAnnotations.summary }}'
        text: '{{ .CommonAnnotations.description }}'
```

---

## Health Monitoring

### Health Check Script

```python
import asyncio
import httpx

async def check_health():
    checks = {
        "api": "https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/v1/health",
        "ready": "https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com/v1/health/ready",
    }
    
    results = {}
    
    async with httpx.AsyncClient() as client:
        for name, url in checks.items():
            try:
                response = await client.get(url, timeout=10)
                results[name] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "latency_ms": response.elapsed.total_seconds() * 1000,
                }
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e),
                }
    
    return results

# Run check
health = asyncio.run(check_health())
print(health)
```

### Kubernetes Liveness

```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
    - name: app
      livenessProbe:
        httpGet:
          path: /v1/health
          port: 8000
        initialDelaySeconds: 10
        periodSeconds: 10
      readinessProbe:
        httpGet:
          path: /v1/health/ready
          port: 8000
        initialDelaySeconds: 20
        periodSeconds: 15
```

---

## CloudWatch (AWS)

### Custom Metrics

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

async def publish_metrics(result):
    cloudwatch.put_metric_data(
        Namespace='ReinforceSpec',
        MetricData=[
            {
                'MetricName': 'SelectionScore',
                'Value': result.selected.composite_score,
                'Unit': 'None',
            },
            {
                'MetricName': 'Latency',
                'Value': result.latency_ms,
                'Unit': 'Milliseconds',
            },
        ]
    )
```

### CloudWatch Alarms

```python
cloudwatch.put_metric_alarm(
    AlarmName='ReinforceSpec-HighLatency',
    MetricName='Latency',
    Namespace='ReinforceSpec',
    Statistic='Average',
    Period=300,
    EvaluationPeriods=2,
    Threshold=5000,
    ComparisonOperator='GreaterThanThreshold',
    AlarmActions=['arn:aws:sns:us-east-1:123456789:alerts'],
)
```

---

## Related

- [Health Check Endpoints](../api-reference/health.md) — API health checks
- [Best Practices](best-practices.md) — Production patterns
- [Error Handling](error-handling.md) — Error management
