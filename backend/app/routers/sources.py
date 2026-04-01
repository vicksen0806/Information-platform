import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.source import Source
from app.core.dependencies import get_current_user
from app.schemas.source import SourceCreate, SourceUpdate, SourceResponse, SourceTestResult

router = APIRouter(prefix="/sources", tags=["sources"])

MAX_SOURCES_PER_USER = 20


@router.get("", response_model=list[SourceResponse])
async def list_sources(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Source).where(Source.user_id == current_user.id).order_by(Source.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    data: SourceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count_result = await db.execute(select(Source).where(Source.user_id == current_user.id))
    if len(count_result.scalars().all()) >= MAX_SOURCES_PER_USER:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_SOURCES_PER_USER} sources allowed")

    source = Source(
        user_id=current_user.id,
        name=data.name,
        url=str(data.url),
        source_type=data.source_type,
        crawl_interval_hours=data.crawl_interval_hours,
    )
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return source


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = await _get_owned_source(source_id, current_user.id, db)
    return source


@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: uuid.UUID,
    data: SourceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = await _get_owned_source(source_id, current_user.id, db)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(source, field, value)
    await db.flush()
    await db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = await _get_owned_source(source_id, current_user.id, db)
    await db.delete(source)


@router.post("/{source_id}/test", response_model=SourceTestResult)
async def test_source(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = await _get_owned_source(source_id, current_user.id, db)
    from app.services.crawler_service import fetch_and_extract
    return await fetch_and_extract(source.url, source.source_type, preview_only=True)


async def _get_owned_source(source_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> Source:
    result = await db.execute(
        select(Source).where(Source.id == source_id, Source.user_id == user_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source
