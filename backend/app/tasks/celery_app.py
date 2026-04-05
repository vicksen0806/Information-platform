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
        "app.tasks.report_tasks",
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

# Run every 30 minutes — crawl_all_users checks each user's personal schedule
celery_app.conf.beat_schedule = {
    "check-user-schedules": {
        "task": "app.tasks.crawl_tasks.crawl_all_users",
        "schedule": crontab(minute="0,30"),
    },
    # Weekly report: every Monday at 09:00 UTC
    "send-weekly-report": {
        "task": "app.tasks.report_tasks.send_weekly_report",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),
    },
    # Monthly report: 1st of each month at 09:00 UTC
    "send-monthly-report": {
        "task": "app.tasks.report_tasks.send_monthly_report",
        "schedule": crontab(hour=9, minute=0, day_of_month=1),
    },
}
