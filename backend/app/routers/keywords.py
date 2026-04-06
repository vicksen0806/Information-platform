import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
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


@router.get("/article-stats")
async def get_article_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Per-keyword article counts (actual articles, not crawl runs) grouped by day (last 30 days)."""
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import func, cast, Date, text
    from app.models.crawl_result import CrawlResult
    from app.models.crawl_job import CrawlJob

    since = datetime.now(timezone.utc) - timedelta(days=30)
    # regexp_count counts "## " section headings which each represent one article
    rows = await db.execute(
        select(
            CrawlResult.keyword_text,
            cast(CrawlResult.crawled_at, Date).label("day"),
            func.sum(
                func.regexp_count(func.coalesce(CrawlResult.raw_content, ""), "## ")
            ).label("cnt"),
        )
        .join(CrawlJob, CrawlResult.crawl_job_id == CrawlJob.id)
        .where(
            CrawlJob.user_id == current_user.id,
            CrawlResult.crawled_at >= since,
            CrawlResult.keyword_text.isnot(None),
        )
        .group_by(CrawlResult.keyword_text, "day")
        .order_by(CrawlResult.keyword_text, "day")
    )
    stats: dict[str, list[dict]] = {}
    for kw, day, cnt in rows.all():
        if kw not in stats:
            stats[kw] = []
        stats[kw].append({"day": str(day), "count": int(cnt or 0)})
    return stats


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


@router.post("/recommend")
async def recommend_keywords(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Use LLM to suggest new keywords based on the user's recently used keywords.
    Returns [{text, reason}] — up to 10 suggestions.
    """
    from datetime import datetime, timezone, timedelta
    from app.models.crawl_job import CrawlJob
    from app.models.crawl_result import CrawlResult
    from app.models.user_llm_config import UserLlmConfig
    from app.services.llm_service import recommend_keywords_sync

    llm_cfg = (await db.execute(
        select(UserLlmConfig).where(UserLlmConfig.user_id == current_user.id)
    )).scalar_one_or_none()
    if not llm_cfg:
        raise HTTPException(status_code=400, detail="LLM config not set")

    kw_result = await db.execute(
        select(Keyword.text).where(Keyword.user_id == current_user.id, Keyword.is_active == True)
    )
    active_keywords = [row[0] for row in kw_result.all()]

    since = datetime.now(timezone.utc) - timedelta(days=15)
    recent_result = await db.execute(
        select(CrawlResult.keyword_text, CrawlResult.crawled_at)
        .join(CrawlJob, CrawlJob.id == CrawlResult.crawl_job_id)
        .where(
            CrawlJob.user_id == current_user.id,
            CrawlResult.keyword_text.isnot(None),
            CrawlResult.crawled_at >= since,
        )
        .order_by(CrawlResult.crawled_at.desc())
    )

    seen: set[str] = set()
    recent_keywords: list[str] = []
    for keyword_text, _ in recent_result.all():
        if not keyword_text or keyword_text in seen:
            continue
        seen.add(keyword_text)
        recent_keywords.append(keyword_text)

    for keyword_text in active_keywords:
        if keyword_text not in seen:
            seen.add(keyword_text)
            recent_keywords.append(keyword_text)

    import asyncio
    suggestions = await asyncio.get_event_loop().run_in_executor(
        None, recommend_keywords_sync, llm_cfg, recent_keywords, active_keywords
    )
    return suggestions


@router.get("/export")
async def export_keywords(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export all keywords as a JSON array."""
    result = await db.execute(select(Keyword).where(Keyword.user_id == current_user.id).order_by(Keyword.created_at))
    keywords = result.scalars().all()
    return [
        {
            "text": kw.text,
            "url": kw.url,
            "source_type": kw.source_type,
            "group_name": kw.group_name,
            "crawl_interval_hours": kw.crawl_interval_hours,
            "is_active": kw.is_active,
        }
        for kw in keywords
    ]


class KeywordImportItem(BaseModel):
    text: str
    url: str | None = None
    source_type: str = "search"
    group_name: str | None = None
    crawl_interval_hours: int = 24
    is_active: bool = True


@router.post("/import")
async def import_keywords(
    data: list[KeywordImportItem],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Import keywords from JSON array. Skips duplicates (by text). Returns counts."""
    existing_result = await db.execute(
        select(Keyword.text).where(Keyword.user_id == current_user.id)
    )
    existing_texts = {row[0] for row in existing_result.all()}

    count_result = await db.execute(select(Keyword).where(Keyword.user_id == current_user.id))
    current_count = len(count_result.scalars().all())

    added = 0
    skipped = 0
    for item in data:
        if item.text in existing_texts:
            skipped += 1
            continue
        if current_count >= MAX_KEYWORDS_PER_USER:
            skipped += len(data) - added - skipped
            break
        kw = Keyword(
            user_id=current_user.id,
            text=item.text,
            url=item.url or None,
            source_type=item.source_type if item.url else "search",
            group_name=item.group_name or None,
            crawl_interval_hours=item.crawl_interval_hours,
            is_active=item.is_active,
        )
        db.add(kw)
        existing_texts.add(item.text)
        current_count += 1
        added += 1

    await db.flush()
    return {"added": added, "skipped": skipped}


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
        requires_js=data.requires_js,
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
    if data.requires_js is not None:
        keyword.requires_js = data.requires_js
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
