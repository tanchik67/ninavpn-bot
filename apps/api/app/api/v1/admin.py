
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from adapters.vpn.xui_adapter import get_vpn_adapter
from apps.api.app.deps import AdminUser, SessionDep
from apps.api.app.schemas import AdminExtendRequest, MessageOut, UserOut
from core.domain.enums import SubscriptionStatus
from core.services.audit import write_audit
from infrastructure.db.models import Subscription, User

router = APIRouter()


@router.get("/users", response_model=list[UserOut])
async def list_users(_: AdminUser, session: SessionDep, limit: int = 100):
    rows = await session.scalars(select(User).order_by(User.created_at.desc()).limit(min(limit, 500)))
    return list(rows)


@router.post("/subscriptions/{subscription_id}/extend", response_model=MessageOut)
async def extend_subscription(
    subscription_id: UUID,
    body: AdminExtendRequest,
    admin: AdminUser,
    session: SessionDep,
):
    sub = await session.get(Subscription, subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="not_found")
    user = await session.get(User, sub.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    vpn = get_vpn_adapter()
    ok = await vpn.extend_by_days(user.panel_user_key, body.days)
    if not ok:
        raise HTTPException(status_code=502, detail="panel_extend_failed")

    base = sub.expires_at or datetime.utcnow()
    if base < datetime.utcnow():
        base = datetime.utcnow()
    sub.expires_at = base + timedelta(days=body.days)
    sub.status = SubscriptionStatus.ACTIVE.value
    sub.disabled_at = None
    await write_audit(
        session,
        action="admin.subscription_extend",
        entity_type="subscription",
        entity_id=str(sub.id),
        actor_user_id=admin.id,
        meta={"days": body.days},
    )
    await session.commit()
    return MessageOut(detail=f"extended_by_{body.days}_days")
