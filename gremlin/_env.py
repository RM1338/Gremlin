"""Tiny .env loader shared by the model backends (no dependency).

Populates os.environ from a project-root `.env` (KEY=value) once, so keys can
live in one git-ignored file. Real environment variables always win.
"""

from __future__ import annotations

import os
from pathlib import Path

_loaded = False


def load_dotenv() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
