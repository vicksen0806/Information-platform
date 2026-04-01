import uuid
from fastapi import APIRouter, Depends, HTTPException, status
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Keyword).where(Keyword.user_id == current_user.id).order_by(Keyword.created_at.asc())
    )
    return result.scalars().all()


@router.post("", response_model=KeywordResponse, status_code=status.HTTP_201_CREATED)
async def create_keyword(
    data: KeywordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count_result = await db.execute(select(Keyword).where(Keyword.user_id == current_user.id))
    if len(count_result.scalars().all()) >= MAX_KEYWORDS_PER_USER:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_KEYWORDS_PER_USER} keywords allowed")

    keyword = Keyword(user_id=current_user.id, text=data.text)
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
    keyword.is_active = data.is_active
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
