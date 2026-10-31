"""Transcript format (contracts/06)."""
import json

import pytest

from agent.factory import build_agent
from agent.tests.fakes import FakeProvider, ScriptedLLM, tool_call


@pytest.fixture()
def agent(settings):
    llm = ScriptedLLM([[tool_call("get_user_profile", {})], "Done."])
    return build_agent(settings, "u_demo_double", [FakeProvider()], llm)


def read(agent):
    return json.loads(agent.transcripts.path_for(agent.session).read_text(encoding="utf-8"))


def test_transcript_is_written_after_each_turn_in_contract_format(agent):
    agent.handle("Hi")
    doc = read(agent)
    assert doc["session_id"] == agent.session.session_id and doc["user_id"] == "u_demo_double"
    assert doc["ended_at"] is None and doc["end_reason"] is None
    roles = [m["role"] for m in doc["messages"]]
    assert roles == ["user", "assistant", "tool", "assistant"]
    assert [m["seq"] for m in doc["messages"]] == [1, 2, 3, 4]
    assert doc["messages"][1]["tool_calls"] == [{"name": "get_user_profile", "args": {}}]
    assert doc["messages"][2]["name"] == "get_user_profile" and doc["messages"][2]["content"]["ok"]
    assert all("thoughts" not in m for m in doc["messages"])


def test_end_sets_reason(agent):
    agent.handle("Hi")
    agent.end()
    doc = read(agent)
    assert doc["end_reason"] == "resolved_by_agent" and doc["ended_at"]


def test_finalization_is_idempotent_and_ended_chats_cannot_continue(agent):
    agent.handle("Hi")
    agent.end(user_left=True)
    before = read(agent)
    agent.end()
    assert read(agent) == before
    assert before["end_reason"] == "user_left"
    with pytest.raises(ValueError):
        agent.handle("Another turn")


def test_escalated_conversation_ends_as_escalated(settings):
    agent = build_agent(settings, "u_demo_cancel", [FakeProvider()], ScriptedLLM([]))
    agent.handle("I will file a chargeback")
    agent.end()
    assert read(agent)["end_reason"] == "escalated"
