"""Tool abstractions shared by MCP tools (A's server) and local tools (RAG).

The agent only talks to ToolRegistry. It does not know where a tool comes from.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Unified tool response (contracts/03-mcp-tools.md)."""
    ok: bool
    status: str                       # done | pending_confirmation | denied | needs_human | error
    data: Any = None
    error: dict | None = None         # {"code", "message", "policy_ref"}
    needs_human: bool = False
    audit_id: int | None = None

    @classmethod
    def from_payload(cls, payload: Any) -> "ToolResult":
        if not isinstance(payload, dict) or "ok" not in payload or "status" not in payload:
            return cls.failure("INTERNAL", f"Tool returned an unexpected payload: {str(payload)[:200]}")
        return cls(ok=bool(payload["ok"]), status=str(payload["status"]), data=payload.get("data"),
                   error=payload.get("error"), needs_human=bool(payload.get("needs_human", False)),
                   audit_id=payload.get("audit_id"))

    @classmethod
    def failure(cls, code: str, message: str) -> "ToolResult":
        return cls(ok=False, status="error", error={"code": code, "message": message, "policy_ref": None})

    def to_dict(self) -> dict:
        return {"ok": self.ok, "status": self.status, "data": self.data, "error": self.error,
                "needs_human": self.needs_human, "audit_id": self.audit_id}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict = field(default_factory=lambda: {"type": "object", "properties": {}})

    def to_openai(self) -> dict:
        return {"type": "function",
                "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}


class ToolProvider(Protocol):
    """A source of tools: A's MCP server, the local RAG tools, or a fake in tests."""
    name: str

    def list_tools(self) -> list[ToolSpec]: ...
    def call(self, name: str, args: dict) -> ToolResult: ...
    def set_context(self, session_id: str, user_id: str, user_turn: int) -> None: ...


class ToolRegistry:
    def __init__(self, providers: list[ToolProvider], hidden_prefix: str,
                 unknown_tool_template: str):
        self._providers = providers
        self._hidden_prefix = hidden_prefix
        self._unknown_template = unknown_tool_template
        self._routes: dict[str, ToolProvider] = {}
        self._specs: list[ToolSpec] = []
        self.refresh()

    def refresh(self) -> None:
        self._routes.clear()
        self._specs.clear()
        for provider in self._providers:
            for spec in provider.list_tools():
                if spec.name.startswith(self._hidden_prefix):
                    continue
                if spec.name in self._routes:
                    raise ValueError(f"Tool name conflict: '{spec.name}' in {provider.name} "
                                     f"and {self._routes[spec.name].name}")
                self._routes[spec.name] = provider
                self._specs.append(spec)
        logger.info("Tools available to the model: %s", self.names())

    def names(self) -> list[str]:
        return [s.name for s in self._specs]

    def openai_schemas(self) -> list[dict]:
        return [s.to_openai() for s in self._specs]

    def set_context(self, session_id: str, user_id: str, user_turn: int) -> None:
        for provider in self._providers:
            provider.set_context(session_id, user_id, user_turn)

    def call(self, name: str, args: dict) -> ToolResult:
        provider = self._routes.get(name)
        if provider is None:
            logger.warning("Model called unknown tool '%s'", name)
            return ToolResult.failure("UNKNOWN_TOOL", self._unknown_template.format(
                name=name, available=", ".join(self.names())))
        try:
            return provider.call(name, args)
        except Exception as e:  # a broken tool must never crash the conversation
            logger.exception("Tool '%s' failed", name)
            return ToolResult.failure("INTERNAL", f"Tool '{name}' failed: {e}")


def truncate_json(value: Any, max_chars: int) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= max_chars else text[:max_chars] + "...(truncated)"
