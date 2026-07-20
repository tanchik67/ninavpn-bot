
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from adapters.notifications.dispatcher import NotificationDispatcher
from apps.api.app.deps import AdminUser, CurrentUser, SessionDep, client_ip
from apps.api.app.schemas import (
    SupportChatOut,
    SupportCreateRequest,
    SupportMessageOut,
    SupportReplyRequest,
    SupportTicketOut,
)
from core.domain.enums import NotificationChannel, SupportTicketStatus, UserRole
from core.ports.notifications import NotificationMessage
from core.services.audit import write_audit
from core.settings import saas_settings
from infrastructure.db.models import SupportMessage, SupportTicket, User

router = APIRouter()

_STAFF_ROLES = {UserRole.ADMIN.value, UserRole.SUPPORT.value}


async def _notify_admin(text: str) -> None:
    if not saas_settings.ADMIN_ID:
        return
    try:
        dispatcher = NotificationDispatcher()
        await dispatcher.dispatch(
            NotificationMessage(
                channel=NotificationChannel.TELEGRAM,
                template="support_ticket",
                recipient=str(saas_settings.ADMIN_ID),
                body=text,
            )
        )
    except Exception:
        pass


def _is_staff(author: User, ticket: SupportTicket) -> bool:
    return author.role in _STAFF_ROLES


async def _message_out(msg: SupportMessage, author: User, ticket: SupportTicket) -> SupportMessageOut:
    return SupportMessageOut(
        id=msg.id,
        author_user_id=msg.author_user_id,
        body=msg.body,
        created_at=msg.created_at,
        is_staff=_is_staff(author, ticket),
    )


async def _load_messages(session: SessionDep, ticket: SupportTicket) -> list[SupportMessageOut]:
    rows = await session.scalars(
        select(SupportMessage)
        .where(SupportMessage.ticket_id == ticket.id)
        .order_by(SupportMessage.created_at.asc())
    )
    messages = list(rows)
    if not messages:
        return []
    author_ids = {m.author_user_id for m in messages}
    authors = {
        u.id: u
        for u in (
            await session.scalars(select(User).where(User.id.in_(author_ids)))
        ).all()
    }
    return [
        await _message_out(m, authors[m.author_user_id], ticket)
        for m in messages
        if m.author_user_id in authors
    ]


async def _get_user_ticket(session: SessionDep, user: User, ticket_id: UUID) -> SupportTicket:
    ticket = await session.get(SupportTicket, ticket_id)
    if not ticket or ticket.user_id != user.id:
        raise HTTPException(status_code=404, detail="not_found")
    return ticket


@router.get("/chat", response_model=SupportChatOut)
async def get_or_open_chat(user: CurrentUser, session: SessionDep):
    ticket = await session.scalar(
        select(SupportTicket)
        .where(
            SupportTicket.user_id == user.id,
            SupportTicket.status.in_(
                [SupportTicketStatus.OPEN.value, SupportTicketStatus.ANSWERED.value]
            ),
        )
        .order_by(SupportTicket.created_at.desc())
        .limit(1)
    )
    if not ticket:
        ticket = SupportTicket(
            user_id=user.id,
            subject="Чат поддержки",
            body="Обращение открыто",
        )
        session.add(ticket)
        await session.flush()
        await session.commit()
        await session.refresh(ticket)

    messages = await _load_messages(session, ticket)
    return SupportChatOut(ticket=ticket, messages=messages)


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

    await _notify_admin(
        f"🆘 Support ticket\nfrom: {user.email}\n<b>{body.subject}</b>\n{body.body[:800]}"
    )
    return ticket


@router.get("/tickets", response_model=list[SupportTicketOut])
async def list_tickets(user: CurrentUser, session: SessionDep):
    rows = await session.scalars(
        select(SupportTicket)
        .where(SupportTicket.user_id == user.id)
        .order_by(SupportTicket.created_at.desc())
    )
    return list(rows)


@router.get("/tickets/{ticket_id}/messages", response_model=list[SupportMessageOut])
async def list_ticket_messages(
    ticket_id: UUID,
    user: CurrentUser,
    session: SessionDep,
):
    ticket = await _get_user_ticket(session, user, ticket_id)
    return await _load_messages(session, ticket)


@router.post("/tickets/{ticket_id}/messages", response_model=SupportMessageOut)
async def send_ticket_message(
    ticket_id: UUID,
    body: SupportReplyRequest,
    request: Request,
    user: CurrentUser,
    session: SessionDep,
):
    ticket = await _get_user_ticket(session, user, ticket_id)
    if ticket.status == SupportTicketStatus.CLOSED.value:
        raise HTTPException(status_code=400, detail="ticket_closed")

    msg = SupportMessage(ticket_id=ticket.id, author_user_id=user.id, body=body.body)
    session.add(msg)
    ticket.status = SupportTicketStatus.OPEN.value
    await write_audit(
        session,
        action="support.client_message",
        entity_type="support_ticket",
        entity_id=str(ticket.id),
        actor_user_id=user.id,
        ip=client_ip(request),
    )
    await session.commit()
    await session.refresh(msg)

    await _notify_admin(
        f"💬 Сообщение в поддержку\nfrom: {user.email}\n{body.body[:800]}"
    )
    return await _message_out(msg, user, ticket)


@router.post("/admin/tickets/{ticket_id}/messages", response_model=SupportMessageOut)
async def staff_reply(
    ticket_id: UUID,
    body: SupportReplyRequest,
    request: Request,
    staff: AdminUser,
    session: SessionDep,
):
    ticket = await session.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="not_found")
    if ticket.status == SupportTicketStatus.CLOSED.value:
        raise HTTPException(status_code=400, detail="ticket_closed")

    owner = await session.get(User, ticket.user_id)
    msg = SupportMessage(ticket_id=ticket.id, author_user_id=staff.id, body=body.body)
    session.add(msg)
    ticket.status = SupportTicketStatus.ANSWERED.value
    await write_audit(
        session,
        action="support.staff_reply",
        entity_type="support_ticket",
        entity_id=str(ticket.id),
        actor_user_id=staff.id,
        ip=client_ip(request),
    )
    await session.commit()
    await session.refresh(msg)

    if owner and owner.tg_id:
        try:
            dispatcher = NotificationDispatcher()
            await dispatcher.dispatch(
                NotificationMessage(
                    channel=NotificationChannel.TELEGRAM,
                    template="support_reply",
                    recipient=str(owner.tg_id),
                    body=f"📩 Ответ поддержки NinaVPN:\n\n{body.body[:1500]}",
                )
            )
        except Exception:
            pass

    return await _message_out(msg, staff, ticket)
