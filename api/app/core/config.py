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

    #: How many players may call the model at once. Five is one bar in
    #: parallel, which is fastest; lower it when the provider's tokens-per-
    #: minute budget cannot absorb five reasoning calls at once.
    llm_max_concurrency: int = 5

    #: Reasoning budget for the per-bar players. They need to be quick and in
    #: time, not deep: "low" costs roughly a fifth of the tokens for the same
    #: musical result. Blank disables the parameter for providers without it.
    llm_player_effort: str = "low"
    llm_leader_effort: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
