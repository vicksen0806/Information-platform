from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.crawl_job import CrawlJob
from app.models.digest import Digest
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/stats", tags=["stats"])


class StatsResponse(BaseModel):
    this_month_crawls: int
    this_month_sources: int
    this_month_tokens: int
    unread_digests: int


@router.get("", response_model=StatsResponse)
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    crawl_row = await db.execute(
        select(func.count(CrawlJob.id)).where(
            CrawlJob.user_id == current_user.id,
            CrawlJob.created_at >= month_start,
        )
    )
    this_month_crawls = crawl_row.scalar() or 0

    digest_row = await db.execute(
        select(
            func.coalesce(func.sum(Digest.sources_count), 0),
            func.coalesce(func.sum(Digest.tokens_used), 0),
        ).where(
            Digest.user_id == current_user.id,
            Digest.created_at >= month_start,
        )
    )
    this_month_sources, this_month_tokens = digest_row.one()

    unread_row = await db.execute(
        select(func.count(Digest.id)).where(
            Digest.user_id == current_user.id,
            Digest.is_read == False,  # noqa: E712
        )
    )
    unread_digests = unread_row.scalar() or 0

    return StatsResponse(
        this_month_crawls=int(this_month_crawls),
        this_month_sources=int(this_month_sources),
        this_month_tokens=int(this_month_tokens),
        unread_digests=int(unread_digests),
    )
