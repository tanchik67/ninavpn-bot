from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.settings import saas_settings


class Base(DeclarativeBase):
    pass


saas_engine = create_async_engine(saas_settings.SAAS_DATABASE_URL, echo=False, pool_pre_ping=True)
SaasSessionLocal = async_sessionmaker(saas_engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SaasSessionLocal() as session:
        yield session


async def init_db() -> None:
    from infrastructure.db import models  # noqa: F401

    async with saas_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Best-effort OAuth columns for DBs created before 002_saas_oauth
        dialect = conn.engine.dialect.name
        try:
            if dialect == "sqlite":
                cols = (await conn.execute(text("PRAGMA table_info(saas_users)"))).fetchall()
                names = {c[1] for c in cols}
                if "google_sub" not in names:
                    await conn.execute(
                        text("ALTER TABLE saas_users ADD COLUMN google_sub VARCHAR(128)")
                    )
                if "profile_emoji" not in names:
                    await conn.execute(
                        text("ALTER TABLE saas_users ADD COLUMN profile_emoji VARCHAR(32)")
                    )
            else:
                await conn.execute(
                    text("ALTER TABLE saas_users ALTER COLUMN password_hash DROP NOT NULL")
                )
                await conn.execute(
                    text(
                        "ALTER TABLE saas_users ADD COLUMN IF NOT EXISTS google_sub VARCHAR(128)"
                    )
                )
                await conn.execute(
                    text(
                        "ALTER TABLE saas_users ADD COLUMN IF NOT EXISTS profile_emoji VARCHAR(32)"
                    )
                )
                await conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ix_saas_users_google_sub "
                        "ON saas_users (google_sub)"
                    )
                )
        except Exception:
            pass
