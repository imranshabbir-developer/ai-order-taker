"""Start Voice WebSocket server — Sprint 4.7 browser test client."""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _resolve_port() -> int:
    preferred = int(os.getenv("VOICE_PORT", "8090"))
    if _port_available(preferred):
        return preferred
    for fallback in (8091, 8092, 9001):
        if _port_available(fallback):
            print(f"Port {preferred} busy — using {fallback}")
            return fallback
    raise SystemExit("No free port for voice server.")


if __name__ == "__main__":
    import uvicorn

    port = _resolve_port()
    print(f"Voice UI:  http://127.0.0.1:{port}/")
    print(f"WebSocket: ws://127.0.0.1:{port}/ws/voice/{{call_id}}")
    print("Requires Order API: python run_api.py")

    uvicorn.run(
        "apps.voice_agent.server:app",
        host="127.0.0.1",
        port=port,
        reload=True,
        reload_dirs=[str(ROOT / "apps"), str(ROOT / "packages")],
    )
