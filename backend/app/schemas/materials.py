"""Material API schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ChunkResponse(BaseModel):
    """Parsed material chunk returned to the frontend."""

    id: str
    material_id: str
    chunk_index: int
    content: str
    page_ref: Optional[int] = None
    bbox: Optional[Any] = None
    media_ref: Optional[str] = None
    modality: str
    token_count: int

    model_config = ConfigDict(from_attributes=True)


class MaterialResponse(BaseModel):
    """Uploaded material metadata."""

    file_id: str
    filename: str
    status: str
    mime: str
    extension: str
    size: int
    chunk_count: int
    created_at: datetime
    parsed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class MaterialDetailResponse(MaterialResponse):
    """Material metadata with parsed chunks."""

    chunks: list[ChunkResponse]
