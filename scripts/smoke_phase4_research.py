"""Phase 4 smoke: presets, settings, research happy/empty/validation paths.

Requires:
  - API running at API_BASE_URL (default http://127.0.0.1:8000)
  - At least one dataset with status=ready (import + index first)
  - AI_API_KEY configured for happy-path research

Optional env:
  DATASET_ID=<uuid>  — skip auto-pick of first ready dataset
"""

from __future__ import annotations

import json
import os
import sys
import uuid

import httpx

BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
DATASET_ID = os.environ.get("DATASET_ID")


def _ok(body: dict) -> bool:
    return body.get("success") is True


def main() -> int:
    failures: list[str] = []

    with httpx.Client(timeout=180.0) as client:
        # --- presets ---
        rq = client.get(f"{BASE}/api/v1/research-questions")
        rq_body = rq.json()
        print("PRESETS", rq.status_code, f"count={len(rq_body.get('data') or [])}")
        if not _ok(rq_body):
            failures.append("research-questions failed")

        # --- settings ---
        settings = client.get(f"{BASE}/api/v1/settings")
        settings_body = settings.json()
        print("SETTINGS", settings.status_code, settings_body.get("data"))
        if not _ok(settings_body):
            failures.append("get settings failed")

        bad = client.put(f"{BASE}/api/v1/settings", json={"ai_provider": "not-a-provider"})
        bad_body = bad.json()
        print("SETTINGS_INVALID", bad.status_code, bad_body.get("message"))
        if bad.status_code != 422 or bad_body.get("success") is not False:
            failures.append("expected 422 for invalid ai_provider")

        # --- resolve ready dataset ---
        dataset_id = DATASET_ID
        if not dataset_id:
            datasets = client.get(f"{BASE}/api/v1/datasets")
            ds_body = datasets.json()
            items = ds_body.get("data") or []
            ready = next((d for d in items if d.get("status") == "ready"), None)
            if not ready:
                print("SKIP research happy path: no ready dataset (import+index first)")
                dataset_id = None
            else:
                dataset_id = ready["id"]
                print("DATASET", dataset_id)

        # --- empty question validation (no report) ---
        if dataset_id:
            empty_q = client.post(
                f"{BASE}/api/v1/research",
                json={"dataset_id": dataset_id, "question": "   "},
            )
            empty_body = empty_q.json()
            print("EMPTY_QUESTION", empty_q.status_code, empty_body.get("message"))
            if empty_q.status_code != 422:
                failures.append("expected 422 for empty question")

            short_q = client.post(
                f"{BASE}/api/v1/research",
                json={"dataset_id": dataset_id, "question": "too short"},
            )
            print("SHORT_QUESTION", short_q.status_code, short_q.json().get("message"))
            if short_q.status_code != 422:
                failures.append("expected 422 for short question")

            missing_ds = client.post(
                f"{BASE}/api/v1/research",
                json={
                    "dataset_id": str(uuid.uuid4()),
                    "question": "What are the top delivery complaints from customers?",
                },
            )
            print("MISSING_DATASET", missing_ds.status_code, missing_ds.json().get("message"))
            if missing_ds.status_code != 404:
                failures.append("expected 404 for unknown dataset")

            # Empty-evidence / low-relevance: nonsense may still retrieve weak neighbors
            # (P4-RAG-015 → low confidence OK) or fail with insufficient evidence (P4-RAG-013).
            nonsense = client.post(
                f"{BASE}/api/v1/research",
                json={
                    "dataset_id": dataset_id,
                    "question": "What do customers say about quantum banana teleportation logistics?",
                },
            )
            nonsense_body = nonsense.json()
            print(
                "EMPTY_OR_WEAK_EVIDENCE",
                nonsense.status_code,
                nonsense_body.get("message"),
                "success=",
                nonsense_body.get("success"),
            )
            if nonsense.status_code >= 500:
                failures.append("empty/weak-evidence path crashed")
            elif nonsense.status_code == 200 and _ok(nonsense_body):
                conf = (nonsense_body.get("data") or {}).get("confidence")
                print("  weak-path confidence=", conf)
            elif nonsense.status_code == 400 and nonsense_body.get("success") is False:
                print("  failed as insufficient evidence (OK)")
            else:
                failures.append("unexpected empty/weak-evidence response")

            # Happy path
            happy = client.post(
                f"{BASE}/api/v1/research",
                json={
                    "dataset_id": dataset_id,
                    "question": "What are the most common customer pain points about delivery and late orders?",
                },
            )
            happy_body = happy.json()
            print("RESEARCH", happy.status_code, happy_body.get("message"))
            if happy.status_code == 200 and _ok(happy_body):
                report = happy_body.get("data") or {}
                report_id = report.get("id")
                print(
                    "REPORT",
                    report.get("status"),
                    "confidence=",
                    report.get("confidence"),
                    "evidence=",
                    len(report.get("evidence") or []),
                )
                if not report.get("question_text"):
                    failures.append("missing question_text")
                if report.get("status") != "completed":
                    failures.append("expected completed report")
                if not report.get("evidence"):
                    failures.append("expected non-empty evidence")

                got = client.get(f"{BASE}/api/v1/reports/{report_id}")
                print("GET_REPORT", got.status_code, _ok(got.json()))
                if not _ok(got.json()):
                    failures.append("get report failed")

                listed = client.get(f"{BASE}/api/v1/reports", params={"dataset_id": dataset_id})
                print("LIST_REPORTS", listed.status_code, len((listed.json().get("data") or [])))
            else:
                print("RESEARCH_BODY", json.dumps(happy_body)[:800])
                # Missing API key is an expected local skip
                msg = (happy_body.get("message") or "").lower()
                if "api_key" in msg or "api key" in msg:
                    print("SKIP happy path: AI_API_KEY not configured")
                else:
                    failures.append(f"research happy path failed: {happy_body.get('message')}")

    if failures:
        print("FAIL", failures)
        return 1
    print("OK phase4 smoke")
    return 0


if __name__ == "__main__":
    sys.exit(main())
