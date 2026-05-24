from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("BACKEND_DB", DATA_DIR / "app.db"))
HOST = os.environ.get("BACKEND_HOST", "127.0.0.1")
PORT = int(os.environ.get("BACKEND_PORT", "8000"))
SECRET = os.environ.get("BACKEND_SECRET", "change-me-for-production")
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 14
