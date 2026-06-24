from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass
class VADResult:
    is_speech: bool
    energy: float


class EnergyVAD:
    """Lightweight end-of-utterance helper — no extra model downloads."""

    def __init__(
        self,
        *,
        energy_threshold: float = 500.0,
        min_speech_ms: int = 200,
        silence_ms: int = 700,
        sample_rate: int = 16000,
    ) -> None:
        self._threshold = energy_threshold
        self._min_speech_samples = int(sample_rate * min_speech_ms / 1000)
        self._silence_samples = int(sample_rate * silence_ms / 1000)

    @staticmethod
    def pcm16_rms(pcm_bytes: bytes) -> float:
        if len(pcm_bytes) < 2:
            return 0.0
        count = len(pcm_bytes) // 2
        samples = struct.unpack(f"<{count}h", pcm_bytes[: count * 2])
        if not samples:
            return 0.0
        mean_sq = sum(s * s for s in samples) / len(samples)
        return mean_sq**0.5

    def classify_chunk(self, pcm_bytes: bytes) -> VADResult:
        energy = self.pcm16_rms(pcm_bytes)
        return VADResult(is_speech=energy >= self._threshold, energy=energy)

    def end_of_turn(
        self, pcm_stream: bytes, *, frame_ms: int = 30, sample_rate: int = 16000
    ) -> bool:
        """Return True when trailing silence exceeds configured threshold."""
        frame_bytes = int(sample_rate * frame_ms / 1000) * 2
        if len(pcm_stream) < frame_bytes:
            return False

        speech_samples = 0
        trailing_silence = 0
        for offset in range(0, len(pcm_stream), frame_bytes):
            chunk = pcm_stream[offset : offset + frame_bytes]
            if not chunk:
                break
            if self.classify_chunk(chunk).is_speech:
                speech_samples += len(chunk) // 2
                trailing_silence = 0
            else:
                trailing_silence += len(chunk) // 2

        if speech_samples < self._min_speech_samples:
            return False
        return trailing_silence >= self._silence_samples
