"""Data structures of the RAG pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PolicySection:
    doc_id: str
    doc_title: str
    version: str
    section: str        # "2.2"
    title: str          # "Duplicate charge"
    text: str

    @property
    def policy_ref(self) -> str:
        return f"{self.doc_id}#{self.section}"


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source: str                         # "policy" | "case"
    text: str                           # what is embedded
    metadata: dict = field(default_factory=dict)
