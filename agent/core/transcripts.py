"""Write the conversation transcript for the analyzer (contracts/06-transcript-and-analysis.md).

The file runtime/transcripts/{session_id}.json is rewritten after every turn (ended_at/end_reason = null while
the chat is open) and finalised when the chat ends. Executed actions come from audit_log, not from here.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from agent.core.session import Session, utc_now

logger = logging.getLogger(__name__)

END_REASONS = ("resolved_by_agent", "escalated", "user_left")
CONTRACT_FIELDS = ("seq", "role", "ts", "content", "tool_calls", "name", "safety_flags")


class TranscriptWriter:
    def __init__(self, directory: Path):
        self.dir = directory

    def path_for(self, session: Session) -> Path:
        return self.dir / f"{session.session_id}.json"

    def write(self, session: Session, end_reason: str | None = None) -> Path:
        if end_reason is not None and end_reason not in END_REASONS:
            raise ValueError(f"end_reason must be one of {END_REASONS}")
        doc = {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "started_at": session.started_at,
            "ended_at": utc_now() if end_reason else None,
            "end_reason": end_reason,
            # Model reasoning ("thoughts") stays out of the shared transcript.
            "messages": [{k: e[k] for k in CONTRACT_FIELDS if k in e} for e in session.events],
        }
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.path_for(session)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        os.replace(tmp, path)   # atomic: the analyzer never reads a half-written file
        logger.info("Transcript %s written (%d messages, end_reason=%s)", path.name, len(doc["messages"]),
                    end_reason)
        return path
