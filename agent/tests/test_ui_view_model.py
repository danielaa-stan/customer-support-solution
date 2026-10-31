from agent.core.agent import AgentTurn
from agent.core.session import ToolEvent
from agent.ui.view_model import chat_messages, cited_policies


def test_cited_policies_split_applied_and_retrieved():
    turn = AgentTurn(reply="", tool_events=[
        ToolEvent("search_policy", {"query": "x"}, {"data": {"results": [{"policy_ref": "refund-policy#2.2"},
                                                                       {"policy_ref": "refund-policy#2.1"}]}}, 0),
        ToolEvent("issue_refund", {"policy_ref": "refund-policy#2.2"}, {"status": "done"}, 0),
        ToolEvent("issue_refund", {}, {"error": {"policy_ref": "refund-policy#2.3"}}, 0),
    ])
    assert cited_policies(turn) == (["refund-policy#2.2", "refund-policy#2.3"], ["refund-policy#2.1"])


def test_chat_messages_skip_tool_events_and_empty_text():
    events = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": ""},
              {"role": "tool", "content": {"ok": True}}, {"role": "assistant", "content": "hello"}]
    assert chat_messages(events) == [("user", "hi"), ("assistant", "hello")]
