"""Celery application used by the material parsing worker."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "educreate",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.materials", "app.tasks.generation"],
)
celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=20,
    result_expires=3600,
    timezone="Asia/Shanghai",
    enable_utc=True,
)
