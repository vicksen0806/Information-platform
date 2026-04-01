import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.user import User
from app.models.crawl_job import CrawlJob
from app.models.digest import Digest
from app.core.dependencies import get_current_admin
from app.schemas.user import UserResponse

router = APIRouter(prefix="/admin", tags=["admin"])


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
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = is_active
    await db.flush()
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
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.tasks.crawl_tasks import crawl_all_users
    crawl_all_users.delay()
    return {"message": "Crawl triggered for all active users"}
