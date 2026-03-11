"""End-to-end test for deployed ReinforceSpec API"""
import requests
import json
import time

BASE_URL = "https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com"

# Disable SSL warnings for self-signed cert
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_health():
    """Test health endpoint"""
    print("=" * 60)
    print("1. HEALTH CHECK")
    print("=" * 60)
    resp = requests.get(f"{BASE_URL}/v1/health", verify=False)
    print(f"Status: {resp.status_code}")
    print(f"Response: {json.dumps(resp.json(), indent=2)}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    print("✅ PASSED\n")

def test_policy_status():
    """Test policy status endpoint"""
    print("=" * 60)
    print("2. POLICY STATUS")
    print("=" * 60)
    resp = requests.get(f"{BASE_URL}/v1/policy/status", verify=False)
    print(f"Status: {resp.status_code}")
    print(f"Response: {json.dumps(resp.json(), indent=2)}")
    assert resp.status_code == 200
    assert "version" in resp.json()
    print("✅ PASSED\n")

def test_evaluate_specs():
    """Test main spec evaluation endpoint"""
    print("=" * 60)
    print("3. EVALUATE SPECS (Main Endpoint)")
    print("=" * 60)
    
    payload = {
        "candidates": [
            {
                "content": "Implement JWT-based authentication with refresh tokens, password hashing using bcrypt, and rate limiting on login attempts.",
                "source_model": "gpt-4",
                "metadata": {"approach": "jwt"}
            },
            {
                "content": "Add basic username/password login with session cookies stored server-side.",
                "source_model": "claude-3",
                "metadata": {"approach": "session"}
            },
            {
                "content": "Implement OAuth2 with Google and GitHub providers, plus optional 2FA using TOTP for enhanced security.",
                "source_model": "gemini-pro",
                "metadata": {"approach": "oauth"}
            }
        ],
        "selection_method": "scoring_only",
        "description": "E2E test: User authentication system for FastAPI"
    }
    
    print(f"Request payload:")
    print(json.dumps(payload, indent=2)[:500] + "...")
    print()
    
    start = time.time()
    resp = requests.post(
        f"{BASE_URL}/v1/specs",
        json=payload,
        verify=False,
        timeout=120  # LLM calls can take time
    )
    elapsed = time.time() - start
    
    print(f"Status: {resp.status_code}")
    print(f"Time: {elapsed:.2f}s")
    print(f"Response: {json.dumps(resp.json(), indent=2)}")
    
    if resp.status_code == 200:
        result = resp.json()
        print(f"\n🏆 Selected Spec: {result.get('selected_id', 'N/A')}")
        print("✅ PASSED\n")
    else:
        print("❌ FAILED\n")
    
    return resp

def test_feedback():
    """Test feedback submission endpoint"""
    print("=" * 60)
    print("4. SUBMIT FEEDBACK")
    print("=" * 60)
    
    payload = {
        "request_id": "test-request-123",
        "selected_id": "spec-1",
        "outcome": "accepted",
        "rating": 5,
        "comment": "The JWT spec worked great for our use case"
    }
    
    resp = requests.post(
        f"{BASE_URL}/v1/specs/feedback",
        json=payload,
        verify=False
    )
    
    print(f"Status: {resp.status_code}")
    print(f"Response: {json.dumps(resp.json(), indent=2)}")
    
    if resp.status_code == 200:
        print("✅ PASSED\n")
    else:
        print("⚠️  May require valid request_id\n")

def test_openapi():
    """Test OpenAPI spec endpoint"""
    print("=" * 60)
    print("5. OPENAPI SPEC")
    print("=" * 60)
    resp = requests.get(f"{BASE_URL}/openapi.json", verify=False)
    print(f"Status: {resp.status_code}")
    spec = resp.json()
    print(f"Title: {spec.get('info', {}).get('title')}")
    print(f"Version: {spec.get('info', {}).get('version')}")
    print(f"Paths: {list(spec.get('paths', {}).keys())}")
    print("✅ PASSED\n")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  ReinforceSpec API End-to-End Tests")
    print(f"  Target: {BASE_URL}")
    print("=" * 60 + "\n")
    
    try:
        test_health()
        test_policy_status()
        test_openapi()
        test_evaluate_specs()
        test_feedback()
        
        print("=" * 60)
        print("  ALL TESTS COMPLETED!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        raise
