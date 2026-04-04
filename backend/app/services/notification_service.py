"""
Webhook notification service.
Supports Feishu (飞书), WeCom (企业微信), and generic webhooks.
"""
import re
import requests


def _strip_markdown(text: str, max_chars: int = 300) -> str:
    """Remove markdown syntax for plain-text notification body."""
    text = re.sub(r"#{1,6}\s+", "", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    text = re.sub(r"[-*+]\s+", "• ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "..."
    return text


def _build_feishu_payload(keywords: list[str], summary_md: str, created_at: str) -> dict:
    """Feishu interactive card message."""
    kw_str = " · ".join(keywords) if keywords else "—"
    excerpt = _strip_markdown(summary_md)
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"📰 New Digest: {kw_str}"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": excerpt},
                },
                {
                    "tag": "note",
                    "elements": [{"tag": "plain_text", "content": f"Generated at {created_at}"}],
                },
            ],
        },
    }


def _build_wecom_payload(keywords: list[str], summary_md: str, created_at: str) -> dict:
    """WeCom markdown message."""
    kw_str = " | ".join(keywords) if keywords else "—"
    excerpt = _strip_markdown(summary_md)
    content = (
        f"## 📰 New Digest\n"
        f"> **Keywords**: {kw_str}\n"
        f"> **Time**: {created_at}\n\n"
        f"{excerpt}"
    )
    return {"msgtype": "markdown", "markdown": {"content": content}}


def _build_generic_payload(keywords: list[str], summary_md: str, created_at: str) -> dict:
    """Generic JSON payload."""
    return {
        "title": f"New Digest: {', '.join(keywords) if keywords else 'Info Platform'}",
        "keywords": keywords,
        "excerpt": _strip_markdown(summary_md),
        "created_at": created_at,
    }


def send_digest_notification(config, keywords: list[str], summary_md: str, created_at: str) -> tuple[bool, str]:
    """
    Send digest notification via webhook.
    Returns (success, message).
    config: UserNotificationConfig ORM object
    """
    if not config.is_active or not config.webhook_url:
        return False, "Notification disabled or no URL"

    try:
        wtype = config.webhook_type
        if wtype == "feishu":
            payload = _build_feishu_payload(keywords, summary_md, created_at)
        elif wtype == "wecom":
            payload = _build_wecom_payload(keywords, summary_md, created_at)
        else:
            payload = _build_generic_payload(keywords, summary_md, created_at)

        resp = requests.post(
            config.webhook_url,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code != 200:
            return False, f"Webhook returned HTTP {resp.status_code}: {resp.text[:200]}"

        # Feishu and WeCom both return JSON with a non-zero code on error
        try:
            body = resp.json()
            code = body.get("code", 0) or body.get("errcode", 0)
            if code != 0:
                msg = body.get("msg") or body.get("errmsg") or str(body)
                return False, f"Webhook error (code {code}): {msg}"
        except Exception:
            pass  # Non-JSON response — treat HTTP 200 as success

        return True, "Notification sent"

    except Exception as e:
        return False, f"Error: {str(e)[:200]}"
