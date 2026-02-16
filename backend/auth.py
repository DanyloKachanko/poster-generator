"""Simple authentication for production deployment."""

import base64
import hashlib
import hmac
import json
import os
import time

# PBKDF2-SHA256 hash of the admin password
_SALT = "poster-gen-auth-v1"
_PASSWORD_HASH = "77wT2pNbyONVpFNpxr/ObRU++CdDsfS3iCXwTrA37PI="
_ADMIN_USER = "admin"
_TOKEN_TTL = 7 * 24 * 3600  # 7 days

REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "").lower() in ("true", "1", "yes")


def _get_secret() -> bytes:
    return os.getenv("AUTH_SECRET", "poster-gen-token-secret-v1").encode()


def verify_password(username: str, password: str) -> bool:
    if username != _ADMIN_USER:
        return False
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), _SALT.encode(), 100000)
    expected = base64.b64decode(_PASSWORD_HASH)
    return hmac.compare_digest(h, expected)


def create_token(username: str) -> str:
    payload = json.dumps({"user": username, "exp": int(time.time()) + _TOKEN_TTL})
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    sig = hmac.new(_get_secret(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_token(token: str) -> bool:
    try:
        parts = token.split(".", 1)
        if len(parts) != 2:
            return False
        payload_b64, sig = parts
        expected_sig = hmac.new(
            _get_secret(), payload_b64.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return False
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return False
        return True
    except Exception:
        return False
