"""Tools from A's MCP server over stdio (contracts/03-mcp-tools.md).

The MCP client library is async; the rest of the agent (and Streamlit) is sync. The provider keeps one
connection open for the whole chat in a background thread with its own event loop, and exposes sync methods.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import threading
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from agent.settings import MCPSettings
from agent.tools.base import ToolResult, ToolSpec

logger = logging.getLogger(__name__)

# Secrets of the agent that the server process must not receive.
SECRET_ENV_VARS = ("GEMINI_API_KEY",)


def parse_command(command: str) -> tuple[str, list[str]]:
    parts = shlex.split(command, posix=os.name != "nt")
    if not parts:
        raise ValueError("MCP server command is empty")
    return parts[0], parts[1:]


def server_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in SECRET_ENV_VARS}


def result_payload(result: Any) -> Any:
    """Extract the JSON payload from an MCP CallToolResult."""
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        # FastMCP wraps non-object return values as {"result": ...}
        return structured.get("result", structured) if set(structured) == {"result"} else structured
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
    return None


class MCPToolProvider:
    name = "mcp"

    def __init__(self, cfg: MCPSettings, transport: Any = None):
        self.cfg = cfg
        if transport is None:
            command, args = parse_command(cfg.server_command)
            transport = StdioTransport(command=command, args=args, env=server_env(), cwd=os.getcwd())
        self._client = Client(transport)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name="mcp-client", daemon=True)
        self._thread.start()
        self._tools: list[ToolSpec] = []
        logger.info("Starting MCP server: %s", cfg.server_command)
        self._run(self._client.__aenter__(), cfg.startup_timeout_s)
        self._tools = self._run(self._load_tools(), cfg.call_timeout_s)
        logger.info("MCP server connected, %d tools", len(self._tools))

    # ------------------------------------------------------------------ ToolProvider
    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools)

    def call(self, name: str, args: dict) -> ToolResult:
        logger.info("MCP call %s %s", name, json.dumps(args, ensure_ascii=False))
        try:
            raw = self._run(self._client.call_tool(name, args, raise_on_error=False), self.cfg.call_timeout_s)
        except TimeoutError:
            logger.error("MCP call %s timed out after %.0fs", name, self.cfg.call_timeout_s)
            return ToolResult.failure("INTERNAL", f"Tool '{name}' timed out")
        result = ToolResult.from_payload(result_payload(raw))
        logger.info("MCP result %s: ok=%s status=%s error=%s", name, result.ok, result.status,
                    (result.error or {}).get("code"))
        return result

    def set_context(self, session_id: str, user_id: str, user_turn: int) -> None:
        result = self.call(self.cfg.context_tool,
                           {"session_id": session_id, "user_id": user_id, "user_turn": user_turn})
        if not result.ok:
            raise RuntimeError(f"{self.cfg.context_tool} failed: {result.error}")

    def close(self) -> None:
        try:
            self._run(self._client.__aexit__(None, None, None), self.cfg.call_timeout_s)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            logger.info("MCP server connection closed")

    # ------------------------------------------------------------------ internals
    def _run(self, coro, timeout: float):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    async def _load_tools(self) -> list[ToolSpec]:
        specs = []
        for tool in await self._client.list_tools():
            schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None) or {
                "type": "object", "properties": {}}
            specs.append(ToolSpec(name=tool.name, description=tool.description or "", parameters=schema))
        return specs
