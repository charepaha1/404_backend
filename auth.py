from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from config import SECRET, TOKEN_TTL_SECONDS


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), 120_000)
    return f"{salt}:{digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split(":", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), 120_000).hex()
    return hmac.compare_digest(digest, expected)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def sign_token(user_id: int) -> str:
    payload = {"sub": user_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    payload_raw = b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(SECRET.encode("utf-8"), payload_raw.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_raw}.{b64url(signature)}"


def read_token(token: str | None) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    payload_raw, signature_raw = token.split(".", 1)
    expected = b64url(hmac.new(SECRET.encode("utf-8"), payload_raw.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature_raw, expected):
        return None

    padded = payload_raw + "=" * (-len(payload_raw) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (ValueError, json.JSONDecodeError):
        return None

    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload
