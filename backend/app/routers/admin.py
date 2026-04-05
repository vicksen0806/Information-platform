import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.user import User
from app.models.crawl_job import CrawlJob
from app.models.digest import Digest
from app.models.audit_log import AuditLog
from app.core.dependencies import get_current_admin
from app.schemas.user import UserResponse

router = APIRouter(prefix="/admin", tags=["admin"])


async def _write_audit(
    db: AsyncSession,
    actor: User,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
):
    log = AuditLog(
        actor_id=actor.id,
        actor_email=actor.email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        ip_address=ip_address,
    )
    db.add(log)
    await db.flush()


# audit-logs must be defined before /{user_id} to avoid route conflict
@router.get("/audit-logs")
async def list_audit_logs(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = 100,
    offset: int = 0,
):
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "actor_email": log.actor_email,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "detail": log.detail,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    return result.scalars().all()


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    is_active: bool,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_status = user.is_active
    user.is_active = is_active

    ip = request.client.host if request.client else None
    await _write_audit(
        db, current_admin,
        action="user.activate" if is_active else "user.deactivate",
        resource_type="user",
        resource_id=str(user_id),
        detail={"email": user.email, "from": old_status, "to": is_active},
        ip_address=ip,
    )

    await db.commit()
    await db.refresh(user)
    return user


@router.get("/stats")
async def get_stats(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    total_users = await db.scalar(select(func.count()).select_from(User))
    total_jobs = await db.scalar(select(func.count()).select_from(CrawlJob))
    total_digests = await db.scalar(select(func.count()).select_from(Digest))
    total_tokens = await db.scalar(select(func.sum(Digest.tokens_used)).select_from(Digest)) or 0

    return {
        "total_users": total_users,
        "total_crawl_jobs": total_jobs,
        "total_digests": total_digests,
        "total_tokens_used": total_tokens,
    }


@router.post("/crawl/trigger-all")
async def trigger_all_crawls(
    request: Request,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.tasks.crawl_tasks import crawl_all_users
    crawl_all_users.delay()

    ip = request.client.host if request.client else None
    await _write_audit(
        db, current_admin,
        action="crawl.trigger_all",
        ip_address=ip,
    )
    await db.commit()

    return {"message": "Crawl triggered for all active users"}
