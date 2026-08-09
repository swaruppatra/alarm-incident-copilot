from functools import lru_cache
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    llm_api_key: str = Field(alias="LLM_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")

    # Base URLs (no /mcp suffix); streamable-http, matching how both MCP
    # servers are actually deployed (docker-compose, separate containers).
    alarm_mcp_url: str = Field(default="http://localhost:9000", alias="MCP_SERVER_URL")
    ticketing_mcp_url: str = Field(default="http://localhost:9100", alias="TICKETING_MCP_SERVER_URL")


@lru_cache
def get_settings() -> Settings:
    """Return the cached, process-wide Settings instance.

    Args:
        None

    Returns:
        Settings: the loaded configuration singleton.
    """
    return Settings()


def get_llm(temperature: float = 0) -> BaseChatModel:
    """Construct the configured chat model, keyed off LLM_PROVIDER.

    This is the one place in the codebase that imports a specific LLM SDK.
    Every graph node calls this instead of constructing ChatOpenAI (or any
    other provider's client) directly, so switching providers is a one-line
    .env change (LLM_PROVIDER=anthropic) rather than an edit in three
    separate node functions. Provider SDKs are imported inside their branch,
    not at module level, so selecting "openai" never requires
    langchain-anthropic (or vice versa) to be installed.

    Args:
        temperature (float): sampling temperature. Every node in this graph
            currently wants deterministic output (0), but it's left as a
            parameter rather than hardcoded here.

    Returns:
        BaseChatModel: the configured chat model instance.

    Raises:
        ValueError: if LLM_PROVIDER is set to a provider not implemented below.
    """
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=settings.llm_model, api_key=settings.llm_api_key, temperature=temperature)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=settings.llm_model, api_key=settings.llm_api_key, temperature=temperature)

    raise ValueError(f"Unsupported LLM_PROVIDER '{settings.llm_provider}'. Supported: 'openai', 'anthropic'.")
