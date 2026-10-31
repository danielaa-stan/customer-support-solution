"""Pre-LLM screening: detect distress, legal threats and prompt injection before the model sees a message.

Patterns and actions live in config/safety.toml, never in code.
"""
from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

logger = logging.getLogger(__name__)

HANDOVER = "handover"
WARN_MODEL = "warn_model"


@dataclass(frozen=True)
class Category:
    name: str
    action: str
    patterns: tuple[re.Pattern, ...]
    reply_prompt: str | None = None
    note_prompt: str | None = None
    priority: str | None = None
    escalation_category: str | None = None


@dataclass(frozen=True)
class ScreeningResult:
    matched: tuple[Category, ...] = ()

    @property
    def handover(self) -> Category | None:
        """The first matched category that requires a human (config order = priority)."""
        return next((c for c in self.matched if c.action == HANDOVER), None)

    @property
    def model_notes(self) -> list[str]:
        return [c.note_prompt for c in self.matched if c.action == WARN_MODEL and c.note_prompt]

    @property
    def names(self) -> list[str]:
        return [c.name for c in self.matched]


class MessageScreener:
    def __init__(self, categories: list[Category]):
        self.categories = categories

    @classmethod
    def from_file(cls, path: Path) -> "MessageScreener":
        with open(path, "rb") as f:
            raw = tomllib.load(f)
        categories = []
        for name, c in raw.get("categories", {}).items():
            if c.get("action") not in (HANDOVER, WARN_MODEL):
                raise ValueError(f"safety category '{name}': unknown action {c.get('action')!r}")
            categories.append(Category(
                name=name, action=c["action"],
                patterns=tuple(re.compile(p, re.IGNORECASE) for p in c.get("patterns", [])),
                reply_prompt=c.get("reply_prompt"), note_prompt=c.get("note_prompt"),
                priority=c.get("priority"), escalation_category=c.get("escalation_category")))
        return cls(categories)

    def screen(self, text: str) -> ScreeningResult:
        matched = tuple(c for c in self.categories if any(p.search(text) for p in c.patterns))
        if matched:
            logger.warning("Screening matched %s", [c.name for c in matched])
        return ScreeningResult(matched)
