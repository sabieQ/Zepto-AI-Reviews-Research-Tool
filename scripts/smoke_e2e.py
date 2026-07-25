"""Phase 6 E2E smoke: happy path + negatives.

Requires API running and AI_API_KEY for the happy-path research/index steps.

  set API_BASE_URL=http://127.0.0.1:8000
  python scripts/smoke_e2e.py

Exits non-zero on first hard failure (P6-OPS-001).
"""

from __future__ import annotations

import io
import json
import os
import sys
import uuid
from pathlib import Path

import httpx

BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = ROOT / "scripts" / "sample_conversations.csv"
TIMEOUT = httpx.Timeout(180.0, connect=30.0)


class StepError(Exception):
    def __init__(self, step: str, detail: str):
        super().__init__(f"[{step}] {detail}")
        self.step = step
        self.detail = detail


def _json(resp: httpx.Response) -> dict:
    try:
        return resp.json()
    except Exception:  # noqa: BLE001
        return {}


def expect_ok(step: str, resp: httpx.Response) -> dict:
    body = _json(resp)
    if resp.status_code >= 400 or body.get("success") is not True:
        raise StepError(step, f"HTTP {resp.status_code}: {body.get('message') or resp.text[:300]}")
    return body


def expect_status(step: str, resp: httpx.Response, codes: set[int], *, success: bool | None = None) -> dict:
    body = _json(resp)
    if resp.status_code not in codes:
        raise StepError(step, f"expected {codes}, got {resp.status_code}: {body.get('message') or resp.text[:300]}")
    if success is not None and body.get("success") is not success:
        raise StepError(step, f"expected success={success}, body={body}")
    return body


def main() -> int:
    failures: list[str] = []
    dataset_id: str | None = None
    report_id: str | None = None

    print(f"API_BASE_URL={BASE}")

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            # --- Phase 1 ---
            health = client.get(f"{BASE}/api/v1/health")
            body = expect_ok("health", health)
            print("OK health", body.get("data", {}).get("status"))

            missing = client.get(f"{BASE}/api/v1/does-not-exist")
            expect_status("404-envelope", missing, {404}, success=False)
            print("OK 404 envelope")

            # --- Negatives (settings / validation) ---
            bad_settings = client.put(
                f"{BASE}/api/v1/settings",
                json={"ai_provider": "not-a-provider"},
            )
            expect_status("invalid-settings", bad_settings, {422}, success=False)
            print("OK invalid settings -> 422")

            # --- Create dataset ---
            created = client.post(
                f"{BASE}/api/v1/datasets",
                json={
                    "name": f"smoke-e2e-{uuid.uuid4().hex[:8]}",
                    "source": "csv",
                    "description": "Phase 6 smoke",
                },
            )
            cbody = expect_ok("create-dataset", created)
            dataset_id = cbody["data"]["id"]
            print("OK create dataset", dataset_id)

            # --- Negative: bad CSV ---
            bad_csv = ("author,rating\n" "alice,5\n").encode("utf-8")
            bad_import = client.post(
                f"{BASE}/api/v1/import",
                data={"dataset_id": dataset_id, "auto_index": "false"},
                files={"file": ("bad.csv", io.BytesIO(bad_csv), "text/csv")},
            )
            expect_status("bad-csv", bad_import, {400, 422}, success=False)
            print("OK bad CSV rejected")

            # --- Import sample ---
            if not SAMPLE_CSV.exists():
                raise StepError("import", f"sample CSV missing: {SAMPLE_CSV}")
            with SAMPLE_CSV.open("rb") as fh:
                imported = client.post(
                    f"{BASE}/api/v1/import",
                    data={"dataset_id": dataset_id, "auto_index": "true"},
                    files={"file": ("sample_conversations.csv", fh, "text/csv")},
                )
            ibody = expect_ok("import", imported)
            print("OK import", ibody.get("message"))

            # Wait / poll for ready (auto-index)
            status = "imported"
            reindex_attempted = False
            for _ in range(60):
                detail = client.get(f"{BASE}/api/v1/datasets/{dataset_id}")
                dbody = expect_ok("poll-dataset", detail)
                status = dbody["data"]["status"]
                print("  status=", status)
                if status == "ready":
                    break
                if status == "failed":
                    err = dbody["data"].get("error_message") or "indexing failed"
                    if "API_KEY" in err or "api key" in err.lower():
                        raise StepError("index", err + " - set AI_API_KEY in backend/.env")
                    raise StepError("index", err)
                if status == "imported" and not reindex_attempted:
                    reindex_attempted = True
                    client.post(f"{BASE}/api/v1/datasets/{dataset_id}/reindex")
                import time

                time.sleep(2)
            if status != "ready":
                raise StepError("index", f"dataset not ready (status={status})")
            print("OK indexed ready")

            # --- Negatives: research validation ---
            empty_q = client.post(
                f"{BASE}/api/v1/research",
                json={"dataset_id": dataset_id, "question": ""},
            )
            expect_status("empty-question", empty_q, {422}, success=False)
            print("OK empty question -> 422")

            missing_ds = client.post(
                f"{BASE}/api/v1/research",
                json={
                    "dataset_id": str(uuid.uuid4()),
                    "question": "What are the most common delivery pain points?",
                },
            )
            expect_status("missing-dataset", missing_ds, {404}, success=False)
            print("OK missing dataset -> 404")

            # Low-relevance / empty-evidence path (may fail or complete low - assert no 500)
            weak = client.post(
                f"{BASE}/api/v1/research",
                json={
                    "dataset_id": dataset_id,
                    "question": "Quantum banana teleportation logistics for zepto customers?",
                },
            )
            if weak.status_code >= 500:
                raise StepError("weak-research", f"server error: {weak.text[:300]}")
            wbody = _json(weak)
            if wbody.get("success") is False:
                # Prefer failed report with retrieval error (P6-OPS-003)
                errs = wbody.get("errors") or []
                print("OK weak research failed cleanly:", wbody.get("message"))
                for err in errs:
                    if isinstance(err, dict) and err.get("code") == "research_failed":
                        failed_id = (err.get("report") or {}).get("id")
                        if failed_id:
                            exp = client.get(
                                f"{BASE}/api/v1/reports/{failed_id}/export",
                                params={"format": "md"},
                            )
                            expect_status("export-failed-report", exp, {400}, success=False)
                            print("OK export failed report -> 400")
            else:
                print("OK weak research completed with low confidence (acceptable P4-RAG-015)")

            # --- Happy path research ---
            question = "What are the most common customer pain points about delivery and late orders?"
            research = client.post(
                f"{BASE}/api/v1/research",
                json={"dataset_id": dataset_id, "question": question},
            )
            rbody = expect_ok("research", research)
            report = rbody["data"]
            report_id = report["id"]
            if report.get("status") != "completed":
                raise StepError("research", f"expected completed, got {report.get('status')}")
            if report.get("question_text") != question:
                raise StepError("research", "question_text mismatch")
            if not report.get("evidence"):
                raise StepError("research", "expected evidence citations")
            print("OK research completed", report_id, "confidence=", report.get("confidence"))

            got = client.get(f"{BASE}/api/v1/reports/{report_id}")
            expect_ok("get-report", got)
            print("OK get report")

            export = client.get(
                f"{BASE}/api/v1/reports/{report_id}/export",
                params={"format": "md"},
            )
            if export.status_code != 200:
                raise StepError("export-md", f"HTTP {export.status_code}: {export.text[:300]}")
            text = export.text
            if "Evidence" not in text and "question" not in text.lower():
                raise StepError("export-md", "markdown missing expected sections")
            print("OK export markdown", len(text), "bytes")

            # --- Delete report then dataset ---
            deleted_report = client.delete(f"{BASE}/api/v1/reports/{report_id}")
            expect_ok("delete-report", deleted_report)
            print("OK delete report")

            deleted_ds = client.delete(f"{BASE}/api/v1/datasets/{dataset_id}")
            expect_ok("delete-dataset", deleted_ds)
            print("OK delete dataset (cascade)")

            gone = client.get(f"{BASE}/api/v1/datasets/{dataset_id}")
            expect_status("dataset-gone", gone, {404}, success=False)
            print("OK dataset 404 after delete")

            dataset_id = None
            report_id = None

    except StepError as exc:
        print("FAIL", exc)
        failures.append(str(exc))
    except Exception as exc:  # noqa: BLE001
        print("FAIL unexpected", exc)
        failures.append(str(exc))
    finally:
        # Best-effort cleanup if mid-path failed
        if dataset_id:
            try:
                with httpx.Client(timeout=30.0) as client:
                    client.delete(f"{BASE}/api/v1/datasets/{dataset_id}")
                    print("cleanup deleted dataset", dataset_id)
            except Exception:  # noqa: BLE001
                pass

    if failures:
        print("SMOKE FAILED", json.dumps(failures))
        return 1
    print("SMOKE OK phase6 e2e")
    return 0


if __name__ == "__main__":
    sys.exit(main())
