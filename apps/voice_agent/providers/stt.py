from __future__ import annotations

from pathlib import Path

import httpx

from apps.voice_agent.settings import VoiceSettings


class GroqWhisperSTT:
    """Speech-to-text via Groq OpenAI-compatible Whisper API."""

    def __init__(self, settings: VoiceSettings) -> None:
        self._settings = settings
        self._api_key = settings.effective_stt_api_key
        if not self._api_key:
            raise ValueError("STT API key missing. Set LLM_API_KEY or STT_API_KEY in .env")

    async def transcribe(self, audio_path: Path) -> str:
        url = f"{self._settings.stt_base_url.rstrip('/')}/audio/transcriptions"
        audio_bytes = audio_path.read_bytes()
        suffix = audio_path.suffix.lower().lstrip(".") or "wav"
        mime = "audio/wav" if suffix == "wav" else f"audio/{suffix}"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                files={"file": (audio_path.name, audio_bytes, mime)},
                data={"model": self._settings.stt_model, "language": "en"},
            )
            response.raise_for_status()
            payload = response.json()
            return str(payload.get("text", "")).strip()


class PassthroughSTT:
    """Use raw text as transcript (testing without audio)."""

    def __init__(self, text: str) -> None:
        self._text = text

    async def transcribe(self, audio_path: Path) -> str:
        return self._text
