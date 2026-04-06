from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import engine, Base
from app.core.limiter import limiter
from app.routers import auth, sources, keywords, crawl_jobs, digests, settings as settings_router, admin, public as public_router
from app.routers import stats as stats_router
from app.routers import export as export_router
from app.routers import push as push_router
# Import new models so SQLAlchemy registers them with Base.metadata
import app.models.user_schedule_config  # noqa: F401
import app.models.user_notification_config  # noqa: F401
import app.models.user_email_config  # noqa: F401
import app.models.digest_feedback  # noqa: F401
import app.models.digest_star  # noqa: F401
import app.models.notification_route  # noqa: F401
import app.models.audit_log  # noqa: F401
import app.models.user_notion_config  # noqa: F401
import app.models.push_subscription  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (for dev; use alembic in production)
    if settings.ENV == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Schema migrations for existing tables (idempotent ALTER TABLE)
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE user_llm_configs ADD COLUMN IF NOT EXISTS summary_style VARCHAR(20) NOT NULL DEFAULT 'concise'"
        ))
        await conn.execute(text(
            "ALTER TABLE digests ADD COLUMN IF NOT EXISTS importance_score FLOAT"
        ))
        await conn.execute(text(
            "ALTER TABLE keywords ADD COLUMN IF NOT EXISTS requires_js BOOLEAN NOT NULL DEFAULT FALSE"
        ))
        await conn.execute(text(
            "ALTER TABLE user_llm_configs ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(100)"
        ))

    # pgvector — vector similarity search (graceful fallback if not installed)
    async with engine.begin() as conn:
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text(
                "ALTER TABLE digests ADD COLUMN IF NOT EXISTS embedding vector(1536)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_digests_embedding "
                "ON digests USING hnsw (embedding vector_cosine_ops)"
            ))
            settings.PGVECTOR_ENABLED = True
        except Exception:
            pass  # pgvector not installed — semantic search will fall back to text search

    # pg_trgm — enables trigram similarity search and fast LIKE/ILIKE for Chinese
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_digests_title_trgm ON digests USING GIN (title gin_trgm_ops)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_digests_summary_trgm ON digests USING GIN (summary_md gin_trgm_ops)"
        ))

    # pg_jieba — Chinese full-text search (installed only if the extension exists)
    async with engine.begin() as conn:
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_jieba"))
            # Create jieba text search configuration (idempotent)
            await conn.execute(text("""
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_ts_config WHERE cfgname = 'jieba_cfg'
                    ) THEN
                        CREATE TEXT SEARCH CONFIGURATION jieba_cfg (PARSER = jieba);
                        ALTER TEXT SEARCH CONFIGURATION jieba_cfg
                            ADD MAPPING FOR n,v,a,i,e,l WITH simple;
                    END IF;
                END $$
            """))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_digests_title_jieba ON digests "
                "USING GIN (to_tsvector('jieba_cfg', coalesce(title,'')))"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_digests_summary_jieba ON digests "
                "USING GIN (to_tsvector('jieba_cfg', coalesce(summary_md,'')))"
            ))
            # Activate jieba search config for runtime queries
            settings.FTS_CONFIG = "jieba_cfg"
        except Exception:
            pass  # pg_jieba not installed — fall back to simple/trgm search

    # Create first admin user if not exists
    await _ensure_admin()

    yield

    await engine.dispose()


async def _ensure_admin():
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.user import User
    from app.core.security import hash_password

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.email == settings.FIRST_ADMIN_EMAIL)
        )
        if not result.scalar_one_or_none():
            admin_user = User(
                email=settings.FIRST_ADMIN_EMAIL,
                hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
                display_name="Admin",
                is_admin=True,
            )
            db.add(admin_user)
            await db.commit()


app = FastAPI(
    title="Information Platform API",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(sources.router, prefix=API_PREFIX)
app.include_router(keywords.router, prefix=API_PREFIX)
app.include_router(crawl_jobs.router, prefix=API_PREFIX)
app.include_router(digests.router, prefix=API_PREFIX)
app.include_router(settings_router.router, prefix=API_PREFIX)
app.include_router(admin.router, prefix=API_PREFIX)
app.include_router(public_router.router, prefix=API_PREFIX)
app.include_router(stats_router.router, prefix=API_PREFIX)
app.include_router(export_router.router, prefix=API_PREFIX)
app.include_router(push_router.router, prefix=API_PREFIX)


@app.get("/health")
async def health():
    """Detailed health check — verifies DB and Redis connectivity."""
    import asyncio
    from app.database import AsyncSessionLocal
    from sqlalchemy import text

    results: dict = {}

    # Check DB
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        results["db"] = "ok"
    except Exception as e:
        results["db"] = f"error: {str(e)[:100]}"

    # Check Redis
    try:
        import redis
        from app.config import settings
        r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        r.ping()
        results["redis"] = "ok"
    except Exception as e:
        results["redis"] = f"error: {str(e)[:100]}"

    # Check Celery workers (via Redis)
    try:
        from app.tasks.celery_app import celery_app
        inspector = celery_app.control.inspect(timeout=2)
        active = inspector.active()
        results["celery"] = "ok" if active is not None else "no workers"
    except Exception as e:
        results["celery"] = f"error: {str(e)[:100]}"

    overall = "ok" if all(v == "ok" for v in results.values()) else "degraded"
    return {"status": overall, **results}
