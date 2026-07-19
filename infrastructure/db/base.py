from __future__ import annotations

from collections.abc import AsyncGenerator

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
