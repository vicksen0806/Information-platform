"""
Celery tasks for crawling.

Note: Celery workers run synchronously, so we use synchronous SQLAlchemy
with a regular (non-async) engine here for simplicity.
"""
import uuid
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.tasks.celery_app import celery_app

# Synchronous DB engine for Celery workers — ensure psycopg2 driver
_sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2").replace("postgresql://", "postgresql+psycopg2://")
_engine = create_engine(_sync_db_url, pool_pre_ping=True)


def _get_session() -> Session:
    return Session(_engine)


def _latest_result_for_keyword(db: Session, user_uuid, keyword_text: str, *, raw_content_only: bool = False):
    from app.models.crawl_result import CrawlResult
    from app.models.crawl_job import CrawlJob

    stmt = (
        select(CrawlResult)
        .join(CrawlJob, CrawlResult.crawl_job_id == CrawlJob.id)
        .where(
            CrawlResult.keyword_text == keyword_text,
            CrawlJob.user_id == user_uuid,
        )
        .order_by(CrawlResult.crawled_at.desc())
        .limit(1)
    )
    if raw_content_only:
        stmt = stmt.where(CrawlResult.raw_content.isnot(None))
    return db.execute(stmt).scalar_one_or_none()


@celery_app.task(name="app.tasks.crawl_tasks.crawl_all_users")
def crawl_all_users():
    """Enqueue a crawl job for every active user."""
    from app.models.user import User

    with _get_session() as db:
        users = db.execute(select(User).where(User.is_active == True)).scalars().all()

        for user in users:
            run_crawl_job.delay(None, str(user.id), triggered_by="admin")


@celery_app.task(name="app.tasks.crawl_tasks.run_crawl_job", bind=True, max_retries=2)
def run_crawl_job(self, job_id: str | None, user_id: str, triggered_by: str = "manual"):
    """
    Core crawl task:
    1. Create or reuse a CrawlJob row
    2. Fetch all active keywords for the user
    3. Store CrawlResult for each keyword (skip if content unchanged)
    4. Chain into generate_digest
    """
    import urllib.parse
    from app.models.user import User
    from app.models.crawl_job import CrawlJob
    from app.models.crawl_result import CrawlResult
    from app.models.keyword import Keyword
    from app.services.crawler_service import fetch_url_sync, compute_content_hash
    from app.tasks.digest_tasks import generate_digest

    user_uuid = uuid.UUID(user_id)

    with _get_session() as db:
        # Resolve user
        user = db.execute(select(User).where(User.id == user_uuid)).scalar_one_or_none()
        if not user or not user.is_active:
            return

        # Create or fetch job
        if job_id:
            job = db.execute(select(CrawlJob).where(CrawlJob.id == uuid.UUID(job_id))).scalar_one_or_none()
        else:
            job = CrawlJob(user_id=user_uuid, triggered_by=triggered_by)
            db.add(job)
            db.flush()

        if not job:
            return

        # Mark running
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.completed_at = None
        job.digest_error = None
        job.summary_expected = False
        db.commit()

        # Get active keywords — each keyword is now also the crawl source
        keywords = db.execute(
            select(Keyword).where(Keyword.user_id == user_uuid, Keyword.is_active == True)
        ).scalars().all()

        if not keywords:
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.summary_expected = False
            db.commit()
            return

        has_new_content = False
        has_digest_input = False

        for kw in keywords:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            latest_today = db.execute(
                select(CrawlResult)
                .join(CrawlJob, CrawlResult.crawl_job_id == CrawlJob.id)
                .where(
                    CrawlResult.keyword_text == kw.text,
                    CrawlJob.user_id == user_uuid,
                    CrawlResult.crawled_at >= today_start,
                    CrawlResult.crawl_job_id != job.id,
                )
                .order_by(CrawlResult.crawled_at.desc())
                .limit(1)
            ).scalar_one_or_none()

            if latest_today:
                reused_result = CrawlResult(
                    crawl_job_id=job.id,
                    keyword_text=kw.text,
                    raw_content=latest_today.raw_content,
                    content_hash=latest_today.content_hash,
                    http_status=latest_today.http_status,
                    crawled_at=latest_today.crawled_at,
                    error_message=latest_today.error_message,
                )
                db.add(reused_result)
                db.flush()
                kw.last_crawled_at = latest_today.crawled_at
                if latest_today.raw_content:
                    has_digest_input = True
                continue

            # Use specified URL or fall back to Google News RSS search
            if kw.url:
                crawl_url = kw.url
                crawl_type = kw.source_type
            else:
                query = urllib.parse.quote(kw.text)
                # Use user's language preference: zh → global Chinese edition (TW), en → global English edition (US)
                if getattr(user, "ui_language", "zh") == "en":
                    rss_params = "hl=en-US&gl=US&ceid=US:en"
                else:
                    rss_params = "hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
                crawl_url = f"https://news.google.com/rss/search?q={query}&{rss_params}"
                crawl_type = "rss"

            content, http_status, error = fetch_url_sync(
                crawl_url, crawl_type, requires_js=getattr(kw, "requires_js", False)
            )

            # Update last_crawled_at regardless of success/failure
            kw.last_crawled_at = datetime.now(timezone.utc)

            if error or not content:
                result = CrawlResult(
                    crawl_job_id=job.id,
                    keyword_text=kw.text,
                    http_status=http_status,
                    error_message=error or "Empty content",
                )
                db.add(result)
                db.flush()
                continue

            content_hash = compute_content_hash(content)
            has_new_content = True
            has_digest_input = True
            result = CrawlResult(
                crawl_job_id=job.id,
                keyword_text=kw.text,
                raw_content=content,
                content_hash=content_hash,
                http_status=http_status,
            )

            db.add(result)
            db.flush()

        job.status = "completed"
        job.new_content_found = has_new_content
        job.summary_expected = has_digest_input
        job.completed_at = None if has_digest_input else datetime.now(timezone.utc)
        db.commit()

        # Failure alert: check if any active keyword has 3+ consecutive errors
        _check_and_alert_failures(db, keywords, user_uuid, job.id)

        job_id_str = str(job.id)

    # Dispatch digest generation if the job has any content to summarize,
    # including content reused from an earlier crawl on the same day.
    if has_digest_input:
        generate_digest.delay(job_id_str, user_id)


def _check_and_alert_failures(db, keywords, user_uuid, current_job_id):
    """After each crawl job, check for keywords with 3+ consecutive failures and send alert."""
    from app.models.crawl_result import CrawlResult
    from app.models.crawl_job import CrawlJob
    from app.models.user_notification_config import UserNotificationConfig
    from app.services.notification_service import send_digest_notification
    from datetime import timezone as tz

    failing = []
    for kw in keywords:
        recent_errors = db.execute(
            select(CrawlResult.error_message)
            .join(CrawlJob, CrawlResult.crawl_job_id == CrawlJob.id)
            .where(
                CrawlResult.keyword_text == kw.text,
                CrawlJob.user_id == user_uuid,
                CrawlResult.error_message.isnot(None),
                CrawlResult.error_message != "Content unchanged since last crawl",
                CrawlResult.error_message != "All articles duplicated across keywords",
            )
            .order_by(CrawlResult.crawled_at.desc())
            .limit(3)
        ).scalars().all()
        if len(recent_errors) >= 3:
            failing.append(kw.text)

    if not failing:
        return

    alert_md = (
        "## ⚠️ 爬取失败告警\n\n"
        f"以下关键词连续 3 次抓取失败，请检查网络或 URL 配置：\n\n"
        + "\n".join(f"- **{kw}**" for kw in failing)
    )
    ts = datetime.now(tz.utc).strftime("%Y-%m-%d %H:%M UTC")

    notif = db.execute(
        select(UserNotificationConfig).where(
            UserNotificationConfig.user_id == user_uuid,
            UserNotificationConfig.is_active == True,
        )
    ).scalar_one_or_none()
    if notif:
        try:
            send_digest_notification(notif, failing, alert_md, ts)
        except Exception:
            pass
