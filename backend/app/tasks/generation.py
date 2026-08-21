"""Bounded background PPTX generation task."""

from app.core.config import get_settings
from app.db import SessionLocal
from app.services.generation_service import run_generation_job
from app.worker import celery_app

settings = get_settings()


@celery_app.task(
    bind=True,
    name="generation.pptx",
    soft_time_limit=settings.generation_task_soft_limit_seconds,
    time_limit=settings.generation_task_hard_limit_seconds,
)
def generate_pptx_task(self, job_id: str) -> dict[str, object]:
    self.update_state(state="STARTED", meta={"job_id": job_id, "progress": 5})
    with SessionLocal() as db:
        result = run_generation_job(db, job_id, task_id=self.request.id)
    return result.model_dump(mode="json")
