"""Start Order API — sets PYTHONPATH automatically (Windows-friendly)."""

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
    preferred = int(os.getenv("PORT", "8080"))
    if _port_available(preferred):
        return preferred
    for fallback in (8000, 8001, 8888, 9000):
        if fallback != preferred and _port_available(fallback):
            print(f"Port {preferred} is busy — using {fallback} instead.")
            print(f"Update apps/admin/.env: VITE_API_PORT={fallback}")
            return fallback
    raise SystemExit(
        "No free port found. Stop the process using the port:\n"
        "  netstat -ano | findstr :8080\n"
        "  taskkill /PID <pid> /F"
    )


if __name__ == "__main__":
    import uvicorn

    port = _resolve_port()
    print(f"Order API: http://127.0.0.1:{port}")
    print(f"Docs:      http://127.0.0.1:{port}/docs")

    uvicorn.run(
        "apps.order_api.main:app",
        host="127.0.0.1",
        port=port,
        reload=True,
        reload_dirs=[str(ROOT / "apps"), str(ROOT / "packages")],
    )
