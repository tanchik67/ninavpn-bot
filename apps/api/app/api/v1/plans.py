
from fastapi import APIRouter

from apps.api.app.deps import SessionDep
from apps.api.app.schemas import PlanOut
from core.services.billing import list_active_plans

router = APIRouter()


@router.get("", response_model=list[PlanOut])
async def get_plans(session: SessionDep):
    plans = await list_active_plans(session)
    return plans
