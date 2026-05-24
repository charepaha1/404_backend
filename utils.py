from __future__ import annotations

import secrets
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_code(prefix: str) -> str:
    return f"{prefix}{secrets.token_hex(4).upper()}"
