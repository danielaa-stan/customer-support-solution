"""Real MCP over stdio against a tiny fake server (tests/fixtures/fake_mcp_server.py)."""
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from agent.tools.mcp_provider import MCPToolProvider, parse_command, server_env

SERVER = Path(__file__).resolve().parent / "fixtures" / "fake_mcp_server.py"


@pytest.fixture()
def provider(settings):
    cfg = replace(settings.mcp, server_command=f'"{sys.executable}" "{SERVER}"', startup_timeout_s=60)
    p = MCPToolProvider(cfg)
    yield p
    p.close()


def test_lists_tools_and_calls_with_context(provider):
    assert {"get_user_profile", "issue_refund", "sys_set_context"} <= {t.name for t in provider.list_tools()}
    provider.set_context("ses_1", "u_demo_double", 1)
    result = provider.call("get_user_profile", {})
    assert result.ok and result.data["user"]["id"] == "u_demo_double"


def test_needs_human_result_is_parsed(provider):
    provider.set_context("ses_1", "u_demo_escalate", 1)
    result = provider.call("issue_refund", {"payment_id": "pay_big", "reason_code": "other",
                                            "policy_ref": "refund-policy#2.3"})
    assert not result.ok and result.needs_human and result.error["code"] == "LIMIT_EXCEEDED"


def test_parse_command_handles_quotes():
    assert parse_command('dotnet run --project "my server"')[1][-1] in ("my server", '"my server"')


def test_agent_secret_is_not_passed_to_server(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    assert "GEMINI_API_KEY" not in server_env()
