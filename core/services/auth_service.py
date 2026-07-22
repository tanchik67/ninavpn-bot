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
    if (
        not user
        or not user.password_hash
        or not verify_password(password, user.password_hash)
    ):
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


async def login_or_register_google(
    session: AsyncSession,
    *,
    google_sub: str,
    email: str,
    email_verified: bool = False,
    ip: Optional[str] = None,
) -> tuple[User, str, str]:
    email_n = email.strip().lower()
    user = await session.scalar(select(User).where(User.google_sub == google_sub))
    if not user:
        by_email = await session.scalar(select(User).where(User.email == email_n))
        if by_email:
            if by_email.is_banned:
                raise AuthError("banned", "Account is banned")
            by_email.google_sub = google_sub
            if email_verified and not by_email.email_verified_at:
                by_email.email_verified_at = datetime.utcnow()
            user = by_email
        else:
            user = User(
                email=email_n,
                password_hash=None,
                google_sub=google_sub,
                panel_user_key=0,
                role=UserRole.USER.value,
                email_verified_at=datetime.utcnow() if email_verified else None,
            )
            session.add(user)
            await session.flush()
            user.panel_user_key = allocate_panel_user_key(user.id)

    if user.is_banned:
        raise AuthError("banned", "Account is banned")

    access, refresh = await _issue_tokens(session, user)
    await write_audit(
        session,
        action="user.login_google",
        entity_type="user",
        entity_id=str(user.id),
        actor_user_id=user.id,
        ip=ip,
        meta={"google_sub": google_sub},
    )
    await session.commit()
    await session.refresh(user)
    return user, access, refresh


async def login_or_register_telegram(
    session: AsyncSession,
    *,
    tg_id: int,
    username: Optional[str] = None,
    ip: Optional[str] = None,
) -> tuple[User, str, str]:
    user = await session.scalar(select(User).where(User.tg_id == tg_id))
    if not user:
        placeholder = f"tg_{tg_id}@telegram.local"
        user = User(
            email=placeholder,
            password_hash=None,
            tg_id=tg_id,
            panel_user_key=0,
            role=UserRole.USER.value,
        )
        session.add(user)
        await session.flush()
        user.panel_user_key = allocate_panel_user_key(user.id)

    if user.is_banned:
        raise AuthError("banned", "Account is banned")

    access, refresh = await _issue_tokens(session, user)
    await write_audit(
        session,
        action="user.login_telegram",
        entity_type="user",
        entity_id=str(user.id),
        actor_user_id=user.id,
        ip=ip,
        meta={"tg_id": tg_id, "username": username},
    )
    await session.commit()
    await session.refresh(user)
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


async def revoke_all_refresh_tokens(session: AsyncSession, user_id: UUID) -> None:
    rows = await session.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    now = datetime.utcnow()
    for row in rows:
        row.revoked_at = now


async def change_password(
    session: AsyncSession,
    *,
    user: User,
    current_password: Optional[str],
    new_password: str,
    ip: Optional[str] = None,
) -> None:
    if user.password_hash:
        if not current_password or not verify_password(current_password, user.password_hash):
            raise AuthError("invalid_current_password", "Current password is wrong")
    user.password_hash = hash_password(new_password)
    await revoke_all_refresh_tokens(session, user.id)
    await write_audit(
        session,
        action="user.password_change",
        entity_type="user",
        entity_id=str(user.id),
        actor_user_id=user.id,
        ip=ip,
    )
    await session.commit()


async def reset_password_with_code(
    session: AsyncSession,
    *,
    email: str,
    new_password: str,
    ip: Optional[str] = None,
) -> User:
    email_n = email.strip().lower()
    user = await session.scalar(select(User).where(User.email == email_n))
    if not user:
        raise AuthError("invalid_code", "Invalid or expired code")
    if user.is_banned:
        raise AuthError("banned", "Account is banned")
    user.password_hash = hash_password(new_password)
    await revoke_all_refresh_tokens(session, user.id)
    await write_audit(
        session,
        action="user.password_reset",
        entity_type="user",
        entity_id=str(user.id),
        actor_user_id=user.id,
        ip=ip,
    )
    await session.commit()
    await session.refresh(user)
    return user


async def find_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    return await session.scalar(select(User).where(User.email == email.strip().lower()))


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
