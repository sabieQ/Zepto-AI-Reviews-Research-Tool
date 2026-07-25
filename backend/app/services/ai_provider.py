"""OpenAI-compatible AI provider (embeddings + chat) with optional free local embeddings."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger("zepto")

PROVIDER_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "openai_compatible": "",  # must set AI_BASE_URL
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
}

DEFAULT_EMBEDDING_MODELS = {
    "openrouter": "openai/text-embedding-3-small",
    "openai": "text-embedding-3-small",
    "openai_compatible": "text-embedding-3-small",
    "groq": "text-embedding-3-small",  # may be unavailable on Groq
    "gemini": "text-embedding-004",
}

_local_model = None


class AIProviderError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def embedding_uses_remote_api(*, provider: str | None = None) -> bool:
    settings = get_settings()
    mode = (provider or settings.embedding_provider or "remote").strip().lower()
    return mode not in {"local", "fastembed", "offline"}


def resolve_base_url(*, provider: str | None = None, base_url: str | None = None) -> str:
    settings = get_settings()
    if base_url and base_url.strip():
        return base_url.strip().rstrip("/")
    if settings.ai_base_url.strip():
        return settings.ai_base_url.strip().rstrip("/")
    resolved_provider = (provider or settings.ai_provider).strip().lower()
    base = PROVIDER_BASE_URLS.get(resolved_provider, "")
    if not base:
        raise AIProviderError(
            f"AI_BASE_URL is required for provider '{resolved_provider}'",
        )
    return base


def resolve_embedding_model(*, model: str | None = None, provider: str | None = None) -> str:
    settings = get_settings()
    if not embedding_uses_remote_api():
        return (model or settings.local_embedding_model or "").strip() or (
            "sentence-transformers/all-MiniLM-L6-v2"
        )
    if model and model.strip():
        return model.strip()
    if settings.embedding_model.strip():
        return settings.embedding_model.strip()
    resolved_provider = (provider or settings.ai_provider).strip().lower()
    return DEFAULT_EMBEDDING_MODELS.get(resolved_provider, "text-embedding-3-small")


def _headers(*, provider: str | None = None) -> dict[str, str]:
    settings = get_settings()
    if not settings.ai_api_key.strip():
        raise AIProviderError(
            "AI_API_KEY is missing. Add your OpenRouter (or OpenAI/Gemini) API key to backend/.env",
        )
    headers = {
        "Authorization": f"Bearer {settings.ai_api_key.strip()}",
        "Content-Type": "application/json",
    }
    resolved_provider = (provider or settings.ai_provider).strip().lower()
    if resolved_provider == "openrouter":
        headers["HTTP-Referer"] = settings.frontend_url
        headers["X-Title"] = "Zepto AI Product Research Assistant"
    return headers


def _pad_or_trim(vector: list[float], expected_dim: int) -> list[float]:
    if len(vector) == expected_dim:
        return vector
    if len(vector) > expected_dim:
        return vector[:expected_dim]
    return vector + [0.0] * (expected_dim - len(vector))


def _get_local_model():
    global _local_model
    if _local_model is not None:
        return _local_model
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise AIProviderError(
            "Local embeddings require fastembed. Run: pip install fastembed"
        ) from exc
    settings = get_settings()
    name = settings.local_embedding_model.strip() or (
        "sentence-transformers/all-MiniLM-L6-v2"
    )
    logger.info("Loading local embedding model %s (first run may download)", name)
    _local_model = TextEmbedding(model_name=name)
    return _local_model


def _embed_local(texts: list[str], *, expected_dim: int, batch_size: int) -> list[list[float]]:
    model = _get_local_model()
    all_vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        try:
            raw = list(model.embed(batch))
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(f"Local embedding failed: {exc}") from exc
        if len(raw) != len(batch):
            raise AIProviderError(
                f"Local embedding count mismatch: expected {len(batch)}, got {len(raw)}"
            )
        for item in raw:
            vec = [float(v) for v in item]
            all_vectors.append(_pad_or_trim(vec, expected_dim))
    return all_vectors


def embed(
    texts: list[str],
    *,
    batch_size: int = 32,
    model: str | None = None,
    dimensions: int | None = None,
    provider: str | None = None,
) -> list[list[float]]:
    """Return embeddings for texts (remote API or free local ONNX)."""
    if not texts:
        return []

    settings = get_settings()
    expected_dim = dimensions if dimensions is not None else settings.embedding_dimensions

    if not embedding_uses_remote_api():
        # Local MiniLM is 384-d; pad to schema dim (1536) — cosine stays consistent.
        return _embed_local(texts, expected_dim=expected_dim, batch_size=max(8, batch_size))

    resolved_model = resolve_embedding_model(model=model, provider=provider)
    url = f"{resolve_base_url(provider=provider)}/embeddings"
    headers = _headers(provider=provider)

    all_vectors: list[list[float] | None] = [None] * len(texts)

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        payload: dict[str, Any] = {"model": resolved_model, "input": batch}
        if "text-embedding-3" in resolved_model or resolved_model.endswith("embedding-3-small"):
            payload["dimensions"] = expected_dim

        data = _post_with_retries(url, headers=headers, payload=payload, timeout=60.0)
        items = data.get("data")
        if not isinstance(items, list):
            raise AIProviderError("Invalid embeddings response: missing data[]")

        items_sorted = sorted(items, key=lambda x: int(x.get("index", 0)))
        if len(items_sorted) != len(batch):
            raise AIProviderError(
                f"Embedding count mismatch: expected {len(batch)}, got {len(items_sorted)}",
            )

        for offset, item in enumerate(items_sorted):
            vector = item.get("embedding")
            if not isinstance(vector, list) or not vector:
                raise AIProviderError("Empty or invalid embedding vector returned")
            if any(not isinstance(v, (int, float)) for v in vector):
                raise AIProviderError("Embedding contains non-numeric values")
            if len(vector) != expected_dim:
                raise AIProviderError(
                    f"Embedding dimension mismatch: got {len(vector)}, "
                    f"expected {expected_dim}. Set EMBEDDING_DIMENSIONS to match the model "
                    f"or use openai/text-embedding-3-small.",
                )
            all_vectors[start + offset] = [float(v) for v in vector]

    return [v for v in all_vectors if v is not None]  # type: ignore[misc]


def chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    model: str | None = None,
    provider: str | None = None,
) -> str:
    """Chat completion for research reports (OpenAI-compatible)."""
    settings = get_settings()
    resolved_model = (model or settings.ai_model).strip() or "openai/gpt-4o-mini"
    url = f"{resolve_base_url(provider=provider)}/chat/completions"
    headers = _headers(provider=provider)
    payload = {
        "model": resolved_model,
        "messages": messages,
        "temperature": temperature,
    }
    data = _post_with_retries(url, headers=headers, payload=payload, timeout=120.0)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIProviderError("Invalid chat completion response") from exc
    if content is None or (isinstance(content, str) and not content.strip()):
        raise AIProviderError("LLM returned empty content")
    return content if isinstance(content, str) else str(content)


def _post_with_retries(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    max_attempts: int = 4,
    timeout: float = 60.0,
) -> dict[str, Any]:
    last_error = "unknown error"
    for attempt in range(max_attempts):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            last_error = "AI provider request timed out"
            if attempt + 1 >= max_attempts:
                raise AIProviderError(last_error, status_code=504) from exc
            time.sleep(min(2**attempt, 8))
            continue
        except httpx.HTTPError as exc:
            last_error = str(exc)
            if attempt + 1 >= max_attempts:
                raise AIProviderError(f"AI provider request failed: {last_error}") from exc
            time.sleep(min(2**attempt, 8))
            continue

        if response.status_code == 429:
            last_error = (
                "AI provider rate limit reached (429). Wait a minute, or switch "
                "provider/model in Settings / backend .env."
            )
            if attempt + 1 >= max_attempts:
                raise AIProviderError(last_error, status_code=429)
            time.sleep(min(2**attempt, 8))
            continue

        if response.status_code >= 500:
            last_error = f"AI provider error {response.status_code}"
            if attempt + 1 >= max_attempts:
                raise AIProviderError(last_error, status_code=response.status_code)
            time.sleep(min(2**attempt, 8))
            continue

        if response.status_code >= 400:
            detail = response.text[:400]
            raise AIProviderError(
                f"AI provider error {response.status_code}: {detail}",
                status_code=response.status_code,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise AIProviderError("AI provider returned non-JSON response") from exc

    raise AIProviderError(last_error)
