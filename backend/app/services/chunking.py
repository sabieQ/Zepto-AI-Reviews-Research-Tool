"""Split conversation text into overlapping chunks for embedding."""

from __future__ import annotations

CHUNK_SIZE = 700
CHUNK_OVERLAP = 80


def chunk_text(text: str, *, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    if len(cleaned) <= size:
        return [cleaned]

    if overlap >= size:
        overlap = max(0, size // 5)

    chunks: list[str] = []
    start = 0
    length = len(cleaned)
    while start < length:
        end = min(start + size, length)
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start = end - overlap
        if start < 0:
            start = 0
        # Safety against infinite loop
        if chunks and start >= length:
            break
        if len(chunks) > 10_000:
            break
    return chunks
