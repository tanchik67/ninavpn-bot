from __future__ import annotations

from typing import Optional

from adapters.payments.mock import MockPaymentGateway
from adapters.payments.tbank import TbankPaymentGateway
from core.ports.payments import PaymentGateway
from core.settings import saas_settings


def _tbank_from_bot_settings() -> Optional[TbankPaymentGateway]:
    try:
        from config import settings as bot_settings
    except Exception:
        return None
    if not bot_settings.TBANK_TERMINAL_KEY or not bot_settings.TBANK_PASSWORD:
        return None
    return TbankPaymentGateway(
        terminal_key=bot_settings.TBANK_TERMINAL_KEY,
        password=bot_settings.TBANK_PASSWORD,
        test_mode=bool(bot_settings.TBANK_TEST_MODE),
        api_base=bot_settings.TBANK_API_BASE,
        verify_ssl=bool(bot_settings.TBANK_VERIFY_SSL),
    )


def get_payment_gateway(provider: Optional[str] = None) -> PaymentGateway:
    """
    Resolution:
    - provider=mock → always mock
    - provider=tbank → T-Bank (error if missing keys unless mock fallback allowed)
    - provider omitted → T-Bank if keys exist and PAYMENT_MOCK_ENABLED=false; else mock
    """
    name = (provider or "").strip().lower()

    if name == "mock":
        return MockPaymentGateway()

    tbank = _tbank_from_bot_settings()

    if name == "tbank":
        if tbank:
            return tbank
        if saas_settings.PAYMENT_MOCK_ENABLED:
            return MockPaymentGateway()
        raise RuntimeError("TBANK_TERMINAL_KEY / TBANK_PASSWORD not configured")

    # default auto
    if tbank and not saas_settings.PAYMENT_MOCK_ENABLED:
        return tbank
    return MockPaymentGateway()
