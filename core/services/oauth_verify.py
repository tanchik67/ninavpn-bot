"""Google ID token + Telegram Login Widget verification."""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Optional

import httpx
from jose import jwk, jwt
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


def _audience_ok(claims: dict[str, Any], audiences: list[str]) -> bool:
    aud = claims.get("aud")
    if isinstance(aud, list):
        if any(a in audiences for a in aud):
            return True
    elif aud in audiences:
        return True
    # Some Google tokens put the web client in azp
    azp = claims.get("azp")
    return isinstance(azp, str) and azp in audiences


async def _verify_google_via_tokeninfo(id_token: str, audiences: list[str]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
        )
    if res.status_code != 200:
        raise OAuthVerifyError("invalid_google_token")
    claims = res.json()
    if not _audience_ok(claims, audiences):
        raise OAuthVerifyError("invalid_google_token")
    if not claims.get("sub"):
        raise OAuthVerifyError("invalid_google_token")
    # tokeninfo returns email_verified as "true"/"false" strings
    verified = claims.get("email_verified")
    if isinstance(verified, str):
        claims["email_verified"] = verified.lower() == "true"
    return claims


async def _verify_google_via_jwks(id_token: str, audiences: list[str]) -> dict[str, Any]:
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
        global _google_jwks_fetched_at
        _google_jwks_fetched_at = 0
        jwks = await _get_google_jwks()
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if not key:
        raise OAuthVerifyError("invalid_google_token")

    try:
        key_obj = jwk.construct(key)
    except Exception as e:
        raise OAuthVerifyError("invalid_google_token") from e

    last_err: Optional[Exception] = None
    # Verify signature + iss/exp first; check aud/azp ourselves (Google may put client in azp).
    for issuer in ("https://accounts.google.com", "accounts.google.com"):
        try:
            claims = jwt.decode(
                id_token,
                key_obj,
                algorithms=["RS256"],
                issuer=issuer,
                options={
                    "verify_at_hash": False,
                    "verify_aud": False,
                },
            )
            if not _audience_ok(claims, audiences):
                raise OAuthVerifyError("invalid_google_token")
            if not claims.get("sub"):
                raise OAuthVerifyError("invalid_google_token")
            return claims
        except OAuthVerifyError:
            raise
        except JWTError as e:
            last_err = e
            continue
    raise OAuthVerifyError("invalid_google_token") from last_err


async def verify_google_id_token(id_token: str) -> dict[str, Any]:
    """Verify Google ID token; returns claims (sub, email, email_verified, name, …)."""
    audiences = _google_audiences()
    if not audiences:
        raise OAuthVerifyError("google_not_configured")

    token = (id_token or "").strip()
    if not token or token.count(".") != 2:
        raise OAuthVerifyError("invalid_google_token")

    try:
        return await _verify_google_via_jwks(token, audiences)
    except OAuthVerifyError as e:
        if e.code == "google_jwks_unavailable":
            return await _verify_google_via_tokeninfo(token, audiences)
        # Fallback: Google tokeninfo (handles edge cases python-jose misses)
        try:
            return await _verify_google_via_tokeninfo(token, audiences)
        except OAuthVerifyError:
            raise e


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
