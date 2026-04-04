"""Public (no-auth) endpoints — share links."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.digest import Digest
from app.schemas.digest import DigestResponse

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/digests/{token}", response_model=DigestResponse)
async def get_shared_digest(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch a digest by its share token — no authentication required."""
    result = await db.execute(
        select(Digest).where(Digest.share_token == token)
    )
    digest = result.scalar_one_or_none()
    if not digest:
        raise HTTPException(status_code=404, detail="Shared digest not found or link has been revoked")
    return digest
