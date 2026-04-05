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


def _send_web_push(db, user_uuid, digest, should_notify: bool):
    """Send Web Push notification to all subscribed devices for this user."""
    if not should_notify:
        return
    from app.config import settings as _settings
    if not _settings.VAPID_PRIVATE_KEY or not _settings.VAPID_PUBLIC_KEY:
        return  # Not configured
    try:
        from app.models.push_subscription import PushSubscription
        from pywebpush import webpush, WebPushException
        import json

        subs = db.execute(
            select(PushSubscription).where(PushSubscription.user_id == user_uuid)
        ).scalars().all()

        if not subs:
            return

        title = (digest.title or "新摘要") if digest else "新摘要"
        payload = json.dumps({
            "title": f"Info Platform: {title}",
            "body": f"已生成新摘要，点击查看",
            "url": f"/digests/{digest.id}" if digest else "/digests",
        })

        dead_endpoints = []
        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=payload,
                    vapid_private_key=_settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": _settings.VAPID_EMAIL},
                )
            except WebPushException as e:
                if e.response and e.response.status_code in (404, 410):
                    dead_endpoints.append(sub.endpoint)
            except Exception:
                pass

        # Clean up expired subscriptions
        for endpoint in dead_endpoints:
            dead = db.execute(
                select(PushSubscription).where(PushSubscription.endpoint == endpoint)
            ).scalar_one_or_none()
            if dead:
                db.delete(dead)
        if dead_endpoints:
            db.commit()
    except Exception:
        pass  # Web Push is optional, never block digest generation


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
            result = generate_digest_sync(llm_config, keyword_texts, crawled_contents, feedback_hint=feedback_hint)
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

        importance_score = result.get("importance_score")
        if existing_digest:
            existing_digest.title = result["title"]
            existing_digest.summary_md = result["summary_md"]
            existing_digest.keywords_used = keyword_texts
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
                keywords_used=keyword_texts,
                sources_count=len(crawled_contents),
                tokens_used=result["tokens_used"],
                llm_model=result["llm_model"],
                importance_score=importance_score,
            )
            db.add(digest)

        db.commit()

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

        from datetime import datetime, timezone as tz
        created_str = datetime.now(tz.utc).strftime("%Y-%m-%d %H:%M UTC")
        final_digest = existing_digest if existing_digest else digest
        final_summary = (final_digest.summary_md if final_digest else "") or ""

        from app.services.notification_service import send_digest_notification, send_email_notification

        # Global webhook (with simple retry)
        if notif_config and should_notify:
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

        if email_config and should_notify:
            _send_with_retry(send_email_notification, email_config, keyword_texts, final_summary, created_str)

        # Web Push notifications
        _send_web_push(db, user_uuid, final_digest, should_notify)
