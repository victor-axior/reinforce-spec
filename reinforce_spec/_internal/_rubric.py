"""12-dimension enterprise-readiness rubric.

Each dimension has:
  - A unique key matching the ScoringWeights field names
  - A display name and description
  - Scoring criteria for levels 1-5 with concrete examples
  - Tags for categorization
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class Dimension(str, enum.Enum):
    """The 12 enterprise-readiness scoring dimensions."""

    COMPLIANCE_REGULATORY = "compliance_regulatory"
    IDENTITY_ACCESS = "identity_access"
    DEPLOYMENT_TOPOLOGY = "deployment_topology"
    DATA_GOVERNANCE = "data_governance"
    OBSERVABILITY_MONITORING = "observability_monitoring"
    INCIDENT_WORKFLOW = "incident_workflow"
    SECURITY_ARCHITECTURE = "security_architecture"
    VENDOR_MODEL_ABSTRACTION = "vendor_model_abstraction"
    SCALABILITY_PERFORMANCE = "scalability_performance"
    FINOPS_COST = "finops_cost"
    DEVELOPER_EXPERIENCE = "developer_experience"
    ONBOARDING_PRODUCTION_PATH = "onboarding_production_path"


@dataclass(frozen=True)
class ScoreCriterion:
    """Criteria for a specific score level (1-5)."""

    score: int
    description: str
    examples: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DimensionDefinition:
    """Full definition of a scoring dimension."""

    key: Dimension
    name: str
    description: str
    default_weight: float
    criteria: list[ScoreCriterion]
    tags: list[str] = field(default_factory=list)


# ── Rubric Definitions ────────────────────────────────────────────────────────

RUBRIC: dict[Dimension, DimensionDefinition] = {
    Dimension.COMPLIANCE_REGULATORY: DimensionDefinition(
        key=Dimension.COMPLIANCE_REGULATORY,
        name="Compliance & Regulatory Readiness",
        description=(
            "Satisfies all applicable compliance regimes out of the box. "
            "Day-zero-safe-by-default posture: fail closed, not open."
        ),
        default_weight=0.10,
        tags=["compliance", "regulatory", "gdpr", "hipaa", "soc2"],
        criteria=[
            ScoreCriterion(
                score=5,
                description=(
                    "Specifies GDPR, HIPAA, SOC2, ISO 27001, EU AI Act compliance with concrete "
                    "implementation details. Day-zero-safe: missing config fails closed. Includes "
                    "data processing agreements, consent mechanisms, right-to-erasure workflows, "
                    "audit logging for all compliance-relevant events, and automated compliance "
                    "reporting. Sector-specific regulations addressed."
                ),
                examples=[
                    "GDPR: data subject access request API with 72h response SLA",
                    "EU AI Act: risk classification, transparency reporting, human oversight mechanisms",
                    "Fail-closed: if encryption key is unavailable, reject all writes",
                ],
            ),
            ScoreCriterion(
                score=4,
                description=(
                    "Covers major compliance frameworks (GDPR, SOC2, HIPAA) with implementation "
                    "approach. Mentions fail-closed behavior. Data retention policies defined but "
                    "some edge cases (cross-border transfer, AI-specific regulation) not fully addressed."
                ),
                examples=["SOC2 Type II controls mapped to specific system components"],
            ),
            ScoreCriterion(
                score=3,
                description=(
                    "References compliance frameworks by name. Some implementation guidance. "
                    "General data protection mentions without specific workflows."
                ),
                examples=["'System supports GDPR compliance' without specifying how"],
            ),
            ScoreCriterion(
                score=2,
                description="Mentions compliance as a concern without specifying frameworks or approach.",
                examples=["'Must comply with applicable regulations'"],
            ),
            ScoreCriterion(
                score=1,
                description="No compliance or regulatory considerations mentioned.",
            ),
        ],
    ),
    Dimension.IDENTITY_ACCESS: DimensionDefinition(
        key=Dimension.IDENTITY_ACCESS,
        name="Identity & Access Integration",
        description=(
            "Drops into existing identity fabric (Okta/AAD/LDAP SSO + SCIM + RBAC) "
            "with zero new credential silos. Hard multi-tenancy guarantees."
        ),
        default_weight=0.09,
        tags=["identity", "auth", "rbac", "multi-tenancy", "sso"],
        criteria=[
            ScoreCriterion(
                score=5,
                description=(
                    "Full SSO integration (Okta, Azure AD, LDAP) via OIDC/SAML. SCIM provisioning "
                    "for automated user lifecycle. RBAC with principle of least privilege, definable "
                    "per tenant. Hard multi-tenancy: data, keys, logs, routing policies isolated per "
                    "tenant. mTLS for service-to-service auth. API key rotation with zero-downtime. "
                    "Audit logging of all auth events. No new credential silos."
                ),
                examples=[
                    "SCIM 2.0 endpoint for automated user provisioning from Okta",
                    "Per-tenant encryption keys with HSM-backed key management",
                    "Session management with configurable idle/absolute timeouts",
                ],
            ),
            ScoreCriterion(
                score=4,
                description=(
                    "SSO with specific protocols (OIDC/SAML). RBAC defined. Multi-tenancy at data "
                    "level. Missing some edge cases (key rotation, SCIM, service-to-service auth)."
                ),
                examples=["OAuth2 + RBAC with 5 predefined roles"],
            ),
            ScoreCriterion(
                score=3,
                description="Basic auth mechanism (JWT/API keys). General RBAC. No multi-tenancy detail.",
                examples=["JWT-based auth with admin/user roles"],
            ),
            ScoreCriterion(
                score=2,
                description="Auth mentioned but underspecified. No SSO or multi-tenancy.",
            ),
            ScoreCriterion(
                score=1,
                description="No identity or access management specified.",
            ),
        ],
    ),
    Dimension.DEPLOYMENT_TOPOLOGY: DimensionDefinition(
        key=Dimension.DEPLOYMENT_TOPOLOGY,
        name="Deployment Topology Flexibility",
        description=(
            "Deployable in any target topology (SaaS, VPC, on-prem, air-gapped) "
            "with one standardized playbook. Respects data residency constraints."
        ),
        default_weight=0.09,
        tags=["deployment", "topology", "data-residency", "air-gapped"],
        criteria=[
            ScoreCriterion(
                score=5,
                description=(
                    "Explicit support for SaaS, VPC-deployed, on-prem, and air-gapped topologies "
                    "with a single, parameterized deployment playbook. Per-tenant routing to allowed "
                    "regions/clouds for data residency. Zero-downtime deployment (blue-green/canary). "
                    "Infrastructure-as-code with Terraform/Helm. Automated rollback on health check "
                    "failure. Instant deployment pipeline."
                ),
                examples=[
                    "Helm chart with values overlays: values-saas.yaml, values-vpc.yaml, values-airgap.yaml",
                    "Data residency: tenant config maps to allowed cloud regions, enforced at routing layer",
                    "Air-gapped: offline artifact bundle with SHA256 verification",
                ],
            ),
            ScoreCriterion(
                score=4,
                description=(
                    "Supports multiple deployment targets with documented procedures. Some IaC. "
                    "Data residency mentioned but routing not fully automated."
                ),
            ),
            ScoreCriterion(
                score=3,
                description="Docker-based deployment. Single topology documented. No data residency.",
            ),
            ScoreCriterion(
                score=2,
                description="Basic deployment instructions. Single environment only.",
            ),
            ScoreCriterion(
                score=1,
                description="No deployment considerations specified.",
            ),
        ],
    ),
    Dimension.DATA_GOVERNANCE: DimensionDefinition(
        key=Dimension.DATA_GOVERNANCE,
        name="Data Governance & Classification",
        description=(
            "Aligns with existing data-classification and DLP policies. "
            "No new shadow data stores. Read-only-to-production patterns."
        ),
        default_weight=0.08,
        tags=["data-governance", "dlp", "classification", "change-control"],
        criteria=[
            ScoreCriterion(
                score=5,
                description=(
                    "Inherits existing data classification schemes. No shadow data stores created. "
                    "DLP policy integration (Microsoft Purview, Symantec). Read-only to production, "
                    "write to sandbox patterns enforced architecturally. Data lineage tracking. "
                    "Automated PII detection and redaction. Data retention policies with automated "
                    "purging. Change-control approval gates for production data access."
                ),
                examples=[
                    "Data classification labels (Public/Internal/Confidential/Restricted) inherited from org taxonomy",
                    "Sandbox environment with synthetic data generation for testing",
                    "Production database access requires ServiceNow change ticket approval",
                ],
            ),
            ScoreCriterion(
                score=4,
                description=(
                    "Data classification mentioned. No shadow stores. Some change-control patterns. "
                    "Missing automated DLP integration or data lineage."
                ),
            ),
            ScoreCriterion(
                score=3,
                description="General data handling policies. Environment separation mentioned.",
            ),
            ScoreCriterion(
                score=2,
                description="Basic data storage considerations without governance framework.",
            ),
            ScoreCriterion(
                score=1,
                description="No data governance considerations.",
            ),
        ],
    ),
    Dimension.OBSERVABILITY_MONITORING: DimensionDefinition(
        key=Dimension.OBSERVABILITY_MONITORING,
        name="Observability & Monitoring Integration",
        description=(
            "Uses organization-approved observability stack (Splunk/ELK/Datadog/New Relic) "
            "for logs, metrics, traces from day one."
        ),
        default_weight=0.08,
        tags=["observability", "monitoring", "logging", "tracing", "metrics"],
        criteria=[
            ScoreCriterion(
                score=5,
                description=(
                    "Pluggable observability: supports Splunk, ELK, Datadog, New Relic via "
                    "OpenTelemetry. Structured logging with correlation IDs. Distributed tracing "
                    "across all service boundaries. RED/USE metrics. SLO/SLI definitions with "
                    "error budgets. Log aggregation with configurable retention. Custom dashboards "
                    "and alerting rules. Health check endpoints (liveness + readiness)."
                ),
                examples=[
                    "OpenTelemetry collector with exporters for Datadog, Splunk, and Jaeger",
                    "SLO: 99.9% availability, p99 latency < 500ms, error rate < 0.1%",
                    "Structured JSON logs with request_id, tenant_id, user_id correlation",
                ],
            ),
            ScoreCriterion(
                score=4,
                description="Logging + metrics + tracing specified. Mentions specific tools. Missing SLOs.",
            ),
            ScoreCriterion(
                score=3,
                description="Basic logging and health checks. No tracing or metrics strategy.",
            ),
            ScoreCriterion(
                score=2,
                description="Mentions logging without structured approach.",
            ),
            ScoreCriterion(
                score=1,
                description="No observability considerations.",
            ),
        ],
    ),
    Dimension.INCIDENT_WORKFLOW: DimensionDefinition(
        key=Dimension.INCIDENT_WORKFLOW,
        name="Incident & Workflow Integration",
        description=(
            "Integrates with current ticketing and incident workflows "
            "(ServiceNow/Jira) for alerts, approvals, and kill-switches."
        ),
        default_weight=0.07,
        tags=["incident", "ticketing", "servicenow", "jira", "kill-switch"],
        criteria=[
            ScoreCriterion(
                score=5,
                description=(
                    "Bi-directional integration with ServiceNow and/or Jira. Automated incident "
                    "creation on critical alerts. Approval workflows for change management via "
                    "ticketing system. Kill-switch mechanisms with audit trail. Runbook automation. "
                    "Escalation policies with on-call rotation integration (PagerDuty/OpsGenie). "
                    "Post-incident review templates."
                ),
                examples=[
                    "Critical alert → auto-creates ServiceNow P1 incident → pages on-call via PagerDuty",
                    "Model deployment requires Jira approval ticket in APPROVED status",
                    "Kill-switch: API endpoint to disable specific model/feature with audit log",
                ],
            ),
            ScoreCriterion(
                score=4,
                description="Ticketing integration specified. Alert routing defined. Missing kill-switches or runbooks.",
            ),
            ScoreCriterion(
                score=3,
                description="Alerts mentioned. Generic escalation process. No specific tooling integration.",
            ),
            ScoreCriterion(
                score=2,
                description="Basic error notification without workflow integration.",
            ),
            ScoreCriterion(
                score=1,
                description="No incident or workflow integration considered.",
            ),
        ],
    ),
    Dimension.SECURITY_ARCHITECTURE: DimensionDefinition(
        key=Dimension.SECURITY_ARCHITECTURE,
        name="Security Architecture & Threat Modeling",
        description=(
            "Ships with pre-approved reference architectures and threat models. "
            "Red-teamable behavior with clear failure modes and sandbox environments."
        ),
        default_weight=0.10,
        tags=["security", "threat-model", "red-team", "architecture"],
        criteria=[
            ScoreCriterion(
                score=5,
                description=(
                    "Pre-approved reference architecture passable in a single CISO session. STRIDE "
                    "threat model with mitigations for each threat. Input validation, output encoding, "
                    "CSP headers, OWASP Top 10 mitigations. Red-teamable: test harness, sandbox "
                    "environments, clear failure modes documented. Encryption at rest (AES-256) and "
                    "in transit (TLS 1.3). Secrets management (Vault/KMS). Vulnerability scanning "
                    "in CI pipeline. Explainable AI behavior for governance bodies."
                ),
                examples=[
                    "STRIDE analysis: 24 threats identified, each with specific mitigation and test case",
                    "Red-team sandbox: isolated environment with full API surface, synthetic data, audit log",
                    "Dependency scanning via Snyk/Dependabot with auto-PR for critical CVEs",
                ],
            ),
            ScoreCriterion(
                score=4,
                description="Encryption + OWASP mitigations + some threat modeling. Missing red-team infrastructure.",
            ),
            ScoreCriterion(
                score=3,
                description="General security (HTTPS, auth). No threat model or red-team capability.",
            ),
            ScoreCriterion(
                score=2,
                description="Minimal security. Basic auth only.",
            ),
            ScoreCriterion(
                score=1,
                description="No security architecture considerations.",
            ),
        ],
    ),
    Dimension.VENDOR_MODEL_ABSTRACTION: DimensionDefinition(
        key=Dimension.VENDOR_MODEL_ABSTRACTION,
        name="Vendor & Model Abstraction",
        description=(
            "Provides model and vendor abstraction so legal/procurement negotiate once. "
            "Clear exit and migration guarantees with no proprietary lock-in."
        ),
        default_weight=0.08,
        tags=["vendor", "abstraction", "portability", "lock-in", "exit"],
        criteria=[
            ScoreCriterion(
                score=5,
                description=(
                    "Complete vendor/model abstraction layer. Legal/procurement negotiate a single "
                    "contract covering all underlying models. Full config + log export capabilities. "
                    "No proprietary data formats (open standards only). Migration playbook with "
                    "estimated effort. Provider-agnostic API that works across OpenAI, Anthropic, "
                    "Google, open-source models. Clear exit guarantees documented for vendor selection "
                    "committees."
                ),
                examples=[
                    "Model abstraction: swap from GPT-4 to Claude via config change, no code change",
                    "Export: one-click export of all configs, logs, policies as JSON/YAML archive",
                    "SLA: 90-day migration support window upon contract termination",
                ],
            ),
            ScoreCriterion(
                score=4,
                description="Model abstraction present. Some portability. Exit process mentioned but not detailed.",
            ),
            ScoreCriterion(
                score=3,
                description="Multiple models supported. No formal exit or migration strategy.",
            ),
            ScoreCriterion(
                score=2,
                description="Single vendor dependency with acknowledgment of risk.",
            ),
            ScoreCriterion(
                score=1,
                description="Hard vendor lock-in with no abstraction.",
            ),
        ],
    ),
    Dimension.SCALABILITY_PERFORMANCE: DimensionDefinition(
        key=Dimension.SCALABILITY_PERFORMANCE,
        name="Scalability, Performance & Resilience",
        description=(
            "Built for scale, max performance, fault tolerance, resilience. "
            "Conservative resource utilization with graceful degradation."
        ),
        default_weight=0.09,
        tags=["scalability", "performance", "resilience", "fault-tolerance"],
        criteria=[
            ScoreCriterion(
                score=5,
                description=(
                    "Horizontal + vertical scaling with auto-scaling policies. Caching layers "
                    "(Redis/CDN). Connection pooling. Async processing with backpressure. Circuit "
                    "breakers with half-open recovery. Retry with exponential backoff + jitter. "
                    "Graceful degradation ladder. Bulkhead pattern. Conservative resource utilization. "
                    "Concrete p99 latency targets. Load testing results documented. Database "
                    "sharding/replication strategy."
                ),
                examples=[
                    "Auto-scale: 2-50 replicas based on CPU (70%) and request queue depth (>100)",
                    "Circuit breaker: 5 failures → open for 60s → half-open probe → close on success",
                    "Degradation: L0=full → L1=reduced ensemble → L2=single model → L3=cached",
                ],
            ),
            ScoreCriterion(
                score=4,
                description="Scaling strategy with specific tech. Performance targets. Partial resilience patterns.",
            ),
            ScoreCriterion(
                score=3,
                description="General scalability ('should scale'). No concrete targets or resilience.",
            ),
            ScoreCriterion(
                score=2,
                description="Single-server design with future scaling mentioned.",
            ),
            ScoreCriterion(
                score=1,
                description="No scalability or performance considerations.",
            ),
        ],
    ),
    Dimension.FINOPS_COST: DimensionDefinition(
        key=Dimension.FINOPS_COST,
        name="FinOps & Cost Controls",
        description=(
            "FinOps-ready cost controls aligned with finance norms: budgets, alerts, "
            "chargeback tags, per-BU/per-project accounting."
        ),
        default_weight=0.07,
        tags=["finops", "cost", "budget", "chargeback"],
        criteria=[
            ScoreCriterion(
                score=5,
                description=(
                    "Comprehensive FinOps: per-tenant/per-BU/per-project cost tracking with "
                    "chargeback tags. Budget thresholds with automated alerts at 50%/80%/100%. "
                    "Cost dashboards. Token/API call metering. Resource rightsizing recommendations. "
                    "Cost anomaly detection. Conservative resource utilization by design. Cloud cost "
                    "allocation tags on all provisioned resources."
                ),
                examples=[
                    "Chargeback: every API call tagged with tenant_id, project_id, cost_center",
                    "Budget alert: Slack notification at 80%, hard cap at 100% with graceful rejection",
                    "Monthly cost report: per-model token usage, per-tenant breakdown, trend analysis",
                ],
            ),
            ScoreCriterion(
                score=4,
                description="Budget tracking and alerts. Some chargeback. Missing anomaly detection.",
            ),
            ScoreCriterion(
                score=3,
                description="Basic cost monitoring. Usage logging without chargeback.",
            ),
            ScoreCriterion(
                score=2,
                description="Cost awareness mentioned without controls.",
            ),
            ScoreCriterion(
                score=1,
                description="No cost controls or FinOps consideration.",
            ),
        ],
    ),
    Dimension.DEVELOPER_EXPERIENCE: DimensionDefinition(
        key=Dimension.DEVELOPER_EXPERIENCE,
        name="Developer Experience & SDK Surface",
        description=(
            "Easy to use, zero friction, plug and play. Minimal SDK surface area "
            "with GitOps-ready configuration."
        ),
        default_weight=0.08,
        tags=["dx", "sdk", "gitops", "developer-experience"],
        criteria=[
            ScoreCriterion(
                score=5,
                description=(
                    "Minimal SDK surface area. Language bindings for Python, TypeScript, Java "
                    "matching enterprise coding standards. Comprehensive API documentation (OpenAPI). "
                    "Code examples for every endpoint. GitOps-ready: all config via YAML/JSON files, "
                    "no manual console. CLI tooling. SDK versioning with backwards compatibility. "
                    "Playground/sandbox environment. Quick-start guide achievable in < 5 minutes."
                ),
                examples=[
                    "Python: `pip install axior-sdk && axior init` → working config in 30 seconds",
                    "GitOps: `git push` triggers config validation → staged rollout → auto-rollback",
                    "SDK surface: 5 core methods, 3 optional config objects, typed everywhere",
                ],
            ),
            ScoreCriterion(
                score=4,
                description="Good SDK with docs. API reference. Config-as-code. Missing some language bindings.",
            ),
            ScoreCriterion(
                score=3,
                description="REST API documented. Basic SDK. Manual configuration.",
            ),
            ScoreCriterion(
                score=2,
                description="API exists but poorly documented. No SDK.",
            ),
            ScoreCriterion(
                score=1,
                description="No developer-facing interface specified.",
            ),
        ],
    ),
    Dimension.ONBOARDING_PRODUCTION_PATH: DimensionDefinition(
        key=Dimension.ONBOARDING_PRODUCTION_PATH,
        name="Onboarding, PoC & Production Path",
        description=(
            "One-click onboarding templates per customer type. Documented PoC → pilot → "
            "production path with success metrics matching customer ROI gates."
        ),
        default_weight=0.07,
        tags=["onboarding", "poc", "pilot", "production", "roi"],
        criteria=[
            ScoreCriterion(
                score=5,
                description=(
                    "One-click onboarding templates per customer type (bank, SI, BPO, SaaS) with "
                    "defaults matching typical constraints. Documented PoC → pilot → production path "
                    "with explicit success metrics at each gate. ROI calculator. Time-boxed PoC with "
                    "clear exit criteria. Pilot checklist with production-readiness scorecard. "
                    "Customer success playbook. Iterative improvement framework."
                ),
                examples=[
                    "Bank template: pre-configured with HIPAA+SOC2, data residency=US, SSO=Azure AD",
                    "PoC gate: 2-week timebox, success = 3 use cases at >90% quality, <500ms p99",
                    "Production scorecard: 15 criteria across security, performance, compliance, ops",
                ],
            ),
            ScoreCriterion(
                score=4,
                description="Onboarding documented. PoC process defined. Missing customer-type presets.",
            ),
            ScoreCriterion(
                score=3,
                description="Getting started guide. General deployment instructions.",
            ),
            ScoreCriterion(
                score=2,
                description="Minimal onboarding. Install instructions only.",
            ),
            ScoreCriterion(
                score=1,
                description="No onboarding or production path documented.",
            ),
        ],
    ),
}


# ── Helper Functions ──────────────────────────────────────────────────────────


def get_all_dimensions() -> list[Dimension]:
    """Return all dimensions in order."""
    return list(Dimension)


def get_dimension_definition(dim: Dimension) -> DimensionDefinition:
    """Return the full definition for a dimension."""
    return RUBRIC[dim]


def get_default_weights() -> dict[str, float]:
    """Return default weights as a dimension_key → weight mapping."""
    return {dim.value: defn.default_weight for dim, defn in RUBRIC.items()}


def validate_weights(weights: dict[str, float], tolerance: float = 1e-6) -> bool:
    """Check that weights sum to 1.0 and cover all dimensions."""
    if set(weights.keys()) != {d.value for d in Dimension}:
        return False
    return abs(sum(weights.values()) - 1.0) < tolerance


def format_rubric_for_prompt() -> str:
    """Format the full rubric as a string for inclusion in LLM judge prompts."""
    lines: list[str] = []
    for dim, defn in RUBRIC.items():
        lines.append(f"### {defn.name}")
        lines.append(f"Key: `{dim.value}`")
        lines.append(f"Description: {defn.description}")
        lines.append(f"Default weight: {defn.default_weight}")
        lines.append("")
        lines.append("Scoring criteria:")
        for criterion in defn.criteria:
            lines.append(f"  **Score {criterion.score}**: {criterion.description}")
            if criterion.examples:
                for ex in criterion.examples:
                    lines.append(f"    - Example: {ex}")
        lines.append("")
    return "\n".join(lines)
