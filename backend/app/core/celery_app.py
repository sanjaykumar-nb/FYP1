from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "teamsync",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.ai_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.analytics_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    beat_schedule={
        "daily-workload-snapshot": {
            "task": "app.tasks.ai_tasks.create_daily_workload_snapshots",
            "schedule": 86400.0,  # 24 hours
        },
        "scheduled-analysis": {
            "task": "app.tasks.ai_tasks.run_scheduled_analyses",
            "schedule": 3600.0,  # 1 hour
        },
    },
)