
from fastapi import APIRouter, Request
from sqlalchemy import select

from adapters.notifications.dispatcher import NotificationDispatcher
from apps.api.app.deps import CurrentUser, SessionDep, client_ip
from apps.api.app.schemas import SupportCreateRequest, SupportTicketOut
from core.domain.enums import NotificationChannel
from core.ports.notifications import NotificationMessage
from core.services.audit import write_audit
from core.settings import saas_settings
from infrastructure.db.models import SupportMessage, SupportTicket

router = APIRouter()


@router.post("/tickets", response_model=SupportTicketOut)
async def create_ticket(
    body: SupportCreateRequest,
    request: Request,
    user: CurrentUser,
    session: SessionDep,
):
    ticket = SupportTicket(user_id=user.id, subject=body.subject, body=body.body)
    session.add(ticket)
    await session.flush()
    session.add(
        SupportMessage(ticket_id=ticket.id, author_user_id=user.id, body=body.body)
    )
    await write_audit(
        session,
        action="support.ticket_created",
        entity_type="support_ticket",
        entity_id=str(ticket.id),
        actor_user_id=user.id,
        ip=client_ip(request),
    )
    await session.commit()
    await session.refresh(ticket)

    # Notify admins via Telegram if configured
    if saas_settings.ADMIN_ID:
        try:
            dispatcher = NotificationDispatcher()
            await dispatcher.dispatch(
                NotificationMessage(
                    channel=NotificationChannel.TELEGRAM,
                    template="support_ticket",
                    recipient=str(saas_settings.ADMIN_ID),
                    body=(
                        f"🆘 Support ticket\n"
                        f"from: {user.email}\n"
                        f"<b>{body.subject}</b>\n{body.body[:800]}"
                    ),
                )
            )
        except Exception:
            pass
    return ticket


@router.get("/tickets", response_model=list[SupportTicketOut])
async def list_tickets(user: CurrentUser, session: SessionDep):
    rows = await session.scalars(
        select(SupportTicket)
        .where(SupportTicket.user_id == user.id)
        .order_by(SupportTicket.created_at.desc())
    )
    return list(rows)
