"""Phase 1 smoke: health + 404 envelope."""

from __future__ import annotations

import json
import os
import sys

import httpx

BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def main() -> int:
    with httpx.Client(timeout=10.0) as client:
        health = client.get(f"{BASE}/api/v1/health")
        print("HEALTH", health.status_code, health.text)
        body = health.json()
        if "success" not in body:
            print("FAIL: health missing success envelope")
            return 1

        missing = client.get(f"{BASE}/api/v1/does-not-exist")
        print("NOTFOUND", missing.status_code, missing.text)
        missing_body = missing.json()
        if missing.status_code != 404 or missing_body.get("success") is not False:
            print("FAIL: expected 404 envelope")
            return 1

    print("OK", json.dumps({"health_success": body.get("success")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
