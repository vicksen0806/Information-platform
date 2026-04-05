"""Export router — Notion integration for digest export."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.digest import Digest
from app.models.user_notion_config import UserNotionConfig
from app.core.dependencies import get_current_user
from app.core.security import encrypt_api_key, decrypt_api_key, mask_api_key

router = APIRouter(tags=["export"])


# ── Notion config ─────────────────────────────────────────────────────────────

class NotionConfigCreate(BaseModel):
    notion_token: str | None = None  # None = keep existing
    database_id: str


class NotionConfigResponse(BaseModel):
    notion_token_masked: str
    database_id: str


@router.get("/settings/notion", response_model=NotionConfigResponse)
async def get_notion_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserNotionConfig).where(UserNotionConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Notion config not set")
    plain_token = decrypt_api_key(config.notion_token_enc)
    return NotionConfigResponse(
        notion_token_masked=mask_api_key(plain_token),
        database_id=config.database_id,
    )


@router.put("/settings/notion", response_model=NotionConfigResponse)
async def upsert_notion_config(
    data: NotionConfigCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserNotionConfig).where(UserNotionConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    if config:
        if data.notion_token:
            config.notion_token_enc = encrypt_api_key(data.notion_token)
        config.database_id = data.database_id
    else:
        if not data.notion_token:
            raise HTTPException(status_code=400, detail="notion_token required for first setup")
        config = UserNotionConfig(
            user_id=current_user.id,
            notion_token_enc=encrypt_api_key(data.notion_token),
            database_id=data.database_id,
        )
        db.add(config)
    await db.flush()
    plain_token = decrypt_api_key(config.notion_token_enc)
    await db.commit()
    return NotionConfigResponse(
        notion_token_masked=mask_api_key(plain_token),
        database_id=config.database_id,
    )


@router.delete("/settings/notion", status_code=204)
async def delete_notion_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserNotionConfig).where(UserNotionConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    if config:
        await db.delete(config)
        await db.commit()


# ── Export digest to Notion ───────────────────────────────────────────────────

@router.post("/digests/{digest_id}/export/notion")
async def export_digest_to_notion(
    digest_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Load digest
    result = await db.execute(
        select(Digest).where(Digest.id == digest_id, Digest.user_id == current_user.id)
    )
    digest = result.scalar_one_or_none()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")

    # Load Notion config
    result = await db.execute(
        select(UserNotionConfig).where(UserNotionConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=400, detail="Notion config not set. Configure in Settings.")

    notion_token = decrypt_api_key(config.notion_token_enc)
    import asyncio
    url = await asyncio.get_event_loop().run_in_executor(
        None, _create_notion_page, notion_token, config.database_id, digest
    )
    return {"url": url}


def _create_notion_page(token: str, database_id: str, digest) -> str:
    """Synchronously create a Notion page from a digest."""
    import requests

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    title = digest.title or "Info Platform Digest"
    keywords = digest.keywords_used or []
    summary_md = digest.summary_md or ""
    created_at = digest.created_at.isoformat() if digest.created_at else ""

    # Split summary into chunks (Notion API has 2000-char limit per block)
    chunks = [summary_md[i:i+1900] for i in range(0, len(summary_md), 1900)]

    children = [
        {
            "object": "block",
            "type": "code",
            "code": {
                "rich_text": [{"type": "text", "text": {"content": chunk}}],
                "language": "markdown",
            },
        }
        for chunk in chunks[:50]  # max 50 blocks
    ]

    payload = {
        "parent": {"database_id": database_id},
        "properties": {
            "Name": {
                "title": [{"type": "text", "text": {"content": title}}]
            },
        },
        "children": children,
    }

    resp = requests.post(
        "https://api.notion.com/v1/pages",
        json=payload,
        headers=headers,
        timeout=30,
    )

    if resp.status_code not in (200, 201):
        raise Exception(f"Notion API error {resp.status_code}: {resp.text[:200]}")

    return resp.json().get("url", "")
