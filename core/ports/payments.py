from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass
class CheckoutResult:
    provider_payment_id: str
    payment_url: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookResult:
    confirmed: bool
    provider_payment_id: Optional[str] = None
    our_payment_id: Optional[int] = None
    raw: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class PaymentGateway(Protocol):
    name: str

    async def create_payment(
        self,
        *,
        payment_id: int,
        amount_rub: float,
        description: str,
        success_url: str,
        fail_url: str,
        notification_url: str,
        customer_email: Optional[str] = None,
    ) -> CheckoutResult: ...

    async def parse_webhook(self, payload: dict[str, Any]) -> WebhookResult: ...
