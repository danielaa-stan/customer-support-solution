"""Agent loop tests with a scripted LLM and fake tools. No network needed."""
import pytest

from agent.factory import build_agent
from agent.tests.fakes import FakeProvider, ScriptedLLM, tool_call


@pytest.fixture()
def make_agent(settings):
    def _make(script, results=None):
        provider, llm = FakeProvider(results), ScriptedLLM(script)
        return build_agent(settings, "u_demo_double", [provider], llm), provider, llm
    return _make


def test_tool_result_goes_back_to_model_and_final_answer_is_returned(make_agent):
    agent, provider, llm = make_agent([[tool_call("get_user_profile", {})], "All good."])
    turn = agent.handle("Hi")
    assert turn.reply == "All good."
    assert provider.calls == [("get_user_profile", {})]
    assert llm.seen_messages[1][-1]["role"] == "tool"
    assert [e.name for e in turn.tool_events] == ["get_user_profile"]


def test_context_is_set_before_every_user_turn(make_agent):
    agent, provider, _ = make_agent(["one", "two"])
    agent.handle("first")
    agent.handle("second")
    sid = agent.session.session_id
    assert provider.contexts == [(sid, "u_demo_double", 1), (sid, "u_demo_double", 2)]


def test_hidden_sys_tools_are_not_shown_to_the_model(make_agent):
    agent, _, llm = make_agent(["ok"])
    agent.handle("hi")
    names = [t["function"]["name"] for t in llm.seen_tools[0]]
    assert "sys_set_context" not in names and "get_user_profile" in names


def test_unknown_tool_returns_error_with_available_tools(make_agent):
    agent, provider, llm = make_agent([[tool_call("list_invoices", {})], "Sorry."])
    turn = agent.handle("hi")
    assert turn.tool_events[0].result["error"]["code"] == "UNKNOWN_TOOL"
    assert "get_user_profile" in turn.tool_events[0].result["error"]["message"]
    assert provider.calls == []


def test_invalid_json_arguments_are_reported_to_model(make_agent):
    agent, provider, _ = make_agent([[tool_call("issue_refund", "{not json")], "Retrying failed."])
    turn = agent.handle("refund")
    assert turn.tool_events[0].result["error"]["code"] == "INVALID_ARGUMENT"
    assert provider.calls == []


def test_needs_human_is_propagated(make_agent):
    results = {"issue_refund": {"ok": False, "status": "needs_human", "needs_human": True,
                                "error": {"code": "LIMIT_EXCEEDED", "message": "too big", "policy_ref": "refund-policy#2.3"}}}
    agent, _, _ = make_agent([[tool_call("issue_refund", {"payment_id": "p"})], "A human will help."], results)
    assert agent.handle("refund").needs_human


def test_max_rounds_falls_back_to_human(make_agent, settings):
    loops = [[tool_call("get_user_profile", {}, f"c{i}")] for i in range(settings.agent.max_tool_rounds)]
    agent, _, _ = make_agent(loops)
    turn = agent.handle("hi")
    assert turn.needs_human and turn.rounds == settings.agent.max_tool_rounds
    assert "support team" in turn.reply


def test_events_are_logged_in_order(make_agent):
    agent, _, _ = make_agent([[tool_call("get_user_profile", {})], "Done."])
    agent.handle("Hi")
    assert [e["role"] for e in agent.session.events] == ["user", "assistant", "tool", "assistant"]
    assert [e["seq"] for e in agent.session.events] == [1, 2, 3, 4]
