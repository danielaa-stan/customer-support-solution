"""The agent loop: customer message -> LLM -> tools -> ... -> reply.

One SupportAgent instance = one chat session.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

from agent.llm import LLMClient
from agent.prompts import PromptLibrary
from agent.settings import AgentSettings
from agent.tools.base import ToolRegistry, ToolResult, truncate_json
from agent.core.session import Session, ToolEvent

logger = logging.getLogger(__name__)


@dataclass
class AgentTurn:
    """Everything the UI needs to show for one customer message."""
    reply: str
    thoughts: list[str] = field(default_factory=list)
    tool_events: list[ToolEvent] = field(default_factory=list)
    needs_human: bool = False
    rounds: int = 0
    latency_s: float = 0.0


class SupportAgent:
    def __init__(self, llm: LLMClient, tools: ToolRegistry, prompts: PromptLibrary, cfg: AgentSettings,
                 user_id: str):
        self.llm = llm
        self.tools = tools
        self.prompts = prompts
        self.cfg = cfg
        self.session = Session.start(user_id, cfg.session_id_prefix, prompts.get("system"))
        logger.info("Session %s started for user %s", self.session.session_id, user_id)

    def handle(self, text: str) -> AgentTurn:
        s = self.session
        start = time.perf_counter()
        s.user_turn += 1
        self.tools.set_context(s.session_id, s.user_id, s.user_turn)
        s.history.append({"role": "user", "content": text})
        s.log("user", text)
        logger.info("[%s] turn %d user: %s", s.session_id, s.user_turn, text)

        turn = AgentTurn(reply="")
        for round_no in range(1, self.cfg.max_tool_rounds + 1):
            turn.rounds = round_no
            reply = self.llm.chat(s.history, self.tools.openai_schemas())
            if reply.thoughts:
                turn.thoughts.append(reply.thoughts)
            s.history.append(reply.assistant_message())

            if not reply.tool_calls:
                turn.reply = reply.content
                s.log("assistant", reply.content, thoughts=reply.thoughts)
                break

            s.log("assistant", reply.content, thoughts=reply.thoughts,
                  tool_calls=[{"name": tc.function.name, "args": self._parse_args(tc)[0]} for tc in reply.tool_calls])
            for tc in reply.tool_calls:
                event = self._run_tool(tc)
                turn.tool_events.append(event)
                turn.needs_human |= bool(event.result.get("needs_human"))
        else:
            logger.warning("[%s] max tool rounds (%d) reached", s.session_id, self.cfg.max_tool_rounds)
            turn.reply = self.prompts.get("max_rounds_reply")
            turn.needs_human = True
            s.history.append({"role": "assistant", "content": turn.reply})
            s.log("assistant", turn.reply)

        turn.latency_s = time.perf_counter() - start
        logger.info("[%s] turn %d done in %.1fs, %d rounds, tools=%s, needs_human=%s", s.session_id, s.user_turn,
                    turn.latency_s, turn.rounds, [e.name for e in turn.tool_events], turn.needs_human)
        return turn

    # ------------------------------------------------------------------ internals
    def _parse_args(self, tool_call) -> tuple[dict, str | None]:
        raw = tool_call.function.arguments or "{}"
        try:
            args = json.loads(raw)
            return (args, None) if isinstance(args, dict) else ({}, "arguments must be a JSON object")
        except json.JSONDecodeError as e:
            return {}, str(e)

    def _run_tool(self, tool_call) -> ToolEvent:
        name = tool_call.function.name
        args, error = self._parse_args(tool_call)
        start = time.perf_counter()
        if error:
            result = ToolResult.failure("INVALID_ARGUMENT", self.prompts.get("tool_invalid_arguments").format(
                name=name, error=error))
        else:
            result = self.tools.call(name, args)
        event = ToolEvent(name=name, args=args, result=result.to_dict(), latency_s=time.perf_counter() - start)

        content = truncate_json(event.result, self.cfg.tool_result_max_chars)
        self.session.history.append({"role": "tool", "tool_call_id": tool_call.id, "content": content})
        self.session.log("tool", event.result, name=name)
        return event
