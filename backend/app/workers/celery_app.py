from celery import Celery

from app.config import settings

celery_app = Celery("invoice_platform")

# Configure Celery
celery_app.conf.update(
    broker_url=settings.REDIS_URL,
    result_backend=settings.REDIS_URL,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_time_limit=300,  # 5 min hard kill for runaway tasks
    beat_schedule={
        # PRD 9.1: safety-net polling sweep every 5 minutes
        "reconciliation-sweep-every-5-minutes": {
            "task": "app.workers.tasks.reconciliation_sweep",
            "schedule": 300.0,
        },
        # PRD 9.1: expire stale payment targets every 1 minute
        "expire-stale-targets-every-1-minute": {
            "task": "app.workers.tasks.expire_stale_payment_targets",
            "schedule": 60.0,
        },
    },
)

celery_app.autodiscover_tasks(["app.workers"])
