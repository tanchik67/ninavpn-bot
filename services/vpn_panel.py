"""
Абстракция панели VPN: Marzban или 3x-ui (выбор через VPN_BACKEND в .env).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import re

from config import settings, xui_nodes_from_settings


_TG_USERNAME_RE = re.compile(r"[^a-z0-9_.-]+")


def _normalize_tg_username(raw: str | None) -> str:
    u = (raw or "").strip().lstrip("@").lower()
    if not u:
        return ""
    u = _TG_USERNAME_RE.sub("_", u).strip("._-")
    return u[:32]


def legacy_client_email(tg_id: int) -> str:
    """Старый стабильный логин клиента в панели (до переноса username)."""
    return f"nina_{int(tg_id)}"


def client_email(tg_id: int, tg_username: str | None = None) -> str:
    """
    Email/логин клиента в панели.

    - Если tg_username задан: <username>_<tg_id>
    - Иначе: legacy nina_<tg_id>
    """
    norm = _normalize_tg_username(tg_username)
    if norm:
        return f"{norm}_{int(tg_id)}"
    return legacy_client_email(tg_id)


class VpnPanel(ABC):
    """Единый интерфейс для выдачи и управления подписками в панели."""

    @staticmethod
    def make_qr_base64(link: str) -> str:
        from services.marzban import MarzbanAPI

        return MarzbanAPI.make_qr_base64(link)

    @abstractmethod
    async def create_or_extend_subscription(
        self, tg_id: int, months: int, devices: int, *, tg_username: str | None = None
    ) -> dict[str, Any]:
        """
        Создаёт клиента или продлевает существующего.
        Возвращает: uuid (str), links (list[str]), subscription_url (str).
        """

    @abstractmethod
    async def extend_by_days(self, tg_id: int, days: int) -> bool:
        """Добавить days календарных дней к текущему сроку клиента."""

    @abstractmethod
    async def disable_client(self, tg_id: int) -> bool:
        """Отключить доступ (бан)."""

    @abstractmethod
    async def delete_client(self, tg_id: int) -> bool:
        """Удалить клиента из панели."""

    @abstractmethod
    async def get_usage(self, tg_id: int) -> dict[str, Any]:
        """Статистика по клиенту: used_gb, status, expire и т.д."""

    @abstractmethod
    async def get_subscription_expiry(self, tg_id: int) -> datetime | None:
        """Дата окончания подписки в панели (UTC naive) или None."""

    @abstractmethod
    async def sync_device_limit(self, tg_id: int, devices: int) -> bool:
        """
        Выставить в панели лимит одновременных IP по тарифу (как в БД подписки).
        False — клиента в панели нет или ошибка API.
        """

    @abstractmethod
    async def grant_free_days(
        self, tg_id: int, days: int, devices: int
    ) -> dict[str, Any]:
        """
        Выдать days календарных дней доступа (продление или создание клиента).
        Возвращает: ok (bool), links (list[str]), subscription_url (str), expires (datetime | None).
        """

def get_vpn_panel() -> VpnPanel:
    backend = (settings.VPN_BACKEND or "marzban").lower().strip()
    if backend == "xui":
        from services.xui_panel import MultiXuiPanel, XuiPanel

        nodes = xui_nodes_from_settings(settings)
        if len(nodes) > 1:
            return MultiXuiPanel(nodes)
        return XuiPanel(nodes[0])
    from services.marzban import MarzbanPanelAdapter

    return MarzbanPanelAdapter()
