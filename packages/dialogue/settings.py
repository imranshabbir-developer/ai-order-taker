from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class DialogueSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_base_url: str = "http://127.0.0.1:8001/v1"
    llm_api_key: str = "not-needed"
    llm_model: str = "Qwen/Qwen2.5-7B-Instruct-AWQ"
    llm_timeout_seconds: float = 60.0
    llm_max_tool_rounds: int = 8

    order_api_base_url: str = "http://127.0.0.1:8080"
    default_restaurant_id: str = "hot_bagels_2nd_street"


@lru_cache
def get_dialogue_settings() -> DialogueSettings:
    return DialogueSettings()
