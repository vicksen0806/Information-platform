"""Public (no-auth) endpoints — share links and RSS feed."""
import hmac
import hashlib
import uuid
from email.utils import formatdate
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.digest import Digest
from app.models.user import User
from app.schemas.digest import DigestResponse

router = APIRouter(prefix="/public", tags=["public"])


def _verify_feed_token(token: str) -> uuid.UUID | None:
    """Return user_id if token is valid, else None."""
    if len(token) != 48:
        return None
    try:
        user_id = uuid.UUID(token[:32])
        expected_sig = hmac.new(settings.SECRET_KEY.encode(), user_id.bytes, hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(token[32:], expected_sig):
            return None
        return user_id
    except Exception:
        return None


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


@router.get("/feed/{token}.rss")
async def get_rss_feed(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """RSS 2.0 feed for a user's digest history. Token is HMAC-authenticated."""
    user_id = _verify_feed_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid feed token")

    user_result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    digest_result = await db.execute(
        select(Digest)
        .where(Digest.user_id == user_id)
        .order_by(Digest.created_at.desc())
        .limit(20)
    )
    digests = digest_result.scalars().all()

    def _escape(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    items_xml = ""
    for d in digests:
        title = _escape(d.title or "Digest")
        pub_date = formatdate(d.created_at.timestamp(), usegmt=True)
        guid = str(d.id)
        kws = ", ".join(d.keywords_used or [])
        description = _escape(f"Keywords: {kws}" if kws else "Info Platform Digest")
        summary = d.summary_md or ""
        # Wrap in CDATA so Markdown isn't double-escaped
        cdata_content = summary.replace("]]>", "]]]]><![CDATA[>")
        items_xml += (
            f"  <item>\n"
            f"    <title>{title}</title>\n"
            f"    <description><![CDATA[{cdata_content}]]></description>\n"
            f"    <pubDate>{pub_date}</pubDate>\n"
            f"    <guid isPermaLink=\"false\">{guid}</guid>\n"
            f"  </item>\n"
        )

    last_build = formatdate(digests[0].created_at.timestamp(), usegmt=True) if digests else formatdate(usegmt=True)
    rss_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        '  <channel>\n'
        f'    <title>Info Platform — {_escape(user.email)}</title>\n'
        f'    <link>/</link>\n'
        f'    <description>Daily digest for {_escape(user.email)}</description>\n'
        f'    <lastBuildDate>{last_build}</lastBuildDate>\n'
        f'{items_xml}'
        '  </channel>\n'
        '</rss>\n'
    )
    return Response(content=rss_xml, media_type="application/rss+xml; charset=utf-8")
