"""Google ID token + Telegram Login Widget verification."""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Optional

import httpx
from jose import jwt
from jose.exceptions import JWTError

from core.settings import saas_settings


class OAuthVerifyError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


_google_jwks_cache: Optional[dict[str, Any]] = None
_google_jwks_fetched_at: float = 0.0
_JWKS_TTL = 3600.0


async def _get_google_jwks() -> dict[str, Any]:
    global _google_jwks_cache, _google_jwks_fetched_at
    now = time.time()
    if _google_jwks_cache and (now - _google_jwks_fetched_at) < _JWKS_TTL:
        return _google_jwks_cache
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.get("https://www.googleapis.com/oauth2/v3/certs")
        res.raise_for_status()
        _google_jwks_cache = res.json()
        _google_jwks_fetched_at = now
        return _google_jwks_cache


def _google_audiences() -> list[str]:
    return [x.strip() for x in saas_settings.GOOGLE_CLIENT_IDS.split(",") if x.strip()]


async def verify_google_id_token(id_token: str) -> dict[str, Any]:
    """Verify Google ID token; returns claims (sub, email, email_verified, name, …)."""
    audiences = _google_audiences()
    if not audiences:
        raise OAuthVerifyError("google_not_configured")

    try:
        header = jwt.get_unverified_header(id_token)
    except JWTError as e:
        raise OAuthVerifyError("invalid_google_token") from e

    kid = header.get("kid")
    if not kid:
        raise OAuthVerifyError("invalid_google_token")

    try:
        jwks = await _get_google_jwks()
    except Exception as e:
        raise OAuthVerifyError("google_jwks_unavailable") from e

    key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if not key:
        # refresh once
        global _google_jwks_fetched_at
        _google_jwks_fetched_at = 0
        jwks = await _get_google_jwks()
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if not key:
        raise OAuthVerifyError("invalid_google_token")

    try:
        claims = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=audiences,
            issuer=["https://accounts.google.com", "accounts.google.com"],
            options={"verify_at_hash": False},
        )
    except JWTError as e:
        raise OAuthVerifyError("invalid_google_token") from e

    if not claims.get("sub"):
        raise OAuthVerifyError("invalid_google_token")
    return claims


def verify_telegram_login(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Verify Telegram Login Widget data per
    https://core.telegram.org/widgets/login#checking-authorization
    """
    bot_token = saas_settings.BOT_TOKEN
    if not bot_token:
        raise OAuthVerifyError("telegram_not_configured")

    check_hash = payload.get("hash")
    if not check_hash or not isinstance(check_hash, str):
        raise OAuthVerifyError("invalid_telegram_auth")

    auth_date = payload.get("auth_date")
    try:
        auth_ts = int(auth_date)
    except (TypeError, ValueError):
        raise OAuthVerifyError("invalid_telegram_auth")

    if time.time() - auth_ts > saas_settings.TELEGRAM_AUTH_MAX_AGE_SEC:
        raise OAuthVerifyError("telegram_auth_expired")

    pairs: list[str] = []
    for key in sorted(payload.keys()):
        if key == "hash":
            continue
        val = payload[key]
        if val is None or val == "":
            continue
        pairs.append(f"{key}={val}")
    data_check_string = "\n".join(pairs)
    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    calculated = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(calculated, check_hash):
        raise OAuthVerifyError("invalid_telegram_auth")

    try:
        tg_id = int(payload["id"])
    except (KeyError, TypeError, ValueError) as e:
        raise OAuthVerifyError("invalid_telegram_auth") from e

    return {
        "id": tg_id,
        "first_name": payload.get("first_name") or "",
        "last_name": payload.get("last_name") or "",
        "username": payload.get("username") or None,
        "photo_url": payload.get("photo_url") or None,
        "auth_date": auth_ts,
    }
