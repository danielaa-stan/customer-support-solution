"""Prompt texts are stored as files in config/prompts/<name>.md, never in code."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path


class PromptLibrary:
    def __init__(self, prompts_dir: Path):
        self.dir = prompts_dir

    @lru_cache(maxsize=None)
    def get(self, name: str) -> str:
        path = self.dir / f"{name}.md"
        if not path.is_file():
            raise FileNotFoundError(f"Prompt '{name}' not found: {path}")
        return path.read_text(encoding="utf-8").strip()
