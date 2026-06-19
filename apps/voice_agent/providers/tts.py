from __future__ import annotations

import sys
from pathlib import Path

import edge_tts

from apps.voice_agent.settings import VoiceSettings


class EdgeTTSProvider:
    """Local-friendly TTS using Microsoft Edge voices (network required)."""

    def __init__(self, settings: VoiceSettings) -> None:
        self._voice = settings.tts_voice

    async def synthesize(self, text: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(text, self._voice)
        await communicate.save(str(output_path))
        return output_path


class TextTTSProvider:
    """Print-only TTS for headless/CI tests."""

    async def synthesize(self, text: str, output_path: Path) -> Path:
        print(f"[TTS] {text}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        return output_path


def play_audio(path: Path) -> None:
    """Best-effort playback on Windows/macOS/Linux."""
    if path.suffix.lower() == ".txt":
        return
    if sys.platform == "win32":
        import os

        os.startfile(str(path))  # noqa: S606
        return
    import subprocess

    if sys.platform == "darwin":
        subprocess.run(["afplay", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)
