"""Public (no-auth) endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.digest import Digest
from app.routers.digests import _build_keyword_cards
from app.schemas.digest import DigestResponse
from app.services.text_service import normalize_markdown_source_links

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
    response = DigestResponse.model_validate(digest)
    response.keyword_cards = await _build_keyword_cards(db, digest)
    response.summary_md = normalize_markdown_source_links(response.summary_md)
    if response.keyword_cards:
        for card in response.keyword_cards:
            card.summary_md = normalize_markdown_source_links(card.summary_md) or card.summary_md
    return response
