#!/usr/bin/env python3
"""Create or promote the master admin cabinet account."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.domain.enums import UserRole  # noqa: E402
from core.services.security import hash_password  # noqa: E402
from infrastructure.db.base import SaasSessionLocal, init_db  # noqa: E402
from infrastructure.db.models import User  # noqa: E402
from sqlalchemy import select  # noqa: E402


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--email", default="admin@ninavpn.store")
    p.add_argument("--password", default="NinaAdmin!2026")
    args = p.parse_args()
    email = args.email.strip().lower()
    password = args.password

    await init_db()
    async with SaasSessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == email))
        if user:
            user.role = UserRole.ADMIN.value
            user.password_hash = hash_password(password)
            user.is_banned = False
            await session.commit()
            print(f"updated admin {email} id={user.id}")
        else:
            # panel_user_key: large offset for email users
            from core.settings import saas_settings

            base = int(getattr(saas_settings, "PANEL_USER_KEY_BASE", 8_000_000_000_000))
            # unique-ish key from email hash
            key = base + (abs(hash(email)) % 1_000_000_000)
            user = User(
                email=email,
                password_hash=hash_password(password),
                role=UserRole.ADMIN.value,
                panel_user_key=key,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            print(f"created admin {email} id={user.id}")
    print("login in the app with this email/password → Settings shows admin inbox")


if __name__ == "__main__":
    asyncio.run(main())
