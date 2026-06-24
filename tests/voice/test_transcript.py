from __future__ import annotations

from pathlib import Path

import pytest
from order_engine.catalog import MenuCatalog

from apps.voice_agent.transcript import normalize_transcript

CONFIG_DIR = (
    Path(__file__).resolve().parents[2] / "config" / "restaurants" / "hot_bagels_2nd_street"
)


@pytest.fixture
def catalog() -> MenuCatalog:
    return MenuCatalog.from_path(CONFIG_DIR)


@pytest.fixture
def pronunciations() -> dict[str, list[str]]:
    from apps.voice_agent.transcript import load_pronunciations

    return load_pronunciations("hot_bagels_2nd_street")


def test_normalize_barakas_to_bourekas(catalog: MenuCatalog, pronunciations: dict) -> None:
    result = normalize_transcript("tray of barakas", catalog, pronunciation_aliases=pronunciations)
    assert "bourekas" in result.lower()


def test_normalize_passthrough(catalog: MenuCatalog) -> None:
    text = "cream cheese sandwich"
    assert normalize_transcript(text, catalog) == text
