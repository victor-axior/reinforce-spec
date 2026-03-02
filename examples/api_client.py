"""Example: Server API usage with httpx.

Demonstrates calling the ReinforceSpec REST API from a Python client.
"""

import asyncio

import httpx
from loguru import logger

BASE_URL = "http://localhost:8000/v1"


async def main() -> None:
    """Demonstrate API client usage against a running server."""
    async with httpx.AsyncClient(timeout=120) as client:
        # 1. Health check
        health = await client.get(f"{BASE_URL}/health")
        logger.info("Health: {}", health.json())

        # 2. Evaluate and select best spec
        logger.info("Evaluating specs...")
        response = await client.post(
            f"{BASE_URL}/specs",
            json={
                "candidates": [
                    {
                        "content": (
                            "# CIAM Platform Specification\n\n"
                            "## Identity Federation\n"
                            "- SAML 2.0 and OIDC support\n"
                            "- PIV/CAC smart card authentication\n"
                            "- FedRAMP High authorization\n"
                        ),
                        "spec_type": "architecture",
                    },
                    {
                        "content": (
                            "openapi: '3.0.3'\n"
                            "info:\n"
                            "  title: CIAM API\n"
                            "  version: '1.0'\n"
                            "paths:\n"
                            "  /v1/identities:\n"
                            "    post:\n"
                            "      summary: Create identity\n"
                        ),
                        "spec_type": "api",
                    },
                    {
                        "content": (
                            "The CIAM platform shall support multi-factor authentication, "
                            "identity proofing at IAL2, and federated SSO across agency "
                            "boundaries with full NIST 800-63 compliance."
                        ),
                        "spec_type": "srs",
                    },
                    {
                        "content": (
                            "# CIAM Security Requirements\n\n"
                            "## Access Control\n"
                            "- ABAC with XACML policies\n"
                            "- Just-in-time provisioning\n"
                            "- Continuous authorization monitoring\n"
                        ),
                        "spec_type": "security",
                    },
                    {
                        "content": (
                            "# CIAM Test Plan\n\n"
                            "## Penetration Testing\n"
                            "- OWASP Top 10 coverage\n"
                            "- Authentication bypass attempts\n"
                            "## Load Testing\n"
                            "- 10,000 concurrent SSO sessions\n"
                        ),
                        "spec_type": "test_plan",
                    },
                ],
                "customer_type": "si",
                "selection_method": "hybrid",
                "description": "CIAM platform for government SI client",
            },
        )
        data = response.json()

        logger.info("Request ID: {}", data['request_id'])
        logger.info("Latency: {}ms", data['latency_ms'])
        logger.info("Selected: {}", data['selected']['spec_type'])
        logger.info("Score: {:.3f}", data['selected']['composite_score'])

        # 3. Show rankings
        logger.info("Rankings:")
        for rank, spec in enumerate(data["rankings"], 1):
            logger.info("  #{}: {:<14} score={:.3f}", rank, spec['spec_type'], spec['composite_score'])

        # 4. Submit feedback
        feedback = await client.post(
            f"{BASE_URL}/specs/feedback",
            json={
                "request_id": data["request_id"],
                "rating": 4.0,
                "comment": "Good CIAM coverage, could use more IAM federation details",
            },
        )
        logger.info("Feedback: {}", feedback.json())

        # 5. Check policy status
        status = await client.get(f"{BASE_URL}/policy/status")
        logger.info("Policy: {}", status.json())


if __name__ == "__main__":
    asyncio.run(main())
