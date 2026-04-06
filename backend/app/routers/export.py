"""Export router — Notion, PDF, EPUB integration for digest export."""
import uuid
import io
from fastapi import APIRouter, Depends, HTTPException, Response
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


# ── PDF export ─────────────────────────────────────────────────────────────────

@router.get("/digests/{digest_id}/export/pdf")
async def export_digest_pdf(
    digest_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Convert digest markdown to PDF via the Playwright microservice.
    Returns raw PDF bytes.
    """
    result = await db.execute(
        select(Digest).where(Digest.id == digest_id, Digest.user_id == current_user.id)
    )
    digest = result.scalar_one_or_none()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")

    import asyncio
    pdf_bytes = await asyncio.get_event_loop().run_in_executor(
        None, _render_pdf, digest
    )
    filename = f"digest-{digest.created_at.strftime('%Y%m%d')}.pdf" if digest.created_at else "digest.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _render_pdf(digest) -> bytes:
    """Build HTML from digest markdown and call Playwright /pdf."""
    import markdown as md_lib
    import requests as req
    from app.config import settings

    title = digest.title or "Info Platform Digest"
    body_md = digest.summary_md or ""
    body_html = md_lib.markdown(body_md, extensions=["tables", "fenced_code"])

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", sans-serif;
         font-size: 14px; line-height: 1.8; color: #222; padding: 10px; }}
  h1 {{ font-size: 20px; border-bottom: 2px solid #4f46e5; padding-bottom: 8px; color: #1e1b4b; }}
  h2 {{ font-size: 16px; color: #312e81; margin-top: 20px; }}
  h3 {{ font-size: 14px; color: #4338ca; }}
  a {{ color: #4f46e5; text-decoration: none; }}
  hr {{ border: none; border-top: 1px solid #e5e7eb; }}
  code {{ background: #f3f4f6; padding: 2px 4px; border-radius: 3px; font-size: 12px; }}
  pre {{ background: #f3f4f6; padding: 12px; border-radius: 6px; overflow-x: auto; }}
  .meta {{ color: #6b7280; font-size: 12px; margin-bottom: 16px; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="meta">Generated {digest.created_at.strftime('%Y-%m-%d %H:%M UTC') if digest.created_at else ''}</p>
{body_html}
</body>
</html>"""

    try:
        resp = req.post(
            f"{settings.PLAYWRIGHT_URL}/pdf",
            json={"html": html},
            timeout=(5, 60),
        )
        if resp.status_code == 200:
            return resp.content
    except Exception:
        pass

    # Fallback: return HTML as bytes if Playwright unavailable
    return html.encode("utf-8")


# ── EPUB export ────────────────────────────────────────────────────────────────

@router.get("/digests/{digest_id}/export/epub")
async def export_digest_epub(
    digest_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Convert digest to EPUB e-book format."""
    result = await db.execute(
        select(Digest).where(Digest.id == digest_id, Digest.user_id == current_user.id)
    )
    digest = result.scalar_one_or_none()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")

    import asyncio
    epub_bytes = await asyncio.get_event_loop().run_in_executor(
        None, _build_epub, digest
    )
    filename = f"digest-{digest.created_at.strftime('%Y%m%d')}.epub" if digest.created_at else "digest.epub"
    return Response(
        content=epub_bytes,
        media_type="application/epub+zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_epub(digest) -> bytes:
    """Build an EPUB from a digest using ebooklib."""
    import markdown as md_lib
    from ebooklib import epub

    title = digest.title or "Info Platform Digest"
    body_md = digest.summary_md or ""
    body_html = md_lib.markdown(body_md, extensions=["tables", "fenced_code"])
    keywords = digest.keywords_used or []

    book = epub.EpubBook()
    book.set_identifier(str(digest.id))
    book.set_title(title)
    book.set_language("zh")
    if keywords:
        book.add_metadata("DC", "subject", ", ".join(keywords))
    if digest.created_at:
        book.add_metadata("DC", "date", digest.created_at.strftime("%Y-%m-%d"))

    # CSS
    style = epub.EpubItem(
        uid="style",
        file_name="style.css",
        media_type="text/css",
        content="""
body { font-family: serif; font-size: 1em; line-height: 1.8; color: #222; margin: 2em; }
h1 { font-size: 1.4em; border-bottom: 1px solid #ccc; padding-bottom: 0.3em; }
h2 { font-size: 1.2em; }
h3 { font-size: 1.1em; }
a { color: #4f46e5; }
.meta { color: #888; font-size: 0.85em; }
""",
    )
    book.add_item(style)

    # Chapter
    created_str = digest.created_at.strftime("%Y-%m-%d") if digest.created_at else ""
    chapter = epub.EpubHtml(title=title, file_name="content.xhtml", lang="zh")
    chapter.content = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh">
<head><title>{title}</title>
<link rel="stylesheet" href="style.css" type="text/css"/>
</head>
<body>
<h1>{title}</h1>
<p class="meta">{created_str}</p>
{body_html}
</body>
</html>"""
    chapter.add_item(style)
    book.add_item(chapter)

    book.toc = (epub.Link("content.xhtml", title, "content"),)
    book.spine = ["nav", chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    buf = io.BytesIO()
    epub.write_epub(buf, book)
    return buf.getvalue()


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
