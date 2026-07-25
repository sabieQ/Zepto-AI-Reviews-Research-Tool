from __future__ import annotations

import os
from pathlib import Path


class PromptError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _prompts_dir() -> Path:
    """Resolve prompts for local monorepo and Docker (PROMPTS_DIR=/prompts)."""
    env = (os.environ.get("PROMPTS_DIR") or "").strip()
    if env:
        return Path(env)

    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / "prompts",  # repo root / prompts (local)
        here.parents[2] / "prompts",  # backend / prompts
        Path("/prompts"),  # Docker default
    ]
    for path in candidates:
        if path.is_dir():
            return path
    return candidates[0]


def load_prompt(filename: str | None = None) -> str:
    """Load a prompt markdown file. Defaults to free_form_research.md."""
    name = (filename or "free_form_research.md").strip()
    if not name.endswith(".md"):
        name = f"{name}.md"
    # Prevent path traversal
    safe = Path(name).name
    path = _prompts_dir() / safe
    if not path.exists():
        if safe != "free_form_research.md":
            # Fall back to primary free-form prompt
            fallback = _prompts_dir() / "free_form_research.md"
            if fallback.exists():
                text = fallback.read_text(encoding="utf-8").strip()
                if text:
                    return text
        raise PromptError(f"Prompt file not found: {safe}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise PromptError(f"Prompt file is empty: {safe}")
    return text


def render_prompt(template: str, *, question: str, evidence: str) -> str:
    return (
        template.replace("{{question}}", question).replace("{{evidence}}", evidence)
    )
