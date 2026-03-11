# Scoring Dimensions

ReinforceSpec evaluates specifications across 12 enterprise-grade dimensions. Each dimension is scored from 0.0 to 1.0 by a multi-judge LLM ensemble.

---

## Dimension Overview

| Dimension | Weight | Description |
|-----------|--------|-------------|
| [Security](#security) | 15% | Authentication, authorization, encryption |
| [Compliance](#compliance) | 12% | Regulatory and standard adherence |
| [Scalability](#scalability) | 10% | Growth and load handling |
| [Maintainability](#maintainability) | 10% | Code quality and modularity |
| [Testability](#testability) | 8% | Test coverage and automation |
| [Observability](#observability) | 8% | Monitoring and debugging |
| [Reliability](#reliability) | 10% | Fault tolerance and recovery |
| [Performance](#performance) | 8% | Speed and efficiency |
| [Cost Efficiency](#cost-efficiency) | 5% | Resource optimization |
| [Interoperability](#interoperability) | 6% | Integration capabilities |
| [Documentation](#documentation) | 4% | Clarity and completeness |
| [Risk Mitigation](#risk-mitigation) | 4% | Risk identification and handling |

---

## Dimension Details

### Security {#security}

**Weight: 15%** | Highest priority dimension

Evaluates protection against threats and secure data handling.

| Sub-criterion | What's Evaluated |
|---------------|------------------|
| Authentication | OAuth 2.0, OIDC, MFA, API keys |
| Authorization | RBAC, ABAC, least privilege |
| Encryption | TLS 1.3, AES-256, key management |
| Input validation | Injection prevention, sanitization |
| Secret management | Vault integration, rotation |

**Score Interpretation:**

| Score | Meaning |
|-------|---------|
| 0.9+ | Enterprise-grade security (OAuth2+PKCE, mTLS, HSM) |
| 0.7-0.9 | Production-ready (OAuth2, TLS 1.3, RBAC) |
| 0.5-0.7 | Basic security (API keys, HTTPS) |
| <0.5 | Security gaps (hardcoded creds, no encryption) |

---

### Compliance {#compliance}

**Weight: 12%**

Evaluates adherence to regulations and industry standards.

| Sub-criterion | What's Evaluated |
|---------------|------------------|
| Data protection | GDPR, CCPA, data residency |
| Industry standards | PCI-DSS, HIPAA, SOC 2 |
| Audit trails | Logging, immutability, retention |
| Privacy | Data minimization, consent |
| Accessibility | WCAG, ADA compliance |

**Score Interpretation:**

| Score | Meaning |
|-------|---------|
| 0.9+ | Multi-regulation compliant (PCI-DSS L1, HIPAA, SOC2) |
| 0.7-0.9 | Major compliance covered (GDPR, audit trails) |
| 0.5-0.7 | Basic compliance awareness |
| <0.5 | Compliance gaps |

---

### Scalability {#scalability}

**Weight: 10%**

Evaluates ability to handle growth and varying loads.

| Sub-criterion | What's Evaluated |
|---------------|------------------|
| Horizontal scaling | Stateless design, auto-scaling |
| Data partitioning | Sharding, replication strategy |
| Caching | CDN, Redis, cache invalidation |
| Async processing | Message queues, event-driven |
| Resource limits | Rate limiting, backpressure |

**Score Interpretation:**

| Score | Meaning |
|-------|---------|
| 0.9+ | Hyper-scale ready (auto-scaling, sharding, CQRS) |
| 0.7-0.9 | Cloud-native scaling (K8s, horizontal pods) |
| 0.5-0.7 | Basic scaling (vertical, simple caching) |
| <0.5 | Scaling limitations (stateful, monolithic) |

---

### Maintainability {#maintainability}

**Weight: 10%**

Evaluates long-term code health and change management.

| Sub-criterion | What's Evaluated |
|---------------|------------------|
| Modularity | Separation of concerns, DRY |
| Code organization | Clean architecture, layering |
| Dependency management | Version pinning, updates |
| Configuration | Environment-based, feature flags |
| Technical debt | Deprecation plans, refactoring |

---

### Testability {#testability}

**Weight: 8%**

Evaluates ability to verify correctness through testing.

| Sub-criterion | What's Evaluated |
|---------------|------------------|
| Unit testing | Isolation, mocking strategies |
| Integration testing | API contracts, E2E flows |
| Test automation | CI/CD integration, coverage |
| Test data | Fixtures, factories, seeding |
| Contract testing | Consumer-driven contracts |

---

### Observability {#observability}

**Weight: 8%**

Evaluates visibility into system behavior.

| Sub-criterion | What's Evaluated |
|---------------|------------------|
| Logging | Structured logs, correlation IDs |
| Metrics | Prometheus, custom metrics |
| Tracing | OpenTelemetry, distributed tracing |
| Alerting | Threshold alerts, anomaly detection |
| Dashboards | Grafana, real-time visibility |

---

### Reliability {#reliability}

**Weight: 10%**

Evaluates system resilience and fault tolerance.

| Sub-criterion | What's Evaluated |
|---------------|------------------|
| Fault tolerance | Circuit breakers, bulkheads |
| Redundancy | Multi-AZ, failover |
| Recovery | Backup strategies, RTO/RPO |
| Graceful degradation | Fallbacks, partial availability |
| Chaos engineering | Failure injection, game days |

---

### Performance {#performance}

**Weight: 8%**

Evaluates speed and efficiency.

| Sub-criterion | What's Evaluated |
|---------------|------------------|
| Latency | P50/P95/P99 targets |
| Throughput | Requests/second capacity |
| Resource efficiency | CPU, memory optimization |
| Database performance | Query optimization, indexing |
| Network efficiency | Payload size, compression |

---

### Cost Efficiency {#cost-efficiency}

**Weight: 5%**

Evaluates resource optimization and cost management.

| Sub-criterion | What's Evaluated |
|---------------|------------------|
| Resource sizing | Right-sizing, spot instances |
| Usage optimization | Reserved capacity, savings plans |
| Waste reduction | Idle resource cleanup |
| Cost allocation | Tagging, chargebacks |
| FinOps practices | Budget alerts, forecasting |

---

### Interoperability {#interoperability}

**Weight: 6%**

Evaluates integration capabilities.

| Sub-criterion | What's Evaluated |
|---------------|------------------|
| API design | REST/GraphQL best practices |
| Standards compliance | OpenAPI, JSON:API |
| Extensibility | Webhooks, plugins |
| Data formats | JSON, Protocol Buffers |
| Version compatibility | Backward compatibility |

---

### Documentation {#documentation}

**Weight: 4%**

Evaluates clarity and completeness of documentation.

| Sub-criterion | What's Evaluated |
|---------------|------------------|
| API documentation | OpenAPI, examples |
| Architecture docs | Diagrams, decision records |
| Runbooks | Operational procedures |
| Onboarding | Getting started guides |
| Change documentation | Changelogs, migration guides |

---

### Risk Mitigation {#risk-mitigation}

**Weight: 4%**

Evaluates risk identification and handling.

| Sub-criterion | What's Evaluated |
|---------------|------------------|
| Risk identification | Threat modeling |
| Mitigation strategies | Controls, safeguards |
| Contingency planning | Fallback options |
| Dependency risks | Vendor lock-in, alternatives |
| Change risk | Rollback procedures |

---

## Composite Score Calculation

The composite score is a weighted average:

```python
composite_score = sum(
    dimension_score * dimension_weight
    for dimension_score, dimension_weight 
    in zip(scores, weights)
)
```

**Example:**

| Dimension | Score | Weight | Contribution |
|-----------|-------|--------|--------------|
| Security | 0.95 | 0.15 | 0.1425 |
| Compliance | 0.92 | 0.12 | 0.1104 |
| Scalability | 0.78 | 0.10 | 0.0780 |
| ... | ... | ... | ... |
| **Total** | | **1.00** | **0.847** |

---

## Customizing Weights

Adjust dimension weights based on your use case:

```python
from reinforce_spec_sdk import ReinforceSpecClient

client = ReinforceSpecClient(
    dimension_weights={
        "security": 0.25,      # Increase for security-critical
        "compliance": 0.20,    # Increase for regulated industries
        "performance": 0.15,   # Increase for latency-sensitive
        # Other dimensions get remaining weight
    }
)
```

### Weight Presets

| Preset | Focus | Use Case |
|--------|-------|----------|
| `enterprise` | Security + Compliance | Financial services, healthcare |
| `startup` | Performance + Cost | Early-stage products |
| `platform` | Scalability + Interoperability | API platforms |
| `regulated` | Compliance + Documentation | Government, banking |

```python
client = ReinforceSpecClient(weight_preset="enterprise")
```

---

## Score Calibration

Scores are calibrated against a reference set of 500+ real-world specifications:

- **0.9+** = Top 5% of specs in the calibration set
- **0.7-0.9** = Above average (top 25%)
- **0.5-0.7** = Average
- **<0.5** = Below average

---

## Related

- [Multi-Judge Ensemble](multi-judge.md) — How dimensions are scored
- [Selection Methods](selection-methods.md) — How scores drive selection
- [API Reference](../api-reference/specs.md) — Using dimension scores
