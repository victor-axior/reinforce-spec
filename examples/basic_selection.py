"""Example: Basic spec selection with ReinforceSpec.

This example demonstrates the core score → RL select pipeline.
Provide your own spec candidates in any format (text, JSON, YAML, Markdown, etc.)
and ReinforceSpec evaluates and selects the best one.
"""

import asyncio

from loguru import logger

from reinforce_spec import CandidateSpec, ReinforceSpec


async def main() -> None:
    """Run end-to-end spec selection demo."""
    async with ReinforceSpec.from_env() as rs:
        # Provide spec candidates (any textual format)
        candidates = [
            CandidateSpec(
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
                spec_type="api",
            ),
            CandidateSpec(
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
                spec_type="architecture",
            ),
            CandidateSpec(
                content='{"openapi":"3.0.3","info":{"title":"Payments","version":"1.0"}}',
                spec_type="api",
            ),
            CandidateSpec(
                content=(
                    "title: Payment SRS\n"
                    "version: 2.0\n"
                    "requirements:\n"
                    "  - id: REQ-001\n"
                    "    description: Process credit card transactions\n"
                    "  - id: REQ-002\n"
                    "    description: Detect fraudulent transactions in real-time\n"
                ),
                spec_type="srs",
            ),
            CandidateSpec(
                content=(
                    "The payment system shall handle credit card transactions, "
                    "provide real-time fraud detection, and automate daily settlement "
                    "batches for enterprise banking clients."
                ),
                spec_type="prd",
            ),
        ]

        # Evaluate and select the best spec
        response = await rs.select(
            candidates=candidates,
            customer_type="bank",
            description="Payment processing specs comparison",
        )

        # Access the selected (best) spec
        logger.info("Request ID: {}", response.request_id)
        logger.info("Selected spec type: {}", response.selected.spec_type)
        logger.info("Detected format: {}", response.selected.format.value)
        logger.info("Composite score: {:.2f}", response.selected.composite_score)
        logger.info("Selection method: {}", response.selection_method)
        logger.info("Latency: {:.0f}ms", response.latency_ms)

        # Show all rankings
        logger.info("=== Rankings ===")
        for rank, spec in enumerate(response.rankings, 1):
            logger.info("  #{}: {:<14} ({:<10}) score={:.3f}", rank, spec.spec_type, spec.format.value, spec.composite_score)

            # Show top 3 dimensions
            sorted_dims = sorted(
                spec.dimension_scores,
                key=lambda d: d.score,
                reverse=True,
            )
            for dim in sorted_dims[:3]:
                logger.info("       {}: {:.1f}", dim.dimension, dim.score)

        # Show the selected spec content (first 500 chars)
        logger.info("=== Selected Specification ===")
        logger.info("{}", response.selected.content[:500])

        # Submit feedback
        feedback_id = await rs.submit_feedback(
            request_id=response.request_id,
            rating=4.5,
            comment="Good coverage of fraud detection patterns",
        )
        logger.info("Feedback submitted: {}", feedback_id)


if __name__ == "__main__":
    asyncio.run(main())
