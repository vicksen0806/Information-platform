import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, cast
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import String

from app.database import get_db
from app.models.user import User
from app.models.digest import Digest
from app.core.dependencies import get_current_user
from app.schemas.digest import DigestResponse, DigestUpdate, DigestListItem

router = APIRouter(prefix="/digests", tags=["digests"])


@router.get("", response_model=list[DigestListItem])
async def list_digests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
    q: str | None = Query(default=None, description="Full-text search query"),
):
    stmt = select(Digest).where(Digest.user_id == current_user.id)

    if q and q.strip():
        term = q.strip()
        # Full-text search via tsvector + keyword array ILIKE fallback
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


@router.get("/{digest_id}", response_model=DigestResponse)
async def get_digest(
    digest_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    digest = await _get_owned_digest(digest_id, current_user.id, db)
    # Auto-mark as read on open
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


async def _get_owned_digest(digest_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> Digest:
    result = await db.execute(
        select(Digest).where(Digest.id == digest_id, Digest.user_id == user_id)
    )
    digest = result.scalar_one_or_none()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")
    return digest
