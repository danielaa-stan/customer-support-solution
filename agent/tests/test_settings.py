import pytest

from agent.prompts import PromptLibrary
from agent.settings import load_settings


def test_defaults_come_from_toml(settings):
    assert settings.llm.model.startswith("gemma")
    assert settings.llm.max_retries >= 0
    assert "test-key" not in repr(settings)  # the secret is never printed or logged


def test_env_overrides_toml():
    s = load_settings(env={"GEMINI_API_KEY": "k", "LLM_REASONING_EFFORT": "low", "LLM_MAX_RETRIES": "5"})
    assert s.llm.reasoning_effort == "low"
    assert s.llm.max_retries == 5


def test_missing_key_is_a_clear_error():
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        load_settings(env={})


def test_prompts_are_loaded_from_files(settings):
    assert PromptLibrary(settings.prompts.dir).get("empty_answer_nudge")
    with pytest.raises(FileNotFoundError):
        PromptLibrary(settings.prompts.dir).get("does_not_exist")
