"""Run scenario tests — sets PYTHONPATH automatically."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
env = {**dict(__import__("os").environ), "PYTHONPATH": str(ROOT / "packages")}

raise SystemExit(
    subprocess.call(
        [sys.executable, "-m", "pytest", "tests/scenarios/", "-v", *sys.argv[1:]],
        cwd=ROOT,
        env=env,
    )
)
