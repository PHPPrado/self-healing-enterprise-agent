"""Central configuration for the self-healing enterprise agent.

Edit this file to change cloud provider, LLM settings, and retry limits.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CloudProvider(str, Enum):
    MOCK = "MOCK"
    AWS = "AWS"
    OCI = "OCI"
    GCP = "GCP"
    AZURE = "AZURE"


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Cloud provider selection. Change this to swap cloud backends.
    cloud_provider: CloudProvider = Field(default=CloudProvider.MOCK, alias="CLOUD_PROVIDER")

    # Self-healing retry configuration
    max_self_healing_retries: int = Field(default=3, alias="MAX_SELF_HEALING_RETRIES", ge=0, le=10)

    # LLM configuration
    llm_model_name: str = Field(default="gpt-4o-mini", alias="LLM_MODEL_NAME")
    llm_api_key: str = Field(default="mock", alias="LLM_API_KEY")
    llm_base_url: str | None = Field(default=None, alias="LLM_BASE_URL")
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE", ge=0.0, le=2.0)

    # API
    api_title: str = "Self-Healing Enterprise Agent"
    api_version: str = "1.0.0"

    @property
    def is_mock_llm(self) -> bool:
        return self.llm_api_key.strip().lower() in {"", "mock", "none", "null"}

    @property
    def cloud_provider_str(self) -> Literal["MOCK", "AWS", "OCI", "GCP", "AZURE"]:
        return self.cloud_provider.value  # type: ignore[return-value]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
"""Module-level singleton used across the app."""
