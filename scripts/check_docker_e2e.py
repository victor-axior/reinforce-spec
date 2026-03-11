from __future__ import annotations

import json
import time

import requests

BASE = "http://localhost:8000"


def main() -> None:
    print("[1/4] GET /v1/health")
    r = requests.get(f"{BASE}/v1/health", timeout=20)
    print(r.status_code, r.text)
    r.raise_for_status()

    print("[2/4] GET /v1/health/ready")
    r = requests.get(f"{BASE}/v1/health/ready", timeout=20)
    print(r.status_code, r.text)
    r.raise_for_status()

    print("[3/4] POST /v1/specs invalid payload (expect 422)")
    r = requests.post(f"{BASE}/v1/specs", json={"candidates": [{"content": "only one"}]}, timeout=30)
    print(r.status_code)
    if r.status_code != 422:
        raise RuntimeError(f"Expected 422, got {r.status_code}: {r.text}")

    print("[4/4] POST /v1/specs scoring_only")
    payload = {
        "candidates": [
            {"content": "# Spec A: Payment API\\n- OAuth2 with mTLS\\n- PCI-DSS Level 1\\n- Encryption at rest/transit"},
            {"content": "# Spec B: Payment API\\n- Basic auth\\n- No encryption"},
        ],
        "selection_method": "scoring_only",
        "description": "Payment gateway security comparison",
    }

    t0 = time.time()
    r = requests.post(f"{BASE}/v1/specs", json=payload, timeout=180)
    dt = time.time() - t0
    print(r.status_code, f"{dt:.1f}s")
    print(json.dumps(r.json(), indent=2)[:1200])
    r.raise_for_status()

    print("All endpoint checks passed.")


if __name__ == "__main__":
    main()
