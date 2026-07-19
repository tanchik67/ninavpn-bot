
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from apps.api.app.api.v1 import api_router
from apps.api.app.limiter import limiter
from core.services.billing import seed_default_plans
from core.settings import saas_settings
from infrastructure.db.base import SaasSessionLocal, init_db
from infrastructure.redis.client import close_redis, get_redis

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(level=logging.INFO)
    await init_db()
    async with SaasSessionLocal() as session:
        await seed_default_plans(session)
    await get_redis()
    log.info("NinaVPN API ready")
    yield
    await close_redis()


app = FastAPI(title="NinaVPN API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

origins = [o.strip() for o in saas_settings.API_CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
@limiter.limit("120/minute")
async def health(request: Request):
    return {"status": "ok", "service": "ninavpn-api"}
