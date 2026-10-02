"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://pipeline:pipeline@localhost:5432/modernization",
        alias="DATABASE_URL",
    )
    database_url_sync: str = Field(
        default="postgresql://pipeline:pipeline@localhost:5432/modernization",
        alias="DATABASE_URL_SYNC",
    )

    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )
    llm_model: str = Field(default="qwen/qwen3.8-27b:free", alias="LLM_MODEL")
    llm_fallback_models: str = Field(
        default=(
            "nvidia/nemotron-3-super-120b-a12b:free,"
            "google/gemma-4-31b-it:free,"
            "cohere/north-mini-code:free,"
            "openrouter/free"
        ),
        alias="LLM_FALLBACK_MODELS",
    )
    openrouter_http_referer: str = Field(
        default="https://github.com/m4rkdevbr/F4bioMiranteTeste2026",
        alias="OPENROUTER_HTTP_REFERER",
    )
    openrouter_app_title: str = Field(
        default="Modernization Pipeline",
        alias="OPENROUTER_APP_TITLE",
    )
    llm_temperature: float = Field(default=0.1, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=8192, alias="LLM_MAX_TOKENS")
    llm_timeout_seconds: int = Field(default=120, alias="LLM_TIMEOUT_SECONDS")

    langfuse_public_key: str = Field(default="", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(default="http://localhost:3000", alias="LANGFUSE_HOST")
    langfuse_enabled: bool = Field(default=False, alias="LANGFUSE_ENABLED")

    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8123, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @property
    def fallback_model_list(self) -> list[str]:
        return [m.strip() for m in self.llm_fallback_models.split(",") if m.strip()]

    @property
    def model_chain(self) -> list[str]:
        chain = [self.llm_model, *self.fallback_model_list]
        seen: set[str] = set()
        ordered: list[str] = []
        for model in chain:
            if model not in seen:
                seen.add(model)
                ordered.append(model)
        return ordered


@lru_cache
def get_settings() -> Settings:
    return Settings()
