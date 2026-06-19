"""Apply Alembic migrations — requires DATABASE_URL in .env."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    import subprocess
    import sys

    root = Path(__file__).resolve().parent
    sys.exit(
        subprocess.call(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(root),
        )
    )
