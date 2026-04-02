import hashlib
import re
import asyncio
from typing import Optional

import requests
import feedparser
from bs4 import BeautifulSoup

from app.schemas.source import SourceTestResult

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

TIMEOUT = 15  # seconds


def _extract_text_from_html(html: str) -> str:
    """Strip HTML to clean plain text."""
    soup = BeautifulSoup(html, "lxml")
    # Remove script, style, nav, footer, header tags
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    # Collapse multiple blank lines
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned


def _extract_rss_content(url: str) -> tuple[str, int | None]:
    """Parse RSS/Atom feed and return concatenated entry summaries."""
    feed = feedparser.parse(url)
    entries = []
    for entry in feed.entries[:20]:  # Max 20 entries
        title = entry.get("title", "")
        summary = entry.get("summary", "") or entry.get("description", "")
        # Strip HTML from summary
        if summary:
            summary = BeautifulSoup(summary, "lxml").get_text()
        link = entry.get("link", "")
        entries.append(f"【{title}】\n{summary}\n链接：{link}")

    content = "\n\n---\n\n".join(entries)
    return content, 200


def _fetch_webpage(url: str) -> tuple[str, int]:
    """Fetch a regular webpage and extract text."""
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    text = _extract_text_from_html(resp.text)
    return text, resp.status_code


def fetch_url_sync(url: str, source_type: str) -> tuple[str | None, int | None, str | None]:
    """
    Returns (content, http_status, error_message).
    Runs synchronously (called from Celery worker thread).
    """
    try:
        if source_type in ("rss", "search"):
            content, status = _extract_rss_content(url)
        else:
            content, status = _fetch_webpage(url)
        return content, status, None
    except requests.exceptions.Timeout:
        return None, None, "Request timed out"
    except requests.exceptions.ConnectionError as e:
        return None, None, f"Connection error: {str(e)[:200]}"
    except Exception as e:
        return None, None, f"Error: {str(e)[:200]}"


async def fetch_and_extract(url: str, source_type: str, preview_only: bool = False) -> SourceTestResult:
    """Async wrapper around the sync fetch (runs in thread pool)."""
    loop = asyncio.get_event_loop()
    content, http_status, error = await loop.run_in_executor(
        None, fetch_url_sync, url, source_type
    )

    if error:
        return SourceTestResult(success=False, error=error)

    preview = None
    if content and preview_only:
        preview = content[:500]

    return SourceTestResult(
        success=True,
        http_status=http_status,
        content_preview=preview,
    )


def compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
