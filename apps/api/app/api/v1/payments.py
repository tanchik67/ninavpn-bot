
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select

from adapters.payments.factory import get_payment_gateway
from apps.api.app.deps import CurrentUser, SessionDep, client_ip
from apps.api.app.schemas import CheckoutRequest, CheckoutResponse, PaymentOut
from core.services.billing import BillingError, confirm_payment_and_enqueue, create_checkout, get_payment
from infrastructure.db.models import Payment

router = APIRouter()


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    body: CheckoutRequest,
    request: Request,
    user: CurrentUser,
    session: SessionDep,
):
    try:
        payment, url = await create_checkout(
            session,
            user=user,
            plan_key=body.plan_key,
            provider=body.provider,
            ip=client_ip(request),
        )
    except BillingError as e:
        raise HTTPException(status_code=400, detail=e.code)
    return CheckoutResponse(
        payment_id=payment.id,
        payment_url=url,
        provider=payment.provider,
        status=payment.status,
        checkout_token=payment.checkout_token,
    )


@router.get("/{payment_id}", response_model=PaymentOut)
async def payment_status(payment_id: int, user: CurrentUser, session: SessionDep):
    payment = await get_payment(session, payment_id, user.id)
    if not payment:
        raise HTTPException(status_code=404, detail="not_found")
    return payment


@router.post("/webhooks/{provider}")
async def payment_webhook(provider: str, request: Request, session: SessionDep):
    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        form = await request.form()
        payload = {k: v for k, v in form.items()}

    # Mock also accepts query params
    if provider == "mock":
        payload = {**dict(request.query_params), **payload}

    gateway = get_payment_gateway(provider)
    result = await gateway.parse_webhook(payload)
    if result.error == "invalid_token":
        raise HTTPException(status_code=403, detail="invalid_signature")
    if not result.confirmed or not result.our_payment_id:
        return JSONResponse({"ok": True, "ignored": True})

    try:
        payment = await confirm_payment_and_enqueue(
            session,
            payment_id=result.our_payment_id,
            provider_payment_id=result.provider_payment_id,
            raw=result.raw,
        )
    except BillingError as e:
        raise HTTPException(status_code=404, detail=e.code)

    # T-Bank expects plain OK
    if provider == "tbank":
        return HTMLResponse("OK")
    return {"ok": True, "payment_id": payment.id, "status": payment.status}


@router.post("/mock/confirm/{payment_id}")
async def mock_confirm(payment_id: int, user: CurrentUser, session: SessionDep):
    """Dev helper: confirm own pending mock payment."""
    payment = await get_payment(session, payment_id, user.id)
    if not payment:
        raise HTTPException(status_code=404, detail="not_found")
    if payment.provider != "mock":
        raise HTTPException(status_code=400, detail="not_mock")
    payment = await confirm_payment_and_enqueue(
        session,
        payment_id=payment.id,
        provider_payment_id=payment.provider_payment_id,
        raw={"Status": "CONFIRMED", "mock": True},
        actor_user_id=user.id,
    )
    return {"ok": True, "payment_id": payment.id, "status": payment.status}


@router.get("/return/success")
async def return_success(token: str, session: SessionDep):
    payment = await session.scalar(select(Payment).where(Payment.checkout_token == token))
    if not payment:
        return HTMLResponse("<h1>Payment not found</h1>", status_code=404)
    return HTMLResponse(
        f"<h1>Оплата принята</h1><p>Платёж #{payment.id}, статус: {payment.status}</p>"
        f"<p>Вернитесь в приложение NinaVPN.</p>"
    )


@router.get("/return/fail")
async def return_fail(token: str = ""):
    return HTMLResponse("<h1>Оплата не завершена</h1><p>Попробуйте снова в приложении.</p>")
