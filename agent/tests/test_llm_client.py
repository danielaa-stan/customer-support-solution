"""LLMClient and ThoughtParser tests. No network or API key needed."""
from dataclasses import replace
from types import SimpleNamespace as NS

import openai
import pytest

from agent.llm import LLMClient
from agent.llm.parsing import ThoughtParser

NUDGE = "nudge"


@pytest.fixture()
def parser(settings):
    return ThoughtParser(settings.llm.thought_open_tag, settings.llm.thought_close_tag)


def test_thoughts_are_removed(parser):
    assert parser.split("<thought>check payments</thought>Refunded.") == ("Refunded.", "check payments")


def test_unclosed_thought_is_all_thought(parser):
    assert parser.split("<thought>still thinking") == ("", "still thinking")


def test_plain_text(parser):
    assert parser.split("Hello!") == ("Hello!", "")
    assert parser.split(None) == ("", "")


class FakeOpenAI:
    """Scripted replies: each item is a content string or an exception to raise."""

    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return NS(choices=[NS(message=NS(content=item, tool_calls=None))], usage=None)


@pytest.fixture()
def make_client(settings, monkeypatch):
    monkeypatch.setattr("agent.llm.client.time.sleep", lambda s: None)

    def _make(script, **overrides):
        fake = FakeOpenAI(script)
        return LLMClient(replace(settings.llm, **overrides), "k", NUDGE, client=fake), fake
    return _make


def connection_error():
    return openai.APIConnectionError(request=NS(method="POST", url="x"))


def test_empty_answer_is_retried_with_nudge(make_client):
    llm, fake = make_client(["<thought>only thinking</thought>", "Here is my answer."])
    reply = llm.chat([{"role": "user", "content": "hi"}])
    assert reply.content == "Here is my answer."
    assert "only thinking" in reply.thoughts
    assert fake.calls[1]["messages"][-1]["content"] == NUDGE


def test_network_error_is_retried(make_client):
    llm, fake = make_client([connection_error(), "ok"])
    assert llm.chat([{"role": "user", "content": "hi"}]).content == "ok"
    assert len(fake.calls) == 2


def test_gives_up_after_max_retries(make_client):
    llm, _ = make_client([connection_error()] * 3, max_retries=2)
    with pytest.raises(openai.APIConnectionError):
        llm.chat([{"role": "user", "content": "hi"}])


def test_rejected_reasoning_effort_falls_back(make_client):
    bad = openai.BadRequestError("unsupported", response=NS(status_code=400, request=None, headers={}), body=None)
    llm, fake = make_client([bad, "ok"], reasoning_effort="low")
    assert llm.chat([{"role": "user", "content": "hi"}]).content == "ok"
    assert "reasoning_effort" in fake.calls[0] and "reasoning_effort" not in fake.calls[1]
