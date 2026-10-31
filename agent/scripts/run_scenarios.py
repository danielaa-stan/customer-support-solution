"""Run the demo scenarios (contracts/07) end to end against the real MCP server and summarise the result.

Run from the repo root:   python -m agent.scripts.run_scenarios          (all)
                          python -m agent.scripts.run_scenarios 2        (only scenarios whose name starts with "2")
Each scenario uses a fresh server process (one conversation = one server run).
Reset the database between full runs: dotnet run --project server/SupportServer -c Release -- reset-db
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from agent.factory import build_agent
from agent.logging_config import setup_logging
from agent.settings import load_settings

logger = logging.getLogger("scenarios")
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "demo_scenarios.json"


def close(agent) -> None:
    for provider in getattr(agent.tools, "_providers", []):
        if hasattr(provider, "close"):
            provider.close()


def run(scenario: dict, settings) -> bool:
    logger.info("=" * 70)
    logger.info("%s (%s)", scenario["name"], scenario["user_id"])
    agent = build_agent(settings, scenario["user_id"])
    called, total_s = [], 0.0
    try:
        for text in scenario["messages"]:
            logger.info("customer> %s", text)
            turn = agent.handle(text)
            total_s += turn.latency_s
            for e in turn.tool_events:
                called.append(e.name)
                err = (e.result.get("error") or {}).get("code")
                logger.info("   tool %-22s %s -> %s %s", e.name, json.dumps(e.args, ensure_ascii=False)[:120],
                            e.result.get("status"), err or "")
            logger.info("agent> %s", turn.reply)
    finally:
        close(agent)
    missing = [t for t in scenario["expect_tools"] if t not in called]
    ok = not missing
    logger.info("%s %s in %.0fs; missing tools: %s", "PASS" if ok else "CHECK", scenario["name"], total_s,
                missing or "none")
    return ok


def main() -> int:
    settings = load_settings()
    setup_logging(settings.logging)
    prefix = sys.argv[1] if len(sys.argv) > 1 else ""
    scenarios = [s for s in json.loads(FIXTURE.read_text(encoding="utf-8")) if s["name"].startswith(prefix)]
    results = {s["name"]: run(s, settings) for s in scenarios}
    logger.info("=" * 70)
    for name, ok in results.items():
        logger.info("%-40s %s", name, "PASS" if ok else "CHECK")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
