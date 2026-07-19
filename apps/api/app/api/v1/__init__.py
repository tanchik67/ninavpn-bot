from fastapi import APIRouter

from apps.api.app.api.v1 import admin, auth, payments, plans, subscriptions, support

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(plans.router, prefix="/plans", tags=["plans"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(support.router, prefix="/support", tags=["support"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
