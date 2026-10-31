"""Smoke test: can the model answer, call tools and use tool results?

Run from the repo root:          python -m agent.scripts.check_llm
Compare thinking levels:         LLM_REASONING_EFFORT=low python -m agent.scripts.check_llm
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from agent.llm import LLMClient
from agent.logging_config import setup_logging
from agent.settings import load_settings

logger = logging.getLogger("check_llm")
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "check_llm.json"


def main() -> int:
    settings = load_settings()
    setup_logging(settings.logging)
    case = json.loads(FIXTURE.read_text(encoding="utf-8"))
    llm = LLMClient.from_settings(settings)

    reply = llm.chat([{"role": "user", "content": case["text_prompt"]}])
    logger.info("[1] Text answer: %r", reply.content)

    messages = list(case["messages"])
    reply = llm.chat(messages, case["tools"])
    logger.info("[2] Tool calls: %s", [(tc.function.name, tc.function.arguments) for tc in reply.tool_calls])
    if not reply.tool_calls:
        logger.error("FAIL: the model did not call the tool.")
        return 1

    call = reply.tool_calls[0]
    messages += [reply.assistant_message(),
                 {"role": "tool", "tool_call_id": call.id, "content": json.dumps(case["fake_tool_result"])}]
    reply = llm.chat(messages, case["tools"])
    logger.info("[3] Answer after tool result: %r", reply.content)
    logger.info("[3] Thoughts (first 300 chars): %r", reply.thoughts[:300])
    if not reply.content:
        logger.error("FAIL: no answer for the customer.")
        return 1
    logger.info("OK: the model answers, calls tools and uses tool results.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
