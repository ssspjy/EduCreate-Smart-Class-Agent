"""PPT 导出 API。

文档 §3.2 API/v1/exports.py：
- POST /exports/pptx  — 基于大纲生成 PPTX 文件
- GET  /exports/{filename} — 下载已生成的 PPTX 文件
"""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import get_settings, resolve_runtime_path
from app.services.generators.pptx_generator import generate_pptx

logger = logging.getLogger(__name__)
router = APIRouter()

settings = get_settings()
EXPORT_DIR = resolve_runtime_path(settings.upload_dir) / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


class PptxExportRequest(BaseModel):
    """导出请求（与 OutlineResponse 结构对齐）。"""
    title: str
    subject: str = ""
    grade: str = ""
    sections: list[dict]  # OutlineSection[]


@router.post("/pptx", summary="导出 PPTX 文件")
async def export_pptx(body: PptxExportRequest) -> dict:
    """基于大纲结构生成 PPTX 文件。

    文件存储在 uploads/exports/ 目录，通过 GET /exports/{filename} 下载。
    """
    try:
        filename = f"{body.title.replace(' ', '_')}_{os.urandom(4).hex()}.pptx"
        filepath = EXPORT_DIR / filename

        generate_pptx(body.dict(), str(filepath))

        # 返回相对路径，前端拼接 API_BASE
        url = f"/api/v1/exports/{filename}"
        logger.info("[Export] PPTX 生成成功：%s", filepath)

        return {"url": url, "filename": filename}

    except Exception as exc:
        logger.error("[Export] PPTX 生成失败：%s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PPT 导出失败：{exc}",
        ) from exc


@router.get("/{filename}", summary="下载 PPTX 文件")
async def download_pptx(filename: str) -> FileResponse:
    """下载已导出的 PPTX 文件。"""
    # 安全检查：禁止路径穿越
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="非法文件名",
        )

    filepath = EXPORT_DIR / filename
    if not filepath.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文件不存在：{filename}",
        )

    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
