from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "infoplatform",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.crawl_tasks",
        "app.tasks.digest_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

celery_app.conf.beat_schedule = {
    "daily-crawl-all-users": {
        "task": "app.tasks.crawl_tasks.crawl_all_users",
        "schedule": crontab(
            hour=settings.DAILY_CRAWL_HOUR,
            minute=settings.DAILY_CRAWL_MINUTE,
        ),
    },
}
