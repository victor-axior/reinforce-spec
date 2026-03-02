"""Example: Using the EnterpriseScorer directly for scoring specs.

This example shows how to use the scoring engine independently
to evaluate spec candidates without RL selection.
"""

import asyncio

from loguru import logger

from reinforce_spec._internal._client import OpenRouterClient
from reinforce_spec._internal._config import LLMConfig, ScoringConfig
from reinforce_spec.scoring import EnterpriseScorer, get_preset
from reinforce_spec.types import CandidateSpec


async def main() -> None:
    """Demonstrate scoring-only mode without the full SDK."""
    # Setup
    llm_config = LLMConfig()  # reads OPENROUTER_API_KEY from env
    scoring_config = ScoringConfig()
    client = OpenRouterClient(llm_config)
    scorer = EnterpriseScorer(client=client, config=scoring_config)

    # Create some sample specs to score
    candidates = [
        CandidateSpec(
            index=0,
            spec_type="api",
            content=(
                "# Payment API Specification\n\n"
                "## Authentication\n"
                "- OAuth 2.0 with mTLS\n"
                "- API key rotation every 90 days\n\n"
                "## Endpoints\n"
                "- POST /v1/payments — Create payment\n"
                "- GET /v1/payments/{id} — Get payment status\n\n"
                "## Compliance\n"
                "- PCI DSS Level 1 compliant\n"
                "- SOC 2 Type II audit trail\n"
            ),
            source_model="human",
        ),
        CandidateSpec(
            index=1,
            spec_type="architecture",
            content=(
                "# Payment Architecture\n\n"
                "## Overview\n"
                "Event-driven microservices with CQRS pattern.\n\n"
                "## Components\n"
                "- API Gateway (Kong)\n"
                "- Payment Orchestrator\n"
                "- Fraud Engine (ML-based)\n"
                "- Settlement Service\n"
                "- Notification Service\n"
            ),
            source_model="human",
        ),
    ]

    # Score with bank preset
    weights = get_preset("bank")
    scored = await scorer.score_candidates(candidates, weights)

    for spec in scored:
        logger.info("Spec {} ({}, {}): {:.3f}", spec.index, spec.spec_type, spec.format.value, spec.composite_score)
        for ds in spec.dimension_scores:
            logger.info("  {}: {:.1f}", ds.dimension, ds.score)


if __name__ == "__main__":
    asyncio.run(main())
