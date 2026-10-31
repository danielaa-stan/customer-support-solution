"""Load agent settings from config/settings.toml, environment variables and .env.

Precedence (lowest to highest): settings.toml -> environment variable SECTION_KEY.
Secrets are read only from the environment / .env.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Mapping

from dotenv import load_dotenv

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

DEFAULT_SETTINGS_PATH = Path(__file__).resolve().parent / "config" / "settings.toml"


@dataclass(frozen=True)
class LLMSettings:
    base_url: str
    model: str
    reasoning_effort: str
    temperature: float
    timeout_s: float
    max_retries: int
    retry_backoff_s: float
    thought_open_tag: str
    thought_close_tag: str


@dataclass(frozen=True)
class LoggingSettings:
    console_level: str
    file_level: str
    dir: Path
    file_name: str
    quiet_libraries: tuple[str, ...]


@dataclass(frozen=True)
class PromptSettings:
    dir: Path


@dataclass(frozen=True)
class AgentSettings:
    max_tool_rounds: int
    tool_result_max_chars: int
    session_id_prefix: str


@dataclass(frozen=True)
class MCPSettings:
    server_command: str
    context_tool: str
    hidden_tool_prefix: str
    startup_timeout_s: float
    call_timeout_s: float


@dataclass(frozen=True)
class Settings:
    llm: LLMSettings
    logging: LoggingSettings
    prompts: PromptSettings
    agent: AgentSettings
    mcp: MCPSettings
    gemini_api_key: str = field(repr=False)


def _cast(value: str, target: Any) -> Any:
    """Convert an environment variable string to the type of the value from the TOML file."""
    if isinstance(target, bool):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(target, int):
        return int(value)
    if isinstance(target, float):
        return float(value)
    if isinstance(target, list):
        return [v.strip() for v in value.split(",") if v.strip()]
    return value


def _section(raw: dict, name: str, cls: type, env: Mapping[str, str]) -> dict:
    values = dict(raw.get(name, {}))
    missing = {f.name for f in fields(cls)} - values.keys()
    if missing:
        raise ValueError(f"settings.toml [{name}] is missing keys: {sorted(missing)}")
    for key in list(values):
        env_name = f"{name}_{key}".upper()
        if env_name in env:
            values[key] = _cast(env[env_name], values[key])
    return values


def load_settings(path: Path = DEFAULT_SETTINGS_PATH, env: Mapping[str, str] | None = None) -> Settings:
    if env is None:
        load_dotenv()
        env = os.environ
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    llm = LLMSettings(**_section(raw, "llm", LLMSettings, env))
    log = _section(raw, "logging", LoggingSettings, env)
    log["dir"] = Path(log["dir"])
    log["quiet_libraries"] = tuple(log["quiet_libraries"])
    prompts = _section(raw, "prompts", PromptSettings, env)
    prompts["dir"] = (path.parent / prompts["dir"]).resolve()

    api_key = env.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Copy .env.example to .env and add the key.")
    return Settings(llm=llm, logging=LoggingSettings(**log), prompts=PromptSettings(**prompts),
                    agent=AgentSettings(**_section(raw, "agent", AgentSettings, env)),
                    mcp=MCPSettings(**_section(raw, "mcp", MCPSettings, env)),
                    gemini_api_key=api_key)
