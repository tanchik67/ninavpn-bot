from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.enums import UserRole
from core.services.audit import write_audit
from core.services.security import (
    allocate_panel_user_key,
    create_access_token,
    create_refresh_token_value,
    hash_password,
    hash_token,
    verify_password,
)
from core.settings import saas_settings
from infrastructure.db.models import RefreshToken, User


class AuthError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


async def register_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    ip: Optional[str] = None,
) -> tuple[User, str, str]:
    email_n = email.strip().lower()
    existing = await session.scalar(select(User).where(User.email == email_n))
    if existing:
        raise AuthError("email_taken", "Email already registered")

    user = User(
        email=email_n,
        password_hash=hash_password(password),
        panel_user_key=0,  # set after flush for uuid
        role=UserRole.USER.value,
    )
    session.add(user)
    await session.flush()
    user.panel_user_key = allocate_panel_user_key(user.id)
    access, refresh = await _issue_tokens(session, user)
    await write_audit(
        session,
        action="user.register",
        entity_type="user",
        entity_id=str(user.id),
        actor_user_id=user.id,
        ip=ip,
    )
    await session.commit()
    await session.refresh(user)
    return user, access, refresh


async def login_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    ip: Optional[str] = None,
) -> tuple[User, str, str]:
    email_n = email.strip().lower()
    user = await session.scalar(select(User).where(User.email == email_n))
    if not user or not verify_password(password, user.password_hash):
        raise AuthError("invalid_credentials", "Invalid email or password")
    if user.is_banned:
        raise AuthError("banned", "Account is banned")
    access, refresh = await _issue_tokens(session, user)
    await write_audit(
        session,
        action="user.login",
        entity_type="user",
        entity_id=str(user.id),
        actor_user_id=user.id,
        ip=ip,
    )
    await session.commit()
    return user, access, refresh


async def refresh_session(session: AsyncSession, refresh_token: str) -> tuple[User, str, str]:
    th = hash_token(refresh_token)
    row = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == th))
    if not row or row.revoked_at is not None or row.expires_at < datetime.utcnow():
        raise AuthError("invalid_refresh", "Invalid refresh token")
    user = await session.get(User, row.user_id)
    if not user or user.is_banned:
        raise AuthError("invalid_refresh", "Invalid refresh token")
    row.revoked_at = datetime.utcnow()
    access, new_refresh = await _issue_tokens(session, user)
    await session.commit()
    return user, access, new_refresh


async def logout(session: AsyncSession, refresh_token: str) -> None:
    th = hash_token(refresh_token)
    row = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == th))
    if row and row.revoked_at is None:
        row.revoked_at = datetime.utcnow()
        await session.commit()


async def _issue_tokens(session: AsyncSession, user: User) -> tuple[str, str]:
    access = create_access_token(user_id=user.id, role=user.role)
    refresh = create_refresh_token_value()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh),
            expires_at=datetime.utcnow() + timedelta(days=saas_settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    return access, refresh


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> Optional[User]:
    return await session.get(User, user_id)
