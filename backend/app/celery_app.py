from celery import Celery
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "airport_mgmt",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.inspection", "app.tasks.maintenance"]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Configure periodic tasks
celery_app.conf.beat_schedule = {
    "daily-inspection-check": {
        "task": "app.tasks.inspection.check_due_inspections",
        "schedule": 24 * 60 * 60,  # Every 24 hours
    },
    "cleanup-old-files": {
        "task": "app.tasks.maintenance.cleanup_temp_files",
        "schedule": 6 * 60 * 60,  # Every 6 hours
    },
}