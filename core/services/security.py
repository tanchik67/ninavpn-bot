from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from core.settings import saas_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(*, user_id: UUID, role: str, extra: Optional[dict[str, Any]] = None) -> str:
    expire = datetime.utcnow() + timedelta(minutes=saas_settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "exp": expire,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, saas_settings.JWT_SECRET, algorithm=saas_settings.JWT_ALGORITHM)


def create_refresh_token_value() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            saas_settings.JWT_SECRET,
            algorithms=[saas_settings.JWT_ALGORITHM],
        )
    except JWTError as e:
        raise ValueError("invalid_token") from e
    if payload.get("type") != "access":
        raise ValueError("invalid_token_type")
    return payload


def allocate_panel_user_key(user_uuid: UUID) -> int:
    """Deterministic 13-digit-ish key in site-user range for 3x-ui client email."""
    digest = hashlib.sha256(user_uuid.bytes).digest()
    n = int.from_bytes(digest[:6], "big") % 1_000_000_000_000
    return saas_settings.PANEL_USER_KEY_BASE + n
