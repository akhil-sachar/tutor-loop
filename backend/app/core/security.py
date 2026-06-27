from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone


def hash_password(password: str, salt: str | None = None) -> str:
    # Hackathon demo auth. Swap for passlib/bcrypt before production.
    salt = salt or secrets.token_hex(16)
    digest = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, digest = stored_hash.split("$", 1)
    except ValueError:
        return False
    candidate = hash_password(password, salt).split("$", 1)[1]
    return hmac.compare_digest(candidate, digest)


def make_demo_token(user_id: str, secret: str) -> str:
    timestamp = str(int(datetime.now(timezone.utc).timestamp()))
    signature = hmac.new(secret.encode("utf-8"), f"{user_id}:{timestamp}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"demo.{user_id}.{timestamp}.{signature}"
