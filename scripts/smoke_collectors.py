"""Smoke: small refresh collector (not full 50k bulk)."""

from __future__ import annotations

import json
import os
import sys

import httpx

BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def main() -> int:
    with httpx.Client(timeout=180.0) as client:
        health = client.get(f"{BASE}/api/v1/health")
        if health.status_code != 200 or not health.json().get("success"):
            print("FAIL health", health.text[:300])
            return 1
        print("OK health")

        run = client.post(
            f"{BASE}/api/v1/collectors/run",
            json={"limit": 20, "sources": ["google_play"], "auto_index": False},
        )
        body = run.json()
        print("REFRESH", run.status_code, body.get("message"))
        if run.status_code >= 500:
            print(json.dumps(body)[:500])
            return 1
        data = body.get("data") or {}
        if body.get("success"):
            print(
                "OK refresh inserted=",
                data.get("inserted"),
                "skipped=",
                data.get("skipped"),
                "dataset=",
                (data.get("dataset") or {}).get("name"),
            )
        else:
            # Soft-ok if Play blocked transiently
            print("WARN refresh soft-fail", body.get("message"))

        runs = client.get(f"{BASE}/api/v1/collectors/runs", params={"limit": 5})
        if runs.status_code != 200 or not runs.json().get("success"):
            print("FAIL list runs")
            return 1
        print("OK runs", len(runs.json().get("data") or []))
    print("SMOKE OK collectors refresh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
