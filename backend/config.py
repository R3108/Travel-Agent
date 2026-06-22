"""Central configuration, loaded from environment / .env file."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings sourced from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM ---
    # Provide the key for whichever provider MODEL points at. Only one is needed.
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    # LiteLLM-style "provider/model" string consumed by CrewAI's LLM wrapper.
    # e.g. "openrouter/deepseek/deepseek-chat-v3.1:free" or "gemini/gemini-2.5-flash".
    model: str = "openrouter/deepseek/deepseek-chat-v3.1:free"

    # --- Optional data integrations (mock fallback when blank) ---
    tavily_api_key: str = ""
    serper_api_key: str = ""
    openweather_api_key: str = ""

    # --- Server ---
    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def provider(self) -> str:
        """Provider prefix from the model string, e.g. 'openrouter' or 'gemini'."""
        return self.model.split("/", 1)[0].strip().lower()

    @property
    def llm_api_key(self) -> str:
        """The API key matching the configured provider."""
        if self.provider == "openrouter":
            return self.openrouter_api_key.strip()
        return self.gemini_api_key.strip()

    @property
    def has_llm_key(self) -> bool:
        return bool(self.llm_api_key)

    def export_provider_env(self) -> None:
        """Expose the key under the env name the active provider / LiteLLM expect."""
        key = self.llm_api_key
        if not key:
            return
        if self.provider == "openrouter":
            os.environ.setdefault("OPENROUTER_API_KEY", key)
        # Set only GEMINI_API_KEY — setting GOOGLE_API_KEY too triggers a
        # "both keys set" warning from the provider.
        elif not os.environ.get("GOOGLE_API_KEY"):
            os.environ.setdefault("GEMINI_API_KEY", key)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    settings = Settings()
    settings.export_provider_env()
    return settings
