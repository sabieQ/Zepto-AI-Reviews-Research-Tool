from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import DatasetStatus, DEFAULT_TOP_K, MAX_TOP_K
from app.models import Dataset, Setting
from app.services.ai_provider import PROVIDER_BASE_URLS
from app.services.logging_service import write_log

ALLOWED_PROVIDERS = set(PROVIDER_BASE_URLS.keys())
SETTING_KEYS = ("ai_provider", "ai_model", "embedding_model", "embedding_dimensions", "top_k")


def _get_row(db: Session, key: str) -> Setting | None:
    return db.scalar(select(Setting).where(Setting.key == key))


def get_effective_settings(db: Session) -> dict[str, Any]:
    env = get_settings()
    effective: dict[str, Any] = {
        "ai_provider": env.ai_provider,
        "ai_model": env.ai_model,
        "embedding_model": env.embedding_model or "openai/text-embedding-3-small",
        "embedding_dimensions": env.embedding_dimensions,
        "top_k": DEFAULT_TOP_K,
        "ai_api_key_set": bool(env.ai_api_key.strip()),
        "reindex_required": False,
    }
    for key in SETTING_KEYS:
        row = _get_row(db, key)
        if row and isinstance(row.value, dict) and "value" in row.value:
            effective[key] = row.value["value"]

    flag = _get_row(db, "embedding_reindex_required")
    if flag and isinstance(flag.value, dict):
        effective["reindex_required"] = bool(flag.value.get("value"))
    return effective


def update_settings(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    before = get_effective_settings(db)
    embedding_changed = False

    if "ai_provider" in payload and payload["ai_provider"] is not None:
        provider = str(payload["ai_provider"]).strip().lower()
        if provider not in ALLOWED_PROVIDERS:
            raise ValueError(f"ai_provider must be one of: {', '.join(sorted(ALLOWED_PROVIDERS))}")
        _upsert(db, "ai_provider", provider)

    if "ai_model" in payload and payload["ai_model"] is not None:
        model = str(payload["ai_model"]).strip()
        if not model:
            raise ValueError("ai_model must not be empty")
        _upsert(db, "ai_model", model)

    if "embedding_model" in payload and payload["embedding_model"] is not None:
        emb = str(payload["embedding_model"]).strip()
        if not emb:
            raise ValueError("embedding_model must not be empty")
        if emb != before.get("embedding_model"):
            embedding_changed = True
        _upsert(db, "embedding_model", emb)

    if "embedding_dimensions" in payload and payload["embedding_dimensions"] is not None:
        dims = int(payload["embedding_dimensions"])
        if dims < 8 or dims > 4096:
            raise ValueError("embedding_dimensions out of range")
        if dims != int(before.get("embedding_dimensions") or 0):
            embedding_changed = True
        _upsert(db, "embedding_dimensions", dims)

    if "top_k" in payload and payload["top_k"] is not None:
        top_k = int(payload["top_k"])
        if top_k < 1 or top_k > MAX_TOP_K:
            raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}")
        _upsert(db, "top_k", top_k)

    datasets_reset = 0
    if embedding_changed:
        datasets_reset = _mark_ready_datasets_for_reindex(db)
        _upsert(db, "embedding_reindex_required", True)
        write_log(
            db,
            level="warn",
            event="embedding_settings_changed",
            message="Embedding settings changed; reindex required before research",
            context={"datasets_reset": datasets_reset},
        )

    db.commit()
    effective = get_effective_settings(db)
    effective["datasets_reset"] = datasets_reset
    if embedding_changed:
        effective["warning"] = (
            "Embedding model/dimensions changed. Ready datasets were reset to "
            "`imported`; re-index before running research."
        )
    return effective


def clear_reindex_required_flag(db: Session) -> None:
    """Call after a successful index when no ready datasets remain out of sync."""
    _upsert(db, "embedding_reindex_required", False)
    db.commit()


def _mark_ready_datasets_for_reindex(db: Session) -> int:
    result = db.execute(
        update(Dataset)
        .where(Dataset.status == DatasetStatus.READY)
        .values(
            status=DatasetStatus.IMPORTED,
            error_message="Re-index required after embedding settings change",
        )
    )
    return int(result.rowcount or 0)


def _upsert(db: Session, key: str, value: Any) -> None:
    row = _get_row(db, key)
    if row is None:
        row = Setting(id=uuid.uuid4(), key=key, value={"value": value})
        db.add(row)
    else:
        row.value = {"value": value}
