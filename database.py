from datetime import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float,
    DateTime, Boolean, ForeignKey, Text, text, UniqueConstraint,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine, AsyncSession, async_sessionmaker
)
from sqlalchemy.orm import DeclarativeBase, relationship
from config import settings


# ─── Engine ────────────────────────────────────────────────
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ─── Модели ────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True)
    tg_id         = Column(BigInteger, unique=True, nullable=False, index=True)
    username      = Column(String(64), nullable=True)
    full_name     = Column(String(128), nullable=True)
    referrer_id   = Column(BigInteger, nullable=True)   # tg_id реферера
    ref_bonus_given = Column(Boolean, default=False)    # выдан ли бонус рефереру
    created_at    = Column(DateTime, default=datetime.utcnow)
    is_banned     = Column(Boolean, default=False)
    active_promo_id = Column(Integer, ForeignKey("promo_codes.id"), nullable=True)

    subscriptions = relationship("Subscription", back_populates="user")
    payments      = relationship("Payment",      back_populates="user")
    active_promo  = relationship("PromoCode", foreign_keys=[active_promo_id])


class Subscription(Base):
    __tablename__ = "subscriptions"

    id            = Column(Integer, primary_key=True)
    user_tg_id    = Column(BigInteger, ForeignKey("users.tg_id"), nullable=False)
    plan_key      = Column(String(32), nullable=False)   # e.g. "6m_3d"
    devices       = Column(Integer, default=1)
    months        = Column(Integer, default=1)
    price_paid    = Column(Float,   default=0)           # RUB
    marzban_uuid  = Column(String(64), nullable=True)    # UUID пользователя в Marzban
    config_link   = Column(Text, nullable=True)          # основная subscription / vless ссылка
    config_link_extra = Column(Text, nullable=True)      # вторая ссылка (второй узел 3x-ui)
    config_qr     = Column(Text, nullable=True)          # base64 QR-кода
    started_at    = Column(DateTime, default=datetime.utcnow)
    expires_at    = Column(DateTime, nullable=True)
    is_active     = Column(Boolean, default=True)
    reminded      = Column(Boolean, default=False)       # отправлено ли напоминание

    user          = relationship("User", back_populates="subscriptions")


class Payment(Base):
    __tablename__ = "payments"

    id            = Column(Integer, primary_key=True)
    user_tg_id    = Column(BigInteger, ForeignKey("users.tg_id"), nullable=False)
    plan_key      = Column(String(32), nullable=False)
    devices       = Column(Integer, default=1)
    method        = Column(String(32), nullable=False)   # usdt_trc20 / ton / card_ru / sber_pbpn / tbank / manual …
    amount_rub    = Column(Float,   nullable=True)
    amount_crypto = Column(Float,   nullable=True)
    currency      = Column(String(10), nullable=True)    # USDT / TON / RUB
    tx_hash       = Column(String(128), nullable=True)   # хэш транзакции
    status        = Column(String(16), default="pending")  # pending/processing/confirmed/failed
    created_at    = Column(DateTime, default=datetime.utcnow)
    confirmed_at  = Column(DateTime, nullable=True)
    promo_id      = Column(Integer, ForeignKey("promo_codes.id"), nullable=True)
    admin_notify_sent = Column(Boolean, default=False)  # уведомление админам о переводе sber_pbpn (анти-спам)
    checkout_token  = Column(String(64), nullable=True, unique=True, index=True)
    checkout_email  = Column(String(254), nullable=True)

    user          = relationship("User", back_populates="payments")
    promo         = relationship("PromoCode", foreign_keys=[promo_id])


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id            = Column(Integer, primary_key=True)
    code          = Column(String(32), unique=True, nullable=False)
    discount_pct  = Column(Integer, default=0)     # устарело; бот использует только bonus_days
    bonus_days    = Column(Integer, default=0)     # бесплатные дни доступа к VPN при активации кода
    max_uses      = Column(Integer, default=100)
    used_count    = Column(Integer, default=0)
    is_active     = Column(Boolean, default=True)
    expires_at    = Column(DateTime, nullable=True)


class PromoRedemption(Base):
    """Один пользователь — не более одного использования данного промокода."""

    __tablename__ = "promo_redemptions"
    __table_args__ = (UniqueConstraint("promo_id", "user_tg_id", name="uq_promo_redemption_user"),)

    id           = Column(Integer, primary_key=True)
    promo_id     = Column(Integer, ForeignKey("promo_codes.id"), nullable=False, index=True)
    user_tg_id   = Column(BigInteger, ForeignKey("users.tg_id"), nullable=False, index=True)
    created_at   = Column(DateTime, default=datetime.utcnow)


class PlanTariff(Base):
    """Тарифы для бота; при наличии хотя бы одной активной записи каталог берётся только из БД."""

    __tablename__ = "plan_tariffs"

    id                   = Column(Integer, primary_key=True)
    plan_key             = Column(String(64), unique=True, nullable=False, index=True)
    name                 = Column(String(128), nullable=False)
    description          = Column(String(512), nullable=True)
    emoji                = Column(String(16), nullable=True)
    months               = Column(Integer, nullable=False)
    devices              = Column(Integer, nullable=False)
    price_rub            = Column(Float, nullable=False)
    price_usdt           = Column(Float, nullable=False)
    popular              = Column(Boolean, default=False)
    sort_order           = Column(Integer, default=0)
    is_active            = Column(Boolean, default=True)
    tribute_link         = Column(Text, nullable=True)
    tribute_product_id   = Column(Integer, nullable=True)
    created_at           = Column(DateTime, default=datetime.utcnow)


# ─── Инициализация ─────────────────────────────────────────

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if "sqlite" in settings.DATABASE_URL:
        async with engine.begin() as conn:
            res = await conn.execute(text("PRAGMA table_info(users)"))
            ucols = [row[1] for row in res.fetchall()]
            if ucols and "active_promo_id" not in ucols:
                await conn.execute(
                    text("ALTER TABLE users ADD COLUMN active_promo_id INTEGER")
                )
            res2 = await conn.execute(text("PRAGMA table_info(payments)"))
            pcols = [row[1] for row in res2.fetchall()]
            if pcols and "promo_id" not in pcols:
                await conn.execute(
                    text("ALTER TABLE payments ADD COLUMN promo_id INTEGER")
                )
            res3 = await conn.execute(text("PRAGMA table_info(subscriptions)"))
            scols = [row[1] for row in res3.fetchall()]
            if scols and "config_link_extra" not in scols:
                await conn.execute(
                    text("ALTER TABLE subscriptions ADD COLUMN config_link_extra TEXT")
                )


async def get_session():
    """Dependency для FastAPI/aiohttp если понадобится."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
