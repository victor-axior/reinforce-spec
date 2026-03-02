"""Customer-type weight presets.

Different enterprise customers have different priorities. These presets
adjust dimension weights to match typical constraints per customer type.
All presets sum to 1.0.
"""

from __future__ import annotations

from reinforce_spec.types import CustomerType, ScoringWeights

# ── Preset Definitions ────────────────────────────────────────────────────────

PRESETS: dict[CustomerType, ScoringWeights] = {
    CustomerType.DEFAULT: ScoringWeights(),  # Uses field defaults (all sum to 1.0)
    CustomerType.BANK: ScoringWeights(
        compliance_regulatory=0.14,
        identity_access=0.11,
        deployment_topology=0.06,
        data_governance=0.12,
        observability_monitoring=0.06,
        incident_workflow=0.08,
        security_architecture=0.14,
        vendor_model_abstraction=0.06,
        scalability_performance=0.06,
        finops_cost=0.05,
        developer_experience=0.05,
        onboarding_production_path=0.07,
    ),
    CustomerType.SI: ScoringWeights(
        compliance_regulatory=0.08,
        identity_access=0.10,
        deployment_topology=0.10,
        data_governance=0.07,
        observability_monitoring=0.08,
        incident_workflow=0.07,
        security_architecture=0.08,
        vendor_model_abstraction=0.09,
        scalability_performance=0.09,
        finops_cost=0.06,
        developer_experience=0.10,
        onboarding_production_path=0.08,
    ),
    CustomerType.BPO: ScoringWeights(
        compliance_regulatory=0.08,
        identity_access=0.12,  # multi-tenancy critical for BPO
        deployment_topology=0.07,
        data_governance=0.09,
        observability_monitoring=0.07,
        incident_workflow=0.08,
        security_architecture=0.09,
        vendor_model_abstraction=0.07,
        scalability_performance=0.10,
        finops_cost=0.09,  # cost per client matters
        developer_experience=0.06,
        onboarding_production_path=0.08,
    ),
    CustomerType.SAAS: ScoringWeights(
        compliance_regulatory=0.07,
        identity_access=0.08,
        deployment_topology=0.06,
        data_governance=0.06,
        observability_monitoring=0.09,
        incident_workflow=0.06,
        security_architecture=0.08,
        vendor_model_abstraction=0.08,
        scalability_performance=0.14,  # scale is king for SaaS
        finops_cost=0.08,
        developer_experience=0.12,  # DX matters for SaaS builders
        onboarding_production_path=0.08,
    ),
}


def get_preset(customer_type: CustomerType) -> ScoringWeights:
    """Return the scoring weights for a customer type."""
    return PRESETS.get(customer_type, PRESETS[CustomerType.DEFAULT])


def list_presets() -> dict[str, ScoringWeights]:
    """Return all available presets as a type_name → weights mapping."""
    return {ct.value: weights for ct, weights in PRESETS.items()}
