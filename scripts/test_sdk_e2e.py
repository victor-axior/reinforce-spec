"""End-to-end test for the ReinforceSpec SDK against production.

This test uses httpx directly with SSL verification disabled to test against
the ALB endpoint (which has a certificate for a custom domain).
It validates responses against the SDK types.
"""

import asyncio
import sys
import warnings
from datetime import datetime

import httpx

from reinforce_spec_sdk.types import (
    HealthResponse,
    PolicyStatus,
    SelectionResponse,
)


# ALB endpoint - HTTPS with SSL verification disabled for testing
BASE_URL = "https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com"

# Suppress SSL warnings for testing
warnings.filterwarnings("ignore", message="Unverified HTTPS request")


async def test_health(client: httpx.AsyncClient) -> bool:
    """Test health endpoint."""
    print("\n1. Testing health endpoint (GET /v1/health)...")
    try:
        response = await client.get("/v1/health")
        response.raise_for_status()
        data = response.json()
        
        # Validate response against SDK type
        health = HealthResponse(**data)
        print(f"   ✓ Status: {health.status}")
        print(f"   ✓ Version: {health.version}")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False


async def test_policy_status(client: httpx.AsyncClient) -> bool:
    """Test policy status endpoint."""
    print("\n2. Testing policy status (GET /v1/policy/status)...")
    try:
        response = await client.get("/v1/policy/status")
        response.raise_for_status()
        data = response.json()
        
        # Validate response against SDK type
        policy = PolicyStatus(**data)
        print(f"   ✓ Version: {policy.version}")
        print(f"   ✓ Stage: {policy.stage}")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False


async def test_select(client: httpx.AsyncClient) -> tuple[bool, str | None]:
    """Test spec selection."""
    print("\n3. Testing spec selection (POST /v1/specs)...")
    print("   This may take up to 60 seconds for LLM scoring...")
    try:
        payload = {
            "candidates": [
                {
                    "content": (
                        "# API Specification\n\n"
                        "## Authentication\n"
                        "- OAuth 2.0 with PKCE\n"
                        "- API key authentication\n"
                        "- JWT token validation\n"
                    ),
                    "source_model": "gpt-4",
                    "spec_type": "api_spec",
                },
                {
                    "content": (
                        "openapi: '3.0.3'\n"
                        "info:\n"
                        "  title: Sample API\n"
                        "  version: '1.0.0'\n"
                        "paths:\n"
                        "  /users:\n"
                        "    get:\n"
                        "      summary: List users\n"
                    ),
                    "source_model": "claude-3",
                    "spec_type": "api_spec",
                },
            ],
            "selection_method": "hybrid",
            "description": "SDK E2E test",
        }
        
        response = await client.post("/v1/specs", json=payload)
        response.raise_for_status()
        data = response.json()
        
        # Validate response against SDK type
        selection = SelectionResponse(**data)
        
        print(f"   ✓ Request ID: {selection.request_id}")
        print(f"   ✓ Selected candidate: {selection.selected.index}")
        print(f"   ✓ Composite score: {selection.selected.composite_score:.2f}")
        print(f"   ✓ Selection method: {selection.selection_method}")
        print(f"   ✓ Selection confidence: {selection.selection_confidence:.2f}")
        print(f"   ✓ Latency: {selection.latency_ms:.0f}ms")
        
        if selection.selected.dimension_scores:
            print("   ✓ Dimension scores:")
            for score in selection.selected.dimension_scores:
                print(f"      - {score.dimension}: {score.score:.1f}")
        
        return True, selection.request_id
    except httpx.HTTPStatusError as e:
        print(f"   ✗ HTTP Error: {e.response.status_code} - {e.response.text}")
        return False, None
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False, None


async def test_feedback(client: httpx.AsyncClient, request_id: str) -> bool:
    """Test feedback submission."""
    print("\n4. Testing feedback submission (POST /v1/specs/feedback)...")
    try:
        payload = {
            "request_id": request_id,
            "rating": 4.5,
            "comment": f"SDK E2E test feedback at {datetime.now().isoformat()}",
        }
        
        response = await client.post("/v1/specs/feedback", json=payload)
        response.raise_for_status()
        data = response.json()
        
        feedback_id = data.get("feedback_id")
        print(f"   ✓ Feedback ID: {feedback_id}")
        print(f"   ✓ Status: {data.get('status', 'received')}")
        return True
    except httpx.HTTPStatusError as e:
        print(f"   ✗ HTTP Error: {e.response.status_code} - {e.response.text}")
        return False
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False


async def main() -> int:
    """Run E2E tests against production."""
    print("=" * 60)
    print("ReinforceSpec SDK End-to-End Test")
    print(f"Target: {BASE_URL}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)
    print("\nNote: Using httpx with SSL verification disabled for ALB access.")

    results = []

    async with httpx.AsyncClient(
        base_url=BASE_URL,
        verify=False,  # Disable SSL verification for ALB direct access
        timeout=httpx.Timeout(timeout=120.0),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "reinforce-spec-sdk-e2e-test/1.0",
        },
    ) as client:
        # Test 1: Health
        results.append(await test_health(client))

        # Test 2: Policy status
        results.append(await test_policy_status(client))

        # Test 3: Selection
        select_ok, request_id = await test_select(client)
        results.append(select_ok)

        # Test 4: Feedback (only if selection succeeded)
        if request_id:
            results.append(await test_feedback(client, request_id))
        else:
            print("\n4. Skipping feedback test (no request_id from selection)")
            results.append(False)

    # Summary
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    status = "PASSED" if all(results) else "FAILED"
    print(f"Results: {passed}/{total} tests passed - {status}")
    print("=" * 60)

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
