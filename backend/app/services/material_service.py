"""Material persistence and parsing service."""

from datetime import datetime
from pathlib import Path
import shutil
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings, resolve_runtime_path
from app.models import Chunk, Material
from app.schemas import ChunkResponse, MaterialDetailResponse, MaterialResponse
from app.services.parsers.parser import ParsedChunk, parse
from app.services.rag.embedder import embed_texts

# Formats currently accepted by the API. The web client advertises the
# text-extractable set (pdf/docx/pptx/md/txt); image/video and legacy Office
# files are retained for backwards-compatible persistence with an explicit
# parser warning until OCR/conversion/transcription is connected.
ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "ppt", "pptx", "md", "txt",
    "png", "jpg", "jpeg", "mp4",
}


def _safe_filename(filename: Optional[str]) -> str:
    """Strip path components and keep a stable fallback filename."""
    if not filename:
        return "unnamed"
    # Normalize both slash styles because the backend may run on Linux while
    # browsers upload a Windows-style filename.
    normalized = filename.replace("\\", "/").replace("\x00", "")
    safe = Path(normalized).name.strip()
    return safe or "unnamed"


def _extension(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def _material_to_response(material: Material) -> MaterialResponse:
    return MaterialResponse(
        file_id=material.id,
        filename=material.filename,
        status=material.status,
        mime=material.mime,
        extension=material.extension,
        size=material.size,
        chunk_count=len(material.chunks),
        created_at=material.created_at,
        parsed_at=material.parsed_at,
        error_message=material.error_message,
    )


def _material_to_detail(material: Material) -> MaterialDetailResponse:
    base = _material_to_response(material).model_dump()
    base["chunks"] = [ChunkResponse.model_validate(chunk) for chunk in material.chunks]
    return MaterialDetailResponse(**base)


async def _save_upload(file: UploadFile, target: Path, max_bytes: int) -> int:
    """Persist an UploadFile with a hard size limit."""
    size = 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as output:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                output.close()
                target.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"file exceeds {max_bytes} bytes",
                )
            output.write(chunk)
    await file.seek(0)
    return size


async def create_material_from_upload(db: Session, file: UploadFile) -> MaterialResponse:
    """Save, parse, and persist a newly uploaded reference material."""
    settings = get_settings()
    filename = _safe_filename(file.filename)
    extension = _extension(filename)
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported file extension: {extension or 'none'}",
        )

    material_id = str(uuid4())
    stored_name = f"{material_id}.{extension}"
    storage_path = resolve_runtime_path(settings.upload_dir) / material_id / stored_name
    size = await _save_upload(
        file,
        storage_path,
        max_bytes=settings.max_upload_size_mb * 1024 * 1024,
    )

    material = Material(
        id=material_id,
        filename=filename,
        mime=file.content_type or "application/octet-stream",
        extension=extension,
        size=size,
        status="parsing",
        storage_path=str(storage_path),
    )
    db.add(material)
    db.flush()

    try:
        parse_result = await parse(str(storage_path), extension)
        parsed_contents: list[str] = []
        parsed_items: list[tuple[int, ParsedChunk]] = []
        for chunk_index, parsed_chunk in enumerate(parse_result.chunks):
            content = parsed_chunk.content.strip()
            if not content:
                continue
            parsed_contents.append(content)
            parsed_items.append((chunk_index, parsed_chunk))

        embeddings = embed_texts(parsed_contents)
        for (chunk_index, parsed_chunk), content, embedding in zip(
            parsed_items, parsed_contents, embeddings, strict=True
        ):
            db.add(
                Chunk(
                    material_id=material.id,
                    chunk_index=chunk_index,
                    content=content,
                    page_ref=parsed_chunk.page_ref,
                    bbox=parsed_chunk.bbox,
                    media_ref=parsed_chunk.media_ref,
                    modality=parsed_chunk.modality,
                    token_count=len(content.split()),
                    embedding=embedding,
                )
            )

        material.parsed_at = datetime.utcnow()
        material.status = "parsed" if parse_result.chunks else "uploaded"
        material.error_message = "; ".join(parse_result.warnings) if parse_result.warnings else None
        db.commit()
    except Exception as exc:
        db.rollback()
        material = db.get(Material, material_id)
        if material is None:
            material = Material(
                id=material_id,
                filename=filename,
                mime=file.content_type or "application/octet-stream",
                extension=extension,
                size=size,
                status="failed",
                storage_path=str(storage_path),
                error_message=str(exc),
            )
            db.add(material)
        else:
            material.status = "failed"
            material.error_message = str(exc)
        db.commit()

    db.refresh(material)
    material = get_material_or_404(db, material.id)
    return _material_to_response(material)


def list_materials(db: Session) -> list[MaterialResponse]:
    """Return uploaded materials ordered newest first."""
    materials = (
        db.query(Material)
        .options(selectinload(Material.chunks))
        .order_by(Material.created_at.desc())
        .all()
    )
    return [_material_to_response(material) for material in materials]


def get_material_or_404(db: Session, material_id: str) -> Material:
    """Fetch a material with chunks or raise 404."""
    material = (
        db.query(Material)
        .options(selectinload(Material.chunks))
        .filter(Material.id == material_id)
        .one_or_none()
    )
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="material not found")
    return material


def get_material_detail(db: Session, material_id: str) -> MaterialDetailResponse:
    """Return material metadata and parsed chunks."""
    return _material_to_detail(get_material_or_404(db, material_id))


def list_material_chunks(db: Session, material_id: str) -> list[ChunkResponse]:
    """Return parsed chunks for one material."""
    material = get_material_or_404(db, material_id)
    return [ChunkResponse.model_validate(chunk) for chunk in material.chunks]


def delete_material(db: Session, material_id: str) -> None:
    """Delete a material, its chunks, and its managed upload directory."""
    material = get_material_or_404(db, material_id)
    storage_path = Path(material.storage_path).resolve()
    upload_root = resolve_runtime_path(get_settings().upload_dir).resolve()
    if upload_root not in storage_path.parents:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="material storage path is outside the upload directory",
        )

    db.delete(material)
    db.commit()
    # Files are removed only after the database commit succeeds.
    shutil.rmtree(storage_path.parent, ignore_errors=True)
