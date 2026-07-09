"""Оформление оплаты Т-Банком с сайта."""
from __future__ import annotations

import logging
import secrets
from typing import Any, Dict, Optional

from sqlalchemy import update

from config import (
    payment_public_base_url,
    settings,
    tbank_configured,
    tbank_effective_test_mode,
    tbank_effective_verify_ssl,
)
from database import AsyncSessionLocal, Payment
from services.plan_pricing import resolve_checkout_plan
from services.site_user import get_or_create_site_user, is_valid_checkout_email, normalize_checkout_email
from services import tbank as tbank_svc

log = logging.getLogger(__name__)


async def create_site_tbank_checkout(
    *,
    email: str,
    plan_key: Optional[str] = None,
    months: Optional[int] = None,
    devices: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Создаёт Payment + Init Т-Банка для оплаты на сайте.
    Возвращает {success, payment_url?, checkout_token?, error?, message?}.
    """
    email_norm = normalize_checkout_email(email)
    if not is_valid_checkout_email(email_norm):
        return {"success": False, "error": "invalid_email", "message": "Укажите корректный email"}

    if not tbank_configured():
        return {"success": False, "error": "tbank_not_configured", "message": "Оплата временно недоступна"}

    try:
        plan_key_resolved, months_resolved, devices_resolved, rub = await resolve_checkout_plan(
            plan_key=plan_key,
            months=months,
            devices=devices,
        )
    except ValueError as e:
        code = str(e)
        messages = {
            "plan_not_found": "Тариф недоступен",
            "invalid_months": "Некорректный срок тарифа",
            "plan_required": "Не выбран тариф",
        }
        return {
            "success": False,
            "error": code,
            "message": messages.get(code, "Некорректный тариф"),
        }

    try:
        user = await get_or_create_site_user(email_norm)
    except ValueError:
        return {"success": False, "error": "invalid_email", "message": "Укажите корректный email"}

    checkout_token = secrets.token_urlsafe(24)
    payment_id: int

    async with AsyncSessionLocal() as s:
        payment = Payment(
            user_tg_id=user.tg_id,
            plan_key=plan_key_resolved,
            devices=devices_resolved,
            method="tbank",
            amount_rub=rub,
            amount_crypto=0.0,
            currency="RUB",
            status="pending",
            checkout_token=checkout_token,
            checkout_email=email_norm,
        )
        s.add(payment)
        await s.commit()
        await s.refresh(payment)
        payment_id = payment.id

    test_mode = tbank_effective_test_mode()
    verify_ssl = tbank_effective_verify_ssl()
    base = tbank_svc.acquiring_base_url(
        test_mode=test_mode,
        override=None,
    )
    pub = payment_public_base_url()
    notification_url = f"{pub}/payment/tbank" if pub else None
    success_url = f"{pub}/payment/success?t={checkout_token}" if pub else None
    fail_url = f"{pub}/payment/fail" if pub else None

    order_id = tbank_svc.order_id_for_payment(payment_id)

    terminal = (settings.TBANK_TERMINAL_KEY or "").strip()
    password = (settings.TBANK_PASSWORD or "").strip()
    kop = tbank_svc.rub_to_kopecks(rub)
    desc = f"NINAVPN {plan_key_resolved}"[:140]

    resp = await tbank_svc.init_payment(
        terminal,
        password,
        order_id=order_id,
        amount_kopecks=kop,
        description=desc,
        base_url=base,
        notification_url=notification_url,
        success_url=success_url,
        fail_url=fail_url,
        verify_ssl=verify_ssl,
    )

    if not resp.get("Success"):
        log.error(
            "Site T-Bank Init failed payment_id=%s resp=%s test_mode=%s",
            payment_id,
            resp,
            test_mode,
        )
        async with AsyncSessionLocal() as s:
            await s.execute(
                update(Payment).where(Payment.id == payment_id).values(status="failed")
            )
            await s.commit()
        return {
            "success": False,
            "error": "init_failed",
            "message": "Не удалось создать оплату. Попробуйте позже.",
        }

    pay_url = (resp.get("PaymentURL") or "").strip()
    if not pay_url:
        log.error("Site T-Bank Init: нет PaymentURL payment_id=%s", payment_id)
        return {
            "success": False,
            "error": "no_payment_url",
            "message": "Ошибка ссылки оплаты",
        }

    ext_id = str(resp.get("PaymentId") or "")[:128]
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(Payment).where(Payment.id == payment_id).values(tx_hash=ext_id or None)
        )
        await s.commit()

    return {
        "success": True,
        "payment_url": pay_url,
        "checkout_token": checkout_token,
        "payment_id": payment_id,
        "amount_rub": rub,
        "plan_key": plan_key_resolved,
        "months": months_resolved,
        "devices": devices_resolved,
    }


async def get_checkout_status(checkout_token: str) -> Dict[str, Any]:
    """Статус заказа с сайта для страницы success (polling)."""
    token = (checkout_token or "").strip()
    if not token or len(token) > 64:
        return {"ok": False, "error": "invalid_token"}

    from database import Payment, Subscription
    from sqlalchemy import desc, select

    async with AsyncSessionLocal() as s:
        payment = await s.scalar(select(Payment).where(Payment.checkout_token == token))
        if not payment:
            return {"ok": False, "error": "not_found"}

        out: Dict[str, Any] = {
            "ok": True,
            "status": payment.status,
            "payment_id": payment.id,
            "plan_key": payment.plan_key,
            "devices": payment.devices,
            "amount_rub": float(payment.amount_rub or 0),
            "email": payment.checkout_email,
        }

        if payment.status != "confirmed":
            return out

        since = payment.confirmed_at or payment.created_at
        sub = await s.scalar(
            select(Subscription)
            .where(Subscription.user_tg_id == payment.user_tg_id)
            .where(Subscription.started_at >= since)
            .order_by(desc(Subscription.started_at))
            .limit(1)
        )
        if sub:
            expires = sub.expires_at.strftime("%d.%m.%Y") if sub.expires_at else None
            out["config_link"] = sub.config_link or ""
            out["config_link_extra"] = sub.config_link_extra or ""
            out["expires_at"] = expires
        return out
