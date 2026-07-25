"""One-shot Play-first bulk backfill (measured run toward 100k).

Usage (from repo root, backend venv active, DATABASE_URL set):

  cd backend
  alembic upgrade head
  ..\\.venv\\Scripts\\python.exe ..\\scripts\\bulk_backfill_reviews.py --target 100000

Options:
  --target 100000
  --country in
  --no-app-store
  --auto-index   (off by default; indexing large corpora needs time + AI quota)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal  # noqa: E402
from app.services.collectors.bulk import run_bulk_backfill  # noqa: E402
from app.services.import_service import get_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Zepto store review bulk backfill")
    parser.add_argument("--target", type=int, default=100_000)
    parser.add_argument("--country", default="in")
    parser.add_argument("--lang", default="en")
    parser.add_argument("--no-app-store", action="store_true")
    parser.add_argument("--auto-index", action="store_true")
    parser.add_argument(
        "--play-countries",
        default="in,us",
        help="Comma-separated Play country codes to try (default in,us)",
    )
    args = parser.parse_args()
    countries = [c.strip() for c in args.play_countries.split(",") if c.strip()]

    def on_progress(entry: dict) -> None:
        print(
            f"  checkpoint inserted={entry.get('inserted')} "
            f"skipped={entry.get('skipped')} "
            f"play_fetched={entry.get('play_fetched')} "
            f"count={entry.get('conversation_count')} "
            f"| {entry.get('note')}",
            flush=True,
        )

    print(
        f"Starting bulk backfill target={args.target} "
        f"countries={countries} app_store={not args.no_app_store}",
        flush=True,
    )

    db = SessionLocal()
    try:
        run = run_bulk_backfill(
            db,
            target=args.target,
            country=args.country,
            lang=args.lang,
            include_app_store=not args.no_app_store,
            auto_index=args.auto_index,
            play_countries=countries,
            on_progress=on_progress,
        )
        ds = get_dataset(db, run.dataset_id)
        report = {
            "run_id": str(run.id),
            "status": run.status,
            "inserted": run.inserted,
            "skipped": run.skipped,
            "error_message": run.error_message,
            "dataset_id": str(run.dataset_id),
            "dataset_name": ds.name if ds else None,
            "conversation_count": ds.conversation_count if ds else None,
            "dataset_status": ds.status if ds else None,
            "context": run.context,
        }
        out = ROOT / "docs" / "spikes" / "out" / "bulk_backfill_report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(json.dumps(report, indent=2, default=str))
        print(f"Wrote {out}")
        target_met = bool((run.context or {}).get("target_met"))
        if run.status != "completed":
            return 1
        if not target_met:
            print(
                "NOTE: Platform ceiling reached before target. "
                "This is the measured max for this method — not a script failure.",
                flush=True,
            )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
