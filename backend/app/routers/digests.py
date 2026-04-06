import uuid
from datetime import timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, String, update
from pydantic import BaseModel

from app.database import get_db
from app.models.crawl_result import CrawlResult
from app.models.crawl_job import CrawlJob
from app.models.user import User
from app.models.digest import Digest
from app.models.digest_feedback import DigestFeedback
from app.models.digest_star import DigestStar
from app.core.dependencies import get_current_user
from app.schemas.digest import (
    DigestResponse,
    DigestUpdate,
    DigestListItem,
    UsageResponse,
    UsageMonthly,
    DigestKeywordCard,
    KeywordHistorySummary,
    KeywordHistoryEntry,
)

router = APIRouter(prefix="/digests", tags=["digests"])


class FeedbackCreate(BaseModel):
    value: str  # 'positive' | 'negative'


def _split_digest_keyword_sections(summary_md: str | None) -> dict[str, str]:
    if not summary_md:
        return {}

    sections: dict[str, list[str]] = {}
    current_keyword: str | None = None

    for raw_line in summary_md.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            current_keyword = line[3:].strip()
            sections.setdefault(current_keyword, [])
            continue
        if current_keyword is not None:
            sections[current_keyword].append(raw_line)

    return {
        keyword: "\n".join(lines).strip()
        for keyword, lines in sections.items()
        if keyword not in {"总结", "详细"}
    }


def _build_fallback_card_markdown(raw_content: str | None) -> str:
    if not raw_content:
        return "今日无可展示内容。"

    articles = [part.strip() for part in raw_content.split("\n\n---\n\n") if part.strip()]
    bullets: list[str] = []

    for article in articles[:6]:
        lines = [line.strip() for line in article.splitlines() if line.strip()]
        title = ""
        source_url = ""
        body_lines: list[str] = []

        for line in lines:
            if line.startswith("## "):
                title = line[3:].strip()
            elif line.startswith("Source: "):
                source_url = line[len("Source: "):].strip()
            else:
                body_lines.append(line)

        summary = " ".join(body_lines).strip()
        if len(summary) > 160:
            summary = summary[:160].rstrip() + "..."

        bullet = "- "
        if title:
            bullet += f"**{title}**"
        else:
            bullet += "**抓取内容**"

        if summary:
            bullet += f"：{summary}"
        if source_url:
            bullet += f" ([来源]({source_url}))"

        bullets.append(bullet)

    return "\n".join(bullets) if bullets else "今日无可展示内容。"


def _article_count_from_raw_content(raw_content: str | None) -> int:
    if not raw_content:
        return 0
    count = raw_content.count("\n## ")
    if raw_content.startswith("## "):
        count += 1
    return count


async def _build_keyword_cards(db: AsyncSession, digest: Digest) -> list[DigestKeywordCard]:
    result = await db.execute(
        select(CrawlResult.keyword_text, CrawlResult.crawled_at, CrawlResult.raw_content)
        .where(
            CrawlResult.crawl_job_id == digest.crawl_job_id,
            CrawlResult.raw_content.isnot(None),
        )
        .order_by(CrawlResult.crawled_at.asc())
    )
    crawl_rows = result.all()
    crawl_map = {
        row.keyword_text: {"crawled_at": row.crawled_at, "raw_content": row.raw_content}
        for row in crawl_rows
        if row.keyword_text
    }
    sections = _split_digest_keyword_sections(digest.summary_md)

    ordered_keywords: list[str] = []
    for keyword in (digest.keywords_used or []):
        if keyword not in ordered_keywords:
            ordered_keywords.append(keyword)
    for keyword in sections:
        if keyword not in ordered_keywords:
            ordered_keywords.append(keyword)
    for keyword in crawl_map:
        if keyword not in ordered_keywords:
            ordered_keywords.append(keyword)

    cards: list[DigestKeywordCard] = []
    for keyword in ordered_keywords:
        body = sections.get(keyword, "").strip()
        crawl_info = crawl_map.get(keyword)

        if crawl_info is None:
            fallback_result = await db.execute(
                select(CrawlResult.crawled_at, CrawlResult.raw_content)
                .join(CrawlJob, CrawlJob.id == CrawlResult.crawl_job_id)
                .where(
                    CrawlJob.user_id == digest.user_id,
                    CrawlResult.keyword_text == keyword,
                    CrawlResult.raw_content.isnot(None),
                )
                .order_by(CrawlResult.crawled_at.desc())
                .limit(1)
            )
            fallback_row = fallback_result.first()
            if fallback_row:
                crawl_info = {
                    "crawled_at": fallback_row.crawled_at,
                    "raw_content": fallback_row.raw_content,
                }

        if not body and crawl_info is not None:
            body = _build_fallback_card_markdown(crawl_info["raw_content"])
        if not body:
            continue
        cards.append(
            DigestKeywordCard(
                keyword=keyword,
                summary_md=body,
                crawl_date=crawl_info.get("crawled_at") if crawl_info else None,
            )
        )
    return cards


@router.get("/keywords", response_model=list[KeywordHistorySummary])
async def list_keyword_history_summaries(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    q: str | None = Query(default=None, description="Search keyword text"),
):
    stmt = (
        select(CrawlResult.keyword_text, CrawlResult.crawled_at)
        .join(CrawlJob, CrawlJob.id == CrawlResult.crawl_job_id)
        .where(
            CrawlJob.user_id == current_user.id,
            CrawlResult.keyword_text.isnot(None),
        )
        .order_by(CrawlResult.crawled_at.desc())
    )
    if q and q.strip():
        stmt = stmt.where(CrawlResult.keyword_text.ilike(f"%{q.strip()}%"))

    rows = (await db.execute(stmt)).all()
    summaries: dict[str, KeywordHistorySummary] = {}
    seen_days: dict[str, set[str]] = {}

    for row in rows:
        keyword = (row.keyword_text or "").strip()
        if not keyword:
            continue
        day_key = row.crawled_at.astimezone(timezone.utc).date().isoformat()
        if keyword not in summaries:
            summaries[keyword] = KeywordHistorySummary(
                keyword=keyword,
                latest_crawled_at=row.crawled_at,
                total_days=0,
            )
            seen_days[keyword] = set()
        if day_key not in seen_days[keyword]:
            seen_days[keyword].add(day_key)
            summaries[keyword].total_days += 1

    return sorted(
        summaries.values(),
        key=lambda item: item.latest_crawled_at.timestamp() if item.latest_crawled_at else 0,
        reverse=True,
    )


@router.get("/keywords/{keyword}/history", response_model=list[KeywordHistoryEntry])
async def get_keyword_history(
    keyword: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=30, ge=1, le=180),
):
    stmt = (
        select(
            CrawlResult.crawl_job_id,
            CrawlResult.crawled_at,
            CrawlResult.raw_content,
            Digest.id.label("digest_id"),
            Digest.title,
            Digest.summary_md,
        )
        .join(CrawlJob, CrawlJob.id == CrawlResult.crawl_job_id)
        .outerjoin(Digest, Digest.crawl_job_id == CrawlResult.crawl_job_id)
        .where(
            CrawlJob.user_id == current_user.id,
            CrawlResult.keyword_text == keyword,
        )
        .order_by(CrawlResult.crawled_at.desc())
    )
    rows = (await db.execute(stmt)).all()

    entries: list[KeywordHistoryEntry] = []
    seen_days: set[str] = set()
    for row in rows:
        day = row.crawled_at.astimezone(timezone.utc).date()
        day_key = day.isoformat()
        if day_key in seen_days:
            continue
        seen_days.add(day_key)

        sections = _split_digest_keyword_sections(row.summary_md)
        body = sections.get(keyword, "").strip()
        if not body:
            body = _build_fallback_card_markdown(row.raw_content)

        entries.append(
            KeywordHistoryEntry(
                keyword=keyword,
                crawl_date=day,
                crawled_at=row.crawled_at,
                summary_md=body,
                article_count=_article_count_from_raw_content(row.raw_content),
                digest_id=row.digest_id,
                title=row.title,
            )
        )
        if len(entries) >= limit:
            break

    return entries


# ── Semantic search ───────────────────────────────────────────────────────────

@router.get("/search/semantic", response_model=list[DigestListItem])
async def semantic_search(
    q: str = Query(..., description="Natural language search query"),
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Vector similarity search across digests using the user's embedding model.
    Falls back to text search if embedding model is not configured or no embeddings exist.
    """
    from app.models.user_llm_config import UserLlmConfig
    from sqlalchemy import text

    llm_cfg = (await db.execute(
        select(UserLlmConfig).where(UserLlmConfig.user_id == current_user.id)
    )).scalar_one_or_none()

    query_vec = None
    if llm_cfg and getattr(llm_cfg, "embedding_model", None):
        import asyncio
        from app.services.llm_service import generate_embedding_sync
        query_vec = await asyncio.get_event_loop().run_in_executor(
            None, generate_embedding_sync, llm_cfg, q
        )

    if query_vec:
        # Use pgvector cosine similarity via raw SQL
        try:
            from sqlalchemy import text as sql_text
            vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
            raw = await db.execute(
                sql_text(
                    "SELECT id FROM digests "
                    "WHERE user_id = :uid AND embedding IS NOT NULL "
                    "ORDER BY embedding <=> :vec::vector "
                    "LIMIT :lim"
                ),
                {"uid": str(current_user.id), "vec": vec_str, "lim": limit},
            )
            ids = [row[0] for row in raw]
            if ids:
                stmt = select(Digest).where(Digest.id.in_(ids))
                result = await db.execute(stmt)
                digests = result.scalars().all()
                # Re-sort by original cosine order
                id_order = {digest_id: idx for idx, digest_id in enumerate(ids)}
                digests = sorted(digests, key=lambda d: id_order.get(d.id, 999))
                return await _attach_digest_meta(db, digests, current_user.id)
        except Exception:
            pass  # Fall through to text search

    # Fall back to trigram / FTS text search
    from app.config import settings as _s
    ts_config = getattr(_s, "FTS_CONFIG", "simple")
    fts = func.to_tsvector(ts_config, func.coalesce(Digest.title, "") + " " + func.coalesce(Digest.summary_md, ""))
    tsq = func.plainto_tsquery(ts_config, q)
    stmt = (
        select(Digest)
        .where(
            Digest.user_id == current_user.id,
            or_(
                fts.op("@@")(tsq),
                Digest.title.ilike(f"%{q}%"),
            ),
        )
        .order_by(Digest.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    digests = result.scalars().all()
    return await _attach_digest_meta(db, digests, current_user.id)


# ── Timeline ──────────────────────────────────────────────────────────────────

@router.get("/timeline")
async def digest_timeline(
    keyword: str = Query(..., description="Filter by keyword"),
    days: int = Query(default=90, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return digests containing a keyword, grouped by date, for timeline display.
    """
    from datetime import datetime, timedelta, timezone
    since = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = (
        select(Digest.id, Digest.title, Digest.created_at, Digest.importance_score, Digest.is_read)
        .where(
            Digest.user_id == current_user.id,
            Digest.keywords_used.contains([keyword]),
            Digest.created_at >= since,
        )
        .order_by(Digest.created_at.asc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    # Group by date
    from collections import defaultdict
    grouped: dict[str, list] = defaultdict(list)
    for row in rows:
        date_str = row.created_at.strftime("%Y-%m-%d")
        grouped[date_str].append({
            "id": str(row.id),
            "title": row.title,
            "created_at": row.created_at.isoformat(),
            "importance_score": row.importance_score,
            "is_read": row.is_read,
        })

    return [
        {"date": date, "digests": items}
        for date, items in sorted(grouped.items())
    ]


async def _attach_digest_meta(db: AsyncSession, digests, user_id) -> list:
    """Attach feedback and star info to a list of Digest ORM objects."""
    if not digests:
        return []
    digest_ids = [d.id for d in digests]
    fb_result = await db.execute(
        select(DigestFeedback.digest_id, DigestFeedback.value)
        .where(DigestFeedback.user_id == user_id, DigestFeedback.digest_id.in_(digest_ids))
    )
    fb_map = {row.digest_id: row.value for row in fb_result}
    star_result = await db.execute(
        select(DigestStar.digest_id)
        .where(DigestStar.user_id == user_id, DigestStar.digest_id.in_(digest_ids))
    )
    starred = {row.digest_id for row in star_result}

    items = []
    for d in digests:
        items.append(DigestListItem(
            id=d.id,
            title=d.title,
            keywords_used=d.keywords_used,
            sources_count=d.sources_count,
            is_read=d.is_read,
            created_at=d.created_at,
            feedback=fb_map.get(d.id),
            is_starred=d.id in starred,
            importance_score=d.importance_score,
        ))
    return items


@router.get("", response_model=list[DigestListItem])
async def list_digests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
    q: str | None = Query(default=None, description="Full-text search query"),
    keyword: str | None = Query(default=None, description="Filter by keyword name"),
):
    stmt = select(Digest).where(Digest.user_id == current_user.id)

    if keyword and keyword.strip():
        # Filter digests where keywords_used array contains the given keyword
        from sqlalchemy.dialects.postgresql import ARRAY
        stmt = stmt.where(Digest.keywords_used.contains([keyword.strip()]))

    if q and q.strip():
        term = q.strip()
        # Use jieba_cfg if pg_jieba is installed, otherwise fall back to simple
        from app.config import settings as _s
        ts_config = getattr(_s, "FTS_CONFIG", "simple")
        fts = func.to_tsvector(ts_config, func.coalesce(Digest.title, "") + " " + func.coalesce(Digest.summary_md, ""))
        tsq = func.plainto_tsquery(ts_config, term)
        stmt = stmt.where(
            or_(
                fts.op("@@")(tsq),
                Digest.title.ilike(f"%{term}%"),
                func.cast(Digest.keywords_used, String).ilike(f"%{term}%"),
            )
        )

    stmt = stmt.order_by(Digest.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    digests = result.scalars().all()

    # Attach user's feedback for each digest
    if digests:
        digest_ids = [d.id for d in digests]
        fb_result = await db.execute(
            select(DigestFeedback.digest_id, DigestFeedback.value).where(
                DigestFeedback.digest_id.in_(digest_ids),
                DigestFeedback.user_id == current_user.id,
            )
        )
        fb_map = {row[0]: row[1] for row in fb_result.all()}

        star_result = await db.execute(
            select(DigestStar.digest_id).where(
                DigestStar.digest_id.in_(digest_ids),
                DigestStar.user_id == current_user.id,
            )
        )
        starred_ids = {row[0] for row in star_result.all()}

        items = []
        for d in digests:
            item = DigestListItem.model_validate(d)
            item.feedback = fb_map.get(d.id)
            item.is_starred = d.id in starred_ids
            items.append(item)
        return items

    return []


@router.post("/mark-all-read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark every unread digest as read for the current user."""
    await db.execute(
        update(Digest)
        .where(Digest.user_id == current_user.id, Digest.is_read == False)
        .values(is_read=True)
    )


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return token usage statistics for the current user."""
    from datetime import datetime, timezone
    from sqlalchemy import func as sqlfunc

    # Total stats
    total_row = await db.execute(
        select(
            sqlfunc.coalesce(sqlfunc.sum(Digest.tokens_used), 0),
            sqlfunc.count(Digest.id),
        ).where(Digest.user_id == current_user.id)
    )
    total_tokens, total_digests = total_row.one()

    # This month
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_row = await db.execute(
        select(
            sqlfunc.coalesce(sqlfunc.sum(Digest.tokens_used), 0),
            sqlfunc.count(Digest.id),
        ).where(Digest.user_id == current_user.id, Digest.created_at >= month_start)
    )
    this_month_tokens, this_month_digests = month_row.one()

    # Monthly breakdown (last 12 months)
    monthly_rows = await db.execute(
        select(
            sqlfunc.to_char(Digest.created_at, "YYYY-MM").label("month"),
            sqlfunc.coalesce(sqlfunc.sum(Digest.tokens_used), 0).label("tokens"),
            sqlfunc.count(Digest.id).label("digests"),
        )
        .where(Digest.user_id == current_user.id)
        .group_by("month")
        .order_by("month")
        .limit(12)
    )
    monthly = [
        UsageMonthly(month=row.month, tokens=int(row.tokens), digests=int(row.digests))
        for row in monthly_rows
    ]

    return UsageResponse(
        total_tokens=int(total_tokens),
        total_digests=int(total_digests),
        this_month_tokens=int(this_month_tokens),
        this_month_digests=int(this_month_digests),
        monthly=monthly,
    )


@router.get("/{digest_id}", response_model=DigestResponse)
async def get_digest(
    digest_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    digest = await _get_owned_digest(digest_id, current_user.id, db)
    if not digest.is_read:
        digest.is_read = True
        await db.flush()
    # Attach feedback
    fb_result = await db.execute(
        select(DigestFeedback.value).where(
            DigestFeedback.digest_id == digest_id,
            DigestFeedback.user_id == current_user.id,
        )
    )
    fb_row = fb_result.scalar_one_or_none()
    star_result = await db.execute(
        select(DigestStar).where(
            DigestStar.digest_id == digest_id,
            DigestStar.user_id == current_user.id,
        )
    )
    is_starred = star_result.scalar_one_or_none() is not None
    response = DigestResponse.model_validate(digest)
    response.feedback = fb_row
    response.is_starred = is_starred
    response.keyword_cards = await _build_keyword_cards(db, digest)
    return response


@router.patch("/{digest_id}", response_model=DigestResponse)
async def update_digest(
    digest_id: uuid.UUID,
    data: DigestUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    digest = await _get_owned_digest(digest_id, current_user.id, db)
    if data.is_read is not None:
        digest.is_read = data.is_read
    await db.flush()
    await db.refresh(digest)
    return digest


@router.delete("/{digest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_digest(
    digest_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    digest = await _get_owned_digest(digest_id, current_user.id, db)
    await db.delete(digest)


@router.post("/{digest_id}/regenerate", response_model=DigestResponse)
async def regenerate_digest(
    digest_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    digest = await _get_owned_digest(digest_id, current_user.id, db)
    from app.tasks.digest_tasks import generate_digest
    generate_digest.delay(str(digest.crawl_job_id), str(current_user.id))
    return digest


@router.post("/{digest_id}/share", response_model=DigestResponse)
async def share_digest(
    digest_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a public share token for this digest. Idempotent — returns existing token if already shared."""
    import secrets
    digest = await _get_owned_digest(digest_id, current_user.id, db)
    if not digest.share_token:
        digest.share_token = secrets.token_urlsafe(32)
        await db.flush()
    await db.refresh(digest)
    return digest


@router.delete("/{digest_id}/share", response_model=DigestResponse)
async def unshare_digest(
    digest_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke the public share link."""
    digest = await _get_owned_digest(digest_id, current_user.id, db)
    digest.share_token = None
    await db.flush()
    await db.refresh(digest)
    return digest


@router.put("/{digest_id}/feedback", response_model=DigestResponse)
async def set_feedback(
    digest_id: uuid.UUID,
    data: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upsert thumbs up/down feedback for a digest."""
    if data.value not in ("positive", "negative"):
        raise HTTPException(status_code=400, detail="value must be 'positive' or 'negative'")
    digest = await _get_owned_digest(digest_id, current_user.id, db)

    fb_result = await db.execute(
        select(DigestFeedback).where(
            DigestFeedback.digest_id == digest_id,
            DigestFeedback.user_id == current_user.id,
        )
    )
    fb = fb_result.scalar_one_or_none()
    if fb:
        fb.value = data.value
    else:
        fb = DigestFeedback(digest_id=digest_id, user_id=current_user.id, value=data.value)
        db.add(fb)
    await db.flush()

    response = DigestResponse.model_validate(digest)
    response.feedback = data.value
    return response


@router.post("/{digest_id}/star", response_model=DigestResponse)
async def star_digest(
    digest_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Star a digest. Idempotent."""
    digest = await _get_owned_digest(digest_id, current_user.id, db)
    existing = await db.execute(
        select(DigestStar).where(
            DigestStar.digest_id == digest_id,
            DigestStar.user_id == current_user.id,
        )
    )
    if not existing.scalar_one_or_none():
        db.add(DigestStar(digest_id=digest_id, user_id=current_user.id))
        await db.flush()
    response = DigestResponse.model_validate(digest)
    response.is_starred = True
    return response


@router.delete("/{digest_id}/star", response_model=DigestResponse)
async def unstar_digest(
    digest_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove star from a digest."""
    digest = await _get_owned_digest(digest_id, current_user.id, db)
    existing = await db.execute(
        select(DigestStar).where(
            DigestStar.digest_id == digest_id,
            DigestStar.user_id == current_user.id,
        )
    )
    star = existing.scalar_one_or_none()
    if star:
        await db.delete(star)
        await db.flush()
    response = DigestResponse.model_validate(digest)
    response.is_starred = False
    return response


@router.delete("/{digest_id}/feedback", response_model=DigestResponse)
async def delete_feedback(
    digest_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove feedback for a digest."""
    digest = await _get_owned_digest(digest_id, current_user.id, db)
    fb_result = await db.execute(
        select(DigestFeedback).where(
            DigestFeedback.digest_id == digest_id,
            DigestFeedback.user_id == current_user.id,
        )
    )
    fb = fb_result.scalar_one_or_none()
    if fb:
        await db.delete(fb)
    await db.flush()
    response = DigestResponse.model_validate(digest)
    response.feedback = None
    return response


async def _get_owned_digest(digest_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> Digest:
    result = await db.execute(
        select(Digest).where(Digest.id == digest_id, Digest.user_id == user_id)
    )
    digest = result.scalar_one_or_none()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")
    return digest
