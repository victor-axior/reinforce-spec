#!/usr/bin/env python3
"""Automated RL data loop: build diverse replay-buffer transitions.

Runs 20 evaluation → feedback → train cycles against the live server
with varied spec content across different domains, formats, and quality
levels.  After each batch of evaluations, triggers a PPO training pass.

Usage:
    # With server running on localhost:8000
    python scripts/build_replay_buffer.py

    # Custom base URL and batch size
    python scripts/build_replay_buffer.py --base-url http://localhost:8000/v1 --rounds 30
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
import time

import httpx

# ── Diverse spec scenarios ────────────────────────────────────────────────────
# Each scenario has 5 candidates of intentionally different quality so candidate
# rewards are spread, giving PPO a meaningful gradient to learn from.

SCENARIOS: list[dict] = [
    # ── 1. Payment Processing ─────────────────────────────────────────────
    {
        "description": "Payment processing API for banking client",
        "selection_method": "hybrid",
        "candidates": [
            {
                "content": (
                    "# Payment API Specification\n\n"
                    "## Authentication\n"
                    "- OAuth 2.0 with mTLS\n"
                    "- API key rotation every 90 days\n\n"
                    "## Endpoints\n"
                    "- POST /v1/payments — Create payment\n"
                    "- GET /v1/payments/{id} — Get payment status\n"
                    "- POST /v1/payments/{id}/refund — Initiate refund\n\n"
                    "## Rate Limiting\n"
                    "- 1000 req/s per client, token-bucket\n\n"
                    "## Compliance\n"
                    "- PCI DSS Level 1 compliant\n"
                    "- SOC 2 Type II audit trail\n"
                    "- GDPR data residency controls\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": (
                    "# Payments Architecture\n\n"
                    "Event-driven microservices with CQRS.\n\n"
                    "## Components\n"
                    "- API Gateway (Kong)\n"
                    "- Payment Orchestrator\n"
                    "- Fraud Engine (ML-based)\n"
                    "- Settlement Service\n"
                    "- Notification Hub\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": '{"openapi":"3.0.3","info":{"title":"Payments","version":"1.0"},"paths":{"/payments":{"post":{"summary":"Create payment"}}}}',
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "title: Payment SRS\nversion: 2.0\nrequirements:\n"
                    "  - id: REQ-001\n    description: Process credit card transactions\n"
                    "  - id: REQ-002\n    description: Detect fraudulent transactions in real-time\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": "The payment system shall handle credit card transactions and settle batches daily.",
                "source_model": "gemini-flash",
            },
        ],
        "expected_best": 0,
        "rating": 4.5,
        "comment": "Excellent coverage of auth, rate limits and compliance",
    },
    # ── 2. CIAM Identity ──────────────────────────────────────────────────
    {
        "description": "CIAM platform specification for government SI",
        "selection_method": "hybrid",
        "candidates": [
            {
                "content": (
                    "# CIAM Platform Specification\n\n"
                    "## Identity Federation\n"
                    "- SAML 2.0 and OIDC support\n"
                    "- PIV/CAC smart card authentication\n"
                    "- FedRAMP High authorization\n\n"
                    "## Access Control\n"
                    "- ABAC with XACML policies\n"
                    "- Just-in-time provisioning\n"
                    "- Continuous authorization monitoring\n\n"
                    "## Compliance\n"
                    "- NIST 800-63 IAL2/AAL2\n"
                    "- FISMA High impact level\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": (
                    "openapi: '3.0.3'\ninfo:\n  title: CIAM API\n  version: '1.0'\n"
                    "paths:\n  /v1/identities:\n    post:\n      summary: Create identity\n"
                    "  /v1/sessions:\n    post:\n      summary: Authenticate\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": (
                    "The CIAM platform shall support multi-factor authentication, "
                    "identity proofing at IAL2, and federated SSO across agency "
                    "boundaries with full NIST 800-63 compliance."
                ),
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "# CIAM Security Requirements\n\n"
                    "## Access Control\n"
                    "- ABAC with XACML policies\n"
                    "- Just-in-time provisioning\n"
                    "- Continuous authorization monitoring\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": "Users should be able to log in with their government ID.",
                "source_model": "gemini-flash",
            },
        ],
        "expected_best": 0,
        "rating": 4.0,
        "comment": "Strong identity federation and compliance coverage",
    },
    # ── 3. Kubernetes Deployment ──────────────────────────────────────────
    {
        "description": "Kubernetes deployment spec for platform engineering",
        "selection_method": "hybrid",
        "candidates": [
            {
                "content": (
                    "# K8s Platform Deployment Specification\n\n"
                    "## Cluster Architecture\n"
                    "- Multi-AZ control plane (3 masters)\n"
                    "- Node pools: general (m5.xlarge), GPU (p3.2xlarge), spot\n"
                    "- Istio service mesh with mTLS\n\n"
                    "## GitOps\n"
                    "- ArgoCD with ApplicationSets\n"
                    "- Helm charts + Kustomize overlays\n"
                    "- Progressive rollouts (Argo Rollouts)\n\n"
                    "## Observability\n"
                    "- Prometheus + Grafana stack\n"
                    "- OpenTelemetry collector\n"
                    "- Loki for log aggregation\n\n"
                    "## Security\n"
                    "- OPA Gatekeeper policies\n"
                    "- Falco runtime security\n"
                    "- Vault for secrets management\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": (
                    "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: api-server\n"
                    "spec:\n  replicas: 3\n  template:\n    spec:\n      containers:\n"
                    "      - name: api\n        image: api:latest\n        resources:\n"
                    "          limits:\n            memory: 512Mi\n            cpu: 500m\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": "Deploy the app to Kubernetes with 3 replicas and a load balancer.",
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "# Infrastructure Requirements\n\n"
                    "| Resource | Spec |\n"
                    "|----------|------|\n"
                    "| CPU | 4 vCPU per node |\n"
                    "| Memory | 16 GB |\n"
                    "| Storage | 100 GB SSD |\n"
                    "| Network | 10 Gbps |\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": '{"kind":"Service","apiVersion":"v1","metadata":{"name":"api"},"spec":{"type":"LoadBalancer","ports":[{"port":80}]}}',
                "source_model": "claude-sonnet",
            },
        ],
        "expected_best": 0,
        "rating": 5.0,
        "comment": "Comprehensive platform spec with security and observability",
    },
    # ── 4. Event-Driven Architecture ──────────────────────────────────────
    {
        "description": "Event-driven architecture for e-commerce platform",
        "selection_method": "hybrid",
        "candidates": [
            {
                "content": (
                    "# Event-Driven E-commerce Architecture\n\n"
                    "## Event Bus\n"
                    "- Apache Kafka with 3 brokers, RF=3\n"
                    "- Schema Registry (Avro)\n"
                    "- Dead letter queues per consumer group\n\n"
                    "## Domain Events\n"
                    "- OrderPlaced, PaymentProcessed, InventoryReserved\n"
                    "- Saga orchestration for distributed transactions\n\n"
                    "## Resilience\n"
                    "- Circuit breakers (Hystrix patterns)\n"
                    "- Idempotent consumers\n"
                    "- Exactly-once semantics via Kafka transactions\n\n"
                    "## Monitoring\n"
                    "- Consumer lag alerting\n"
                    "- Event flow visualization (Conduktor)\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": (
                    "## Messaging Requirements\n"
                    "- Use a message queue\n"
                    "- Events should be processed in order\n"
                    "- Retry failed messages\n"
                ),
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    '{"asyncapi":"2.6.0","info":{"title":"Orders","version":"1.0"},'
                    '"channels":{"orders":{"subscribe":{"message":{"payload":{"type":"object"}}}}}}'
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": (
                    "# E-commerce Event Flows\n\n"
                    "```mermaid\n"
                    "sequenceDiagram\n"
                    "    Customer->>+OrderService: Place Order\n"
                    "    OrderService->>+Kafka: OrderPlaced\n"
                    "    Kafka->>+PaymentService: Process Payment\n"
                    "    Kafka->>+InventoryService: Reserve Stock\n"
                    "```\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": "Use Kafka for events between microservices.",
                "source_model": "gemini-flash",
            },
        ],
        "expected_best": 0,
        "rating": 4.5,
        "comment": "Strong event architecture with saga and resilience patterns",
    },
    # ── 5. ML Pipeline ────────────────────────────────────────────────────
    {
        "description": "ML pipeline specification for fraud detection model",
        "selection_method": "hybrid",
        "candidates": [
            {
                "content": (
                    "# Fraud Detection ML Pipeline\n\n"
                    "## Feature Engineering\n"
                    "- Transaction velocity features (1h, 24h, 7d windows)\n"
                    "- Device fingerprint embeddings\n"
                    "- Network graph features (PageRank, degree centrality)\n\n"
                    "## Model Architecture\n"
                    "- Gradient Boosted Trees (LightGBM) for real-time scoring\n"
                    "- Graph Neural Network for ring detection (offline)\n"
                    "- Ensemble: 0.7 × LightGBM + 0.3 × GNN\n\n"
                    "## Training Infrastructure\n"
                    "- Feature store: Feast on Redis\n"
                    "- Training: SageMaker with Spot instances\n"
                    "- Model registry: MLflow\n"
                    "- A/B testing via LaunchDarkly flags\n\n"
                    "## SLAs\n"
                    "- P99 inference latency < 50ms\n"
                    "- Model refresh cadence: daily\n"
                    "- Precision@95% recall ≥ 0.80\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": (
                    "# ML Requirements\n"
                    "- Train a model to detect fraud\n"
                    "- Use historical transaction data\n"
                    "- Deploy model to production\n"
                    "- Monitor for drift\n"
                ),
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "steps:\n"
                    "  - name: ingest\n    type: spark_job\n    source: s3://data/transactions/\n"
                    "  - name: feature_eng\n    type: python\n    script: features.py\n"
                    "  - name: train\n    type: sagemaker\n    instance: ml.p3.2xlarge\n"
                    "  - name: evaluate\n    type: python\n    metrics: [precision, recall, f1]\n"
                    "  - name: deploy\n    type: endpoint\n    instance: ml.m5.xlarge\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": (
                    "## Model Card\n\n"
                    "| Metric | Value |\n"
                    "|--------|-------|\n"
                    "| AUC-ROC | 0.97 |\n"
                    "| Precision@95R | 0.82 |\n"
                    "| Training Time | 4.2h |\n"
                    "| Inference P99 | 42ms |\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": "Build a fraud detection model using machine learning.",
                "source_model": "gemini-flash",
            },
        ],
        "expected_best": 0,
        "rating": 5.0,
        "comment": "Excellent ML pipeline spec with SLAs and model architecture",
    },
    # ── 6. API Gateway ────────────────────────────────────────────────────
    {
        "description": "API gateway configuration for multi-tenant SaaS",
        "selection_method": "hybrid",
        "candidates": [
            {
                "content": (
                    "# API Gateway Specification\n\n"
                    "## Routing\n"
                    "- Path-based routing with tenant isolation\n"
                    "- Header-based A/B routing (X-Canary: true)\n"
                    "- gRPC-Web transcoding for frontend clients\n\n"
                    "## Security\n"
                    "- JWT validation with JWKS rotation\n"
                    "- WAF integration (OWASP ModSecurity CRS)\n"
                    "- Bot detection and CAPTCHA challenge\n\n"
                    "## Rate Limiting\n"
                    "- Sliding window per tenant (Redis-backed)\n"
                    "- Burst allowance: 2× base rate for 10s\n"
                    "- Graduated throttling (429 → 503)\n\n"
                    "## Observability\n"
                    "- Request tracing (W3C Trace Context)\n"
                    "- Custom metrics: latency_p99, error_rate, throttle_rate\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": (
                    "# Gateway Config\n\n"
                    "```yaml\n"
                    "routes:\n"
                    "  - path: /api/v1/*\n"
                    "    upstream: backend:8080\n"
                    "    plugins:\n"
                    "      - rate-limiting:\n"
                    "          limit: 100\n"
                    "          window: 60s\n"
                    "```\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": "Set up an API gateway with rate limiting and authentication.",
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "## Gateway Requirements\n"
                    "- Support 10,000 RPS\n"
                    "- TLS termination\n"
                    "- Load balancing across backends\n"
                    "- Health checks every 10s\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": '{"service":"gateway","version":"2.0","routes":[{"path":"/api","methods":["GET","POST"]}]}',
                "source_model": "claude-sonnet",
            },
        ],
        "expected_best": 0,
        "rating": 4.0,
        "comment": "Good gateway spec with multi-tenant awareness",
    },
    # ── 7. Database Migration ─────────────────────────────────────────────
    {
        "description": "Database migration strategy for legacy Oracle to PostgreSQL",
        "selection_method": "hybrid",
        "candidates": [
            {
                "content": (
                    "# Oracle → PostgreSQL Migration Plan\n\n"
                    "## Phase 1: Schema Conversion\n"
                    "- AWS SCT for automated conversion\n"
                    "- Manual review of PL/SQL → PL/pgSQL\n"
                    "- Custom type mappings: NUMBER → NUMERIC, VARCHAR2 → TEXT\n\n"
                    "## Phase 2: Data Migration\n"
                    "- AWS DMS with CDC for zero-downtime cutover\n"
                    "- Data validation: row counts, checksums, sampling\n"
                    "- Performance baseline: capture Oracle AWR, replay on PG\n\n"
                    "## Phase 3: Application Migration\n"
                    "- Connection pooling: PgBouncer (transaction mode)\n"
                    "- Query rewrite: CONNECT BY → WITH RECURSIVE\n"
                    "- ORM mapping updates (Hibernate dialect)\n\n"
                    "## Rollback Strategy\n"
                    "- Bidirectional DMS replication for 30 days\n"
                    "- Feature flags for database routing\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": (
                    "## Migration Steps\n"
                    "1. Export Oracle schema\n"
                    "2. Convert to PostgreSQL\n"
                    "3. Migrate data\n"
                    "4. Test application\n"
                    "5. Cutover\n"
                ),
                "source_model": "gemini-flash",
            },
            {
                "content": "Migrate from Oracle to Postgres using AWS DMS.",
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "-- Schema comparison\n"
                    "-- Oracle\n"
                    "CREATE TABLE orders (\n"
                    "  id NUMBER(19) PRIMARY KEY,\n"
                    "  amount NUMBER(10,2),\n"
                    "  created_at TIMESTAMP DEFAULT SYSTIMESTAMP\n"
                    ");\n\n"
                    "-- PostgreSQL equivalent\n"
                    "CREATE TABLE orders (\n"
                    "  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,\n"
                    "  amount NUMERIC(10,2),\n"
                    "  created_at TIMESTAMPTZ DEFAULT NOW()\n"
                    ");\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": (
                    "# Migration Testing Checklist\n"
                    "- [ ] Schema diff report\n"
                    "- [ ] Row count validation\n"
                    "- [ ] Stored procedure tests\n"
                    "- [ ] Performance regression suite\n"
                    "- [ ] Rollback drill\n"
                ),
                "source_model": "claude-sonnet",
            },
        ],
        "expected_best": 0,
        "rating": 4.5,
        "comment": "Thorough migration plan with rollback strategy",
    },
    # ── 8. Monitoring & Alerting ──────────────────────────────────────────
    {
        "description": "Monitoring and alerting specification for SRE team",
        "selection_method": "hybrid",
        "candidates": [
            {
                "content": (
                    "# Observability Platform Specification\n\n"
                    "## Metrics (Prometheus)\n"
                    "- Four Golden Signals: latency, traffic, errors, saturation\n"
                    "- Custom business KPIs via StatsD bridge\n"
                    "- 15s scrape interval, 90d retention\n\n"
                    "## Logging (ELK)\n"
                    "- Structured JSON logs via Filebeat\n"
                    "- Index lifecycle: hot (7d) → warm (30d) → cold (90d) → delete\n"
                    "- Correlation via trace_id field\n\n"
                    "## Tracing (Jaeger)\n"
                    "- OpenTelemetry SDK instrumentation\n"
                    "- Tail-based sampling: 100% errors, 1% success\n"
                    "- Service dependency graph\n\n"
                    "## Alerting\n"
                    "- Multi-window burn rate SLO alerts\n"
                    "- PagerDuty integration with escalation policies\n"
                    "- Alert deduplication and grouping\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": (
                    "groups:\n"
                    "  - name: slo-alerts\n"
                    "    rules:\n"
                    "    - alert: HighErrorRate\n"
                    "      expr: rate(http_errors_total[5m]) > 0.01\n"
                    "      for: 5m\n"
                    "      labels:\n"
                    "        severity: critical\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": "Set up monitoring with Prometheus and Grafana dashboards.",
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "## Dashboard Requirements\n"
                    "- Service health overview\n"
                    "- Request latency heatmap\n"
                    "- Error rate by endpoint\n"
                    "- Pod resource utilization\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": '{"dashboard":{"title":"SRE Overview","panels":[{"type":"graph","title":"Latency P99"}]}}',
                "source_model": "claude-sonnet",
            },
        ],
        "expected_best": 0,
        "rating": 5.0,
        "comment": "Complete observability spec covering metrics, logs, traces, and alerting",
    },
    # ── 9. CI/CD Pipeline ─────────────────────────────────────────────────
    {
        "description": "CI/CD pipeline specification for regulated fintech",
        "selection_method": "hybrid",
        "candidates": [
            {
                "content": (
                    "# CI/CD Pipeline Specification\n\n"
                    "## Build Stage\n"
                    "- Multi-stage Docker builds with distroless base images\n"
                    "- SBOM generation (Syft) and vulnerability scanning (Grype)\n"
                    "- Unit + integration tests (>80% coverage gate)\n\n"
                    "## Security Gate\n"
                    "- SAST: Semgrep with custom rules\n"
                    "- DAST: OWASP ZAP baseline scan\n"
                    "- Secret scanning: TruffleHog\n"
                    "- License compliance: FOSSA\n\n"
                    "## Deployment\n"
                    "- Blue/green with automated rollback on error budget burn\n"
                    "- Canary: 5% → 25% → 100% over 2h\n"
                    "- Deployment windows: Mon-Thu, 10am-3pm EST\n\n"
                    "## Audit\n"
                    "- Signed commits (GPG)\n"
                    "- Provenance attestation (SLSA Level 3)\n"
                    "- Change approval via 2-person rule\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": (
                    "stages:\n"
                    "  - build\n"
                    "  - test\n"
                    "  - deploy\n\n"
                    "build:\n"
                    "  script: docker build -t app .\n"
                    "test:\n"
                    "  script: pytest\n"
                    "deploy:\n"
                    "  script: kubectl apply -f k8s/\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": "Automate builds and deploys using GitHub Actions.",
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "## Pipeline Metrics\n"
                    "| Metric | Target |\n"
                    "|--------|--------|\n"
                    "| Build Time | < 5 min |\n"
                    "| Deploy Frequency | Daily |\n"
                    "| Change Failure Rate | < 5% |\n"
                    "| MTTR | < 1h |\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": '{"pipeline":"v1","steps":[{"name":"build","image":"node:18"},{"name":"test","command":"npm test"}]}',
                "source_model": "claude-sonnet",
            },
        ],
        "expected_best": 0,
        "rating": 4.5,
        "comment": "Excellent regulated CI/CD with SLSA attestation and security gates",
    },
    # ── 10. Data Lake Architecture ────────────────────────────────────────
    {
        "description": "Data lakehouse architecture for analytics platform",
        "selection_method": "hybrid",
        "candidates": [
            {
                "content": (
                    "# Data Lakehouse Specification\n\n"
                    "## Storage Layer\n"
                    "- Delta Lake on S3 (ACID transactions)\n"
                    "- Medallion architecture: Bronze → Silver → Gold\n"
                    "- Z-order optimization on partition keys\n\n"
                    "## Ingestion\n"
                    "- Batch: Spark 3.4 on EMR Serverless\n"
                    "- Streaming: Kafka → Spark Structured Streaming\n"
                    "- CDC: Debezium → Kafka → Delta Lake\n\n"
                    "## Governance\n"
                    "- Unity Catalog for fine-grained access control\n"
                    "- Column-level masking for PII\n"
                    "- Data lineage tracking end-to-end\n\n"
                    "## Query Layer\n"
                    "- Databricks SQL Serverless for BI\n"
                    "- Presto/Trino for ad-hoc federation\n"
                    "- dbt for transformation orchestration\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": (
                    "# Data Pipeline\n"
                    "1. Extract from source databases\n"
                    "2. Load into S3 as Parquet\n"
                    "3. Transform with Spark\n"
                    "4. Serve via Redshift/Athena\n"
                ),
                "source_model": "gemini-flash",
            },
            {
                "content": "Store data in S3 and query with Athena for analytics.",
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "## Data Catalog\n"
                    "| Dataset | Format | Size | Freshness |\n"
                    "|---------|--------|------|-----------|\n"
                    "| transactions | Delta | 2TB | Real-time |\n"
                    "| customers | Delta | 50GB | Daily |\n"
                    "| products | Parquet | 5GB | Weekly |\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": (
                    "CREATE SCHEMA bronze;\n"
                    "CREATE SCHEMA silver;\n"
                    "CREATE SCHEMA gold;\n\n"
                    "-- Bronze: raw ingestion\n"
                    "CREATE TABLE bronze.transactions (\n"
                    "  raw_data STRING,\n"
                    "  ingested_at TIMESTAMP\n"
                    ") USING DELTA;\n"
                ),
                "source_model": "gpt-4o",
            },
        ],
        "expected_best": 0,
        "rating": 5.0,
        "comment": "Comprehensive lakehouse with medallion architecture and governance",
    },
    # ── 11. Zero Trust Security ───────────────────────────────────────────
    {
        "description": "Zero trust network architecture for enterprise",
        "selection_method": "hybrid",
        "candidates": [
            {
                "content": (
                    "# Zero Trust Architecture Specification\n\n"
                    "## Identity Verification\n"
                    "- Continuous authentication (risk-based MFA)\n"
                    "- Device posture assessment (EDR integration)\n"
                    "- Session binding to device + location\n\n"
                    "## Micro-segmentation\n"
                    "- Service mesh mTLS (Istio/Linkerd)\n"
                    "- Dynamic firewall rules per workload identity\n"
                    "- East-west traffic encryption\n\n"
                    "## Policy Engine\n"
                    "- OPA/Rego for authorization decisions\n"
                    "- Context-aware policies (time, location, device trust)\n"
                    "- Policy audit log with immutable storage\n\n"
                    "## Data Protection\n"
                    "- Encryption at rest (AES-256) and in transit (TLS 1.3)\n"
                    "- DLP scanning at egress points\n"
                    "- Key management via HSM-backed KMS\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": (
                    "## Security Controls Checklist\n"
                    "- [ ] Network segmentation\n"
                    "- [ ] MFA enrollment\n"
                    "- [ ] Endpoint protection\n"
                    "- [ ] Log aggregation\n"
                    "- [ ] Incident response plan\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": "Implement zero trust by verifying every request and encrypting all traffic.",
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "# Network Policies\n\n"
                    "```yaml\n"
                    "apiVersion: networking.k8s.io/v1\n"
                    "kind: NetworkPolicy\n"
                    "metadata:\n"
                    "  name: deny-all\n"
                    "spec:\n"
                    "  podSelector: {}\n"
                    "  policyTypes:\n"
                    "  - Ingress\n"
                    "  - Egress\n"
                    "```\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": '{"zta_version":"1.0","components":["identity","device_trust","policy_engine"]}',
                "source_model": "claude-sonnet",
            },
        ],
        "expected_best": 0,
        "rating": 4.5,
        "comment": "Thorough zero trust spec with micro-segmentation and policy engine",
    },
    # ── 12. Mobile Backend ────────────────────────────────────────────────
    {
        "description": "Mobile BFF (backend for frontend) API specification",
        "selection_method": "hybrid",
        "candidates": [
            {
                "content": (
                    "# Mobile BFF API Specification\n\n"
                    "## GraphQL Schema\n"
                    "- Federated graph (Apollo Federation v2)\n"
                    "- Persisted queries for mobile (APQ)\n"
                    "- Dataloader batching for N+1 prevention\n\n"
                    "## Offline Support\n"
                    "- Conflict resolution: last-writer-wins with vector clocks\n"
                    "- Delta sync via GraphQL subscriptions\n"
                    "- Local-first with SQLite (WatermelonDB)\n\n"
                    "## Performance\n"
                    "- CDN caching for static queries (30min TTL)\n"
                    "- Response compression (Brotli)\n"
                    "- Image optimization pipeline (WebP, AVIF)\n\n"
                    "## Push Notifications\n"
                    "- FCM/APNs unified abstraction\n"
                    "- Topic-based and targeted delivery\n"
                    "- Silent push for background sync\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": (
                    "type Query {\n"
                    "  user(id: ID!): User\n"
                    "  feed(cursor: String, limit: Int): FeedConnection\n"
                    "}\n\n"
                    "type User {\n"
                    "  id: ID!\n"
                    "  name: String!\n"
                    "  avatar: String\n"
                    "}\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": "Build a REST API for the mobile app with authentication and push notifications.",
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "## Mobile API Endpoints\n"
                    "- GET /api/v2/user/profile\n"
                    "- POST /api/v2/user/update\n"
                    "- GET /api/v2/feed?page=1\n"
                    "- POST /api/v2/notifications/register\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": '{"swagger":"2.0","info":{"title":"Mobile API","version":"1.0"},"basePath":"/api/v2"}',
                "source_model": "claude-sonnet",
            },
        ],
        "expected_best": 0,
        "rating": 4.0,
        "comment": "Good BFF spec with offline support and GraphQL federation",
    },
    # ── 13. Disaster Recovery ─────────────────────────────────────────────
    {
        "description": "Disaster recovery and business continuity specification",
        "selection_method": "hybrid",
        "candidates": [
            {
                "content": (
                    "# Disaster Recovery Specification\n\n"
                    "## RPO/RTO Targets\n"
                    "- Tier 1 (payments): RPO=0, RTO=15m (active-active)\n"
                    "- Tier 2 (core services): RPO=5m, RTO=1h (warm standby)\n"
                    "- Tier 3 (analytics): RPO=1h, RTO=4h (pilot light)\n\n"
                    "## Multi-Region Architecture\n"
                    "- Primary: us-east-1, Secondary: us-west-2\n"
                    "- Aurora Global Database with <1s replication lag\n"
                    "- Route 53 health-check-based failover\n\n"
                    "## Backup Strategy\n"
                    "- Automated daily snapshots with cross-region copy\n"
                    "- Point-in-time recovery for databases\n"
                    "- S3 cross-region replication with versioning\n\n"
                    "## DR Testing\n"
                    "- Quarterly full failover drill\n"
                    "- Monthly backup restoration test\n"
                    "- Chaos engineering: Kill primary region simulation\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": (
                    "## DR Requirements\n"
                    "- Backups every 24 hours\n"
                    "- Recovery within 4 hours\n"
                    "- Offsite backup storage\n"
                ),
                "source_model": "gemini-flash",
            },
            {
                "content": "Ensure the system can recover from a disaster within 4 hours with daily backups.",
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "# Failover Runbook\n\n"
                    "1. Detect failure (automated health checks)\n"
                    "2. Verify secondary region health\n"
                    "3. Promote read replica to primary\n"
                    "4. Update DNS (Route 53 failover)\n"
                    "5. Verify application connectivity\n"
                    "6. Notify stakeholders\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": (
                    "## RTO/RPO Matrix\n"
                    "| Tier | RPO | RTO | Strategy |\n"
                    "|------|-----|-----|----------|\n"
                    "| 1 | 0 | 15m | Active-Active |\n"
                    "| 2 | 5m | 1h | Warm Standby |\n"
                    "| 3 | 1h | 4h | Pilot Light |\n"
                ),
                "source_model": "gpt-4o",
            },
        ],
        "expected_best": 0,
        "rating": 5.0,
        "comment": "Excellent DR spec with tiered RPO/RTO and chaos testing",
    },
    # ── 14. Microservices Communication ───────────────────────────────────
    {
        "description": "Microservices communication patterns and service mesh",
        "selection_method": "hybrid",
        "candidates": [
            {
                "content": (
                    "# Service Mesh & Communication Specification\n\n"
                    "## Synchronous Communication\n"
                    "- gRPC with protobuf for internal service calls\n"
                    "- Automatic retries with exponential backoff + jitter\n"
                    "- Circuit breaker: 5 failures in 30s → open for 60s\n\n"
                    "## Asynchronous Communication\n"
                    "- NATS JetStream for at-least-once delivery\n"
                    "- Consumer groups for horizontal scaling\n"
                    "- Dead letter subjects with alerting\n\n"
                    "## Service Discovery\n"
                    "- Consul with health checks (TCP + HTTP)\n"
                    "- DNS-based service resolution\n"
                    "- Weighted routing for canary deployments\n\n"
                    "## Resilience Patterns\n"
                    "- Bulkhead isolation per downstream dependency\n"
                    "- Timeout budget propagation via context\n"
                    "- Graceful degradation with circuit-breaker fallbacks\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": (
                    "syntax = \"proto3\";\n\n"
                    "service OrderService {\n"
                    "  rpc CreateOrder (CreateOrderRequest) returns (Order);\n"
                    "  rpc GetOrder (GetOrderRequest) returns (Order);\n"
                    "}\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": "Services communicate via REST APIs with JSON payloads.",
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "## Communication Matrix\n"
                    "| From | To | Protocol | Pattern |\n"
                    "|------|----|----------|---------|\n"
                    "| API GW | Auth | gRPC | Sync |\n"
                    "| Orders | Payment | gRPC | Sync |\n"
                    "| Payment | Notify | NATS | Async |\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": '{"services":[{"name":"orders","port":8080},{"name":"payments","port":8081}]}',
                "source_model": "claude-sonnet",
            },
        ],
        "expected_best": 0,
        "rating": 4.5,
        "comment": "Comprehensive service mesh spec with resilience patterns",
    },
    # ── 15. Compliance & Audit ────────────────────────────────────────────
    {
        "description": "Compliance and audit trail specification for fintech",
        "selection_method": "hybrid",
        "candidates": [
            {
                "content": (
                    "# Compliance & Audit Specification\n\n"
                    "## Audit Trail\n"
                    "- Immutable append-only log (Amazon QLDB)\n"
                    "- Event sourcing for all state changes\n"
                    "- Cryptographic hash chaining for tamper evidence\n\n"
                    "## Regulatory Compliance\n"
                    "- SOX Section 404: automated control testing\n"
                    "- PCI DSS: quarterly ASV scans + annual ROC\n"
                    "- GDPR: automated DSAR processing (30-day SLA)\n"
                    "- CCPA: opt-out mechanism with 72h processing\n\n"
                    "## Data Retention\n"
                    "- Transaction records: 7 years (SOX requirement)\n"
                    "- PII: minimum retention with automated purge\n"
                    "- Audit logs: 10 years (regulatory floor)\n\n"
                    "## Reporting\n"
                    "- Real-time compliance dashboard\n"
                    "- Automated anomaly detection on access patterns\n"
                    "- Monthly compliance posture reports\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": (
                    "## Audit Requirements\n"
                    "- Log all user actions\n"
                    "- Retain logs for 1 year\n"
                    "- Weekly audit review\n"
                ),
                "source_model": "gemini-flash",
            },
            {
                "content": "All transactions must be logged for compliance and auditing purposes.",
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "CREATE TABLE audit_log (\n"
                    "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),\n"
                    "  actor_id UUID NOT NULL,\n"
                    "  action VARCHAR(100) NOT NULL,\n"
                    "  resource_type VARCHAR(50),\n"
                    "  resource_id UUID,\n"
                    "  old_value JSONB,\n"
                    "  new_value JSONB,\n"
                    "  created_at TIMESTAMPTZ DEFAULT NOW()\n"
                    ");\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": (
                    "## Compliance Controls\n"
                    "| Control | Framework | Status |\n"
                    "|---------|-----------|--------|\n"
                    "| Access logging | SOX 404 | Implemented |\n"
                    "| Encryption | PCI DSS | Implemented |\n"
                    "| Data retention | GDPR | In Progress |\n"
                ),
                "source_model": "gpt-4o",
            },
        ],
        "expected_best": 0,
        "rating": 4.5,
        "comment": "Strong compliance spec with multiple regulatory frameworks",
    },
    # ── 16. Caching Strategy ──────────────────────────────────────────────
    {
        "description": "Multi-layer caching architecture for high-traffic platform",
        "selection_method": "rl_only",
        "candidates": [
            {
                "content": (
                    "# Caching Architecture\n\n"
                    "## L1: Application Cache\n"
                    "- In-process LRU cache (Caffeine)\n"
                    "- 10,000 entries, 5-minute TTL\n"
                    "- Automatic invalidation via pub/sub\n\n"
                    "## L2: Distributed Cache\n"
                    "- Redis Cluster (6 nodes, 3 primaries)\n"
                    "- Cache-aside pattern with write-through for hot paths\n"
                    "- Key namespacing per service\n\n"
                    "## L3: CDN\n"
                    "- CloudFront with custom cache policies\n"
                    "- Stale-while-revalidate for API responses\n"
                    "- Edge compute for personalization\n\n"
                    "## Cache Invalidation\n"
                    "- Event-driven invalidation via Kafka\n"
                    "- Versioned keys for atomic updates\n"
                    "- Cache stampede protection (probabilistic early expiration)\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": (
                    "## Cache Config\n"
                    "```yaml\n"
                    "redis:\n"
                    "  host: redis-cluster\n"
                    "  ttl: 300\n"
                    "  max_memory: 4gb\n"
                    "  eviction_policy: allkeys-lru\n"
                    "```\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": "Use Redis for caching frequently accessed data.",
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "## Cache Hit Rate Targets\n"
                    "| Layer | Target | Current |\n"
                    "|-------|--------|---------|\n"
                    "| L1 | >90% | 92% |\n"
                    "| L2 | >80% | 78% |\n"
                    "| L3 | >95% | 96% |\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": '{"cache":{"type":"redis","cluster":true,"nodes":6,"memory":"4gb"}}',
                "source_model": "claude-sonnet",
            },
        ],
        "expected_best": 0,
        "rating": 4.0,
        "comment": "Excellent multi-layer caching with invalidation strategy",
    },
    # ── 17. Testing Strategy ──────────────────────────────────────────────
    {
        "description": "Testing strategy for mission-critical financial platform",
        "selection_method": "rl_only",
        "candidates": [
            {
                "content": (
                    "# Testing Strategy Specification\n\n"
                    "## Test Pyramid\n"
                    "- Unit: 70% (pytest, >90% coverage)\n"
                    "- Integration: 20% (testcontainers + real Postgres/Redis)\n"
                    "- E2E: 10% (Playwright + custom API harness)\n\n"
                    "## Specialized Testing\n"
                    "- Property-based: Hypothesis for invariant validation\n"
                    "- Contract: Pact for service boundaries\n"
                    "- Chaos: Litmus for resilience verification\n"
                    "- Performance: k6 with SLO-based thresholds\n\n"
                    "## Quality Gates\n"
                    "- PR: unit + integration (< 10min)\n"
                    "- Staging: full E2E + performance suite\n"
                    "- Release: chaos + security scan\n\n"
                    "## Test Data Management\n"
                    "- Factories: faker-based deterministic generation\n"
                    "- Fixtures: snapshotted from sanitized production\n"
                    "- Environments: ephemeral per-PR via Argo\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": (
                    "## Test Plan\n"
                    "- Write unit tests for all modules\n"
                    "- Run integration tests in CI\n"
                    "- Manual QA before release\n"
                ),
                "source_model": "gemini-flash",
            },
            {
                "content": "Test everything thoroughly before deploying to production.",
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "# Test Coverage Report\n"
                    "| Module | Coverage | Target |\n"
                    "|--------|----------|--------|\n"
                    "| auth | 94% | 90% |\n"
                    "| payments | 88% | 90% |\n"
                    "| orders | 91% | 90% |\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": (
                    "def test_create_payment():\n"
                    "    response = client.post('/payments', json={'amount': 100})\n"
                    "    assert response.status_code == 201\n"
                ),
                "source_model": "gpt-4o",
            },
        ],
        "expected_best": 0,
        "rating": 5.0,
        "comment": "Comprehensive testing strategy with pyramid and specialized testing",
    },
    # ── 18. Logging & Tracing ─────────────────────────────────────────────
    {
        "description": "Structured logging and distributed tracing specification",
        "selection_method": "rl_only",
        "candidates": [
            {
                "content": (
                    "# Logging & Tracing Specification\n\n"
                    "## Structured Logging\n"
                    "- JSON format with W3C Trace Context fields\n"
                    "- Log levels: TRACE/DEBUG/INFO/WARN/ERROR/FATAL\n"
                    "- Mandatory fields: timestamp, service, trace_id, span_id, level\n"
                    "- PII scrubbing middleware (email, SSN, card numbers)\n\n"
                    "## Distributed Tracing\n"
                    "- OpenTelemetry SDK (auto + manual instrumentation)\n"
                    "- Baggage propagation for tenant context\n"
                    "- Span attributes: http.method, db.statement, rpc.service\n\n"
                    "## Collection Pipeline\n"
                    "- OpenTelemetry Collector with tail sampling processor\n"
                    "- Export: Jaeger (traces), Loki (logs), Prometheus (metrics)\n"
                    "- Correlation: trace_id linkage across all three signals\n\n"
                    "## Retention & Cost\n"
                    "- Hot: 7d full fidelity\n"
                    "- Warm: 30d sampled (errors=100%, success=10%)\n"
                    "- Cold: 90d aggregated metrics only\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": (
                    "import structlog\n\n"
                    "logger = structlog.get_logger()\n"
                    "logger.info('payment_processed', amount=100, currency='USD')\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": "Add logging to all services using a standard format.",
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "## Log Format Specification\n"
                    "```json\n"
                    '{"timestamp":"2024-01-15T10:30:00Z","level":"INFO",'
                    '"service":"payments","trace_id":"abc123",'
                    '"message":"Payment processed","amount":100}\n'
                    "```\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": '{"logging":{"format":"json","level":"info","output":"stdout"}}',
                "source_model": "claude-sonnet",
            },
        ],
        "expected_best": 0,
        "rating": 4.5,
        "comment": "Excellent observability spec covering all three pillars",
    },
    # ── 19. Feature Flags ─────────────────────────────────────────────────
    {
        "description": "Feature flag system for progressive delivery",
        "selection_method": "hybrid",
        "candidates": [
            {
                "content": (
                    "# Feature Flag System Specification\n\n"
                    "## Flag Types\n"
                    "- Boolean: simple on/off\n"
                    "- Multivariate: A/B/C testing with traffic splits\n"
                    "- JSON: complex configuration payloads\n"
                    "- Operational: kill switches with <1s propagation\n\n"
                    "## Targeting\n"
                    "- User attributes: role, plan, tenant_id\n"
                    "- Percentage rollout with sticky bucketing (murmur3)\n"
                    "- Segment-based: beta_users, internal_testers\n\n"
                    "## Architecture\n"
                    "- Server-side SDK with local evaluation (no network hop)\n"
                    "- Streaming updates via SSE (Server-Sent Events)\n"
                    "- Evaluation cache: in-memory, <1ms P99\n\n"
                    "## Governance\n"
                    "- Flag lifecycle: created → active → deprecated → archived\n"
                    "- Stale flag detection (>90d inactive)\n"
                    "- Audit trail for all flag changes\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": (
                    "## Feature Flags\n"
                    "- new_checkout: enabled for beta users\n"
                    "- dark_mode: 50% rollout\n"
                    "- payment_v2: internal only\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": "Use feature flags to control rollout of new features.",
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "if feature_flags.is_enabled('new_checkout', user=current_user):\n"
                    "    return render_new_checkout()\n"
                    "else:\n"
                    "    return render_legacy_checkout()\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": '{"flags":{"new_checkout":{"enabled":true,"rollout":50},"dark_mode":{"enabled":false}}}',
                "source_model": "claude-sonnet",
            },
        ],
        "expected_best": 0,
        "rating": 4.0,
        "comment": "Good feature flag system with targeting and governance",
    },
    # ── 20. Rate Limiting ─────────────────────────────────────────────────
    {
        "description": "API rate limiting and throttling specification",
        "selection_method": "rl_only",
        "candidates": [
            {
                "content": (
                    "# Rate Limiting Specification\n\n"
                    "## Algorithms\n"
                    "- Token bucket for API endpoints (burst-friendly)\n"
                    "- Sliding window log for authentication attempts\n"
                    "- Fixed window counter for billing quotas\n\n"
                    "## Tier System\n"
                    "- Free: 100 req/min, 10k req/day\n"
                    "- Pro: 1000 req/min, 100k req/day\n"
                    "- Enterprise: custom, with burst allowance\n\n"
                    "## Implementation\n"
                    "- Redis Lua scripts for atomic operations\n"
                    "- Distributed rate limiting with cluster-wide counters\n"
                    "- Graceful degradation on Redis failure (local fallback)\n\n"
                    "## Response Handling\n"
                    "- 429 Too Many Requests with Retry-After header\n"
                    "- X-RateLimit-Limit, X-RateLimit-Remaining headers\n"
                    "- Client SDK with automatic retry + exponential backoff\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": (
                    "## Rate Limit Config\n"
                    "```yaml\n"
                    "rate_limits:\n"
                    "  default:\n"
                    "    requests_per_minute: 100\n"
                    "    burst: 20\n"
                    "  premium:\n"
                    "    requests_per_minute: 1000\n"
                    "    burst: 200\n"
                    "```\n"
                ),
                "source_model": "claude-sonnet",
            },
            {
                "content": "Limit API requests to prevent abuse.",
                "source_model": "gemini-flash",
            },
            {
                "content": (
                    "## Rate Limit Response Headers\n"
                    "| Header | Description |\n"
                    "|--------|-------------|\n"
                    "| X-RateLimit-Limit | Max requests per window |\n"
                    "| X-RateLimit-Remaining | Requests left |\n"
                    "| X-RateLimit-Reset | Window reset time |\n"
                    "| Retry-After | Seconds until retry allowed |\n"
                ),
                "source_model": "gpt-4o",
            },
            {
                "content": '{"rateLimit":{"enabled":true,"maxRequests":100,"window":"1m"}}',
                "source_model": "claude-sonnet",
            },
        ],
        "expected_best": 0,
        "rating": 4.5,
        "comment": "Thorough rate limiting with multiple algorithms and tier system",
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _jitter(base: float, factor: float = 0.3) -> float:
    """Add random jitter to a delay."""
    return base * (1.0 + random.uniform(-factor, factor))


async def _evaluate(
    client: httpx.AsyncClient,
    scenario: dict,
    base_url: str,
) -> dict | None:
    """POST /v1/specs and return the response JSON, or None on failure."""
    payload = {
        "candidates": scenario["candidates"],
        "selection_method": scenario["selection_method"],
        "description": scenario["description"],
    }
    try:
        resp = await client.post(f"{base_url}/specs", json=payload)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        print(f"  [ERROR] /specs returned {exc.response.status_code}: {exc.response.text[:200]}")
        return None
    except httpx.ConnectError:
        print("  [ERROR] Cannot connect to server — is it running?")
        return None


async def _feedback(
    client: httpx.AsyncClient,
    request_id: str,
    scenario: dict,
    base_url: str,
) -> bool:
    """POST /v1/specs/feedback."""
    payload = {
        "request_id": request_id,
        "rating": scenario["rating"],
        "comment": scenario["comment"],
    }
    try:
        resp = await client.post(f"{base_url}/specs/feedback", json=payload)
        resp.raise_for_status()
        return True
    except httpx.HTTPStatusError as exc:
        print(f"  [ERROR] /feedback returned {exc.response.status_code}: {exc.response.text[:200]}")
        return False


async def _train(
    client: httpx.AsyncClient,
    n_steps: int,
    base_url: str,
) -> dict | None:
    """POST /v1/policy/train."""
    try:
        resp = await client.post(
            f"{base_url}/policy/train",
            json={"n_steps": n_steps},
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        print(f"  [ERROR] /train returned {exc.response.status_code}: {exc.response.text[:200]}")
        return None


async def _policy_status(
    client: httpx.AsyncClient,
    base_url: str,
) -> dict | None:
    """GET /v1/policy/status."""
    try:
        resp = await client.get(f"{base_url}/policy/status")
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError:
        return None


# ── Main loop ─────────────────────────────────────────────────────────────────

async def run(
    base_url: str,
    rounds: int,
    train_every: int,
    n_steps: int,
) -> None:
    """Execute the data-loop: evaluate → feedback → train."""
    scenarios = SCENARIOS[:rounds]
    total = len(scenarios)

    print(f"\n{'='*60}")
    print(f"  ReinforceSpec — RL Data Loop")
    print(f"  Server:       {base_url}")
    print(f"  Rounds:       {total}")
    print(f"  Train every:  {train_every} evaluations")
    print(f"  PPO steps:    {n_steps}")
    print(f"{'='*60}\n")

    async with httpx.AsyncClient(timeout=180) as client:
        # Verify server is reachable
        status = await _policy_status(client, base_url)
        if status is None:
            print("[FATAL] Cannot reach server. Start it with: make serve")
            return
        print(f"[OK] Server reachable — policy version: {status.get('version', 'none')}\n")

        evaluated = 0
        trained = 0
        t_start = time.monotonic()

        for i, scenario in enumerate(scenarios, 1):
            print(f"[{i}/{total}] {scenario['description']}")
            print(f"         method={scenario['selection_method']}")

            # ── Step 1: Evaluate ──────────────────────────────────────
            result = await _evaluate(client, scenario, base_url)
            if result is None:
                print("         ⏭ Skipping (evaluation failed)\n")
                continue

            req_id = result["request_id"]
            selected = result["selected"]
            print(
                f"         → Selected index={selected.get('index', '?')} "
                f"score={selected.get('composite_score', 0):.3f} "
                f"latency={result.get('latency_ms', 0):.0f}ms"
            )

            # Show all candidate scores
            for c in result.get("all_candidates", []):
                marker = " ★" if c.get("index") == selected.get("index") else ""
                print(f"           [{c.get('index')}] {c.get('composite_score', 0):.3f}{marker}")

            evaluated += 1

            # ── Step 2: Feedback ──────────────────────────────────────
            ok = await _feedback(client, req_id, scenario, base_url)
            if ok:
                print(f"         ✓ Feedback: rating={scenario['rating']}")
            else:
                print("         ✗ Feedback submission failed")

            # ── Step 3: Train (periodic) ──────────────────────────────
            if evaluated % train_every == 0:
                print(f"\n  ──── Training (buffer={evaluated} transitions, steps={n_steps}) ────")
                train_result = await _train(client, n_steps, base_url)
                if train_result:
                    trained += 1
                    mr = train_result.get("mean_reward", 0)
                    ver = train_result.get("policy_id", "?")
                    print(f"         ✓ Policy {ver} — mean_reward={mr:.3f}")
                else:
                    print("         ✗ Training failed")

                # Show updated status
                status = await _policy_status(client, base_url)
                if status:
                    print(f"         Policy status: stage={status.get('stage')}, "
                          f"episodes={status.get('training_episodes')}, "
                          f"reward={status.get('mean_reward', 0):.3f}")
                print()

            # Small delay between rounds to avoid overwhelming scorers
            await asyncio.sleep(_jitter(1.0))

        # Final training pass if buffer has unprocessed transitions
        remaining = evaluated % train_every
        if remaining > 0:
            print(f"\n  ──── Final training ({remaining} new transitions, steps={n_steps}) ────")
            train_result = await _train(client, n_steps, base_url)
            if train_result:
                trained += 1
                mr = train_result.get("mean_reward", 0)
                print(f"         ✓ Final policy — mean_reward={mr:.3f}")

        elapsed = time.monotonic() - t_start

        # Summary
        print(f"\n{'='*60}")
        print(f"  Summary")
        print(f"  Evaluations:  {evaluated}/{total}")
        print(f"  Training runs: {trained}")
        print(f"  Elapsed:      {elapsed:.1f}s")

        status = await _policy_status(client, base_url)
        if status:
            print(f"\n  Final Policy")
            print(f"    Version:   {status.get('version')}")
            print(f"    Stage:     {status.get('stage')}")
            print(f"    Episodes:  {status.get('training_episodes')}")
            print(f"    Reward:    {status.get('mean_reward', 0):.3f}")
            print(f"    Explore:   {status.get('explore_rate', 0):.3f}")
        print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build RL replay buffer with diverse spec scenarios",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000/v1",
        help="Base URL of the ReinforceSpec API (default: http://localhost:8000/v1)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=20,
        help="Number of evaluation rounds (default: 20, max: %(default)s)",
    )
    parser.add_argument(
        "--train-every",
        type=int,
        default=5,
        help="Train after every N evaluations (default: 5)",
    )
    parser.add_argument(
        "--n-steps",
        type=int,
        default=256,
        help="PPO training timesteps per training run (default: 256)",
    )
    args = parser.parse_args()

    asyncio.run(run(
        base_url=args.base_url,
        rounds=min(args.rounds, len(SCENARIOS)),
        train_every=args.train_every,
        n_steps=args.n_steps,
    ))


if __name__ == "__main__":
    main()
