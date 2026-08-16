import asyncio
import html
import logging
import re
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from adapters.notifications.dispatcher import NotificationDispatcher
from apps.api.app.deps import AdminUser, CurrentUser, SessionDep, client_ip
from apps.api.app.schemas import (
    SupportChatOut,
    SupportCreateRequest,
    SupportMessageOut,
    SupportPhotoChunkAck,
    SupportPhotoChunkRequest,
    SupportReplyRequest,
    SupportTicketAdminOut,
    SupportTicketOut,
)
from core.domain.enums import NotificationChannel, SupportTicketStatus, UserRole
from core.ports.notifications import NotificationMessage
from core.services.audit import write_audit
from core.services.support_media import (
    media_root,
    resolve_media_file,
    save_image_base64,
    save_image_bytes,
)
from core.settings import saas_settings
from infrastructure.db.models import SupportMessage, SupportTicket, User

router = APIRouter()
log = logging.getLogger(__name__)

_STAFF_ROLES = {UserRole.ADMIN.value, UserRole.SUPPORT.value}
_ACTIVE_STATUSES = [
    SupportTicketStatus.OPEN.value,
    SupportTicketStatus.ANSWERED.value,
]


def _admin_chat_ids() -> list[int]:
    """Mirror bot admin_id_set: ADMIN_ID + comma-separated ADMIN_IDS."""
    ids: set[int] = set()
    if saas_settings.ADMIN_ID is not None:
        ids.add(int(saas_settings.ADMIN_ID))
    raw = (saas_settings.ADMIN_IDS or "").strip()
    if raw:
        for part in raw.split(","):
            p = part.strip()
            if p.isdigit():
                ids.add(int(p))
    return sorted(ids)


async def _notify_admin(text: str, photo_abs: str | None = None) -> None:
    """Notify admins via Telegram Bot API from the server (not the user's phone)."""
    targets = _admin_chat_ids()
    if not targets:
        log.warning("support notify skipped: ADMIN_ID/ADMIN_IDS empty")
        return
    if not saas_settings.BOT_TOKEN:
        log.warning("support notify skipped: BOT_TOKEN missing")
        return
    dispatcher = NotificationDispatcher()
    payload: dict = {}
    if photo_abs:
        payload["photo_path"] = photo_abs
    for chat_id in targets:
        try:
            ok = await dispatcher.dispatch(
                NotificationMessage(
                    channel=NotificationChannel.TELEGRAM,
                    template="support_ticket",
                    recipient=str(chat_id),
                    body=text,
                    payload=payload,
                )
            )
            if not ok:
                log.warning("support notify failed for chat_id=%s", chat_id)
        except Exception:
            log.exception("support admin notify failed chat_id=%s", chat_id)


def _notify_admin_bg(text: str, photo_abs: str | None = None) -> None:
    """Fire-and-forget so HTTP responses are not blocked by Telegram latency."""
    try:
        asyncio.create_task(_notify_admin(text, photo_abs))
    except RuntimeError:
        pass


def _tg_support_alert(email: str | None, preview: str) -> str:
    who = html.escape((email or "unknown")[:200])
    body = html.escape((preview or "")[:800])
    return f"💬 Сообщение в поддержку\nfrom: {who}\n{body}"


def _is_staff(author: User, ticket: SupportTicket) -> bool:
    return author.role in _STAFF_ROLES


def _image_url(msg: SupportMessage) -> str | None:
    if not getattr(msg, "image_path", None):
        return None
    return f"/api/v1/support/media/{msg.id}"


async def _message_out(msg: SupportMessage, author: User, ticket: SupportTicket) -> SupportMessageOut:
    return SupportMessageOut(
        id=msg.id,
        author_user_id=msg.author_user_id,
        body=msg.body or "",
        created_at=msg.created_at,
        is_staff=_is_staff(author, ticket),
        image_url=_image_url(msg),
        client_msg_id=getattr(msg, "client_msg_id", None),
    )


def _clean_client_msg_id(raw: str | None) -> str | None:
    if not raw:
        return None
    s = str(raw).strip()[:64]
    if not s:
        return None
    # Allow local-* and uuid-like ids from the app
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{4,64}", s):
        return None
    return s


def _normalize_message(text: str, image_path: str | None) -> tuple[str, str | None]:
    text = (text or "").strip()
    if not text and not image_path:
        raise HTTPException(status_code=400, detail="empty_message")
    if not text and image_path:
        text = "📷 Фото"
    return text, image_path


def _parse_reply(body: SupportReplyRequest) -> tuple[str, str | None]:
    image_path: str | None = None
    token = (body.image_token or "").strip()
    if token:
        if not resolve_media_file(token):
            raise HTTPException(status_code=400, detail="invalid_image_token")
        image_path = token
    elif body.image_base64:
        try:
            image_path = save_image_base64(
                body.image_base64,
                body.image_mime or "image/jpeg",
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    return _normalize_message(body.body or "", image_path)


async def _parse_multipart(
    body: str | None,
    image: object | None,
) -> tuple[str, str | None]:
    image_path: str | None = None
    # Duck-type UploadFile — Starlette/FastAPI class identity can diverge across versions.
    read = getattr(image, "read", None) if image is not None else None
    if callable(read):
        raw = await read()
        if raw:
            mime = getattr(image, "content_type", None) or "image/jpeg"
            try:
                image_path = save_image_bytes(raw, str(mime))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
    return _normalize_message(body or "", image_path)


_MAX_CHAT_MESSAGES = 40
_MAX_ADMIN_CHAT_MESSAGES = 120


async def _load_messages(
    session: SessionDep,
    ticket: SupportTicket,
    *,
    limit: int | None = None,
) -> list[SupportMessageOut]:
    # Newest N only — full history grew huge from retry storms and slowed mobile ACK.
    cap = limit if limit is not None else _MAX_CHAT_MESSAGES
    rows = (
        await session.scalars(
            select(SupportMessage)
            .where(SupportMessage.ticket_id == ticket.id)
            .order_by(SupportMessage.created_at.desc())
            .limit(cap)
        )
    ).all()
    messages = list(reversed(list(rows)))
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

    _notify_admin_bg(
        "🆘 Support ticket\n"
        f"from: {html.escape((user.email or '')[:200])}\n"
        f"<b>{html.escape((body.subject or '')[:200])}</b>\n"
        f"{html.escape((body.body or '')[:800])}"
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


@router.get(
    "/tickets/{ticket_id}/messages/by-client/{client_msg_id}",
    response_model=SupportMessageOut,
)
async def get_message_by_client_id(
    ticket_id: UUID,
    client_msg_id: str,
    user: CurrentUser,
    session: SessionDep,
):
    """Tiny ACK lookup — mobile uses this when POST response is lost on the wire."""
    ticket = await _get_user_ticket(session, user, ticket_id)
    cid = _clean_client_msg_id(client_msg_id)
    if not cid:
        raise HTTPException(status_code=404, detail="not_found")
    msg = await session.scalar(
        select(SupportMessage).where(
            SupportMessage.ticket_id == ticket.id,
            SupportMessage.client_msg_id == cid,
        )
    )
    if not msg:
        raise HTTPException(status_code=404, detail="not_found")
    author = await session.get(User, msg.author_user_id)
    if not author:
        raise HTTPException(status_code=404, detail="not_found")
    return await _message_out(msg, author, ticket)


@router.post("/tickets/{ticket_id}/photo-chunk")
async def support_photo_chunk(
    ticket_id: UUID,
    body: SupportPhotoChunkRequest,
    request: Request,
    user: CurrentUser,
    session: SessionDep,
):
    """
    Accept a photo as many tiny JSON chunks (same size as text messages).
    When all chunks are present, assemble JPEG + create message + Telegram photo.
    """
    ticket = await _get_user_ticket(session, user, ticket_id)
    cid = _clean_client_msg_id(body.client_msg_id)
    if not cid:
        raise HTTPException(status_code=400, detail="invalid_client_msg_id")
    if body.index >= body.total:
        raise HTTPException(status_code=400, detail="invalid_chunk_index")
    if not re.fullmatch(r"[A-Za-z0-9+/=\s]{1,4500}", body.data or ""):
        raise HTTPException(status_code=400, detail="invalid_chunk_data")

    existing = await session.scalar(
        select(SupportMessage).where(
            SupportMessage.ticket_id == ticket.id,
            SupportMessage.client_msg_id == cid,
        )
    )
    if existing and existing.image_path:
        return await _message_out(existing, user, ticket)

    chunk_dir = media_root() / "chunks" / cid
    chunk_dir.mkdir(parents=True, exist_ok=True)
    # If client retries with a new total (smaller re-encode), reset stale parts
    meta = chunk_dir / "meta.txt"
    if meta.exists():
        try:
            prev_total = int(meta.read_text(encoding="utf-8").splitlines()[0])
        except (ValueError, IndexError):
            prev_total = body.total
        if prev_total != body.total:
            for p in chunk_dir.iterdir():
                p.unlink(missing_ok=True)

    (chunk_dir / f"{body.index:03d}.b64").write_text(
        body.data.strip(), encoding="ascii"
    )
    if body.index == 0 or not meta.exists():
        # Avoid emoji in meta — some stacks mishandle non-ascii captions in files
        caption = (body.body or "").strip() or "Photo"
        meta.write_text(
            f"{body.total}\n{caption}\n{body.image_mime or 'image/jpeg'}\n",
            encoding="utf-8",
        )

    parts = sorted(
        p for p in chunk_dir.glob("*.b64") if p.stem.isdigit()
    )
    if len(parts) < body.total:
        log.info(
            "support photo-chunk progress ticket=%s cid=%s %s/%s",
            ticket_id,
            cid,
            len(parts),
            body.total,
        )
        return SupportPhotoChunkAck(ok=True, received=len(parts), total=body.total)

    meta_lines = meta.read_text(encoding="utf-8").splitlines()
    caption = (meta_lines[1] if len(meta_lines) > 1 else "") or "📷 Фото"
    mime = (meta_lines[2] if len(meta_lines) > 2 else "image/jpeg") or "image/jpeg"
    b64 = "".join(p.read_text(encoding="ascii") for p in parts)
    try:
        image_path = save_image_base64(b64, mime)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        try:
            for p in chunk_dir.iterdir():
                p.unlink(missing_ok=True)
            chunk_dir.rmdir()
        except OSError:
            pass

    log.info(
        "support photo-chunk complete ticket=%s cid=%s parts=%s",
        ticket_id,
        cid,
        body.total,
    )
    return await _client_send(
        ticket_id=ticket_id,
        text=caption,
        image_path=image_path,
        request=request,
        user=user,
        session=session,
        client_msg_id=cid,
    )


@router.post("/tickets/{ticket_id}/upload", response_model=SupportMessageOut)
async def upload_support_image(
    ticket_id: UUID,
    request: Request,
    user: CurrentUser,
    session: SessionDep,
):
    """
    One-shot photo message for flaky mobile networks.
    Multipart fields: image (required), body?, client_msg_id?
    Saves file, creates the chat message, notifies admins via Telegram document.
    """
    ctype = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" not in ctype:
        raise HTTPException(status_code=400, detail="multipart_required")
    form = await request.form()
    image_field = form.get("image")
    read = getattr(image_field, "read", None) if image_field is not None else None
    if not callable(read):
        raise HTTPException(status_code=400, detail="image_required")
    raw = await read()
    if not raw:
        raise HTTPException(status_code=400, detail="image_required")
    mime = getattr(image_field, "content_type", None) or "image/jpeg"
    try:
        path = save_image_bytes(raw, str(mime))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Prefer form fields; MIUI often only delivers a single-file multipart,
    # so also accept body/client_msg_id from query string.
    body_field = form.get("body")
    raw_cid = form.get("client_msg_id")
    if body_field is None:
        body_field = request.query_params.get("body")
    if raw_cid is None:
        raw_cid = request.query_params.get("client_msg_id")
    text = str(body_field).strip() if body_field is not None else ""
    client_msg_id = str(raw_cid) if raw_cid is not None else None
    log.info(
        "support upload+message ticket=%s bytes=%s cid=%s",
        ticket_id,
        len(raw),
        client_msg_id,
    )
    return await _client_send(
        ticket_id=ticket_id,
        text=text or "📷 Фото",
        image_path=path,
        request=request,
        user=user,
        session=session,
        client_msg_id=client_msg_id,
    )


async def _client_send(
    *,
    ticket_id: UUID,
    text: str,
    image_path: str | None,
    request: Request,
    user: User,
    session: SessionDep,
    client_msg_id: str | None = None,
) -> SupportMessageOut:
    ticket = await _get_user_ticket(session, user, ticket_id)
    if ticket.status == SupportTicketStatus.CLOSED.value:
        raise HTTPException(status_code=400, detail="ticket_closed")

    cid = _clean_client_msg_id(client_msg_id)
    if cid:
        existing = await session.scalar(
            select(SupportMessage).where(
                SupportMessage.ticket_id == ticket.id,
                SupportMessage.client_msg_id == cid,
            )
        )
        if existing:
            return await _message_out(existing, user, ticket)

    # Soft dedupe for older clients without client_msg_id (retry storms)
    if not cid:
        since = datetime.utcnow() - timedelta(seconds=120)
        twin = await session.scalar(
            select(SupportMessage)
            .where(
                SupportMessage.ticket_id == ticket.id,
                SupportMessage.author_user_id == user.id,
                SupportMessage.body == text,
                SupportMessage.created_at >= since,
            )
            .order_by(SupportMessage.created_at.desc())
            .limit(1)
        )
        if twin and bool(twin.image_path) == bool(image_path):
            return await _message_out(twin, user, ticket)

    msg = SupportMessage(
        ticket_id=ticket.id,
        author_user_id=user.id,
        body=text,
        image_path=image_path,
        client_msg_id=cid,
    )
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
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        if cid:
            existing = await session.scalar(
                select(SupportMessage).where(
                    SupportMessage.ticket_id == ticket.id,
                    SupportMessage.client_msg_id == cid,
                )
            )
            if existing:
                return await _message_out(existing, user, ticket)
        raise
    await session.refresh(msg)
    out = await _message_out(msg, user, ticket)

    preview = text if not image_path else f"{text}"
    photo_abs: str | None = None
    if image_path:
        resolved = resolve_media_file(image_path)
        if resolved is not None:
            photo_abs = str(resolved)
        else:
            preview = f"{text} [photo]"
    _notify_admin_bg(_tg_support_alert(user.email, preview), photo_abs)
    return out


@router.post("/tickets/{ticket_id}/messages", response_model=SupportMessageOut)
async def send_ticket_message(
    ticket_id: UUID,
    request: Request,
    user: CurrentUser,
    session: SessionDep,
):
    """
    Accepts either JSON `{body, image_base64?, client_msg_id?}` or multipart
    `body` + `image` + optional `client_msg_id`.
    """
    ctype = (request.headers.get("content-type") or "").lower()
    client_msg_id: str | None = None
    if "multipart/form-data" in ctype:
        form = await request.form()
        body_field = form.get("body")
        image_field = form.get("image")
        raw_cid = form.get("client_msg_id")
        client_msg_id = str(raw_cid) if raw_cid is not None else None
        text, image_path = await _parse_multipart(
            str(body_field) if body_field is not None else None,
            image_field,
        )
    else:
        try:
            payload = await request.json()
            body_json = SupportReplyRequest.model_validate(payload)
        except Exception as e:
            raise HTTPException(status_code=400, detail="invalid_body") from e
        text, image_path = _parse_reply(body_json)
        client_msg_id = body_json.client_msg_id
    return await _client_send(
        ticket_id=ticket_id,
        text=text,
        image_path=image_path,
        request=request,
        user=user,
        session=session,
        client_msg_id=client_msg_id,
    )


@router.get("/media/{message_id}")
async def get_message_media(
    message_id: UUID,
    user: CurrentUser,
    session: SessionDep,
):
    msg = await session.get(SupportMessage, message_id)
    if not msg or not msg.image_path:
        raise HTTPException(status_code=404, detail="not_found")
    ticket = await session.get(SupportTicket, msg.ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="not_found")
    staff = user.role in _STAFF_ROLES
    if not staff and ticket.user_id != user.id:
        raise HTTPException(status_code=404, detail="not_found")
    path = resolve_media_file(msg.image_path)
    if not path:
        raise HTTPException(status_code=404, detail="not_found")
    media = "image/jpeg"
    suf = path.suffix.lower()
    if suf == ".png":
        media = "image/png"
    elif suf == ".webp":
        media = "image/webp"
    elif suf == ".gif":
        media = "image/gif"
    return FileResponse(path, media_type=media)


@router.get("/admin/tickets", response_model=list[SupportTicketAdminOut])
async def admin_list_tickets(
    staff: AdminUser,
    session: SessionDep,
    include_closed: bool = False,
):
    q = select(SupportTicket).order_by(SupportTicket.created_at.desc())
    if not include_closed:
        q = q.where(SupportTicket.status.in_(_ACTIVE_STATUSES))
    tickets = list(await session.scalars(q))
    if not tickets:
        return []

    user_ids = {t.user_id for t in tickets}
    users = {
        u.id: u
        for u in (await session.scalars(select(User).where(User.id.in_(user_ids)))).all()
    }

    # Latest message per ticket only — do NOT pull full history (sigma-size threads).
    ticket_ids = [t.id for t in tickets]
    latest_subq = (
        select(
            SupportMessage.ticket_id.label("tid"),
            func.max(SupportMessage.created_at).label("max_created"),
        )
        .where(SupportMessage.ticket_id.in_(ticket_ids))
        .group_by(SupportMessage.ticket_id)
        .subquery()
    )
    msg_rows = list(
        await session.scalars(
            select(SupportMessage).join(
                latest_subq,
                (SupportMessage.ticket_id == latest_subq.c.tid)
                & (SupportMessage.created_at == latest_subq.c.max_created),
            )
        )
    )
    latest: dict = {}
    author_ids: set = set()
    for m in msg_rows:
        # Same timestamp collision — keep one
        if m.ticket_id in latest:
            continue
        latest[m.ticket_id] = m
        author_ids.add(m.author_user_id)
    authors = {
        u.id: u
        for u in (
            await session.scalars(select(User).where(User.id.in_(author_ids)))
        ).all()
    } if author_ids else {}

    out: list[SupportTicketAdminOut] = []
    for ticket in tickets:
        owner = users.get(ticket.user_id)
        last = latest.get(ticket.id)
        last_is_staff = False
        if last:
            author = authors.get(last.author_user_id)
            last_is_staff = bool(author and author.role in _STAFF_ROLES)
        out.append(
            SupportTicketAdminOut(
                id=ticket.id,
                subject=ticket.subject,
                body=ticket.body,
                status=ticket.status,
                created_at=ticket.created_at,
                user_id=ticket.user_id,
                user_email=owner.email if owner else "—",
                last_message=(last.body[:200] if last else None),
                last_message_at=(last.created_at if last else None),
                last_is_staff=last_is_staff,
            )
        )
    return out


@router.get("/admin/tickets/{ticket_id}", response_model=SupportChatOut)
async def admin_get_ticket(
    ticket_id: UUID,
    staff: AdminUser,
    session: SessionDep,
):
    ticket = await session.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="not_found")
    messages = await _load_messages(
        session, ticket, limit=_MAX_ADMIN_CHAT_MESSAGES
    )
    return SupportChatOut(ticket=ticket, messages=messages)


@router.get("/admin/tickets/{ticket_id}/messages", response_model=list[SupportMessageOut])
async def admin_list_messages(
    ticket_id: UUID,
    staff: AdminUser,
    session: SessionDep,
):
    ticket = await session.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="not_found")
    return await _load_messages(
        session, ticket, limit=_MAX_ADMIN_CHAT_MESSAGES
    )


@router.post("/admin/tickets/{ticket_id}/messages", response_model=SupportMessageOut)
async def staff_reply(
    ticket_id: UUID,
    request: Request,
    staff: AdminUser,
    session: SessionDep,
):
    ticket = await session.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="not_found")
    if ticket.status == SupportTicketStatus.CLOSED.value:
        raise HTTPException(status_code=400, detail="ticket_closed")

    ctype = (request.headers.get("content-type") or "").lower()
    client_msg_id: str | None = None
    if "multipart/form-data" in ctype:
        form = await request.form()
        body_field = form.get("body")
        image_field = form.get("image")
        raw_cid = form.get("client_msg_id")
        client_msg_id = str(raw_cid) if raw_cid is not None else None
        text, image_path = await _parse_multipart(
            str(body_field) if body_field is not None else None,
            image_field,
        )
    else:
        try:
            payload = await request.json()
            body = SupportReplyRequest.model_validate(payload)
        except Exception as e:
            raise HTTPException(status_code=400, detail="invalid_body") from e
        text, image_path = _parse_reply(body)
        client_msg_id = body.client_msg_id

    cid = _clean_client_msg_id(client_msg_id)
    if cid:
        existing = await session.scalar(
            select(SupportMessage).where(
                SupportMessage.ticket_id == ticket.id,
                SupportMessage.client_msg_id == cid,
            )
        )
        if existing:
            return await _message_out(existing, staff, ticket)

    owner = await session.get(User, ticket.user_id)
    msg = SupportMessage(
        ticket_id=ticket.id,
        author_user_id=staff.id,
        body=text,
        image_path=image_path,
        client_msg_id=cid,
    )
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
    out = await _message_out(msg, staff, ticket)

    if owner and owner.tg_id:
        async def _notify_owner() -> None:
            try:
                dispatcher = NotificationDispatcher()
                preview = text if not image_path else f"{text}\n(фото в приложении)"
                await dispatcher.dispatch(
                    NotificationMessage(
                        channel=NotificationChannel.TELEGRAM,
                        template="support_reply",
                        recipient=str(owner.tg_id),
                        body=f"📩 Ответ поддержки NinaVPN:\n\n{preview[:1500]}",
                    )
                )
            except Exception:
                log.exception("support owner notify failed")

        try:
            asyncio.create_task(_notify_owner())
        except RuntimeError:
            pass

    return out
