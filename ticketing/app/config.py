from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    ticketing_api_token: str = Field(alias="TICKETING_API_TOKEN")
    ticketing_db_path: str = Field(default="./var/ticketing.sqlite3", alias="TICKETING_DB_PATH")


@lru_cache
def get_settings() -> Settings:
    """Return the cached, process-wide Settings instance.

    Args:
        None

    Returns:
        Settings: the loaded configuration singleton.
    """
    return Settings()
