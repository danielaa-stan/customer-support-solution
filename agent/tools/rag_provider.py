"""Local RAG tools (search_policy, find_similar_cases) exposed to the model like MCP tools."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from agent.rag.retriever import RetrievalResult, Retriever
from agent.tools.base import ToolResult, ToolSpec

logger = logging.getLogger(__name__)


def _envelope(r: RetrievalResult) -> ToolResult:
    return ToolResult(ok=True, status="done", data={"results": r.results, "kb_gap": r.kb_gap})


class RAGToolProvider:
    name = "rag"

    def __init__(self, retriever: Retriever, tools_file: Path):
        self.retriever = retriever
        self._specs = [ToolSpec(t["name"], t["description"], t["parameters"])
                       for t in json.loads(tools_file.read_text(encoding="utf-8"))]
        self._handlers = {"search_policy": self._search_policy, "find_similar_cases": self._find_similar_cases}
        unknown = {s.name for s in self._specs} - self._handlers.keys()
        if unknown:
            raise ValueError(f"{tools_file.name} describes tools without a handler: {unknown}")

    def list_tools(self) -> list[ToolSpec]:
        return list(self._specs)

    def call(self, name: str, args: dict) -> ToolResult:
        query = str(args.get("query", "")).strip()
        if not query:
            return ToolResult.failure("INVALID_ARGUMENT", "query is required")
        return self._handlers[name](query, args)

    def set_context(self, session_id: str, user_id: str, user_turn: int) -> None:
        """RAG is the same for every customer."""

    def _search_policy(self, query: str, args: dict) -> ToolResult:
        return _envelope(self.retriever.search_policy(query, args.get("top_k"), args.get("doc_id")))

    def _find_similar_cases(self, query: str, args: dict) -> ToolResult:
        return _envelope(self.retriever.find_similar_cases(query, args.get("top_k"), args.get("reason")))
