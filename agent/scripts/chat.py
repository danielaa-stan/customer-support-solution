"""Chat with the agent in the terminal, against the MCP server from settings (MCP_SERVER_COMMAND).

Run from the repo root:   python -m agent.scripts.chat u_demo_double
Type 'exit' to quit.
"""
from __future__ import annotations

import logging
import sys

from agent.factory import build_agent
from agent.logging_config import setup_logging
from agent.settings import load_settings

logger = logging.getLogger("chat")
EXIT_WORDS = {"exit", "quit"}


def main() -> int:
    if len(sys.argv) != 2:
        logger.error("Usage: python -m agent.scripts.chat <user_id>")
        return 2
    settings = load_settings()
    setup_logging(settings.logging)
    agent = build_agent(settings, sys.argv[1])
    try:
        while True:
            text = input("\ncustomer> ").strip()
            if text.lower() in EXIT_WORDS:
                return 0
            if not text:
                continue
            turn = agent.handle(text)
            for event in turn.tool_events:
                logger.info("tool %s %s -> %s", event.name, event.args, event.result.get("status"))
            logger.info("agent> %s", turn.reply)
            if turn.needs_human:
                logger.warning("Needs a human agent.")
    finally:
        agent.end(user_left=True)
        for provider in getattr(agent.tools, "_providers", []):
            close = getattr(provider, "close", None)
            if close:
                close()


if __name__ == "__main__":
    sys.exit(main())
