
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    tg_id: Optional[int] = None
    panel_user_key: int
    created_at: datetime

    model_config = {"from_attributes": True}


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


class ConfigOut(BaseModel):
    subscription_url: Optional[str] = None
    links: list[str] = []
    qr_base64: Optional[str] = None
    deeplinks: dict[str, str] = {}
    expires_at: Optional[datetime] = None
    status: str


class CheckoutRequest(BaseModel):
    plan_key: str
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


class SupportReplyRequest(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class SupportChatOut(BaseModel):
    ticket: SupportTicketOut
    messages: list[SupportMessageOut]


class LinkTelegramRequest(BaseModel):
    """One-time code from Telegram /linkcabinet. tg_id resolved from Redis."""

    code: str = Field(min_length=4, max_length=64)
    # Optional legacy field — ignored if code is valid in Redis
    tg_id: Optional[int] = None



class AdminExtendRequest(BaseModel):
    days: int = Field(ge=1, le=3650)


class MessageOut(BaseModel):
    detail: str
