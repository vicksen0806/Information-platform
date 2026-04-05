"""
Crawler service — production-grade fetching and content extraction.

Key improvements over v1:
- RSS: follows each article link to extract full text (not just feed summaries)
- Webpage: uses Mozilla readability algorithm for clean main-content extraction
- User-Agent rotation across a pool of realistic browser strings
- Session-level automatic retry with exponential backoff (429/5xx)
- Per-domain rate limiting (≥1s between requests to same domain)
- Separate connect/read timeouts
- Skips social media and other unscrapable domains gracefully
"""
import hashlib
import time
import random
import asyncio
import threading
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import feedparser
from bs4 import BeautifulSoup
from readability import Document

from app.schemas.source import SourceTestResult

# ── Constants ──────────────────────────────────────────────────────────────────

CONNECT_TIMEOUT = 8    # seconds to establish TCP connection
READ_TIMEOUT = 25      # seconds to receive full response
MAX_ARTICLE_CHARS = 3000   # max chars kept per individual article
MAX_ARTICLES_PER_FEED = 12  # max articles fetched per RSS feed

# Domains that block scrapers or return nothing useful
_SKIP_DOMAINS = {
    "twitter.com", "x.com", "facebook.com", "instagram.com",
    "linkedin.com", "tiktok.com", "youtube.com", "youtu.be",
    "reddit.com", "pinterest.com", "snapchat.com",
}

# Per-domain rate limiting state
_domain_last_request: dict[str, float] = {}
_rate_lock = threading.Lock()

# ── User-Agent pool ────────────────────────────────────────────────────────────

_USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Firefox Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Safari Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


def _get_headers(referer: str = "") -> dict:
    """Return a realistic browser header set with a random User-Agent."""
    headers = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }
    if referer:
        headers["Referer"] = referer
    return headers


# ── Session factory ────────────────────────────────────────────────────────────

def _make_session() -> requests.Session:
    """Create a session with retry on transient server errors and rate limits."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.5,           # waits: 0s, 1.5s, 3s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ── Rate limiting ──────────────────────────────────────────────────────────────

def _rate_limit(domain: str, min_gap: float = 1.0):
    """Ensure at least min_gap seconds between requests to the same domain."""
    with _rate_lock:
        last = _domain_last_request.get(domain, 0)
        wait = min_gap - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        _domain_last_request[domain] = time.time()


def _domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return url


def _should_skip(url: str) -> bool:
    return _domain_of(url) in _SKIP_DOMAINS


# ── Content extraction ─────────────────────────────────────────────────────────

def _extract_with_readability(html: str, url: str = "") -> str:
    """
    Use Mozilla's readability algorithm to isolate the main article body.
    Falls back to basic BeautifulSoup extraction if readability fails.
    """
    try:
        doc = Document(html)
        title = (doc.title() or "").strip()
        content_html = doc.summary(html_partial=True)
        soup = BeautifulSoup(content_html, "lxml")
        lines = [l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip()]
        body = "\n".join(lines)

        # Reject readability output that looks like boilerplate (too short)
        if len(body) < 100:
            return _extract_basic(html)

        full = f"{title}\n\n{body}" if title else body
        return full[:MAX_ARTICLE_CHARS]
    except Exception:
        return _extract_basic(html)


def _extract_basic(html: str) -> str:
    """Fallback: strip noise tags, return raw text."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "form"]):
        tag.decompose()
    lines = [l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip()]
    return "\n".join(lines)[:MAX_ARTICLE_CHARS]


# ── Article fetcher ────────────────────────────────────────────────────────────

def _fetch_article_js(url: str) -> tuple[str, str] | None:
    """
    Fetch a JS-rendered article via the Playwright microservice.
    Returns (clean_text, url) or None on failure.
    """
    from app.config import settings
    try:
        resp = requests.post(
            f"{settings.PLAYWRIGHT_URL}/render",
            json={"url": url},
            timeout=(5, 30),
        )
        if resp.status_code != 200:
            return None
        html = resp.json().get("html", "")
        text = _extract_with_readability(html, url)
        return (text, url) if len(text.strip()) > 150 else None
    except Exception:
        return None


def _fetch_article(url: str, session: requests.Session, referer: str = "", use_js: bool = False) -> tuple[str, str] | None:
    """
    Fetch a single article and return (clean_text, resolved_url).
    resolved_url is the final URL after redirects (e.g. after Google News redirect).
    Returns None on any failure so callers can fall back to feed summary.
    If use_js=True, delegates to the Playwright microservice.
    """
    if _should_skip(url):
        return None
    if use_js:
        return _fetch_article_js(url)
    try:
        domain = _domain_of(url)
        _rate_limit(domain)
        resp = session.get(
            url,
            headers=_get_headers(referer=referer),
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        ct = resp.headers.get("Content-Type", "")
        if "html" not in ct:
            return None
        resolved_url = resp.url  # final URL after all redirects
        text = _extract_with_readability(resp.text, resolved_url)
        return (text, resolved_url) if len(text.strip()) > 150 else None
    except Exception:
        return None


# ── RSS extraction ─────────────────────────────────────────────────────────────

def _extract_rss_content(feed_url: str) -> tuple[str, int]:
    """
    Parse RSS/Atom feed. For each entry:
    1. Try to fetch the full article at entry.link
    2. Fall back to feed summary if fetch fails or is too short
    """
    feed = feedparser.parse(feed_url)
    entries = feed.entries[:MAX_ARTICLES_PER_FEED]

    session = _make_session()
    parts = []

    for entry in entries:
        title = (entry.get("title", "") or "").strip()
        link = (entry.get("link", "") or "").strip()
        summary = entry.get("summary", "") or entry.get("description", "")
        if summary:
            summary = BeautifulSoup(summary, "lxml").get_text().strip()

        # Attempt full-text extraction from the article URL
        result = None
        if link:
            result = _fetch_article(link, session, referer=feed_url)

        full_text, resolved_url = (result if result else (None, link))
        source_url = resolved_url or link

        # Use whichever is longer: full article vs feed summary
        if full_text and len(full_text) > max(len(summary), 200):
            body = full_text
        elif summary:
            body = summary[:MAX_ARTICLE_CHARS]
        else:
            body = ""

        if title or body:
            parts.append(f"## {title}\n{body}\nSource: {source_url}")

    content = "\n\n---\n\n".join(parts)
    return content, 200


# ── Webpage extraction ─────────────────────────────────────────────────────────

def _fetch_webpage(url: str) -> tuple[str, int]:
    """Fetch a webpage and extract clean main content via readability."""
    session = _make_session()
    domain = _domain_of(url)
    _rate_limit(domain)
    resp = session.get(
        url,
        headers=_get_headers(),
        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        allow_redirects=True,
    )
    text = _extract_with_readability(resp.text, url)
    return text, resp.status_code


# ── Public API ─────────────────────────────────────────────────────────────────

def fetch_url_sync(url: str, source_type: str, requires_js: bool = False) -> tuple[str | None, int | None, str | None]:
    """
    Fetch and extract content from url.
    Returns (content, http_status, error_message).
    Runs synchronously — called from Celery worker thread.
    If requires_js=True and source_type is webpage, delegates to Playwright microservice.
    """
    try:
        if source_type in ("rss", "search"):
            content, status = _extract_rss_content(url)
        elif requires_js:
            result = _fetch_article_js(url)
            if result:
                content, _ = result
                status = 200
            else:
                content, status = None, None
        else:
            content, status = _fetch_webpage(url)

        if not content or len(content.strip()) < 50:
            return None, None, "No meaningful content extracted"

        return content, status, None

    except requests.exceptions.Timeout:
        return None, None, "Request timed out"
    except requests.exceptions.ConnectionError as e:
        return None, None, f"Connection error: {str(e)[:200]}"
    except Exception as e:
        return None, None, f"Error: {str(e)[:200]}"


async def fetch_and_extract(url: str, source_type: str, preview_only: bool = False) -> SourceTestResult:
    """Async wrapper — runs sync fetch in thread pool."""
    loop = asyncio.get_event_loop()
    content, http_status, error = await loop.run_in_executor(
        None, fetch_url_sync, url, source_type
    )

    if error:
        return SourceTestResult(success=False, error=error)

    preview = content[:500] if (content and preview_only) else None
    return SourceTestResult(success=True, http_status=http_status, content_preview=preview)


def compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
