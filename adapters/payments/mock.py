from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlencode

from core.ports.payments import CheckoutResult, WebhookResult


class MockPaymentGateway:
    """Local/dev gateway: returns a confirm URL that hits our mock webhook."""

    name = "mock"

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
    ) -> CheckoutResult:
        qs = urlencode({"payment_id": payment_id, "Status": "CONFIRMED"})
        # Client opens success_url; webhook can be triggered separately or via /mock/confirm
        pay_url = f"{notification_url.rstrip('/')}?{qs}" if "://" in notification_url else success_url
        # Prefer redirecting user to success with token; API will expose POST confirm for mock
        return CheckoutResult(
            provider_payment_id=f"mock_{payment_id}",
            payment_url=success_url if success_url else pay_url,
            raw={
                "mock": True,
                "payment_id": payment_id,
                "amount_rub": amount_rub,
                "description": description,
                "notification_url": notification_url,
                "customer_email": customer_email,
                "fail_url": fail_url,
            },
        )

    async def parse_webhook(self, payload: dict[str, Any]) -> WebhookResult:
        status = str(payload.get("Status") or payload.get("status") or "").upper()
        pid = payload.get("payment_id") or payload.get("PaymentId")
        try:
            our_id = int(pid) if pid is not None else None
        except (TypeError, ValueError):
            our_id = None
        confirmed = status in ("CONFIRMED", "AUTHORIZED", "SUCCESS", "OK")
        return WebhookResult(
            confirmed=confirmed,
            provider_payment_id=str(payload.get("provider_payment_id") or f"mock_{our_id}"),
            our_payment_id=our_id,
            raw=payload,
        )
