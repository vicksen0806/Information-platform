import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, cast, String, update
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.digest import Digest
from app.models.digest_feedback import DigestFeedback
from app.models.digest_star import DigestStar
from app.core.dependencies import get_current_user
from app.schemas.digest import DigestResponse, DigestUpdate, DigestListItem, UsageResponse, UsageMonthly

router = APIRouter(prefix="/digests", tags=["digests"])


class FeedbackCreate(BaseModel):
    value: str  # 'positive' | 'negative'


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
        fts = func.to_tsvector("simple", func.coalesce(Digest.title, "") + " " + func.coalesce(Digest.summary_md, ""))
        tsq = func.plainto_tsquery("simple", term)
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
