"""State of one chat: identifiers, user turn counter, model history and events for the transcript/UI."""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def new_session_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now(timezone.utc):%Y%m%d}_{secrets.token_hex(3)}"


@dataclass
class ToolEvent:
    name: str
    args: dict
    result: dict
    latency_s: float
    ts: str = field(default_factory=utc_now)


@dataclass
class Session:
    session_id: str
    user_id: str
    user_turn: int = 0
    started_at: str = field(default_factory=utc_now)
    history: list[dict] = field(default_factory=list)       # messages in OpenAI format (what the model sees)
    events: list[dict[str, Any]] = field(default_factory=list)  # ordered log for transcript and Copilot panel

    @classmethod
    def start(cls, user_id: str, prefix: str, system_prompt: str) -> "Session":
        return cls(session_id=new_session_id(prefix), user_id=user_id,
                   history=[{"role": "system", "content": system_prompt}])

    def log(self, role: str, content: Any, **extra) -> None:
        self.events.append({"seq": len(self.events) + 1, "role": role, "ts": utc_now(), "content": content, **extra})
