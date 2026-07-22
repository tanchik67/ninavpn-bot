from secrets import randbelow

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from adapters.notifications.dispatcher import NotificationDispatcher
from apps.api.app.deps import CurrentUser, SessionDep, client_ip
from apps.api.app.limiter import limiter
from apps.api.app.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    GoogleAuthRequest,
    LinkTelegramRequest,
    LoginRequest,
    MessageOut,
    ProfileEmojiRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TelegramAuthRequest,
    TokenResponse,
    UserOut,
)
from core.domain.enums import NotificationChannel
from core.ports.notifications import NotificationMessage
from core.services import auth_service
from core.services.audit import write_audit
from core.services.auth_service import AuthError
from core.services.oauth_verify import (
    OAuthVerifyError,
    verify_google_id_token,
    verify_telegram_login,
)
from core.settings import saas_settings
from infrastructure.db.models import User
from infrastructure.redis.client import get_redis

router = APIRouter()

_PWD_RESET_TTL = 900  # 15 minutes
_PWD_RESET_COOLDOWN = 60


def _smtp_configured() -> bool:
    return bool(saas_settings.SMTP_HOST and saas_settings.SMTP_FROM)


@router.post("/register", response_model=TokenResponse)
@limiter.limit(saas_settings.AUTH_RATE_LIMIT)
async def register(body: RegisterRequest, request: Request, session: SessionDep):
    try:
        user, access, refresh = await auth_service.register_user(
            session, email=body.email, password=body.password, ip=client_ip(request)
        )
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.code)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(saas_settings.AUTH_RATE_LIMIT)
async def login(body: LoginRequest, request: Request, session: SessionDep):
    try:
        user, access, refresh = await auth_service.login_user(
            session, email=body.email, password=body.password, ip=client_ip(request)
        )
    except AuthError as e:
        code = status.HTTP_403_FORBIDDEN if e.code == "banned" else status.HTTP_401_UNAUTHORIZED
        raise HTTPException(status_code=code, detail=e.code)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/google", response_model=TokenResponse)
@limiter.limit(saas_settings.AUTH_RATE_LIMIT)
async def login_google(body: GoogleAuthRequest, request: Request, session: SessionDep):
    try:
        claims = await verify_google_id_token(body.id_token)
    except OAuthVerifyError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.code)

    email = claims.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="google_email_required")

    try:
        _, access, refresh = await auth_service.login_or_register_google(
            session,
            google_sub=str(claims["sub"]),
            email=str(email),
            email_verified=bool(claims.get("email_verified")),
            ip=client_ip(request),
        )
    except AuthError as e:
        code = status.HTTP_403_FORBIDDEN if e.code == "banned" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=e.code)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/telegram", response_model=TokenResponse)
@limiter.limit(saas_settings.AUTH_RATE_LIMIT)
async def login_telegram(body: TelegramAuthRequest, request: Request, session: SessionDep):
    payload = body.model_dump(exclude_none=True)
    try:
        data = verify_telegram_login(payload)
    except OAuthVerifyError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.code)

    try:
        _, access, refresh = await auth_service.login_or_register_telegram(
            session,
            tg_id=int(data["id"]),
            username=data.get("username"),
            ip=client_ip(request),
        )
    except AuthError as e:
        code = status.HTTP_403_FORBIDDEN if e.code == "banned" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=e.code)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, session: SessionDep):
    try:
        _, access, refresh_tok = await auth_service.refresh_session(session, body.refresh_token)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.code)
    return TokenResponse(access_token=access, refresh_token=refresh_tok)


@router.post("/logout", response_model=MessageOut)
async def logout(body: RefreshRequest, session: SessionDep):
    await auth_service.logout(session, body.refresh_token)
    return MessageOut(detail="ok")


@router.post("/password/forgot", response_model=ForgotPasswordResponse)
@limiter.limit(saas_settings.AUTH_RATE_LIMIT)
async def forgot_password(body: ForgotPasswordRequest, request: Request, session: SessionDep):
    """Send a 6-digit reset code to email. Always returns ok (no email enumeration)."""
    email_n = str(body.email).strip().lower()
    redis = await get_redis()
    cooldown_key = f"pwd_reset_cd:{email_n}"
    if await redis.get(cooldown_key):
        return ForgotPasswordResponse(detail="ok")

    user = await auth_service.find_user_by_email(session, email_n)
    # Fake success for unknown / telegram-placeholder emails
    if not user or email_n.endswith("@telegram.local"):
        await redis.set(cooldown_key, "1", ex=_PWD_RESET_COOLDOWN)
        return ForgotPasswordResponse(detail="ok")

    code = f"{randbelow(1_000_000):06d}"
    await redis.set(f"pwd_reset:{email_n}", code, ex=_PWD_RESET_TTL)
    await redis.set(cooldown_key, "1", ex=_PWD_RESET_COOLDOWN)

    body_text = (
        f"Код восстановления пароля NinaVPN: {code}\n\n"
        f"Действует 15 минут. Если вы не запрашивали сброс — игнорируйте письмо."
    )
    await NotificationDispatcher().dispatch(
        NotificationMessage(
            channel=NotificationChannel.EMAIL,
            template="password_reset",
            recipient=email_n,
            subject="NinaVPN — восстановление пароля",
            body=body_text,
        )
    )
    await write_audit(
        session,
        action="user.password_forgot",
        entity_type="user",
        entity_id=str(user.id),
        actor_user_id=user.id,
        ip=client_ip(request),
    )
    await session.commit()

    resp = ForgotPasswordResponse(detail="ok")
    if not _smtp_configured():
        resp.dev_code = code
    return resp


@router.post("/password/reset", response_model=MessageOut)
@limiter.limit(saas_settings.AUTH_RATE_LIMIT)
async def reset_password(body: ResetPasswordRequest, request: Request, session: SessionDep):
    email_n = str(body.email).strip().lower()
    redis = await get_redis()
    stored = await redis.get(f"pwd_reset:{email_n}")
    if not stored or stored != body.code.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_code")

    try:
        await auth_service.reset_password_with_code(
            session,
            email=email_n,
            new_password=body.new_password,
            ip=client_ip(request),
        )
    except AuthError as e:
        code = status.HTTP_403_FORBIDDEN if e.code == "banned" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=e.code)

    await redis.delete(f"pwd_reset:{email_n}")
    return MessageOut(detail="ok")


@router.post("/password/change", response_model=MessageOut)
@limiter.limit(saas_settings.AUTH_RATE_LIMIT)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user: CurrentUser,
    session: SessionDep,
):
    try:
        await auth_service.change_password(
            session,
            user=user,
            current_password=body.current_password,
            new_password=body.new_password,
            ip=client_ip(request),
        )
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.code)
    return MessageOut(detail="ok")


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


@router.api_route("/me/emoji", methods=["POST", "PATCH"], response_model=UserOut)
async def update_profile_emoji(
    body: ProfileEmojiRequest,
    request: Request,
    user: CurrentUser,
    session: SessionDep,
):
    raw = (body.emoji or "").strip()
    if len(raw) > 32:
        raise HTTPException(status_code=400, detail="emoji_too_long")
    db_user = await session.get(User, user.id)
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid user")
    db_user.profile_emoji = raw or None
    await write_audit(
        session,
        action="user.profile_emoji",
        entity_type="user",
        entity_id=str(db_user.id),
        actor_user_id=db_user.id,
        ip=client_ip(request),
        meta={"emoji": raw or None},
    )
    await session.commit()
    await session.refresh(db_user)
    return db_user


@router.post("/link-telegram", response_model=UserOut)
async def link_telegram(body: LinkTelegramRequest, request: Request, user: CurrentUser, session: SessionDep):
    """Bind Telegram via one-time code from bot /linkcabinet (Redis: tg_link:{code} → tg_id)."""
    code = body.code.strip().lower()
    redis = await get_redis()
    stored = await redis.get(f"tg_link:{code}")
    if not stored:
        stored = await redis.get(f"tg_link:{body.code.strip()}")
        code = body.code.strip()
    if not stored:
        raise HTTPException(status_code=400, detail="invalid_or_expired_code")

    try:
        tg_id = int(stored)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="invalid_or_expired_code")

    if body.tg_id is not None and int(body.tg_id) != tg_id:
        raise HTTPException(status_code=400, detail="tg_id_mismatch")

    existing = await session.scalar(select(User).where(User.tg_id == tg_id))
    if existing and existing.id != user.id:
        raise HTTPException(status_code=400, detail="tg_taken")

    user.tg_id = tg_id
    await redis.delete(f"tg_link:{code}")
    await write_audit(
        session,
        action="user.link_telegram",
        entity_type="user",
        entity_id=str(user.id),
        actor_user_id=user.id,
        ip=client_ip(request),
        meta={"tg_id": tg_id},
    )
    await session.commit()
    await session.refresh(user)

    try:
        dispatcher = NotificationDispatcher()
        await dispatcher.dispatch(
            NotificationMessage(
                channel=NotificationChannel.TELEGRAM,
                template="telegram_linked",
                recipient=str(tg_id),
                body=(
                    "✅ Telegram привязан к кабинету NinaVPN.\n\n"
                    f"Email: <code>{user.email}</code>\n"
                    "Теперь сюда будут приходить уведомления о доступе и окончании подписки."
                ),
            )
        )
    except Exception:
        pass

    return user


@router.post("/unlink-telegram", response_model=UserOut)
async def unlink_telegram(request: Request, user: CurrentUser, session: SessionDep):
    if not user.tg_id:
        return user
    old = user.tg_id
    user.tg_id = None
    await write_audit(
        session,
        action="user.unlink_telegram",
        entity_type="user",
        entity_id=str(user.id),
        actor_user_id=user.id,
        ip=client_ip(request),
        meta={"tg_id": old},
    )
    await session.commit()
    await session.refresh(user)
    return user
