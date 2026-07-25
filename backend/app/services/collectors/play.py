from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from typing import Any

ProgressCb = Callable[[dict[str, Any]], None]


def _iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _row_from_item(item: dict[str, Any], *, app_id: str, country: str, lang: str) -> dict[str, Any] | None:
    review_id = str(item.get("reviewId") or "")
    content = (item.get("content") or "").strip()
    if not content:
        return None
    at = item.get("at")
    posted = _iso(at) if isinstance(at, datetime) else str(at or "")
    return {
        "content": content,
        "author": item.get("userName") or "",
        "rating": item.get("score"),
        "posted_at": posted,
        "url": (
            f"https://play.google.com/store/apps/details?id={app_id}"
            f"&hl={lang}&gl={country}"
        ),
        "external_id": f"gp-{review_id}" if review_id else "",
        "source": "google_play",
        "metadata": {
            "thumbsUpCount": item.get("thumbsUpCount"),
            "appVersion": item.get("appVersion") or item.get("reviewCreatedVersion"),
            "country": country,
            "lang": lang,
        },
    }


def iter_play_review_batches(
    *,
    app_id: str,
    country: str,
    lang: str,
    limit: int,
    sort_name: str = "newest",
    batch_size: int = 100,
    sleep_s: float = 0.4,
    on_progress: ProgressCb | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """Yield batches of normalized Play reviews until limit or platform stops."""
    try:
        from google_play_scraper import Sort, reviews
    except ImportError as exc:
        raise RuntimeError(
            "google-play-scraper is not installed. pip install google-play-scraper"
        ) from exc

    sort_map = {
        "newest": Sort.NEWEST,
        "most_relevant": Sort.MOST_RELEVANT,
        "rating": Sort.RATING,
    }
    sort = sort_map.get(sort_name.lower(), Sort.NEWEST)

    token = None
    yielded = 0
    page = 0
    while yielded < limit:
        need = min(batch_size, limit - yielded)
        try:
            batch, token = reviews(
                app_id,
                lang=lang,
                country=country,
                sort=sort,
                count=need,
                continuation_token=token,
            )
        except Exception:
            break
        if not batch:
            break
        page += 1
        rows: list[dict[str, Any]] = []
        for item in batch:
            row = _row_from_item(item, app_id=app_id, country=country, lang=lang)
            if row:
                rows.append(row)
        if not rows:
            if not token:
                break
            time.sleep(sleep_s)
            continue
        yielded += len(rows)
        if on_progress:
            on_progress(
                {
                    "sort": sort_name,
                    "country": country,
                    "page": page,
                    "batch": len(rows),
                    "yielded": yielded,
                }
            )
        yield rows
        if not token:
            break
        time.sleep(sleep_s)


def fetch_play_reviews(
    *,
    app_id: str,
    country: str,
    lang: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Small refresh helper — collect up to `limit` newest reviews into memory."""
    rows: list[dict[str, Any]] = []
    for batch in iter_play_review_batches(
        app_id=app_id,
        country=country,
        lang=lang,
        limit=limit,
        sort_name="newest",
    ):
        rows.extend(batch)
        if len(rows) >= limit:
            break
    return rows[:limit]
