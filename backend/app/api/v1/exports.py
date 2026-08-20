"""导出 API。

文档 §3.2 API/v1/exports.py：导出（.pptx / .docx / zip）。
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class OutlineSection(BaseModel):
    id: str
    title: str
    bullets: list[str]
    duration_minutes: int
    slide_count: int


class OutlineBody(BaseModel):
    title: str
    subject: str
    grade: str
    sections: list[OutlineSection]
    total_slides: int
    total_duration_minutes: int


@router.post("/pptx", summary="导出 PPT（基于大纲）")
async def export_pptx(outline: OutlineBody) -> dict[str, str]:
    """占位：调用 PptxGenJS 或后端 python-pptx 将 Outline 渲染为 .pptx。

    返回下载 URL，实际接入时走 MinIO 或本地文件服务。
    """
    return {
        "url": f"/exports/download/mock-outline-{outline.title}.pptx",
        "filename": f"{outline.title}.pptx",
        "status": "ready",
    }


@router.post("/lesson/{lesson_id}/pptx", summary="导出 PPT（基于 lesson_id）")
async def export_pptx(lesson_id: str) -> dict[str, str]:
    """占位：导出 .pptx。"""
    return {"lesson_id": lesson_id, "format": "pptx", "status": "queued"}


@router.post("/lesson/{lesson_id}/docx", summary="导出教案")
async def export_docx(lesson_id: str) -> dict[str, str]:
    """占位：导出 .docx。"""
    return {"lesson_id": lesson_id, "format": "docx", "status": "queued"}


@router.post("/lesson/{lesson_id}/bundle", summary="打包导出")
async def export_bundle(lesson_id: str) -> dict[str, str]:
    """占位：导出 zip 包。"""
    return {"lesson_id": lesson_id, "format": "zip", "status": "queued"}