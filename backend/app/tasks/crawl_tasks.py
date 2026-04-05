"""
Celery tasks for crawling.

Note: Celery workers run synchronously, so we use synchronous SQLAlchemy
with a regular (non-async) engine here for simplicity.
"""
import re
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


def _filter_seen_articles(content: str, seen_urls: set) -> tuple[str, set]:
    """
    Split content into individual articles (separated by ---), filter out
    those whose Source URL was already processed in this job (cross-keyword dedup).
    Returns (filtered_content, newly_seen_urls).
    """
    articles = content.split("\n\n---\n\n")
    new_articles = []
    new_urls: set = set()
    for article in articles:
        match = re.search(r"^Source:\s*(.+)$", article, re.MULTILINE)
        if match:
            url = match.group(1).strip()
            if url in seen_urls:
                continue  # duplicate across keywords — skip
            new_urls.add(url)
        new_articles.append(article)
    return "\n\n---\n\n".join(new_articles), new_urls


@celery_app.task(name="app.tasks.crawl_tasks.crawl_all_users", bind=True, max_retries=1)
def crawl_all_users(self):
    """
    Runs every 30 minutes. For each active user, checks whether their
    personal schedule matches the current time (within a 30-minute window).
    Falls back to the global DAILY_CRAWL_HOUR setting for users without a schedule.
    """
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    from app.models.user import User
    from app.models.user_schedule_config import UserScheduleConfig

    now_utc = datetime.now(timezone.utc)

    with _get_session() as db:
        users = db.execute(select(User).where(User.is_active == True)).scalars().all()

        for user in users:
            schedule = db.execute(
                select(UserScheduleConfig).where(UserScheduleConfig.user_id == user.id)
            ).scalar_one_or_none()

            if schedule and not schedule.is_active:
                continue  # User explicitly disabled scheduling

            if schedule:
                try:
                    tz = ZoneInfo(schedule.timezone)
                except ZoneInfoNotFoundError:
                    tz = ZoneInfo("UTC")
                now_local = now_utc.astimezone(tz)
                target_hour = schedule.schedule_hour
                target_minute = schedule.schedule_minute
            else:
                # Default: use global config (UTC)
                now_local = now_utc
                target_hour = settings.DAILY_CRAWL_HOUR
                target_minute = settings.DAILY_CRAWL_MINUTE

            # Trigger if we're within 15 minutes of the scheduled time
            # Use modular arithmetic to handle midnight rollover correctly
            current_total = now_local.hour * 60 + now_local.minute
            target_total = target_hour * 60 + target_minute
            diff = (current_total - target_total) % (24 * 60)
            # diff is minutes since target; also check wrap-around (i.e. up to 15min before)
            if diff <= 15 or diff >= (24 * 60 - 15):
                run_crawl_job.delay(None, str(user.id), triggered_by="schedule")


@celery_app.task(name="app.tasks.crawl_tasks.run_crawl_job", bind=True, max_retries=2)
def run_crawl_job(self, job_id: str | None, user_id: str, triggered_by: str = "manual"):
    """
    Core crawl task:
    1. Create or reuse a CrawlJob row
    2. Fetch all active sources for the user
    3. Store CrawlResult for each (skip if content unchanged)
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
        db.commit()

        # Get active keywords — each keyword is now also the crawl source
        keywords = db.execute(
            select(Keyword).where(Keyword.user_id == user_uuid, Keyword.is_active == True)
        ).scalars().all()

        if not keywords:
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        has_new_content = False
        seen_urls: set = set()  # Track article URLs seen in this job (cross-keyword dedup)

        for kw in keywords:
            # Check per-keyword crawl interval — skip if crawled too recently
            if kw.last_crawled_at is not None:
                elapsed_hours = (datetime.now(timezone.utc) - kw.last_crawled_at).total_seconds() / 3600
                effective_interval = kw.crawl_interval_hours

                # Auto-adjust: if last 5 crawls all empty, use 4× interval (max 168h)
                recent_contents = db.execute(
                    select(CrawlResult.raw_content)
                    .join(CrawlJob, CrawlResult.crawl_job_id == CrawlJob.id)
                    .where(CrawlResult.keyword_text == kw.text, CrawlJob.user_id == user_uuid)
                    .order_by(CrawlResult.crawled_at.desc())
                    .limit(5)
                ).scalars().all()
                if len(recent_contents) >= 5 and all(r is None for r in recent_contents):
                    effective_interval = min(kw.crawl_interval_hours * 4, 168)

                if elapsed_hours < effective_interval:
                    continue  # Not due yet

            # Use specified URL or fall back to Google News RSS search
            if kw.url:
                crawl_url = kw.url
                crawl_type = kw.source_type
            else:
                query = urllib.parse.quote(kw.text)
                crawl_url = f"https://news.google.com/rss/search?q={query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
                crawl_type = "rss"

            content, http_status, error = fetch_url_sync(
                crawl_url, crawl_type, requires_js=getattr(kw, "requires_js", False)
            )

            # Update last_crawled_at regardless of success/failure
            kw.last_crawled_at = datetime.now(timezone.utc)

            if error or not content:
                result = CrawlResult(
                    crawl_job_id=job.id,
                    source_id=None,
                    keyword_text=kw.text,
                    http_status=http_status,
                    error_message=error or "Empty content",
                )
                db.add(result)
                db.flush()
                continue

            # Cross-keyword URL dedup: filter out articles already seen in this job
            filtered_content, new_urls = _filter_seen_articles(content, seen_urls)
            seen_urls.update(new_urls)

            if not filtered_content.strip():
                # All articles were duplicates from other keywords — skip
                result = CrawlResult(
                    crawl_job_id=job.id,
                    source_id=None,
                    keyword_text=kw.text,
                    http_status=http_status,
                    error_message="All articles duplicated across keywords",
                )
                db.add(result)
                db.flush()
                continue

            content = filtered_content
            content_hash = compute_content_hash(content)

            # Only deduplicate within the same day
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            duplicate = db.execute(
                select(CrawlResult)
                .where(
                    CrawlResult.content_hash == content_hash,
                    CrawlResult.crawled_at >= today_start,
                    CrawlResult.crawl_job_id != job.id,
                )
                .limit(1)
            ).scalar_one_or_none()

            if duplicate:
                result = CrawlResult(
                    crawl_job_id=job.id,
                    source_id=None,
                    keyword_text=kw.text,
                    raw_content=None,
                    content_hash=content_hash,
                    http_status=http_status,
                    error_message="Content unchanged since last crawl",
                )
            else:
                has_new_content = True
                result = CrawlResult(
                    crawl_job_id=job.id,
                    source_id=None,
                    keyword_text=kw.text,
                    raw_content=content,
                    content_hash=content_hash,
                    http_status=http_status,
                )

            db.add(result)
            db.flush()

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.new_content_found = has_new_content
        db.commit()

        # Failure alert: check if any active keyword has 3+ consecutive errors
        _check_and_alert_failures(db, keywords, user_uuid, job.id)

        job_id_str = str(job.id)

    # Dispatch digest generation if there's new content and user has LLM configured
    if has_new_content:
        generate_digest.delay(job_id_str, user_id)


def _check_and_alert_failures(db, keywords, user_uuid, current_job_id):
    """After each crawl job, check for keywords with 3+ consecutive failures and send alert."""
    from app.models.user_notification_config import UserNotificationConfig
    from app.models.user_email_config import UserEmailConfig
    from app.services.notification_service import send_digest_notification, send_email_notification
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

    email = db.execute(
        select(UserEmailConfig).where(
            UserEmailConfig.user_id == user_uuid,
            UserEmailConfig.is_active == True,
        )
    ).scalar_one_or_none()
    if email:
        try:
            send_email_notification(email, failing, alert_md, ts)
        except Exception:
            pass
