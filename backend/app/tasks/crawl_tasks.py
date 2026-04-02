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


@celery_app.task(name="app.tasks.crawl_tasks.crawl_all_users", bind=True, max_retries=1)
def crawl_all_users(self):
    """Scheduled task: trigger a crawl job for every active user."""
    from app.models.user import User

    with _get_session() as db:
        users = db.execute(select(User).where(User.is_active == True)).scalars().all()
        for user in users:
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
    from app.models.user import User
    from app.models.source import Source
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

        # Get active sources
        sources = db.execute(
            select(Source).where(Source.user_id == user_uuid, Source.is_active == True)
        ).scalars().all()

        if not sources:
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        has_new_content = False

        for source in sources:
            content, http_status, error = fetch_url_sync(source.url, source.source_type)

            if error or not content:
                result = CrawlResult(
                    crawl_job_id=job.id,
                    source_id=source.id,
                    http_status=http_status,
                    error_message=error or "Empty content",
                )
                db.add(result)
                db.flush()
                continue

            content_hash = compute_content_hash(content)

            # Check for duplicate (same hash as most recent result for this source)
            latest = db.execute(
                select(CrawlResult)
                .where(CrawlResult.source_id == source.id)
                .order_by(CrawlResult.crawled_at.desc())
                .limit(1)
            ).scalar_one_or_none()

            if latest and latest.content_hash == content_hash:
                # Content unchanged — still record it but flag it
                result = CrawlResult(
                    crawl_job_id=job.id,
                    source_id=source.id,
                    raw_content=None,  # Don't store duplicate content
                    content_hash=content_hash,
                    http_status=http_status,
                    error_message="Content unchanged since last crawl",
                )
            else:
                has_new_content = True
                result = CrawlResult(
                    crawl_job_id=job.id,
                    source_id=source.id,
                    raw_content=content,
                    content_hash=content_hash,
                    http_status=http_status,
                )

            db.add(result)
            # Update last_crawled_at on source
            source.last_crawled_at = datetime.now(timezone.utc)
            db.flush()

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        job_id_str = str(job.id)

    # Dispatch digest generation if there's new content and user has LLM configured
    if has_new_content:
        generate_digest.delay(job_id_str, user_id)
