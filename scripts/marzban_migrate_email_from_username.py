#!/usr/bin/env python3
"""
Опциональная миграция идентификатора пользователя в Marzban.

Задача: чтобы в Marzban в поле username/email было видно tg username, а не nina_<tg_id>.

ВАЖНО:
- В Marzban нет безопасного "rename username" без смены UUID/ссылок.
- Этот скрипт по умолчанию ТОЛЬКО показывает, что найдено (dry-run).
- В режиме --apply он СОЗДАЁТ НОВОГО пользователя в Marzban с новым username и ОТКЛЮЧАЕТ legacy.
  Это может потребовать выдать пользователю новый конфиг/подписку.

Запуск на сервере:
  cd /opt/ninavpn-bot && ./venv/bin/python scripts/marzban_migrate_email_from_username.py --dry-run
  cd /opt/ninavpn-bot && ./venv/bin/python scripts/marzban_migrate_email_from_username.py --apply --i-understand
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    try:
        from dotenv import dotenv_values
    except ImportError:
        print("Нужен python-dotenv.", file=sys.stderr)
        raise
    env_file = ROOT / ".env"
    if env_file.is_file():
        for k, v in dotenv_values(env_file).items():
            if k and v is not None:
                os.environ[k] = v


async def main() -> int:
    # Чтобы работали `import database`, `import services...` при запуске как файла.
    root_s = str(ROOT)
    if root_s not in sys.path:
        sys.path.insert(0, root_s)

    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Только показать, ничего не менять (по умолчанию)")
    ap.add_argument("--apply", action="store_true", help="Создать preferred и отключить legacy")
    ap.add_argument("--i-understand", action="store_true", help="Подтверждение для --apply")
    ap.add_argument("--limit", type=int, default=200, help="Сколько пользователей обработать из БД")
    args = ap.parse_args()

    if args.apply and not args.i_understand:
        print("Для --apply нужно добавить --i-understand (это создаёт новых пользователей в панели).", file=sys.stderr)
        return 2

    _load_env()
    os.chdir(ROOT)

    from sqlalchemy import select

    from database import AsyncSessionLocal, User
    from services.marzban import marzban, _marzban_raise
    from services.vpn_panel import client_email, legacy_client_email
    import httpx

    async with AsyncSessionLocal() as s:
        users = (await s.execute(select(User).order_by(User.created_at.desc()).limit(args.limit))).scalars().all()

    async with httpx.AsyncClient() as c:
        headers = await marzban._headers()  # noqa: SLF001 (internal helper, acceptable for ops script)

        changed = 0
        for u in users:
            tg_id = int(u.tg_id)
            preferred = client_email(tg_id, u.username)
            legacy = legacy_client_email(tg_id)

            r_pref = await c.get(f"{marzban.api_base}/api/user/{preferred}", headers=headers, timeout=10)
            pref_exists = r_pref.status_code == 200
            if r_pref.status_code not in (200, 404):
                _marzban_raise(r_pref)

            r_leg = await c.get(f"{marzban.api_base}/api/user/{legacy}", headers=headers, timeout=10)
            leg_exists = r_leg.status_code == 200
            if r_leg.status_code not in (200, 404):
                _marzban_raise(r_leg)

            status = []
            status.append("preferred=OK" if pref_exists else "preferred=—")
            status.append("legacy=OK" if leg_exists else "legacy=—")
            print(f"tg_id={tg_id} tg_username={u.username!r} -> {preferred} | {legacy} | " + " ".join(status))

            if not args.apply:
                continue

            # apply: если legacy есть, preferred нет — создаём preferred с expire/max_ips из legacy и отключаем legacy
            if leg_exists and not pref_exists and preferred != legacy:
                legacy_data = r_leg.json()
                payload = {
                    "username": preferred,
                    "proxies": marzban._vless_proxies(),  # noqa: SLF001
                    "inbounds": marzban._vless_inbounds(),  # noqa: SLF001
                    "expire": legacy_data.get("expire"),
                    "data_limit": 0,
                    "data_limit_reset_strategy": "no_reset",
                    "status": "active",
                    "note": f"migrated_from={legacy} tg_id={tg_id}",
                }
                mi = legacy_data.get("max_ips")
                if mi is not None:
                    payload["max_ips"] = mi
                r_create = await c.post(f"{marzban.api_base}/api/user", json=payload, headers=headers, timeout=15)
                _marzban_raise(r_create)
                r_disable = await c.put(
                    f"{marzban.api_base}/api/user/{legacy}",
                    json={"status": "disabled", "note": f"disabled_after_migration -> {preferred}"},
                    headers=headers,
                    timeout=10,
                )
                _marzban_raise(r_disable)
                changed += 1

        print(f"Done. migrated={changed}")

    return 0


if __name__ == "__main__":
    try:
        import asyncio

        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(130)

