from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    ticketing_api_base_url: str = Field(alias="TICKETING_API_URL")
    ticketing_api_token: str = Field(alias="TICKETING_API_TOKEN")
    request_timeout_seconds: float = Field(default=5.0, alias="TICKETING_API_TIMEOUT_SECONDS")
    max_retries: int = Field(default=3, alias="TICKETING_API_MAX_RETRIES")

    # stdio: spawned as a local subprocess by a client (Claude Desktop, MCP
    # Inspector, Claude Code). streamable-http: a real network service, used
    # when this server runs in its own container (e.g. docker-compose).
    mcp_transport: str = Field(default="stdio", alias="MCP_TRANSPORT")
    mcp_host: str = Field(default="0.0.0.0", alias="MCP_HOST")
    mcp_port: int = Field(default=9100, alias="MCP_PORT")


@lru_cache
def get_settings() -> Settings:
    """Return the cached, process-wide Settings instance.

    Args:
        None

    Returns:
        Settings: the loaded configuration singleton.
    """
    return Settings()
