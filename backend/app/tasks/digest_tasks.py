"""Celery task for LLM digest generation."""
import time
import uuid
from datetime import datetime, timezone

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
        from app.models.crawl_job import CrawlJob

        def _mark_job_finished(*, digest_error: str | None = None):
            job = db.execute(
                select(CrawlJob).where(CrawlJob.id == job_uuid)
            ).scalar_one_or_none()
            if not job:
                return
            job.completed_at = job.completed_at or datetime.now(timezone.utc)
            if digest_error is not None:
                job.digest_error = digest_error
            db.commit()

        # Load user language preference
        from app.models.user import User
        user = db.execute(select(User).where(User.id == user_uuid)).scalar_one_or_none()
        ui_language = getattr(user, "ui_language", "zh") if user else "zh"

        # Load LLM config
        llm_config = db.execute(
            select(UserLlmConfig).where(UserLlmConfig.user_id == user_uuid)
        ).scalar_one_or_none()

        if not llm_config:
            _mark_job_finished(digest_error="未配置 LLM，请在系统设置中填写 API Key")
            return

        all_job_results = db.execute(
            select(CrawlResult.keyword_text, CrawlResult.crawled_at)
            .where(CrawlResult.crawl_job_id == job_uuid)
            .order_by(CrawlResult.crawled_at.asc())
        ).all()

        job_keyword_texts: list[str] = []
        for row in all_job_results:
            keyword_text = (row.keyword_text or "").strip()
            if keyword_text and keyword_text not in job_keyword_texts:
                job_keyword_texts.append(keyword_text)

        # Load crawl results with actual content
        rows = db.execute(
            select(CrawlResult)
            .where(
                CrawlResult.crawl_job_id == job_uuid,
                CrawlResult.raw_content.isnot(None),
            )
            .order_by(CrawlResult.crawled_at.asc())
        ).scalars().all()

        if not rows:
            _mark_job_finished()
            return  # Nothing to summarize

        keywords = db.execute(
            select(Keyword).where(
                Keyword.user_id == user_uuid,
                Keyword.text.in_(job_keyword_texts),
            )
        ).scalars().all()
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

        # Build feedback hint from user's recent digests (min 5 samples)
        feedback_hint = None
        try:
            from app.models.digest_feedback import DigestFeedback
            recent_fb = db.execute(
                select(DigestFeedback.value)
                .where(DigestFeedback.user_id == user_uuid)
                .order_by(DigestFeedback.created_at.desc())
                .limit(30)
            ).scalars().all()
            if len(recent_fb) >= 5:
                pos = sum(1 for v in recent_fb if v == "positive")
                total = len(recent_fb)
                pos_pct = pos / total
                neg_pct = 1 - pos_pct
                if pos_pct >= 0.70:
                    feedback_hint = f"用户对近期摘要总体满意（正面反馈 {round(pos_pct*100)}%），请继续保持当前摘要风格和详细程度"
                elif neg_pct >= 0.60:
                    feedback_hint = f"用户对近期摘要不太满意（负面反馈 {round(neg_pct*100)}%），请尝试调整：减少冗余信息，突出最重要的几个要点，确保每条信息都有实际价值"
        except Exception:
            pass  # feedback hint is optional, never block digest generation

        # Call LLM
        try:
            result = generate_digest_sync(llm_config, job_keyword_texts, crawled_contents, feedback_hint=feedback_hint, ui_language=ui_language)
        except Exception as exc:
            from openai import AuthenticationError as OpenAIAuthError, RateLimitError as OpenAIRateLimitError

            def _write_digest_error(msg: str):
                _mark_job_finished(digest_error=msg)

            if isinstance(exc, OpenAIAuthError):
                # API Key invalid — record error and stop immediately, do not retry
                _write_digest_error("API Key 已失效，请在设置页面更新")
                return
            if isinstance(exc, OpenAIRateLimitError):
                # Rate limit (429) — retry with longer backoff, up to 5 attempts total
                if self.request.retries >= 4:
                    _write_digest_error("LLM 调用超出频率限制，已重试 5 次，请稍后手动重试")
                    return
                raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries), max_retries=5)
            # Other errors: standard retry with 60s backoff; write error on final failure
            if self.request.retries >= (self.max_retries or 2):
                _write_digest_error(f"LLM 调用失败：{type(exc).__name__}")
            raise self.retry(exc=exc, countdown=60)

        # Upsert digest
        existing_digest = db.execute(
            select(Digest).where(Digest.crawl_job_id == job_uuid)
        ).scalar_one_or_none()

        importance_score = result.get("importance_score")
        if existing_digest:
            existing_digest.title = result["title"]
            existing_digest.summary_md = result["summary_md"]
            existing_digest.keywords_used = job_keyword_texts
            existing_digest.sources_count = len(crawled_contents)
            existing_digest.tokens_used = result["tokens_used"]
            existing_digest.llm_model = result["llm_model"]
            existing_digest.is_read = False
            existing_digest.importance_score = importance_score
        else:
            digest = Digest(
                user_id=user_uuid,
                crawl_job_id=job_uuid,
                title=result["title"],
                summary_md=result["summary_md"],
                keywords_used=job_keyword_texts,
                sources_count=len(crawled_contents),
                tokens_used=result["tokens_used"],
                llm_model=result["llm_model"],
                importance_score=importance_score,
            )
            db.add(digest)

        db.commit()
        final_digest = existing_digest if existing_digest else digest
        db.refresh(final_digest)

        job = db.execute(
            select(CrawlJob).where(CrawlJob.id == job_uuid)
        ).scalar_one_or_none()
        if job:
            job.completed_at = datetime.now(timezone.utc)
            job.digest_error = None
            db.commit()

        # Generate and store embedding via raw SQL (optional — skip silently on failure)
        try:
            from app.services.llm_service import generate_embedding_sync
            from app.config import settings as _s
            if getattr(llm_config, "embedding_model", None) and final_digest and getattr(_s, "PGVECTOR_ENABLED", False):
                embed_text = f"{final_digest.title or ''}\n{(final_digest.summary_md or '')[:2000]}"
                vec = generate_embedding_sync(llm_config, embed_text)
                if vec:
                    from sqlalchemy import text as sql_text
                    vec_str = "[" + ",".join(str(v) for v in vec) + "]"
                    db.execute(
                        sql_text("UPDATE digests SET embedding = :vec::vector WHERE id = :id"),
                        {"vec": vec_str, "id": str(final_digest.id)},
                    )
                    db.commit()
        except Exception:
            pass

        # Notify only if importance_score is absent (unknown) or above threshold
        IMPORTANCE_THRESHOLD = 0.4
        should_notify = importance_score is None or importance_score >= IMPORTANCE_THRESHOLD

        # Send webhook notification if configured
        from app.models.user_notification_config import UserNotificationConfig
        notif_config = db.execute(
            select(UserNotificationConfig).where(
                UserNotificationConfig.user_id == user_uuid,
                UserNotificationConfig.is_active == True,
            )
        ).scalar_one_or_none()

        created_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        final_digest = existing_digest if existing_digest else digest
        final_summary = (final_digest.summary_md if final_digest else "") or ""

        from app.services.notification_service import send_digest_notification

        # Global webhook (with simple retry)
        if notif_config and should_notify:
            _send_with_retry(send_digest_notification, notif_config, job_keyword_texts, final_summary, created_str)
