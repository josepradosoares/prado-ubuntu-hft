"""Authentication and HMAC Session Token Manager for Prado Web Dashboard."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time


def hash_password(password: str, salt: str | None = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    if "$" not in stored_hash:
        return False
    salt, _ = stored_hash.split("$", 1)
    expected = hash_password(password, salt)
    return hmac.compare_digest(expected, stored_hash)


def create_session_token(username: str, secret_key: str, ttl_sec: int = 86400 * 7) -> str:
    expires = int(time.time()) + ttl_sec
    payload = f"{username}:{expires}"
    sig = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_session_token(token: str | None, secret_key: str) -> str | None:
    if not token or token.count(":") != 2:
        return None
    username, exp_str, sig = token.split(":")
    try:
        expires = int(exp_str)
    except ValueError:
        return None
    if time.time() > expires:
        return None
    payload = f"{username}:{expires}"
    expected_sig = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    return username
