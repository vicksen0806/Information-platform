"""Celery tasks for periodic digest report emails (weekly/monthly)."""
from datetime import datetime, timedelta, timezone as tz

from celery import shared_task
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.config import settings
from app.tasks.celery_app import celery_app

_sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
_engine = create_engine(_sync_db_url, pool_pre_ping=True)


def _get_session() -> Session:
    return Session(_engine)


def _build_report_md(period_label: str, digests: list) -> str:
    """Build a Markdown report from a list of Digest ORM objects."""
    if not digests:
        return f"# {period_label} 信息摘要报告\n\n本周期内暂无摘要生成。"

    lines = [f"# {period_label} 信息摘要报告\n"]
    lines.append(f"共生成 **{len(digests)}** 条摘要\n")

    # Keyword frequency
    kw_freq: dict[str, int] = {}
    for d in digests:
        for kw in (d.keywords_used or []):
            kw_freq[kw] = kw_freq.get(kw, 0) + 1
    if kw_freq:
        top_kws = sorted(kw_freq.items(), key=lambda x: -x[1])[:10]
        lines.append("## 关键词频次 TOP 10\n")
        for kw, cnt in top_kws:
            lines.append(f"- **{kw}**: {cnt} 次")
        lines.append("")

    lines.append("## 摘要列表\n")
    for d in sorted(digests, key=lambda x: x.created_at, reverse=True):
        date_str = d.created_at.strftime("%Y-%m-%d") if d.created_at else "—"
        title = d.title or "（无标题）"
        lines.append(f"- [{date_str}] {title}")

    lines.append("\n---\n*由信息平台自动生成*")
    return "\n".join(lines)


def _send_report_for_user(user, db: Session, since: datetime, period_label: str):
    """Query digests and send report via email/webhook for one user."""
    from app.models.digest import Digest
    from app.models.user_notification_config import UserNotificationConfig
    from app.models.user_email_config import UserEmailConfig
    from app.services.notification_service import send_digest_notification, send_email_notification

    digests = db.execute(
        select(Digest).where(
            Digest.user_id == user.id,
            Digest.created_at >= since,
        ).order_by(Digest.created_at.desc())
    ).scalars().all()

    report_md = _build_report_md(period_label, list(digests))
    keywords = list({kw for d in digests for kw in (d.keywords_used or [])})
    created_str = datetime.now(tz.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Email notification
    email_config = db.execute(
        select(UserEmailConfig).where(
            UserEmailConfig.user_id == user.id,
            UserEmailConfig.is_active == True,
        )
    ).scalar_one_or_none()
    if email_config:
        try:
            send_email_notification(email_config, keywords, report_md, created_str)
        except Exception:
            pass

    # Webhook notification
    notif_config = db.execute(
        select(UserNotificationConfig).where(
            UserNotificationConfig.user_id == user.id,
            UserNotificationConfig.is_active == True,
        )
    ).scalar_one_or_none()
    if notif_config:
        try:
            send_digest_notification(notif_config, keywords, report_md, created_str)
        except Exception:
            pass


@celery_app.task(name="app.tasks.report_tasks.send_weekly_report")
def send_weekly_report():
    """Send weekly digest report to all users who have email or webhook configured."""
    from app.models.user import User
    since = datetime.now(tz.utc) - timedelta(days=7)

    with _get_session() as db:
        users = db.execute(select(User).where(User.is_active == True)).scalars().all()
        for user in users:
            try:
                _send_report_for_user(user, db, since, "本周")
            except Exception:
                continue


@celery_app.task(name="app.tasks.report_tasks.send_monthly_report")
def send_monthly_report():
    """Send monthly digest report to all users who have email or webhook configured."""
    from app.models.user import User
    since = datetime.now(tz.utc) - timedelta(days=30)

    with _get_session() as db:
        users = db.execute(select(User).where(User.is_active == True)).scalars().all()
        for user in users:
            try:
                _send_report_for_user(user, db, since, "本月")
            except Exception:
                continue
