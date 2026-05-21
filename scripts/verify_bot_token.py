#!/usr/bin/env python3
"""
Проверка BOT_TOKEN: что в .env и отвечает ли api.telegram.org (getMe).
Запуск на сервере из каталога бота:
  cd /opt/ninavpn-bot && ./venv/bin/python scripts/verify_bot_token.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"


def main() -> int:
    try:
        from dotenv import dotenv_values
    except ImportError:
        print("Нужен python-dotenv (входит в зависимости бота).", file=sys.stderr)
        return 1

    if not ENV_PATH.is_file():
        print(f"Нет файла: {ENV_PATH}", file=sys.stderr)
        return 1

    raw = dotenv_values(ENV_PATH)
    lines_with_key = [
        i + 1
        for i, line in enumerate(ENV_PATH.read_text(encoding="utf-8-sig").splitlines())
        if line.strip().startswith("BOT_TOKEN")
    ]
    if len(lines_with_key) > 1:
        print(
            f"ВНИМАНИЕ: в .env несколько строк BOT_TOKEN (строки {lines_with_key}). "
            "Оставьте одну актуальную строку.",
            file=sys.stderr,
        )

    token = (raw.get("BOT_TOKEN") or "").strip()
    if (token.startswith('"') and token.endswith('"')) or (token.startswith("'") and token.endswith("'")):
        token = token[1:-1].strip()

    if not token:
        print("BOT_TOKEN в .env пустой.", file=sys.stderr)
        return 1

    parts = token.split(":", 1)
    prefix = parts[0][:6] + "..." if parts else "?"
    print(f"Длина токена: {len(token)} символов; начало id-части: {prefix}")

    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        r = httpx.get(url, timeout=20.0)
        data = r.json()
    except Exception as e:
        print(f"Ошибка HTTP: {e}", file=sys.stderr)
        return 1

    print(json.dumps(data, ensure_ascii=False, indent=2))
    if data.get("ok"):
        print("Итог: токен принят Telegram (getMe ok).")
        return 0

    print("Итог: Telegram отклонил токен. Выпустите новый в @BotFather → ваш бот → API Token.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
