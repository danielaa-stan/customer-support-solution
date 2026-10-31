"""LLM client: Gemma 4 through the Gemini API (OpenAI-compatible endpoint).

* retries on network errors, rate limits and empty answers
* separates <thought> blocks from the answer (thoughts are kept for the Copilot panel)
* logs every request: summary at INFO, full prompts and answers at DEBUG
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, replace
from typing import Any

import openai

from agent.llm.parsing import ThoughtParser
from agent.prompts import PromptLibrary
from agent.settings import LLMSettings, Settings

logger = logging.getLogger(__name__)

RETRYABLE_ERRORS = (openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError,
                    openai.APITimeoutError)


@dataclass
class LLMReply:
    content: str                                   # text for the customer (thoughts removed)
    thoughts: str                                  # model reasoning, for the Copilot panel and logs
    tool_calls: list[Any] = field(default_factory=list)
    latency_s: float = 0.0
    usage: dict = field(default_factory=dict)

    def assistant_message(self) -> dict:
        """Message to append to the conversation history (OpenAI format)."""
        msg: dict = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = [tc.model_dump() for tc in self.tool_calls]
        return msg


class LLMClient:
    def __init__(self, cfg: LLMSettings, api_key: str, empty_answer_nudge: str, client: Any = None):
        self.cfg = cfg
        self._nudge = empty_answer_nudge
        self._parser = ThoughtParser(cfg.thought_open_tag, cfg.thought_close_tag)
        self._client = client or openai.OpenAI(base_url=cfg.base_url, api_key=api_key, timeout=cfg.timeout_s)
        logger.info("LLM client ready: model=%s reasoning_effort=%s", cfg.model, cfg.reasoning_effort or "default")

    @classmethod
    def from_settings(cls, settings: Settings, client: Any = None) -> "LLMClient":
        prompts = PromptLibrary(settings.prompts.dir)
        return cls(settings.llm, settings.gemini_api_key, prompts.get("empty_answer_nudge"), client)

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMReply:
        reply = self._request(messages, tools)
        if not reply.content and not reply.tool_calls:
            logger.warning("Empty answer (only thoughts). Asking the model again.")
            retry = self._request(messages + [{"role": "user", "content": self._nudge}], tools)
            retry.thoughts = "\n".join(t for t in (reply.thoughts, retry.thoughts) if t)
            retry.latency_s += reply.latency_s
            reply = retry
        return reply

    # ------------------------------------------------------------------ internals
    def _request(self, messages: list[dict], tools: list[dict] | None) -> LLMReply:
        kwargs: dict = {"model": self.cfg.model, "messages": messages, "temperature": self.cfg.temperature}
        if tools:
            kwargs["tools"] = tools
        if self.cfg.reasoning_effort:
            kwargs["reasoning_effort"] = self.cfg.reasoning_effort
        logger.debug("LLM request: %s", json.dumps(
            {"messages": messages, "tools": [t["function"]["name"] for t in tools or []]},
            ensure_ascii=False, default=str))

        attempt = 0
        while True:
            start = time.perf_counter()
            try:
                resp = self._client.chat.completions.create(**kwargs)
                break
            except openai.BadRequestError as e:
                if "reasoning_effort" not in kwargs:
                    raise
                logger.warning("Model rejected reasoning_effort=%s (%s); continuing without it.",
                               kwargs.pop("reasoning_effort"), e)
                self.cfg = replace(self.cfg, reasoning_effort="")
            except RETRYABLE_ERRORS as e:
                if attempt >= self.cfg.max_retries:
                    logger.error("LLM request failed after %d attempts: %s", attempt + 1, e)
                    raise
                wait = self.cfg.retry_backoff_s * 2 ** attempt
                attempt += 1
                logger.warning("LLM request failed (%s). Retry %d in %.0fs.", type(e).__name__, attempt, wait)
                time.sleep(wait)
        latency = time.perf_counter() - start

        message = resp.choices[0].message
        answer, thoughts = self._parser.split(message.content)
        usage = resp.usage.model_dump() if getattr(resp, "usage", None) else {}
        reply = LLMReply(answer, thoughts, list(message.tool_calls or []), latency, usage)

        logger.info("LLM reply in %.1fs: tool_calls=%s answer_chars=%d thought_chars=%d tokens=%s",
                    latency, [tc.function.name for tc in reply.tool_calls], len(answer), len(thoughts),
                    usage.get("total_tokens"))
        logger.debug("LLM answer: %s | thoughts: %s | tool_calls: %s", answer, thoughts,
                     [(tc.function.name, tc.function.arguments) for tc in reply.tool_calls])
        return reply
