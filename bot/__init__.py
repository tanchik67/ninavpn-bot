"""
Telegram bot package marker.

Phase 1: bot entrypoint remains at repository root (`main.py`, `handlers/`).
Shared SaaS domain lives in `core/` + `adapters/`; use `core.compat.bot_bridge`
for cross-cutting helpers (Telegram link codes, etc.).
"""
