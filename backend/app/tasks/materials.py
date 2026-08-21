"""Background tasks for bounded OCR and media parsing."""

import asyncio

from app.core.config import get_settings
from app.db import SessionLocal
from app.services.material_service import parse_material_record
from app.worker import celery_app

settings = get_settings()


@celery_app.task(
    bind=True,
    name="materials.parse",
    soft_time_limit=settings.material_task_soft_limit_seconds,
    time_limit=settings.material_task_hard_limit_seconds,
)
def parse_material_task(self, material_id: str) -> dict[str, object]:
    """Parse one material in a worker and persist canonical progress in SQL."""
    self.update_state(state="STARTED", meta={"material_id": material_id, "progress": 5})
    with SessionLocal() as db:
        result = asyncio.run(parse_material_record(db, material_id))
    return result.model_dump(mode="json")
