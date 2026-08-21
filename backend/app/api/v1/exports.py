"""PPT 导出 API。

文档 §3.2 API/v1/exports.py：
- POST /exports/pptx  — 基于大纲生成 PPTX 文件
- GET  /exports/{filename} — 下载已生成的 PPTX 文件
"""

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings, resolve_runtime_path
from app.services.generators.pptx_generator import generate_pptx
from app.services.generators.docx_generator import generate_docx
from app.core.security import require_user
from app.db import SessionLocal, get_db
from app.models import GeneratedArtifact, GenerationJob, Lesson
from app.schemas.generation import GenerationJobResponse, GenerationRequest
from app.schemas.pptagent import PptEditAction
from app.services.generation_service import (
    TERMINAL_GENERATION_STATUSES,
    create_generation_job,
    cancel_generation_job,
    generation_job_response,
    get_generation_job,
    retry_generation_job,
)
from app.services.pptagent.editor import apply_actions

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_user)])

settings = get_settings()
EXPORT_DIR = resolve_runtime_path(settings.upload_dir) / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
SSE_MAX_SECONDS = 330


class PptxExportRequest(BaseModel):
    """导出请求（与 OutlineResponse 结构对齐）。"""
    title: str
    subject: str = ""
    grade: str = ""
    sections: list[dict]  # OutlineSection[]
    lesson_id: str | None = None
    actions: list[PptEditAction] = Field(default_factory=list, max_length=30)


class DocxExportRequest(PptxExportRequest):
    """DOCX export uses the same outline payload as PPTX."""


def _safe_export_stem(title: str) -> str:
    """Convert a user title into a flat, filesystem-safe filename stem."""
    stem = re.sub(r"[^\w\-.\u4e00-\u9fff]+", "_", title.strip(), flags=re.UNICODE)
    stem = stem.strip("._")
    return (stem or "lesson")[:100]


@router.post("/pptx", summary="导出 PPTX 文件")
async def export_pptx(body: PptxExportRequest, db: Session = Depends(get_db)) -> dict:
    """基于大纲结构生成 PPTX 文件。

    文件存储在 uploads/exports/ 目录，通过 GET /exports/{filename} 下载。
    """
    try:
        filename = f"{_safe_export_stem(body.title)}_{os.urandom(4).hex()}.pptx"
        filepath = EXPORT_DIR / filename

        outline = body.dict(exclude={"lesson_id", "actions"})
        if body.actions:
            outline, _, warnings = apply_actions(outline, body.actions)
        else:
            warnings = []
        artifact_id = None
        version = None
        if body.lesson_id:
            if db.get(Lesson, body.lesson_id) is None:
                raise HTTPException(status_code=404, detail="lesson_id 不存在")
            latest = db.query(func.max(GeneratedArtifact.version)).filter(
                GeneratedArtifact.lesson_id == body.lesson_id,
                GeneratedArtifact.type == "pptx",
            ).scalar()
            version = int(latest or 0) + 1
        generate_pptx(outline, str(filepath))
        if body.lesson_id:
            artifact = GeneratedArtifact(
                lesson_id=body.lesson_id,
                type="pptx",
                version=version,
                storage_path=str(filepath),
            )
            db.add(artifact)
            db.commit()
            db.refresh(artifact)
            artifact_id = artifact.id

        # 返回相对路径，前端拼接 API_BASE
        url = f"/api/v1/exports/{filename}"
        logger.info("[Export] PPTX 生成成功：%s", filepath)

        return {"url": url, "filename": filename, "artifact_id": artifact_id, "version": version, "warnings": warnings}

    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        logger.error("[Export] PPTX 生成失败：%s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PPT 导出失败：{exc}",
        ) from exc


@router.post("/docx", summary="导出 DOCX 教案")
async def export_docx(body: DocxExportRequest) -> dict:
    """Render the outline as a valid Word lesson plan."""
    try:
        filename = f"{_safe_export_stem(body.title)}_{os.urandom(4).hex()}.docx"
        filepath = EXPORT_DIR / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(generate_docx(body.model_dump()))
        url = f"/api/v1/exports/{filename}"
        logger.info("[Export] DOCX 生成成功：%s", filepath)
        return {"url": url, "filename": filename}
    except Exception as exc:
        logger.error("[Export] DOCX 生成失败：%s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"DOCX 导出失败：{exc}",
        ) from exc


@router.post(
    "/pptx/jobs",
    response_model=GenerationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建 PPTX 后台生成任务",
)
async def create_pptx_job(
    body: GenerationRequest,
    db: Session = Depends(get_db),
) -> GenerationJobResponse:
    """Persist the request before dispatching it to the existing Celery worker."""
    try:
        return create_generation_job(db, body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/jobs/{job_id}", response_model=GenerationJobResponse, summary="查询课件生成任务")
async def get_pptx_job(job_id: str, db: Session = Depends(get_db)) -> GenerationJobResponse:
    try:
        return generation_job_response(get_generation_job(db, job_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/cancel", response_model=GenerationJobResponse, summary="取消课件生成任务")
async def cancel_pptx_job(job_id: str, db: Session = Depends(get_db)) -> GenerationJobResponse:
    try:
        return cancel_generation_job(db, job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/retry", response_model=GenerationJobResponse, summary="重试课件生成任务")
async def retry_pptx_job(job_id: str, db: Session = Depends(get_db)) -> GenerationJobResponse:
    try:
        return retry_generation_job(db, job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/events", summary="订阅课件生成 SSE 事件")
async def generation_events(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    if db.get(GenerationJob, job_id) is None:
        raise HTTPException(status_code=404, detail="生成任务不存在")

    async def event_stream():
        deadline = time.monotonic() + SSE_MAX_SECONDS
        while time.monotonic() < deadline:
            if await request.is_disconnected():
                break
            with SessionLocal() as session:
                job = session.get(GenerationJob, job_id)
                if job is None:
                    break
                payload = generation_job_response(job).model_dump(mode="json")
                status_value = job.status
            yield f"event: generation\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if status_value in TERMINAL_GENERATION_STATUSES:
                break
            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/{filename}", summary="下载导出文件")
async def download_export(filename: str) -> FileResponse:
    """Download a generated PPTX or DOCX file."""
    # 安全检查：禁止路径穿越
    if (
        ".." in filename
        or "/" in filename
        or "\\" in filename
        or Path(filename).suffix.lower() not in {".pptx", ".docx"}
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="非法文件名",
        )

    filepath = EXPORT_DIR / filename
    if not filepath.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文件不存在：{filename}",
        )

    media_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if filepath.suffix.lower() == ".docx"
        else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type=media_type,
    )
