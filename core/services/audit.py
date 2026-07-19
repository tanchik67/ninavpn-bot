from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.models import AuditLog


async def write_audit(
    session: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    actor_user_id: Optional[UUID] = None,
    ip: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
) -> None:
    session.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip=ip,
            meta=meta,
        )
    )
