"""Persisted PPTX generation jobs shared by HTTP and Celery."""

import logging
import os
import re
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings, resolve_runtime_path
from app.models import GeneratedArtifact, GenerationJob, Lesson
from app.schemas.generation import GenerationJobListResponse, GenerationJobResponse, GenerationRequest
from app.services.generators.pptx_generator import generate_pptx
from app.services.pptagent.editor import apply_actions

logger = logging.getLogger(__name__)
settings = get_settings()
EXPORT_DIR = resolve_runtime_path(settings.upload_dir) / "exports"
TERMINAL_GENERATION_STATUSES = {"completed", "failed", "cancelled"}


class GenerationCancelled(Exception):
    """Internal cooperative cancellation signal."""


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
        cancel_requested=job.cancel_requested,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def get_generation_job(db: Session, job_id: str) -> GenerationJob:
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise LookupError("生成任务不存在")
    return job


def list_generation_jobs(
    db: Session,
    *,
    lesson_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> GenerationJobListResponse:
    """Return newest generation jobs with bounded pagination and filters."""
    query = db.query(GenerationJob)
    if lesson_id:
        query = query.filter(GenerationJob.lesson_id == lesson_id)
    if status:
        query = query.filter(GenerationJob.status == status)
    total = query.count()
    jobs = (
        query.order_by(GenerationJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return GenerationJobListResponse(
        items=[generation_job_response(job) for job in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


def _raise_if_cancelled(db: Session, job: GenerationJob) -> None:
    db.refresh(job)
    if job.cancel_requested or job.status in {"cancelling", "cancelled"}:
        raise GenerationCancelled("教师已取消课件生成")


def _mark_cancelled(db: Session, job_id: str) -> GenerationJobResponse:
    job = get_generation_job(db, job_id)
    job.status = "cancelled"
    job.progress = 100
    job.cancel_requested = True
    job.error_message = "教师已取消课件生成"
    db.commit()
    return generation_job_response(job)


def run_generation_job(
    db: Session,
    job_id: str,
    task_id: str | None = None,
) -> GenerationJobResponse:
    """Render one queued job and persist every externally visible transition."""
    job = get_generation_job(db, job_id)
    if task_id and job.task_id and task_id != job.task_id:
        return generation_job_response(job)
    if job.status in TERMINAL_GENERATION_STATUSES:
        return generation_job_response(job)
    if job.cancel_requested or job.status == "cancelling":
        return _mark_cancelled(db, job_id)

    job.status = "generating"
    job.progress = 10
    job.error_message = None
    db.commit()

    try:
        request = GenerationRequest.model_validate(job.request_json)
        lesson = db.get(Lesson, job.lesson_id)
        if lesson is None:
            raise ValueError("lesson_id 不存在")
        _raise_if_cancelled(db, job)

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
        _raise_if_cancelled(db, job)
        generate_pptx(outline, str(filepath))
        try:
            _raise_if_cancelled(db, job)
        except GenerationCancelled:
            if filepath.is_file():
                filepath.unlink()
            raise

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
    except GenerationCancelled:
        db.rollback()
        return _mark_cancelled(db, job_id)
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


def _dispatch_generation_job(db: Session, job: GenerationJob) -> GenerationJobResponse:
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

    return _dispatch_generation_job(db, job)


def cancel_generation_job(db: Session, job_id: str) -> GenerationJobResponse:
    job = get_generation_job(db, job_id)
    if job.status in {"completed", "failed", "cancelled"}:
        if job.status == "cancelled":
            return generation_job_response(job)
        raise ValueError("当前任务已进入终态，不能取消")
    job.cancel_requested = True
    if job.status == "queued":
        job.status = "cancelled"
        job.progress = 100
        job.error_message = "教师已取消课件生成"
    else:
        job.status = "cancelling"
        job.error_message = "正在等待生成器安全停止"
    db.commit()
    if job.task_id:
        try:
            from app.worker import celery_app

            celery_app.control.revoke(job.task_id, terminate=False)
        except Exception:
            logger.warning("Unable to revoke generation task %s", job.task_id, exc_info=True)
    return generation_job_response(job)


def retry_generation_job(db: Session, job_id: str) -> GenerationJobResponse:
    job = get_generation_job(db, job_id)
    if job.status not in {"failed", "cancelled"}:
        raise ValueError("只有失败或已取消的任务可以重试")
    job.status = "queued"
    job.progress = 0
    job.task_id = None
    job.cancel_requested = False
    job.error_message = None
    job.output_json = None
    job.retry_count += 1
    db.commit()
    return _dispatch_generation_job(db, job)
