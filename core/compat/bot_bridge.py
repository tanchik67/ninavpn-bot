"""Minimal glue between Telegram bot and SaaS API/Redis."""
from __future__ import annotations

import secrets
from uuid import UUID

from core.services.security import allocate_panel_user_key


async def create_telegram_link_code(tg_id: int, *, ttl_sec: int = 600) -> str:
    """
    Store one-time code in Redis for POST /api/v1/auth/link-telegram.
    Bot shows the code; Expo client submits {code}.
    """
    from infrastructure.redis.client import get_redis

    code = secrets.token_hex(3)  # 6 hex chars, lowercase
    redis = await get_redis()
    await redis.set(f"tg_link:{code}", str(int(tg_id)), ex=ttl_sec)
    return code


def panel_key_for_saas_user(user_id: UUID) -> int:
    return allocate_panel_user_key(user_id)
