"""
Реальный HTTP-пинг до панелей (3x-ui / Marzban) для «Серверы / статус».
Кэш на SERVER_STATUS_CACHE_SEC. Используется MultiXuiPanel для порядка узлов (быстрый → первый vless).
"""
from __future__ import annotations

import asyncio
import logging
import time
from html import escape as html_escape
from typing import Optional

import httpx

from config import XuiNodeConfig, settings, xui_nodes_from_settings

log = logging.getLogger(__name__)

_cache_mono: float = 0.0
_cache_text: str = ""


def _xui_login_probe_url(node: XuiNodeConfig) -> str:
    base = node.url.rstrip("/")
    px = (node.path_prefix or "").strip().strip("/")
    if px:
        return f"{base}/{px}/login"
    return f"{base}/login"


async def ping_http_ms(url: str) -> Optional[float]:
    """Время GET до ответа (мс) или None при ошибке/таймауте."""
    u = (url or "").strip()
    if not u:
        return None
    verify = bool(settings.SERVER_PING_VERIFY_SSL)
    timeout = float(settings.SERVER_PING_TIMEOUT_SEC or 4.0)
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(
            verify=verify,
            follow_redirects=True,
            timeout=httpx.Timeout(timeout),
        ) as c:
            r = await c.get(u)
        if r.status_code >= 500:
            return None
    except Exception as e:
        log.debug("ping_http_ms %s: %s", u[:80], e)
        return None
    return (time.monotonic() - t0) * 1000.0


async def ping_xui_node_ms(node: XuiNodeConfig) -> Optional[float]:
    return await ping_http_ms(_xui_login_probe_url(node))


async def ping_marzban_api_ms() -> Optional[float]:
    raw = (settings.MARZBAN_API_URL or settings.MARZBAN_URL or "").strip().rstrip("/")
    if not raw:
        return None
    verify = bool(settings.SERVER_PING_VERIFY_SSL)
    for path in ("/openapi.json", "/docs", "/"):
        ms = await ping_http_ms(raw + path)
        if ms is not None:
            return ms
    return None


async def _build_servers_status_text() -> str:
    backend = (settings.VPN_BACKEND or "marzban").lower().strip()
    lines: list[str] = [
        "🌍 <b>Статус серверов NINAVPN</b>\n",
        "<i>Задержка — HTTP до панели (не ICMP).</i>\n",
    ]

    if backend == "xui":
        nodes = xui_nodes_from_settings(settings)
        if not nodes:
            lines.append("\n⚠️ Узлы 3x-ui не настроены (<code>XUI_NODES</code> / <code>XUI_URL</code>).")
        else:
            pings = await asyncio.gather(
                *[ping_xui_node_ms(n) for n in nodes], return_exceptions=True
            )
            ordered: list[tuple[XuiNodeConfig, Optional[float]]] = []
            for n, p in zip(nodes, pings):
                if isinstance(p, Exception):
                    log.warning("ping node %s: %s", n.label, p)
                    ordered.append((n, None))
                else:
                    ordered.append((n, p))
            ordered.sort(
                key=lambda x: (
                    x[1] is None,
                    x[1] if x[1] is not None else 1e12,
                )
            )
            lines.append("")
            for i, (node, ms) in enumerate(ordered, start=1):
                label = html_escape((node.label or f"Узел {i}").strip() or f"Узел {i}")
                if ms is None:
                    lines.append(f"🔴 <b>{label}</b> — нет ответа")
                else:
                    lines.append(f"🟢 <b>{label}</b> — <code>{ms:.0f}</code> мс")
            if len(ordered) > 1:
                lines.append(
                    "\n⚡ <b>Балансировка:</b> в выдаче конфига первым идёт узел с "
                    "<b>меньшей</b> задержкой (удобно для клиентов, берущих первый сервер)."
                )
    elif backend == "marzban":
        ms = await ping_marzban_api_ms()
        lines.append("")
        if ms is None:
            lines.append("🔴 <b>Marzban API</b> — нет ответа (проверьте <code>MARZBAN_API_URL</code>).")
        else:
            lines.append(f"🟢 <b>Marzban API</b> — <code>{ms:.0f}</code> мс")
    else:
        lines.append(f"\n⚠️ Неизвестный <code>VPN_BACKEND={backend}</code>.")

    ttl = int(settings.SERVER_STATUS_CACHE_SEC or 90)
    lines.append(f"\n🔄 Кэш экрана: <code>{ttl}</code> с")
    return "\n".join(lines)


async def get_servers_status_message() -> str:
    global _cache_mono, _cache_text
    now = time.monotonic()
    ttl = float(settings.SERVER_STATUS_CACHE_SEC or 90)
    if _cache_text and (now - _cache_mono) < ttl:
        return _cache_text
    _cache_text = await _build_servers_status_text()
    _cache_mono = now
    return _cache_text


def invalidate_servers_status_cache() -> None:
    global _cache_mono, _cache_text
    _cache_mono = 0.0
    _cache_text = ""
