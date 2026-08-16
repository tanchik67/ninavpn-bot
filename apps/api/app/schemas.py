
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, TypeAdapter, field_validator

_email_adapter = TypeAdapter(EmailStr)


def _normalize_login_email(value: str) -> str:
    """Accept real emails and Telegram placeholder accounts (tg_*@telegram.local)."""
    email = (value or "").strip().lower()
    if not email:
        raise ValueError("email required")
    if email.endswith("@telegram.local") or email.endswith("@tg.ninavpn.store"):
        local = email.split("@", 1)[0]
        if not local.startswith("tg_") or len(local) < 4:
            raise ValueError("invalid telegram placeholder email")
        return email
    return str(_email_adapter.validate_python(email)).lower()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str

    @field_validator("email")
    @classmethod
    def validate_login_email(cls, v: str) -> str:
        return _normalize_login_email(v)


class GoogleAuthRequest(BaseModel):
    id_token: str = Field(min_length=20, max_length=8192)


class TelegramAuthRequest(BaseModel):
    id: int
    first_name: str = ""
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str = Field(min_length=32, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: UUID
    # str (not EmailStr): Telegram users use placeholder emails like tg_*@telegram.local
    email: str
    role: str
    tg_id: Optional[int] = None
    panel_user_key: int
    created_at: datetime
    has_password: bool = False
    profile_emoji: Optional[str] = None

    model_config = {"from_attributes": True}


class ProfileEmojiRequest(BaseModel):
    """Empty string clears the emoji."""

    emoji: str = Field(default="", max_length=32)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    detail: str = "ok"
    # Present only when SMTP is not configured (local/dev)
    dev_code: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: Optional[str] = None
    new_password: str = Field(min_length=8, max_length=128)


class PlanOut(BaseModel):
    id: UUID
    plan_key: str
    name: str
    description: Optional[str] = None
    months: int
    devices: int
    price_rub: float

    model_config = {"from_attributes": True}


class SubscriptionOut(BaseModel):
    id: UUID
    status: str
    devices: int
    months: int
    plan_key: Optional[str] = None
    plan_name: Optional[str] = None
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    has_config: bool = False

    model_config = {"from_attributes": True}


class ConfigNodeOut(BaseModel):
    id: str
    flag: str = "🌐"
    city: str
    uri: str
    protocol: str = "VLESS"
    protocols: list[str] = []


class ConfigOut(BaseModel):
    subscription_url: Optional[str] = None
    links: list[str] = []
    nodes: list[ConfigNodeOut] = []
    qr_base64: Optional[str] = None
    deeplinks: dict[str, str] = {}
    expires_at: Optional[datetime] = None
    status: str


class CheckoutRequest(BaseModel):
    plan_key: Optional[str] = None
    months: Optional[int] = Field(default=None, ge=1, le=12)
    devices: Optional[int] = Field(default=None, ge=1, le=10)
    provider: Optional[str] = None


class CheckoutResponse(BaseModel):
    payment_id: int
    payment_url: str
    provider: str
    status: str
    checkout_token: Optional[str] = None


class PaymentOut(BaseModel):
    id: int
    status: str
    provider: str
    amount: float
    currency: str
    plan_id: UUID
    confirmed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentStatusDetail(BaseModel):
    """Checkout follow-up: payment + provision job + config readiness."""

    payment_id: int
    payment_status: str
    provider: str
    provision_status: Optional[str] = None
    provision_error: Optional[str] = None
    subscription_id: Optional[UUID] = None
    subscription_status: Optional[str] = None
    has_config: bool = False
    ready: bool = False



class SupportCreateRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=5, max_length=5000)


class SupportTicketOut(BaseModel):
    id: UUID
    subject: str
    body: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SupportMessageOut(BaseModel):
    id: UUID
    author_user_id: UUID
    body: str
    created_at: datetime
    is_staff: bool = False
    image_url: Optional[str] = None
    client_msg_id: Optional[str] = None


class SupportReplyRequest(BaseModel):
    body: str = Field(default="", max_length=5000)
    image_base64: Optional[str] = Field(default=None, max_length=12_000_000)
    image_mime: Optional[str] = Field(default="image/jpeg", max_length=64)
    # From POST .../upload — preferred over base64 on mobile
    image_token: Optional[str] = Field(default=None, max_length=80)
    # Mobile retries send the same id — server returns the existing row (no TG spam)
    client_msg_id: Optional[str] = Field(default=None, max_length=64)


class SupportPhotoChunkRequest(BaseModel):
    """Small JSON chunks — MIUI often drops multipart / large bodies."""

    client_msg_id: str = Field(min_length=4, max_length=64)
    index: int = Field(ge=0, le=64)
    total: int = Field(ge=1, le=64)
    data: str = Field(min_length=1, max_length=4500)
    body: str = Field(default="", max_length=5000)
    image_mime: str = Field(default="image/jpeg", max_length=64)


class SupportPhotoChunkAck(BaseModel):
    ok: bool = True
    received: int
    total: int


class SupportChatOut(BaseModel):
    ticket: SupportTicketOut
    messages: list[SupportMessageOut]


class SupportTicketAdminOut(BaseModel):
    id: UUID
    subject: str
    body: str
    status: str
    created_at: datetime
    user_id: UUID
    user_email: str
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    last_is_staff: bool = False


class LinkTelegramRequest(BaseModel):
    """One-time code from Telegram /linkcabinet. tg_id resolved from Redis."""

    code: str = Field(min_length=4, max_length=64)
    # Optional legacy field — ignored if code is valid in Redis
    tg_id: Optional[int] = None



class AdminExtendRequest(BaseModel):
    days: int = Field(ge=1, le=3650)


class MessageOut(BaseModel):
    detail: str
