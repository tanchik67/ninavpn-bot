"""Пользователи, оформившие подписку на сайте (без Telegram)."""
from __future__ import annotations

import re
import secrets

from sqlalchemy import select

from config import SITE_USER_TG_ID_BASE
from database import AsyncSessionLocal, User

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_checkout_email(raw: str) -> str:
    return (raw or "").strip().lower()


def is_valid_checkout_email(email: str) -> bool:
    return bool(email) and len(email) <= 254 and bool(_EMAIL_RE.match(email))


async def get_or_create_site_user(email: str) -> User:
    """Создаёт User с синтетическим tg_id (диапазон SITE_USER_TG_ID_BASE+)."""
    email = normalize_checkout_email(email)
    if not is_valid_checkout_email(email):
        raise ValueError("invalid_email")

    username_key = f"site:{email}"
    async with AsyncSessionLocal() as s:
        user = await s.scalar(select(User).where(User.username == username_key))
        if user:
            return user

        tg_id: int | None = None
        for _ in range(32):
            candidate = SITE_USER_TG_ID_BASE + secrets.randbelow(1_000_000_000)
            taken = await s.scalar(select(User).where(User.tg_id == candidate))
            if not taken:
                tg_id = candidate
                break
        if tg_id is None:
            raise RuntimeError("cannot_allocate_site_tg_id")

        user = User(
            tg_id=tg_id,
            username=username_key,
            full_name=email,
        )
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return user
