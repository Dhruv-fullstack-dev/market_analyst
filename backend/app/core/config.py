from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central app configuration, loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM (Google Gemini free tier)
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # Logging
    log_level: str = "INFO"
    log_file: str = "dump.log"

    # Backend
    backend_url: str = "http://localhost:8000"

    # Cache TTLs (seconds)
    quote_cache_ttl_seconds: int = 60
    history_cache_ttl_seconds: int = 300
    fundamentals_cache_ttl_seconds: int = 86400
    search_cache_ttl_seconds: int = 86400
    search_max_results: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()
