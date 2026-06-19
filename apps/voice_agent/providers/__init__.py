from __future__ import annotations

from pathlib import Path
from typing import Protocol

from order_engine.catalog import MenuCatalog


class STTProvider(Protocol):
    async def transcribe(self, audio_path: Path) -> str: ...


class TTSProvider(Protocol):
    async def synthesize(self, text: str, output_path: Path) -> Path: ...


def load_catalog(restaurant_id: str) -> MenuCatalog:
    config_dir = Path(__file__).resolve().parents[3] / "config" / "restaurants" / restaurant_id
    return MenuCatalog.from_path(config_dir)
