"""Streamlit UI: customer chat + Copilot panel.

Run from the repo root:   streamlit run agent/ui/app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # streamlit puts only the script folder on sys.path
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from agent.factory import build_agent  # noqa: E402
from agent.logging_config import setup_logging  # noqa: E402
from agent.settings import load_settings  # noqa: E402
from agent.ui.view_model import chat_messages, cited_policies  # noqa: E402
from analytics.worker import start_background_worker  # noqa: E402

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

UI_CONFIG = Path(__file__).resolve().parents[1] / "config" / "ui.toml"


@st.cache_resource
def app_config():
    settings = load_settings()
    setup_logging(settings.logging)
    with open(UI_CONFIG, "rb") as f:
        return settings, tomllib.load(f)


settings, ui = app_config()


@st.cache_resource
def analytics_worker():
    return start_background_worker()


analytics_worker()
T, ICONS = ui["texts"], ui["status_icons"]
CUSTOMERS = {c["id"]: c for c in ui["customers"]}

st.set_page_config(page_title=T["page_title"], page_icon="🎧", layout="wide")


def close_agent(user_left: bool) -> None:
    agent = st.session_state.pop("agent", None)
    if agent is None:
        return
    if agent.session.user_turn:
        agent.end(user_left=user_left)
    for provider in getattr(agent.tools, "_providers", []):
        if hasattr(provider, "close"):
            provider.close()


def start_agent(user_id: str) -> None:
    close_agent(user_left=True)
    with st.spinner(T["starting"]):
        st.session_state.agent = build_agent(settings, user_id)
    st.session_state.turns = []
    st.session_state.ended = False


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title(T["app_title"])
    st.caption(T["app_subtitle"])
    user_id = st.selectbox(T["customer_label"], list(CUSTOMERS), format_func=lambda u: CUSTOMERS[u]["label"])
    if "agent" not in st.session_state or st.session_state.agent.session.user_id != user_id:
        start_agent(user_id)
    left, right = st.columns(2)
    if left.button(T["new_chat"], width="stretch"):
        start_agent(user_id)
    if right.button(T["end_chat"], width="stretch", disabled=st.session_state.ended):
        st.session_state.agent.end()
        st.session_state.ended = True
    st.caption(T["sample_label"])
    st.code(CUSTOMERS[user_id]["sample"], language=None, wrap_lines=True)
    st.caption(f"Session `{st.session_state.agent.session.session_id}`")

agent = st.session_state.agent
chat_col, panel_col = st.columns([3, 2], gap="large")

# ------------------------------------------------------------------ chat
with chat_col:
    st.subheader(T["chat_header"])
    for role, text in chat_messages(agent.session.events):
        with st.chat_message("user" if role == "user" else "assistant", avatar="🙂" if role == "user" else "🎧"):
            st.write(text)
    if st.session_state.ended:
        st.success(T["ended"])
    elif prompt := st.chat_input(T["chat_placeholder"]):
        with st.spinner(T["working"]):
            st.session_state.turns.append(agent.handle(prompt))
        st.rerun()

# ------------------------------------------------------------------ copilot panel
with panel_col:
    st.subheader(T["copilot_header"])
    if not st.session_state.turns:
        st.caption(T["copilot_empty"])
    for i, turn in enumerate(reversed(st.session_state.turns)):
        number = len(st.session_state.turns) - i
        with st.container(border=True):
            st.markdown(f"**Turn {number}** · {turn.latency_s:.1f}s · {turn.rounds} model calls")
            if turn.safety_flags:
                st.warning(f"🛡️ {T['safety']}: {', '.join(turn.safety_flags)}")
            if turn.needs_human:
                st.error(f"🧑‍💼 {T['needs_human']}")
            applied, retrieved = cited_policies(turn)
            if applied:
                st.markdown(f"**{T['policies_applied']}:** " + " ".join(f"`{r}`" for r in applied))
            if retrieved:
                st.caption(f"{T['policies_retrieved']}: " + " ".join(f"`{r}`" for r in retrieved))
            if turn.tool_events:
                st.markdown(f"**{T['actions']}**")
                for e in turn.tool_events:
                    status = e.result.get("status", "")
                    code = (e.result.get("error") or {}).get("code")
                    with st.expander(f"{ICONS.get(status, '•')} {e.name} → {status}{' · ' + code if code else ''}"):
                        st.code(json.dumps({"args": e.args, "result": e.result}, indent=2, ensure_ascii=False),
                                language="json")
            if turn.thoughts:
                with st.expander(f"🧠 {T['reasoning']}", expanded=(i == 0)):
                    st.write("\n\n".join(turn.thoughts))
