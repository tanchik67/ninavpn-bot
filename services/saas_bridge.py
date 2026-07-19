"""
Optional import surface for the Telegram bot.

Keeps bot handlers from depending on deep SaaS paths while we migrate.
"""
from __future__ import annotations

from core.compat.bot_bridge import create_telegram_link_code, panel_key_for_saas_user

# Re-export existing panel factory for clarity in new code paths
from services.vpn_panel import get_vpn_panel  # noqa: F401

__all__ = [
    "create_telegram_link_code",
    "panel_key_for_saas_user",
    "get_vpn_panel",
]
