from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class VoiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Reuse Groq key from LLM settings when STT key not set separately.
    stt_api_key: str = ""
    stt_base_url: str = "https://api.groq.com/openai/v1"
    stt_model: str = "whisper-large-v3"

    tts_voice: str = "en-US-JennyNeural"
    tts_enabled: bool = True

    # Live voice should use a fast LLM (Groq). Ollama on CPU can take 2–3 min/turn.
    voice_llm_base_url: str = ""
    voice_llm_model: str = "llama-3.1-8b-instant"
    voice_llm_api_key: str = ""

    default_restaurant_id: str = "hot_bagels_2nd_street"
    models_dir: str = "models"

    @property
    def effective_stt_api_key(self) -> str:
        if self.stt_api_key:
            return self.stt_api_key
        from dialogue.settings import get_dialogue_settings

        return get_dialogue_settings().llm_api_key


@lru_cache
def get_voice_settings() -> VoiceSettings:
    return VoiceSettings()
