"""参考资料上传 / 解析 / 查询 API。

文档 §3.2 API/v1/materials.py：上传 / 解析 / 查询。
支持 PDF / Word / PPT / 图片 / 视频。
"""

from fastapi import APIRouter, UploadFile, File, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.core.security import require_user
from app.schemas import ChunkResponse, MaterialDetailResponse, MaterialResponse
from app.services.material_service import (
    cancel_material_parse,
    create_material_from_upload,
    delete_material,
    get_material_detail,
    list_material_chunks,
    list_materials,
)

router = APIRouter(dependencies=[Depends(require_user)])


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


@router.post("/{material_id}/cancel", response_model=MaterialResponse, summary="取消材料解析")
async def cancel_uploaded_material_parse(
    material_id: str,
    db: Session = Depends(get_db),
) -> MaterialResponse:
    """Cancel a queued task or request cooperative cancellation for a running task."""
    return cancel_material_parse(db, material_id)


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除参考资料")
async def delete_uploaded_material(
    material_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Delete the material record and its managed file contents."""
    delete_material(db, material_id)
