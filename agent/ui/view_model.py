"""Pure helpers that turn agent turns into what the Copilot panel shows (kept out of Streamlit for testing)."""
from __future__ import annotations

from agent.core.agent import AgentTurn


def cited_policies(turn: AgentTurn) -> list[str]:
    """policy_refs the agent relied on: retrieved by search_policy, passed to tools, or returned in errors."""
    refs: list[str] = []
    for e in turn.tool_events:
        if e.name == "search_policy":
            refs += [r["policy_ref"] for r in (e.result.get("data") or {}).get("results", [])]
        if e.args.get("policy_ref"):
            refs.append(e.args["policy_ref"])
        if (e.result.get("error") or {}).get("policy_ref"):
            refs.append(e.result["error"]["policy_ref"])
    return list(dict.fromkeys(refs))


def chat_messages(events: list[dict]) -> list[tuple[str, str]]:
    """(role, text) pairs for the chat column: customer and agent text only."""
    out = []
    for e in events:
        if e["role"] in ("user", "assistant") and isinstance(e.get("content"), str) and e["content"].strip():
            out.append((e["role"], e["content"]))
    return out
