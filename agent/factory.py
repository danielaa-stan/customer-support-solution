"""Build a ready-to-use agent from settings. The only place that wires the pieces together."""
from __future__ import annotations

from agent.core.agent import SupportAgent
from agent.llm import LLMClient
from agent.prompts import PromptLibrary
from agent.safety.screening import MessageScreener
from agent.settings import Settings
from agent.tools.base import ToolProvider, ToolRegistry
from agent.tools.mcp_provider import MCPToolProvider


def build_registry(settings: Settings, providers: list[ToolProvider]) -> ToolRegistry:
    prompts = PromptLibrary(settings.prompts.dir)
    return ToolRegistry(providers, settings.mcp.hidden_tool_prefix, prompts.get("tool_unknown"))


def build_agent(settings: Settings, user_id: str, providers: list[ToolProvider] | None = None,
                llm: LLMClient | None = None) -> SupportAgent:
    providers = providers if providers is not None else [MCPToolProvider(settings.mcp)]
    prompts = PromptLibrary(settings.prompts.dir)
    return SupportAgent(llm or LLMClient.from_settings(settings), build_registry(settings, providers),
                        prompts, settings.agent, user_id,
                        MessageScreener.from_file(settings.safety.config_file), settings.safety)
