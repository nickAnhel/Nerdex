from celery import Celery

from src.config import settings


celery_app = Celery(
    "nerdex",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
    include=["src.assets.tasks", "src.recommendations.tasks"],
)

celery_app.conf.update(
    task_default_queue=settings.celery.media_queue_name,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    beat_schedule={
        "cleanup-stale-uploads": {
            "task": "assets.cleanup_stale_uploads",
            "schedule": 60 * 30,
        },
        "cleanup-orphaned-assets": {
            "task": "assets.cleanup_orphaned_assets",
            "schedule": 60 * 60,
        },
        "reconcile-failed-assets": {
            "task": "assets.reconcile_failed_assets",
            "schedule": 60 * 60,
        },
        "recommendations-incremental-sync": {
            "task": "recommendations.incremental_sync",
            "schedule": 60 * 5,
        },
    },
)
