import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.user import User
from app.models.keyword import Keyword
from app.core.dependencies import get_current_user
from app.schemas.keyword import KeywordCreate, KeywordUpdate, KeywordResponse

router = APIRouter(prefix="/keywords", tags=["keywords"])

MAX_KEYWORDS_PER_USER = 50


@router.get("", response_model=list[KeywordResponse])
async def list_keywords(
    group: str | None = Query(default=None, description="Filter by group name"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Keyword).where(Keyword.user_id == current_user.id)
    if group is not None:
        if group == "":
            stmt = stmt.where(Keyword.group_name.is_(None))
        else:
            stmt = stmt.where(Keyword.group_name == group)
    stmt = stmt.order_by(Keyword.group_name.asc().nulls_last(), Keyword.created_at.asc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/groups", response_model=list[str])
async def list_groups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return distinct non-null group names for this user."""
    from sqlalchemy import distinct
    result = await db.execute(
        select(distinct(Keyword.group_name))
        .where(Keyword.user_id == current_user.id, Keyword.group_name.isnot(None))
        .order_by(Keyword.group_name)
    )
    return [row for row in result.scalars().all()]


@router.post("", response_model=KeywordResponse, status_code=status.HTTP_201_CREATED)
async def create_keyword(
    data: KeywordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count_result = await db.execute(select(Keyword).where(Keyword.user_id == current_user.id))
    if len(count_result.scalars().all()) >= MAX_KEYWORDS_PER_USER:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_KEYWORDS_PER_USER} keywords allowed")

    keyword = Keyword(
        user_id=current_user.id,
        text=data.text,
        url=data.url or None,
        source_type=data.source_type if data.url else "search",
        group_name=data.group_name or None,
        crawl_interval_hours=data.crawl_interval_hours,
    )
    db.add(keyword)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Keyword already exists")
    await db.refresh(keyword)
    return keyword


@router.patch("/{keyword_id}", response_model=KeywordResponse)
async def update_keyword(
    keyword_id: uuid.UUID,
    data: KeywordUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    keyword = await _get_owned_keyword(keyword_id, current_user.id, db)
    if data.is_active is not None:
        keyword.is_active = data.is_active
    if data.url is not None or data.source_type is not None:
        keyword.url = data.url or None
        keyword.source_type = data.source_type if data.url else "search"
    if data.group_name is not None:
        keyword.group_name = data.group_name if data.group_name.strip() else None
    if data.crawl_interval_hours is not None:
        keyword.crawl_interval_hours = data.crawl_interval_hours
    await db.flush()
    await db.refresh(keyword)
    return keyword


@router.delete("/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword(
    keyword_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    keyword = await _get_owned_keyword(keyword_id, current_user.id, db)
    await db.delete(keyword)


async def _get_owned_keyword(keyword_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> Keyword:
    result = await db.execute(
        select(Keyword).where(Keyword.id == keyword_id, Keyword.user_id == user_id)
    )
    kw = result.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return kw
