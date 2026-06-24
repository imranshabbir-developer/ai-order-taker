"""Start voice CLI — sets PYTHONPATH automatically."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

raise SystemExit(
    subprocess.call([sys.executable, str(ROOT / "scripts" / "run_voice_cli.py"), *sys.argv[1:]])
)
