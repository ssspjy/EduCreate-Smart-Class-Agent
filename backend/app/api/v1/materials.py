"""参考资料上传 / 解析 / 查询 API。

文档 §3.2 API/v1/materials.py：上传 / 解析 / 查询。
支持 PDF / Word / PPT / 图片 / 视频。
"""

from fastapi import APIRouter, UploadFile, File
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ChunkResponse, MaterialDetailResponse, MaterialResponse
from app.services.material_service import (
    create_material_from_upload,
    get_material_detail,
    list_material_chunks,
    list_materials,
)

router = APIRouter()


@router.post("/upload", response_model=MaterialResponse, summary="上传参考资料")
async def upload_material(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> MaterialResponse:
    """Save uploaded material, parse supported text formats, and persist chunks."""
    return await create_material_from_upload(db, file)


@router.get("", response_model=list[MaterialResponse], summary="列出参考资料")
async def list_uploaded_materials(db: Session = Depends(get_db)) -> list[MaterialResponse]:
    """List uploaded materials."""
    return list_materials(db)


@router.get("/{material_id}", response_model=MaterialDetailResponse, summary="参考资料详情")
async def get_uploaded_material(
    material_id: str,
    db: Session = Depends(get_db),
) -> MaterialDetailResponse:
    """Return material metadata and parsed chunks."""
    return get_material_detail(db, material_id)


@router.get("/{material_id}/chunks", response_model=list[ChunkResponse], summary="参考资料 chunks")
async def get_uploaded_material_chunks(
    material_id: str,
    db: Session = Depends(get_db),
) -> list[ChunkResponse]:
    """Return parsed chunks for a material."""
    return list_material_chunks(db, material_id)
