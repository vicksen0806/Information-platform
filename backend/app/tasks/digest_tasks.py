"""Celery task for LLM digest generation."""
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
    from app.models.source import Source
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
            select(CrawlResult, Source.name.label("source_name"))
            .join(Source, CrawlResult.source_id == Source.id)
            .where(
                CrawlResult.crawl_job_id == job_uuid,
                CrawlResult.raw_content.isnot(None),
            )
        ).all()

        if not rows:
            return  # Nothing to summarize

        crawled_contents = [
            {"source_name": row.source_name, "content": row.CrawlResult.raw_content}
            for row in rows
        ]

        # Load active keywords
        keywords = db.execute(
            select(Keyword).where(
                Keyword.user_id == user_uuid,
                Keyword.is_active == True,
            )
        ).scalars().all()
        keyword_texts = [kw.text for kw in keywords]

        # Call LLM
        try:
            result = generate_digest_sync(llm_config, keyword_texts, crawled_contents)
        except Exception as exc:
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
