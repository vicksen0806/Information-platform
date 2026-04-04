import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, cast, String

from app.database import get_db
from app.models.user import User
from app.models.digest import Digest
from app.core.dependencies import get_current_user
from app.schemas.digest import DigestResponse, DigestUpdate, DigestListItem, UsageResponse, UsageMonthly

router = APIRouter(prefix="/digests", tags=["digests"])


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
    return result.scalars().all()


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
    return digest


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


async def _get_owned_digest(digest_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> Digest:
    result = await db.execute(
        select(Digest).where(Digest.id == digest_id, Digest.user_id == user_id)
    )
    digest = result.scalar_one_or_none()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")
    return digest
