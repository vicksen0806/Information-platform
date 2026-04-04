"""Celery task for LLM digest generation."""
import time
import uuid

from celery import shared_task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.tasks.celery_app import celery_app

_sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
_engine = create_engine(_sync_db_url, pool_pre_ping=True)


def _get_session() -> Session:
    return Session(_engine)


def _send_with_retry(send_fn, config, keywords, summary_md, created_at, max_attempts=3):
    """Send notification with exponential backoff retry (30s, 60s)."""
    for attempt in range(max_attempts):
        try:
            success, _ = send_fn(config, keywords, summary_md, created_at)
            if success:
                return
        except Exception:
            pass
        if attempt < max_attempts - 1:
            time.sleep(30 * (2 ** attempt))


@celery_app.task(name="app.tasks.digest_tasks.generate_digest", bind=True, max_retries=2)
def generate_digest(self, job_id: str, user_id: str):
    """
    Generate an LLM digest from completed crawl results.
    - Loads all CrawlResults with content for the job
    - Loads user's active keywords
    - Calls LLM via llm_service
    - Upserts a Digest row
    """
    from app.models.crawl_result import CrawlResult
    from app.models.digest import Digest
    from app.models.keyword import Keyword
    from app.models.user_llm_config import UserLlmConfig
    from app.services.llm_service import generate_digest_sync

    job_uuid = uuid.UUID(job_id)
    user_uuid = uuid.UUID(user_id)

    with _get_session() as db:
        # Load LLM config
        llm_config = db.execute(
            select(UserLlmConfig).where(UserLlmConfig.user_id == user_uuid)
        ).scalar_one_or_none()

        if not llm_config:
            return  # User hasn't configured LLM — skip silently

        # Load crawl results with actual content
        rows = db.execute(
            select(CrawlResult)
            .where(
                CrawlResult.crawl_job_id == job_uuid,
                CrawlResult.raw_content.isnot(None),
            )
        ).scalars().all()

        if not rows:
            return  # Nothing to summarize

        # Load active keywords (for group mapping and prompt context)
        keywords = db.execute(
            select(Keyword).where(
                Keyword.user_id == user_uuid,
                Keyword.is_active == True,
            )
        ).scalars().all()
        keyword_texts = [kw.text for kw in keywords]
        kw_group_map = {kw.text: kw.group_name for kw in keywords}

        # Group content by keyword so LLM receives per-keyword sections
        keyword_content_map: dict[str, list[str]] = {}
        for row in rows:
            kw_label = row.keyword_text or "其他"
            keyword_content_map.setdefault(kw_label, []).append(row.raw_content or "")

        crawled_contents = [
            {
                "keyword": kw_label,
                "content": "\n\n".join(contents),
                "group": kw_group_map.get(kw_label),
            }
            for kw_label, contents in keyword_content_map.items()
        ]

        # Call LLM
        try:
            result = generate_digest_sync(llm_config, keyword_texts, crawled_contents)
        except Exception as exc:
            from openai import AuthenticationError as OpenAIAuthError
            if isinstance(exc, OpenAIAuthError):
                # API Key invalid — record error and stop immediately, do not retry
                from app.models.crawl_job import CrawlJob
                job = db.execute(
                    select(CrawlJob).where(CrawlJob.id == job_uuid)
                ).scalar_one_or_none()
                if job:
                    job.digest_error = "API Key 已失效，请在设置页面更新"
                    db.commit()
                return
            raise self.retry(exc=exc, countdown=60)

        # Upsert digest
        existing_digest = db.execute(
            select(Digest).where(Digest.crawl_job_id == job_uuid)
        ).scalar_one_or_none()

        if existing_digest:
            existing_digest.title = result["title"]
            existing_digest.summary_md = result["summary_md"]
            existing_digest.keywords_used = keyword_texts
            existing_digest.sources_count = len(crawled_contents)
            existing_digest.tokens_used = result["tokens_used"]
            existing_digest.llm_model = result["llm_model"]
            existing_digest.is_read = False
        else:
            digest = Digest(
                user_id=user_uuid,
                crawl_job_id=job_uuid,
                title=result["title"],
                summary_md=result["summary_md"],
                keywords_used=keyword_texts,
                sources_count=len(crawled_contents),
                tokens_used=result["tokens_used"],
                llm_model=result["llm_model"],
            )
            db.add(digest)

        db.commit()

        # Send webhook notification if configured
        from app.models.user_notification_config import UserNotificationConfig
        notif_config = db.execute(
            select(UserNotificationConfig).where(
                UserNotificationConfig.user_id == user_uuid,
                UserNotificationConfig.is_active == True,
            )
        ).scalar_one_or_none()

        from datetime import datetime, timezone as tz
        created_str = datetime.now(tz.utc).strftime("%Y-%m-%d %H:%M UTC")
        final_digest = existing_digest if existing_digest else digest
        final_summary = (final_digest.summary_md if final_digest else "") or ""

        from app.services.notification_service import send_digest_notification, send_email_notification

        # Global webhook (with simple retry)
        if notif_config:
            _send_with_retry(send_digest_notification, notif_config, keyword_texts, final_summary, created_str)

        # Per-group webhook routing
        from app.models.notification_route import NotificationRoute
        routes = db.execute(
            select(NotificationRoute).where(
                NotificationRoute.user_id == user_uuid,
                NotificationRoute.is_active == True,
            )
        ).scalars().all()

        if routes:
            # Build per-group raw content for routing
            group_content_map: dict[str | None, list[str]] = {}
            for item in crawled_contents:
                g = item.get("group")
                group_content_map.setdefault(g, []).append(
                    f"**{item['keyword']}**:\n{item['content'][:1500]}"
                )
            for route in routes:
                group_kws = [item["keyword"] for item in crawled_contents if item.get("group") == route.group_name]
                if group_kws and route.group_name in group_content_map or route.group_name is None and None in group_content_map:
                    route_content = "\n\n".join(group_content_map.get(route.group_name, []))
                    _send_with_retry(send_digest_notification, route, group_kws or keyword_texts, route_content, created_str)

        # Email notification (with simple retry)
        from app.models.user_email_config import UserEmailConfig
        email_config = db.execute(
            select(UserEmailConfig).where(
                UserEmailConfig.user_id == user_uuid,
                UserEmailConfig.is_active == True,
            )
        ).scalar_one_or_none()

        if email_config:
            _send_with_retry(send_email_notification, email_config, keyword_texts, final_summary, created_str)
