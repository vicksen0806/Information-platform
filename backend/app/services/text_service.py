import re
from urllib.parse import urlparse

try:
    from opencc import OpenCC
except Exception:  # pragma: no cover - graceful fallback when dependency is missing
    OpenCC = None


_t2s = OpenCC("t2s") if OpenCC else None

_KNOWN_SOURCE_NAMES = {
    "news.google.com": "Google新闻",
    "google.com": "Google",
    "linkedin.com": "LinkedIn",
    "x.com": "X",
    "twitter.com": "X",
    "youtube.com": "YouTube",
    "github.com": "GitHub",
    "reddit.com": "Reddit",
    "medium.com": "Medium",
    "substack.com": "Substack",
    "techcrunch.com": "TechCrunch",
    "theverge.com": "The Verge",
    "ltn.com.tw": "自由时报",
    "ettoday.net": "ETtoday新闻云",
    "udn.com": "联合新闻网",
    "storm.mg": "风传媒",
    "newtalk.tw": "Newtalk新闻",
    "thenewslens.com": "The News Lens",
    "cna.com.tw": "中央社",
    "setn.com": "三立新闻网",
    "reuters.com": "Reuters",
    "bbc.com": "BBC",
    "nikkei.com": "日经中文网",
    "yahoo.com": "Yahoo",
    "yahoo.co.jp": "Yahoo Japan",
}


def to_simplified_chinese(text: str | None) -> str | None:
    if not text:
        return text
    if not _t2s:
        return text
    try:
        return _t2s.convert(text)
    except Exception:
        return text


def source_name_from_url(url: str | None) -> str:
    if not url:
        return "来源"

    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    if host in _KNOWN_SOURCE_NAMES:
        return _KNOWN_SOURCE_NAMES[host]

    for domain, name in _KNOWN_SOURCE_NAMES.items():
        if host.endswith(f".{domain}"):
            return name

    root = host.split(".")[0] if host else ""
    return root.capitalize() if root else "来源"


def _clean_source_label(label: str | None, url: str) -> str:
    normalized = (label or "").strip().strip("[]()（）")
    normalized = re.sub(r"\s+", " ", normalized)
    if not normalized:
        return source_name_from_url(url)
    if normalized.lower().startswith(("http://", "https://")):
        return source_name_from_url(url)
    if len(normalized) > 32 or any(token in normalized for token in ("/", "?", "&", "=")):
        return source_name_from_url(url)
    return normalized


def normalize_markdown_source_links(text: str | None) -> str | None:
    if not text:
        return text

    normalized = text

    # Repair truncated patterns like `([来源名](https://...)` at end of line / EOF.
    normalized = re.sub(
        r"(?P<open>[（(])\[(?P<label>[^\]\n]{1,120})\]\((?P<url>https?://[^\s)]+)(?=$|\n)",
        lambda m: f"{m.group('open')}[{_clean_source_label(m.group('label'), m.group('url'))}]({m.group('url')}){'）' if m.group('open') == '（' else ')'}",
        normalized,
    )

    # Repair truncated patterns like `[来源名](https://...)` at end of line / EOF.
    normalized = re.sub(
        r"\[(?P<label>[^\]\n]{1,120})\]\((?P<url>https?://[^\s)]+)(?=$|\n)",
        lambda m: f"[{_clean_source_label(m.group('label'), m.group('url'))}]({m.group('url')})",
        normalized,
    )

    # Keep existing markdown links, but normalize the visible label.
    normalized = re.sub(
        r"\[(?P<label>[^\]\n]{1,120})\]\((?P<url>https?://[^\s)]+)\)",
        lambda m: f"[{_clean_source_label(m.group('label'), m.group('url'))}]({m.group('url')})",
        normalized,
    )

    # Convert any remaining bare URLs to short source links.
    normalized = re.sub(
        r"(?<!\]\()(?P<url>https?://[^\s)]+)",
        lambda m: f"[{source_name_from_url(m.group('url'))}]({m.group('url')})",
        normalized,
    )

    return normalized


def localize_digest_text(text: str | None, ui_language: str) -> str | None:
    if ui_language == "zh":
        return to_simplified_chinese(text)
    return text
