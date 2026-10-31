"""Build a ready-to-use agent from settings. The only place that wires the pieces together."""
from __future__ import annotations

import logging

from agent.core.agent import SupportAgent
from agent.core.transcripts import TranscriptWriter
from agent.llm import LLMClient
from agent.prompts import PromptLibrary
from agent.rag.pipeline import load_retriever
from agent.safety.screening import MessageScreener
from agent.settings import Settings
from agent.tools.base import ToolProvider, ToolRegistry
from agent.tools.mcp_provider import MCPToolProvider
from agent.tools.rag_provider import RAGToolProvider

logger = logging.getLogger(__name__)


def build_registry(settings: Settings, providers: list[ToolProvider]) -> ToolRegistry:
    prompts = PromptLibrary(settings.prompts.dir)
    return ToolRegistry(providers, settings.mcp.hidden_tool_prefix, prompts.get("tool_unknown"))


def default_providers(settings: Settings) -> list[ToolProvider]:
    """A's MCP server + local RAG tools. Without an index the agent still works, only without RAG."""
    providers: list[ToolProvider] = [MCPToolProvider(settings.mcp)]
    try:
        providers.append(RAGToolProvider(load_retriever(settings), settings.rag.tools_file))
    except FileNotFoundError as e:
        logger.warning("RAG disabled: %s", e)
    return providers


def build_agent(settings: Settings, user_id: str, providers: list[ToolProvider] | None = None,
                llm: LLMClient | None = None) -> SupportAgent:
    providers = providers if providers is not None else default_providers(settings)
    prompts = PromptLibrary(settings.prompts.dir)
    return SupportAgent(llm or LLMClient.from_settings(settings), build_registry(settings, providers),
                        prompts, settings.agent, user_id,
                        MessageScreener.from_file(settings.safety.config_file), settings.safety,
                        TranscriptWriter(settings.transcripts.dir))
