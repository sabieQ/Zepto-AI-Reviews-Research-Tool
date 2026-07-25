from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

JS_DIR = Path(__file__).resolve().parent / "js"
SCRIPT = JS_DIR / "fetch_app_store_reviews.js"


def fetch_app_store_reviews(
    *,
    app_id: str,
    country: str,
    limit: int,
) -> tuple[list[dict[str, Any]], str | None]:
    """Return (rows, warning). Soft-fails with empty rows + warning when Node/Apple unavailable."""
    if not SCRIPT.exists():
        return [], f"App Store helper missing: {SCRIPT}"

    node = shutil.which("node")
    if not node:
        return [], "Node.js not found on PATH (required for App Store collector)"

    if not (JS_DIR / "node_modules" / "app-store-scraper").exists():
        return [], (
            f"app-store-scraper not installed. Run: npm install --prefix {JS_DIR}"
        )

    try:
        proc = subprocess.run(
            [
                node,
                str(SCRIPT),
                "--app-id",
                app_id,
                "--country",
                country,
                "--limit",
                str(limit),
            ],
            capture_output=True,
            text=False,
            cwd=str(JS_DIR),
            check=False,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return [], "App Store fetch timed out"
    except OSError as exc:
        return [], f"Failed to start Node helper: {exc}"

    stdout = (proc.stdout or b"").decode("utf-8", errors="replace")
    stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
    if proc.returncode != 0:
        return [], f"App Store helper failed: {(stderr or stdout)[:500]}"
    if not stdout.strip():
        return [], f"App Store helper returned empty output. {stderr[:300]}"

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return [], f"App Store helper returned invalid JSON: {exc}"

    rows: list[dict[str, Any]] = []
    for item in payload.get("reviews") or []:
        text = (item.get("text") or "").strip()
        title = (item.get("title") or "").strip()
        content = f"{title}\n{text}".strip() if title and title not in text else text
        if not content:
            continue
        review_id = str(item.get("id") or "")
        used_country = item.get("country") or country
        rows.append(
            {
                "content": content,
                "author": item.get("userName") or "",
                "rating": item.get("score"),
                "posted_at": str(item.get("updated") or ""),
                "url": item.get("url")
                or f"https://apps.apple.com/{used_country}/app/id{app_id}",
                "external_id": f"as-{review_id}" if review_id else "",
                "source": "app_store",
                "metadata": {"version": item.get("version"), "title": title},
            }
        )

    if not rows:
        return [], "App Store returned 0 reviews (endpoint flaky or no public reviews)"
    return rows[:limit], None
