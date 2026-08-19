"""导出 API。

文档 §3.2 API/v1/exports.py：导出（.pptx / .docx / zip）。
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/lesson/{lesson_id}/pptx", summary="导出 PPT")
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