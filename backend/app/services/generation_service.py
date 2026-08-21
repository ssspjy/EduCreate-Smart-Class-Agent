"""Persisted PPTX generation jobs shared by HTTP and Celery."""

import logging
import os
import re
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings, resolve_runtime_path
from app.models import GeneratedArtifact, GenerationJob, Lesson
from app.schemas.generation import GenerationJobResponse, GenerationRequest
from app.services.generators.pptx_generator import generate_pptx
from app.services.pptagent.editor import apply_actions

logger = logging.getLogger(__name__)
settings = get_settings()
EXPORT_DIR = resolve_runtime_path(settings.upload_dir) / "exports"
TERMINAL_GENERATION_STATUSES = {"completed", "failed"}


def _safe_export_stem(title: str) -> str:
    stem = re.sub(r"[^\w\-.\u4e00-\u9fff]+", "_", title.strip(), flags=re.UNICODE)
    return (stem.strip("._") or "lesson")[:100]


def generation_job_response(job: GenerationJob) -> GenerationJobResponse:
    return GenerationJobResponse(
        job_id=job.id,
        lesson_id=job.lesson_id,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        task_id=job.task_id,
        output=job.output_json,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def get_generation_job(db: Session, job_id: str) -> GenerationJob:
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise LookupError("生成任务不存在")
    return job


def run_generation_job(db: Session, job_id: str) -> GenerationJobResponse:
    """Render one queued job and persist every externally visible transition."""
    job = get_generation_job(db, job_id)
    if job.status in TERMINAL_GENERATION_STATUSES:
        return generation_job_response(job)

    job.status = "generating"
    job.progress = 10
    job.error_message = None
    db.commit()

    try:
        request = GenerationRequest.model_validate(job.request_json)
        lesson = db.get(Lesson, job.lesson_id)
        if lesson is None:
            raise ValueError("lesson_id 不存在")

        outline = request.model_dump(exclude={"lesson_id", "actions"})
        if request.actions:
            outline, _, warnings = apply_actions(outline, request.actions)
        else:
            warnings = []

        latest = db.query(func.max(GeneratedArtifact.version)).filter(
            GeneratedArtifact.lesson_id == job.lesson_id,
            GeneratedArtifact.type == "pptx",
        ).scalar()
        version = int(latest or 0) + 1
        filename = f"{_safe_export_stem(request.title)}_{os.urandom(4).hex()}.pptx"
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        filepath = EXPORT_DIR / filename

        job.progress = 45
        db.commit()
        generate_pptx(outline, str(filepath))

        artifact = GeneratedArtifact(
            job_id=job.id,
            lesson_id=job.lesson_id,
            type="pptx",
            version=version,
            storage_path=str(filepath),
        )
        db.add(artifact)
        db.flush()
        job.output_json = {
            "url": f"/api/v1/exports/{filename}",
            "filename": filename,
            "artifact_id": artifact.id,
            "version": version,
            "warnings": warnings,
        }
        job.status = "completed"
        job.progress = 100
        lesson.status = "courseware_ready"
        db.commit()
        db.refresh(job)
        logger.info("[Generation] PPTX 任务完成：job=%s file=%s", job.id, filepath)
    except Exception as exc:
        db.rollback()
        job = db.get(GenerationJob, job_id)
        if job is None:
            raise
        job.status = "failed"
        job.progress = 100
        job.error_message = str(exc)
        db.commit()
        logger.exception("[Generation] PPTX 任务失败：job=%s", job_id)

    return generation_job_response(get_generation_job(db, job_id))


def create_generation_job(db: Session, request: GenerationRequest) -> GenerationJobResponse:
    if db.get(Lesson, request.lesson_id) is None:
        raise LookupError("lesson_id 不存在")

    job = GenerationJob(
        lesson_id=request.lesson_id,
        job_type="pptx",
        status="queued",
        progress=0,
        request_json=request.model_dump(mode="json"),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if not settings.generation_async_enabled:
        return run_generation_job(db, job.id)

    try:
        from app.tasks.generation import generate_pptx_task

        async_result = generate_pptx_task.delay(job.id)
        job.task_id = async_result.id
        db.commit()
        db.refresh(job)
        return generation_job_response(job)
    except Exception as exc:
        logger.exception("Generation task publish failed; falling back inline: %s", exc)
        job.error_message = "任务队列不可用，已退回同步生成"
        db.commit()
        return run_generation_job(db, job.id)
