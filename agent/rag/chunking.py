"""Step 3: split documents into chunks and attach metadata.

Policies: one chunk per numbered section (contracts/05 guarantees self-contained sections); a section longer
than max_chars is split by sentences with an overlap. Cases: one chunk per case (title + customer_message + summary).
"""
from __future__ import annotations

import re

from agent.rag.cleaning import clean_text
from agent.rag.models import Chunk, PolicySection

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    sentences = _SENTENCE_END.split(text)
    parts, current = [], []
    for sentence in sentences:
        if current and len(" ".join(current + [sentence])) > max_chars:
            parts.append(" ".join(current))
            current = current[-overlap:] if overlap else []
        current.append(sentence)
    if current:
        parts.append(" ".join(current))
    return parts


def chunk_policies(sections: list[PolicySection], max_chars: int, overlap: int) -> list[Chunk]:
    chunks = []
    for s in sections:
        body = clean_text(s.text)
        parts = split_sentences(body, max_chars, overlap)
        for i, part in enumerate(parts):
            suffix = f"-{i + 1}" if len(parts) > 1 else ""
            chunks.append(Chunk(
                chunk_id=f"{s.policy_ref}{suffix}", source="policy",
                text=f"{s.doc_title}. {s.section} {s.title}. {part}",
                metadata={"doc_id": s.doc_id, "section": s.section, "title": s.title, "version": s.version,
                          "policy_ref": s.policy_ref, "text": part, "part": i + 1, "parts": len(parts)}))
    return chunks


def chunk_cases(cases: list[dict]) -> list[Chunk]:
    chunks = []
    for c in cases:
        text = clean_text(f"{c['title']}. {c['customer_message']} {c['summary']}")
        chunks.append(Chunk(
            chunk_id=c["case_id"], source="case", text=text,
            metadata={"case_id": c["case_id"], "title": c["title"], "intent": c["intent"], "reason": c["reason"],
                      "plan": c.get("plan"), "resolution": c["resolution"], "actions": c.get("actions", []),
                      "policy_refs": c.get("policy_refs", []), "tags": c.get("tags", [])}))
    return chunks
