"""
Central config — reads from environment variables / .env file.

WHY pydantic-settings: type-safe env var parsing, auto-validation,
                       IDE autocomplete, and fails loud on missing required vars.
                       Senior practice: never scatter os.environ.get() calls across files.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Redis
    redis_url: str = "redis://redis:6379/0"

    # PostgreSQL
    database_url: str

    # HuggingFace
    huggingface_api_token: str
    hf_model_id: str = "mistralai/Mistral-7B-Instruct-v0.3"

    # LLM behaviour
    llm_temperature: float = 0.3  # lower = more deterministic, better for agents

    # Shared media volume — same mount as Django's MEDIA_ROOT
    media_root: str = "/media"

    # Internal service communication
    django_internal_url: str = "http://core-api:8000"   # Docker service name
    internal_api_key: str = "dev-internal-key-change-in-prod"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """
    Cached singleton — settings are read once at startup.
    WHY lru_cache: avoids re-reading .env on every call (cheap but good habit).
    """
    return Settings()
