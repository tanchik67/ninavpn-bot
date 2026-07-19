from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

import redis.asyncio as redis

from core.settings import saas_settings

log = logging.getLogger(__name__)

_redis: Optional[redis.Redis] = None
_memory_locks: dict[str, float] = {}
_memory_kv: dict[str, tuple[str, float]] = {}
_use_memory = False


class _MemoryRedis:
    """Minimal async stand-in when Redis is unavailable (local smoke tests)."""

    async def set(self, key: str, value: str, nx: bool = False, ex: Optional[int] = None) -> bool:
        now = time.time()
        # expire cleanup
        for k, (_, exp) in list(_memory_kv.items()):
            if exp and exp < now:
                _memory_kv.pop(k, None)
        if nx and key in _memory_kv:
            return False
        exp = (now + ex) if ex else 0.0
        _memory_kv[key] = (value, exp)
        return True

    async def get(self, key: str) -> Optional[str]:
        item = _memory_kv.get(key)
        if not item:
            return None
        val, exp = item
        if exp and exp < time.time():
            _memory_kv.pop(key, None)
            return None
        return val

    async def delete(self, key: str) -> int:
        return 1 if _memory_kv.pop(key, None) is not None else 0

    async def aclose(self) -> None:
        return None


async def get_redis() -> Any:
    global _redis, _use_memory
    if _use_memory:
        return _MemoryRedis()
    if _redis is None:
        client = redis.from_url(saas_settings.REDIS_URL, decode_responses=True)
        try:
            await asyncio.wait_for(client.ping(), timeout=1.5)
            _redis = client
        except Exception:
            log.warning("Redis unavailable at %s — using in-memory fallback", saas_settings.REDIS_URL)
            try:
                await client.aclose()
            except Exception:
                pass
            _use_memory = True
            return _MemoryRedis()
    return _redis


async def close_redis() -> None:
    global _redis, _use_memory
    if _redis is not None:
        await _redis.aclose()
        _redis = None
    _use_memory = False
