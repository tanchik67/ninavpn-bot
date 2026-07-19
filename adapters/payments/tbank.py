from __future__ import annotations

import logging
from typing import Any, Optional

from core.ports.payments import CheckoutResult, WebhookResult
from services.tbank import acquiring_base_url, init_payment, order_id_for_payment, parse_payment_id_from_order_id, verify_notification_token

log = logging.getLogger(__name__)


class TbankPaymentGateway:
    name = "tbank"

    def __init__(
        self,
        *,
        terminal_key: str,
        password: str,
        test_mode: bool = False,
        api_base: Optional[str] = None,
        verify_ssl: bool = True,
    ) -> None:
        self._terminal_key = terminal_key
        self._password = password
        self._test_mode = test_mode
        self._api_base = api_base
        self._verify_ssl = verify_ssl

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
        amount_kopecks = int(round(float(amount_rub) * 100))
        order_id = order_id_for_payment(payment_id)
        base_url = acquiring_base_url(test_mode=self._test_mode, override=self._api_base)
        data = await init_payment(
            self._terminal_key,
            self._password,
            order_id=order_id,
            amount_kopecks=amount_kopecks,
            description=description[:140],
            base_url=base_url,
            notification_url=notification_url,
            success_url=success_url,
            fail_url=fail_url,
            verify_ssl=self._verify_ssl,
        )
        if not data.get("Success"):
            raise RuntimeError(f"T-Bank Init failed: {data.get('Message') or data}")
        return CheckoutResult(
            provider_payment_id=str(data.get("PaymentId") or order_id),
            payment_url=str(data.get("PaymentURL") or ""),
            raw=data,
        )

    async def parse_webhook(self, payload: dict[str, Any]) -> WebhookResult:
        if not verify_notification_token(payload, self._password):
            return WebhookResult(confirmed=False, error="invalid_token", raw=payload)

        status = str(payload.get("Status") or "").upper()
        confirmed = status in ("CONFIRMED", "AUTHORIZED")
        order_id = str(payload.get("OrderId") or "")
        our_id = parse_payment_id_from_order_id(order_id)
        return WebhookResult(
            confirmed=confirmed,
            provider_payment_id=str(payload.get("PaymentId") or ""),
            our_payment_id=our_id,
            raw=payload,
        )
