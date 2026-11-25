from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Travel Planner"
    environment: str = "local"

    database_url: str
    checkpoint_db_url: str

    groq_api_key: str
    groq_model: str = "openai/gpt-oss-120b"
    tavily_api_key: str
    aviationstack_api_key: str

    max_revisions: int = 3

    # JWT Authentication
    jwt_secret_key: str = "travel-planner-super-secret-jwt-key-2026-auth"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24 * 7  # 7 days


@lru_cache
def get_settings() -> Settings:
    return Settings()
