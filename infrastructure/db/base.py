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


async def _sqlite_ensure_oauth_schema(conn) -> None:
    """SQLite cannot ALTER COLUMN nullability — rebuild saas_users if needed."""
    cols = (await conn.execute(text("PRAGMA table_info(saas_users)"))).fetchall()
    if not cols:
        return
    by_name = {c[1]: c for c in cols}
    if "google_sub" not in by_name:
        await conn.execute(text("ALTER TABLE saas_users ADD COLUMN google_sub VARCHAR(128)"))
    if "profile_emoji" not in by_name:
        await conn.execute(text("ALTER TABLE saas_users ADD COLUMN profile_emoji VARCHAR(32)"))
    if "referral_rewarded_at" not in by_name:
        await conn.execute(text("ALTER TABLE saas_users ADD COLUMN referral_rewarded_at DATETIME"))

    sub_cols = (await conn.execute(text("PRAGMA table_info(saas_subscriptions)"))).fetchall()
    sub_names = {c[1] for c in sub_cols}
    if sub_cols and "config_links" not in sub_names:
        await conn.execute(text("ALTER TABLE saas_subscriptions ADD COLUMN config_links JSON"))

    cols = (await conn.execute(text("PRAGMA table_info(saas_users)"))).fetchall()
    ph = next((c for c in cols if c[1] == "password_hash"), None)
    if ph is None or ph[3] == 0:  # already nullable
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_saas_users_google_sub "
                "ON saas_users (google_sub)"
            )
        )
        return

    await conn.execute(text("PRAGMA foreign_keys=OFF"))
    await conn.execute(
        text(
            """
            CREATE TABLE saas_users__oauth (
                id CHAR(32) NOT NULL PRIMARY KEY,
                email VARCHAR(254) NOT NULL,
                password_hash VARCHAR(255),
                tg_id BIGINT,
                panel_user_key BIGINT NOT NULL,
                role VARCHAR(32) NOT NULL,
                is_banned BOOLEAN NOT NULL,
                referrer_id CHAR(32),
                email_verified_at DATETIME,
                created_at DATETIME NOT NULL,
                google_sub VARCHAR(128),
                profile_emoji VARCHAR(32),
                referral_rewarded_at DATETIME,
                FOREIGN KEY(referrer_id) REFERENCES saas_users__oauth (id)
            )
            """
        )
    )
    await conn.execute(
        text(
            """
            INSERT INTO saas_users__oauth (
                id, email, password_hash, tg_id, panel_user_key, role, is_banned,
                referrer_id, email_verified_at, created_at, google_sub, profile_emoji,
                referral_rewarded_at
            )
            SELECT
                id, email, password_hash, tg_id, panel_user_key, role, is_banned,
                referrer_id, email_verified_at, created_at, google_sub, profile_emoji,
                referral_rewarded_at
            FROM saas_users
            """
        )
    )
    await conn.execute(text("DROP TABLE saas_users"))
    await conn.execute(text("ALTER TABLE saas_users__oauth RENAME TO saas_users"))
    await conn.execute(
        text("CREATE UNIQUE INDEX IF NOT EXISTS ix_saas_users_email ON saas_users (email)")
    )
    await conn.execute(
        text("CREATE UNIQUE INDEX IF NOT EXISTS ix_saas_users_tg_id ON saas_users (tg_id)")
    )
    await conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_saas_users_panel_user_key "
            "ON saas_users (panel_user_key)"
        )
    )
    await conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_saas_users_google_sub "
            "ON saas_users (google_sub)"
        )
    )
    await conn.execute(text("PRAGMA foreign_keys=ON"))


async def init_db() -> None:
    from infrastructure.db import models  # noqa: F401

    async with saas_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Best-effort OAuth columns for DBs created before 002_saas_oauth
        dialect = conn.engine.dialect.name
        try:
            if dialect == "sqlite":
                await _sqlite_ensure_oauth_schema(conn)
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
                        "ALTER TABLE saas_users ADD COLUMN IF NOT EXISTS referral_rewarded_at TIMESTAMP"
                    )
                )
                await conn.execute(
                    text(
                        "ALTER TABLE saas_subscriptions ADD COLUMN IF NOT EXISTS config_links JSONB"
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
