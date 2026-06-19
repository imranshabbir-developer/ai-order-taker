from __future__ import annotations

import json
import time
from pathlib import Path


class LatencyLogger:
    """Append per-turn latency metrics for Sprint 4.8 profiling."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Path("output/voice/latency.jsonl")
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        *,
        call_id: str,
        event: str,
        latency_ms: dict[str, float],
        extra: dict | None = None,
    ) -> None:
        row = {
            "ts": time.time(),
            "call_id": call_id,
            "event": event,
            "latency_ms": latency_ms,
            **(extra or {}),
        }
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
