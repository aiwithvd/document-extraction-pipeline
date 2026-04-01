from celery import Celery

from app.core.config import settings

celery_app = Celery("document_extraction")

celery_app.conf.update(
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,  # 24 hours
    task_routes={
        "app.workers.tasks.*": {"queue": "extraction"},
    },
)

celery_app.autodiscover_tasks(["app.workers"])
