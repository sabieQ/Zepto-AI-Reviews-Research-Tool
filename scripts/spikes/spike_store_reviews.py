#!/usr/bin/env python3
"""Phase 7a spike: pull <=100 Zepto reviews from Google Play + App Store.

Methods:
  - Google Play: Python `google-play-scraper` (unofficial / Conditional)
  - App Store: Node `app-store-scraper` helper (unofficial / Conditional)
    Python `app-store-scraper` is broken against Apple endpoints as of 2026;
    Apple public RSS for Zepto currently returns 0 entries.

Outputs (under docs/spikes/out/):
  - google_play_reviews.csv / .json
  - app_store_reviews.csv / .json
  - combined_import.csv  (ready for Datasets → Import)

Hard caps: max 100 per store. For research only — not a production collector.

Usage (from repo root):
  backend\\.venv\\Scripts\\pip.exe install -r scripts\\spikes\\requirements-spikes.txt
  cd scripts\\spikes && npm install
  backend\\.venv\\Scripts\\python.exe scripts\\spikes\\spike_store_reviews.py
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs" / "spikes" / "out"
SPIKES_DIR = Path(__file__).resolve().parent

DEFAULT_PLAY_APP_ID = "com.zeptoconsumerapp"
DEFAULT_IOS_APP_ID = "1575323645"
MAX_PER_STORE = 100


def _iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_play(app_id: str, country: str, lang: str, limit: int) -> list[dict]:
    try:
        from google_play_scraper import Sort, reviews
    except ImportError as exc:
        raise SystemExit(
            "Missing google-play-scraper. Install:\n"
            "  pip install -r scripts/spikes/requirements-spikes.txt"
        ) from exc

    rows: list[dict] = []
    token = None
    remaining = limit
    while remaining > 0:
        batch_size = min(100, remaining)
        batch, token = reviews(
            app_id,
            lang=lang,
            country=country,
            sort=Sort.NEWEST,
            count=batch_size,
            continuation_token=token,
        )
        if not batch:
            break
        for item in batch:
            review_id = str(item.get("reviewId") or "")
            content = (item.get("content") or "").strip()
            if not content:
                continue
            at = item.get("at")
            posted = _iso(at) if isinstance(at, datetime) else str(at or "")
            rows.append(
                {
                    "content": content,
                    "author": item.get("userName") or "",
                    "rating": item.get("score"),
                    "posted_at": posted,
                    "url": f"https://play.google.com/store/apps/details?id={app_id}&hl={lang}&gl={country}",
                    "external_id": f"gp-{review_id}" if review_id else "",
                    "source": "google_play",
                    "metadata": {
                        "thumbsUpCount": item.get("thumbsUpCount"),
                        "appVersion": item.get("appVersion") or item.get("reviewCreatedVersion"),
                        "replyContent": item.get("replyContent"),
                    },
                }
            )
        remaining = limit - len(rows)
        if not token:
            break
        time.sleep(0.4)
    return rows[:limit]


def fetch_app_store(app_id: str, country: str, limit: int) -> list[dict]:
    script = SPIKES_DIR / "fetch_app_store_reviews.js"
    if not (SPIKES_DIR / "node_modules" / "app-store-scraper").exists():
        raise SystemExit(
            "Node app-store-scraper not installed. Run:\n"
            "  cd scripts/spikes && npm install"
        )
    proc = subprocess.run(
        [
            "node",
            str(script),
            "--app-id",
            app_id,
            "--country",
            country,
            "--limit",
            str(limit),
        ],
        capture_output=True,
        text=False,
        cwd=str(SPIKES_DIR),
        check=False,
    )
    stdout = (proc.stdout or b"").decode("utf-8", errors="replace")
    stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"App Store spike failed:\n{stderr or stdout}")
    if not stdout.strip():
        raise RuntimeError(f"App Store spike returned empty stdout.\n{stderr}")
    payload = json.loads(stdout)
    rows: list[dict] = []
    for item in payload.get("reviews") or []:
        text = (item.get("text") or "").strip()
        title = (item.get("title") or "").strip()
        content = f"{title}\n{text}".strip() if title and title not in text else text
        if not content:
            continue
        review_id = str(item.get("id") or "")
        rows.append(
            {
                "content": content,
                "author": item.get("userName") or "",
                "rating": item.get("score"),
                "posted_at": str(item.get("updated") or ""),
                "url": item.get("url")
                or f"https://apps.apple.com/{country}/app/id{app_id}",
                "external_id": f"as-{review_id}" if review_id else "",
                "source": "app_store",
                "metadata": {"version": item.get("version"), "title": title},
            }
        )
    return rows[:limit]


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = ["content", "author", "rating", "posted_at", "url", "external_id", "source"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def write_json(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def summarize(name: str, rows: list[dict]) -> None:
    ratings = [r.get("rating") for r in rows if isinstance(r.get("rating"), (int, float))]
    avg = (sum(ratings) / len(ratings)) if ratings else None
    print(f"[{name}] count={len(rows)} avg_rating={avg!s}")
    if rows:
        sample = rows[0]["content"].replace("\n", " ")[:100]
        print(f"[{name}] sample: {sample}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 7a Play + App Store review spike")
    parser.add_argument("--play-app-id", default=DEFAULT_PLAY_APP_ID)
    parser.add_argument("--ios-app-id", default=DEFAULT_IOS_APP_ID)
    parser.add_argument("--country", default="in")
    parser.add_argument("--lang", default="en")
    parser.add_argument("--limit", type=int, default=50, help="Per store, max 100")
    parser.add_argument("--skip-play", action="store_true")
    parser.add_argument("--skip-ios", action="store_true")
    args = parser.parse_args()

    limit = max(1, min(args.limit, MAX_PER_STORE))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    play_rows: list[dict] = []
    ios_rows: list[dict] = []

    if not args.skip_play:
        print(f"Fetching Google Play reviews for {args.play_app_id} ({args.country})…")
        play_rows = fetch_play(args.play_app_id, args.country, args.lang, limit)
        summarize("google_play", play_rows)
        write_csv(OUT_DIR / "google_play_reviews.csv", play_rows)
        write_json(OUT_DIR / "google_play_reviews.json", play_rows)

    if not args.skip_ios:
        print(f"Fetching App Store reviews for {args.ios_app_id} ({args.country})…")
        try:
            ios_rows = fetch_app_store(args.ios_app_id, args.country, limit)
        except Exception as exc:  # noqa: BLE001
            print(f"[app_store] FAILED: {exc}")
            print(
                "See docs/phase-7-user-guide.md for App Store Connect (official) fallback."
            )
            ios_rows = []
        summarize("app_store", ios_rows)
        write_csv(OUT_DIR / "app_store_reviews.csv", ios_rows)
        write_json(OUT_DIR / "app_store_reviews.json", ios_rows)

    combined = play_rows + ios_rows
    write_csv(OUT_DIR / "combined_import.csv", combined)
    write_json(OUT_DIR / "combined_import.json", combined)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "play_app_id": args.play_app_id,
        "ios_app_id": args.ios_app_id,
        "country": args.country,
        "limit_per_store": limit,
        "counts": {
            "google_play": len(play_rows),
            "app_store": len(ios_rows),
            "combined": len(combined),
        },
        "methods": {
            "google_play": "python google-play-scraper (unofficial Conditional)",
            "app_store": "node app-store-scraper (unofficial Conditional)",
        },
        "outputs": {
            "combined_csv": str(OUT_DIR / "combined_import.csv"),
        },
        "next_step": "Import combined_import.csv into a dataset via UI or POST /import",
    }
    (OUT_DIR / "spike_summary.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["counts"], indent=2))
    print(f"Wrote {OUT_DIR / 'combined_import.csv'}")
    return 0 if combined else 1


if __name__ == "__main__":
    sys.exit(main())
