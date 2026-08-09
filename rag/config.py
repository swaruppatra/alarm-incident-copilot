from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    llm_api_key: str = Field(alias="LLM_API_KEY")
    vector_store_url: str = Field(alias="VECTOR_STORE_URL")
    # None locally (unauthenticated container); real hosted Qdrant clusters require it.
    qdrant_api_key: str | None = Field(default=None, alias="QDRANT_API_KEY")
    qdrant_collection_name: str = Field(default="alarm_incident_docs", alias="QDRANT_COLLECTION_NAME")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    # Starting point, not tuned yet -- revisit once run against the golden set.
    retrieval_score_threshold: float = Field(default=0.35, alias="RETRIEVAL_SCORE_THRESHOLD")


@lru_cache
def get_settings() -> Settings:
    """Return the cached, process-wide Settings instance.

    Args:
        None

    Returns:
        Settings: the loaded configuration singleton.
    """
    return Settings()
