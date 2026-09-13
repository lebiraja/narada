from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://band:change-me@postgres:5432/band"
    redis_url: str = "redis://redis:6379/0"
    secret_key: str = "change-me"

    llm_base_url: str = "https://api.anthropic.com/v1"
    llm_api_key: str = ""
    llm_model_leader: str = "claude-opus-5"
    llm_model_player: str = "claude-haiku-4-5-20251001"


@lru_cache
def get_settings() -> Settings:
    return Settings()
