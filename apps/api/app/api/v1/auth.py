
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from apps.api.app.deps import CurrentUser, SessionDep, client_ip
from apps.api.app.schemas import (
    LinkTelegramRequest,
    LoginRequest,
    MessageOut,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from core.services import auth_service
from core.services.auth_service import AuthError
from apps.api.app.limiter import limiter
from core.settings import saas_settings
from infrastructure.db.models import User
from infrastructure.redis.client import get_redis

router = APIRouter()


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


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


@router.post("/link-telegram", response_model=UserOut)
async def link_telegram(body: LinkTelegramRequest, user: CurrentUser, session: SessionDep):
    """Minimal link: one-time code stored in Redis by bot (tg_link:{code} -> tg_id)."""
    redis = await get_redis()
    stored = await redis.get(f"tg_link:{body.code.strip()}")
    if not stored or str(stored) != str(body.tg_id):
        raise HTTPException(status_code=400, detail="invalid_code")
    existing = await session.scalar(select(User).where(User.tg_id == body.tg_id))
    if existing and existing.id != user.id:
        raise HTTPException(status_code=400, detail="tg_taken")
    user.tg_id = body.tg_id
    await redis.delete(f"tg_link:{body.code.strip()}")
    await session.commit()
    await session.refresh(user)
    return user
