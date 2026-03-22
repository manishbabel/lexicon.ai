"""Config loading from environment variables and ~/.lexicon/config.json."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

from .constants import CONFIG_PATH, GATEWAY_HOST, GATEWAY_PORT


class Settings(BaseSettings):
    # API Keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    deepgram_api_key: str = ""
    tavily_api_key: str = ""

    # LLM routing
    default_llm_provider: str = "openai"
    default_llm_model: str = ""
    chief_llm_provider: str = ""
    chief_llm_model: str = ""
    software_engineer_llm_provider: str = ""
    software_engineer_llm_model: str = ""
    ai_educator_llm_provider: str = ""
    ai_educator_llm_model: str = ""
    doctor_llm_provider: str = ""
    doctor_llm_model: str = ""

    # Gateway
    gateway_host: str = GATEWAY_HOST
    gateway_port: int = GATEWAY_PORT

    # Logging
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def load_settings() -> Settings:
    """Load settings from env vars, .env file, and ~/.lexicon/config.json."""
    # Start with env vars / .env file
    settings = Settings()

    # Override with ~/.lexicon/config.json if it exists
    if CONFIG_PATH.exists():
        try:
            file_config = json.loads(CONFIG_PATH.read_text())
            # Map JSON keys to settings fields
            field_map = {
                "openai_api_key": "openai_api_key",
                "anthropic_api_key": "anthropic_api_key",
                "deepgram_api_key": "deepgram_api_key",
                "default_llm_provider": "default_llm_provider",
                "default_llm_model": "default_llm_model",
                "chief_llm_provider": "chief_llm_provider",
                "chief_llm_model": "chief_llm_model",
                "software_engineer_llm_provider": "software_engineer_llm_provider",
                "software_engineer_llm_model": "software_engineer_llm_model",
                "ai_educator_llm_provider": "ai_educator_llm_provider",
                "ai_educator_llm_model": "ai_educator_llm_model",
                "doctor_llm_provider": "doctor_llm_provider",
                "doctor_llm_model": "doctor_llm_model",
                "gateway_host": "gateway_host",
                "gateway_port": "gateway_port",
                "log_level": "log_level",
            }
            updates = {}
            for json_key, field_name in field_map.items():
                if json_key in file_config and file_config[json_key]:
                    updates[field_name] = file_config[json_key]
            if updates:
                settings = settings.model_copy(update=updates)
        except (json.JSONDecodeError, KeyError):
            pass

    return settings


# Singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings
