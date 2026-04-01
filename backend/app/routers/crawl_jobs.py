import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.crawl_job import CrawlJob
from app.models.crawl_result import CrawlResult
from app.models.source import Source
from app.core.dependencies import get_current_user
from app.schemas.crawl_job import CrawlJobResponse, CrawlResultResponse

router = APIRouter(prefix="/crawl-jobs", tags=["crawl-jobs"])


@router.get("", response_model=list[CrawlJobResponse])
async def list_crawl_jobs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
):
    result = await db.execute(
        select(CrawlJob)
        .where(CrawlJob.user_id == current_user.id)
        .order_by(CrawlJob.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.post("", response_model=CrawlJobResponse, status_code=status.HTTP_201_CREATED)
async def trigger_crawl(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Check if there's already a running job for this user
    result = await db.execute(
        select(CrawlJob).where(
            CrawlJob.user_id == current_user.id,
            CrawlJob.status.in_(["pending", "running"]),
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A crawl job is already running")

    job = CrawlJob(user_id=current_user.id, triggered_by="manual")
    db.add(job)
    await db.flush()
    await db.refresh(job)

    # Dispatch to Celery
    from app.tasks.crawl_tasks import run_crawl_job
    run_crawl_job.delay(str(job.id), str(current_user.id))

    return job


@router.get("/{job_id}", response_model=CrawlJobResponse)
async def get_crawl_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_owned_job(job_id, current_user.id, db)


@router.get("/{job_id}/results", response_model=list[CrawlResultResponse])
async def get_crawl_results(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_job(job_id, current_user.id, db)

    result = await db.execute(
        select(CrawlResult, Source.name.label("source_name"))
        .join(Source, CrawlResult.source_id == Source.id)
        .where(CrawlResult.crawl_job_id == job_id)
        .order_by(CrawlResult.crawled_at.asc())
    )
    rows = result.all()

    items = []
    for crawl_result, source_name in rows:
        preview = None
        if crawl_result.raw_content:
            preview = crawl_result.raw_content[:300]
        items.append(CrawlResultResponse(
            id=crawl_result.id,
            source_id=crawl_result.source_id,
            source_name=source_name,
            http_status=crawl_result.http_status,
            content_preview=preview,
            error_message=crawl_result.error_message,
            crawled_at=crawl_result.crawled_at,
        ))
    return items


async def _get_owned_job(job_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> CrawlJob:
    result = await db.execute(
        select(CrawlJob).where(CrawlJob.id == job_id, CrawlJob.user_id == user_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return job
