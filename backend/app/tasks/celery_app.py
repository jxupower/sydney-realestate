from celery import Celery

from app.config import settings

celery_app = Celery(
    "sydney_realestate",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.ingestion_tasks",
        "app.tasks.ml_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Australia/Sydney",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,  # 24 hours
)

# Import beat schedule (registers periodic tasks)
from app.tasks.beat_schedule import BEAT_SCHEDULE  # noqa: E402
celery_app.conf.beat_schedule = BEAT_SCHEDULE
