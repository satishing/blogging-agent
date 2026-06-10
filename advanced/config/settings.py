from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App identity ---
    app_name: str = "production-blogging-agent"
    env: Literal["local", "dev", "staging", "prod"] = "local"
    log_level: str = "INFO"

    # --- API security ---
    api_auth_enabled: bool = True
    api_auth_header_name: str = "X-API-Key"
    api_auth_key: str | None = Field(default=None, alias="API_AUTH_KEY")
    api_rate_limit_enabled: bool = True
    api_rate_limit_per_minute: int = 30
    api_rate_limit_window_seconds: int = 60

    # --- LLM (via OpenRouter) ---
    model_name: str = Field(default="openai/gpt-4o")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")
    openrouter_api_key: str = Field(alias="OPENROUTER_API_KEY")

    # --- Web search (Serper) ---
    serper_api_key: str = Field(alias="SERPER_API_KEY")
    serper_api_url: str = "https://google.serper.dev/search"
    search_result_count: int = 10
    # Number of query variants SourceService issues per topic (1 = topic only;
    # 2 adds "<topic> latest"; 3 adds "<topic> <current-year>").
    search_query_variants: int = 1

    # --- Publishing (Dev.to) ---
    devto_api_key: str | None = Field(default=None, alias="DEVTO_API_KEY")
    devto_api_url: str = "https://dev.to/api/articles"
    publish_as_draft: bool = True

    # --- Cache ---
    cache_backend: Literal["file", "redis"] = "file"
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 3600

    # --- Content guardrails ---
    min_sources: int = 4
    min_source_year: int = Field(default_factory=lambda: date.today().year)
    # How far below `min_source_year` SourceService may relax the freshness floor
    # (in years) when there aren't enough sources at the target year.
    source_year_retry_steps: int = Field(default=3, ge=0)
    min_read_minutes: int = 6
    max_read_minutes: int = 8

    # --- Filesystem paths ---
    # Subpaths default to None and get derived from `data_dir` in the
    # validator below. Set them explicitly only when you need a path that
    # diverges from `<data_dir>/<subdir>`.
    data_dir: str = "data"
    output_dir: str | None = None
    log_dir: str | None = None
    cache_dir: str | None = None

    @model_validator(mode="after")
    def _derive_data_subdirs(self) -> "Settings":
        if self.output_dir is None:
            self.output_dir = f"{self.data_dir}/outputs"
        if self.log_dir is None:
            self.log_dir = f"{self.data_dir}/logs"
        if self.cache_dir is None:
            self.cache_dir = f"{self.data_dir}/cache"
        return self

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.output_dir, self.log_dir, self.cache_dir):
            if path:
                Path(path).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
