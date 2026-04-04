from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.routers import auth, sources, keywords, crawl_jobs, digests, settings as settings_router, admin, public as public_router
# Import new models so SQLAlchemy registers them with Base.metadata
import app.models.user_schedule_config  # noqa: F401
import app.models.user_notification_config  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (for dev; use alembic in production)
    if settings.ENV == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

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
