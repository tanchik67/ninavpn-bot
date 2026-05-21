"""
Alembic: синхронный URL в ALEMBIC_SYNC_DATABASE_URL или вывод из DATABASE_URL.
Для PostgreSQL: postgresql+psycopg2://user:pass@host/dbname
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_sync_url() -> str:
    sync = (os.environ.get("ALEMBIC_SYNC_DATABASE_URL") or "").strip()
    if sync:
        return sync
    du = (os.environ.get("DATABASE_URL") or "sqlite+aiosqlite:///ninavpn.db").strip()
    if "sqlite+aiosqlite" in du:
        return du.replace("sqlite+aiosqlite:///", "sqlite:///", 1)
    if "+asyncpg" in du:
        return du.replace("+asyncpg", "+psycopg2", 1)
    return du


def run_migrations_offline() -> None:
    url = get_sync_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_sync_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
