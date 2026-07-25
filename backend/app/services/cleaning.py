import hashlib
import html
import re
from datetime import datetime
from typing import Any

from app.core.constants import MAX_CONTENT_CHARS

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def strip_html(value: str) -> str:
    # Remove tags first so script bodies are not kept as text unexpectedly in simple cases
    no_tags = _TAG_RE.sub(" ", value)
    return html.unescape(no_tags)


def normalize_whitespace(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value).strip()


def clean_content(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = str(raw)
    text = _CONTROL_RE.sub("", text)
    text = strip_html(text)
    text = normalize_whitespace(text)
    if not text:
        return None
    if len(text) > MAX_CONTENT_CHARS:
        text = text[:MAX_CONTENT_CHARS]
    return text


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parse_rating(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        rating = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    if rating < 1 or rating > 5:
        return None
    return rating


def parse_posted_at(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if not text:
        return None
    # Support trailing Z
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def parse_url(value: Any) -> str | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if not text:
        return None
    if not (text.startswith("http://") or text.startswith("https://")):
        return None
    return text[:2000]


def optional_str(value: Any, max_len: int = 500) -> str | None:
    if value is None:
        return None
    text = normalize_whitespace(str(value))
    if not text:
        return None
    return text[:max_len]
