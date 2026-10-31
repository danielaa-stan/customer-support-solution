"""Test doubles: a scripted LLM and an in-memory tool provider."""
from __future__ import annotations

import json
from types import SimpleNamespace as NS

from agent.llm.client import LLMReply
from agent.tools.base import ToolResult, ToolSpec


def tool_call(name: str, args: dict | str, call_id: str = "call_1"):
    arguments = args if isinstance(args, str) else json.dumps(args)
    tc = NS(id=call_id, type="function", function=NS(name=name, arguments=arguments))
    tc.model_dump = lambda: {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}
    return tc


class ScriptedLLM:
    """Each script item is either a reply text or a list of tool calls."""

    def __init__(self, script):
        self.script = list(script)
        self.seen_messages: list[list[dict]] = []
        self.seen_tools: list[list[dict]] = []

    def chat(self, messages, tools=None):
        self.seen_messages.append([dict(m) for m in messages])
        self.seen_tools.append(tools or [])
        item = self.script.pop(0)
        if isinstance(item, list):
            return LLMReply(content="", thoughts="thinking", tool_calls=item)
        return LLMReply(content=item, thoughts="")


class FakeProvider:
    name = "fake"

    def __init__(self, results: dict[str, dict] | None = None):
        self.results = results or {}
        self.calls: list[tuple[str, dict]] = []
        self.contexts: list[tuple[str, str, int]] = []

    def list_tools(self):
        return [ToolSpec("get_user_profile", "profile"), ToolSpec("issue_refund", "refund"),
                ToolSpec("escalate_to_human", "handover"),
                ToolSpec("sys_set_context", "hidden")]

    def call(self, name, args):
        self.calls.append((name, args))
        return ToolResult.from_payload(self.results.get(name, {"ok": True, "status": "done", "data": {}}))

    def set_context(self, session_id, user_id, user_turn):
        self.contexts.append((session_id, user_id, user_turn))
