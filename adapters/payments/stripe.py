"""Stripe Checkout stub — enable when STRIPE_SECRET_KEY is set."""
from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlencode

from core.ports.payments import CheckoutResult, WebhookResult
from core.services.fx_display import rub_to_usd


class StripePaymentGateway:
    """
    Stub gateway for global card payments.
    When Stripe keys are missing, behaves like a redirect stub for local UX.
    Real Charge/Checkout Session wiring lands when STRIPE_SECRET_KEY is configured.
    """

    name = "stripe"

    def __init__(self, secret_key: Optional[str] = None, webhook_secret: Optional[str] = None):
        self.secret_key = (secret_key or "").strip()
        self.webhook_secret = (webhook_secret or "").strip()

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
        amount_usd = rub_to_usd(amount_rub)
        if not self.secret_key:
            qs = urlencode(
                {
                    "payment_id": payment_id,
                    "provider": "stripe",
                    "amount_usd": amount_usd,
                    "stub": "1",
                }
            )
            return CheckoutResult(
                provider_payment_id=f"stripe_stub_{payment_id}",
                payment_url=f"{success_url}{'&' if '?' in success_url else '?'}{qs}",
                raw={
                    "stub": True,
                    "amount_usd": amount_usd,
                    "amount_rub": amount_rub,
                    "description": description,
                    "customer_email": customer_email,
                    "notification_url": notification_url,
                    "fail_url": fail_url,
                },
            )

        # Placeholder for real Stripe Checkout Session create call.
        return CheckoutResult(
            provider_payment_id=f"stripe_pending_{payment_id}",
            payment_url=success_url,
            raw={
                "configured": True,
                "amount_usd": amount_usd,
                "note": "Replace with stripe.checkout.Session.create in production.",
            },
        )

    async def parse_webhook(self, payload: dict[str, Any]) -> WebhookResult:
        event = str(payload.get("type") or payload.get("Status") or "").lower()
        pid = payload.get("payment_id") or payload.get("client_reference_id")
        try:
            our_id = int(pid) if pid is not None else None
        except (TypeError, ValueError):
            our_id = None
        confirmed = event in (
            "checkout.session.completed",
            "payment_intent.succeeded",
            "confirmed",
            "success",
        )
        return WebhookResult(
            confirmed=confirmed,
            provider_payment_id=str(payload.get("id") or f"stripe_{our_id}"),
            our_payment_id=our_id,
            raw=payload,
        )
