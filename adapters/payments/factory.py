from __future__ import annotations

from typing import Optional

from adapters.payments.mock import MockPaymentGateway
from adapters.payments.tbank import TbankPaymentGateway
from core.ports.payments import PaymentGateway
from core.settings import saas_settings


def get_payment_gateway(provider: Optional[str] = None) -> PaymentGateway:
    name = (provider or "").strip().lower()
    if not name:
        name = "tbank"

    if name == "mock" or (name == "tbank" and saas_settings.PAYMENT_MOCK_ENABLED):
        # Prefer real T-Bank when credentials present and mock not forced via provider=mock
        if name == "mock":
            return MockPaymentGateway()
        try:
            from config import settings as bot_settings

            if bot_settings.TBANK_TERMINAL_KEY and bot_settings.TBANK_PASSWORD:
                if not saas_settings.PAYMENT_MOCK_ENABLED:
                    return TbankPaymentGateway(
                        terminal_key=bot_settings.TBANK_TERMINAL_KEY,
                        password=bot_settings.TBANK_PASSWORD,
                        test_mode=bool(bot_settings.TBANK_TEST_MODE),
                        api_base=bot_settings.TBANK_API_BASE,
                        verify_ssl=bool(bot_settings.TBANK_VERIFY_SSL),
                    )
        except Exception:
            pass
        return MockPaymentGateway()

    if name == "tbank":
        from config import settings as bot_settings

        if not bot_settings.TBANK_TERMINAL_KEY or not bot_settings.TBANK_PASSWORD:
            if saas_settings.PAYMENT_MOCK_ENABLED:
                return MockPaymentGateway()
            raise RuntimeError("TBANK_TERMINAL_KEY / TBANK_PASSWORD not configured")
        return TbankPaymentGateway(
            terminal_key=bot_settings.TBANK_TERMINAL_KEY,
            password=bot_settings.TBANK_PASSWORD,
            test_mode=bool(bot_settings.TBANK_TEST_MODE),
            api_base=bot_settings.TBANK_API_BASE,
            verify_ssl=bool(bot_settings.TBANK_VERIFY_SSL),
        )

    raise ValueError(f"Unknown payment provider: {provider}")
