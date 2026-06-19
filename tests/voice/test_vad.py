from __future__ import annotations

import struct

from apps.voice_agent.providers.vad import EnergyVAD


def test_energy_vad_detects_silence() -> None:
    vad = EnergyVAD(energy_threshold=100.0)
    silent = struct.pack("<1000h", *([0] * 1000))
    assert not vad.classify_chunk(silent).is_speech


def test_energy_vad_detects_speech() -> None:
    vad = EnergyVAD(energy_threshold=100.0)
    loud = struct.pack("<1000h", *([5000] * 1000))
    assert vad.classify_chunk(loud).is_speech


def test_end_of_turn_after_silence() -> None:
    vad = EnergyVAD(energy_threshold=100.0, silence_ms=100, min_speech_ms=50)
    speech = struct.pack("<1600h", *([8000] * 1600))
    silence = struct.pack("<1600h", *([0] * 1600))
    assert vad.end_of_turn(speech + silence, frame_ms=20, sample_rate=16000)
