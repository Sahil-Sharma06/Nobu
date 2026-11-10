"""Application settings, read only from environment variables (or a local .env)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NOBU_", env_file="../.env", extra="ignore")

    database_url: str = "sqlite:///./nobu.db"

    llm_provider: Literal["stub", "ollama", "anthropic", "openai_compat"] = "stub"
    llm_model: str = "llama3.1:8b"
    ollama_url: str = "http://localhost:11434"
    llm_base_url: str = ""  # openai_compat only
    llm_api_key: str = ""  # openai_compat only (NOBU_LLM_API_KEY)
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")

    dry_run: bool = True
    daily_cap: int = Field(default=15, ge=0)
    dedupe_days: int = Field(default=60, ge=0)

    data_dir: Path = Path("../data")


@lru_cache
def get_settings() -> Settings:
    return Settings()
