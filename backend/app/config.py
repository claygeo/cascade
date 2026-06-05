"""Application configuration, loaded from environment / .env via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    environment: str = "development"
    log_level: str = "info"

    # --- Database ---
    database_url: str
    db_schema: str = "cascade"
    db_ssl_require: bool = False  # Supabase pooler requires SSL; local Postgres does not

    # --- Auth ---
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 14

    # --- BYOK encryption ---
    fernet_key: str

    # --- LLM (OpenRouter) ---
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_default_model: str = "openai/gpt-4o-mini"
    llm_max_output_tokens: int = 512
    llm_request_timeout_seconds: int = 60

    # --- Public sample-run rate limit ---
    sample_runs_per_hour_per_ip: int = 10

    # --- Worker ---
    worker_id: str = "worker-local"
    run_lease_seconds: int = 60
    run_max_attempts: int = 2
    worker_poll_interval_seconds: int = 2
    http_fetch_timeout_seconds: int = 20
    run_worker_in_process: bool = False  # run the worker loop inside the API process

    # --- CORS ---
    frontend_origin: str = "http://localhost:5173"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def cors_origins(self) -> list[str]:
        """Allow a comma-separated list of allowed origins."""
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
