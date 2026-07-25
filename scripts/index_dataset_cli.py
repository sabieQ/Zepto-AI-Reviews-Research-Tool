"""Reset a stuck dataset and/or run indexing locally.

Free local embeddings (no OpenRouter embedding cost):

  $env:EMBEDDING_PROVIDER="local"
  .\\backend\\.venv\\Scripts\\python.exe .\\scripts\\index_dataset_cli.py `
    --name "Zepto Public Mentions" --index --limit 40000
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402

from app.core.constants import DatasetStatus  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models import Dataset  # noqa: E402
from app.services.indexing import IndexingError, index_dataset  # noqa: E402


def _find(db, *, dataset_id: str | None, name: str | None) -> Dataset:
    if dataset_id:
        ds = db.get(Dataset, dataset_id)
        if not ds:
            raise SystemExit(f"Dataset id not found: {dataset_id}")
        return ds
    if name:
        ds = db.scalar(select(Dataset).where(Dataset.name == name).limit(1))
        if not ds:
            raise SystemExit(f"Dataset name not found: {name}")
        return ds
    raise SystemExit("Provide --id or --name")


def main() -> int:
    parser = argparse.ArgumentParser(description="Unstick / index a dataset locally")
    parser.add_argument("--id", dest="dataset_id", default=None)
    parser.add_argument("--name", default="Zepto Public Mentions")
    parser.add_argument(
        "--reset-stuck",
        action="store_true",
        help="If status is indexing, set back to imported so Index can run again",
    )
    parser.add_argument(
        "--index",
        action="store_true",
        help="Run embedding index (use EMBEDDING_PROVIDER=local to avoid API cost)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max conversations to index (e.g. 40000). Newest first.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Force EMBEDDING_PROVIDER=local for this run (free on-device embeddings)",
    )
    args = parser.parse_args()
    if not args.reset_stuck and not args.index:
        parser.error("Specify --reset-stuck and/or --index")

    if args.local:
        os.environ["EMBEDDING_PROVIDER"] = "local"
        # Settings are cached — clear so new env is picked up
        from app.core.config import get_settings

        get_settings.cache_clear()

    db = SessionLocal()
    try:
        ds = _find(db, dataset_id=args.dataset_id, name=None if args.dataset_id else args.name)
        print(
            f"Dataset: {ds.name}\n"
            f"  id={ds.id}\n"
            f"  status={ds.status}\n"
            f"  conversations={ds.conversation_count}\n"
            f"  error={ds.error_message!r}\n"
            f"  EMBEDDING_PROVIDER={os.environ.get('EMBEDDING_PROVIDER', '(from .env/default)')}",
            flush=True,
        )

        if args.reset_stuck:
            if ds.status == DatasetStatus.INDEXING:
                ds.status = DatasetStatus.IMPORTED
                ds.error_message = (
                    "Indexing was interrupted (likely Render request timeout). "
                    "Reset locally — re-run with --index."
                )
                db.commit()
                db.refresh(ds)
                print(f"Reset OK → status={ds.status}", flush=True)
            else:
                print(f"No reset needed (status is {ds.status}, not indexing)", flush=True)

        if args.index:
            db.refresh(ds)
            limit_note = f"limit={args.limit}" if args.limit else "limit=all"
            print(f"Indexing started ({limit_note})…", flush=True)
            try:
                ds = index_dataset(db, ds, conversation_limit=args.limit)
            except IndexingError as exc:
                print(f"INDEX FAILED: {exc.message}", flush=True)
                return 1
            print(
                f"INDEX OK → status={ds.status} conversations={ds.conversation_count}",
                flush=True,
            )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
