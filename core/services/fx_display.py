"""Multi-currency display helpers (RUB remains settlement for RU rails)."""
from __future__ import annotations

# Approximate display rates — update periodically; checkout still settles in RUB/crypto/Stripe.
USD_PER_RUB = 0.011
EUR_PER_RUB = 0.010


def rub_to_usd(amount_rub: float) -> float:
    return round(float(amount_rub) * USD_PER_RUB, 2)


def rub_to_eur(amount_rub: float) -> float:
    return round(float(amount_rub) * EUR_PER_RUB, 2)


def format_price_bundle(amount_rub: float) -> dict[str, float]:
    return {
        "rub": round(float(amount_rub), 2),
        "usd": rub_to_usd(amount_rub),
        "eur": rub_to_eur(amount_rub),
    }
