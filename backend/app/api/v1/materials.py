"""参考资料上传 / 解析 / 查询 API。

文档 §3.2 API/v1/materials.py：上传 / 解析 / 查询。
支持 PDF / Word / PPT / 图片 / 视频。
"""

from fastapi import APIRouter, UploadFile, File

router = APIRouter()


@router.post("/upload", summary="上传参考资料")
async def upload_material(file: UploadFile = File(...)) -> dict[str, str]:
    """占位：上传后返回文件 ID，后续接入 MinIO + Celery 异步解析。"""
    return {
        "file_id": "pending",
        "filename": file.filename or "unnamed",
        "status": "queued",
    }


@router.get("", summary="列出参考资料")
async def list_materials() -> list[dict[str, str]]:
    """占位：返回空列表。"""
    return []