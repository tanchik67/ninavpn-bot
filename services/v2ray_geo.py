"""
Кэш geoip.dat / geosite.dat из проекта runetfreedom/russia-v2ray-rules-dat
(https://github.com/runetfreedom/russia-v2ray-rules-dat) для клиентов v2ray / v2rayN.
Файлы обновляются на стороне upstream примерно каждые 6 часов; локально кэшируем на диске.
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import httpx

from config import settings

log = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "v2ray_geo"
_LOCKS: dict[str, asyncio.Lock] = {"geoip": asyncio.Lock(), "geosite": asyncio.Lock()}

_FILENAMES = {"geoip": "geoip.dat", "geosite": "geosite.dat"}


def _url_for(kind: str) -> str:
    if kind == "geoip":
        return (settings.V2RAY_GEO_GEOIP_URL or "").strip()
    if kind == "geosite":
        return (settings.V2RAY_GEO_GEOSITE_URL or "").strip()
    raise ValueError(kind)


def _ttl_sec() -> int:
    return max(60, int(getattr(settings, "V2RAY_GEO_CACHE_TTL_SEC", 21600) or 21600))


def _cache_path(kind: str) -> Path:
    return _CACHE_DIR / _FILENAMES[kind]


def _cache_fresh(path: Path) -> bool:
    if not path.is_file():
        return False
    age = time.time() - path.stat().st_mtime
    return age < float(_ttl_sec())


async def _fetch_upstream(url: str) -> bytes:
    timeout = httpx.Timeout(180.0, connect=30.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.content


async def get_bytes(kind: str) -> bytes:
    """Вернуть содержимое geoip или geosite (из кэша или с upstream)."""
    if kind not in _FILENAMES:
        raise ValueError(kind)
    url = _url_for(kind)
    if not url:
        raise RuntimeError(f"V2RAY_GEO: пустой URL для {kind}")

    path = _cache_path(kind)
    lock = _LOCKS[kind]
    async with lock:
        if _cache_fresh(path):
            return path.read_bytes()
        log.info("V2RAY_GEO: загрузка %s", kind)
        data = await _fetch_upstream(url)
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        log.info("V2RAY_GEO: сохранено %s (%s байт)", kind, len(data))
        return data


async def prefetch_both() -> None:
    """Фоновая подгрузка при старте (ошибки не падают в polling)."""
    results = await asyncio.gather(
        get_bytes("geoip"),
        get_bytes("geosite"),
        return_exceptions=True,
    )
    for r in results:
        if isinstance(r, BaseException):
            log.warning("V2RAY_GEO: prefetch — %s", r)
