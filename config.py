from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(ROOT / ".env")
load_env_file(PROJECT_ROOT / "bot" / ".env")

DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("BACKEND_DB", DATA_DIR / "app.db"))
HOST = os.environ.get("BACKEND_HOST", "0.0.0.0")
PORT = int(os.environ.get("BACKEND_PORT", "8000"))
SECRET = os.environ.get("BACKEND_SECRET", "change-me-for-production")
BOT_TOKEN = os.environ.get("BACKEND_BOT_TOKEN", "change-me-404-bot-token")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN", "")
ADMIN_IDS = [
    int(value.strip())
    for value in os.environ.get("ADMIN_IDS", "").split(",")
    if value.strip().lstrip("-").isdigit()
]
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.environ.get("MONGO_DB", "diplom_404")
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 14
