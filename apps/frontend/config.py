from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    backend_url: str = Field(default="http://localhost:8080", alias="COPILOT_BACKEND_URL")
    request_timeout_seconds: float = Field(default=60.0, alias="COPILOT_REQUEST_TIMEOUT_SECONDS")

    # Ops tab reads this SQLite file directly. Same default and same env var
    # name as apps.backend.audit.DB_PATH, so one AUDIT_DB_PATH in .env points
    # both processes at the same file for local (non-Docker) dev, where
    # backend and frontend share a filesystem.
    audit_db_path: Path = Field(default=REPO_ROOT / "var" / "audit_trail.sqlite3", alias="AUDIT_DB_PATH")

    server_port: int = Field(default=3000, alias="COPILOT_FRONTEND_PORT")


@lru_cache
def get_settings() -> Settings:
    """Return the cached, process-wide Settings instance.

    Args:
        None

    Returns:
        Settings: the loaded configuration singleton.
    """
    return Settings()
